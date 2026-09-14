"""Core portfolio analytics used by the dashboard and memo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

import numpy as np
import pandas as pd


ASSETS = [
    "uk_gilts",
    "global_equities",
    "uk_equities",
    "investment_grade_bonds",
    "cash",
    "gold",
    "fx_usd_vs_gbp",
]

DISPLAY_NAMES = {
    "uk_gilts": "UK gilts",
    "global_equities": "Global equities",
    "uk_equities": "UK equities",
    "investment_grade_bonds": "Investment-grade bonds",
    "cash": "Cash",
    "gold": "Gold",
    "fx_usd_vs_gbp": "FX (USD vs GBP)",
}

PORTFOLIOS: Dict[str, Dict[str, float]] = {
    "Growth": {
        "uk_gilts": 0.10,
        "global_equities": 0.45,
        "uk_equities": 0.15,
        "investment_grade_bonds": 0.10,
        "cash": 0.05,
        "gold": 0.10,
        "fx_usd_vs_gbp": 0.05,
    },
    "Balanced": {
        "uk_gilts": 0.25,
        "global_equities": 0.25,
        "uk_equities": 0.10,
        "investment_grade_bonds": 0.20,
        "cash": 0.10,
        "gold": 0.07,
        "fx_usd_vs_gbp": 0.03,
    },
    "Capital Preservation": {
        "uk_gilts": 0.35,
        "global_equities": 0.08,
        "uk_equities": 0.05,
        "investment_grade_bonds": 0.25,
        "cash": 0.20,
        "gold": 0.05,
        "fx_usd_vs_gbp": 0.02,
    },
}

HORIZONS = {"Growth": 20, "Balanced": 10, "Capital Preservation": 5}


@dataclass(frozen=True)
class DurationResult:
    modified_duration: float
    dv01_per_million: float
    observations: int


def clean_monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Coerce, de-duplicate, sort and retain complete monthly price observations."""
    frame = prices.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.set_index("date")
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    for col in frame.columns:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame.ffill(limit=1).dropna(how="any")
    return frame[ASSETS]


def monthly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate simple monthly returns from cleaned price/index levels."""
    return clean_monthly_prices(prices).pct_change().dropna(how="any")


def max_drawdown(return_series: pd.Series) -> float:
    wealth = (1.0 + return_series.fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def performance_metrics(returns: pd.DataFrame, risk_free_annual: float = 0.02) -> pd.DataFrame:
    """Return annualised performance statistics for each column."""
    rows = []
    monthly_rf = (1.0 + risk_free_annual) ** (1.0 / 12.0) - 1.0
    for name in returns.columns:
        series = returns[name].dropna()
        annual_return = float((1.0 + series).prod() ** (12.0 / len(series)) - 1.0)
        annual_vol = float(series.std(ddof=1) * np.sqrt(12.0))
        sharpe = (annual_return - risk_free_annual) / annual_vol if annual_vol else np.nan
        rows.append(
            {
                "asset": name,
                "annualised_return": annual_return,
                "annualised_volatility": annual_vol,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_drawdown(series),
                "observations": int(len(series)),
            }
        )
    return pd.DataFrame(rows).set_index("asset")


def portfolio_returns(asset_returns: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """Compute a monthly portfolio return series from fixed target weights."""
    missing = set(weights) - set(asset_returns.columns)
    if missing:
        raise KeyError("Missing assets: " + ", ".join(sorted(missing)))
    total = sum(weights.values())
    if not np.isclose(total, 1.0):
        raise ValueError(f"Portfolio weights must sum to 1.0, got {total:.6f}")
    return asset_returns[list(weights)].mul(pd.Series(weights)).sum(axis=1).rename("portfolio_return")


def portfolio_metrics(asset_returns: pd.DataFrame, risk_free_annual: float = 0.02) -> pd.DataFrame:
    result = {}
    for name, weights in PORTFOLIOS.items():
        result[name] = performance_metrics(portfolio_returns(asset_returns, weights).to_frame(name), risk_free_annual).iloc[0]
    return pd.DataFrame(result).T


def estimate_gilt_duration(
    gilt_returns: pd.Series,
    yield_series: pd.Series,
    portfolio_value: float = 1_000_000.0,
) -> DurationResult:
    """Estimate modified duration as -cov(price return, yield change)/var(yield change)."""
    data = pd.concat([gilt_returns.rename("price_return"), yield_series.rename("yield")], axis=1).dropna()
    # Yield data is stored in percentage points; duration needs decimal yield changes.
    dy = data["yield"].diff() * 0.01
    aligned = pd.concat([data["price_return"], dy.rename("yield_change")], axis=1).dropna()
    variance = float(aligned["yield_change"].var(ddof=1))
    if variance == 0 or len(aligned) < 3:
        duration = 7.0
    else:
        covariance = float(aligned["price_return"].cov(aligned["yield_change"]))
        duration = -covariance / variance
        duration = float(np.clip(duration, 0.5, 20.0))
    dv01 = duration * portfolio_value * 0.0001
    return DurationResult(duration, dv01, len(aligned))


def duration_table(duration: DurationResult, portfolio_value: float = 1_000_000.0) -> pd.DataFrame:
    rows = []
    for name, weights in PORTFOLIOS.items():
        gilt_value = portfolio_value * weights["uk_gilts"]
        bond_value = portfolio_value * weights["investment_grade_bonds"]
        rows.append(
            {
                "portfolio": name,
                "gilt_weight": weights["uk_gilts"],
                "gilt_market_value_gbp": gilt_value,
                "gilt_modified_duration_years": duration.modified_duration,
                "gilt_dv01_gbp_per_bp": duration.modified_duration * gilt_value * 0.0001,
                "ig_duration_assumption_years": 4.5,
                "estimated_total_rate_dv01_gbp_per_bp": duration.modified_duration * gilt_value * 0.0001 + 4.5 * bond_value * 0.0001,
            }
        )
    return pd.DataFrame(rows).set_index("portfolio")


def scenario_shocks(duration: float) -> Dict[str, Dict[str, float]]:
    """One-period sleeve shocks for the requested macro scenarios."""
    gilt_rate = duration * 0.01
    ig_rate = 4.5 * 0.01
    base = {asset: 0.0 for asset in ASSETS}
    scenarios = {}
    scenarios["Rates +100bp"] = {**base, "uk_gilts": -gilt_rate, "investment_grade_bonds": -ig_rate, "global_equities": -0.02, "uk_equities": -0.02}
    scenarios["Rates -100bp"] = {**base, "uk_gilts": gilt_rate, "investment_grade_bonds": ig_rate, "global_equities": 0.02, "uk_equities": 0.02}
    scenarios["Equities -20%"] = {**base, "global_equities": -0.20, "uk_equities": -0.20}
    scenarios["Inflation higher"] = {**base, "uk_gilts": -0.07, "investment_grade_bonds": -0.05, "global_equities": -0.05, "uk_equities": -0.04, "cash": 0.01, "gold": 0.08, "fx_usd_vs_gbp": 0.03}
    scenarios["GBP weaker 10%"] = {**base, "global_equities": 0.10, "cash": 0.10, "gold": 0.10, "fx_usd_vs_gbp": 0.10}
    return scenarios


def scenario_table(duration: float) -> pd.DataFrame:
    rows = []
    for scenario, shocks in scenario_shocks(duration).items():
        for portfolio, weights in PORTFOLIOS.items():
            impact = sum(weights[asset] * shocks[asset] for asset in ASSETS)
            rows.append({"scenario": scenario, "portfolio": portfolio, "estimated_impact": impact})
    return pd.DataFrame(rows).pivot(index="scenario", columns="portfolio", values="estimated_impact")


def period_table(asset_returns: pd.DataFrame) -> pd.DataFrame:
    """Compare portfolio outcomes in named historical windows."""
    end = asset_returns.index.max()
    periods = {
        "Full sample": (asset_returns.index.min(), end),
        "COVID shock": (pd.Timestamp("2020-02-01"), pd.Timestamp("2020-04-30")),
        "Rates & inflation": (pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")),
        "Recent": (pd.Timestamp("2024-01-01"), end),
    }
    rows = []
    for period, (start, finish) in periods.items():
        window = asset_returns.loc[(asset_returns.index >= start) & (asset_returns.index <= finish)]
        if window.empty:
            continue
        for portfolio, weights in PORTFOLIOS.items():
            series = portfolio_returns(window, weights)
            rows.append({"period": period, "portfolio": portfolio, "cumulative_return": (1 + series).prod() - 1, "worst_month": series.min(), "observations": len(series)})
    return pd.DataFrame(rows).set_index(["period", "portfolio"])
