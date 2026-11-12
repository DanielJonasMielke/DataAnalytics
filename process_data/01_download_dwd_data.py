"""Download the DWD station measurements (ground truth) for the station.

Source:   DWD Climate Data Center, hourly station observations (CC BY 4.0, source: Deutscher Wetterdienst)
Content:  air temperature (TT_TU, plus RF_TU = relative humidity) and precipitation (R1 = mm/h,
          WRTR = form of precipitation), hourly, from 2024-04-01 until yesterday
Output:   data/dwd/dwd_01975_air_temperature_hourly.csv
          data/dwd/dwd_01975_precipitation_hourly.csv
          (the downloaded zip files stay in data/dwd/ as well)

The DWD splits each station into two files:
  historical/  checked data, but only up to the last annual update
  recent/      the last ~1.5 years, updated daily, not fully quality-checked yet
We download both, stack them, and where they overlap we keep the checked 'historical' row.
The column 'source' tells which file a row came from; 'QN_*' is the DWD quality level.

Run:      uv run ./process_data/01_download_dwd_data.py
"""

import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd
from common import DATA_DIR, END, START, STATION_ID

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly"
OUT_DIR = DATA_DIR / "dwd"

# folder on the DWD server -> product code used in the file names
PRODUCTS = {
    "air_temperature": "TU",
    "precipitation": "RR",
}

ONE_DAY = 24 * 3600


def find_zip_name(folder, code, period):
    """Look in the directory listing of the DWD server for this station's zip file."""
    listing_url = f"{BASE_URL}/{folder}/{period}/"
    try:
        with urllib.request.urlopen(listing_url, timeout=60) as response:
            html = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code == 404:  # this folder does not exist for this product
            return None
        raise
    if period == "historical":
        pattern = rf"stundenwerte_{code}_{STATION_ID}_\d{{8}}_\d{{8}}_hist\.zip"
    else:
        pattern = rf"stundenwerte_{code}_{STATION_ID}_akt\.zip"
    match = re.search(pattern, html)
    return match.group(0) if match else None


def fetch_station_zip(folder, code, period):
    """Download the station zip (if not already there) and return its path, or None if it does not exist."""
    zip_name = find_zip_name(folder, code, period)
    if zip_name is None:
        return None
    zip_path = OUT_DIR / zip_name
    # historical files never change; 'recent' files are refreshed when older than one day
    fresh_enough = zip_path.exists() and (period == "historical" or time.time() - zip_path.stat().st_mtime < ONE_DAY)
    if not fresh_enough:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  downloading {zip_name} ...")
        part_path = zip_path.with_name(zip_path.name + ".part")
        urllib.request.urlretrieve(f"{BASE_URL}/{folder}/{period}/{zip_name}", part_path)
        part_path.replace(zip_path)  # only a complete download gets the final name
    return zip_path


def read_product(zip_path, source):
    """Read the measurement table ('produkt...' file) from inside the zip."""
    with zipfile.ZipFile(zip_path) as zf:
        product_file = next(name for name in zf.namelist() if name.startswith("produkt"))
        with zf.open(product_file) as f:
            df = pd.read_csv(f, sep=";", skipinitialspace=True, na_values=[-999], encoding="latin-1")
    df.columns = df.columns.str.strip()
    df = df.drop(columns=["eor"], errors="ignore")
    df.insert(0, "time", pd.to_datetime(df["MESS_DATUM"].astype(str), format="%Y%m%d%H"))  # UTC
    df["source"] = source
    return df


def build_product(folder, code):
    parts = []
    for period in ["historical", "recent"]:
        zip_path = fetch_station_zip(folder, code, period)
        if zip_path is None:
            print(f"  note: no '{period}' file for station {STATION_ID} in {folder}")
            continue
        parts.append(read_product(zip_path, period))
    if not parts:
        raise RuntimeError(
            f"Station {STATION_ID} has no hourly '{folder}' data on the DWD server. "
            f"Pick a nearby station from {BASE_URL}/{folder}/recent/*_Stundenwerte_Beschreibung_Stationen.txt"
        )

    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset="time", keep="first")  # 'historical' comes first, so it wins
    df = df[(df["time"] >= START) & (df["time"] < END + pd.Timedelta(days=1))].sort_values("time")
    return df.reset_index(drop=True)


def main():
    failed = []
    for folder, code in PRODUCTS.items():
        print(f"\n{folder}:")
        try:
            df = build_product(folder, code)
        except Exception as error:  # noqa: BLE001 - report and continue with the other product
            print(f"  FAILED: {error}")
            failed.append(folder)
            continue

        out_csv = OUT_DIR / f"dwd_{STATION_ID}_{folder}_hourly.csv"
        df.to_csv(out_csv, index=False)

        expected = int((df["time"].max() - df["time"].min()) / pd.Timedelta(hours=1)) + 1
        print(f"  saved {out_csv}")
        print(f"  {len(df)} rows from {df['time'].min()} to {df['time'].max()} (hourly rows expected: {expected})")
        print("  missing values per column:", df.drop(columns=["time", "source"]).isna().sum().to_dict())

    if failed:
        sys.exit(f"\nFailed: {failed}")


if __name__ == "__main__":
    main()
