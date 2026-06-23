"""
nps_simulator.py
================

Runnable National Pension System (NPS) Monte Carlo simulator for the JCP 2026
asset-mix paper: "Optimal asset mix for NPS under long secular horizons".

This is an honest, self-contained Python reconstruction prepared from:
1. the public GitHub README / dashboard / technical architecture text,
2. the uploaded paper module, and
3. the uploaded Excel formula walkthrough.

Important honesty note
----------------------
The public GitHub repository visible during preparation contained the README,
index.html and NPS_Simulator_Dashboard.html. It did not expose the original
nps_simulator.py, Jupyter notebook, or NPS_DataTables.xlsx as downloadable files.
Accordingly, this file does not pretend to be the missing original source file.
It is a clean, runnable research simulator based on the methodology and formulas
available in the modules.

The AI layer here is a transparent proxy de-risking rule using observable market
features. It is NOT a trained production Gradient Boosting / LSTM model because
no actual training data or fitted model object was available in the supplied
modules. You can replace `proxy_stress_probability()` with a fitted scikit-learn
classifier later if you supply the historical feature data.

Quick Jupyter usage
-------------------
    from nps_simulator import NPSConfig, run_all, simulate_strategy, plot_strategy_summary, plot_fan_chart

    cfg = NPSConfig(n_paths=500, seed=42)
    summary = run_all(cfg)
    summary

    result = simulate_strategy(cfg.with_changes(entry_age=25), strategy="ai")
    fig = plot_fan_chart(result)

Command line usage
------------------
    python nps_simulator.py --n-paths 500 --seed 42 --outdir outputs

Dependencies
------------
Required: numpy, pandas, matplotlib
Optional: openpyxl or xlsxwriter for Excel export through pandas.ExcelWriter

All monetary values are in rupees unless you set `initial_salary=1.0` for a unit
salary model. Results are illustrative, stochastic and not investment advice.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NPSConfig:
    """Base-case assumptions used by the simulator.

    Parameters are annual unless explicitly described as monthly.
    The defaults follow the supplied paper/dashboard as closely as practical.
    """

    # Run control
    n_paths: int = 1_000
    seed: int = 42
    entry_age: int = 25
    retirement_age: int = 60
    time_step: float = 1.0 / 12.0  # monthly

    # Salary, contribution and liability
    initial_salary: float = 1_000_000.0
    initial_corpus: float = 0.0
    contribution_rate: float = 0.24  # 10% subscriber + 14% employer
    target_replacement_rate: float = 0.50
    real_salary_growth: float = 0.02
    salary_sigma: float = 0.00  # left at 0 because no stable calibration was supplied

    # Equity: two-regime GBM
    equity_mu_bull: float = 0.135
    equity_sigma_bull: float = 0.18
    equity_mu_bear: float = -0.08
    equity_sigma_bear: float = 0.38
    p_bull_to_bear_monthly: float = 0.06
    p_bear_to_bull_monthly: float = 0.25

    # Vasicek interest-rate model and G-Sec total return
    vasicek_kappa: float = 0.18
    vasicek_theta: float = 0.072
    vasicek_sigma: float = 0.012
    r0: float = 0.072
    min_rate: float = 0.003
    gsec_duration: float = 8.0
    rho_equity_rate: float = -0.18

    # Inflation: Ornstein-Uhlenbeck
    inflation_kappa: float = 0.20
    inflation_theta: float = 0.055
    inflation_sigma: float = 0.015
    inflation0: float = 0.055

    # Other assets
    corp_mu: float = 0.080
    corp_sigma: float = 0.045
    alt_mu: float = 0.105
    alt_sigma: float = 0.120

    # Mortality / annuity benchmark.
    # Defaults mirror the uploaded Excel module because it reproduces the q_x
    # pattern on the manuscript table better than the text-only dashboard proxy.
    gompertz_A: float = 0.0005
    gompertz_B: float = 0.0001122
    gompertz_c: float = 1.0703
    max_annuity_age: int = 100

    # AI proxy de-risking thresholds
    ai_high_threshold: float = 0.65
    ai_low_threshold: float = 0.35
    ai_equity_adjustment: float = -0.10
    ai_restore_step: float = 0.02  # gradual monthly restoration once stress recedes

    # Fan chart / output
    fan_points: int = 9  # start + 7 interim points + retirement

    def with_changes(self, **kwargs) -> "NPSConfig":
        """Jupyter-friendly method to create a modified copy.

        Example:
            cfg2 = cfg.with_changes(n_paths=10_000, entry_age=35)
        """

        return replace(self, **kwargs)


STRATEGY_LABELS: Mapping[str, str] = {
    "current": "Current NPS",
    "proposed": "Proposed Glide Path",
    "ai": "AI Dynamic Glide Path",
}

SCENARIOS: Mapping[str, Mapping[str, float | str]] = {
    "base": {
        "label": "Base Case",
        "equity_mu_bull": 0.135,
        "vasicek_theta": 0.072,
        "inflation_theta": 0.055,
    },
    "high_inflation": {
        "label": "High Inflation (+200bps CPI)",
        "equity_mu_bull": 0.110,
        "vasicek_theta": 0.085,
        "inflation_theta": 0.075,
    },
    "rising_rates": {
        "label": "Rising Rates (+150bps)",
        "equity_mu_bull": 0.100,
        "vasicek_theta": 0.090,
        "inflation_theta": 0.060,
    },
    "market_stress": {
        "label": "Market Stress",
        "equity_mu_bull": 0.080,
        "equity_mu_bear": -0.320,
        "p_bull_to_bear_monthly": 0.10,
        "vasicek_theta": 0.080,
        "inflation_theta": 0.055,
    },
    "low_growth": {
        "label": "Prolonged Low Growth",
        "equity_mu_bull": 0.070,
        "vasicek_theta": 0.055,
        "inflation_theta": 0.040,
    },
    "bull_case": {
        "label": "Bull Case",
        "equity_mu_bull": 0.170,
        "vasicek_theta": 0.075,
        "inflation_theta": 0.050,
    },
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _safe_percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q))


def _as_percent(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def strategy_weights(strategy: str, age: int) -> Dict[str, float]:
    """Return age-based weights for E, C, G and Alt.

    The proposed glide path follows the uploaded manuscript table:
    25-34: 85/5/0/10, 35-44: 70/5/15/10, 45-49: 55/5/25/15,
    50-54: 35/5/40/20, 55-60: 15/5/60/20.

    Current NPS is approximated from the public dashboard: 75% equity to age 35,
    linear de-risking to 15% by age 55, 10% corporate and 5% alternatives.
    """

    if strategy not in STRATEGY_LABELS:
        raise ValueError(f"Unknown strategy '{strategy}'. Use one of {list(STRATEGY_LABELS)}")

    if strategy == "current":
        if age <= 35:
            equity = 0.75
        elif age >= 55:
            equity = 0.15
        else:
            equity = max(0.15, 0.75 - (age - 35) * 0.03)
        corp = 0.10
        alt = 0.05
        gsec = max(0.0, 1.0 - equity - corp - alt)
        return {"E": equity, "C": corp, "G": gsec, "Alt": alt}

    # AI starts from the proposed base glide path, then dynamically adjusts E/G.
    if age <= 34:
        equity, corp, gsec, alt = 0.85, 0.05, 0.00, 0.10
    elif age <= 44:
        equity, corp, gsec, alt = 0.70, 0.05, 0.15, 0.10
    elif age <= 49:
        equity, corp, gsec, alt = 0.55, 0.05, 0.25, 0.15
    elif age <= 54:
        equity, corp, gsec, alt = 0.35, 0.05, 0.40, 0.20
    else:
        equity, corp, gsec, alt = 0.15, 0.05, 0.60, 0.20
    return {"E": equity, "C": corp, "G": gsec, "Alt": alt}


def qx_makeham_gompertz(age: int, cfg: NPSConfig) -> float:
    """One-year mortality rate at integer age using the Excel module proxy."""

    force = cfg.gompertz_A + cfg.gompertz_B * (cfg.gompertz_c**age)
    return float(np.clip(1.0 - math.exp(-force), 0.0, 1.0))


def annuity_due_factor(retirement_age: int, rate: np.ndarray | float, cfg: NPSConfig) -> np.ndarray:
    """Actuarial annuity-due factor at retirement for vector or scalar rates.

    a_due = sum_t v^t * t_p_x, starting at t=0.
    """

    r = np.asarray(rate, dtype=float)
    scalar = r.ndim == 0
    r = np.atleast_1d(r)
    r = np.maximum(r, cfg.min_rate)

    apv = np.ones_like(r, dtype=float)  # payment at t=0
    survival = np.ones_like(r, dtype=float)
    last_t = max(0, cfg.max_annuity_age - retirement_age)

    for t in range(1, last_t + 1):
        age = retirement_age + t - 1
        qx = qx_makeham_gompertz(age, cfg)
        survival *= 1.0 - qx
        apv += survival / np.power(1.0 + r, t)

    return apv[0] if scalar else apv


def proxy_stress_probability(
    trailing_equity_return: np.ndarray,
    trailing_volatility: np.ndarray,
    rate: np.ndarray,
    is_stress_regime: np.ndarray,
) -> np.ndarray:
    """Transparent replacement for the unavailable fitted AI classifier.

    The supplied methodology says the AI layer reads five signals:
    trailing equity return, trailing volatility, yield-curve slope, credit spread,
    and equity valuation. The public materials did not include historical credit
    spread, PE ratio or a fitted sklearn model, so this function constructs a
    conservative, interpretable proxy score from simulated quantities.

    Replace this function with `classifier.predict_proba(features)[:, 1]` when
    actual feature data and a fitted model are available.
    """

    # Simulated proxies for missing features. During stress, credit spread widens
    # and valuation proxy deteriorates. Rate slope is approximated by theta-rate.
    slope_proxy = 0.015 + (0.072 - rate)  # positive is normal, negative is stress-like
    credit_spread_proxy = np.where(is_stress_regime, 0.025, 0.012)
    pe_relative_proxy = np.where(is_stress_regime, 0.72, 1.00)

    score = np.full_like(trailing_equity_return, -1.75, dtype=float)
    score += np.where(trailing_equity_return < -0.10, 1.60, 0.0)
    score += np.where(trailing_equity_return < -0.20, 0.80, 0.0)
    score += np.where(trailing_volatility > 0.28, 1.20, 0.0)
    score += np.where(slope_proxy < 0.00, 0.70, 0.0)
    score += np.where(credit_spread_proxy > 0.020, 1.00, 0.0)
    score += np.where(pe_relative_proxy < 0.75, 0.90, 0.0)

    return 1.0 / (1.0 + np.exp(-score))


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


@dataclass
class NPSResult:
    """Container returned by simulate_strategy()."""

    config: NPSConfig
    strategy: str
    strategy_label: str
    terminal_rr: np.ndarray
    terminal_corpus: np.ndarray
    final_salary: np.ndarray
    annuity_factor: np.ndarray
    max_drawdown: np.ndarray
    fan_chart: pd.DataFrame
    metrics: Dict[str, float | int | str]

    def summary_frame(self) -> pd.DataFrame:
        """Return one-row pandas DataFrame of key metrics."""

        return pd.DataFrame([self.metrics])


def simulate_strategy(cfg: Optional[NPSConfig] = None, strategy: str = "proposed") -> NPSResult:
    """Run one NPS strategy for one entry age.

    Args:
        cfg: NPSConfig. Use cfg.with_changes(...) to modify defaults.
        strategy: "current", "proposed", or "ai".

    Returns:
        NPSResult containing terminal replacement-rate paths, fan-chart data and
        summary metrics.
    """

    cfg = cfg or NPSConfig()
    if cfg.n_paths < 10:
        raise ValueError("n_paths should be at least 10 for percentile statistics.")
    if cfg.retirement_age <= cfg.entry_age:
        raise ValueError("retirement_age must exceed entry_age.")

    # AI strategy uses proposed static weights as its base.
    base_weight_strategy = "proposed" if strategy == "ai" else strategy
    if base_weight_strategy not in STRATEGY_LABELS:
        raise ValueError(f"Unknown strategy '{strategy}'.")

    rng = np.random.default_rng(cfg.seed)
    n = int(cfg.n_paths)
    dt = float(cfg.time_step)
    sqrt_dt = math.sqrt(dt)
    months = int(round((cfg.retirement_age - cfg.entry_age) / dt))
    if months <= 0:
        raise ValueError("Projection horizon is zero or negative.")

    # State variables
    corpus = np.full(n, cfg.initial_corpus, dtype=float)
    salary = np.full(n, cfg.initial_salary, dtype=float)
    rate = np.full(n, cfg.r0, dtype=float)
    inflation = np.full(n, cfg.inflation0, dtype=float)
    stress_regime = np.zeros(n, dtype=bool)
    ai_adj = np.zeros(n, dtype=float)

    # Rolling equity tracking for proxy AI features
    equity_return_buffer = np.zeros((12, n), dtype=float)
    equity_buffer_count = 0

    fan_idx = np.linspace(0, months, cfg.fan_points, dtype=int)
    fan_records: List[Dict[str, float | int]] = []

    running_peak = np.zeros(n, dtype=float)
    max_drawdown = np.zeros(n, dtype=float)

    # Main monthly loop
    for m in range(months + 1):
        years_elapsed = m * dt
        current_age = int(math.floor(cfg.entry_age + years_elapsed))

        annuity_now = annuity_due_factor(cfg.retirement_age, rate, cfg)
        liability_now = np.maximum(salary * cfg.target_replacement_rate * annuity_now, 1e-9)
        funding_ratio = corpus / liability_now

        running_peak = np.maximum(running_peak, funding_ratio)
        drawdown = np.zeros_like(funding_ratio)
        positive_peak = running_peak > 0
        drawdown[positive_peak] = (running_peak[positive_peak] - funding_ratio[positive_peak]) / running_peak[positive_peak]
        max_drawdown = np.maximum(max_drawdown, drawdown)

        if m in set(fan_idx.tolist()):
            fan_records.append(
                {
                    "month": int(m),
                    "year": float(years_elapsed),
                    "age": float(cfg.entry_age + years_elapsed),
                    "p5": _safe_percentile(funding_ratio, 5),
                    "p25": _safe_percentile(funding_ratio, 25),
                    "median": _safe_percentile(funding_ratio, 50),
                    "p75": _safe_percentile(funding_ratio, 75),
                    "p95": _safe_percentile(funding_ratio, 95),
                }
            )

        if m == months:
            break

        # Correlated rate/equity innovations
        z_rate = rng.standard_normal(n)
        z_independent = rng.standard_normal(n)
        z_equity = cfg.rho_equity_rate * z_rate + math.sqrt(1.0 - cfg.rho_equity_rate**2) * z_independent

        # Markov regime update
        u = rng.random(n)
        stress_regime = np.where(
            stress_regime,
            u > cfg.p_bear_to_bull_monthly,
            u < cfg.p_bull_to_bear_monthly,
        )

        # Equity exact GBM update
        mu_equity = np.where(stress_regime, cfg.equity_mu_bear, cfg.equity_mu_bull)
        sigma_equity = np.where(stress_regime, cfg.equity_sigma_bear, cfg.equity_sigma_bull)
        equity_return = np.exp((mu_equity - 0.5 * sigma_equity**2) * dt + sigma_equity * sqrt_dt * z_equity) - 1.0

        # Vasicek exact update and duration-based G-Sec total return
        previous_rate = rate.copy()
        exp_kdt = math.exp(-cfg.vasicek_kappa * dt)
        vasicek_sd = cfg.vasicek_sigma * math.sqrt((1.0 - math.exp(-2.0 * cfg.vasicek_kappa * dt)) / (2.0 * cfg.vasicek_kappa))
        rate = cfg.vasicek_theta + (rate - cfg.vasicek_theta) * exp_kdt + vasicek_sd * z_rate
        rate = np.maximum(rate, cfg.min_rate)
        gsec_return = previous_rate * dt - cfg.gsec_duration * (rate - previous_rate)

        # Corporate bonds and alternatives as lognormal total returns
        corp_return = np.exp((cfg.corp_mu - 0.5 * cfg.corp_sigma**2) * dt + cfg.corp_sigma * sqrt_dt * rng.standard_normal(n)) - 1.0
        alt_return = np.exp((cfg.alt_mu - 0.5 * cfg.alt_sigma**2) * dt + cfg.alt_sigma * sqrt_dt * rng.standard_normal(n)) - 1.0

        # Inflation OU exact update and salary growth
        exp_pidt = math.exp(-cfg.inflation_kappa * dt)
        infl_sd = cfg.inflation_sigma * math.sqrt((1.0 - math.exp(-2.0 * cfg.inflation_kappa * dt)) / (2.0 * cfg.inflation_kappa))
        inflation = cfg.inflation_theta + (inflation - cfg.inflation_theta) * exp_pidt + infl_sd * rng.standard_normal(n)
        salary_growth = np.exp(
            (cfg.real_salary_growth + inflation - 0.5 * cfg.salary_sigma**2) * dt
            + cfg.salary_sigma * sqrt_dt * rng.standard_normal(n)
        )
        salary *= salary_growth

        # AI proxy de-risking at annual rebalancing points after 12 months
        equity_return_buffer[m % 12, :] = equity_return
        equity_buffer_count = min(12, equity_buffer_count + 1)
        if strategy == "ai" and m > 12 and m % 12 == 0:
            recent_returns = equity_return_buffer[:equity_buffer_count, :]
            trailing_return = np.prod(1.0 + recent_returns, axis=0) - 1.0
            trailing_vol = np.std(recent_returns, axis=0, ddof=0) * math.sqrt(12.0)
            p_stress = proxy_stress_probability(trailing_return, trailing_vol, rate, stress_regime)

            trigger = p_stress > cfg.ai_high_threshold
            restore = p_stress < cfg.ai_low_threshold
            ai_adj = np.where(trigger, cfg.ai_equity_adjustment, ai_adj)
            ai_adj = np.where(restore, np.minimum(0.0, ai_adj + cfg.ai_restore_step), ai_adj)

        # Portfolio weights and accumulation
        weights = strategy_weights(base_weight_strategy, current_age)
        w_e = np.full(n, weights["E"], dtype=float)
        w_c = np.full(n, weights["C"], dtype=float)
        w_g = np.full(n, weights["G"], dtype=float)
        w_a = np.full(n, weights["Alt"], dtype=float)

        if strategy == "ai":
            w_e = np.maximum(0.0, w_e + ai_adj)
            # Reallocate equity reduction/addition to G-Sec, leaving C and Alt fixed.
            w_g = np.maximum(0.0, 1.0 - w_e - w_c - w_a)

        portfolio_return = w_e * equity_return + w_c * corp_return + w_g * gsec_return + w_a * alt_return
        contribution = salary * cfg.contribution_rate * dt
        corpus = corpus * (1.0 + portfolio_return) + contribution

    terminal_annuity = annuity_due_factor(cfg.retirement_age, rate, cfg)
    terminal_liability = np.maximum(salary * cfg.target_replacement_rate * terminal_annuity, 1e-9)
    terminal_rr = corpus / terminal_liability

    sorted_rr = np.sort(terminal_rr)
    p5 = _safe_percentile(sorted_rr, 5)
    p95 = _safe_percentile(sorted_rr, 95)
    cvar_cut = max(1, int(math.ceil(0.05 * n)))
    cvar_95 = float(np.mean(sorted_rr[:cvar_cut]))

    metrics: Dict[str, float | int | str] = {
        "entry_age": int(cfg.entry_age),
        "retirement_age": int(cfg.retirement_age),
        "horizon_years": int(cfg.retirement_age - cfg.entry_age),
        "strategy": strategy,
        "strategy_label": STRATEGY_LABELS[strategy],
        "n_paths": int(n),
        "seed": int(cfg.seed),
        "median_rr": _safe_percentile(sorted_rr, 50),
        "p5_rr": p5,
        "p25_rr": _safe_percentile(sorted_rr, 25),
        "p75_rr": _safe_percentile(sorted_rr, 75),
        "p95_rr": p95,
        "cvar_95_lower_tail_rr": cvar_95,
        "probability_adequate_rr_ge_1": float(np.mean(terminal_rr >= 1.0)),
        "mean_max_drawdown": float(np.mean(max_drawdown)),
        "p95_max_drawdown": _safe_percentile(max_drawdown, 95),
        "median_terminal_corpus": _safe_percentile(corpus, 50),
        "median_final_salary": _safe_percentile(salary, 50),
        "median_annuity_factor": _safe_percentile(terminal_annuity, 50),
        "ai_note": "proxy de-risking rule, not fitted GradientBoosting/LSTM" if strategy == "ai" else "not applicable",
    }

    return NPSResult(
        config=cfg,
        strategy=strategy,
        strategy_label=STRATEGY_LABELS[strategy],
        terminal_rr=terminal_rr,
        terminal_corpus=corpus,
        final_salary=salary,
        annuity_factor=terminal_annuity,
        max_drawdown=max_drawdown,
        fan_chart=pd.DataFrame(fan_records),
        metrics=metrics,
    )


def run_all(
    cfg: Optional[NPSConfig] = None,
    entry_ages: Iterable[int] = (25, 35, 45),
    strategies: Iterable[str] = ("current", "proposed", "ai"),
) -> pd.DataFrame:
    """Run base-case simulations for all selected entry ages and strategies."""

    cfg = cfg or NPSConfig()
    rows: List[Dict[str, float | int | str]] = []
    for age in entry_ages:
        for strategy in strategies:
            result = simulate_strategy(cfg.with_changes(entry_age=int(age)), strategy=strategy)
            rows.append(result.metrics)
    return pd.DataFrame(rows)


def run_scenarios(
    cfg: Optional[NPSConfig] = None,
    entry_age: int = 25,
    strategy: str = "proposed",
    scenarios: Mapping[str, Mapping[str, float | str]] = SCENARIOS,
) -> pd.DataFrame:
    """Run the scenario table for one entry age and strategy."""

    cfg = cfg or NPSConfig()
    rows: List[Dict[str, float | int | str]] = []
    for key, changes in scenarios.items():
        label = str(changes.get("label", key))
        params = {k: v for k, v in changes.items() if k != "label"}
        scenario_cfg = cfg.with_changes(entry_age=entry_age, **params)
        result = simulate_strategy(scenario_cfg, strategy=strategy)
        row = dict(result.metrics)
        row["scenario"] = key
        row["scenario_label"] = label
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        base_median = float(df.loc[df["scenario"] == "base", "median_rr"].iloc[0]) if "base" in set(df["scenario"]) else float(df["median_rr"].iloc[0])
        df["median_rr_vs_base_pct"] = (df["median_rr"] / base_median - 1.0) * 100.0
    return df


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------


def plot_fan_chart(result: NPSResult, *, show: bool = True):
    """Plot a replacement-rate/funding-ratio fan chart for a simulation result."""

    import matplotlib.pyplot as plt

    f = result.fan_chart
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.fill_between(f["age"], f["p5"], f["p95"], alpha=0.18, label="5th-95th percentile")
    ax.fill_between(f["age"], f["p25"], f["p75"], alpha=0.28, label="25th-75th percentile")
    ax.plot(f["age"], f["median"], linewidth=2, label="Median")
    ax.axhline(1.0, linestyle="--", linewidth=1, label="Adequacy target = 1.0x")
    ax.set_title(f"Funding ratio fan chart — {result.strategy_label}, entry age {result.config.entry_age}")
    ax.set_xlabel("Age")
    ax.set_ylabel("Funding ratio / replacement-rate multiple")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    if show:
        plt.show()
    return fig


def plot_strategy_summary(summary: pd.DataFrame, *, show: bool = True):
    """Grouped bar chart of median replacement rate by entry age and strategy."""

    import matplotlib.pyplot as plt

    pivot = summary.pivot(index="entry_age", columns="strategy_label", values="median_rr")
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="bar", ax=ax)
    ax.axhline(1.0, linestyle="--", linewidth=1)
    ax.set_title("Median replacement rate by entry age and strategy")
    ax.set_xlabel("Entry age")
    ax.set_ylabel("Median replacement-rate multiple")
    ax.legend(title="Strategy")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    if show:
        plt.show()
    return fig


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def save_outputs(
    outdir: str | os.PathLike = "outputs",
    cfg: Optional[NPSConfig] = None,
    summary: Optional[pd.DataFrame] = None,
    scenarios: Optional[pd.DataFrame] = None,
    make_plots: bool = True,
) -> Dict[str, str]:
    """Save CSV, optional XLSX, plots and a small HTML report.

    Returns a dictionary of output labels to file paths.
    """

    cfg = cfg or NPSConfig()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    summary = summary if summary is not None else run_all(cfg)
    scenarios = scenarios if scenarios is not None else run_scenarios(cfg)

    written: Dict[str, str] = {}

    summary_csv = out / "nps_results_summary.csv"
    scenario_csv = out / "nps_scenario_summary.csv"
    summary.to_csv(summary_csv, index=False)
    scenarios.to_csv(scenario_csv, index=False)
    written["summary_csv"] = str(summary_csv)
    written["scenario_csv"] = str(scenario_csv)

    # Excel export is optional because a minimal Jupyter environment may not have
    # openpyxl/xlsxwriter. CSV export above is always available.
    xlsx_path = out / "NPS_DataTables_generated.xlsx"
    try:
        with pd.ExcelWriter(xlsx_path) as writer:
            pd.DataFrame([asdict(cfg)]).T.reset_index().rename(columns={"index": "parameter", 0: "value"}).to_excel(writer, sheet_name="Assumptions", index=False)
            summary.to_excel(writer, sheet_name="Base Results", index=False)
            scenarios.to_excel(writer, sheet_name="Scenarios", index=False)
        written["xlsx"] = str(xlsx_path)
    except Exception as exc:  # pragma: no cover - environment dependent
        written["xlsx_skipped"] = f"Excel export skipped: {exc}"

    if make_plots:
        import matplotlib.pyplot as plt

        fig1 = plot_strategy_summary(summary, show=False)
        chart_path = out / "nps_strategy_summary.png"
        fig1.savefig(chart_path, dpi=160, bbox_inches="tight")
        plt.close(fig1)
        written["strategy_chart"] = str(chart_path)

        fan_result = simulate_strategy(cfg.with_changes(entry_age=25), strategy="ai")
        fig2 = plot_fan_chart(fan_result, show=False)
        fan_path = out / "nps_fan_chart_age25_ai.png"
        fig2.savefig(fan_path, dpi=160, bbox_inches="tight")
        plt.close(fig2)
        written["fan_chart"] = str(fan_path)

    html_path = out / "nps_report.html"
    html = build_html_report(cfg, summary, scenarios, written)
    html_path.write_text(html, encoding="utf-8")
    written["html_report"] = str(html_path)

    meta_path = out / "run_metadata.json"
    meta_path.write_text(json.dumps({"config": asdict(cfg), "outputs": written}, indent=2), encoding="utf-8")
    written["metadata_json"] = str(meta_path)
    return written


def build_html_report(
    cfg: NPSConfig,
    summary: pd.DataFrame,
    scenarios: pd.DataFrame,
    outputs: Optional[Mapping[str, str]] = None,
) -> str:
    """Create a simple self-contained HTML summary."""

    outputs = outputs or {}
    display_cols = [
        "entry_age",
        "strategy_label",
        "median_rr",
        "p5_rr",
        "p95_rr",
        "cvar_95_lower_tail_rr",
        "probability_adequate_rr_ge_1",
        "mean_max_drawdown",
    ]
    scenario_cols = [
        "scenario_label",
        "median_rr",
        "p5_rr",
        "cvar_95_lower_tail_rr",
        "median_rr_vs_base_pct",
    ]

    s1 = summary[display_cols].copy()
    s2 = scenarios[scenario_cols].copy()
    for df in (s1, s2):
        for c in df.select_dtypes(include=["float", "float64"]).columns:
            df[c] = df[c].map(lambda x: f"{x:.3f}" if abs(x) < 10 else f"{x:.2f}")

    chart_tags = ""
    if "strategy_chart" in outputs:
        chart_tags += f'<h2>Strategy summary chart</h2><img src="{Path(outputs["strategy_chart"]).name}" style="max-width:100%;">'
    if "fan_chart" in outputs:
        chart_tags += f'<h2>Fan chart</h2><img src="{Path(outputs["fan_chart"]).name}" style="max-width:100%;">'

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>NPS Simulator Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 32px; line-height: 1.45; color: #1f2937; }}
h1, h2 {{ color: #12355b; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
th, td {{ border: 1px solid #d1d5db; padding: 7px; text-align: right; }}
th:first-child, td:first-child, td:nth-child(2) {{ text-align: left; }}
th {{ background: #eef2ff; }}
.note {{ background: #fff7ed; border-left: 4px solid #f97316; padding: 10px 14px; }}
</style>
</head>
<body>
<h1>NPS Monte Carlo Simulator — Generated Report</h1>
<p class="note"><strong>Honesty note:</strong> outputs are stochastic model projections from the runnable Python engine. They are not hard-coded paper tables and do not constitute investment advice. The AI layer is a transparent proxy rule because no fitted model or training dataset was provided.</p>
<p><strong>Paths:</strong> {cfg.n_paths:,} &nbsp; <strong>Seed:</strong> {cfg.seed} &nbsp; <strong>Time step:</strong> monthly</p>
<h2>Base-case results</h2>
{s1.to_html(index=False, escape=False)}
<h2>Scenario results — age 25, proposed strategy</h2>
{s2.to_html(index=False, escape=False)}
{chart_tags}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------------------------


def _print_console_summary(summary: pd.DataFrame) -> None:
    cols = ["entry_age", "strategy_label", "median_rr", "p5_rr", "cvar_95_lower_tail_rr", "probability_adequate_rr_ge_1", "mean_max_drawdown"]
    printable = summary[cols].copy()
    for c in ["median_rr", "p5_rr", "cvar_95_lower_tail_rr"]:
        printable[c] = printable[c].map(lambda x: f"{x:.2f}x")
    printable["probability_adequate_rr_ge_1"] = printable["probability_adequate_rr_ge_1"].map(_as_percent)
    printable["mean_max_drawdown"] = printable["mean_max_drawdown"].map(_as_percent)
    print(printable.to_string(index=False))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the NPS Monte Carlo simulator.")
    parser.add_argument("--n-paths", type=int, default=500, help="Monte Carlo paths. Use 500 for quick test; 10000 for research run.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--entry-age", type=int, default=None, help="Optional single entry age to run for console output.")
    parser.add_argument("--strategy", choices=list(STRATEGY_LABELS), default=None, help="Optional single strategy to run for console output.")
    parser.add_argument("--outdir", default="outputs", help="Output folder for CSV/XLSX/HTML/PNG files.")
    parser.add_argument("--no-plots", action="store_true", help="Skip PNG plot creation.")
    args = parser.parse_args(argv)

    cfg = NPSConfig(n_paths=args.n_paths, seed=args.seed)

    if args.entry_age is not None and args.strategy is not None:
        result = simulate_strategy(cfg.with_changes(entry_age=args.entry_age), args.strategy)
        summary = result.summary_frame()
        scenarios = run_scenarios(cfg.with_changes(entry_age=args.entry_age), entry_age=args.entry_age, strategy=args.strategy)
    else:
        summary = run_all(cfg)
        scenarios = run_scenarios(cfg)

    _print_console_summary(summary)
    outputs = save_outputs(args.outdir, cfg, summary, scenarios, make_plots=not args.no_plots)
    print("\nFiles written:")
    for k, v in outputs.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
