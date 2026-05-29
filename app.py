"""
NYISO Gaussian Copula Load Uncertainty Scenario Generator
Flask Web Application
"""
import warnings
warnings.filterwarnings("ignore")

import os
import re
import json
import uuid
import tempfile
import traceback
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file

from copula.engine import run_copula, CopulaParams, save_excel, detect_day_type, lookup_weather
from copula.plots import generate_all_plots

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

DATA_DIR = Path(__file__).parent / "data"
TEMP_DIR = Path(tempfile.gettempdir()) / "nyiso_copula_sessions"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _find_holiday_file():
    for fn in ["Holiday Calendar Full Year (2011-2025).xlsx",
               "Holiday Calender NDJ (2019-2026).xlsx"]:
        p = DATA_DIR / fn
        if p.exists():
            return p
    return None


def _find_zone_a_file():
    for fn in ["Zone A Combined Data (Full Year 2011-2025).xlsx",
               "Zone A Combined Data.xlsx"]:
        p = DATA_DIR / fn
        if p.exists():
            return p
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/date-info")
def date_info():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "date parameter required"}), 400
    try:
        ts = pd.Timestamp(date_str)
    except Exception:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    day_info = detect_day_type(ts, _find_holiday_file())

    hdh = None
    zone_a = _find_zone_a_file()
    if zone_a:
        try:
            hdh = lookup_weather(ts, zone_a)
        except Exception:
            pass

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]

    return jsonify({
        "day_type":     day_info["day_type"],
        "holiday_name": day_info.get("holiday_name"),
        "label":        day_info.get("label"),
        "weekday_name": day_names[day_info["weekday_num"]],
        "hdh":          round(hdh, 1) if hdh is not None else None,
        "date_display": ts.strftime("%B %-d"),
    })


@app.route("/api/upload-forecast", methods=["POST"])
def upload_forecast():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    f = request.files["file"]
    fname = f.filename.lower()

    try:
        if fname.endswith(".xlsx") or fname.endswith(".xls"):
            df = pd.read_excel(f, header=None)
            nums = []
            # Try each column, pick first that has >= 24 numeric values
            for col in df.columns:
                col_vals = pd.to_numeric(df[col], errors="coerce").dropna().tolist()
                if len(col_vals) >= 24:
                    nums = col_vals
                    break
            if len(nums) < 24:
                # Flatten all cells
                flat = []
                for col in df.columns:
                    flat.extend(pd.to_numeric(df[col], errors="coerce").dropna().tolist())
                nums = flat
        else:
            text = f.read().decode("utf-8", errors="ignore")
            nums = [float(x) for x in re.split(r"[\n,;\t\s]+", text.strip()) if x.strip()]

        # Keep positive values only
        nums = [n for n in nums if n > 0]

        if len(nums) < 24:
            return jsonify({
                "success": False,
                "error": f"Found only {len(nums)} valid values — need at least 24"
            }), 422

        return jsonify({"success": True, "values": [round(v, 1) for v in nums[:24]]})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
            day_type=data.get("day_type"),          # None → auto-detected in engine
            historical_years=int(data.get("historical_years", 5)),
            day_window=int(data.get("day_window", 30)),
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
        return jsonify({"success": False, "error": str(e)}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 200
    except Exception as e:
        # Return 200 so Render's proxy doesn't replace the JSON body with HTML
        return jsonify({
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
        }), 200


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
    holiday_found = _find_holiday_file() is not None
    return jsonify({
        "data_dir": str(DATA_DIR),
        "zones_found": found,
        "zones_missing": missing,
        "holiday_found": holiday_found,
        "ready": not missing and holiday_found,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7862))
    app.run(host="0.0.0.0", port=port, debug=False)
