"""Shared settings and helpers for the download scripts in process_data/.

Every download script takes the same location and time window from here, so the
five data sources always describe the same place and the same period.
"""

import argparse
import time
from pathlib import Path

import pandas as pd

# --- Settings used by all download scripts -------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# The single location: DWD station Hamburg-Fuhlsbüttel (same as in notebooks/01_first_look.ipynb)
STATION_ID = "01975"
STATION_NAME = "Hamburg-Fuhlsbüttel"
STATION_LAT, STATION_LON = 53.6332, 9.9881  # degrees north / east

# Time window: first day of AIFS Single in the dynamical.org archive until today (UTC)
START = pd.Timestamp("2024-04-01T00:00")
END = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()


# --- Small helpers -------------------------------------------------------------------------
def parse_limit(description):
    """Command line: optional --limit N to try a script on only N forecasts first."""
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="only download the first N forecasts that are not yet in the CSV (quick test run)",
    )
    return parser.parse_args()


def with_retries(function, attempts=3, wait_seconds=10):
    """Call function(); if it raises, wait and try again (network hiccups)."""
    for attempt in range(1, attempts + 1):
        try:
            return function()
        except Exception as error:  # noqa: BLE001 - we re-raise after the last attempt
            if attempt == attempts:
                raise
            print(f"  attempt {attempt} failed ({error!r}); retrying in {wait_seconds} s")
            time.sleep(wait_seconds)


def done_init_times(csv_path):
    """Forecast start times that are already stored in the CSV (so a re-run continues where it stopped)."""
    if not csv_path.exists():
        return set()
    column = pd.read_csv(csv_path, usecols=["init_time"], parse_dates=["init_time"])["init_time"]
    return set(pd.DatetimeIndex(column.unique()))


def append_csv(df, csv_path):
    """Append rows to the CSV; the header is written only once and the column order stays fixed."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_path.exists():
        df = df.reindex(columns=pd.read_csv(csv_path, nrows=0).columns)
    df.to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False)


def print_csv_summary(csv_path):
    df = pd.read_csv(csv_path)
    size_mb = csv_path.stat().st_size / 1e6
    print(f"\nDone: {csv_path}  ({len(df)} rows, {size_mb:.1f} MB)")
    if "init_time" in df.columns:
        print(f"Forecasts: {df['init_time'].nunique()}  from {df['init_time'].min()} to {df['init_time'].max()}")


# --- Shared by the three dynamical.org sources (AIFS Single, IFS control, GFS) -------------
def pick_variables(ds):
    """Choose 2 m temperature and precipitation from a dynamical.org dataset."""
    names = list(ds.data_vars)
    if "temperature_2m" not in names:
        raise SystemExit(f"No 'temperature_2m' in this dataset. Variables: {names}")

    if "precipitation_surface" in names:
        precipitation = "precipitation_surface"
    else:
        candidates = [n for n in names if "precipitation" in n and "categorical" not in n and "percent" not in n]
        precipitation = candidates[0] if candidates else None

    if precipitation is None:
        print(f"WARNING: no precipitation variable found. Only temperature is downloaded. Variables: {names}")
        return ["temperature_2m"]
    return ["temperature_2m", precipitation]


def download_dynamical_point(dataset_name, out_csv, member=None, limit=None, batch_size=20):
    """Download temperature + precipitation at the station for all 00 UTC forecasts in the time window.

    The dataset is opened lazily from the cloud; only the grid point nearest to the station is read.
    Values are stored as they come from the archive (temperature in degree Celsius, precipitation as a
    rate in kg m-2 s-1 = mm/s averaged since the previous step). All available lead times are kept.
    The CSV is extended batch by batch, so an interrupted run can simply be started again.
    """
    import dynamical_catalog  # imported here so that common.py also works without it (e.g. for the DWD script)

    print(f"Opening dataset '{dataset_name}' ...")
    ds = dynamical_catalog.open(dataset_name, chunks=None)

    all_inits = pd.DatetimeIndex(ds["init_time"].values)
    inits = all_inits[(all_inits.hour == 0) & (all_inits >= START) & (all_inits <= END)]
    done = done_init_times(out_csv)
    todo = [t for t in inits if t not in done]
    if limit is not None:
        todo = todo[:limit]
    print(f"{len(inits)} forecasts at 00 UTC in the window, {len(done)} already downloaded, {len(todo)} to do.")
    if not todo:
        print("Nothing to do.")
        return

    variables = pick_variables(ds)
    print("Variables:", {v: ds[v].attrs.get("units", "?") for v in variables})

    point = ds[variables]
    if member is not None:
        point = point.sel(ensemble_member=member)
    point = point.sel(latitude=STATION_LAT, longitude=STATION_LON, method="nearest")
    print(
        f"Nearest grid point: {float(point.latitude):.2f}°N, {float(point.longitude):.2f}°E "
        f"(station: {STATION_LAT}°N, {STATION_LON}°E)"
    )

    started = time.time()
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        loaded = with_retries(lambda: point.sel(init_time=batch).load())  # the actual download happens here
        df = loaded.to_dataframe().reset_index()

        df["lead_time_h"] = df.pop("lead_time") / pd.Timedelta(hours=1)
        df = df.drop(columns=["spatial_ref", "expected_forecast_length", "ingested_forecast_length"], errors="ignore")
        first = ["init_time", "lead_time_h", "valid_time"]
        df = df[first + [c for c in df.columns if c not in first]]

        append_csv(df, out_csv)
        print(
            f"  forecasts {i + len(batch)}/{len(todo)} done "
            f"(up to {batch[-1]:%Y-%m-%d}), {time.time() - started:.0f} s elapsed"
        )

    print_csv_summary(out_csv)
