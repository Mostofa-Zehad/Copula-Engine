"""
Plotly chart generator — converts all 14 analysis charts to interactive JSON.
"""
from __future__ import annotations

import numpy as np
from typing import List, Dict, Any

from .engine import ScenarioResult

TEAL   = "#0D9488"
RED    = "#DC3545"
NAVY   = "#0B1F3A"
GOLD   = "#F59E0B"
GREEN  = "#1D9E75"
PURPLE = "#7F77DD"
LGRAY  = "#94A3B8"
OFFWH  = "#F8FAFC"
ORANGE = "#F97316"

LAYOUT_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor=OFFWH,
    font=dict(family="Inter, system-ui, sans-serif", color=NAVY),
    margin=dict(l=55, r=30, t=55, b=45),
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                xanchor="left", x=0, bgcolor="rgba(0,0,0,0)", font_size=11),
    xaxis=dict(gridcolor="#E2E8F0", zerolinecolor="#E2E8F0",
               tickfont=dict(size=10)),
    yaxis=dict(gridcolor="#E2E8F0", zerolinecolor="#E2E8F0",
               tickfont=dict(size=10)),
    hoverlabel=dict(bgcolor="white", font_size=12,
                    bordercolor=NAVY),
)


def _layout(**extra) -> dict:
    d = LAYOUT_BASE.copy()
    d.update(extra)
    return d


def generate_all_plots(sr: ScenarioResult) -> List[Dict[str, Any]]:
    m = sr.get_metrics_dict()
    plots = []
    plots.append(_plot_scenario_band(m, sr))
    plots.append(_plot_fan(m, sr))
    plots.append(_plot_crps(m))
    plots.append(_plot_load_boxplot(m, sr))
    plots.append(_plot_std_cv(m))
    plots.append(_plot_corr_heatmap(m))
    plots.append(_plot_daily_energy(m))
    plots.append(_plot_adj_corr(m))
    plots.append(_plot_peak_hour(m))
    plots.append(_plot_ramp_band(m))
    plots.append(_plot_ramp_boxplot(m))
    plots.append(_plot_ramp_std(m))
    plots.append(_plot_zone_energy(m))
    plots.append(_plot_reserve(m))
    return plots


# ── 01: Scenario Band ─────────────────────────────────────────────────────────
def _plot_scenario_band(m, sr) -> dict:
    hrs = list(range(1, 25))
    p5 = m["pcts"]["5"]; p25 = m["pcts"]["25"]
    p75 = m["pcts"]["75"]; p95 = m["pcts"]["95"]
    p50 = m["pcts"]["50"]

    traces = [
        dict(x=hrs + hrs[::-1], y=p5 + p95[::-1],
             fill="toself", fillcolor="rgba(13,148,136,0.15)",
             line=dict(color="rgba(0,0,0,0)"), name="P05–P95 Band",
             hoverinfo="skip"),
        dict(x=hrs + hrs[::-1], y=p25 + p75[::-1],
             fill="toself", fillcolor="rgba(13,148,136,0.28)",
             line=dict(color="rgba(0,0,0,0)"), name="P25–P75 Band",
             hoverinfo="skip"),
        dict(x=hrs, y=m["tgt_forecast"], mode="lines",
             line=dict(color=GOLD, width=2.5), name="Forecast (Input)"),
        dict(x=hrs, y=m["smean"], mode="lines",
             line=dict(color=RED, width=2, dash="dash"), name="Scenario Mean"),
        dict(x=hrs, y=p50, mode="lines",
             line=dict(color=PURPLE, width=1.5, dash="dot"), name="Median (P50)"),
        dict(x=hrs, y=p5, mode="lines",
             line=dict(color=TEAL, width=1, dash="dash"), name="P05",
             hovertemplate="H%{x} P05: %{y:,.0f} MW<extra></extra>"),
        dict(x=hrs, y=p95, mode="lines",
             line=dict(color=TEAL, width=1, dash="dash"), name="P95",
             hovertemplate="H%{x} P95: %{y:,.0f} MW<extra></extra>"),
    ]

    layout = _layout(
        title=dict(text=f"<b>GC-50 System Load Scenario Band  |  {m['target_date']}</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25)),
                   ticktext=[str(h) for h in range(1, 25)]),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="System Load (MW)",
                   tickformat=",.0f"),
        # Legend inside the plot (top-right) so it doesn't collide with the title
        legend=dict(orientation="v", yanchor="top", y=0.99,
                    xanchor="right", x=0.99,
                    bgcolor="rgba(255,255,255,0.88)",
                    bordercolor="#E2E8F0", borderwidth=1, font_size=10),
    )
    return {"id": "plot_01_scenario_band", "title": "Scenario Band",
            "data": traces, "layout": layout}


# ── 02: Fan Plot ──────────────────────────────────────────────────────────────
def _plot_fan(m, sr) -> dict:
    hrs = list(range(1, 25))
    scenarios = m["total_scenarios"]
    traces = []
    for i, sc in enumerate(scenarios):
        traces.append(dict(
            x=hrs, y=sc, mode="lines",
            line=dict(color="rgba(13,148,136,0.18)", width=0.9),
            showlegend=(i == 0), name="Scenarios",
            hovertemplate=f"Sc {i+1} H%{{x}}: %{{y:,.0f}} MW<extra></extra>",
        ))
    traces.append(dict(x=hrs, y=m["smean"], mode="lines",
                       line=dict(color=RED, width=2.5), name="Scenario Mean"))
    traces.append(dict(x=hrs, y=m["tgt_forecast"], mode="lines",
                       line=dict(color=GOLD, width=2.5, dash="dash"),
                       name="Forecast"))

    layout = _layout(
        title=dict(text=f"<b>{m['n_scenarios']} Dependent Copula Scenarios  |  {m['target_date']}</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="System Load (MW)",
                   tickformat=",.0f"),
    )
    return {"id": "plot_02_fan", "title": "Fan Plot (All 50 Scenarios)",
            "data": traces, "layout": layout}


# ── 03: CRPS by Hour ──────────────────────────────────────────────────────────
def _plot_crps(m) -> dict:
    hrs = list(range(1, 25))
    crps = m["crps_vec"]
    mean_c = m["mean_crps"]
    colors = [RED if v > mean_c else TEAL for v in crps]

    traces = [
        dict(x=hrs, y=crps, type="bar", marker=dict(color=colors),
             name="Hourly Spread CRPS",
             hovertemplate="H%{x}: %{y:.1f} MW<extra></extra>"),
        dict(x=[1, 24], y=[mean_c, mean_c], mode="lines",
             line=dict(color=NAVY, width=2, dash="dash"),
             name=f"Mean CRPS = {mean_c:.1f} MW"),
    ]
    layout = _layout(
        title=dict(text="<b>Hourly Spread CRPS  (lower = tighter scenarios)  |  Red > mean</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="CRPS (MW)"),
        bargap=0.15,
    )
    return {"id": "plot_03_crps", "title": "Hourly CRPS",
            "data": traces, "layout": layout}


# ── 04: Load Box Plot ─────────────────────────────────────────────────────────
def _plot_load_boxplot(m, sr) -> dict:
    hrs = list(range(1, 25))
    scenarios = np.array(m["total_scenarios"])
    traces = []
    for h in range(24):
        traces.append(dict(
            x=[h + 1] * sr.n_scenarios,
            y=scenarios[:, h].tolist(),
            type="box",
            marker=dict(color=TEAL, opacity=0.7, size=3),
            line=dict(color=TEAL),
            showlegend=(h == 0), name="50 Scenarios",
            hovertemplate=f"H{h+1} <br>%{{y:,.0f}} MW<extra></extra>",
            boxpoints=False,
        ))
    traces.append(dict(x=hrs, y=m["tgt_forecast"], mode="lines+markers",
                       line=dict(color=GOLD, width=2, dash="dash"),
                       marker=dict(size=5, color=GOLD), name="Forecast"))
    traces.append(dict(x=hrs, y=m["smean"], mode="lines",
                       line=dict(color=PURPLE, width=2), name="Scenario Mean"))

    layout = _layout(
        title=dict(text=f"<b>Hourly Load Box Plot — {sr.n_scenarios} Scenarios  |  {m['target_date']}</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="System Load (MW)",
                   tickformat=",.0f"),
        boxmode="overlay",
    )
    return {"id": "plot_04_load_boxplot", "title": "Hourly Box Plot",
            "data": traces, "layout": layout}


# ── 05: Std Dev + CV% ────────────────────────────────────────────────────────
def _plot_std_cv(m) -> dict:
    hrs = list(range(1, 25))
    traces = [
        dict(x=hrs, y=m["sstd"], type="bar",
             marker=dict(color=TEAL, opacity=0.75),
             name="Std Dev (MW)",
             hovertemplate="H%{x} Std: %{y:,.0f} MW<extra></extra>",
             yaxis="y"),
        dict(x=hrs, y=m["cv_pct"], mode="lines+markers",
             line=dict(color=RED, width=2.5),
             marker=dict(size=5, color=RED),
             name="CV %",
             hovertemplate="H%{x} CV: %{y:.2f}%<extra></extra>",
             yaxis="y2"),
    ]
    layout = _layout(
        title=dict(text="<b>Hourly Load Uncertainty — Std Dev & Coefficient of Variation</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Std Dev (MW)", tickformat=",.0f"),
        yaxis2=dict(title="CV (%)", overlaying="y", side="right",
                    tickfont=dict(color=RED, size=10),
                    titlefont=dict(color=RED), showgrid=False),
        bargap=0.15,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return {"id": "plot_05_std_cv", "title": "Uncertainty: Std Dev & CV%",
            "data": traces, "layout": layout}


# ── 06: Correlation Heatmap ──────────────────────────────────────────────────
def _plot_corr_heatmap(m) -> dict:
    corr = m["corr_mat"]
    hrs = [str(h) for h in range(1, 25)]
    traces = [dict(
        z=corr, x=hrs, y=hrs, type="heatmap",
        colorscale="RdBu_r", zmin=-1, zmax=1,
        colorbar=dict(title="r", thickness=14),
        hovertemplate="H%{x} vs H%{y}: r = %{z:.3f}<extra></extra>",
    )]
    layout = _layout(
        title=dict(text="<b>Hour-to-Hour Scenario Correlation Matrix</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(title="Hour", tickfont=dict(size=9),
                   showgrid=False, zeroline=False),
        yaxis=dict(title="Hour", tickfont=dict(size=9),
                   showgrid=False, zeroline=False, autorange="reversed"),
        width=520, height=480,
    )
    return {"id": "plot_06_corr_heatmap", "title": "Correlation Heatmap",
            "data": traces, "layout": layout}


# ── 07: Daily Energy Distribution ────────────────────────────────────────────
def _plot_daily_energy(m) -> dict:
    daily_E = m["daily_E"]
    mean_E = m["daily_E_mean"]
    p05_E = m["daily_E_p05"]
    p95_E = m["daily_E_p95"]

    traces = [
        dict(x=daily_E, type="histogram", nbinsx=12,
             marker=dict(color=TEAL, opacity=0.75,
                         line=dict(color="white", width=1)),
             name="Daily Energy", hovertemplate="%{x:,.0f} MWh<extra></extra>"),
        dict(x=[mean_E, mean_E], y=[0, 15], mode="lines",
             line=dict(color=NAVY, width=2.5, dash="dash"),
             name=f"Mean {mean_E:,.0f} MWh"),
        dict(x=[p05_E, p05_E], y=[0, 15], mode="lines",
             line=dict(color=RED, width=2, dash="dot"),
             name=f"P05 {p05_E:,.0f} MWh"),
        dict(x=[p95_E, p95_E], y=[0, 15], mode="lines",
             line=dict(color=RED, width=2, dash="dot"),
             name=f"P95 {p95_E:,.0f} MWh"),
    ]
    layout = _layout(
        title=dict(text="<b>Daily Energy Distribution — 50 Scenarios</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Daily Energy (MWh)",
                   tickformat=",.0f"),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Count"),
        bargap=0.1,
    )
    return {"id": "plot_07_daily_energy", "title": "Daily Energy Distribution",
            "data": traces, "layout": layout}


# ── 08: Adjacent-Hour Correlation ─────────────────────────────────────────────
def _plot_adj_corr(m) -> dict:
    rh = list(range(2, 25))
    adj = m["adj_corr"]
    avg = m["adj_corr_mean"]

    traces = [
        dict(x=rh, y=[0.99] * 23, mode="lines",
             line=dict(color=GOLD, width=1.8, dash="dash"),
             name="Actual load benchmark (~0.99)",
             hoverinfo="skip"),
        dict(x=rh, y=[0.0] * 23, mode="lines",
             line=dict(color=LGRAY, width=1, dash="dot"),
             name="Independent model (~0.00)", hoverinfo="skip"),
        dict(x=rh, y=adj, mode="lines+markers",
             line=dict(color=TEAL, width=2.5),
             marker=dict(size=6, color=TEAL),
             name=f"GC-50  (avg = {avg:.3f})",
             hovertemplate="H%{x} corr: %{y:.4f}<extra></extra>"),
    ]
    layout = _layout(
        title=dict(text="<b>Adjacent-Hour Correlation  (higher = more realistic temporal structure)</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour Pair (h → h+1)",
                   tickvals=list(range(2, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Pearson r",
                   range=[-0.1, 1.1]),
    )
    return {"id": "plot_08_adj_corr", "title": "Adjacent-Hour Correlation",
            "data": traces, "layout": layout}


# ── 09: Peak Hour Frequency ───────────────────────────────────────────────────
def _plot_peak_hour(m) -> dict:
    hrs = list(range(1, 25))
    freq = m["peak_hr_freq"]
    pct = [100.0 * v / m["n_scenarios"] for v in freq]
    mode_h = m["peak_hr_mode"]
    colors = [RED if h == mode_h else TEAL for h in hrs]

    traces = [dict(
        x=hrs, y=pct, type="bar",
        marker=dict(color=colors),
        name="Peak Hour %",
        hovertemplate="H%{x}: %{y:.1f}%<extra></extra>",
    )]
    layout = _layout(
        title=dict(text=f"<b>Peak Hour Probability — {m['n_scenarios']} Scenarios  "
                   f"(Most likely: H{mode_h} @ {m['peak_hr_mode_pct']:.1f}%)</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Probability (%)",
                   ticksuffix="%"),
        bargap=0.15,
    )
    return {"id": "plot_09_peak_hour", "title": "Peak Hour Distribution",
            "data": traces, "layout": layout}


# ── 10: Ramp Band ─────────────────────────────────────────────────────────────
def _plot_ramp_band(m) -> dict:
    rh = list(range(2, 25))
    ramps = np.array(m["ramps"])
    rp05 = np.percentile(ramps, 5, axis=0).tolist()
    rp25 = np.percentile(ramps, 25, axis=0).tolist()
    rp50 = np.percentile(ramps, 50, axis=0).tolist()
    rp75 = np.percentile(ramps, 75, axis=0).tolist()
    rp95 = np.percentile(ramps, 95, axis=0).tolist()
    rmean = ramps.mean(axis=0).tolist()

    traces = [
        dict(x=rh + rh[::-1], y=rp05 + rp95[::-1],
             fill="toself", fillcolor="rgba(13,148,136,0.15)",
             line=dict(color="rgba(0,0,0,0)"), name="P05–P95 Band",
             hoverinfo="skip"),
        dict(x=rh + rh[::-1], y=rp25 + rp75[::-1],
             fill="toself", fillcolor="rgba(13,148,136,0.28)",
             line=dict(color="rgba(0,0,0,0)"), name="P25–P75 Band",
             hoverinfo="skip"),
        dict(x=rh, y=rmean, mode="lines",
             line=dict(color=TEAL, width=2, dash="dash"), name="Scenario Mean"),
        dict(x=rh, y=rp50, mode="lines",
             line=dict(color=PURPLE, width=1.5, dash="dot"), name="Median (P50)"),
        dict(x=[rh[0], rh[-1]], y=[0, 0], mode="lines",
             line=dict(color=LGRAY, width=1.2, dash="dash"),
             name="Zero line", hoverinfo="skip"),
    ]
    layout = _layout(
        title=dict(text=f"<b>Ramp Profile — P05/P95 Band  |  {m['target_date']}</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Ramp Ending Hour",
                   tickvals=list(range(2, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Ramp (MW/h)", tickformat=","),
    )
    return {"id": "plot_10_ramp_band", "title": "Ramp Band",
            "data": traces, "layout": layout}


# ── 11: Ramp Box Plot ─────────────────────────────────────────────────────────
def _plot_ramp_boxplot(m) -> dict:
    rh = list(range(2, 25))
    ramps = np.array(m["ramps"])
    traces = []
    for idx, h in enumerate(rh):
        traces.append(dict(
            x=[h] * m["n_scenarios"],
            y=ramps[:, idx].tolist(),
            type="box",
            marker=dict(color=TEAL, opacity=0.7, size=3),
            line=dict(color=TEAL),
            showlegend=(idx == 0), name="Ramp Scenarios",
            boxpoints=False,
            hovertemplate=f"H{h} Ramp<br>%{{y:,.0f}} MW<extra></extra>",
        ))

    traces.append(dict(
        x=[rh[0], rh[-1]], y=[0, 0], mode="lines",
        line=dict(color=LGRAY, width=1.2, dash="dash"),
        name="Zero line", hoverinfo="skip",
    ))

    layout = _layout(
        title=dict(text=f"<b>Hourly Ramp Box Plot — {m['n_scenarios']} Scenarios</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Ramp Ending Hour",
                   tickvals=list(range(2, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Ramp (MW/h)", tickformat=","),
        boxmode="overlay",
    )
    return {"id": "plot_11_ramp_boxplot", "title": "Ramp Box Plot",
            "data": traces, "layout": layout}


# ── 12: Ramp Std Dev ──────────────────────────────────────────────────────────
def _plot_ramp_std(m) -> dict:
    rh = list(range(2, 25))
    ramps = np.array(m["ramps"])
    ramp_std = ramps.std(axis=0, ddof=1).tolist()
    abs_p95 = np.percentile(np.abs(ramps), 95, axis=0).tolist()

    traces = [
        dict(x=[h - 0.22 for h in rh], y=ramp_std, type="bar", width=0.4,
             marker=dict(color=TEAL, opacity=0.80),
             name="Ramp Std Dev (MW)",
             hovertemplate="H%{x:.0f} Std: %{y:,.0f} MW<extra></extra>"),
        dict(x=[h + 0.22 for h in rh], y=abs_p95, type="bar", width=0.4,
             marker=dict(color=RED, opacity=0.65),
             name="Abs Ramp P95 (MW)",
             hovertemplate="H%{x:.0f} |Ramp| P95: %{y:,.0f} MW<extra></extra>"),
    ]
    layout = _layout(
        title=dict(text="<b>Ramp Uncertainty — Std Dev & Abs P95 by Hour</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Ramp Ending Hour",
                   tickvals=list(range(2, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Ramp (MW/h)", tickformat=","),
        barmode="group", bargap=0.05,
    )
    return {"id": "plot_12_ramp_std", "title": "Ramp Uncertainty",
            "data": traces, "layout": layout}


# ── 13: Zone Daily Energy ─────────────────────────────────────────────────────
def _plot_zone_energy(m) -> dict:
    zd = m["zone_daily"]
    zones = [d["zone"] for d in zd]
    means = [d["mean"] for d in zd]
    p05s = [d["p05"] for d in zd]
    p95s = [d["p95"] for d in zd]
    err_lo = [means[i] - p05s[i] for i in range(len(zones))]
    err_hi = [p95s[i] - means[i] for i in range(len(zones))]

    traces = [dict(
        x=zones, y=means, type="bar",
        marker=dict(color=TEAL, opacity=0.80),
        name="Scenario Mean Daily Energy",
        error_y=dict(type="data", symmetric=False,
                     array=err_hi, arrayminus=err_lo,
                     color=NAVY, thickness=2, width=6),
        hovertemplate="%{x}<br>Mean: %{y:,.0f} MWh<extra></extra>",
    )]
    layout = _layout(
        title=dict(text="<b>Zone Daily Energy — Scenario Mean with P05–P95 Error Bars</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(title="Zone", tickfont=dict(size=10),
                   gridcolor="#E2E8F0"),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Daily Energy (MWh)",
                   tickformat=",.0f"),
        bargap=0.25,
    )
    return {"id": "plot_13_zone_energy", "title": "Zone Daily Energy",
            "data": traces, "layout": layout}


# ── 14: Reserve Requirements ──────────────────────────────────────────────────
def _plot_reserve(m) -> dict:
    hrs = list(range(1, 25))
    up95 = m["reserve_up_p95"]
    dn05 = m["reserve_dn_p05"]
    band = m["band_width"]

    traces = [
        dict(x=[h - 0.22 for h in hrs], y=up95, type="bar", width=0.42,
             marker=dict(color=TEAL, opacity=0.80),
             name="Up-Reserve P95 (MW)",
             hovertemplate="H%{x:.0f} Up-Rsv P95: %{y:,.0f} MW<extra></extra>"),
        dict(x=[h + 0.22 for h in hrs], y=dn05, type="bar", width=0.42,
             marker=dict(color=RED, opacity=0.70),
             name="Dn-Reserve P05 (MW)",
             hovertemplate="H%{x:.0f} Dn-Rsv P05: %{y:,.0f} MW<extra></extra>"),
        dict(x=hrs, y=band, mode="lines+markers",
             line=dict(color=GOLD, width=2.5),
             marker=dict(size=5, color=GOLD, symbol="diamond"),
             name="P05–P95 Band Width (MW)",
             yaxis="y2",
             hovertemplate="H%{x} Band: %{y:,.0f} MW<extra></extra>"),
    ]
    layout = _layout(
        title=dict(text="<b>Operating Reserve Requirements by Hour  (GC-50 Copula)</b>",
                   font=dict(size=14, color=NAVY), x=0),
        xaxis=dict(**LAYOUT_BASE["xaxis"], title="Hour of Day",
                   tickvals=list(range(1, 25))),
        yaxis=dict(**LAYOUT_BASE["yaxis"], title="Reserve (MW)", tickformat=","),
        yaxis2=dict(title="Band Width (MW)", overlaying="y", side="right",
                    tickfont=dict(color=GOLD, size=10),
                    titlefont=dict(color=GOLD), showgrid=False,
                    tickformat=","),
        barmode="group", bargap=0.05,
    )
    return {"id": "plot_14_reserve", "title": "Reserve Requirements",
            "data": traces, "layout": layout}
