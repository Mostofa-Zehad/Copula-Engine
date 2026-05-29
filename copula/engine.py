"""
Gaussian Copula Load Uncertainty Engine
Adapted from the original NYISO copula pipeline for web deployment.
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata
from sklearn.covariance import LedoitWolf

DOWNSTATE_ZONES = ["Zone I", "Zone J", "Zone K"]
ZONE_LETTERS    = "ABCDEFGHIJK"

# US Federal holidays (month, day) — fixed-date ones
_FIXED_HOLIDAYS = {
    (1,  1): "New Year's Day",
    (6, 19): "Juneteenth",
    (7,  4): "Independence Day",
    (11,11): "Veterans Day",
    (12,25): "Christmas Day",
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC HELPERS (used by app.py endpoints)
# ─────────────────────────────────────────────────────────────────────────────
def detect_day_type(ts: pd.Timestamp, holiday_file: Optional[Path] = None) -> dict:
    """
    Return day_type ('weekday'|'weekend'|'holiday'), holiday name, and
    a human-readable label for the given timestamp.
    """
    ts = pd.Timestamp(ts)
    dow = ts.dayofweek          # 0=Mon … 6=Sun
    m, d, y = ts.month, ts.day, ts.year

    # Check fixed federal holidays
    holiday_name = _FIXED_HOLIDAYS.get((m, d))

    # Check floating holidays via the Excel calendar if available
    if holiday_name is None and holiday_file and holiday_file.exists():
        try:
            cal = pd.read_excel(holiday_file, usecols=[0, 1, 2])
            cal.columns = cal.columns[:3]
            cal.rename(columns={cal.columns[0]: "Date"}, inplace=True)
            cal["Date"] = pd.to_datetime(cal["Date"], errors="coerce")
            row = cal[cal["Date"].dt.normalize() == ts.normalize()]
            if not row.empty:
                # Try to find IsHoliday column
                for col in row.columns:
                    if "holiday" in str(col).lower() and col != "Date":
                        if int(row.iloc[0][col]) == 1:
                            # Try to get holiday name from another column
                            for nc in row.columns:
                                v = str(row.iloc[0][nc])
                                if v not in ("0", "1", "nan") and nc != "Date":
                                    holiday_name = v
                                    break
                            if not holiday_name:
                                holiday_name = "Federal Holiday"
                            break
        except Exception:
            pass

    if holiday_name:
        day_type = "holiday"
    elif dow >= 5:
        day_type = "weekend"
    else:
        day_type = "weekday"

    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    label = f"{ts.strftime('%B %-d, %Y')} — {day_names[dow]}"

    return {
        "day_type":     day_type,
        "holiday_name": holiday_name,
        "label":        label,
        "weekday_num":  dow,
    }


def lookup_weather(ts: pd.Timestamp, zone_a_path: Path) -> Optional[float]:
    """Return HDH for a given date from Zone A's Weather sheet, or None."""
    ts = pd.Timestamp(ts).normalize()
    hdh_series = _load_weather(zone_a_path)
    if ts in hdh_series.index:
        return float(hdh_series.loc[ts])
    # Try nearest year (same month+day, most recent year before ts)
    for yr_delta in range(1, 15):
        ref = ts.replace(year=ts.year - yr_delta)
        if ref in hdh_series.index:
            return float(hdh_series.loc[ref])
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PARAMETER + RESULT CLASSES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class CopulaParams:
    target_date: str
    forecast_24h: List[float]
    hdh: Optional[float] = None          # auto-filled if None
    day_type: Optional[str] = None       # auto-detected if None
    historical_years: int = 5
    day_window: int = 30                 # ±days around target day-of-year
    n_scenarios: int = 50
    seed: int = 42
    data_dir: Path = Path("data")
    w_peak: float = 0.30
    w_energy: float = 0.25
    w_ramp: float = 0.15
    w_downstate: float = 0.15
    w_weather: float = 0.10
    w_recency: float = 0.05
    min_err: float = -0.95

    def __post_init__(self):
        self.target_ts = pd.Timestamp(self.target_date)
        self.forecast_array = np.array(self.forecast_24h, dtype=float)
        if len(self.forecast_array) != 24:
            raise ValueError("Forecast must have exactly 24 hourly values")
        total_w = (self.w_peak + self.w_energy + self.w_ramp +
                   self.w_downstate + self.w_weather + self.w_recency)
        if abs(total_w - 1.0) > 0.02:
            self.w_peak      /= total_w
            self.w_energy    /= total_w
            self.w_ramp      /= total_w
            self.w_downstate /= total_w
            self.w_weather   /= total_w
            self.w_recency   /= total_w


@dataclass
class ScenarioResult:
    total_scenarios: np.ndarray
    zonal_cube: np.ndarray
    zone_names: List[str]
    tgt_forecast: np.ndarray
    analog_df: pd.DataFrame
    sampling_probs: np.ndarray
    shrink_coeff: float
    n_dimensions: int
    n_analogs: int
    target_date: pd.Timestamp
    n_scenarios: int
    seed: int
    params: CopulaParams
    day_type: str
    hdh_used: Optional[float]

    def get_metrics_dict(self) -> dict:
        S = self.total_scenarios
        smean = S.mean(axis=0)
        sstd  = S.std(axis=0, ddof=1)
        pcts  = {str(q): np.percentile(S, q, axis=0).tolist()
                 for q in [1, 5, 10, 25, 50, 75, 90, 95, 99]}
        daily_E   = S.sum(axis=1)
        peak_hr   = S.argmax(axis=1) + 1
        ramps     = np.diff(S, axis=1)
        corr_mat  = np.corrcoef(S, rowvar=False)
        adj_corr  = np.array([corr_mat[h, h+1] for h in range(23)])
        peak_hr_freq = (pd.Series(peak_hr)
                        .value_counts()
                        .reindex(range(1, 25), fill_value=0)
                        .sort_index())

        reserve_up_p90 = np.maximum(np.percentile(S, 90, axis=0) - self.tgt_forecast, 0)
        reserve_up_p95 = np.maximum(np.percentile(S, 95, axis=0) - self.tgt_forecast, 0)
        reserve_up_p99 = np.maximum(np.percentile(S, 99, axis=0) - self.tgt_forecast, 0)
        reserve_dn_p10 = np.maximum(self.tgt_forecast - np.percentile(S, 10, axis=0), 0)
        reserve_dn_p05 = np.maximum(self.tgt_forecast - np.percentile(S,  5, axis=0), 0)
        reserve_dn_p01 = np.maximum(self.tgt_forecast - np.percentile(S,  1, axis=0), 0)
        band_width     = np.percentile(S, 95, axis=0) - np.percentile(S, 5, axis=0)
        crps_vec       = np.array([_crps(S[:, h], smean[h]) for h in range(24)])

        zone_daily = []
        for zi, z in enumerate(self.zone_names):
            zs = self.zonal_cube[:, zi, :].sum(axis=1)
            zone_daily.append({
                "zone":      z,
                "mean":      float(round(zs.mean(), 1)),
                "std":       float(round(zs.std(ddof=1), 1)),
                "p05":       float(round(np.percentile(zs, 5), 1)),
                "p95":       float(round(np.percentile(zs, 95), 1)),
                "peak_mean": float(round(self.zonal_cube[:, zi, :].max(axis=1).mean(), 1)),
            })

        return {
            "hours":          list(range(1, 25)),
            "smean":          smean.tolist(),
            "sstd":           sstd.tolist(),
            "pcts":           pcts,
            "daily_E":        daily_E.tolist(),
            "daily_E_mean":   float(round(daily_E.mean(), 1)),
            "daily_E_p05":    float(round(np.percentile(daily_E, 5), 1)),
            "daily_E_p95":    float(round(np.percentile(daily_E, 95), 1)),
            "peak_hr":        peak_hr.tolist(),
            "peak_hr_freq":   peak_hr_freq.values.tolist(),
            "peak_hr_mode":   int(peak_hr_freq.idxmax()),
            "peak_hr_mode_pct": float(round(100.0 * peak_hr_freq.max() / self.n_scenarios, 1)),
            "ramps":          ramps.tolist(),
            "adj_corr":       adj_corr.tolist(),
            "adj_corr_mean":  float(round(adj_corr.mean(), 4)),
            "corr_mat":       corr_mat.tolist(),
            "total_scenarios": self.total_scenarios.tolist(),
            "tgt_forecast":   self.tgt_forecast.tolist(),
            "zone_names":     self.zone_names,
            "zone_daily":     zone_daily,
            "target_date":    self.target_date.date().isoformat(),
            "n_scenarios":    self.n_scenarios,
            "n_analogs":      self.n_analogs,
            "shrink_coeff":   round(self.shrink_coeff, 4),
            "n_dimensions":   self.n_dimensions,
            "day_type":       self.day_type,
            "hdh_used":       self.hdh_used,
            "reserve_up_p90": reserve_up_p90.tolist(),
            "reserve_up_p95": reserve_up_p95.tolist(),
            "reserve_up_p99": reserve_up_p99.tolist(),
            "reserve_dn_p10": reserve_dn_p10.tolist(),
            "reserve_dn_p05": reserve_dn_p05.tolist(),
            "reserve_dn_p01": reserve_dn_p01.tolist(),
            "band_width":     band_width.tolist(),
            "crps_vec":       crps_vec.tolist(),
            "mean_crps":      float(round(crps_vec.mean(), 2)),
            "cv_pct":         (100.0 * sstd / np.maximum(smean, 1.0)).tolist(),
        }


def _crps(scenarios: np.ndarray, reference: float) -> float:
    t1 = np.mean(np.abs(scenarios - reference))
    t2 = 0.5 * np.mean(np.abs(scenarios[:, None] - scenarios[None, :]))
    return float(t1 - t2)


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────
def _load_zone(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
        df["Time Stamp"] = pd.to_datetime(df["Time Stamp"])
        if "Date" not in df.columns:
            df["Date"] = df["Time Stamp"].dt.floor("D")
        if "Hour" not in df.columns:
            df["Hour"] = df["Time Stamp"].dt.hour + 1
        return df.sort_values("Time Stamp").reset_index(drop=True)

    df = pd.read_excel(path, sheet_name="Combined Load Error")
    rename = {}
    for c in df.columns:
        cl = str(c).strip().lower()
        if "time" in cl:                       rename[c] = "Time Stamp"
        elif "actual" in cl:                   rename[c] = "Actual"
        elif "forecast" in cl:                 rename[c] = "Forecast"
        elif cl in ["error (mw)", "error mw"]: rename[c] = "Error_MW"
        elif cl in ["error (%)", "error %"]:   rename[c] = "Error_pct"
    df = df.rename(columns=rename)
    df["Time Stamp"] = pd.to_datetime(df["Time Stamp"])
    df["Date"] = df["Time Stamp"].dt.floor("D")
    df["Hour"] = df["Time Stamp"].dt.hour + 1
    return df.sort_values("Time Stamp").reset_index(drop=True)


def _load_weather(path: Path) -> pd.Series:
    # Try Parquet first (fast)
    pq = path.parent / "parquet" / "zone_A_weather.parquet"
    if pq.exists():
        try:
            df = pd.read_parquet(pq)
            if "Date" in df.columns and "HDH" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                return df.dropna(subset=["HDH"]).set_index("Date")["HDH"]
        except Exception:
            pass
    # Fall back to Excel
    try:
        df = pd.read_excel(path, sheet_name="Weather", header=1)
        col_map = {}
        for c in df.columns:
            cl = str(c).strip().lower()
            if "date" in cl:  col_map[c] = "Date"
            elif "hdh" in cl: col_map[c] = "HDH"
        df = df.rename(columns=col_map)
        if "Date" not in df.columns or "HDH" not in df.columns:
            return pd.Series(dtype=float)
        df["Date"] = pd.to_datetime(df["Date"])
        return df.dropna(subset=["HDH"]).set_index("Date")["HDH"]
    except Exception:
        return pd.Series(dtype=float)


def _day_profile(zone_df: pd.DataFrame, date: pd.Timestamp,
                 col: str) -> Optional[np.ndarray]:
    rows = zone_df.loc[zone_df["Date"] == date].sort_values("Hour")
    if len(rows) != 24:
        return None
    return rows[col].to_numpy(dtype=float)


def _nearest_psd(R: np.ndarray) -> np.ndarray:
    R = (R + R.T) / 2.0
    ev, ec = np.linalg.eigh(R)
    ev = np.clip(ev, 1e-8, None)
    Rpsd = (ec * ev) @ ec.T
    d = np.sqrt(np.diag(Rpsd))
    Rpsd = Rpsd / np.outer(d, d)
    np.fill_diagonal(Rpsd, 1.0)
    return Rpsd


def _circular_doy_distance(d1: pd.Timestamp, d2: pd.Timestamp) -> int:
    """Day-of-year distance, circular so Dec 31 ↔ Jan 1 = 1 day."""
    doy1 = d1.timetuple().tm_yday
    doy2 = d2.timetuple().tm_yday
    diff = abs(doy1 - doy2)
    return min(diff, 366 - diff)


def _estimate_downstate(zone_hist: Dict[str, pd.DataFrame],
                        target_ts: pd.Timestamp,
                        tgt_forecast: np.ndarray) -> np.ndarray:
    for delta in range(1, 730):
        ref = target_ts - pd.Timedelta(days=delta)
        ds, tot, ok = np.zeros(24), np.zeros(24), True
        for z, df in zone_hist.items():
            f = _day_profile(df, ref, "Forecast")
            if f is None: ok = False; break
            tot += f
            if z in DOWNSTATE_ZONES: ds += f
        if ok and tot.sum() > 0:
            return (ds / np.maximum(tot, 1.0)) * tgt_forecast
    return tgt_forecast * 0.55


def _find_zone_files(data_dir: Path) -> Dict[str, Path]:
    zone_files: Dict[str, Path] = {}
    pq_dir = data_dir / "parquet"
    for z in ZONE_LETTERS:
        # Prefer Parquet (fast) — falls back to Excel if not yet converted
        pq = pq_dir / f"zone_{z}.parquet"
        if pq.exists():
            zone_files[f"Zone {z}"] = pq
            continue
        for name in [f"Zone {z} Combined Data (Full Year 2011-2025).xlsx",
                     f"Zone {z} Combined Data.xlsx",
                     f"Zone_{z}_Combined_Data.xlsx"]:
            p = data_dir / name
            if p.exists():
                zone_files[f"Zone {z}"] = p
                break
        if f"Zone {z}" not in zone_files:
            raise FileNotFoundError(
                f"Data file for Zone {z} not found in {data_dir}. "
                "Run convert_to_parquet.py or copy Excel files into data/.")
    return zone_files


def _find_holiday_file(data_dir: Path) -> Optional[Path]:
    for fn in ["Holiday Calendar Full Year (2011-2025).xlsx",
               "Holiday Calender NDJ (2019-2026).xlsx",
               "Holiday_Calendar.xlsx"]:
        p = data_dir / fn
        if p.exists():
            return p
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN COPULA PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
def run_copula(params: CopulaParams) -> ScenarioResult:
    data_dir  = params.data_dir
    target_ts = params.target_ts
    tgt_year  = target_ts.year

    # ── Locate data files ─────────────────────────────────────────────────────
    zone_files   = _find_zone_files(data_dir)
    holiday_file = _find_holiday_file(data_dir)
    zone_names   = [f"Zone {z}" for z in ZONE_LETTERS]

    # ── Auto-detect day type ──────────────────────────────────────────────────
    day_info = detect_day_type(target_ts, holiday_file)
    day_type = params.day_type or day_info["day_type"]

    # ── Load zone data ────────────────────────────────────────────────────────
    zone_hist = {z: _load_zone(zone_files[z]) for z in zone_names}

    # ── Auto-lookup weather ───────────────────────────────────────────────────
    hdh_used = params.hdh
    if hdh_used is None:
        hdh_used = lookup_weather(target_ts, zone_files["Zone A"])

    system_hdh = _load_weather(zone_files["Zone A"])

    # ── Load / build calendar ─────────────────────────────────────────────────
    cal = None
    if holiday_file:
        try:
            cal = pd.read_excel(holiday_file)
            # Normalise column names — accept "date", "Date", "DATE", etc.
            col_map = {c: c.strip() for c in cal.columns}
            cal = cal.rename(columns=col_map)
            date_col = next((c for c in cal.columns
                             if str(c).strip().lower() == "date"), None)
            if date_col and date_col != "Date":
                cal = cal.rename(columns={date_col: "Date"})
            if "Date" not in cal.columns:
                cal = None          # fall through to synthetic calendar
            else:
                cal["Date"] = pd.to_datetime(cal["Date"], errors="coerce")
                cal = cal.dropna(subset=["Date"])
                if "IsHoliday" not in cal.columns:
                    cal["IsHoliday"] = 0
                if "IsWeekend" not in cal.columns:
                    cal["IsWeekend"] = (cal["Date"].dt.dayofweek >= 5).astype(int)
                if "Month" not in cal.columns:
                    cal["Month"] = cal["Date"].dt.month
        except Exception:
            cal = None

    if cal is None:
        dates = pd.date_range("2011-01-01", "2025-12-31", freq="D")
        cal = pd.DataFrame({
            "Date":      dates,
            "Month":     dates.month,
            "IsWeekend": (dates.dayofweek >= 5).astype(int),
            "IsHoliday": 0,
        })

    # ── Target-day profiles ───────────────────────────────────────────────────
    tgt_forecast  = params.forecast_array.copy()
    tgt_downstate = _estimate_downstate(zone_hist, target_ts, tgt_forecast)

    # ── Candidate analog days — filtered by day_window ────────────────────────
    earliest = tgt_year - params.historical_years

    if day_type == "weekday":
        type_mask = (cal["IsWeekend"] == 0) & (cal["IsHoliday"] == 0)
    elif day_type == "weekend":
        type_mask = cal["IsWeekend"] == 1
    elif day_type == "holiday":
        type_mask = cal["IsHoliday"] == 1
    else:
        type_mask = pd.Series(True, index=cal.index)

    all_dates = cal.loc[
        (cal["Date"] < target_ts) &
        (cal["Date"].dt.year >= earliest) &
        type_mask,
        "Date"
    ].tolist()

    # Apply circular day-of-year window
    candidates = [
        d for d in all_dates
        if _circular_doy_distance(d, target_ts) <= params.day_window
    ]

    if len(candidates) < 10:
        raise ValueError(
            f"Only {len(candidates)} analog candidates found with ±{params.day_window}-day window. "
            f"Try a wider window (±1 month or ±2 months) or more historical years."
        )

    # ── Score analog days ─────────────────────────────────────────────────────
    tgt_peak   = tgt_forecast.max()
    tgt_energy = tgt_forecast.sum()
    tgt_ramps  = np.diff(tgt_forecast)
    ramp_scale = max(np.abs(tgt_ramps).mean(), 1.0)
    ds_scale   = max(tgt_downstate.mean(), 1.0)

    rows = []
    for d in candidates:
        tf, ds, ok = np.zeros(24), np.zeros(24), True
        for z in zone_names:
            f = _day_profile(zone_hist[z], d, "Forecast")
            if f is None: ok = False; break
            tf += f
            if z in DOWNSTATE_ZONES: ds += f
        if not ok:
            continue

        peak_s   = abs(tf.max() - tgt_peak)   / max(tgt_peak, 1.0)
        energy_s = abs(tf.sum() - tgt_energy) / max(tgt_energy, 1.0)
        ramp_s   = np.abs(np.diff(tf) - tgt_ramps).mean() / ramp_scale
        ds_s     = np.abs(ds - tgt_downstate).mean() / ds_scale
        yr_s     = abs(d.year - tgt_year) / max(params.historical_years, 1.0)

        if (hdh_used is not None and len(system_hdh) > 0
                and d in system_hdh.index):
            wx_s = abs(float(system_hdh.loc[d]) - hdh_used) / max(abs(hdh_used) + 1.0, 1.0)
        else:
            wx_s = 0.0

        dist = (params.w_peak      * peak_s  +
                params.w_energy    * energy_s +
                params.w_ramp      * ramp_s   +
                params.w_downstate * ds_s     +
                params.w_weather   * wx_s     +
                params.w_recency   * yr_s)

        rows.append({
            "Date": d, "Dist": dist, "Year": d.year,
            "DOY_Distance": _circular_doy_distance(d, target_ts),
            "Peak_Score":   round(peak_s, 4),
            "Energy_Score": round(energy_s, 4),
            "Ramp_Score":   round(ramp_s, 4),
            "DS_Score":     round(ds_s, 4),
            "Weather_Score":round(wx_s, 4),
            "Recency_Score":round(yr_s, 4),
            "Sys_Fcst_Peak": round(tf.max(), 1),
        })

    if not rows:
        raise ValueError("No analog days with complete zone data found.")

    analog_df = pd.DataFrame(rows).sort_values("Dist").reset_index(drop=True)
    inv_dist  = 1.0 / (analog_df["Dist"].values + 1e-9)
    probs     = inv_dist / inv_dist.sum()
    analog_df["Sample_Weight_pct"] = (probs * 100).round(4)
    n_all = len(analog_df)

    # ── Build error matrix ────────────────────────────────────────────────────
    p = len(zone_names) * 24
    X = np.empty((n_all, p))
    for i, d in enumerate(analog_df["Date"].tolist()):
        col = 0
        for z in zone_names:
            e = _day_profile(zone_hist[z], d, "Error_pct")
            X[i, col:col+24] = e / 100.0
            col += 24
    X = np.clip(X, params.min_err, 2.0)

    # ── Fit Gaussian copula ───────────────────────────────────────────────────
    U = np.empty_like(X)
    for j in range(p):
        rk = rankdata(X[:, j], method="average")
        U[:, j] = rk / (n_all + 1.0)

    Z  = norm.ppf(np.clip(U, 1e-6, 1.0 - 1e-6))
    lw = LedoitWolf(assume_centered=True).fit(Z)
    R  = lw.covariance_.copy()
    dv = np.sqrt(np.diag(R))
    R  = R / np.outer(dv, dv)
    np.fill_diagonal(R, 1.0)
    R  = _nearest_psd(R)
    shrink = float(lw.shrinkage_)

    # ── Generate 50 scenarios ─────────────────────────────────────────────────
    rng  = np.random.default_rng(params.seed)
    chol = np.linalg.cholesky(R + 1e-10 * np.eye(p))
    Z_sim = rng.standard_normal((params.n_scenarios, p)) @ chol.T
    U_sim = norm.cdf(Z_sim)

    # ── Back-transform ────────────────────────────────────────────────────────
    Fmat = np.zeros((len(zone_names), 24))
    for zi, z in enumerate(zone_names):
        f = _day_profile(zone_hist[z], target_ts, "Forecast")
        if f is not None:
            Fmat[zi, :] = f
        else:
            for delta in range(1, 730):
                ref    = target_ts - pd.Timedelta(days=delta)
                zone_f = _day_profile(zone_hist[z], ref, "Forecast")
                if zone_f is None: continue
                tot = np.zeros(24); ok2 = True
                for zz in zone_names:
                    ff = _day_profile(zone_hist[zz], ref, "Forecast")
                    if ff is None: ok2 = False; break
                    tot += ff
                if ok2 and tot.sum() > 0:
                    Fmat[zi, :] = (zone_f / np.maximum(tot, 1.0)) * tgt_forecast
                    break
            else:
                Fmat[zi, :] = tgt_forecast / len(zone_names)

    zonal_cube = np.zeros((params.n_scenarios, len(zone_names), 24))
    for zi in range(len(zone_names)):
        for h in range(24):
            hist_err = np.maximum(X[:, zi * 24 + h], params.min_err)
            order    = np.argsort(hist_err)
            e_sorted = hist_err[order]
            w_sorted = probs[order]
            cdf_w    = np.cumsum(w_sorted); cdf_w /= cdf_w[-1]
            e_samp   = np.interp(U_sim[:, zi * 24 + h], cdf_w, e_sorted)
            e_samp   = np.maximum(e_samp, params.min_err)
            zonal_cube[:, zi, h] = Fmat[zi, h] / (1.0 + e_samp)

    total_scenarios = zonal_cube.sum(axis=1)

    return ScenarioResult(
        total_scenarios = total_scenarios,
        zonal_cube      = zonal_cube,
        zone_names      = zone_names,
        tgt_forecast    = tgt_forecast,
        analog_df       = analog_df,
        sampling_probs  = probs,
        shrink_coeff    = shrink,
        n_dimensions    = p,
        n_analogs       = n_all,
        target_date     = target_ts,
        n_scenarios     = params.n_scenarios,
        seed            = params.seed,
        params          = params,
        day_type        = day_type,
        hdh_used        = hdh_used,
    )


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL EXPORT
# ─────────────────────────────────────────────────────────────────────────────
def save_excel(sr: ScenarioResult, path: Path) -> None:
    m = sr.get_metrics_dict()
    path.parent.mkdir(parents=True, exist_ok=True)
    hour_cols = [f"H{h:02d}" for h in range(1, 25)]

    total_scen_df = pd.DataFrame(sr.total_scenarios.round(1), columns=hour_cols)
    total_scen_df.insert(0, "Scenario",    np.arange(1, sr.n_scenarios + 1))
    total_scen_df.insert(1, "Probability", round(1.0 / sr.n_scenarios, 6))

    hourly_df = pd.DataFrame({
        "Hour":              range(1, 25),
        "Forecast_MW":       np.array(m["tgt_forecast"]).round(1),
        "Scen_Mean_MW":      np.array(m["smean"]).round(1),
        "Scen_Std_MW":       np.array(m["sstd"]).round(1),
        "CV_pct":            np.array(m["cv_pct"]).round(2),
        "Scen_P05_MW":       np.array(m["pcts"]["5"]).round(1),
        "Scen_P25_MW":       np.array(m["pcts"]["25"]).round(1),
        "Scen_P50_MW":       np.array(m["pcts"]["50"]).round(1),
        "Scen_P75_MW":       np.array(m["pcts"]["75"]).round(1),
        "Scen_P95_MW":       np.array(m["pcts"]["95"]).round(1),
        "Band_P5_P95_MW":    np.array(m["band_width"]).round(1),
        "Up_Reserve_P95_MW": np.array(m["reserve_up_p95"]).round(1),
        "Dn_Reserve_P05_MW": np.array(m["reserve_dn_p05"]).round(1),
    })

    ramps = np.array(m["ramps"])
    ramp_df = pd.DataFrame({
        "Ramp_End_Hour": range(2, 25),
        "Ramp_Mean_MW":  ramps.mean(axis=0).round(1),
        "Ramp_Std_MW":   ramps.std(axis=0, ddof=1).round(1),
        "Ramp_P05_MW":   np.percentile(ramps, 5,  axis=0).round(1),
        "Ramp_P50_MW":   np.percentile(ramps, 50, axis=0).round(1),
        "Ramp_P95_MW":   np.percentile(ramps, 95, axis=0).round(1),
        "AbsRamp_P95_MW":np.percentile(np.abs(ramps), 95, axis=0).round(1),
    })

    window_label = {7:"±7 days", 14:"±14 days", 30:"±1 month", 60:"±2 months"}.get(
        sr.params.day_window, f"±{sr.params.day_window} days")

    overall_df = pd.DataFrame([
        ("Target Date",               m["target_date"]),
        ("Day Type (auto-detected)",  m["day_type"]),
        ("HDH Used",                  m["hdh_used"] if m["hdh_used"] else "Not available"),
        ("Analog Window",             window_label),
        ("Historical Years",          sr.params.historical_years),
        ("Zones Modelled",            len(m["zone_names"])),
        ("Copula Dimensions",         m["n_dimensions"]),
        ("Scenarios Generated",       m["n_scenarios"]),
        ("Analog Pool Size",          m["n_analogs"]),
        ("Ledoit-Wolf Shrinkage",     m["shrink_coeff"]),
        ("Methodology",               "Gaussian Copula + Ledoit-Wolf + Weighted Bootstrap"),
        ("Daily Energy — Mean (MWh)", m["daily_E_mean"]),
        ("Daily Energy P05 (MWh)",    m["daily_E_p05"]),
        ("Daily Energy P95 (MWh)",    m["daily_E_p95"]),
        ("Most Likely Peak Hour",     m["peak_hr_mode"]),
        ("Avg Adjacent-Hour Corr",    m["adj_corr_mean"]),
        ("Mean Spread CRPS (MW)",     m["mean_crps"]),
    ], columns=["Metric", "Value"])

    zone_val_df = pd.DataFrame(m["zone_daily"])
    zone_tables = {}
    for zi, z in enumerate(sr.zone_names):
        df = pd.DataFrame(sr.zonal_cube[:, zi, :].round(1), columns=hour_cols)
        df.insert(0, "Scenario",    np.arange(1, sr.n_scenarios + 1))
        df.insert(1, "Probability", round(1.0 / sr.n_scenarios, 6))
        zone_tables[z] = df

    with pd.ExcelWriter(path, engine="openpyxl") as wr:
        overall_df.to_excel(wr,    sheet_name="Overall_Summary",       index=False)
        hourly_df.to_excel(wr,     sheet_name="Hourly_Summary",        index=False)
        total_scen_df.to_excel(wr, sheet_name="50_Total_Scenarios_MW", index=False)
        ramp_df.to_excel(wr,       sheet_name="Ramp_Statistics",       index=False)
        zone_val_df.to_excel(wr,   sheet_name="Zone_Summary",          index=False)
        sr.analog_df.round(5).to_excel(wr, sheet_name="Analog_Day_Scores", index=False)
        for z, zdf in zone_tables.items():
            zdf.to_excel(wr, sheet_name=z.replace(" ", "_") + "_50Sc", index=False)
