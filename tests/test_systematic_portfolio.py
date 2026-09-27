import numpy as np
import pandas as pd

from catl_quant.systematic_portfolio import (
    _apply_turnover_and_capacity,
    _project_score_tilt,
    run_long_only_backtest,
    transaction_cost_breakdown,
)


def test_score_tilt_is_fully_invested_and_group_neutral() -> None:
    symbols = [f"{idx:06d}" for idx in range(6)]
    benchmark = pd.Series([1 / 6] * 6, index=symbols)
    score = pd.Series([-2, -1, 0, 1, 2, 3], index=symbols)
    groups = pd.Series(["a", "a", "a", "b", "b", "b"], index=symbols)
    result = _project_score_tilt(
        benchmark,
        score,
        groups,
        score_tilt=0.3,
        max_weight=0.30,
        max_active_weight=0.10,
    )
    assert np.isclose(result.sum(), 1.0)
    assert np.isclose(result.loc[groups.eq("a")].sum(), 0.5)
    assert result.loc["000005"] > result.loc["000003"]


def test_turnover_cap_scales_whole_trade_vector() -> None:
    target = pd.Series([0.8, 0.2], index=["a", "b"])
    current = pd.Series([0.2, 0.8], index=["a", "b"])
    implemented, desired, actual = _apply_turnover_and_capacity(
        target,
        current,
        pd.Series([1e12, 1e12], index=["a", "b"]),
        turnover_cap=0.25,
        aum_rmb=1e8,
        max_adv_participation=0.05,
    )
    assert np.isclose(desired, 0.6)
    assert np.isclose(actual, 0.25)
    assert np.isclose(implemented.sum(), 1.0)


def test_costs_increase_with_multiplier_and_include_sell_tax() -> None:
    trades = pd.Series({"buy": 0.1, "sell": -0.1})
    adv = pd.Series({"buy": 1e9, "sell": 1e9})
    vol = pd.Series({"buy": 0.02, "sell": 0.02})
    config = {
        "commission_bps_each_side": 3.0,
        "spread_bps_each_side": 5.0,
        "stamp_duty_sell_bps_before_2023_08_28": 10.0,
        "stamp_duty_sell_bps_from_2023_08_28": 5.0,
        "market_impact_eta": 0.25,
    }
    base = transaction_cost_breakdown(trades, adv, vol, pd.Timestamp("2024-01-31"), config, aum_rmb=1e8)
    high = transaction_cost_breakdown(
        trades,
        adv,
        vol,
        pd.Timestamp("2024-01-31"),
        config,
        aum_rmb=1e8,
        multiplier=2.0,
    )
    assert base["stamp_duty_cost"] > 0
    assert np.isclose(high["total_cost"], 2 * base["total_cost"])


def test_universe_exit_is_sold_costed_and_carried_through_nav() -> None:
    panel_rows: list[dict[str, object]] = []
    months = [
        ("2024-01-31", "2024-01-30", {"A": 0.0, "B": 0.0}),
        ("2024-02-29", "2024-02-28", {"B": 0.10, "C": 0.0}),
        ("2024-03-29", "2024-03-28", {"B": 0.0, "C": 0.0}),
    ]
    for execution, signal, returns in months:
        for symbol, forward_return in returns.items():
            panel_rows.append(
                {
                    "execution_date": execution,
                    "signal_date": signal,
                    "symbol": symbol,
                    "benchmark_weight": 0.5,
                    "composite_score": 0.0,
                    "forward_return": forward_return,
                    "market_beta_126d": 1.0,
                    "adv20_rmb": 1e12,
                    "volatility_63d": 0.02,
                    "industry_group": "battery",
                    "research_split": "final_holdout",
                }
            )
    panel = pd.DataFrame.from_records(panel_rows)

    dates = pd.bdate_range("2023-01-02", "2024-03-28")
    market_rows: list[dict[str, object]] = []
    for offset, symbol in enumerate(["A", "B", "C"]):
        prices = (10 + offset) * np.cumprod(1 + 0.001 * np.sin(np.arange(len(dates)) / 13 + offset))
        for date, close in zip(dates, prices, strict=True):
            market_rows.append({"date": date, "symbol": symbol, "close_adj": close})
    market = pd.DataFrame.from_records(market_rows)

    portfolio_config = {
        "score_tilt": 0.35,
        "max_weight": 0.80,
        "max_active_weight": 0.40,
        "max_active_beta": 1.0,
        "annualized_tracking_error_cap": 1.0,
        "covariance_lookback_days": 126,
        "covariance_diagonal_shrinkage": 0.35,
        "monthly_one_way_turnover_cap": 1.0,
        "min_holdings": 2,
        "aum_rmb": 1e8,
        "max_adv_participation": 0.05,
    }
    cost_config = {
        "commission_bps_each_side": 0.0,
        "spread_bps_each_side": 0.0,
        "stamp_duty_sell_bps_before_2023_08_28": 10.0,
        "stamp_duty_sell_bps_from_2023_08_28": 5.0,
        "market_impact_eta": 0.0,
    }
    result = run_long_only_backtest(panel, market, portfolio_config, cost_config)

    february = result.monthly_returns.loc[
        result.monthly_returns["execution_date"].eq(pd.Timestamp("2024-02-29"))
    ].iloc[0]
    february_trades = result.trades.loc[
        result.trades["execution_date"].eq(pd.Timestamp("2024-02-29"))
    ].set_index("symbol")
    february_weights = result.weights.loc[
        result.weights["execution_date"].eq(pd.Timestamp("2024-02-29"))
    ].set_index("symbol")

    # A left the universe but remains in both ledgers as an explicit full sale.
    np.testing.assert_allclose(february_trades.loc["A", "trade_weight"], -0.5)
    assert bool(february_trades.loc["A", "forced_exit"])
    assert bool(february_weights.loc["A", "forced_exit"])
    np.testing.assert_allclose(february_weights.loc["A", "implemented_weight"], 0.0)
    np.testing.assert_allclose(february["forced_exit_sell_weight"], 0.5)
    assert february["forced_exit_count"] == 1

    # Replacing A with C trades one full portfolio weight gross, which is 50%
    # under the documented half-L1 one-way-turnover convention.
    np.testing.assert_allclose(february["gross_traded_weight"], 1.0, atol=1e-10)
    np.testing.assert_allclose(february["implemented_one_way_turnover"], 0.5, atol=1e-10)
    assert february["stamp_duty_cost"] > 0
    assert february["strategy_net_return"] < february["strategy_gross_return"]
    np.testing.assert_allclose(
        february["post_trade_risky_weight"] + february["cash_weight"] + february["total_cost"],
        1.0,
        atol=1e-10,
    )

    # February's unequal asset returns drift the weights carried into March;
    # they are not reset to benchmark before the next rebalance.
    march_weights = result.weights.loc[
        result.weights["execution_date"].eq(pd.Timestamp("2024-03-29"))
    ].set_index("symbol")
    assert march_weights.loc["B", "pre_trade_weight"] > 0.52
    assert march_weights.loc["C", "pre_trade_weight"] < 0.48

    all_summary = result.summary.loc[result.summary["research_split"].eq("all")].iloc[0]
    np.testing.assert_allclose(
        all_summary["total_cost_arithmetic"], result.monthly_returns["total_cost"].sum()
    )
    assert all_summary["months_with_forced_exits"] == 1
    np.testing.assert_allclose(all_summary["total_forced_exit_sell_weight"], 0.5)
