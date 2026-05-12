# NPS Asset Mix Simulator — JCP 2026

[![GitHub Pages](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-blue?style=flat-square)](https://raginipriti.github.io/nps-simulator)
[![Dashboard](https://img.shields.io/badge/Simulator-Live%20Dashboard-gold?style=flat-square&color=C9980A)](https://raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html)
[![Conference](https://img.shields.io/badge/Conference-JCP%202026-green?style=flat-square)](https://actuariesindia.org/jcpconference/index.html)
[![Track](https://img.shields.io/badge/Track-2%20%7C%20Investment%20Practices-orange?style=flat-square)](https://actuariesindia.org/jcpconference/index.html)

---

## Paper

**Title:** Optimal asset mix for NPS under long secular horizons: a liability-aware approach

**Author:** Ragini  
**Affiliation:** United India Insurance Company Limited  
**Conference:** Joint Conference on Pensions (JCP) 2026 · PFRDA / Institute of Actuaries of India  
**Track:** Track 2 — Investment Practices and Asset Mix for Long-Term Horizons (30–60 Years)  
**Submission deadline:** 28 May 2026

---

## Abstract

The National Pension System (NPS) administers retirement savings across horizons of 30 to 60 years. Despite regulatory provisions for lifecycle-based asset allocation, the current NPS investment framework has not been rigorously validated against stochastic liability projections or actuarial stress scenarios calibrated to Indian capital market conditions.

This paper develops a multi-period Monte Carlo simulation framework integrating: (i) regime-switching GBM equity modelling and Vasicek interest rate dynamics calibrated to BSE Sensex and RBI data; (ii) actuarial liability benchmarks using IAI LIC 2006-08 mortality tables; and (iii) an AI-driven dynamic de-risking overlay using Gradient Boosting regime detection.

Results show that raising the equity cap from 75% to 85% for younger cohorts, combined with a 10–15% InvIT allocation and AI-assisted dynamic de-risking, improves median replacement rates by 12–18% while reducing tail-risk drawdown by 8–14 percentage points — with direct policy implications for PFRDA's NPS investment guidelines.

---

## Live Resources

| Resource | URL |
|----------|-----|
| 🌐 **Architecture & Methodology** | [raginipriti.github.io/nps-simulator](https://raginipriti.github.io/nps-simulator) |
| 📊 **Interactive Live Dashboard** | [raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html](https://raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html) |
| 💻 **Source Code** | [github.com/raginipriti/nps-simulator](https://github.com/raginipriti/nps-simulator) |

---

## Repository Contents

```
nps-simulator/
│
├── index.html                     ← Technical architecture document (9 sections)
│                                    Open at raginipriti.github.io/nps-simulator
│
├── NPS_Simulator_Dashboard.html   ← Standalone interactive dashboard
│                                    Runs in any browser · No installation needed
│                                    Monte Carlo simulation with live parameter controls
│
├── NPS_Simulator_JCP2026.ipynb    ← Jupyter notebook (17 cells)
│                                    Full pipeline: imports → simulation → HTML report
│                                    Run cell-by-cell with Shift+Enter
│
├── nps_simulator.py               ← Python simulation engine
│                                    Generates HTML report + Excel tables + PNG charts
│                                    Usage: python nps_simulator.py
│
├── NPS_DataTables.xlsx            ← 10-sheet Excel data workbook
│                                    All calibrated parameters, glide paths,
│                                    mortality table, annuity factors, results
│
└── README.md                      ← This file
```

---

## Simulation Framework

### Models

| Component | Model | Calibration |
|-----------|-------|-------------|
| Equity returns | Regime-switching GBM | BSE Sensex 2000–2023; μ_bull=13.5%, μ_bear=−8%, σ_bull=18%, σ_bear=38% |
| Interest rates | Vasicek mean-reverting | RBI 10-yr G-Sec 2000–2024; κ=0.18, θ=7.2%, σ_r=1.2% |
| Inflation | Ornstein-Uhlenbeck | RBI CPI 2012–2024; κ=0.20, θ=5.5%, σ=1.5% |
| Corporate bonds | Lognormal | Crisil AA index; μ=8.0%, σ=4.5% |
| InvIT / Alt assets | Lognormal | Infra debt proxy; μ=10.5%, σ=12.0% (+180bps illiquidity premium) |
| Salary growth | Stochastic nominal | Real growth 2.0% + OU inflation path |

### Liability Benchmark

Liability defined as annuity present value: **L_T = W_T × R_target × ä(x, i_T)**

- Mortality: **IAI LIC 2006-08 Ultimate tables** with 1.5%/yr generational improvement to 2026
- Target replacement rate: **50% of final salary**
- Discount rate: Vasicek short rate prevailing at retirement

### Replacement Rate

**RR = Terminal Corpus ÷ Liability PV**

| RR | Interpretation |
|----|---------------|
| ≥ 1.5x | Strong surplus — full annuity funded with margin |
| 1.0–1.5x | Adequate — target annuity funded |
| < 1.0x | Deficit — cannot fully fund target annuity |

### AI De-Risking Layer

- **Model:** Gradient Boosting Classifier (scikit-learn)
- **Features:** 12-month equity return, volatility, yield curve slope, credit spread, P/E ratio
- **Trigger:** Equity reduced by −10pp when stress probability > 0.65
- **Restoration:** Equity restored to base glide path when stress probability < 0.35
- **Impact:** Reduces maximum funding ratio drawdown by 8–14 percentage points

---

## Key Results

| Entry Age | Strategy | Median RR | P5 RR | CVaR 95% | Max Drawdown | vs Current |
|-----------|----------|-----------|-------|----------|--------------|------------|
| 25 | Current NPS (75% E) | 2.41x | 0.92x | 0.71x | 23.1% | — |
| 25 | Proposed (85% E + InvIT) | 2.78x | 1.02x | 0.70x | 19.4% | **+15.4%** |
| 25 | AI Dynamic | 2.91x | 1.08x | 0.68x | 16.2% | **+20.7%** |
| 35 | Current NPS (75% E) | 1.89x | 0.78x | 0.58x | 20.3% | — |
| 35 | Proposed (85% E + InvIT) | 2.14x | 0.85x | 0.57x | 17.8% | **+13.2%** |
| 35 | AI Dynamic | 2.23x | 0.89x | 0.55x | 15.1% | **+17.9%** |
| 45 | Current NPS (50% E) | 1.42x | 0.68x | 0.40x | 13.7% | — |
| 45 | Proposed (55% E + InvIT) | 1.53x | 0.72x | 0.41x | 12.9% | **+7.7%** |
| 45 | AI Dynamic | 1.58x | 0.74x | 0.40x | 11.4% | **+11.3%** |

*10,000 Monte Carlo paths · IAI LIC 2006-08 mortality · Base case capital market assumptions*

---

## Policy Recommendations

Three specific recommendations for PFRDA emerging from this research:

1. **Raise equity allocation cap** from 75% to 85% for NPS subscribers aged 25–34 under Active Choice and LC75 Auto Choice funds. Over a 35-year horizon, the incremental equity risk premium outweighs additional volatility risk by approximately 2.3:1 on a risk-adjusted replacement rate basis.

2. **Expand alternative asset allocation** (Asset Class A — InvITs, REITs) from 5% to 15% of the NPS portfolio, with a mandatory minimum of 5% for Auto Choice subscribers below age 50. The illiquidity premium of ~150–200bps compounds materially over long horizons.

3. **Commission an AI-assisted dynamic de-risking pilot** within the LC75 and LC50 Auto Choice funds, specifying a standardised regime detection methodology, symmetric trigger mechanism, and governance framework for model validation.

---

## Running the Simulator

### Option 1 — Browser (no installation)

Open directly:
```
https://raginipriti.github.io/nps-simulator/NPS_Simulator_Dashboard.html
```
Adjust any slider — the simulation re-runs automatically.

### Option 2 — Python script

```bash
# Install dependencies
pip install numpy pandas matplotlib scipy scikit-learn openpyxl

# Run simulation (generates nps_report.html + NPS_DataTables.xlsx)
python nps_simulator.py
```

### Option 3 — Jupyter Notebook

```bash
# Install dependencies
pip install numpy pandas matplotlib scipy scikit-learn openpyxl ipywidgets

# Launch Jupyter
jupyter notebook NPS_Simulator_JCP2026.ipynb
```

Run cells top-to-bottom with `Shift+Enter`.  
Set `N_PATHS = 500` in Cell 2 for a quick test (~30 seconds).  
Set `N_PATHS = 10_000` for full paper results (~8 minutes).

### Quick test (30 seconds)

```python
# Paste into any Python environment to verify the core works
import numpy as np
np.random.seed(42)
n = 200
corpus = 0; salary = 1.0; rate = 0.072
for t in range(300):  # 25yr horizon
    eq_ret = np.random.normal(0.135/12, 0.18/12**0.5)
    corpus = corpus * (1 + 0.85*eq_ret + 0.10*0.072/12) + salary*0.24/12
    salary *= (1 + (0.02 + 0.055)/12)
apv = sum((1/1.072)**t * max(0, 1 - t*0.015/100) for t in range(30))
rr = corpus / (salary * 0.50 * apv)
print(f"Quick-check Replacement Rate: {rr:.2f}x  (expect ~2.0–3.0x)")
```

---

## Data Sources

| Data | Source | Period |
|------|--------|--------|
| BSE Sensex total return | Bombay Stock Exchange | Jan 2000 – Dec 2023 |
| RBI 10-yr benchmark G-Sec yield | Reserve Bank of India | Jan 2000 – Dec 2024 |
| Crisil AA corporate bond spread | Crisil | Jan 2005 – Dec 2024 |
| CPI headline inflation | RBI / MOSPI | Jan 2012 – Dec 2024 |
| InvIT return proxy | BSE InvIT index / Infra debt | 2019 – 2024 |
| Mortality table | IAI LIC 2006-08 Ultimate | Base year 2008 |
| Improvement scale | IAI generational projection | 1.5%/yr from 2008 |
| Salary growth | GOI Pay Commission (6th, 7th) | 2006–2016 |
| NPS AUM / subscriber data | PFRDA Annual Report 2024 | 2024 |

---

## Technical Specifications

| Component | Specification |
|-----------|--------------|
| Language | Python 3.10+ |
| Core libraries | NumPy · Pandas · Matplotlib · SciPy · scikit-learn |
| Notebook | Jupyter 6+ / JupyterLab 3+ |
| Dashboard | HTML5 · Chart.js 4.4.1 (CDN) · Vanilla JS |
| Excel output | openpyxl |
| Monte Carlo paths | 200–10,000 (configurable) |
| Time step | Monthly (dt = 1/12) |
| Cohorts | Entry ages 25, 35, 45 |
| Strategies | Current NPS · Proposed · AI Dynamic |
| Scenarios | 6 macroeconomic regimes |

---

## File Sizes

| File | Size | Notes |
|------|------|-------|
| `nps_simulator.py` | ~54 KB | Full Python engine |
| `NPS_Simulator_JCP2026.ipynb` | ~120 KB | With inline outputs |
| `NPS_Simulator_Dashboard.html` | ~38 KB | Self-contained; no backend |
| `index.html` | ~55 KB | Architecture document |
| `NPS_DataTables.xlsx` | ~180 KB | 10 formatted sheets |

---

## Citation

If you use this simulator or reference this work, please cite:

```
Ragini (2026). Optimal asset mix for NPS under long secular horizons:
a liability-aware approach. Joint Conference on Pensions 2026,
PFRDA / Institute of Actuaries of India, Track 2.
Available at: https://raginipriti.github.io/nps-simulator
```

**BibTeX:**
```bibtex
@inproceedings{ragini2026nps,
  author    = {Ragini},
  title     = {Optimal asset mix for {NPS} under long secular horizons:
               a liability-aware approach},
  booktitle = {Joint Conference on Pensions 2026},
  year      = {2026},
  publisher = {Pension Fund Regulatory and Development Authority /
               Institute of Actuaries of India},
  note      = {Track 2: Investment Practices and Asset Mix for
               Long-Term Horizons},
  url       = {https://raginipriti.github.io/nps-simulator}
}
```

---

## Disclaimer

This simulator and all associated documentation are developed for academic research purposes in connection with the Joint Conference on Pensions (JCP) 2026 organised by PFRDA and the Institute of Actuaries of India. Results are illustrative and based on calibrated historical data; they do not constitute investment advice or regulatory guidance. All views expressed are those of the author in a personal capacity and do not represent the views of United India Insurance Company Limited or any regulatory authority.

---

## Author

**Ragini**  
Actuarial Department · United India Insurance Company Limited  
Member, Institute of Actuaries of India (IAI)  
Student Member, Institute and Faculty of Actuaries (IFoA)

*For queries related to this paper, contact via the IAI JCP 2026 conference portal.*

---

*© 2026 · JCP 2026 Conference Submission · PFRDA / IAI · Track 2*  
*Repository: github.com/raginipriti/nps-simulator*
