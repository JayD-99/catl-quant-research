from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd
import yfinance as yf

from .config import ResearchConfig
from .io import update_manifest, write_frame


def _normalize_market_frame(frame: pd.DataFrame, symbol: str, name: str, segment: str) -> pd.DataFrame:
    rename = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    frame = frame.rename(columns=rename).copy()
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{symbol} missing market columns: {missing}")
    keep = required + (["amount"] if "amount" in frame.columns else [])
    frame = frame[keep]
    frame["date"] = pd.to_datetime(frame["date"])
    for column in [c for c in keep if c != "date"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["symbol"] = symbol
    frame["name"] = name
    frame["segment"] = segment
    return frame.sort_values("date").drop_duplicates(["date", "symbol"])


def _yahoo_ticker(symbol: str) -> str:
    if "." in symbol:
        return symbol
    return f"{symbol}.SS" if symbol.startswith(("5", "6", "9")) else f"{symbol}.SZ"


def _eastmoney_secucode(symbol: str) -> str:
    return f"{symbol}.SH" if symbol.startswith(("5", "6", "9")) else f"{symbol}.SZ"


def _download_yahoo(symbol: str, start: str, end: str) -> pd.DataFrame:
    end_exclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    frame = yf.download(
        _yahoo_ticker(symbol),
        start=pd.Timestamp(start).strftime("%Y-%m-%d"),
        end=end_exclusive,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if frame.empty:
        return frame
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.reset_index().rename(
        columns={"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )
    return frame[["date", "open", "high", "low", "close", "volume"]]


def _download_a_share_with_fallback(symbol: str, start: str, end: str) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            frame = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust="qfq",
                timeout=30,
            )
            if not frame.empty:
                return frame, "Eastmoney via AkShare"
        except Exception as exc:
            last_error = exc
            time.sleep(1.0 * (attempt + 1))
    frame = _download_yahoo(symbol, start, end)
    if frame.empty:
        raise RuntimeError(f"Both Eastmoney and Yahoo failed for {symbol}") from last_error
    return frame, "Yahoo Finance fallback"


def download_market_data(config: ResearchConfig) -> pd.DataFrame:
    project = config.raw["project"]
    market = config.raw["market"]
    start = str(project["market_data_start"])
    end = str(project["research_as_of"])

    securities = [market["focal"], *market["core_peers"], *market["value_chain"]]
    frames: list[pd.DataFrame] = []
    providers: dict[str, str] = {}
    for security in securities:
        raw, provider = _download_a_share_with_fallback(str(security["symbol"]), start, end)
        providers[str(security["symbol"])] = provider
        frames.append(
            _normalize_market_frame(raw, str(security["symbol"]), str(security["name"]), str(security["segment"]))
        )
        time.sleep(0.15)

    benchmark = market["benchmark"]
    try:
        raw_index = ak.stock_zh_index_daily_em(
            symbol=str(benchmark["symbol"]), start_date=start.replace("-", ""), end_date=end.replace("-", "")
        )
        if raw_index.empty:
            raise RuntimeError("empty benchmark response")
        providers[str(benchmark["symbol"])] = "Eastmoney index via AkShare"
    except Exception:
        raw_index = _download_yahoo(str(benchmark["yahoo_fallback"]), start, end)
        providers[str(benchmark["symbol"])] = "Yahoo Finance CSI 300 ETF fallback"
    frames.append(_normalize_market_frame(raw_index, str(benchmark["symbol"]), str(benchmark["name"]), "market"))

    panel = pd.concat(frames, ignore_index=True)
    cutoff = pd.Timestamp(config.as_of)
    panel = panel.loc[panel["date"] <= cutoff].copy()
    path = config.root / "data" / "raw" / "market_daily.parquet"
    write_frame(panel, path)
    update_manifest(
        config.root,
        "market_daily",
        {
            "provider": "Eastmoney via AkShare with Yahoo Finance per-symbol fallback",
            "url": "https://quote.eastmoney.com/center/",
            "as_of": config.as_of,
            "rows": int(len(panel)),
            "symbols": sorted(panel["symbol"].unique().tolist()),
            "providers_by_symbol": providers,
            "path": str(path.relative_to(config.root)),
        },
    )
    return panel


def _date_chunks(start: date, end: date, days: int = 10):
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def download_gfex_lithium(config: ResearchConfig) -> pd.DataFrame:
    start = pd.Timestamp(config.raw["project"]["lithium_data_start"])
    end = pd.Timestamp(config.as_of)
    raw = ak.futures_zh_daily_sina(symbol="LC0")
    if raw.empty:
        raise RuntimeError("No lithium-carbonate main-contract history returned for LC0")
    continuous = raw.rename(columns={"hold": "open_interest"}).copy()
    continuous["date"] = pd.to_datetime(continuous["date"])
    continuous = continuous.loc[continuous["date"].between(start, end)].copy()
    numeric = ["open", "high", "low", "close", "volume", "open_interest", "settle"]
    for column in numeric:
        continuous[column] = pd.to_numeric(continuous[column], errors="coerce")
    continuous["symbol"] = "LC0"
    continuous["variety"] = "LC"
    continuous["selection_rule"] = "sina_main_continuous"
    continuous = continuous.drop_duplicates("date").sort_values("date")

    continuous_path = config.root / "data" / "raw" / "gfex_lithium_continuous.parquet"
    write_frame(continuous, continuous_path)
    update_manifest(
        config.root,
        "gfex_lithium_carbonate",
        {
            "provider": "Sina main-continuous GFEX lithium-carbonate series via AkShare",
            "official_reference_url": "https://www.gfex.com.cn/en/MarketData/HistoricalData.shtml",
            "vendor_url": "https://finance.sina.com.cn/futures/quotes/LC0.shtml",
            "as_of": config.as_of,
            "rows_continuous": int(len(continuous)),
            "continuous_rule": "vendor main-continuous series; contract-level roll reconstruction is unavailable in the public baseline; regression-only outlier winsorization is recorded in build diagnostics",
            "path": str(continuous_path.relative_to(config.root)),
        },
    )
    return continuous


def download_peer_fundamentals(config: ResearchConfig) -> pd.DataFrame:
    market = config.raw["market"]
    securities = [market["focal"], *market["core_peers"], *market["value_chain"]]
    cutoff = pd.Timestamp(config.as_of)
    records: list[dict[str, object]] = []
    failures: dict[str, str] = {}
    for security in securities:
        symbol = str(security["symbol"])
        frame: pd.DataFrame | None = None
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                candidate = ak.stock_financial_analysis_indicator_em(
                    symbol=_eastmoney_secucode(symbol), indicator="按报告期"
                )
                if not candidate.empty:
                    frame = candidate
                    break
            except Exception as exc:
                last_error = exc
                time.sleep(1.0 * (attempt + 1))
        if frame is None:
            failures[symbol] = repr(last_error)
            continue

        frame = frame.copy()
        frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"])
        frame["NOTICE_DATE"] = pd.to_datetime(frame["NOTICE_DATE"])
        eligible = frame.loc[
            frame["REPORT_TYPE"].astype(str).eq("年报")
            & frame["NOTICE_DATE"].le(cutoff)
            & frame["REPORT_DATE"].le(cutoff)
        ].sort_values(["REPORT_DATE", "NOTICE_DATE"])
        if eligible.empty:
            failures[symbol] = "no point-in-time annual report before cutoff"
            continue
        eligible = eligible.loc[eligible["REPORT_DATE"].ge(pd.Timestamp("2022-12-31"))]
        for _, row in eligible.iterrows():
            records.append(
                {
                    "symbol": symbol,
                    "name": str(security["name"]),
                    "segment": str(security["segment"]),
                    "report_date": row["REPORT_DATE"],
                    "notice_date": row["NOTICE_DATE"],
                    "revenue": row.get("TOTALOPERATEREVE"),
                    "revenue_growth_pct": row.get("TOTALOPERATEREVETZ"),
                    "net_profit": row.get("PARENTNETPROFIT"),
                    "net_profit_growth_pct": row.get("PARENTNETPROFITTZ"),
                    "roe_pct": row.get("ROEJQ"),
                    "gross_margin_pct": row.get("XSMLL"),
                    "net_margin_pct": row.get("XSJLL"),
                    "debt_ratio_pct": row.get("ZCFZL"),
                }
            )
        time.sleep(0.15)

    fundamentals = pd.DataFrame.from_records(records)
    numeric = [
        "revenue",
        "revenue_growth_pct",
        "net_profit",
        "net_profit_growth_pct",
        "roe_pct",
        "gross_margin_pct",
        "net_margin_pct",
        "debt_ratio_pct",
    ]
    for column in numeric:
        fundamentals[column] = pd.to_numeric(fundamentals[column], errors="coerce")
    path = config.root / "data" / "raw" / "peer_fundamentals_point_in_time.parquet"
    write_frame(fundamentals, path)
    update_manifest(
        config.root,
        "peer_fundamentals",
        {
            "provider": "Eastmoney financial analysis via AkShare",
            "url": "https://emweb.securities.eastmoney.com/",
            "as_of": config.as_of,
            "rows": int(len(fundamentals)),
            "failures": failures,
            "point_in_time_rule": "annual reports from 2022 onward with notice_date on or before research cutoff",
            "path": str(path.relative_to(config.root)),
        },
    )
    return fundamentals


def download_all(config: ResearchConfig) -> None:
    download_market_data(config)
    download_gfex_lithium(config)
    download_peer_fundamentals(config)
