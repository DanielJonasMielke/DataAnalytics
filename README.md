# AI vs. physics weather models, compared with DWD measurements

Semester project for **Data Analytics** (M-Inf, WiSe 2026/27, Prof. Dr. Martin Schultz, HAW Hamburg).

**Team:** Daniel Mielke, Joans Westphal

## Research question

How well do AI weather models predict the weather in Northern Germany compared with classical physics-based models,
and how does their error change with lead time (+6 h to +240 h)? We compare 2 m temperature and precipitation at the
DWD station Hamburg-Fuhlsbüttel (01975), from 01.04.2024 until today, using the forecasts started at 00 UTC.

## Data sources

| #   | Source                                        | Type    | What it is                                                                                                                                |
| --- | --------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **AIFS Single** (ECMWF)                       | AI      | Single forecast, 15 days, every 6 h. [dynamical.org](https://dynamical.org/catalog/ecmwf-aifs-single-forecast)                            |
| 2   | **GraphCast** (Google, started from IFS data) | AI      | Single forecast, 10 days, every 6 h. [NOAA/CIRA AIWP archive](https://registry.opendata.aws/aiwp/)                                        |
| 3   | **IFS control run** (ECMWF)                   | Physics | Unperturbed member of the IFS ensemble, 15 days. [dynamical.org](https://dynamical.org/catalog/ecmwf-ifs-ens-forecast-15-day-0-25-degree) |
| 4   | **GFS** (NOAA)                                | Physics | Single forecast, 16 days. [dynamical.org](https://dynamical.org/catalog/noaa-gfs-forecast)                                                |
| 5   | **DWD station measurements**                  | Truth   | Hourly observations. [DWD Open Data](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/)                |

## Course schedule

| Date       | Practical session                       |
| ---------- | --------------------------------------- |
| 30.10.2026 | Use case + data acquisition             |
| 20.11.2026 | Data preparation + explorative analysis |
| 18.12.2026 | Modeling & evaluation                   |
| 22.01.2027 | Presentation & discussion of results    |

## What the repository can do right now

Download temperature and precipitation at the station from all 5 sources and save them as CSV files.
Nothing is cleaned or unified yet.

```
├── process_data/
│   ├── common.py                      shared settings (station, time window) and download code
│   ├── 01_download_dwd_data.py        DWD measurements   -> data/dwd/
│   ├── 02_download_aifs_data.py       AIFS Single        -> data/aifs_single/
│   ├── 03_download_graphcast_data.py  GraphCast          -> data/graphcast/
│   ├── 04_download_ifs_data.py        IFS control run    -> data/ifs/
│   └── 05_download_gfs_data.py        GFS                -> data/gfs/
├── data/                              downloaded CSV files (not in git)
├── pyproject.toml                     Python dependencies
└── uv.lock                            exact package versions
```

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync    # creates .venv and installs the exact versions from uv.lock
```

## Downloading the data

```bash
uv run ./process_data/01_download_dwd_data.py
uv run ./process_data/02_download_aifs_data.py
uv run ./process_data/03_download_graphcast_data.py    # --workers 4 downloads in parallel
uv run ./process_data/04_download_ifs_data.py
uv run ./process_data/05_download_gfs_data.py
```

- Add `--limit 3` to a forecast script (02 to 05) to try it on 3 forecasts first. The DWD script (01) has no `--limit`: it always saves the full time window.
- An interrupted script continues where it stopped; it skips forecasts that are already in its CSV.
- Station and time window are set in `process_data/common.py`.

## Data attribution

- AIFS Single, IFS and GFS forecast data processed by dynamical.org from ECMWF Open Data (CC BY 4.0) and NOAA.
- GraphCast forecasts: NOAA/CIRA AI Weather Prediction archive (AIWP).
- Station observations: Deutscher Wetterdienst (DWD), Climate Data Center (CC BY 4.0).
