import pandas as pd
import pytest

from catl_quant.build import _assert_point_in_time, _zscore


def test_zscore_winsorizes_and_centers() -> None:
    scored = _zscore(pd.Series([1.0, 2.0, 3.0, 1000.0]))
    assert abs(scored.mean()) < 1e-12
    assert scored.notna().all()


def test_point_in_time_rejects_late_notice_date() -> None:
    market = pd.DataFrame({"date": pd.to_datetime(["2025-08-29"])})
    lithium = pd.DataFrame({"date": pd.to_datetime(["2025-08-29"])})
    fundamentals = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2024-12-31"]),
            "notice_date": pd.to_datetime(["2025-08-30"]),
        }
    )
    with pytest.raises(ValueError, match="notice"):
        _assert_point_in_time(market, lithium, fundamentals, pd.Timestamp("2025-08-29"))
