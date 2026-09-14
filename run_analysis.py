#!/usr/bin/env python3
"""Run the complete analysis and build the dashboard/memo artifacts."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portfolio_dashboard.analytics import (  # noqa: E402
    DISPLAY_NAMES,
    PORTFOLIOS,
    clean_monthly_prices,
    duration_table,
    estimate_gilt_duration,
    monthly_returns,
    performance_metrics,
    period_table,
    portfolio_metrics,
    scenario_table,
)


def pct(x: float) -> str:
    return f"{x:.1%}"


def gbp(x: float) -> str:
    return f"£{x:,.0f}"


def html_table(frame: pd.DataFrame, percent_cols=()) -> str:
    out = frame.copy()
    for col in percent_cols:
        if col in out.columns:
            out[col] = out[col].map(pct)
    return out.to_html(classes="data-table", border=0, na_rep="—")


def make_figures(asset_returns: pd.DataFrame, port_returns: pd.DataFrame, metrics: pd.DataFrame, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    colors = {"Growth": "#14b8a6", "Balanced": "#4f46e5", "Capital Preservation": "#f59e0b"}

    fig, ax = plt.subplots(figsize=(8.8, 4.0), dpi=160)
    wealth = (1 + port_returns).cumprod()
    for col in wealth:
        ax.plot(wealth.index, wealth[col], label=col, lw=2.2, color=colors[col])
    ax.set_title("Illustrative portfolio growth of £1", loc="left", fontweight="bold")
    ax.set_ylabel("Index level")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(figure_dir / "portfolio_growth.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=160)
    x = metrics["annualised_volatility"] * 100
    y = metrics["annualised_return"] * 100
    for name in metrics.index:
        ax.scatter(x[name], y[name], s=90, color=colors.get(name, "#0f172a"))
        ax.annotate(name, (x[name], y[name]), xytext=(7, 5), textcoords="offset points", fontsize=9)
    ax.set_title("Risk / return snapshot", loc="left", fontweight="bold")
    ax.set_xlabel("Annualised volatility (%)")
    ax.set_ylabel("Annualised return (%)")
    fig.tight_layout()
    fig.savefig(figure_dir / "risk_return.png", bbox_inches="tight")
    plt.close(fig)

    corr = asset_returns.corr()
    fig, ax = plt.subplots(figsize=(7.3, 5.1), dpi=160)
    im = ax.imshow(corr.values, cmap="RdYlBu", vmin=-1, vmax=1)
    labels = [DISPLAY_NAMES.get(c, c) for c in corr.columns]
    ax.set_xticks(range(len(labels)), labels, rotation=50, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7)
    ax.set_title("Monthly return correlations", loc="left", fontweight="bold")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(figure_dir / "correlation_heatmap.png", bbox_inches="tight")
    plt.close(fig)


def write_dashboard(output_dir: Path, metrics: pd.DataFrame, scenarios: pd.DataFrame, duration: pd.DataFrame, figure_dir: Path, start: pd.Timestamp, end: pd.Timestamp) -> None:
    images = {}
    for filename in ["portfolio_growth.png", "risk_return.png", "correlation_heatmap.png"]:
        images[filename] = "data:image/png;base64," + base64.b64encode((figure_dir / filename).read_bytes()).decode()
    m = metrics.copy()
    m.index.name = "Portfolio"
    scenario_rows = scenarios.reset_index()
    scenario_rows.columns = ["Scenario"] + list(scenario_rows.columns[1:])
    scenario_display = scenario_rows.copy()
    for col in scenario_display.columns[1:]:
        scenario_display[col] = scenario_display[col].map(pct)
    d = duration.reset_index()
    cards = "".join(
        f'<div class="card"><div class="eyebrow">{name}</div><div class="big">{pct(m.loc[name, "annualised_return"])}</div><div class="sub">annualised return</div><div class="mini">{pct(m.loc[name, "annualised_volatility"])} vol · {pct(m.loc[name, "max_drawdown"])} max drawdown</div></div>'
        for name in m.index
    )
    html = f'''<!doctype html>
<html><head><meta charset="utf-8"><title>Client Portfolio Dashboard</title>
<style>
@page {{ size: A4 landscape; margin: 12mm; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:#f5f7fb; color:#18233a; font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }}
.page {{ max-width:1200px; margin:0 auto; padding:28px 32px; }}
.top {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:1px solid #dce2ee; padding-bottom:16px; }}
h1 {{ margin:0; font-size:30px; letter-spacing:-.03em; }} .kicker {{ color:#4f46e5; text-transform:uppercase; letter-spacing:.13em; font-size:11px; font-weight:800; margin-bottom:7px; }}
.note {{ color:#63708a; font-size:12px; max-width:380px; text-align:right; line-height:1.5; }}
.cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:18px 0; }} .card {{ background:white; border:1px solid #e2e7f0; border-radius:13px; padding:16px 18px; box-shadow:0 5px 15px rgba(30,50,90,.04); }}
.eyebrow {{ font-size:12px; font-weight:800; color:#46526a; }} .big {{ font-size:30px; font-weight:800; margin-top:9px; }} .sub,.mini {{ color:#6b7790; font-size:12px; }} .mini {{ margin-top:9px; }}
.grid {{ display:grid; grid-template-columns:1.12fr .88fr; gap:16px; align-items:start; }} .panel {{ background:white; border:1px solid #e2e7f0; border-radius:13px; padding:15px; margin-bottom:16px; }} .panel h2 {{ font-size:14px; margin:0 0 12px; }}
img {{ max-width:100%; display:block; }} table {{ width:100%; border-collapse:collapse; font-size:11px; }} th {{ text-align:left; color:#65718a; font-weight:700; border-bottom:1px solid #e2e7f0; padding:7px 6px; }} td {{ border-bottom:1px solid #edf0f5; padding:7px 6px; }} td:not(:first-child), th:not(:first-child) {{ text-align:right; }} .foot {{ color:#768198; font-size:10px; line-height:1.4; margin-top:8px; }}
</style></head><body><main class="page">
<div class="top"><div><div class="kicker">Wealth management · illustrative analysis</div><h1>Client Portfolio & Macro Scenario Dashboard</h1></div><div class="note">Monthly total-return proxies · {start:%b %Y}–{end:%b %Y}<br>For education only · not investment advice</div></div>
<section class="cards">{cards}</section>
<div class="grid"><div><div class="panel"><h2>Portfolio paths</h2><img src="{images['portfolio_growth.png']}" alt="Portfolio growth chart"></div><div class="panel"><h2>Risk / return</h2><img src="{images['risk_return.png']}" alt="Risk return chart"></div></div>
<div><div class="panel"><h2>Macro stress test · estimated one-period impact</h2>{html_table(scenario_display.set_index("Scenario"), percent_cols=[])}<div class="foot">Rate shocks use estimated gilt duration and a 4.5-year investment-grade bond assumption. Inflation and FX shocks are directional assumptions.</div></div><div class="panel"><h2>Rate sensitivity on a hypothetical £1m account</h2>{html_table(d.set_index("portfolio")[["gilt_modified_duration_years","gilt_dv01_gbp_per_bp","estimated_total_rate_dv01_gbp_per_bp"]])}<div class="foot">DV01 is the approximate £ change for a 1bp move, based on target weights; it is not a live risk number.</div></div><div class="panel"><h2>Diversification check</h2><img src="{images['correlation_heatmap.png']}" alt="Correlation heatmap"></div></div></div>
<div class="foot">Sources: Yahoo Finance adjusted monthly closes for proxy ETFs and GBP/USD; UK 10-year gilt yield is a transparent demonstration proxy included in the repository. See README and memo for methodology and suitability caveats.</div>
</main></body></html>'''
    (output_dir / "dashboard.html").write_text(html.replace("Jan 2014–Sep 2026", "Jan 2014 to Sep 2026"), encoding="utf-8")


def write_memo(output_dir: Path, metrics: pd.DataFrame, scenarios: pd.DataFrame, duration: pd.DataFrame, period: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> None:
    growth = metrics.loc["Growth"]
    balanced = metrics.loc["Balanced"]
    preserve = metrics.loc["Capital Preservation"]
    dur = duration.loc["Balanced"]
    scenario_text = scenarios.map(pct).to_html(classes="memo-table", border=0)
    period_text = period.reset_index().pivot(index="period", columns="portfolio", values="cumulative_return").map(pct).to_html(classes="memo-table", border=0)
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>Client Portfolio & Macro Scenario Memo</title><style>
@page {{ size:A4; margin:17mm 18mm; }} body {{ font-family:Georgia,serif; color:#202a3b; line-height:1.42; font-size:10.5pt; margin:0; }} h1 {{ font:800 22pt/1.1 Arial,sans-serif; letter-spacing:-.03em; margin:0 0 5px; }} h2 {{ font:800 13pt Arial,sans-serif; color:#3543a8; margin:18px 0 7px; }} h3 {{ font:800 10pt Arial,sans-serif; margin:12px 0 3px; }} .eyebrow {{ color:#4f46e5; font:800 8pt Arial,sans-serif; text-transform:uppercase; letter-spacing:.12em; }} .meta {{ font:9pt Arial,sans-serif; color:#67738b; margin:0 0 13px; }} .callout {{ border-left:4px solid #14b8a6; padding:8px 12px; background:#f1fbfa; font-family:Arial,sans-serif; font-size:9.5pt; }} .columns {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }} .portfolio {{ break-inside:avoid; }} table {{ width:100%; border-collapse:collapse; font:8.3pt Arial,sans-serif; margin:6px 0 8px; }} th {{ text-align:left; color:#66728a; border-bottom:1px solid #ccd4e3; padding:4px; }} td {{ border-bottom:1px solid #edf0f5; padding:4px; }} td:not(:first-child),th:not(:first-child) {{ text-align:right; }} .pagebreak {{ page-break-before:always; }} .small {{ font-size:8.5pt; color:#68748a; }} ul {{ margin-top:5px; padding-left:18px; }} li {{ margin-bottom:3px; }} .signature {{ margin-top:14px; font:9pt Arial,sans-serif; color:#516078; }} </style></head><body>
<div class="eyebrow">Illustrative wealth-management case study</div><h1>Client Portfolio & Macro Scenario Memo</h1><p class="meta">Prepared 13 September 2026 · Historical proxy sample: {start:%b %Y} to {end:%b %Y}</p>
<div class="callout"><strong>Executive view.</strong> The three portfolios express different trade-offs between long-term growth, drawdown tolerance and near-term liquidity. The Growth allocation has the highest expected variability; Capital Preservation gives up upside to reduce equity risk and preserve optionality. these are fictional portfolios for education, not recommendations.</div>
<h2>1. What each client is trying to achieve</h2><div class="columns"><div class="portfolio"><h3>Growth-focused · 20-year horizon</h3><p>Seeks real capital growth over a long runway and can accept interim losses. A 60% equity allocation, plus gold and a small FX sleeve, makes the portfolio the most exposed to global risk assets and the most able to recover from short-term volatility.</p></div><div class="portfolio"><h3>Balanced · 10-year horizon</h3><p>Seeks a compromise between growth and capital stability. A 35% equity allocation is paired with 45% gilts and investment-grade bonds, 10% cash, and diversifiers. it is intended for a client who values progress but cannot ignore medium-term drawdowns.</p></div><div class="portfolio"><h3>Capital Preservation · 5-year horizon and liquidity needs</h3><p>Prioritises avoiding forced sales and funding known or plausible withdrawals. The 60% gilt, investment-grade bond and cash allocation provides a larger liquidity and ballast reserve, while a modest 13% equity allocation retains some inflation-fighting growth potential.</p></div></div>
<h2>2. Why the allocations fit the stated objectives</h2><p>Gilts and investment-grade bonds provide contractual-income and duration exposure; cash addresses immediate spending and rebalancing needs; equities provide long-run growth; gold is a diversifier in inflation or confidence shocks; and the small USD-oriented sleeve can help when sterling weakens. The structure is deliberately simple enough to explain to a client and transparent enough to challenge.</p>
<table class="memo-table"><tr><th>Portfolio</th><th>Ann. return</th><th>Ann. vol.</th><th>Sharpe</th><th>Max drawdown</th></tr>{''.join(f'<tr><td>{n}</td><td>{pct(metrics.loc[n,"annualised_return"])}</td><td>{pct(metrics.loc[n,"annualised_volatility"])}</td><td>{metrics.loc[n,"sharpe_ratio"]:.2f}</td><td>{pct(metrics.loc[n,"max_drawdown"])}</td></tr>' for n in metrics.index)}</table>
<p class="small">Statistics are backward-looking and based on monthly proxy total returns. Annualisation can make a short or regime-specific sample look more precise than it is.</p>
<div class="pagebreak"></div><div class="eyebrow">Client implications</div><h1>Risks, scenarios & suitability questions</h1>
<h2>3. Main risks and trade-offs</h2><div class="columns"><div><ul><li><strong>Market risk:</strong> equities can fall sharply and may remain below prior peaks; the Growth portfolio has the largest loss capacity requirement.</li><li><strong>Duration risk:</strong> rate rises reduce gilt and bond prices. The Balanced portfolio has an estimated gilt sleeve DV01 of {gbp(dur['gilt_dv01_gbp_per_bp'])} per bp on £1m.</li><li><strong>Inflation risk:</strong> nominal bonds and cash may lose purchasing power when inflation rises faster than yields.</li></ul></div><div><ul><li><strong>Credit and liquidity:</strong> investment-grade is not risk-free, and ETF prices can gap or trade wide in stress.</li><li><strong>Currency risk:</strong> overseas assets and the FX sleeve create GBP outcomes that differ from local-market returns.</li><li><strong>Model risk:</strong> proxies, fixed weights, a constant risk-free assumption and one-period shocks simplify reality.</li></ul></div></div>
<h2>4. How the portfolios behave under requested scenarios</h2>{scenario_text}<p class="small">Positive values indicate estimated gains; negative values indicate estimated losses. "Rates +100bp" uses duration-based price sensitivity, while the inflation and currency cases apply transparent directional sleeve shocks.</p>
<h2>5. Historical period comparison</h2>{period_text}<p class="small">The period table shows cumulative outcomes, not a claim that any regime will repeat. COVID shock is February to April 2020; Rates & inflation is January 2022 to December 2023; recent begins January 2024.</p>
<h2>6. What we would need before making a real recommendation</h2><p>We would first establish the client's objectives and success measures, spending and withdrawal schedule, income stability, liabilities, emergency reserve, tax residence and wrapper, existing assets, loss capacity, loss tolerance, investment experience, horizon certainty, liquidity constraints, ethical or ESG preferences, currency commitments, concentration risks, capacity for complexity and any restrictions. We would then test the proposed strategy against cash-flow scenarios, fees, taxes, inflation and a documented rebalancing plan, and confirm that the client understands the possibility of loss.</p>
    <p class="signature"><strong>Conclusion:</strong> The framework helps structure a client conversation because it makes the allocation, risk budget and scenario trade-offs visible. It is not a substitute for regulated advice, approved instruments, verified data or a formal suitability assessment.</p>
</body></html>'''
    (output_dir / "client_memo.html").write_text(html, encoding="utf-8")


def main() -> int:
    raw_dir = ROOT / "data" / "raw"
    output_dir = ROOT / "outputs"
    figure_dir = ROOT / "reports" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    prices = pd.read_csv(raw_dir / "market_data_monthly.csv")
    yields = pd.read_csv(raw_dir / "yields_monthly.csv", parse_dates=["date"]).set_index("date")["uk_10y_gilt_yield_pct"]
    clean = clean_monthly_prices(prices)
    returns = monthly_returns(clean)
    metrics = performance_metrics(returns)
    p_metrics = portfolio_metrics(returns)
    p_returns = pd.DataFrame({name: returns[list(weights)].mul(pd.Series(weights)).sum(axis=1) for name, weights in PORTFOLIOS.items()})
    duration = estimate_gilt_duration(returns["uk_gilts"], yields)
    duration_df = duration_table(duration)
    scenarios = scenario_table(duration.modified_duration)
    periods = period_table(returns)
    clean.reset_index().to_csv(output_dir / "clean_prices.csv", index=False, float_format="%.8f")
    metrics.reset_index().to_csv(output_dir / "asset_metrics.csv", index=False, float_format="%.8f")
    p_metrics.to_csv(output_dir / "portfolio_metrics.csv", float_format="%.8f")
    returns.corr().rename(index=DISPLAY_NAMES, columns=DISPLAY_NAMES).to_csv(output_dir / "correlation_matrix.csv", float_format="%.4f")
    duration_df.to_csv(output_dir / "duration_dv01.csv", float_format="%.4f")
    scenarios.to_csv(output_dir / "scenario_analysis.csv", float_format="%.6f")
    periods.to_csv(output_dir / "period_comparison.csv", float_format="%.6f")
    weights = pd.DataFrame(PORTFOLIOS).T.rename(columns=DISPLAY_NAMES)
    weights.to_csv(output_dir / "portfolio_weights.csv", float_format="%.4f")
    make_figures(returns, p_returns, p_metrics, figure_dir)
    write_dashboard(ROOT / "reports", p_metrics, scenarios, duration_df, figure_dir, clean.index.min(), clean.index.max())
    write_memo(ROOT / "reports", p_metrics, scenarios, duration_df, periods, clean.index.min(), clean.index.max())
    print(f"Analysed {len(clean):,} monthly observations ({clean.index.min():%b %Y} to {clean.index.max():%b %Y}).")
    print(f"Estimated gilt modified duration: {duration.modified_duration:.2f} years; DV01 on £1m gilt sleeve: £{duration.dv01_per_million:,.0f} per bp.")
    print("Wrote tables to outputs/ and dashboard/memo to reports/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
