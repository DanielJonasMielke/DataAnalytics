"""Download the IFS control run (ECMWF's physics model, single forecast) at the station.

Source:   dynamical.org catalog 'ecmwf-ifs-ens-forecast-15-day-0-25-degree' (ECMWF Open Data, CC BY 4.0)
          This is the IFS *ensemble*; we keep only member 0, the unperturbed control run, which is a
          single forecast like the other models (no ensemble mean).
Content:  2 m temperature + precipitation, every forecast started at 00 UTC from 2024-04-01 until today,
          all lead times (+0 h to +360 h; 3-hourly up to +144 h, 6-hourly after that),
          grid point nearest to the station
Output:   data/ifs/ifs_control_hamburg_t2m_precip.csv

Run:      uv run ./process_data/04_download_ifs_data.py            (everything)
          uv run ./process_data/04_download_ifs_data.py --limit 5  (quick test with 5 forecasts)
"""

from common import DATA_DIR, download_dynamical_point, parse_limit

args = parse_limit(__doc__)

download_dynamical_point(
    dataset_name="ecmwf-ifs-ens-forecast-15-day-0-25-degree",
    out_csv=DATA_DIR / "ifs" / "ifs_control_hamburg_t2m_precip.csv",
    member=0,  # control run
    limit=args.limit,
)
