import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from catl_quant.systematic_pipeline import run_systematic_pipeline


def _write_project(root: Path) -> Path:
    (root / "config").mkdir(parents=True)
    (root / "data" / "raw").mkdir(parents=True)
    (root / "data" / "manual").mkdir(parents=True)
    dates = pd.bdate_range("2020-01-02", "2024-12-31")
    symbols = [f"00000{index}" for index in range(1, 7)]
    market_rows = []
    benchmark_return = 0.0002 + np.sin(np.arange(len(dates)) / 17) * 0.001
    for index, symbol in enumerate([*symbols, "510300"]):
        daily = benchmark_return if symbol == "510300" else benchmark_return + (index - 2) * 0.00003
        close = (10 + index) * np.cumprod(1 + daily)
        for date, value in zip(dates, close, strict=True):
            market_rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "close_adjusted": value,
                    "close_raw": value,
                    "high_raw": value * 1.01,
                    "low_raw": value * 0.99,
                    "volume_raw": 10_000_000 + index * 1_000_000,
                }
            )
    pd.DataFrame(market_rows).to_parquet(root / "data" / "raw" / "systematic_market_daily.parquet", index=False)

    fundamentals = []
    for index, symbol in enumerate(symbols):
        for year in range(2019, 2025):
            scale = 1 + index * 0.05 + (year - 2019) * 0.03
            fundamentals.append(
                {
                    "symbol": symbol,
                    "report_date": f"{year}-12-31",
                    "notice_date": f"{year + 1}-03-15",
                    "available_date": f"{year + 1}-03-15",
                    "report_type": "年报",
                    "revenue": 100 * scale,
                    "revenue_yoy_pct": 5 + index,
                    "net_profit": 10 * scale,
                    "net_profit_yoy_pct": 4 + index,
                    "roe_pct": 10 + index,
                    "gross_margin_pct": 20 + index,
                    "net_margin_pct": 8 + index,
                    "debt_ratio_pct": 50 - index,
                }
            )
    pd.DataFrame(fundamentals).to_parquet(
        root / "data" / "raw" / "systematic_fundamentals_pit.parquet", index=False
    )
    membership = pd.DataFrame(
        {
            "fund_symbol": "561910",
            "snapshot_date": pd.Timestamp("2019-12-31"),
            "available_date": pd.Timestamp("2020-03-31"),
            "year": 2019,
            "quarter": 4,
            "symbol": symbols,
            "name": [f"Company {index}" for index in range(6)],
            "weight_pct": [100 / 6] * 6,
            "rank": list(range(1, 7)),
        }
    )
    membership.to_parquet(root / "data" / "raw" / "systematic_membership.parquet", index=False)
    pd.DataFrame(
        {
            "symbol": symbols,
            "industry_group": ["cell"] * 3 + ["materials"] * 3,
            "include": [True, True, True, True, True, False],
        }
    ).to_csv(root / "data" / "manual" / "systematic_industry_groups.csv", index=False)

    config = {
        "project": {
            "title": "Test Systematic Research",
            "research_type": "test",
            "research_as_of": "2024-12-31",
            "market_data_start": "2020-01-01",
            "random_seed": 1,
        },
        "universe": {
            "benchmark_symbol": "510300",
            "min_price_history_days": 252,
            "min_cross_section": 3,
            "min_adv20_rmb": 1,
        },
        "features": {
            "momentum_12_1_long_days": 252,
            "momentum_12_1_skip_days": 21,
            "momentum_6_1_long_days": 126,
            "volatility_days": 63,
            "beta_days": 126,
            "liquidity_days": 20,
            "mad_clip": 5.0,
            "min_family_coverage": 0.5,
            "min_composite_families": 3,
            "family_weights": {
                "price_momentum": 0.25,
                "operating_quality": 0.25,
                "fundamental_momentum": 0.25,
                "low_risk": 0.25,
            },
        },
        "evaluation": {
            "forward_horizon_months": 1,
            "quantiles": 3,
            "hac_lags": 2,
            "design_end": "2022-06-30",
            "validation_end": "2023-06-30",
            "final_holdout_end": "2024-12-31",
        },
        "portfolio": {
            "score_tilt": 0.2,
            "max_weight": 0.4,
            "max_active_weight": 0.1,
            "max_active_beta": 0.2,
            "annualized_tracking_error_cap": 0.2,
            "covariance_lookback_days": 126,
            "covariance_diagonal_shrinkage": 0.35,
            "monthly_one_way_turnover_cap": 0.3,
            "min_holdings": 3,
            "aum_rmb": 1_000_000,
            "max_adv_participation": 0.1,
        },
        "transaction_costs": {
            "commission_bps_each_side": 3.0,
            "spread_bps_each_side": 5.0,
            "stamp_duty_sell_bps_before_2023_08_28": 10.0,
            "stamp_duty_sell_bps_from_2023_08_28": 5.0,
            "market_impact_eta": 0.01,
            "cost_sensitivity_multipliers": [0.5, 1.0, 2.0],
        },
        "disclosures": ["Synthetic integration test."],
    }
    config_path = root / "config" / "systematic.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def test_pipeline_writes_reproducible_split_and_cost_outputs(tmp_path) -> None:
    config_path = _write_project(tmp_path)
    first = run_systematic_pipeline(config_path)
    summary_path = tmp_path / "reports" / "systematic_summary.json"
    first_bytes = summary_path.read_bytes()
    second = run_systematic_pipeline(config_path)

    assert first == second
    assert summary_path.read_bytes() == first_bytes
    assert (tmp_path / "data" / "processed" / "systematic_monthly_panel.parquet").exists()
    assert (tmp_path / "reports" / "generated" / "systematic_research_report.md").exists()
    assert (tmp_path / "reports" / "tables" / "systematic_monthly_ic.csv").exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert {row["research_split"] for row in summary["time_splits"]["counts"]} == {
        "design",
        "validation",
        "final_holdout",
    }
    assert {row["cost_multiplier"] for row in summary["portfolio_cost_sensitivity"]} == {
        0.5,
        1.0,
        2.0,
    }
    panel = pd.read_parquet(tmp_path / "data" / "processed" / "systematic_monthly_panel.parquet")
    assert panel["composite_score"].notna().any()
    assert set(panel["industry_group"]) == {"cell", "materials"}
    assert "000006" not in set(panel["symbol"])
    assert summary["industry_groups"]["excluded_symbols"] == ["000006"]
    assert panel["financial_effective_date"].dropna().le(panel.loc[panel["financial_effective_date"].notna(), "signal_date"]).all()
