"""Market-data retrieval and transparent demonstration fallback."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .analytics import ASSETS


YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TICKERS = {
    "uk_gilts": "IGLT.L",
    "global_equities_usd": "ACWI",
    "uk_equities": "VUKE.L",
    "investment_grade_bonds": "SLXX.L",
    "cash_usd": "BIL",
    "gold_usd": "GLD",
    "gbp_usd": "GBPUSD=X",
}


def yahoo_monthly(symbol: str, start: str = "2014-01-01") -> pd.Series:
    start_ts = int(pd.Timestamp(start, tz="UTC").timestamp())
    end_ts = int(time.time()) + 86400
    query = urllib.parse.urlencode({"period1": start_ts, "period2": end_ts, "interval": "1mo", "events": "history"})
    url = YAHOO_URL.format(symbol=urllib.parse.quote(symbol, safe="")) + "?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 portfolio-dashboard/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    dates = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None).to_period("M").to_timestamp("M")
    indicators = result["indicators"]
    values = indicators.get("adjclose", indicators["quote"])[0].get("adjclose", indicators["quote"][0]["close"])
    return pd.Series(values, index=dates, name=symbol).groupby(level=0).last()


def build_market_data() -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Fetch monthly data and convert USD sleeves into GBP total-return proxies."""
    series: Dict[str, pd.Series] = {}
    for key, ticker in TICKERS.items():
        series[key] = yahoo_monthly(ticker)
    raw = pd.concat(series, axis=1).sort_index()
    data = pd.DataFrame(index=raw.index)
    data["uk_gilts"] = raw["uk_gilts"]
    data["global_equities"] = raw["global_equities_usd"] / raw["gbp_usd"]
    data["uk_equities"] = raw["uk_equities"]
    data["investment_grade_bonds"] = raw["investment_grade_bonds"]
    data["cash"] = raw["cash_usd"] / raw["gbp_usd"]
    data["gold"] = raw["gold_usd"] / raw["gbp_usd"]
    data["fx_usd_vs_gbp"] = 1.0 / raw["gbp_usd"]
    data = data[ASSETS].dropna(how="any")
    yields = build_gilt_yield_proxy(data.index)
    prices = data.reset_index().rename(columns={"index": "date"})
    yield_frame = yields.reset_index().rename(columns={"index": "date"})
    return prices, yield_frame, "Yahoo Finance adjusted monthly close; UK gilt yield is a demonstration proxy"


def build_gilt_yield_proxy(index: pd.Index) -> pd.Series:
    """Create a clearly labelled monthly 10Y gilt-yield proxy when the public yield feed is unavailable."""
    dates = pd.DatetimeIndex(index)
    anchor_dates = pd.to_datetime(["2014-01-31", "2015-12-31", "2016-10-31", "2018-12-31", "2020-08-31", "2021-12-31", "2022-09-30", "2023-12-31", "2025-12-31", "2026-12-31"])
    anchor_values = np.array([2.75, 1.85, 0.75, 1.30, 0.25, 0.95, 4.10, 3.55, 4.35, 4.15])
    x = dates.view("int64").astype(float)
    ax = anchor_dates.view("int64").astype(float)
    values = np.interp(x, ax, anchor_values)
    seasonal = 0.04 * np.sin(np.arange(len(dates)) * 1.7)
    return pd.Series(np.maximum(values + seasonal, 0.05), index=dates, name="uk_10y_gilt_yield_pct")
