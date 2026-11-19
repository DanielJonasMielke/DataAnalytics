"""Shared settings and helpers for the download scripts in process_data/."""

import argparse
import time
from pathlib import Path

import dynamical_catalog
import pandas as pd

# --- Settings used by all download scripts ---
REPO_ROOT = Path(__file__).resolve().parent.parent  # the main project folder
DATA_DIR = REPO_ROOT / "data"

# Our weather station: Hamburg-Fuhlsbüttel
STATION_ID = "01975"
STATION_LAT, STATION_LON = 53.6332, 9.9881  # position in degrees north and east

# Time range: from the first AIFS forecast until today
START = pd.Timestamp("2024-04-01")
END = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()  # today at midnight (UTC)

VARIABLES = ["temperature_2m", "precipitation_surface"]  # temperature and rain, as dynamical.org names them


def parse_limit(description):
    """Read the optional --limit N setting for quick test runs."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--limit", type=int, default=None, help="only download the first N missing forecasts")
    return parser.parse_args()


def done_init_times(csv_path):
    """Return the forecast days already saved, so we can skip them."""
    if not csv_path.exists():
        return set()
    column = pd.read_csv(csv_path, usecols=["init_time"], parse_dates=["init_time"])["init_time"]
    return set(column)


def append_csv(df, csv_path):
    """Add new rows to the CSV file, header only for new files."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False)


def print_csv_summary(csv_path):
    df = pd.read_csv(csv_path)
    print(f"\nDone: {csv_path} ({len(df)} rows)")
    print(f"Forecasts: {df['init_time'].nunique()} from {df['init_time'].min()} to {df['init_time'].max()}")


def download_dynamical_point(dataset_name, out_csv, member=None, limit=None, batch_size=20):
    """Download temperature and rain at our station from dynamical.org.

    Values are saved unchanged: temperature in °C, rain as a rate in mm per second.
    The CSV grows step by step, so a stopped run can simply be restarted.
    """
    ds = dynamical_catalog.open(dataset_name, chunks=None)  # connect to the dataset, nothing downloaded yet

    # Forecasts we still need: started at midnight, inside our time range
    all_inits = pd.DatetimeIndex(ds["init_time"].values)
    inits = all_inits[(all_inits.hour == 0) & (all_inits >= START) & (all_inits <= END)]
    done = done_init_times(out_csv)
    todo = [t for t in inits if t not in done][:limit]  # without --limit we take all of them
    print(f"{len(inits)} forecasts in the window, {len(done)} already downloaded, {len(todo)} to do.")
    if not todo:
        return

    point = ds[VARIABLES]
    if member is not None:
        point = point.sel(ensemble_member=member)  # IFS only: member 0 is the normal, undisturbed run
    point = point.sel(latitude=STATION_LAT, longitude=STATION_LON, method="nearest")  # grid point closest to the station
    print(f"Grid point used: {float(point.latitude):.2f}°N, {float(point.longitude):.2f}°E")

    started = time.time()
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        loaded = point.sel(init_time=batch).load()  # the actual download happens here
        df = loaded.to_dataframe().reset_index()  # turn into a table: one row per forecast hour

        df["lead_time_h"] = df.pop("lead_time") / pd.Timedelta(hours=1)  # forecast hour as a plain number
        df = df.drop(columns=["spatial_ref", "expected_forecast_length", "ingested_forecast_length"], errors="ignore")  # remove columns we don't need
        first = ["init_time", "lead_time_h", "valid_time"]
        df = df[first + [c for c in df.columns if c not in first]]  # put the time columns first

        append_csv(df, out_csv)
        print(f"  {i + len(batch)}/{len(todo)} forecasts done, {time.time() - started:.0f} s elapsed")

    print_csv_summary(out_csv)
