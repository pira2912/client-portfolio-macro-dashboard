#!/usr/bin/env python3
"""Refresh the bundled monthly market data."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portfolio_dashboard.data import build_market_data  # noqa: E402


def main() -> int:
    target = ROOT / "data" / "raw"
    target.mkdir(parents=True, exist_ok=True)
    try:
        prices, yields, source = build_market_data()
    except Exception as exc:  # preserve the bundled data when a feed is unavailable
        print(f"Data refresh skipped: {exc}")
        print("The repository already contains a validated bundled CSV snapshot.")
        return 0
    prices.to_csv(target / "market_data_monthly.csv", index=False, float_format="%.8f")
    yields.to_csv(target / "yields_monthly.csv", index=False, float_format="%.6f")
    (target / "data_source.txt").write_text(source + "\n", encoding="utf-8")
    print(f"Wrote {len(prices):,} monthly observations to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
