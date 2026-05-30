"""
Plotly chart generator — 14 professional analysis charts.
Professional redesign: publication-quality typography, refined palette,
two-line titles, pure-white backgrounds, consistent spacing.
"""
from __future__ import annotations

import copy
import numpy as np
from typing import List, Dict, Any

from .engine import ScenarioResult

# ── Professional color palette ────────────────────────────────────────────────
NAVY   = "#1E3A5F"   # primary text / titles
BLUE   = "#0369A1"   # primary accent — scenario mean, key reference
TEAL   = "#0F766E"   # bands, distributions, default bars
AMBER  = "#B45309"   # forecast input (warm, clearly distinct)
RED    = "#C0392B"   # alerts, above-mean, down-reserve
VIOLET = "#6D28D9"   # median / P50
SLATE  = "#64748B"   # secondary reference lines, annotations
GREEN  = "#047857"   # zone chart accent
ORANGE = "#C2410C"   # ramp P95
LGRAY  = "#94A3B8"   # zero lines, faint guides

# Band fills (outer = P05-P95, inner = P25-P75)
BAND_OUTER = "rgba(15,118,110,0.10)"
BAND_INNER = "rgba(15,118,110,0.22)"

# ── Shared axis style ─────────────────────────────────────────────────────────
_AX = dict(
    gridcolor="#EDF2F7",
    gridwidth=1,
    zerolinecolor="#CBD5E1",
    zerolinewidth=1,
    linecolor="#E2E8F0",
    linewidth=1,
    tickfont=dict(size=10, color="#475569"),
    title_font=dict(size=11.5, color="#334155"),
    showgrid=True,
    ticks="outside",
    ticklen=3,
    tickwidth=1,
    tickcolor="#E2E8F0",
)

LAYOUT_BASE = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    font=dict(family="Inter, system-ui, sans-serif", size=11, color=NAVY),
    margin=dict(l=72, r=58, t=80, b=56),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="left", x=0,
        bgcolor="rgba(255,255,255,0)",
        borderwidth=0,
        font=dict(size=10.5, color="#334155"),
        itemsizing="constant",
        tracegroupgap=2,
    ),
    xaxis=_AX.copy(),
    yaxis=_AX.copy(),
    hoverlabel=dict(
        bgcolor="white",
        font=dict(size=11.5, family="Inter, system-ui, sans-serif", color=NAVY),
        bordercolor="#CBD5E1",
    ),
)


def _layout(**extra) -> dict:
    d = copy.deepcopy(LAYOUT_BASE)
    d.update(extra)
    return d


def _title(main: str, sub: str = "") -> dict:
    """Two-line professional title: bold main + small gray subtitle."""
    text = f"<b>{main}</b>"
    if sub:
        text += (f"<br><span style='font-size:10px;color:#64748B;"
                 f"font-weight:400;letter-spacing:0.01em'>{sub}</span>")
    return dict(
        text=text,
        font=dict(size=13.5, color=NAVY),
        x=0.0, xanchor="left",
        # No manual y — let Plotly centre the title inside the top margin
    )


def _xax(title: str, **kw) -> dict:
    d = copy.deepcopy(_AX); d["title"] = title; d.update(kw); return d


def _yax(title: str, **kw) -> dict:
    d = copy.deepcopy(_AX); d["title"] = title; d.update(kw); return d


def _leg_inside(**kw) -> dict:
    """Legend positioned inside the chart area — for crowded top margins."""
    base = dict(
        orientation="v",
        yanchor="top", y=0.985,
        xanchor="right", x=0.985,
        bgcolor="rgba(255,255,255,0.93)",
        bordercolor="#E2E8F0", borderwidth=1,
        font=dict(size=10, color="#334155"),
        itemsizing="constant",
    )
    base.update(kw)
    return base


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
    hrs  = list(range(1, 25))
    p5   = m["pcts"]["5"];  p25 = m["pcts"]["25"]
    p75  = m["pcts"]["75"]; p95 = m["pcts"]["95"]
    p50  = m["pcts"]["50"]
    n_z  = len(m["zone_names"])

    traces = [
        # Outer band P05–P95
        dict(x=hrs + hrs[::-1], y=p5 + p95[::-1],
             fill="toself", fillcolor=BAND_OUTER,
             line=dict(color="rgba(0,0,0,0)"), name="P05 – P95 Band",
             hoverinfo="skip"),
        # Inner band P25–P75
        dict(x=hrs + hrs[::-1], y=p25 + p75[::-1],
             fill="toself", fillcolor=BAND_INNER,
             line=dict(color="rgba(0,0,0,0)"), name="P25 – P75 Band",
             hoverinfo="skip"),
        # P05 / P95 boundary lines
        dict(x=hrs, y=p5, mode="lines",
             line=dict(color=TEAL, width=1.0, dash="dot"), name="P05",
             hovertemplate="Hour %{x}  ·  P05: <b>%{y:,.0f} MW</b><extra></extra>"),
        dict(x=hrs, y=p95, mode="lines",
             line=dict(color=TEAL, width=1.0, dash="dot"), name="P95",
             hovertemplate="Hour %{x}  ·  P95: <b>%{y:,.0f} MW</b><extra></extra>"),
        # Median
        dict(x=hrs, y=p50, mode="lines",
             line=dict(color=VIOLET, width=1.5, dash="dot"), name="Median (P50)",
             hovertemplate="Hour %{x}  ·  P50: <b>%{y:,.0f} MW</b><extra></extra>"),
        # Scenario mean
        dict(x=hrs, y=m["smean"], mode="lines",
             line=dict(color=BLUE, width=2.2, dash="dash"), name="Scenario Mean",
             hovertemplate="Hour %{x}  ·  Mean: <b>%{y:,.0f} MW</b><extra></extra>"),
        # Forecast input — most prominent
        dict(x=hrs, y=m["tgt_forecast"], mode="lines",
             line=dict(color=AMBER, width=2.8), name="Forecast (Input)",
             hovertemplate="Hour %{x}  ·  Forecast: <b>%{y:,.0f} MW</b><extra></extra>"),
    ]

    sub = (f"{m['target_date']}  ·  {sr.n_scenarios} scenarios  ·  "
           f"{m['n_analogs']} analog days  ·  {n_z} zone{'s' if n_z > 1 else ''}")
    layout = _layout(
        title=_title("Scenario Uncertainty Band", sub),
        xaxis=_xax("Hour of Day",
                   tickvals=list(range(1, 25)),
                   ticktext=[str(h) for h in range(1, 25)],
                   range=[0.5, 24.5]),
        yaxis=_yax("System Load (MW)", tickformat=",.0f"),
        legend=_leg_inside(),
    )
    return {"id": "plot_01_scenario_band", "title": "Scenario Band",
            "data": traces, "layout": layout}


# ── 02: Fan Plot ──────────────────────────────────────────────────────────────
def _plot_fan(m, sr) -> dict:
    hrs       = list(range(1, 25))
    scenarios = m["total_scenarios"]
    traces    = []
    for i, sc in enumerate(scenarios):
        traces.append(dict(
            x=hrs, y=sc, mode="lines",
            line=dict(color="rgba(15,118,110,0.16)", width=0.8),
            showlegend=(i == 0), name=f"{sr.n_scenarios} Scenario Paths",
            hovertemplate=f"Sc {i+1}  H%{{x}}: <b>%{{y:,.0f}} MW</b><extra></extra>",
        ))
    traces.append(dict(
        x=hrs, y=m["smean"], mode="lines",
        line=dict(color=BLUE, width=2.5), name="Scenario Mean",
        hovertemplate="H%{x}  ·  Mean: <b>%{y:,.0f} MW</b><extra></extra>",
    ))
    traces.append(dict(
        x=hrs, y=m["tgt_forecast"], mode="lines",
        line=dict(color=AMBER, width=2.5, dash="dash"), name="Forecast (Input)",
        hovertemplate="H%{x}  ·  Forecast: <b>%{y:,.0f} MW</b><extra></extra>",
    ))

    sub = f"{m['target_date']}  ·  {sr.n_scenarios} correlated Gaussian Copula draws"
    layout = _layout(
        title=_title(f"{sr.n_scenarios} Dependent Load Scenarios", sub),
        xaxis=_xax("Hour of Day", tickvals=list(range(1, 25)), range=[0.5, 24.5]),
        yaxis=_yax("System Load (MW)", tickformat=",.0f"),
    )
    return {"id": "plot_02_fan", "title": "Fan Plot (All Scenarios)",
            "data": traces, "layout": layout}


# ── 03: CRPS by Hour ──────────────────────────────────────────────────────────
def _plot_crps(m) -> dict:
    hrs    = list(range(1, 25))
    crps   = m["crps_vec"]
    mean_c = m["mean_crps"]
    colors = [RED if v > mean_c else TEAL for v in crps]

    traces = [
        dict(x=hrs, y=crps, type="bar",
             marker=dict(color=colors, opacity=0.82,
                         line=dict(color="white", width=0.6)),
             name="Hourly CRPS",
             hovertemplate="Hour %{x}  ·  CRPS: <b>%{y:.1f} MW</b><extra></extra>"),
        dict(x=[0.5, 24.5], y=[mean_c, mean_c], mode="lines",
             line=dict(color=NAVY, width=1.8, dash="dash"),
             name=f"Mean  {mean_c:.1f} MW",
             hoverinfo="skip"),
    ]
    layout = _layout(
        title=_title("Hourly Spread CRPS",
                     "Lower = tighter, more confident scenarios  ·  Red bars exceed the mean"),
        xaxis=_xax("Hour of Day", tickvals=list(range(1, 25)), range=[0.5, 24.5]),
        yaxis=_yax("CRPS (MW)"),
        bargap=0.18,
    )
    return {"id": "plot_03_crps", "title": "Hourly CRPS",
            "data": traces, "layout": layout}


# ── 04: Load Box Plot ─────────────────────────────────────────────────────────
def _plot_load_boxplot(m, sr) -> dict:
    hrs       = list(range(1, 25))
    scenarios = np.array(m["total_scenarios"])
    traces    = []
    for h in range(24):
        traces.append(dict(
            x=[h + 1] * sr.n_scenarios,
            y=scenarios[:, h].tolist(),
            type="box",
            marker=dict(color=TEAL, opacity=0.6, size=3),
            line=dict(color=TEAL, width=1.2),
            fillcolor="rgba(15,118,110,0.18)",
            showlegend=(h == 0), name="Scenario Range",
            hovertemplate=f"H{h+1}<br>%{{y:,.0f}} MW<extra></extra>",
            boxpoints=False,
            whiskerwidth=0.6,
        ))
    traces.append(dict(
        x=hrs, y=m["tgt_forecast"], mode="lines+markers",
        line=dict(color=AMBER, width=2.4),
        marker=dict(size=4.5, color=AMBER, symbol="circle"),
        name="Forecast (Input)",
        hovertemplate="H%{x}  ·  Forecast: <b>%{y:,.0f} MW</b><extra></extra>",
    ))
    traces.append(dict(
        x=hrs, y=m["smean"], mode="lines",
        line=dict(color=BLUE, width=2, dash="dash"),
        name="Scenario Mean",
        hovertemplate="H%{x}  ·  Mean: <b>%{y:,.0f} MW</b><extra></extra>",
    ))

    sub = f"{m['target_date']}  ·  {sr.n_scenarios} scenarios  ·  whiskers = P05/P95"
    layout = _layout(
        title=_title("Hourly Load Distribution", sub),
        xaxis=_xax("Hour of Day", tickvals=list(range(1, 25)), range=[0.5, 24.5]),
        yaxis=_yax("System Load (MW)", tickformat=",.0f"),
        boxmode="overlay",
    )
    return {"id": "plot_04_load_boxplot", "title": "Hourly Box Plot",
            "data": traces, "layout": layout}


# ── 05: Std Dev + CV% ────────────────────────────────────────────────────────
def _plot_std_cv(m) -> dict:
    hrs = list(range(1, 25))
    traces = [
        dict(x=hrs, y=m["sstd"], type="bar",
             marker=dict(color=TEAL, opacity=0.78,
                         line=dict(color="white", width=0.5)),
             name="Std Dev (MW)", yaxis="y",
             hovertemplate="H%{x}  ·  Std Dev: <b>%{y:,.0f} MW</b><extra></extra>"),
        dict(x=hrs, y=m["cv_pct"], mode="lines+markers",
             line=dict(color=RED, width=2.2),
             marker=dict(size=4.5, color=RED, symbol="circle"),
             name="CV %", yaxis="y2",
             hovertemplate="H%{x}  ·  CV: <b>%{y:.2f}%</b><extra></extra>"),
    ]
    y2 = copy.deepcopy(_AX)
    y2.update(dict(
        title="Coefficient of Variation (%)",
        overlaying="y", side="right",
        tickfont=dict(color=RED, size=10),
        title_font=dict(color=RED, size=11),
        showgrid=False,
        ticksuffix="%",
    ))
    layout = _layout(
        title=_title("Hourly Load Uncertainty",
                     "Bars = standard deviation (MW)  ·  Line = coefficient of variation (%)"),
        xaxis=_xax("Hour of Day", tickvals=list(range(1, 25)), range=[0.5, 24.5]),
        yaxis=_yax("Standard Deviation (MW)", tickformat=",.0f"),
        yaxis2=y2,
        margin=dict(l=72, r=78, t=80, b=56),
        bargap=0.18,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(255,255,255,0)", font=dict(size=10.5),
        ),
    )
    return {"id": "plot_05_std_cv", "title": "Uncertainty: Std Dev & CV%",
            "data": traces, "layout": layout}


# ── 06: Correlation Heatmap ──────────────────────────────────────────────────
def _plot_corr_heatmap(m) -> dict:
    corr = m["corr_mat"]
    hrs  = [str(h) for h in range(1, 25)]
    traces = [dict(
        z=corr, x=hrs, y=hrs, type="heatmap",
        colorscale=[
            [0.0,  "#B91C1C"], [0.25, "#F87171"],
            [0.45, "#FEF2F2"], [0.5,  "#F8FAFC"],
            [0.55, "#EFF6FF"], [0.75, "#60A5FA"],
            [1.0,  "#1D4ED8"],
        ],
        zmin=-1, zmax=1,
        colorbar=dict(
            title=dict(text="r", font=dict(size=11, color=NAVY)),
            thickness=13, len=0.85,
            tickfont=dict(size=9, color="#475569"),
            tickvals=[-1, -0.5, 0, 0.5, 1],
        ),
        hovertemplate="H%{x} vs H%{y}<br>r = <b>%{z:.3f}</b><extra></extra>",
    )]
    layout = _layout(
        title=_title("Hour-to-Hour Scenario Correlation Matrix",
                     "Gaussian Copula preserves empirical temporal structure across all hours"),
        xaxis=dict(title=dict(text="Hour", font=dict(size=11)), tickfont=dict(size=9),
                   showgrid=False, zeroline=False, linecolor="#E2E8F0"),
        yaxis=dict(title=dict(text="Hour", font=dict(size=11)), tickfont=dict(size=9),
                   showgrid=False, zeroline=False, autorange="reversed",
                   linecolor="#E2E8F0"),
        margin=dict(l=55, r=55, t=80, b=54),
    )
    return {"id": "plot_06_corr_heatmap", "title": "Correlation Heatmap",
            "data": traces, "layout": layout}


# ── 07: Daily Energy Distribution ────────────────────────────────────────────
def _plot_daily_energy(m) -> dict:
    daily_E = m["daily_E"]
    mean_E  = m["daily_E_mean"]
    p05_E   = m["daily_E_p05"]
    p95_E   = m["daily_E_p95"]

    traces = [
        dict(x=daily_E, type="histogram", nbinsx=12,
             marker=dict(color=TEAL, opacity=0.78,
                         line=dict(color="white", width=1.2)),
             name="Scenario Daily Energy",
             hovertemplate="%{x:,.0f} MWh  ·  Count: %{y}<extra></extra>"),
        dict(x=[mean_E, mean_E], y=[0, 18], mode="lines",
             line=dict(color=NAVY, width=2, dash="dash"),
             name=f"Mean  {mean_E:,.0f} MWh",
             hoverinfo="skip"),
        dict(x=[p05_E, p05_E], y=[0, 18], mode="lines",
             line=dict(color=RED, width=1.5, dash="dot"),
             name=f"P05  {p05_E:,.0f} MWh",
             hoverinfo="skip"),
        dict(x=[p95_E, p95_E], y=[0, 18], mode="lines",
             line=dict(color=RED, width=1.5, dash="dot"),
             name=f"P95  {p95_E:,.0f} MWh",
             hoverinfo="skip"),
    ]
    layout = _layout(
        title=_title("Daily Energy Distribution",
                     f"50 scenario outcomes  ·  P05–P95 spread: "
                     f"{p95_E - p05_E:,.0f} MWh"),
        xaxis=_xax("Daily Energy (MWh)", tickformat=",.0f"),
        yaxis=_yax("Frequency (Scenarios)"),
        bargap=0.08,
    )
    return {"id": "plot_07_daily_energy", "title": "Daily Energy Distribution",
            "data": traces, "layout": layout}


# ── 08: Adjacent-Hour Correlation ─────────────────────────────────────────────
def _plot_adj_corr(m) -> dict:
    rh  = list(range(2, 25))
    adj = m["adj_corr"]
    avg = m["adj_corr_mean"]

    # Shaded fill between GC-50 and the actual load benchmark
    bm = [0.99] * 23
    traces = [
        # Fill between GC-50 and benchmark
        dict(x=rh + rh[::-1], y=bm + adj[::-1],
             fill="toself", fillcolor="rgba(3,105,161,0.07)",
             line=dict(color="rgba(0,0,0,0)"), name="Gap to benchmark",
             hoverinfo="skip"),
        dict(x=rh, y=bm, mode="lines",
             line=dict(color=AMBER, width=1.8, dash="dash"),
             name="Actual load benchmark (≈0.99)",
             hoverinfo="skip"),
        dict(x=rh, y=[0.0] * 23, mode="lines",
             line=dict(color=LGRAY, width=1.0, dash="dot"),
             name="Independent (0.00)", hoverinfo="skip"),
        dict(x=rh, y=adj, mode="lines+markers",
             line=dict(color=BLUE, width=2.5),
             marker=dict(size=5.5, color=BLUE, symbol="circle",
                         line=dict(color="white", width=1)),
             name=f"GC-50  (avg = {avg:.3f})",
             hovertemplate="H%{x}−H%{x}+1  ·  r = <b>%{y:.4f}</b><extra></extra>"),
    ]
    layout = _layout(
        title=_title("Adjacent-Hour Correlation",
                     "Higher = stronger temporal realism  ·  GC-50 should approach the actual benchmark"),
        xaxis=_xax("Hour Pair  (h → h+1)", tickvals=list(range(2, 25)), range=[1.5, 24.5]),
        yaxis=_yax("Pearson Correlation (r)", range=[-0.05, 1.08]),
    )
    return {"id": "plot_08_adj_corr", "title": "Adjacent-Hour Correlation",
            "data": traces, "layout": layout}


# ── 09: Peak Hour Frequency ───────────────────────────────────────────────────
def _plot_peak_hour(m) -> dict:
    hrs    = list(range(1, 25))
    freq   = m["peak_hr_freq"]
    pct    = [100.0 * v / m["n_scenarios"] for v in freq]
    mode_h = m["peak_hr_mode"]
    colors = [AMBER if h == mode_h else TEAL for h in hrs]
    opacities = [1.0 if h == mode_h else 0.72 for h in hrs]

    traces = [dict(
        x=hrs, y=pct, type="bar",
        marker=dict(
            color=colors,
            opacity=opacities,
            line=dict(color="white", width=0.6),
        ),
        name="Peak Hour Probability (%)",
        hovertemplate="Hour %{x}  ·  <b>%{y:.1f}%</b> of scenarios<extra></extra>",
    )]
    layout = _layout(
        title=_title("Peak Hour Probability Distribution",
                     f"Most likely peak: Hour {mode_h}  ·  "
                     f"{m['peak_hr_mode_pct']:.1f}% of {m['n_scenarios']} scenarios  ·  Amber = mode"),
        xaxis=_xax("Hour of Day", tickvals=list(range(1, 25)), range=[0.5, 24.5]),
        yaxis=_yax("Probability (%)", ticksuffix="%"),
        bargap=0.18,
        showlegend=False,
    )
    return {"id": "plot_09_peak_hour", "title": "Peak Hour Distribution",
            "data": traces, "layout": layout}


# ── 10: Ramp Band ─────────────────────────────────────────────────────────────
def _plot_ramp_band(m) -> dict:
    rh    = list(range(2, 25))
    ramps = np.array(m["ramps"])
    rp05  = np.percentile(ramps,  5, axis=0).tolist()
    rp25  = np.percentile(ramps, 25, axis=0).tolist()
    rp50  = np.percentile(ramps, 50, axis=0).tolist()
    rp75  = np.percentile(ramps, 75, axis=0).tolist()
    rp95  = np.percentile(ramps, 95, axis=0).tolist()
    rmean = ramps.mean(axis=0).tolist()

    traces = [
        dict(x=rh + rh[::-1], y=rp05 + rp95[::-1],
             fill="toself", fillcolor=BAND_OUTER,
             line=dict(color="rgba(0,0,0,0)"), name="P05 – P95 Band",
             hoverinfo="skip"),
        dict(x=rh + rh[::-1], y=rp25 + rp75[::-1],
             fill="toself", fillcolor=BAND_INNER,
             line=dict(color="rgba(0,0,0,0)"), name="P25 – P75 Band",
             hoverinfo="skip"),
        dict(x=[rh[0] - 0.3, rh[-1] + 0.3], y=[0, 0], mode="lines",
             line=dict(color=LGRAY, width=1.2, dash="dot"),
             name="Zero", hoverinfo="skip"),
        dict(x=rh, y=rp50, mode="lines",
             line=dict(color=VIOLET, width=1.5, dash="dot"), name="Median (P50)",
             hovertemplate="H%{x}  ·  P50: <b>%{y:,.0f} MW/h</b><extra></extra>"),
        dict(x=rh, y=rmean, mode="lines",
             line=dict(color=BLUE, width=2.2, dash="dash"), name="Scenario Mean",
             hovertemplate="H%{x}  ·  Mean: <b>%{y:,.0f} MW/h</b><extra></extra>"),
    ]
    layout = _layout(
        title=_title("Ramp Uncertainty Band",
                     f"{m['target_date']}  ·  P05–P95 corridor across {m['n_scenarios']} scenarios"),
        xaxis=_xax("Ramp Ending Hour", tickvals=list(range(2, 25)), range=[1.5, 24.5]),
        yaxis=_yax("Ramp Rate (MW / hour)", tickformat=","),
    )
    return {"id": "plot_10_ramp_band", "title": "Ramp Band",
            "data": traces, "layout": layout}


# ── 11: Ramp Box Plot ─────────────────────────────────────────────────────────
def _plot_ramp_boxplot(m) -> dict:
    rh    = list(range(2, 25))
    ramps = np.array(m["ramps"])
    traces = []
    for idx, h in enumerate(rh):
        traces.append(dict(
            x=[h] * m["n_scenarios"],
            y=ramps[:, idx].tolist(),
            type="box",
            marker=dict(color=TEAL, opacity=0.6, size=2.5),
            line=dict(color=TEAL, width=1.2),
            fillcolor="rgba(15,118,110,0.18)",
            showlegend=(idx == 0), name="Ramp Scenarios",
            boxpoints=False,
            whiskerwidth=0.6,
            hovertemplate=f"H{h}  ·  %{{y:,.0f}} MW/h<extra></extra>",
        ))
    traces.append(dict(
        x=[rh[0] - 0.3, rh[-1] + 0.3], y=[0, 0], mode="lines",
        line=dict(color=LGRAY, width=1.2, dash="dot"),
        name="Zero", hoverinfo="skip",
    ))
    layout = _layout(
        title=_title("Hourly Ramp Distribution",
                     f"{m['target_date']}  ·  {m['n_scenarios']} scenarios  ·  whiskers = P05 / P95"),
        xaxis=_xax("Ramp Ending Hour", tickvals=list(range(2, 25)), range=[1.5, 24.5]),
        yaxis=_yax("Ramp Rate (MW / hour)", tickformat=","),
        boxmode="overlay",
    )
    return {"id": "plot_11_ramp_boxplot", "title": "Ramp Box Plot",
            "data": traces, "layout": layout}


# ── 12: Ramp Std Dev ──────────────────────────────────────────────────────────
def _plot_ramp_std(m) -> dict:
    rh      = list(range(2, 25))
    ramps   = np.array(m["ramps"])
    r_std   = ramps.std(axis=0, ddof=1).tolist()
    abs_p95 = np.percentile(np.abs(ramps), 95, axis=0).tolist()

    traces = [
        dict(x=[h - 0.22 for h in rh], y=r_std,
             type="bar", width=0.40,
             marker=dict(color=TEAL, opacity=0.82,
                         line=dict(color="white", width=0.5)),
             name="Ramp Std Dev (MW/h)",
             hovertemplate="H%{x:.0f}  ·  Std: <b>%{y:,.0f} MW/h</b><extra></extra>"),
        dict(x=[h + 0.22 for h in rh], y=abs_p95,
             type="bar", width=0.40,
             marker=dict(color=ORANGE, opacity=0.78,
                         line=dict(color="white", width=0.5)),
             name="|Ramp| P95 (MW/h)",
             hovertemplate="H%{x:.0f}  ·  |Ramp| P95: <b>%{y:,.0f} MW/h</b><extra></extra>"),
    ]
    layout = _layout(
        title=_title("Ramp Uncertainty — Std Dev & Extreme Ramps",
                     "Teal = standard deviation  ·  Orange = 95th-percentile absolute ramp"),
        xaxis=_xax("Ramp Ending Hour", tickvals=list(range(2, 25)), range=[1.5, 24.5]),
        yaxis=_yax("Ramp Rate (MW / hour)", tickformat=","),
        barmode="group", bargap=0.12,
    )
    return {"id": "plot_12_ramp_std", "title": "Ramp Uncertainty",
            "data": traces, "layout": layout}


# ── 13: Zone Daily Energy ─────────────────────────────────────────────────────
def _plot_zone_energy(m) -> dict:
    zd      = m["zone_daily"]
    zones   = [d["zone"] for d in zd]
    means   = [d["mean"] for d in zd]
    p05s    = [d["p05"] for d in zd]
    p95s    = [d["p95"] for d in zd]
    err_lo  = [means[i] - p05s[i] for i in range(len(zones))]
    err_hi  = [p95s[i] - means[i] for i in range(len(zones))]
    peaks   = [d["peak_mean"] for d in zd]

    # Color gradient across zones (light → dark teal/blue)
    n = len(zones)
    bar_colors = [
        f"rgba({int(3 + 9*i/(max(n-1,1)))}, {int(105 - 35*i/(max(n-1,1)))}, "
        f"{int(161 - 50*i/(max(n-1,1)))}, 0.82)"
        for i in range(n)
    ]

    traces = [
        dict(
            x=zones, y=means, type="bar",
            marker=dict(color=bar_colors,
                        line=dict(color="white", width=0.8)),
            name="Mean Daily Energy (MWh)",
            error_y=dict(
                type="data", symmetric=False,
                array=err_hi, arrayminus=err_lo,
                color=NAVY, thickness=1.8, width=5,
            ),
            hovertemplate="%{x}<br>Mean: <b>%{y:,.0f} MWh</b><extra></extra>",
        ),
        dict(
            x=zones, y=peaks, mode="markers",
            marker=dict(symbol="diamond", size=8, color=AMBER,
                        line=dict(color="white", width=1)),
            name="Mean Peak Load (MW)",
            hovertemplate="%{x}<br>Mean Peak: <b>%{y:,.0f} MW</b><extra></extra>",
        ),
    ]
    layout = _layout(
        title=_title("Zonal Daily Energy",
                     "Bars = scenario mean daily energy  ·  Error bars = P05–P95  ·  ◆ = mean peak load"),
        xaxis=dict(title=dict(text="NYISO Zone", font=dict(size=11.5, color="#334155")),
                   tickfont=dict(size=10, color="#475569"),
                   gridcolor="#EDF2F7", showgrid=False,
                   linecolor="#E2E8F0", linewidth=1),
        yaxis=_yax("Daily Energy (MWh)", tickformat=",.0f"),
        bargap=0.28,
    )
    return {"id": "plot_13_zone_energy", "title": "Zone Daily Energy",
            "data": traces, "layout": layout}


# ── 14: Reserve Requirements ──────────────────────────────────────────────────
def _plot_reserve(m) -> dict:
    hrs  = list(range(1, 25))
    up95 = m["reserve_up_p95"]
    dn05 = m["reserve_dn_p05"]
    band = m["band_width"]

    traces = [
        dict(x=[h - 0.22 for h in hrs], y=up95,
             type="bar", width=0.42,
             marker=dict(color=BLUE, opacity=0.82,
                         line=dict(color="white", width=0.5)),
             name="Up-Reserve P95 (MW)",
             hovertemplate="H%{x:.0f}  ·  Up-Rsv P95: <b>%{y:,.0f} MW</b><extra></extra>"),
        dict(x=[h + 0.22 for h in hrs], y=dn05,
             type="bar", width=0.42,
             marker=dict(color=RED, opacity=0.78,
                         line=dict(color="white", width=0.5)),
             name="Dn-Reserve P05 (MW)",
             hovertemplate="H%{x:.0f}  ·  Dn-Rsv P05: <b>%{y:,.0f} MW</b><extra></extra>"),
        dict(x=hrs, y=band, mode="lines+markers",
             line=dict(color=AMBER, width=2.2),
             marker=dict(size=5, color=AMBER, symbol="diamond",
                         line=dict(color="white", width=1)),
             name="P05–P95 Band Width (MW)",
             yaxis="y2",
             hovertemplate="H%{x}  ·  Band: <b>%{y:,.0f} MW</b><extra></extra>"),
    ]
    y2 = copy.deepcopy(_AX)
    y2.update(dict(
        title="P05–P95 Band Width (MW)",
        overlaying="y", side="right",
        tickfont=dict(color=AMBER, size=10),
        title_font=dict(color=AMBER, size=11),
        showgrid=False, tickformat=",",
    ))
    layout = _layout(
        title=_title("Operating Reserve Requirements by Hour",
                     "Blue = upward reserve (P95)  ·  Red = downward reserve (P05)  ·  ◆ = scenario spread"),
        xaxis=_xax("Hour of Day", tickvals=list(range(1, 25)), range=[0.5, 24.5]),
        yaxis=_yax("Reserve Requirement (MW)", tickformat=","),
        yaxis2=y2,
        margin=dict(l=72, r=78, t=80, b=56),
        barmode="group", bargap=0.08,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(255,255,255,0)", font=dict(size=10.5),
        ),
    )
    return {"id": "plot_14_reserve", "title": "Reserve Requirements",
            "data": traces, "layout": layout}
