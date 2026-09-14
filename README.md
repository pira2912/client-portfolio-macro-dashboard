# Client Portfolio & Macro Scenario Dashboard | Python

This repository is a small wealth-management case study for three fictional UK clients. It turns monthly market data into portfolio statistics, scenario results and two client-facing reports. the point is to connect the numbers to a client's time horizon and need for cash.

## What is in the repository

- A monthly data fetcher using Yahoo Finance's public chart endpoint.
- A bundled CSV snapshot, so the project still runs offline.
- Pandas and NumPy calculations for return, volatility, Sharpe ratio, drawdown and correlations.
- A regression estimate for gilt duration and an illustrative DV01 table.
- Three allocations: Growth (20 years), Balanced (10 years), and Capital Preservation (5 years with liquidity needs).
- Historical comparisons for the full sample, the COVID shock, the 2022 rate and inflation period, and recent data.
- Scenario analysis for rates rising or falling 100bp, equities falling 20%, higher inflation, and sterling weakening 10%.
- `reports/client_memo.html`: a concise two-page client-style memo.
- `reports/dashboard.html`: a one-page static dashboard with figures.
- Tests for data cleaning, portfolio arithmetic and scenario direction.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_analysis.py
pytest
```

Open `reports/dashboard.html` and `reports/client_memo.html` in a browser. Generated tables go to `outputs/`, and charts go to `reports/figures/`.

To refresh the bundled data:

```bash
python scripts/fetch_data.py
python scripts/run_analysis.py
```

The fetcher uses adjusted monthly closes where Yahoo provides them. If the endpoint is unavailable, it leaves the bundled snapshot in place and reports the reason. the included `uk_10y_gilt_yield_pct` series is a transparent demonstration proxy based on representative UK 10-year gilt levels, so replace it with a Bank of England series before using the code with real clients. See `data/raw/data_sources.csv` for the source map.

## Data and method

The price series are adjusted-close proxies intended to represent total returns:

| Sleeve | Proxy | Currency treatment |
|---|---|---|
| UK gilts | `IGLT.L` | GBP-listed ETF |
| Global equities | `ACWI` | USD adjusted close converted to GBP |
| UK equities | `VUKE.L` | GBP-listed ETF |
| Investment-grade bonds | `SLXX.L` | GBP-listed sterling corporate-bond ETF |
| Cash | `BIL` | USD T-bill ETF converted to GBP |
| Gold | `GLD` | USD gold ETF converted to GBP |
| FX exposure | `GBPUSD=X` | USD versus GBP return, `1 / GBPUSD` |

Portfolio returns are monthly weighted sums of sleeve returns. Annualised volatility is monthly standard deviation multiplied by `sqrt(12)`. Sharpe uses a constant 2% annual risk-free assumption. Maximum drawdown is the lowest distance from a running wealth peak.

Gilt modified duration comes from the regression of monthly gilt returns on changes in the proxy 10-year gilt yield, with a 0.5 to 20 year clamp. DV01 is `modified duration × gilt market value × 0.0001`, shown for a hypothetical £1m account. it is a risk estimate, not a live quote. Investment-grade bond rate sensitivity uses an illustrative 4.5-year duration assumption.

Stress tests are one-period directional shocks, not forecasts. They isolate the requested risks and leave out convexity, spread changes, taxes, fees, trading costs and manager skill.

## Important limitations

This is an educational framework, not regulated investment advice. The allocations are fictional. A real suitability assessment would need the client's objectives, spending and withdrawal schedule, income stability, liabilities, cash reserve, tax position, existing holdings, loss capacity, loss tolerance, investment experience, horizon, liquidity constraints, ESG preferences, currency needs, concentration risks and restrictions.

## Suggested GitHub presentation

Start with `reports/dashboard.html`, then link to `reports/client_memo.html`. The separation between data ingestion, analytics and presentation makes the project easy to review. it also shows the part that matters in a client conversation: the same market information leads to different choices for different people.

## CV-ready summary

**Client Portfolio & Macro Scenario Dashboard | Python**

- Built a suitability-led portfolio framework for three hypothetical client profiles, combining UK gilts, equities, bonds, cash, gold and FX using historical risk and correlation data.
- Stress-tested allocations under rate, inflation, equity and currency shocks, estimated gilt duration and DV01 exposure, and translated the results into a client-style memo covering trade-offs and liquidity needs.

## License

MIT. Market data remains subject to the terms of its source provider.
