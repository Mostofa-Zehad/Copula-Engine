"""
NYISO Gaussian Copula Load Uncertainty Scenario Generator
Flask Web Application
"""
import warnings
warnings.filterwarnings("ignore")

import os
import json
import uuid
import tempfile
import traceback
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

from copula.engine import run_copula, CopulaParams, save_excel
from copula.plots import generate_all_plots

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

DATA_DIR = Path(__file__).parent / "data"
TEMP_DIR = Path(tempfile.gettempdir()) / "nyiso_copula_sessions"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "No JSON payload received"}), 400

        for field in ("target_date", "forecast_24h"):
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400

        if len(data["forecast_24h"]) != 24:
            return jsonify({"success": False,
                            "error": "forecast_24h must contain exactly 24 values"}), 400

        params = CopulaParams(
            target_date=data["target_date"],
            forecast_24h=data["forecast_24h"],
            hdh=data.get("hdh"),
            temperature_f=data.get("temperature_f"),
            day_type=data.get("day_type", "weekday"),
            historical_years=int(data.get("historical_years", 5)),
            month_window=int(data.get("month_window", 1)),
            n_scenarios=50,
            seed=int(data.get("seed", 42)),
            data_dir=DATA_DIR,
            w_peak=float(data.get("w_peak", 0.30)),
            w_energy=float(data.get("w_energy", 0.25)),
            w_ramp=float(data.get("w_ramp", 0.15)),
            w_downstate=float(data.get("w_downstate", 0.15)),
            w_weather=float(data.get("w_weather", 0.10)),
            w_recency=float(data.get("w_recency", 0.05)),
        )

        sr = run_copula(params)
        plots = generate_all_plots(sr)

        session_id = str(uuid.uuid4())
        excel_path = TEMP_DIR / f"{session_id}.xlsx"
        save_excel(sr, excel_path)

        return jsonify({
            "success": True,
            "plots": plots,
            "metrics": sr.get_metrics_dict(),
            "session_id": session_id,
        })

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
        }), 500


@app.route("/api/download/<session_id>")
def download(session_id):
    try:
        uuid.UUID(session_id)
    except ValueError:
        return jsonify({"error": "Invalid session ID"}), 400

    excel_path = TEMP_DIR / f"{session_id}.xlsx"
    if not excel_path.exists():
        return jsonify({"error": "File not found — sessions expire after server restart"}), 404

    return send_file(
        excel_path,
        as_attachment=True,
        download_name="NYISO_GC50_Scenarios.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/status")
def status():
    zones = list("ABCDEFGHIJK")
    found, missing = [], []
    for z in zones:
        candidates = [
            DATA_DIR / f"Zone {z} Combined Data (Full Year 2011-2025).xlsx",
            DATA_DIR / f"Zone {z} Combined Data.xlsx",
        ]
        if any(c.exists() for c in candidates):
            found.append(f"Zone {z}")
        else:
            missing.append(f"Zone {z}")
    holiday_found = any((DATA_DIR / fn).exists() for fn in [
        "Holiday Calendar Full Year (2011-2025).xlsx",
        "Holiday Calender NDJ (2019-2026).xlsx",
    ])
    return jsonify({
        "data_dir": str(DATA_DIR),
        "zones_found": found,
        "zones_missing": missing,
        "holiday_found": holiday_found,
        "ready": not missing and holiday_found,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
