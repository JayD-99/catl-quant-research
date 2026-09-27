import json

import numpy as np
import pandas as pd

from catl_quant.systematic_data import (
    build_source_record,
    dataframe_sha256,
    download_eastmoney_fundamentals,
    download_etf_membership_snapshots,
    download_tencent_ohlcv,
    download_yfinance_ohlcv,
    membership_union_symbols,
    write_source_manifest,
)


def test_membership_keeps_q2_q4_top_50_and_conservative_dates() -> None:
    def provider(*, symbol: str, date: str) -> pd.DataFrame:
        assert symbol == "561910"
        year = int(date)
        rows = []
        for quarter in [1, 2, 4]:
            for rank in range(1, 56):
                rows.append(
                    {
                        "股票代码": str(rank),
                        "股票名称": f"Company {rank}",
                        "占净值比例": f"{100-rank}%",
                        "季度": f"{year}年{quarter}季度股票投资明细",
                    }
                )
        return pd.DataFrame(rows)

    result = download_etf_membership_snapshots(
        years=[2024, 2025], provider=provider, sleep_fn=lambda _: None
    )

    assert set(zip(result["year"], result["quarter"])) == {(2024, 2), (2024, 4), (2025, 2)}
    assert result.groupby(["year", "quarter"]).size().eq(50).all()
    assert result.loc[result["quarter"].eq(2), "available_date"].dt.strftime("%m-%d").eq("08-29").all()
    assert result.loc[result["quarter"].eq(4), "available_date"].iloc[0] == pd.Timestamp("2025-03-31")
    assert result.loc[result["rank"].eq(1), "symbol"].eq("000001").all()
    assert membership_union_symbols(result)[:2] == ["000001", "000002"]


def _fake_yahoo_frame(tickers: list[str], adjusted: bool) -> pd.DataFrame:
    dates = pd.to_datetime(["2025-08-28", "2025-08-29", "2025-08-30"])
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"] + ([] if adjusted else ["Adj Close"]), tickers]
    )
    data = np.empty((len(dates), len(columns)))
    for column_index, (field, _) in enumerate(columns):
        base = {"Open": 10, "High": 12, "Low": 9, "Close": 11, "Volume": 1000, "Adj Close": 10}[field]
        data[:, column_index] = base * (0.5 if adjusted and field != "Volume" else 1.0)
    return pd.DataFrame(data, index=pd.Index(dates, name="Date"), columns=columns)


def test_yahoo_download_is_batched_long_and_retains_raw_adjusted() -> None:
    calls: list[tuple[tuple[str, ...], bool]] = []

    def provider(**kwargs) -> pd.DataFrame:
        tickers = list(kwargs["tickers"])
        calls.append((tuple(tickers), bool(kwargs["auto_adjust"])))
        return _fake_yahoo_frame(tickers, bool(kwargs["auto_adjust"]))

    result = download_yfinance_ohlcv(
        ["1", "600000", "300750"], batch_size=2, provider=provider, sleep_fn=lambda _: None
    )

    assert len(calls) == 4
    assert set(result["symbol"]) == {"000001", "300750", "600000"}
    assert result["date"].max() == pd.Timestamp("2025-08-29")
    assert len(result) == 6
    assert result["close_raw"].eq(11).all()
    assert result["close_adjusted"].eq(5.5).all()
    assert result["adjustment_factor"].eq(0.5).all()


def test_fundamentals_retry_and_cutoff_keep_notice_date() -> None:
    attempts = {"count": 0}

    def provider(*, symbol: str, indicator: str) -> pd.DataFrame:
        assert symbol == "000001.SZ"
        assert indicator == "按报告期"
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionError("temporary")
        return pd.DataFrame(
            {
                "REPORT_DATE": ["2025-06-30", "2025-09-30"],
                "NOTICE_DATE": ["2025-08-20", "2025-10-30"],
                "REPORT_TYPE": ["中报", "三季报"],
                "TOTALOPERATEREVE": [100.0, 160.0],
                "TOTALOPERATEREVETZ": [10.0, 12.0],
                "PARENTNETPROFIT": [20.0, 30.0],
                "PARENTNETPROFITTZ": [5.0, 7.0],
                "ROEJQ": [8.0, 9.0],
                "XSMLL": [30.0, 31.0],
                "XSJLL": [20.0, 19.0],
                "ZCFZL": [40.0, 41.0],
            }
        )

    result = download_eastmoney_fundamentals(
        ["1"], provider=provider, sleep_fn=lambda _: None, attempts=2
    )

    assert attempts["count"] == 2
    assert result["symbol"].tolist() == ["000001"]
    assert result["notice_date"].tolist() == [pd.Timestamp("2025-08-20")]
    assert result["available_date"].equals(result["notice_date"])
    assert result["report_type"].tolist() == ["中报"]


def test_tencent_fallback_aligns_raw_and_back_adjusted_prices() -> None:
    calls: list[tuple[str, str]] = []

    def provider(**kwargs) -> pd.DataFrame:
        calls.append((kwargs["symbol"], kwargs["adjust"]))
        multiplier = 10.0 if kwargs["adjust"] == "hfq" else 1.0
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-08-28", "2025-08-29", "2025-08-30"]),
                "open": [1.0, 1.1, 1.2],
                "close": np.array([1.1, 1.2, 1.3]) * multiplier,
                "high": np.array([1.2, 1.3, 1.4]) * multiplier,
                "low": np.array([0.9, 1.0, 1.1]) * multiplier,
                "volume": [1000.0, 1100.0, 1200.0],
            }
        )

    result = download_tencent_ohlcv(
        ["300116"], provider=provider, sleep_fn=lambda _: None
    )

    assert calls == [("sz300116", ""), ("sz300116", "hfq")]
    assert result["date"].max() == pd.Timestamp("2025-08-29")
    assert result["close_raw"].tolist() == [1.1, 1.2]
    assert result["close_adjusted"].tolist() == [11.0, 12.0]
    assert result["adjustment_factor"].eq(10.0).all()


def test_manifest_hash_is_order_independent_and_mergeable(tmp_path) -> None:
    frame = pd.DataFrame(
        {"symbol": ["000002", "000001"], "date": pd.to_datetime(["2025-01-02", "2025-01-01"])}
    )
    shuffled = frame.iloc[::-1].reset_index(drop=True)
    assert dataframe_sha256(frame) == dataframe_sha256(shuffled)

    record = build_source_record(
        frame,
        provider="test provider",
        parameters={"cutoff": "2025-08-29"},
        retrieved_at_utc="2025-08-30T00:00:00+00:00",
    )
    path = tmp_path / "source_manifest.json"
    write_source_manifest(path, {"membership": record})
    write_source_manifest(path, {"market": {"provider": "test market"}})
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["sources"]["membership"]["dataframe_sha256"] == dataframe_sha256(frame)
    assert manifest["sources"]["membership"]["rows"] == 2
    assert manifest["sources"]["market"]["provider"] == "test market"
