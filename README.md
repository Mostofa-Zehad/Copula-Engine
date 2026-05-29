# NYISO Copula Scenario Generator

A professional web application for **probabilistic load uncertainty quantification** using a **Gaussian Copula** fitted to NYISO's 11-zone historical load forecast errors.

Built for power system operators, planners, and researchers who need calibrated scenario sets for unit commitment, reserve sizing, and market analysis.

---

## What It Does

Given a 24-hour load forecast for any day of the year, the engine:

1. **Selects analog days** — scores historical days by peak shape, daily energy, ramp profile, downstate (Zones I/J/K) load, weather (HDH), and recency
2. **Fits a 264-dimensional Gaussian Copula** — 11 zones × 24 hours, using Ledoit-Wolf shrinkage on the correlation matrix
3. **Generates 50 correlated scenarios** — Cholesky-based draws mapped back to MW via probability-weighted empirical quantile
4. **Produces 14 interactive charts** — scenario bands, fan plots, CRPS, box plots, ramp analysis, reserve requirements, zone energy, correlation heatmap, and more
5. **Exports full Excel workbook** — all 50 scenarios by zone and system, hourly summary, ramp stats, reserve requirements, analog day scores

---

## Quickstart (Local)

### 1. Clone the repo
```bash
git clone https://github.com/Mostofa-Zehad/Copula-Engine.git
cd Copula-Engine
```

### 2. Install dependencies
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Add data files
Copy your zone Excel files into the `data/` directory:
```
data/
├── Zone A Combined Data (Full Year 2011-2025).xlsx
├── Zone B Combined Data (Full Year 2011-2025).xlsx
├── ...
├── Zone K Combined Data (Full Year 2011-2025).xlsx
└── Holiday Calendar Full Year (2011-2025).xlsx
```

### 4. Run the app
```bash
python app.py
```
Open `http://localhost:5000` in your browser.

---

## Input Parameters

| Parameter | Description |
|-----------|-------------|
| **Target Date** | Any date in 2011–2025 range |
| **24-Hour Forecast** | System-total load forecast in MW (H01 = midnight–1AM) |
| **Day Type** | Weekday / Weekend / Holiday (filters analog pool) |
| **Temperature (°F)** | Daily average — auto-converted to HDH |
| **HDH** | Heating Degree Hours (manual override) |
| **Historical Years** | How many years of history to search for analogs (1–14) |
| **Month Window** | ±N months around target month to widen analog search |

### Advanced: Analog Scoring Weights

| Weight | Default | Description |
|--------|---------|-------------|
| Peak Shape | 0.30 | How close the historical day's peak matches your forecast |
| Daily Energy | 0.25 | Total MWh similarity |
| Ramp Profile | 0.15 | Hour-to-hour change similarity |
| Downstate Load | 0.15 | NYC-area (Zones I/J/K) load matching |
| Weather (HDH) | 0.10 | Heating degree hour similarity |
| Recency | 0.05 | Bonus for more recent historical years |

---

## Output Charts

| # | Chart | What It Shows |
|---|-------|---------------|
| 01 | Scenario Band | P05/P25/P75/P95 bands + Forecast vs Scenario Mean |
| 02 | Fan Plot | All 50 individual scenario traces |
| 03 | CRPS by Hour | Hourly spread score (lower = tighter) |
| 04 | Load Box Plot | Full distribution per hour |
| 05 | Std Dev & CV% | Uncertainty magnitude by hour |
| 06 | Correlation Heatmap | Hour-to-hour correlation in generated scenarios |
| 07 | Daily Energy Dist. | Distribution of total daily energy across 50 scenarios |
| 08 | Adjacent-Hour Corr. | Temporal realism check (≈1.0 = realistic) |
| 09 | Peak Hour Dist. | Which hour peaks most often across scenarios |
| 10 | Ramp Band | Ramp profile uncertainty (P05–P95) |
| 11 | Ramp Box Plot | Distribution of ramps per hour |
| 12 | Ramp Uncertainty | Std Dev & abs P95 of ramps |
| 13 | Zone Energy | Per-zone daily energy with P05–P95 range |
| 14 | Reserve Requirements | Up/Down operating reserves by hour |

---

## Methodology

```
Historical Load Errors (2011–2025)
         │
         ▼
  Analog Day Scoring
  (6-component distance metric, inverse-distance weights)
         │
         ▼
  Rank-transform errors → Uniform [0,1]
         │
         ▼
  Φ⁻¹ transform → Standard Normal
         │
         ▼
  Ledoit-Wolf Shrinkage → 264×264 Correlation Matrix R
         │
         ▼
  Cholesky decomposition → Correlated Normal samples
         │
         ▼
  Φ CDF → Uniform samples U_sim
         │
         ▼
  Weighted Empirical Quantile → Error samples ε
         │
         ▼
  Load = Forecast / (1 + ε)   [per zone, per hour]
         │
         ▼
  50 Zonal Scenarios → System Total (sum across 11 zones)
```

---

## Project Structure

```
nyiso-copula-scenarios/
├── app.py                  # Flask web application
├── copula/
│   ├── engine.py           # Copula computation engine
│   └── plots.py            # Plotly chart generator
├── templates/
│   └── index.html          # Single-page application
├── static/
│   ├── css/style.css
│   └── js/app.js
├── data/                   # Zone data files (not in git)
├── requirements.txt
└── Procfile                # For Heroku/Railway deployment
```

---

## Deployment

### Heroku
```bash
heroku create nyiso-copula
heroku buildpacks:set heroku/python
git push heroku main
```
Note: Upload data files via a private S3 bucket or Heroku add-on storage.

### Railway / Render
Connect the GitHub repo, set `START_COMMAND = gunicorn app:app --timeout 180`.

---

## References

- Sklar, A. (1959). *Fonctions de répartition à n dimensions et leurs marges*
- Ledoit, O. & Wolf, M. (2004). *A well-conditioned estimator for large-dimensional covariance matrices*
- NYISO Market Operations Manual — Load Forecasting
- Pinson, P. et al. (2007). *Trading Wind Generation From Short-Term Probabilistic Forecasts of Wind Power*

---

*For research and operational planning purposes. Not an official NYISO product.*
