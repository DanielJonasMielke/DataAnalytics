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
import urllib.request
import zipfile

import pandas as pd
from common import DATA_DIR, END, START, STATION_ID

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly"
OUT_DIR = DATA_DIR / "dwd"

PRODUCTS = {"air_temperature": "TU", "precipitation": "RR"}  # folder on the server -> code in file names


def download_zip(folder, code, period):
    """Download the station's zip file and return its path."""
    listing_url = f"{BASE_URL}/{folder}/{period}/"
    html = urllib.request.urlopen(listing_url).read().decode()
    zip_name = re.search(rf"stundenwerte_{code}_{STATION_ID}_\w+\.zip", html).group(0)  # name ends in _hist or _akt

    zip_path = OUT_DIR / zip_name
    if period == "recent" or not zip_path.exists():  # 'recent' changes daily, 'historical' never
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(listing_url + zip_name, zip_path)
    return zip_path


def read_product(zip_path, source):
    """Read the measurement table from inside the zip file."""
    with zipfile.ZipFile(zip_path) as zf:
        product_file = next(name for name in zf.namelist() if name.startswith("produkt"))  # the data file
        with zf.open(product_file) as f:
            df = pd.read_csv(f, sep=";", skipinitialspace=True, na_values=[-999], encoding="latin-1")  # -999 = missing
    df.columns = df.columns.str.strip()  # remove spaces around column names
    df = df.drop(columns=["eor"])  # 'eor' = end-of-row marker
    df.insert(0, "time", pd.to_datetime(df["MESS_DATUM"].astype(str), format="%Y%m%d%H"))  # 2024040112 -> datetime (UTC)
    df["source"] = source
    return df


for folder, code in PRODUCTS.items():
    print(f"\n{folder}:")
    parts = [read_product(download_zip(folder, code, period), period) for period in ["historical", "recent"]]

    df = pd.concat(parts, ignore_index=True)  # historical rows first, then recent
    df = df.drop_duplicates(subset="time", keep="first")  # overlap: keep the historical row
    df = df[(df["time"] >= START) & (df["time"] < END + pd.Timedelta(days=1))].sort_values("time")  # time window only

    out_csv = OUT_DIR / f"dwd_{STATION_ID}_{folder}_hourly.csv"
    df.to_csv(out_csv, index=False)

    expected = int((df["time"].max() - df["time"].min()) / pd.Timedelta(hours=1)) + 1  # rows if no hour is missing
    print(f"  saved {out_csv}")
    print(f"  {len(df)} rows from {df['time'].min()} to {df['time'].max()} (hourly rows expected: {expected})")
    print("  missing values per column:", df.drop(columns=["time", "source"]).isna().sum().to_dict())
