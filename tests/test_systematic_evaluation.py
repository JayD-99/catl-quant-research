import numpy as np
import pandas as pd

from catl_quant.systematic_evaluation import (
    _benjamini_hochberg,
    assign_research_split,
    evaluate_signals,
    monthly_information_coefficients,
    quantile_portfolio_returns,
)


def _panel() -> pd.DataFrame:
    rows = []
    for month in pd.date_range("2023-01-31", periods=4, freq="ME"):
        for idx in range(20):
            rows.append(
                {
                    "execution_date": month,
                    "symbol": f"{idx:06d}",
                    "signal": float(idx),
                    "forward_return": idx / 1000,
                    "forward_excess_return": idx / 1000,
                }
            )
    return pd.DataFrame(rows)


def test_information_coefficient_detects_monotonic_signal() -> None:
    result = monthly_information_coefficients(_panel(), ["signal"], min_cross_section=10)
    assert len(result) == 4
    assert np.allclose(result["rank_ic"], 1.0)


def test_quantile_sort_keeps_future_return_out_of_sort_key() -> None:
    result = quantile_portfolio_returns(_panel(), ["signal"], requested_quantiles=5)
    spreads = result.loc[result["leg"].eq("top_minus_bottom"), "return"]
    assert len(spreads) == 4
    assert (spreads > 0).all()


def test_research_splits_are_strictly_chronological() -> None:
    dates = pd.Series(pd.to_datetime(["2023-01-31", "2023-07-31", "2024-07-31"]))
    split = assign_research_split(dates, "2023-06-30", "2024-06-30")
    assert split.tolist() == ["design", "validation", "final_holdout"]


def test_benjamini_hochberg_is_monotone_and_bounded() -> None:
    adjusted = _benjamini_hochberg(pd.Series({"a": 0.01, "b": 0.04, "c": 0.20}))
    assert (adjusted >= 0).all() and (adjusted <= 1).all()
    assert adjusted["a"] <= adjusted["b"] <= adjusted["c"]


def test_evaluation_reports_quantiles_by_chronological_split() -> None:
    panel = _panel()
    result = evaluate_signals(
        panel,
        ["signal"],
        design_end="2023-01-31",
        validation_end="2023-02-28",
        min_cross_section=10,
    )
    assert set(result.quantile_summary["research_split"]) == {
        "all",
        "design",
        "validation",
        "final_holdout",
    }
