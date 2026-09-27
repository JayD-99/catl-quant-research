import numpy as np
import pandas as pd

from catl_quant.systematic_features import (
    FeatureConfig,
    build_monthly_systematic_features,
    cross_sectional_neutralize,
    robust_mad_zscore,
)


def _research_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2022-01-03", "2024-04-30")
    benchmark_returns = 0.0002 + 0.004 * np.sin(np.arange(len(dates)) / 9)
    return_map = {
        "BM": benchmark_returns,
        "A": 0.0003 + 1.5 * benchmark_returns,
        "B": -0.0001 + 0.7 * benchmark_returns + 0.001 * np.cos(np.arange(len(dates)) / 7),
        "C": 0.0002 + 1.1 * benchmark_returns - 0.001 * np.sin(np.arange(len(dates)) / 5),
        "D": 0.0001 + 0.9 * benchmark_returns + 0.0005 * np.cos(np.arange(len(dates)) / 11),
    }
    market_rows: list[dict[str, object]] = []
    for offset, (symbol, returns) in enumerate(return_map.items()):
        close = (20.0 + offset * 3) * np.cumprod(1 + returns)
        volume = np.full(len(dates), 1_000_000.0 * (offset + 1))
        for date, price, shares in zip(dates, close, volume, strict=True):
            market_rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "close_adj": price,
                    "close_raw": price,
                    "high_raw": price * 1.01,
                    "low_raw": price * 0.99,
                    "volume": shares,
                }
            )
    market = pd.DataFrame.from_records(market_rows)

    fundamental_rows: list[dict[str, object]] = []
    for idx, symbol in enumerate(["A", "B", "C", "D"]):
        scale = 1 + idx * 0.1
        for year, revenue, cogs, profit, cfo, assets, liabilities, notice in [
            (2021, 100.0, 60.0, 10.0, 11.0, 200.0, 90.0, "2022-03-15"),
            (2022, 110.0, 64.0, 11.0, 12.5, 220.0, 95.0, "2023-03-15"),
            (2023, 130.0, 70.0, 13.0, 15.0, 260.0, 100.0, "2024-02-15"),
        ]:
            fundamental_rows.append(
                {
                    "symbol": symbol,
                    "report_date": f"{year}-12-31",
                    "notice_date": notice,
                    "available_date": notice,
                    "revenue": revenue * scale,
                    "cost_of_goods_sold": cogs * scale,
                    "net_income": profit * scale,
                    "operating_cash_flow": cfo * scale,
                    "total_assets": assets * scale,
                    "total_liabilities": liabilities * scale,
                }
            )
    # A later vendor revision of the 2023 report must not enter before its own
    # available date even though its report and notice dates are unchanged.
    fundamental_rows.append(
        {
            "symbol": "A",
            "report_date": "2023-12-31",
            "notice_date": "2024-02-15",
            "available_date": "2024-03-15",
            "revenue": 9_999.0,
            "cost_of_goods_sold": 1.0,
            "net_income": 9_999.0,
            "operating_cash_flow": 9_999.0,
            "total_assets": 10_000.0,
            "total_liabilities": 1.0,
        }
    )
    fundamentals = pd.DataFrame.from_records(fundamental_rows)

    membership_rows: list[dict[str, object]] = []
    for symbol, group in [("A", "cell"), ("B", "cell"), ("C", "materials"), ("D", "materials")]:
        membership_rows.append(
            {
                "available_date": "2021-12-31",
                "snapshot_date": "2021-12-31",
                "symbol": symbol,
                "benchmark_weight": 0.25,
                "subindustry": group,
            }
        )
    # This snapshot is dated after January's signal and only becomes available
    # in February; D must therefore remain in January and leave in February.
    for symbol, group in [("A", "cell"), ("B", "cell"), ("C", "materials")]:
        membership_rows.append(
            {
                "available_date": "2024-02-15",
                "snapshot_date": "2024-01-31",
                "symbol": symbol,
                "benchmark_weight": 1 / 3,
                "subindustry": group,
            }
        )
    memberships = pd.DataFrame.from_records(membership_rows)
    return market, fundamentals, memberships


def _config() -> FeatureConfig:
    return FeatureConfig(min_cross_section=3, min_cross_section_coverage=0.50)


def test_monthly_timing_price_formulas_and_forward_label() -> None:
    market, fundamentals, memberships = _research_inputs()
    panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        config=_config(),
    )
    row = panel.loc[
        panel["execution_date"].eq(pd.Timestamp("2024-01-31")) & panel["symbol"].eq("A")
    ].iloc[0]
    assert row["signal_date"] == pd.Timestamp("2024-01-30")
    assert row["next_execution_date"] == pd.Timestamp("2024-02-29")

    security = market.loc[
        market["symbol"].eq("A") & market["date"].le(row["signal_date"])
    ].sort_values("date").copy()
    security["simple_return"] = security["close_adj"].pct_change(fill_method=None)
    expected_12_1 = np.log(security["close_adj"].iloc[-22] / security["close_adj"].iloc[-253])
    expected_6_1 = np.log(security["close_adj"].iloc[-22] / security["close_adj"].iloc[-127])
    expected_vol = security["simple_return"].dropna().tail(63).std(ddof=1) * np.sqrt(252)
    liquidity = security.tail(20)
    dollar_volume = liquidity["close_raw"] * liquidity["volume"]
    expected_adv = dollar_volume.mean()
    expected_amihud = (liquidity["simple_return"].abs() / dollar_volume).dropna().mean()

    np.testing.assert_allclose(row["momentum_12_1"], expected_12_1)
    np.testing.assert_allclose(row["momentum_6_1"], expected_6_1)
    np.testing.assert_allclose(row["volatility_3m"], expected_vol)
    np.testing.assert_allclose(row["adv_20d"], expected_adv)
    np.testing.assert_allclose(row["amihud_20d"], expected_amihud)

    start = market.loc[
        market["symbol"].eq("A") & market["date"].eq(pd.Timestamp("2024-01-31")), "close_adj"
    ].iloc[0]
    end = market.loc[
        market["symbol"].eq("A") & market["date"].eq(pd.Timestamp("2024-02-29")), "close_adj"
    ].iloc[0]
    np.testing.assert_allclose(row["forward_return_1m"], end / start - 1)


def test_six_month_beta_and_idiosyncratic_volatility_formula() -> None:
    market, fundamentals, memberships = _research_inputs()
    panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        config=_config(),
    )
    row = panel.loc[
        panel["execution_date"].eq(pd.Timestamp("2024-01-31")) & panel["symbol"].eq("A")
    ].iloc[0]
    # A was generated exactly as a constant plus 1.5 times benchmark returns.
    np.testing.assert_allclose(row["beta_6m"], 1.5, atol=1e-10)
    assert row["idio_volatility_6m"] < 1e-10
    assert row["beta_observations"] == 126


def test_future_prices_change_label_but_not_signal_features() -> None:
    market, fundamentals, memberships = _research_inputs()
    base = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        config=_config(),
    )
    changed_market = market.copy()
    execution_mask = changed_market["symbol"].eq("A") & changed_market["date"].eq(
        pd.Timestamp("2024-01-31")
    )
    changed_market.loc[execution_mask, "close_adj"] *= 2
    changed = build_monthly_systematic_features(
        changed_market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        config=_config(),
    )
    key = lambda frame: frame.loc[
        frame["execution_date"].eq(pd.Timestamp("2024-01-31")) & frame["symbol"].eq("A")
    ].iloc[0]
    before, after = key(base), key(changed)
    for feature in [
        "momentum_12_1",
        "momentum_6_1",
        "volatility_3m",
        "beta_6m",
        "idio_volatility_6m",
        "adv_20d",
        "amihud_20d",
    ]:
        np.testing.assert_allclose(before[feature], after[feature])
    assert before["forward_return_1m"] != after["forward_return_1m"]


def test_fundamentals_and_memberships_are_point_in_time() -> None:
    market, fundamentals, memberships = _research_inputs()
    panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        group_col="subindustry",
        config=_config(),
    )

    january = panel.loc[panel["execution_date"].eq(pd.Timestamp("2024-01-31"))]
    assert set(january["symbol"]) == {"A", "B", "C", "D"}
    january_a = january.loc[january["symbol"].eq("A")].iloc[0]
    assert january_a["financial_report_date"] == pd.Timestamp("2022-12-31")
    assert january_a["fin_revenue"] == 110.0
    assert january_a["financial_effective_date"] <= january_a["signal_date"]

    february = panel.loc[panel["execution_date"].eq(pd.Timestamp("2024-02-29"))]
    assert set(february["symbol"]) == {"A", "B", "C"}
    february_a = february.loc[february["symbol"].eq("A")].iloc[0]
    assert february_a["financial_report_date"] == pd.Timestamp("2023-12-31")
    assert february_a["fin_revenue"] == 130.0
    assert february_a["financial_effective_date"] == pd.Timestamp("2024-02-15")
    assert february_a["financial_effective_date"] <= february_a["signal_date"]

    expected_quality = np.mean([(130 - 70) / 260, -(13 - 15) / 260, -100 / 260])
    prior_quality = np.mean([(110 - 64) / 220, -(11 - 12.5) / 220, -95 / 220])
    expected_growth = np.mean([130 / 110 - 1, (13 - 11) / 220])
    np.testing.assert_allclose(february_a["quality_raw"], expected_quality)
    np.testing.assert_allclose(february_a["growth_raw"], expected_growth)
    np.testing.assert_allclose(
        february_a["fundamental_momentum_raw"], expected_quality - prior_quality
    )

    march_a = panel.loc[
        panel["execution_date"].eq(pd.Timestamp("2024-03-29")) & panel["symbol"].eq("A")
    ].iloc[0]
    assert march_a["fin_revenue"] == 9_999.0
    assert march_a["financial_effective_date"] == pd.Timestamp("2024-03-15")


def test_robust_scores_and_adv_group_neutralization() -> None:
    index = pd.RangeIndex(10)
    adv = pd.Series(np.exp(np.linspace(10, 15, 10)), index=index)
    groups = pd.Series(["cell"] * 5 + ["materials"] * 5, index=index)
    feature = 2.0 * np.log(adv) + groups.map({"cell": 3.0, "materials": -2.0})
    feature += pd.Series([0.1, -0.2, 0.15, -0.05, 0.0, -0.1, 0.2, -0.15, 0.05, 50.0])

    raw_score = robust_mad_zscore(feature)
    assert np.isfinite(raw_score).all()
    score = cross_sectional_neutralize(
        feature,
        adv,
        groups=groups,
        min_observations=6,
    )
    assert np.isfinite(score).all()
    np.testing.assert_allclose(score.mean(), 0.0, atol=1e-12)
    np.testing.assert_allclose(score.std(ddof=0), 1.0, atol=1e-12)
    np.testing.assert_allclose(np.dot(score, np.log(adv) - np.log(adv).mean()), 0.0, atol=1e-10)
    np.testing.assert_allclose(score.groupby(groups).mean().to_numpy(), 0.0, atol=1e-10)


def test_minimum_history_flags_early_months() -> None:
    market, fundamentals, memberships = _research_inputs()
    panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        config=_config(),
    )
    early = panel.sort_values("execution_date").iloc[0]
    assert not bool(early["price_history_ok"])
    assert not bool(early["minimum_history_ok"])
    assert not bool(early["eligible_for_scoring"])
    assert np.isnan(early["momentum_12_1"])


def test_additional_signal_lag_moves_information_date_not_return_window() -> None:
    market, fundamentals, memberships = _research_inputs()
    panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol="BM",
        config=FeatureConfig(
            min_cross_section=3,
            min_cross_section_coverage=0.50,
            signal_lag_trading_days=2,
        ),
    )
    row = panel.loc[
        panel["execution_date"].eq(pd.Timestamp("2024-01-31"))
        & panel["symbol"].eq("A")
    ].iloc[0]
    assert row["signal_date"] == pd.Timestamp("2024-01-29")
    assert row["next_execution_date"] == pd.Timestamp("2024-02-29")
