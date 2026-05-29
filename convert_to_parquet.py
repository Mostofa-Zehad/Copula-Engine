"""
Run this ONCE locally to convert zone Excel files → Parquet.
Parquet loads 20x faster and uses half the memory on Render's free tier.

Usage:
    cd /path/to/webapp
    python3 convert_to_parquet.py
"""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
PQ_DIR   = DATA_DIR / "parquet"
PQ_DIR.mkdir(exist_ok=True)

ZONES = "ABCDEFGHIJK"

def _load_zone_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Combined Load Error")
    rename = {}
    for c in df.columns:
        cl = str(c).strip().lower()
        if "time" in cl:                        rename[c] = "Time Stamp"
        elif "actual" in cl:                    rename[c] = "Actual"
        elif "forecast" in cl:                  rename[c] = "Forecast"
        elif cl in ["error (mw)", "error mw"]:  rename[c] = "Error_MW"
        elif cl in ["error (%)", "error %"]:    rename[c] = "Error_pct"
    df = df.rename(columns=rename)
    df["Time Stamp"] = pd.to_datetime(df["Time Stamp"])
    df["Date"]  = df["Time Stamp"].dt.floor("D")
    df["Hour"]  = df["Time Stamp"].dt.hour + 1
    return df.sort_values("Time Stamp").reset_index(drop=True)

print("=" * 55)
print("  NYISO Copula — Excel → Parquet Converter")
print("=" * 55)
print(f"  Output: {PQ_DIR}\n")

converted = 0
for z in ZONES:
    out = PQ_DIR / f"zone_{z}.parquet"
    found = False
    for name in [
        f"Zone {z} Combined Data (Full Year 2011-2025).xlsx",
        f"Zone {z} Combined Data.xlsx",
    ]:
        p = DATA_DIR / name
        if p.exists():
            print(f"  Zone {z}  {name[:45]:<45}", end="  ", flush=True)
            df = _load_zone_excel(p)
            df.to_parquet(out, index=False)
            kb = out.stat().st_size // 1024
            print(f"✓  {len(df):>8,} rows  →  {kb:,} KB")
            converted += 1
            found = True
            break
    if not found:
        print(f"  Zone {z}  NOT FOUND — check data/ folder")

# Weather sheet from Zone A
print()
for name in [
    "Zone A Combined Data (Full Year 2011-2025).xlsx",
    "Zone A Combined Data.xlsx",
]:
    p = DATA_DIR / name
    if p.exists():
        print(f"  Weather  {name[:45]:<45}", end="  ", flush=True)
        try:
            df = pd.read_excel(p, sheet_name="Weather", header=1)
            col_map = {}
            for c in df.columns:
                cl = str(c).strip().lower()
                if "date" in cl:  col_map[c] = "Date"
                elif "hdh" in cl: col_map[c] = "HDH"
            df = df.rename(columns=col_map)
            if "Date" in df.columns and "HDH" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.dropna(subset=["HDH"])[["Date", "HDH"]]
                out = PQ_DIR / "zone_A_weather.parquet"
                df.to_parquet(out, index=False)
                kb = out.stat().st_size // 1024
                print(f"✓  {len(df):>8,} rows  →  {kb:,} KB")
            else:
                print("⚠  Date/HDH columns not found — skipped")
        except Exception as ex:
            print(f"✗  {ex}")
        break

print()
if converted == 11:
    print("  All 11 zones converted successfully!")
    print()
    print("  Next steps:")
    print("    git add data/parquet .python-version requirements.txt")
    print("    git add copula/engine.py convert_to_parquet.py")
    print("    git commit -m 'Add parquet data for fast Render loading'")
    print("    git push origin main")
else:
    print(f"  ⚠  Only {converted}/11 zones converted. Check missing files above.")
