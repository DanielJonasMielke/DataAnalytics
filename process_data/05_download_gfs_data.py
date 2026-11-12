"""Download GFS (NOAA's physics model, single forecast) at the station.

Source:   dynamical.org catalog 'noaa-gfs-forecast' (NOAA Open Data Dissemination, CC BY 4.0 via dynamical.org)
Content:  2 m temperature + precipitation, every forecast started at 00 UTC from 2024-04-01 until today,
          all lead times (+0 h to +384 h; hourly up to +120 h, 3-hourly after that),
          grid point nearest to the station
Output:   data/gfs/gfs_hamburg_t2m_precip.csv

Run:      uv run ./process_data/05_download_gfs_data.py            (everything)
          uv run ./process_data/05_download_gfs_data.py --limit 5  (quick test with 5 forecasts)
"""

from common import DATA_DIR, download_dynamical_point, parse_limit

args = parse_limit(__doc__)

download_dynamical_point(
    dataset_name="noaa-gfs-forecast",
    out_csv=DATA_DIR / "gfs" / "gfs_hamburg_t2m_precip.csv",
    limit=args.limit,
)
