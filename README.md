# Neural vs. physics weather forecasts: AIFS ENS vs. IFS ENS at DWD stations

Semester project for **Data Analytics** (M-Inf, WiSe 2026/27, Prof. Dr. Martin Schultz, HAW Hamburg).

**Team:** Daniel Mielke, Joans Westphal

## Research question (draft)

> How does the forecast error of ECMWF's **neural-network ensemble (AIFS ENS)** compare with that of its
> **physics-based ensemble (IFS ENS)** at DWD weather stations in Northern Germany, and how does the difference
> change with lead time (+6 h to +15 days)?

Both models start from the same initial conditions, so differences in the results come from the forecasting
method (neural network vs. physics equations). Possible follow-up questions:

1. Does the difference depend on season, time of day or weather situation (calm vs. stormy)?
2. Is each ensemble honest about its uncertainty (does the measured value fall inside the predicted range as often as it should)?
3. Does the neural model smooth out extremes (strong wind, very high or low temperatures) more than the physics model?

## Data sources

| #   | Source                       | What it is                                                                                                                                         | Link                                                                                                           |
| --- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 1   | **AIFS ENS** (ECMWF)         | Machine-learning ensemble forecast: 51 members, 0.25° grid, 15 days, a value every 6 h. Archive from July 2025.                                    | [dynamical.org catalog](https://dynamical.org/catalog/ecmwf-aifs-ens-forecast)                                 |
| 2   | **IFS ENS** (ECMWF)          | Physics-based ensemble forecast: 51 members, 0.25° grid, 15 days, a value every 3 h (to +144 h) and every 6 h after that. Archive from April 2024. | [dynamical.org catalog](https://dynamical.org/catalog/ecmwf-ifs-ens-forecast-15-day-0-25-degree)               |
| 3   | **DWD station observations** | Measured values at German weather stations (ground truth), hourly and 10-minute data.                                                              | [DWD Open Data (hourly)](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/) |

Background: [ECMWF AIFS data page](https://www.ecmwf.int/en/forecasts/datasets/aifs-machine-learning-data),
[ECMWF: AIFS uses the same initial conditions as the IFS](https://www.ecmwf.int/node/29308).

## Process (CRISP-DM) and session plan

| Date       | Practical session                       | CRISP-DM phase                             |
| ---------- | --------------------------------------- | ------------------------------------------ |
| 30.10.2026 | Use case + data acquisition             | Business understanding, data understanding |
| 20.11.2026 | Data preparation + explorative analysis | Data understanding, data preparation       |
| 18.12.2026 | Modeling & evaluation                   | Modeling, evaluation                       |
| 22.01.2027 | Presentation & discussion of results    | Deployment / communication                 |

## Repository structure

```
├── README.md          project overview (this file)
├── pyproject.toml     project name and Python dependencies
├── uv.lock            exact package versions, so everyone gets the same environment
├── data/              downloaded data (not committed to git, re-created by the notebooks)
├── notebooks/
│   └── 01_first_look.ipynb   loads one forecast from each model + the DWD measurements and plots them
└── docs/              slides and notes for the practical sessions
```

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync               # creates .venv and installs the exact versions from uv.lock
uv run jupyter lab    # then open notebooks/01_first_look.ipynb
```

In VS Code, you can instead open the notebook directly and select the `.venv` Python environment as the kernel.

## Data attribution

- ECMWF AIFS ENS / IFS ENS forecast data processed by dynamical.org from ECMWF Open Data (CC BY 4.0).
- Station observations: Deutscher Wetterdienst (DWD), Climate Data Center.
