import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_dashboard.analytics import (  # noqa: E402
    ASSETS,
    PORTFOLIOS,
    clean_monthly_prices,
    portfolio_returns,
    scenario_table,
)


def sample_prices():
    index = pd.date_range("2020-01-31", periods=5, freq="ME")
    return pd.DataFrame({asset: np.arange(100, 105, dtype=float) for asset in ASSETS}, index=index)


def test_cleaning_sorts_coerces_and_deduplicates():
    raw = sample_prices().reset_index().rename(columns={"index": "date"})
    raw["cash"] = raw["cash"].astype(object)
    raw.loc[2, "cash"] = "bad"
    raw = pd.concat([raw.iloc[[3, 0, 1, 2, 4]], raw.iloc[[4]]], ignore_index=True)
    cleaned = clean_monthly_prices(raw)
    assert cleaned.index.is_monotonic_increasing
    assert not cleaned.index.duplicated().any()
    assert cleaned["cash"].isna().sum() == 0


def test_portfolios_sum_to_one_and_returns_are_weighted():
    returns = pd.DataFrame(0.01, index=pd.date_range("2020-01-31", periods=2, freq="ME"), columns=ASSETS)
    for weights in PORTFOLIOS.values():
        assert np.isclose(sum(weights.values()), 1.0)
        assert np.allclose(portfolio_returns(returns, weights), 0.01)


def test_rate_and_equity_stresses_have_expected_direction():
    scenarios = scenario_table(7.0)
    assert scenarios.loc["Rates +100bp", "Capital Preservation"] < 0
    assert scenarios.loc["Rates -100bp", "Capital Preservation"] > 0
    assert scenarios.loc["Equities -20%", "Growth"] < scenarios.loc["Equities -20%", "Balanced"]
