# NPS Asset Mix Simulator — JCP 2026

[![GitHub Pages](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-blue?style=flat-square)](https://raginipriti.github.io/nps-simulator)
[![Dashboard](https://img.shields.io/badge/Simulator-Live%20Dashboard-gold?style=flat-square&color=C9980A)](https://raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html)
[![Conference](https://img.shields.io/badge/Conference-JCP%202026-green?style=flat-square)](https://actuariesindia.org/jcpconference/index.html)
[![Track](https://img.shields.io/badge/Track-2%20%7C%20Investment%20Practices-orange?style=flat-square)](https://actuariesindia.org/jcpconference/index.html)

---

## Paper

**Title:** Optimal asset mix for NPS under long secular horizons: a liability-aware approach  
**Author:** Priti Ragini  
**Affiliation:** United India Insurance Company Limited  
**Conference:** Joint Conference on Pensions (JCP) 2026 · PFRDA / Institute of Actuaries of India  
**Track:** Track 2 — Investment Practices and Asset Mix for Long-Term Horizons (30–60 Years)

---

## Abstract

The National Pension System (NPS) administers retirement savings across horizons of 30 to 60 years. Despite regulatory provisions for lifecycle-based asset allocation, the current NPS investment framework has not been rigorously validated against stochastic liability projections or actuarial stress scenarios calibrated to Indian capital market conditions.

This repository provides a reproducible simulator supporting the paper. It includes a browser dashboard, a technical architecture document, a runnable Python engine, and a Jupyter notebook workflow that generates charts, Excel data tables, and an HTML report.

---

## Live resources

| Resource | URL |
|---|---|
| Architecture & methodology | <https://raginipriti.github.io/nps-simulator> |
| Interactive dashboard | <https://raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html> |
| Source code | <https://github.com/raginipriti/nps-simulator> |

---

## Repository contents

```text
nps-simulator/
│
├── index.html                         # Technical architecture document
├── NPS_Simulator_Dashboard.html       # Standalone browser dashboard
├── NPS_Simulator_JCP2026.ipynb        # Runnable Jupyter notebook
├── nps_simulator.py                   # Python simulation engine
├── requirements.txt                   # Python package requirements
├── NPS_DataTables.xlsx                # Generated workbook, if uploaded after notebook run
├── nps_report.html                    # Generated HTML report, if uploaded after notebook run
├── fig_*.png                          # Generated simulation charts, if uploaded after notebook run
└── README.md                          # This file
```

---

## Reproducibility note

The Python script and notebook are designed to be runnable in a normal Anaconda/Jupyter environment. The dynamic de-risking layer included in the runnable code is a transparent proxy stress-scoring rule based on observable market signals. It is suitable for reproducible demonstration and reviewer verification. A production Gradient Boosting or LSTM model can be substituted later if the historical feature dataset and fitted model objects are added to the repository.

---

## Simulation framework

| Component | Model / approach |
|---|---|
| Equity returns | Regime-switching GBM |
| Interest rates | Vasicek mean-reverting short-rate model |
| Inflation | Ornstein-Uhlenbeck process |
| Corporate bonds | Lognormal return approximation |
| InvIT / alternative assets | Infrastructure-debt proxy |
| Salary | Real salary growth plus stochastic inflation |
| Liability benchmark | Annuity present value based on target replacement income |
| Strategies | Current NPS, Proposed glide path, AI/proxy dynamic de-risking |

---

## Running the simulator

### Option 1 — Browser dashboard

Open:

```text
https://raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html
```

### Option 2 — Jupyter notebook

```bash
pip install -r requirements.txt
jupyter notebook NPS_Simulator_JCP2026.ipynb
```

Run the notebook cells from top to bottom.

For a quick check, use:

```python
N_PATHS = 500
```

For final paper-level output, use:

```python
N_PATHS = 10000
```

### Option 3 — Python script

```bash
pip install -r requirements.txt
python nps_simulator.py --n-paths 500 --seed 42 --outdir outputs
```

---

## Generated outputs

After running the notebook/script, upload these generated files to the repository if required:

```text
NPS_DataTables.xlsx
nps_report.html
fig_fan_age25.png
fig_fan_age35.png
fig_fan_age45.png
fig_ai_overlay.png
fig_glide_paths.png
fig_rr_distributions.png
fig_scenarios.png
```

---

## Disclaimer

This simulator and all associated documentation are developed for academic research purposes in connection with the Joint Conference on Pensions 2026. Results are illustrative and based on model assumptions and calibrated historical data. They do not constitute investment advice, actuarial advice, or regulatory guidance.

All views expressed are those of the author in a personal capacity and do not represent the views of United India Insurance Company Limited or any regulatory authority.
