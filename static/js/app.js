/* ═══════════════════════════════════════════════════════════════════
   NYISO Copula Scenario Generator — Frontend Application
   ═══════════════════════════════════════════════════════════════════ */

"use strict";

// ── Sample forecasts ─────────────────────────────────────────────────────────
const SAMPLE_WINTER = [
  15297, 14885, 14625, 14563, 14803, 15587, 16992, 18179,
  18705, 18820, 18624, 18461, 18338, 18456, 18685, 19247,
  20083, 20870, 20921, 20602, 20173, 19462, 18517, 17628
];

const SAMPLE_SUMMER = [
  17800, 17100, 16700, 16500, 16800, 17600, 19200, 21000,
  22500, 23800, 24600, 25100, 25400, 25700, 25900, 26100,
  26400, 26900, 27100, 26600, 25800, 24500, 22800, 20500
];

const CHART_CATEGORIES = {
  scenarios:   ["plot_01_scenario_band", "plot_02_fan"],
  uncertainty: ["plot_03_crps", "plot_04_load_boxplot", "plot_05_std_cv",
                "plot_06_corr_heatmap", "plot_07_daily_energy", "plot_08_adj_corr",
                "plot_09_peak_hour"],
  ramps:       ["plot_10_ramp_band", "plot_11_ramp_boxplot", "plot_12_ramp_std"],
  operations:  ["plot_13_zone_energy", "plot_14_reserve"],
};

const WIDE_CHARTS = ["plot_02_fan", "plot_06_corr_heatmap",
                     "plot_08_adj_corr", "plot_14_reserve"];

let currentSessionId = null;
let allPlots = [];

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  buildForecastGrid();
  checkDataStatus();
  setDefaultDate();
  setupChartNav();
});

function setDefaultDate() {
  const el = document.getElementById("targetDate");
  if (el) el.value = "2026-01-15";
}

// ── Data status check ─────────────────────────────────────────────────────────
async function checkDataStatus() {
  const badge = document.getElementById("statusBadge");
  try {
    const res = await fetch("/api/status");
    const d = await res.json();
    if (d.ready) {
      badge.className = "status-badge status-ready";
      badge.innerHTML = `<i class="bi bi-circle-fill me-1"></i> Data Ready (${d.zones_found.length}/11 Zones)`;
    } else {
      badge.className = "status-badge status-error";
      const missing = d.zones_missing.length;
      badge.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i> ${missing} Zone(s) Missing`;
    }
  } catch {
    badge.className = "status-badge status-error";
    badge.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i> Server Offline`;
  }
}

// ── Forecast grid ─────────────────────────────────────────────────────────────
function buildForecastGrid() {
  const grid = document.getElementById("forecastGrid");
  if (!grid) return;
  grid.innerHTML = "";
  for (let h = 1; h <= 24; h++) {
    const cell = document.createElement("div");
    cell.className = "forecast-cell";
    cell.innerHTML = `
      <label>H${String(h).padStart(2, "0")}</label>
      <input type="number" id="fc_h${h}" placeholder="MW"
             min="0" max="100000" step="1"
             oninput="markCell(this)" autocomplete="off"/>`;
    grid.appendChild(cell);
  }
}

function markCell(input) {
  input.classList.toggle("has-value", input.value.trim() !== "");
}

function getForecast24() {
  const vals = [];
  for (let h = 1; h <= 24; h++) {
    const v = parseFloat(document.getElementById(`fc_h${h}`)?.value);
    vals.push(isNaN(v) ? 0 : v);
  }
  return vals;
}

function setForecast24(arr) {
  for (let h = 1; h <= 24; h++) {
    const el = document.getElementById(`fc_h${h}`);
    if (!el) continue;
    el.value = arr[h - 1] ?? "";
    el.classList.toggle("has-value", !!el.value);
  }
}

function loadSampleForecast()       { setForecast24(SAMPLE_WINTER); }
function loadSampleForecastSummer() { setForecast24(SAMPLE_SUMMER); }
function clearForecast()            { setForecast24(Array(24).fill("")); }

// ── CSV upload ────────────────────────────────────────────────────────────────
function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const text = e.target.result;
    const nums = text.split(/[\n,;\t\s]+/)
      .map(s => parseFloat(s.trim()))
      .filter(n => !isNaN(n));
    if (nums.length >= 24) {
      setForecast24(nums.slice(0, 24));
      showToast(`Loaded ${Math.min(nums.length, 24)} values from file`, "success");
    } else {
      showToast(`Found only ${nums.length} values — need 24`, "error");
    }
  };
  reader.readAsText(file);
  input.value = "";
}

// ── Weight sum updater ────────────────────────────────────────────────────────
function updateWeightSum() {
  const ids = ["wPeak", "wEnergy", "wRamp", "wDownstate", "wWeather", "wRecency"];
  const sum = ids.reduce((acc, id) => {
    const v = parseFloat(document.getElementById(id)?.value) || 0;
    return acc + v;
  }, 0);
  const sumEl = document.getElementById("weightSumVal");
  const warnEl = document.getElementById("weightSumWarn");
  if (!sumEl) return;
  sumEl.textContent = sum.toFixed(2);
  const ok = Math.abs(sum - 1.0) < 0.02;
  sumEl.className = ok ? "text-success" : "text-danger";
  warnEl?.classList.toggle("d-none", ok);
}

// ── Chart category filter ─────────────────────────────────────────────────────
function setupChartNav() {
  document.querySelectorAll(".chart-nav-link").forEach(link => {
    link.addEventListener("click", e => {
      e.preventDefault();
      document.querySelectorAll(".chart-nav-link").forEach(l => l.classList.remove("active"));
      link.classList.add("active");
      const cat = link.dataset.cat;
      filterCharts(cat);
    });
  });
}

function filterCharts(cat) {
  document.querySelectorAll(".plot-card").forEach(card => {
    if (cat === "all") {
      card.style.display = "";
    } else {
      const ids = CHART_CATEGORIES[cat] || [];
      card.style.display = ids.includes(card.dataset.plotId) ? "" : "none";
    }
  });
  // Re-relayout visible Plotly charts to fix sizing
  setTimeout(() => {
    document.querySelectorAll(".plot-container[data-plot-id]").forEach(el => {
      if (el.closest(".plot-card").style.display !== "none") {
        Plotly.Plots.resize(el);
      }
    });
  }, 50);
}

// ── Loading animation ─────────────────────────────────────────────────────────
const LOAD_STEPS = ["ls1", "ls2", "ls3", "ls4", "ls5"];
let loadTimer = null;

function animateLoadingSteps() {
  const steps = LOAD_STEPS.map(id => document.getElementById(id));
  steps.forEach((s, i) => {
    if (i === 0) {
      s?.classList.add("active");
    } else {
      s?.classList.remove("active", "done");
      s?.querySelector("i")?.className.replace(/bi-\S+/, "bi-circle");
    }
  });

  let idx = 0;
  loadTimer = setInterval(() => {
    if (idx < steps.length) {
      const prev = steps[idx - 1];
      const cur  = steps[idx];
      if (prev) {
        prev.classList.remove("active");
        prev.classList.add("done");
        const ico = prev.querySelector("i");
        if (ico) ico.className = "bi bi-check-circle-fill me-2";
      }
      if (cur) {
        cur.classList.add("active");
        const ico = cur.querySelector("i");
        if (ico) ico.className = "bi bi-arrow-repeat me-2";
      }
      idx++;
    }
  }, 1200);
}

function stopLoadingAnimation() {
  if (loadTimer) { clearInterval(loadTimer); loadTimer = null; }
}

// ── MAIN: Generate scenarios ──────────────────────────────────────────────────
async function generateScenarios() {
  const btn = document.getElementById("generateBtn");
  const targetDate = document.getElementById("targetDate")?.value;

  // Validate
  if (!targetDate) {
    showToast("Please select a target date", "error");
    return;
  }

  const forecast24h = getForecast24();
  const nonZero = forecast24h.filter(v => v > 0).length;
  if (nonZero < 12) {
    showToast("Please enter at least 12 hourly forecast values (MW)", "error");
    return;
  }

  // Collect form data
  const dayType       = document.querySelector('input[name="dayType"]:checked')?.value || "weekday";
  const histYears     = parseInt(document.getElementById("histYears")?.value || "5");
  const monthWindow   = parseInt(document.getElementById("monthWindow")?.value || "1");
  const tempF         = parseFloat(document.getElementById("tempF")?.value) || null;
  const hdhOverride   = parseFloat(document.getElementById("hdh")?.value) || null;
  const seed          = parseInt(document.getElementById("randSeed")?.value || "42");
  const wPeak         = parseFloat(document.getElementById("wPeak")?.value || "0.30");
  const wEnergy       = parseFloat(document.getElementById("wEnergy")?.value || "0.25");
  const wRamp         = parseFloat(document.getElementById("wRamp")?.value || "0.15");
  const wDownstate    = parseFloat(document.getElementById("wDownstate")?.value || "0.15");
  const wWeather      = parseFloat(document.getElementById("wWeather")?.value || "0.10");
  const wRecency      = parseFloat(document.getElementById("wRecency")?.value || "0.05");

  const payload = {
    target_date: targetDate,
    forecast_24h: forecast24h,
    day_type: dayType,
    historical_years: histYears,
    month_window: monthWindow,
    seed,
    w_peak: wPeak, w_energy: wEnergy, w_ramp: wRamp,
    w_downstate: wDownstate, w_weather: wWeather, w_recency: wRecency,
  };
  if (tempF !== null && !isNaN(tempF))  payload.temperature_f = tempF;
  if (hdhOverride !== null && !isNaN(hdhOverride)) payload.hdh = hdhOverride;

  // UI transitions
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Running Copula…`;
  showSection("loading");
  animateLoadingSteps();

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    stopLoadingAnimation();

    if (!data.success) {
      showSection("error", data.error || "Unknown server error");
      return;
    }

    currentSessionId = data.session_id;
    allPlots = data.plots;
    renderResults(data.metrics, data.plots);
    showSection("results");
    checkDataStatus();

  } catch (err) {
    stopLoadingAnimation();
    showSection("error", `Network error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-cpu me-2"></i>Generate 50 Scenarios`;
  }
}

// ── Section visibility ────────────────────────────────────────────────────────
function showSection(section, errorMsg = "") {
  document.getElementById("resultsPlaceholder")?.classList.add("d-none");
  document.getElementById("loadingState")?.classList.add("d-none");
  document.getElementById("resultsSection")?.classList.add("d-none");

  const errorEl = document.getElementById("errorSection");
  if (errorEl) errorEl.remove();

  if (section === "loading") {
    document.getElementById("loadingState")?.classList.remove("d-none");
  } else if (section === "results") {
    document.getElementById("resultsSection")?.classList.remove("d-none");
    window.scrollTo({ top: document.getElementById("resultsSection")?.offsetTop - 80, behavior: "smooth" });
  } else if (section === "error") {
    const div = document.createElement("div");
    div.id = "errorSection";
    div.className = "error-card fade-in";
    div.innerHTML = `
      <div class="error-title"><i class="bi bi-exclamation-triangle-fill me-2"></i>Generation Failed</div>
      <div class="error-msg">${escapeHtml(errorMsg)}</div>
      <div class="mt-3 text-muted small">
        <strong>Common fixes:</strong> Verify data files are in <code>data/</code>,
        increase historical years, or widen the month window.
      </div>`;
    const right = document.querySelector(".col-xl-8, .col-lg-7");
    if (right) right.prepend(div);
  } else {
    document.getElementById("resultsPlaceholder")?.classList.remove("d-none");
  }
}

// ── Render full results ───────────────────────────────────────────────────────
function renderResults(m, plots) {
  renderKPICards(m);
  renderPlots(plots);
  renderAnalogTable(m);
}

// ── KPI Cards ─────────────────────────────────────────────────────────────────
function renderKPICards(m) {
  const container = document.getElementById("kpiCards");
  if (!container) return;

  const kpis = [
    {
      label: "Analog Days Used",
      value: m.n_analogs.toLocaleString(),
      sub: `${m.historical_years || "–"}yr window`,
      cls: "kpi-navy",
    },
    {
      label: "Copula Dimensions",
      value: m.n_dimensions,
      sub: "11 zones × 24 hours",
      cls: "kpi-purple",
    },
    {
      label: "LW Shrinkage",
      value: m.shrink_coeff,
      sub: "Ledoit-Wolf coefficient",
      cls: "",
    },
    {
      label: "Mean Daily Energy",
      value: `${(m.daily_E_mean / 1000).toFixed(1)}k`,
      sub: `P05: ${(m.daily_E_p05 / 1000).toFixed(1)}k · P95: ${(m.daily_E_p95 / 1000).toFixed(1)}k MWh`,
      cls: "kpi-green",
    },
    {
      label: "Most Likely Peak Hour",
      value: `H${String(m.peak_hr_mode).padStart(2, "0")}`,
      sub: `${m.peak_hr_mode_pct}% probability`,
      cls: "kpi-gold",
    },
    {
      label: "Adj-Hour Correlation",
      value: m.adj_corr_mean.toFixed(3),
      sub: "Temporal structure (≈1.0 = realistic)",
      cls: "kpi-orange",
    },
    {
      label: "Spread CRPS",
      value: `${m.mean_crps.toFixed(0)} MW`,
      sub: "Mean hourly spread metric",
      cls: "kpi-red",
    },
    {
      label: "Scenarios Generated",
      value: m.n_scenarios,
      sub: `P = ${(1 / m.n_scenarios).toFixed(4)} each`,
      cls: "",
    },
  ];

  container.innerHTML = kpis.map((k, i) => `
    <div class="col-xl-3 col-md-4 col-6 fade-in fade-in-delay-${Math.min(i + 1, 3)}">
      <div class="kpi-card ${k.cls}">
        <div class="kpi-label">${k.label}</div>
        <div class="kpi-value">${k.value}</div>
        <div class="kpi-sub">${k.sub}</div>
      </div>
    </div>`).join("");
}

// ── Plot rendering ────────────────────────────────────────────────────────────
const CHART_ICONS = {
  plot_01_scenario_band: "bi-graph-up",
  plot_02_fan:           "bi-activity",
  plot_03_crps:          "bi-bar-chart",
  plot_04_load_boxplot:  "bi-box",
  plot_05_std_cv:        "bi-distribute-vertical",
  plot_06_corr_heatmap:  "bi-grid-3x3",
  plot_07_daily_energy:  "bi-bar-chart-steps",
  plot_08_adj_corr:      "bi-link-45deg",
  plot_09_peak_hour:     "bi-lightning-charge",
  plot_10_ramp_band:     "bi-arrows-vertical",
  plot_11_ramp_boxplot:  "bi-box-arrow-up",
  plot_12_ramp_std:      "bi-bezier2",
  plot_13_zone_energy:   "bi-building",
  plot_14_reserve:       "bi-shield-check",
};

function renderPlots(plots) {
  const grid = document.getElementById("plotGrid");
  if (!grid) return;
  grid.innerHTML = "";

  plots.forEach((p, idx) => {
    const isWide = WIDE_CHARTS.includes(p.id);
    const icon = CHART_ICONS[p.id] || "bi-graph-up";
    const containerId = `pc_${p.id}`;

    const card = document.createElement("div");
    card.className = `plot-card${isWide ? " wide" : ""} fade-in`;
    card.dataset.plotId = p.id;
    card.style.animationDelay = `${0.05 * idx}s`;
    card.innerHTML = `
      <div class="plot-card-header">
        <span class="plot-card-title">
          <i class="bi ${icon} me-2"></i>${p.title}
        </span>
        <button class="btn-expand" onclick="expandChart('${containerId}', '${escapeHtml(p.title)}')" title="Expand">
          <i class="bi bi-fullscreen"></i>
        </button>
      </div>
      <div class="plot-container" id="${containerId}" data-plot-id="${p.id}"></div>`;
    grid.appendChild(card);

    const layout = {
      ...p.layout,
      autosize: true,
      height: isWide ? 420 : 350,
    };

    Plotly.newPlot(containerId, p.data, layout, {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"],
      displaylogo: false,
      toImageButtonOptions: {
        format: "png",
        filename: `NYISO_${p.id}`,
        scale: 2,
      },
    });
  });
}

// ── Expand chart to modal ────────────────────────────────────────────────────
function expandChart(containerId, title) {
  const src = document.getElementById(containerId);
  if (!src || !src._fullLayout) return;

  // Remove existing modal if any
  document.getElementById("chartModal")?.remove();

  const modal = document.createElement("div");
  modal.id = "chartModal";
  modal.style.cssText = `
    position:fixed;inset:0;background:rgba(11,31,58,.85);z-index:9999;
    display:flex;align-items:center;justify-content:center;padding:20px;`;
  modal.innerHTML = `
    <div style="background:white;border-radius:12px;width:100%;max-width:1100px;
                box-shadow:0 25px 60px rgba(0,0,0,.4);overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;
                  padding:12px 20px;background:#F8FAFC;border-bottom:1px solid #E2E8F0;">
        <strong style="color:#0B1F3A">${title}</strong>
        <button onclick="document.getElementById('chartModal').remove()"
                style="background:none;border:none;font-size:20px;cursor:pointer;color:#94A3B8">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div id="expandedChart" style="padding:8px;min-height:500px;"></div>
    </div>`;
  document.body.appendChild(modal);
  modal.addEventListener("click", e => { if (e.target === modal) modal.remove(); });

  const data = Plotly.d3.select(src).node().__data__[0];
  Plotly.newPlot("expandedChart",
    JSON.parse(JSON.stringify(src.data)),
    { ...JSON.parse(JSON.stringify(src.layout)), height: 520, autosize: true },
    { responsive: true, displaylogo: false }
  );
}

// ── Analog table ──────────────────────────────────────────────────────────────
function renderAnalogTable(m) {
  // The metrics dict doesn't carry analog_df directly; we only have what was computed.
  // We show the top analog info from what we have — if the server returns analog_scores we use it.
  // For now display a summary note.
  const thead = document.querySelector("#analogTable thead");
  const tbody = document.querySelector("#analogTable tbody");
  if (!thead || !tbody) return;

  // We don't have analog_df in metrics dict — it will be in the Excel file.
  // Show informational row.
  thead.innerHTML = `<tr>
    <th>Rank</th><th>Metric</th><th>Value</th>
  </tr>`;
  const rows = [
    ["#1", "Analog Pool Size", `${m.n_analogs} matching days`],
    ["#2", "Ledoit-Wolf Shrinkage", m.shrink_coeff],
    ["#3", "Copula Dimensions", `${m.n_dimensions} (11 zones × 24 hr)`],
    ["#4", "Adj-Hour Corr (avg)", m.adj_corr_mean.toFixed(4)],
    ["#5", "Scenario Mean Daily Energy", `${m.daily_E_mean.toLocaleString()} MWh`],
    ["#6", "Daily Energy P05 – P95", `${m.daily_E_p05.toLocaleString()} – ${m.daily_E_p95.toLocaleString()} MWh`],
    ["#7", "Most Likely Peak Hour", `H${String(m.peak_hr_mode).padStart(2,"0")} (${m.peak_hr_mode_pct}%)`],
    ["#8", "Spread CRPS (mean)", `${m.mean_crps.toFixed(1)} MW`],
  ];
  tbody.innerHTML = rows.map(([rank, metric, val], i) => `
    <tr>
      <td><span class="rank-badge${i < 3 ? " top3" : ""}">${i + 1}</span></td>
      <td>${metric}</td>
      <td><strong>${val}</strong></td>
    </tr>`).join("");
}

// ── Excel download ─────────────────────────────────────────────────────────────
function downloadExcel() {
  if (!currentSessionId) {
    showToast("No session found — please generate scenarios first", "error");
    return;
  }
  const btn = document.getElementById("downloadBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Preparing…`;
  }
  const link = document.createElement("a");
  link.href = `/api/download/${currentSessionId}`;
  link.download = "NYISO_GC50_Scenarios.xlsx";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  setTimeout(() => {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-download me-2"></i>Download Excel`;
    }
    showToast("Excel file downloaded", "success");
  }, 1500);
}

// ── Toast notification ────────────────────────────────────────────────────────
function showToast(msg, type = "info") {
  const colors = {
    success: "#1D9E75",
    error:   "#DC3545",
    info:    "#0D9488",
  };
  const icons = { success: "bi-check-circle-fill", error: "bi-x-circle-fill", info: "bi-info-circle-fill" };

  const toast = document.createElement("div");
  toast.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:10000;
    background:white;border-left:4px solid ${colors[type]};
    border-radius:8px;padding:12px 18px;
    box-shadow:0 8px 24px rgba(0,0,0,.12);
    display:flex;align-items:center;gap:10px;
    font-size:13px;font-weight:600;color:#0B1F3A;
    animation:fadeInUp .3s ease;
    max-width:340px;`;
  toast.innerHTML = `<i class="bi ${icons[type]}" style="color:${colors[type]};font-size:16px"></i>${escapeHtml(msg)}`;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity .3s";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
