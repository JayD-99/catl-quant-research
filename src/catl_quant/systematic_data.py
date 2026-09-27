"""Point-in-time data adapters for the systematic-equity research extension.

The functions in this module deliberately stop at the data boundary.  They do
not create signals, portfolios, or backtests.  Every network-facing function
accepts an injectable provider so unit tests and institutional replacements do
not need to call the public endpoints.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import akshare as ak
import pandas as pd
import yaml
import yfinance as yf

from .io import write_frame


FrameProvider = Callable[..., pd.DataFrame]
SleepFunction = Callable[[float], None]

MEMBERSHIP_COLUMNS = [
    "fund_symbol",
    "snapshot_date",
    "available_date",
    "year",
    "quarter",
    "symbol",
    "name",
    "weight_pct",
    "rank",
]

MARKET_COLUMNS = [
    "date",
    "symbol",
    "yahoo_ticker",
    "open_raw",
    "high_raw",
    "low_raw",
    "close_raw",
    "volume_raw",
    "adj_close_vendor",
    "open_adjusted",
    "high_adjusted",
    "low_adjusted",
    "close_adjusted",
    "volume_adjusted",
    "adjustment_factor",
]

FUNDAMENTAL_COLUMNS = [
    "symbol",
    "report_date",
    "notice_date",
    "available_date",
    "report_type",
    "revenue",
    "revenue_yoy_pct",
    "net_profit",
    "net_profit_yoy_pct",
    "roe_pct",
    "gross_margin_pct",
    "net_margin_pct",
    "debt_ratio_pct",
]


def _call_with_retry(
    provider: FrameProvider,
    *,
    provider_name: str,
    attempts: int,
    backoff_seconds: float,
    sleep_fn: SleepFunction,
    kwargs: Mapping[str, Any],
) -> pd.DataFrame:
    """Call a tabular provider with bounded exponential backoff."""

    if attempts < 1:
        raise ValueError("attempts must be at least one")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            result = provider(**dict(kwargs))
            if not isinstance(result, pd.DataFrame):
                raise TypeError(f"{provider_name} returned {type(result)!r}, expected DataFrame")
            return result
        except Exception as exc:  # providers expose several network exception types
            last_error = exc
            if attempt + 1 < attempts:
                sleep_fn(backoff_seconds * (2**attempt))
    raise RuntimeError(f"{provider_name} failed after {attempts} attempts") from last_error


def _six_digit_symbol(value: object) -> str | None:
    match = re.search(r"(?<!\d)(\d{1,6})(?!\d)", str(value).strip())
    return match.group(1).zfill(6) if match else None


def _first_present_column(frame: pd.DataFrame, candidates: Sequence[str], label: str) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise ValueError(f"Missing {label} column; expected one of {list(candidates)}")


def _parse_quarter(value: object, fallback_year: int) -> tuple[int, int] | None:
    text = str(value).strip().upper().replace(" ", "")
    year_match = re.search(r"(20\d{2})", text)
    quarter_match = re.search(r"(?:第)?([1-4])季度", text) or re.search(r"Q([1-4])", text)
    if quarter_match is None:
        return None
    return (int(year_match.group(1)) if year_match else fallback_year, int(quarter_match.group(1)))


def _period_dates(year: int, quarter: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    if quarter == 2:
        snapshot = pd.Timestamp(year=year, month=6, day=30)
        return snapshot, snapshot + pd.Timedelta(days=60)
    if quarter == 4:
        snapshot = pd.Timestamp(year=year, month=12, day=31)
        return snapshot, snapshot + pd.Timedelta(days=90)
    raise ValueError("Only Q2 and Q4 membership snapshots are supported")


def download_etf_membership_snapshots(
    fund_symbol: str = "561910",
    years: Iterable[int] = range(2021, 2026),
    *,
    cutoff: str | pd.Timestamp = "2025-08-29",
    top_n: int = 50,
    provider: FrameProvider = ak.fund_portfolio_hold_em,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    sleep_fn: SleepFunction = time.sleep,
) -> pd.DataFrame:
    """Build conservative Q2/Q4 membership snapshots from ETF holdings.

    Eastmoney returns all disclosed quarters for a requested calendar year.
    Q2 holdings are treated as available 60 calendar days after June 30 and Q4
    holdings 90 days after December 31.  A snapshot whose conservative
    ``available_date`` exceeds ``cutoff`` is excluded, so unavailable 2025 Q4
    constituents are never inferred.
    """

    normalized_fund = _six_digit_symbol(fund_symbol)
    if normalized_fund is None:
        raise ValueError(f"Invalid fund symbol: {fund_symbol!r}")
    if top_n < 1:
        raise ValueError("top_n must be positive")
    cutoff_ts = pd.Timestamp(cutoff).normalize()
    snapshots: list[pd.DataFrame] = []

    for requested_year in sorted({int(year) for year in years}):
        raw = _call_with_retry(
            provider,
            provider_name="AkShare fund_portfolio_hold_em",
            attempts=attempts,
            backoff_seconds=backoff_seconds,
            sleep_fn=sleep_fn,
            kwargs={"symbol": normalized_fund, "date": str(requested_year)},
        )
        if raw.empty:
            continue
        code_column = _first_present_column(raw, ["股票代码", "证券代码", "代码"], "security code")
        name_column = _first_present_column(raw, ["股票名称", "证券名称", "名称"], "security name")
        weight_column = _first_present_column(
            raw,
            ["占净值比例", "占净值 比例", "持仓占比", "占基金净值比"],
            "portfolio weight",
        )
        quarter_column = _first_present_column(raw, ["季度", "报告期"], "quarter")

        working = raw[[code_column, name_column, weight_column, quarter_column]].copy()
        working["symbol"] = working[code_column].map(_six_digit_symbol)
        working["name"] = working[name_column].astype(str).str.strip()
        working["weight_pct"] = pd.to_numeric(
            working[weight_column].astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
            errors="coerce",
        )
        working["parsed_period"] = working[quarter_column].map(
            lambda value: _parse_quarter(value, requested_year)
        )
        working = working.dropna(subset=["symbol", "weight_pct", "parsed_period"])

        for (period_year, quarter), group in working.groupby("parsed_period", sort=True):
            if quarter not in {2, 4}:
                continue
            snapshot_date, available_date = _period_dates(int(period_year), int(quarter))
            if available_date > cutoff_ts:
                continue
            selected = (
                group.sort_values(["weight_pct", "symbol"], ascending=[False, True], kind="mergesort")
                .drop_duplicates("symbol", keep="first")
                .head(top_n)
                .copy()
            )
            selected["rank"] = range(1, len(selected) + 1)
            selected["fund_symbol"] = normalized_fund
            selected["snapshot_date"] = snapshot_date
            selected["available_date"] = available_date
            selected["year"] = int(period_year)
            selected["quarter"] = int(quarter)
            snapshots.append(selected[MEMBERSHIP_COLUMNS])

    if not snapshots:
        return pd.DataFrame(columns=MEMBERSHIP_COLUMNS)
    result = pd.concat(snapshots, ignore_index=True)
    return result.sort_values(["snapshot_date", "rank", "symbol"], kind="mergesort").reset_index(drop=True)


def membership_union_symbols(membership: pd.DataFrame) -> list[str]:
    """Return the sorted six-digit symbol union from membership snapshots."""

    if "symbol" not in membership.columns:
        raise ValueError("membership must contain a symbol column")
    symbols = {_six_digit_symbol(value) for value in membership["symbol"]}
    return sorted(symbol for symbol in symbols if symbol is not None)


def _yahoo_ticker(symbol: str) -> str:
    normalized = _six_digit_symbol(symbol)
    if normalized is None:
        raise ValueError(f"Invalid A-share symbol: {symbol!r}")
    # Major mainland indices use a Shanghai suffix despite beginning with 0.
    if normalized in {"000300", "000905", "000852"}:
        suffix = "SS"
    elif normalized.startswith(("4", "8", "92")):
        suffix = "BJ"
    elif normalized.startswith(("5", "6", "9")):
        suffix = "SS"
    elif normalized.startswith(("0", "1", "2", "3")):
        suffix = "SZ"
    else:
        raise ValueError(f"Unsupported A-share exchange prefix: {normalized}")
    return f"{normalized}.{suffix}"


def _eastmoney_secucode(symbol: str) -> str:
    ticker = _yahoo_ticker(symbol)
    code, suffix = ticker.split(".")
    exchange = {"SS": "SH", "SZ": "SZ", "BJ": "BJ"}[suffix]
    return f"{code}.{exchange}"


def _extract_yahoo_ticker(frame: pd.DataFrame, ticker: str, batch_size: int) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    extracted: pd.DataFrame
    if isinstance(frame.columns, pd.MultiIndex):
        matching_levels = [
            level for level in range(frame.columns.nlevels) if ticker in frame.columns.get_level_values(level)
        ]
        if not matching_levels:
            return pd.DataFrame()
        extracted = frame.xs(ticker, axis=1, level=matching_levels[-1], drop_level=True).copy()
        if isinstance(extracted.columns, pd.MultiIndex):
            extracted.columns = ["_".join(map(str, item)).strip("_") for item in extracted.columns]
    else:
        if batch_size != 1:
            return pd.DataFrame()
        extracted = frame.copy()
    extracted = extracted.reset_index()
    date_column = next((column for column in extracted.columns if str(column).lower() in {"date", "datetime"}), None)
    if date_column is None:
        date_column = extracted.columns[0]
    extracted = extracted.rename(columns={date_column: "date"})
    extracted.columns = [str(column).strip().lower().replace(" ", "_") for column in extracted.columns]
    extracted["date"] = pd.to_datetime(extracted["date"], errors="coerce", utc=True).dt.tz_localize(None)
    extracted["yahoo_ticker"] = ticker
    return extracted.dropna(subset=["date"])


def _normalize_yahoo_variant(
    frame: pd.DataFrame,
    tickers: Sequence[str],
    suffix: str,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for ticker in tickers:
        extracted = _extract_yahoo_ticker(frame, ticker, len(tickers))
        if extracted.empty:
            continue
        rename = {
            "open": f"open_{suffix}",
            "high": f"high_{suffix}",
            "low": f"low_{suffix}",
            "close": f"close_{suffix}",
            "volume": f"volume_{suffix}",
            "adj_close": "adj_close_vendor",
        }
        extracted = extracted.rename(columns=rename)
        wanted = ["date", "yahoo_ticker", *[column for column in rename.values() if column in extracted.columns]]
        pieces.append(extracted[wanted])
    if not pieces:
        return pd.DataFrame(columns=["date", "yahoo_ticker"])
    return pd.concat(pieces, ignore_index=True)


def _batches(values: Sequence[str], batch_size: int) -> Iterable[list[str]]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    for start in range(0, len(values), batch_size):
        yield list(values[start : start + batch_size])


def download_yfinance_ohlcv(
    symbols: Iterable[str],
    *,
    start: str | pd.Timestamp = "2017-01-01",
    end: str | pd.Timestamp = "2025-08-29",
    batch_size: int = 25,
    provider: FrameProvider = yf.download,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    sleep_fn: SleepFunction = time.sleep,
    strict: bool = True,
) -> pd.DataFrame:
    """Download raw and auto-adjusted Yahoo OHLCV into one long table.

    Yahoo treats ``end`` as exclusive, so the provider request adds one day and
    the normalized result is explicitly bounded to the requested inclusive
    interval.  Two provider calls per batch retain vendor raw prices and the
    separately auto-adjusted OHLCV returned by Yahoo.
    """

    normalized_symbols = sorted({_six_digit_symbol(value) for value in symbols} - {None})
    if not normalized_symbols:
        return pd.DataFrame(columns=MARKET_COLUMNS)
    symbol_by_ticker = {_yahoo_ticker(symbol): symbol for symbol in normalized_symbols}
    tickers = sorted(symbol_by_ticker)
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    if start_ts > end_ts:
        raise ValueError("start must not be after end")
    provider_end = (end_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    output: list[pd.DataFrame] = []
    observed: set[str] = set()

    for batch in _batches(tickers, batch_size):
        common = {
            "tickers": batch,
            "start": start_ts.strftime("%Y-%m-%d"),
            "end": provider_end,
            "actions": False,
            "threads": False,
            "progress": False,
            "group_by": "column",
            "multi_level_index": True,
        }
        raw = _call_with_retry(
            provider,
            provider_name="yfinance raw OHLCV",
            attempts=attempts,
            backoff_seconds=backoff_seconds,
            sleep_fn=sleep_fn,
            kwargs={**common, "auto_adjust": False},
        )
        adjusted = _call_with_retry(
            provider,
            provider_name="yfinance adjusted OHLCV",
            attempts=attempts,
            backoff_seconds=backoff_seconds,
            sleep_fn=sleep_fn,
            kwargs={**common, "auto_adjust": True},
        )
        raw_long = _normalize_yahoo_variant(raw, batch, "raw")
        adjusted_long = _normalize_yahoo_variant(adjusted, batch, "adjusted").drop(
            columns=["adj_close_vendor"], errors="ignore"
        )
        merged = raw_long.merge(adjusted_long, on=["date", "yahoo_ticker"], how="inner")
        if merged.empty:
            continue
        merged["symbol"] = merged["yahoo_ticker"].map(symbol_by_ticker)
        merged = merged.loc[merged["date"].between(start_ts, end_ts)].copy()
        for column in [item for item in MARKET_COLUMNS if item not in {"date", "symbol", "yahoo_ticker"}]:
            if column not in merged.columns:
                merged[column] = pd.NA
            merged[column] = pd.to_numeric(merged[column], errors="coerce")
        merged["adjustment_factor"] = merged["close_adjusted"] / merged["close_raw"]
        observed.update(merged.loc[merged["close_raw"].notna(), "symbol"].dropna().astype(str))
        output.append(merged[MARKET_COLUMNS])

    missing = sorted(set(normalized_symbols) - observed)
    if strict and missing:
        raise ValueError(f"Yahoo returned no usable observations for symbols: {missing}")
    if not output:
        return pd.DataFrame(columns=MARKET_COLUMNS)
    result = pd.concat(output, ignore_index=True)
    return (
        result.drop_duplicates(["date", "symbol"], keep="last")
        .sort_values(["symbol", "date"], kind="mergesort")
        .reset_index(drop=True)
    )


def _tencent_symbol(symbol: str) -> str:
    normalized = _six_digit_symbol(symbol)
    if normalized is None:
        raise ValueError(f"Invalid A-share symbol: {symbol!r}")
    if normalized.startswith(("5", "6", "9")):
        return f"sh{normalized}"
    if normalized.startswith(("0", "1", "2", "3")):
        return f"sz{normalized}"
    raise ValueError(f"Tencent fallback does not support this exchange: {normalized}")


def download_tencent_ohlcv(
    symbols: Iterable[str],
    *,
    start: str | pd.Timestamp = "2017-01-01",
    end: str | pd.Timestamp = "2025-08-29",
    provider: FrameProvider = ak.stock_zh_a_hist_tx,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    sleep_fn: SleepFunction = time.sleep,
    strict: bool = True,
) -> pd.DataFrame:
    """Download raw and back-adjusted OHLCV from Tencent via AkShare.

    This is primarily a delisted-security fallback.  Using it after a Yahoo
    miss keeps former constituents such as 300116 in the historical universe
    instead of silently introducing survivorship bias.  The provider's
    back-adjusted (``hfq``) prices are used for returns while raw prices and raw
    volume remain available for liquidity and transaction-cost calculations.
    """

    normalized_symbols = sorted({_six_digit_symbol(value) for value in symbols} - {None})
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    if start_ts > end_ts:
        raise ValueError("start must not be after end")
    output: list[pd.DataFrame] = []
    failures: list[str] = []

    for symbol in normalized_symbols:
        market_symbol = _tencent_symbol(symbol)
        common = {
            "symbol": market_symbol,
            "start_date": start_ts.strftime("%Y%m%d"),
            "end_date": end_ts.strftime("%Y%m%d"),
        }
        try:
            raw = _call_with_retry(
                provider,
                provider_name=f"Tencent raw OHLCV for {symbol}",
                attempts=attempts,
                backoff_seconds=backoff_seconds,
                sleep_fn=sleep_fn,
                kwargs={**common, "adjust": ""},
            )
            adjusted = _call_with_retry(
                provider,
                provider_name=f"Tencent hfq OHLCV for {symbol}",
                attempts=attempts,
                backoff_seconds=backoff_seconds,
                sleep_fn=sleep_fn,
                kwargs={**common, "adjust": "hfq"},
            )
        except RuntimeError:
            failures.append(symbol)
            continue
        required = {"date", "open", "high", "low", "close", "volume"}
        if raw.empty or adjusted.empty or not required.issubset(raw.columns) or not required.issubset(adjusted.columns):
            failures.append(symbol)
            continue
        raw = raw.copy()
        adjusted = adjusted.copy()
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        adjusted["date"] = pd.to_datetime(adjusted["date"], errors="coerce")
        raw = raw.rename(
            columns={
                "open": "open_raw",
                "high": "high_raw",
                "low": "low_raw",
                "close": "close_raw",
                "volume": "volume_raw",
            }
        )
        adjusted = adjusted.rename(
            columns={
                "open": "open_adjusted",
                "high": "high_adjusted",
                "low": "low_adjusted",
                "close": "close_adjusted",
                "volume": "volume_adjusted",
            }
        )
        merged = raw[["date", "open_raw", "high_raw", "low_raw", "close_raw", "volume_raw"]].merge(
            adjusted[
                [
                    "date",
                    "open_adjusted",
                    "high_adjusted",
                    "low_adjusted",
                    "close_adjusted",
                    "volume_adjusted",
                ]
            ],
            on="date",
            how="inner",
        )
        merged = merged.loc[merged["date"].between(start_ts, end_ts)].copy()
        if merged.empty:
            failures.append(symbol)
            continue
        merged["symbol"] = symbol
        merged["yahoo_ticker"] = f"{market_symbol}.Tencent"
        merged["adj_close_vendor"] = merged["close_adjusted"]
        merged["adjustment_factor"] = merged["close_adjusted"] / merged["close_raw"]
        for column in [item for item in MARKET_COLUMNS if item not in {"date", "symbol", "yahoo_ticker"}]:
            merged[column] = pd.to_numeric(merged[column], errors="coerce")
        output.append(merged[MARKET_COLUMNS])

    if strict and failures:
        raise ValueError(f"Tencent returned no usable observations for symbols: {sorted(failures)}")
    if not output:
        return pd.DataFrame(columns=MARKET_COLUMNS)
    return (
        pd.concat(output, ignore_index=True)
        .drop_duplicates(["date", "symbol"], keep="last")
        .sort_values(["symbol", "date"], kind="mergesort")
        .reset_index(drop=True)
    )


def download_eastmoney_fundamentals(
    symbols: Iterable[str],
    *,
    cutoff: str | pd.Timestamp = "2025-08-29",
    provider: FrameProvider = ak.stock_financial_analysis_indicator_em,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    sleep_fn: SleepFunction = time.sleep,
    strict: bool = True,
) -> pd.DataFrame:
    """Download quarterly and annual Eastmoney indicators known by ``cutoff``."""

    normalized_symbols = sorted({_six_digit_symbol(value) for value in symbols} - {None})
    cutoff_ts = pd.Timestamp(cutoff).normalize()
    records: list[pd.DataFrame] = []
    failures: list[str] = []
    rename = {
        "REPORT_DATE": "report_date",
        "NOTICE_DATE": "notice_date",
        "REPORT_TYPE": "report_type",
        "TOTALOPERATEREVE": "revenue",
        "TOTALOPERATEREVETZ": "revenue_yoy_pct",
        "PARENTNETPROFIT": "net_profit",
        "PARENTNETPROFITTZ": "net_profit_yoy_pct",
        "ROEJQ": "roe_pct",
        "XSMLL": "gross_margin_pct",
        "XSJLL": "net_margin_pct",
        "ZCFZL": "debt_ratio_pct",
    }

    for symbol in normalized_symbols:
        try:
            raw = _call_with_retry(
                provider,
                provider_name=f"Eastmoney fundamentals for {symbol}",
                attempts=attempts,
                backoff_seconds=backoff_seconds,
                sleep_fn=sleep_fn,
                kwargs={"symbol": _eastmoney_secucode(symbol), "indicator": "按报告期"},
            )
        except RuntimeError:
            failures.append(symbol)
            continue
        if raw.empty:
            failures.append(symbol)
            continue
        missing_dates = [column for column in ["REPORT_DATE", "NOTICE_DATE"] if column not in raw.columns]
        if missing_dates:
            raise ValueError(f"Eastmoney fundamentals for {symbol} missing columns: {missing_dates}")
        normalized = raw.rename(columns=rename).copy()
        normalized["symbol"] = symbol
        normalized["report_date"] = pd.to_datetime(normalized["report_date"], errors="coerce").dt.normalize()
        normalized["notice_date"] = pd.to_datetime(normalized["notice_date"], errors="coerce").dt.normalize()
        normalized["available_date"] = normalized["notice_date"]
        for column in FUNDAMENTAL_COLUMNS:
            if column not in normalized.columns:
                normalized[column] = pd.NA
        numeric = [
            "revenue",
            "revenue_yoy_pct",
            "net_profit",
            "net_profit_yoy_pct",
            "roe_pct",
            "gross_margin_pct",
            "net_margin_pct",
            "debt_ratio_pct",
        ]
        for column in numeric:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized = normalized.loc[
            normalized["report_date"].notna()
            & normalized["notice_date"].notna()
            & normalized["report_date"].le(cutoff_ts)
            & normalized["notice_date"].le(cutoff_ts)
        ]
        records.append(normalized[FUNDAMENTAL_COLUMNS])

    if strict and failures:
        raise ValueError(f"No usable Eastmoney fundamentals for symbols: {sorted(failures)}")
    if not records:
        return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)
    result = pd.concat(records, ignore_index=True)
    return (
        result.drop_duplicates(["symbol", "report_date", "notice_date"], keep="last")
        .sort_values(["symbol", "report_date", "notice_date"], kind="mergesort")
        .reset_index(drop=True)
    )


def dataframe_sha256(frame: pd.DataFrame) -> str:
    """Return an order-independent SHA-256 for a normalized tabular asset."""

    stable = frame.copy()
    stable = stable.reindex(sorted(map(str, stable.columns)), axis=1)
    dtype_header = json.dumps({column: str(stable[column].dtype) for column in stable.columns}, sort_keys=True)
    for column in stable.columns:
        if isinstance(stable[column].dtype, pd.DatetimeTZDtype) or pd.api.types.is_datetime64_any_dtype(
            stable[column]
        ):
            stable[column] = pd.to_datetime(stable[column], errors="coerce", utc=True).dt.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        else:
            stable[column] = stable[column].astype("string")
    stable = stable.fillna("<NA>")
    if len(stable.columns):
        stable = stable.sort_values(list(stable.columns), kind="mergesort").reset_index(drop=True)
    payload = dtype_header + "\n" + stable.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_source_record(
    frame: pd.DataFrame,
    *,
    provider: str,
    parameters: Mapping[str, Any],
    url: str | None = None,
    retrieved_at_utc: str | None = None,
) -> dict[str, Any]:
    """Create a manifest record with a deterministic content hash."""

    record: dict[str, Any] = {
        "provider": provider,
        "retrieved_at_utc": retrieved_at_utc or datetime.now(timezone.utc).isoformat(),
        "rows": int(len(frame)),
        "columns": list(map(str, frame.columns)),
        "dataframe_sha256": dataframe_sha256(frame),
        "parameters": dict(parameters),
    }
    if url is not None:
        record["url"] = url
    return record


def write_source_manifest(
    path: str | Path,
    records: Mapping[str, Mapping[str, Any]],
    *,
    merge: bool = True,
) -> None:
    """Atomically write or merge source records into a JSON manifest."""

    manifest_path = Path(path)
    if merge and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"schema_version": 1, "sources": {}}
    manifest.setdefault("schema_version", 1)
    manifest.setdefault("sources", {})
    for key, record in records.items():
        manifest["sources"][str(key)] = dict(record)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)


def download_systematic_assets(
    config_path: str | Path = "config/systematic.yaml",
) -> dict[str, pd.DataFrame]:
    """Download and freeze the three raw assets used by the systematic run.

    Yahoo supplies the primary raw/adjusted OHLCV panel.  Missing Shanghai or
    Shenzhen names are retried through Tencent so historical delistings are
    not silently discarded.  Securities explicitly excluded by the manual
    comparability map remain in the membership asset for audit but are not
    requested from the market or fundamental providers.
    """

    resolved = Path(config_path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    root = resolved.parent.parent
    project = config["project"]
    universe = config["universe"]
    cutoff = str(project["research_as_of"])
    start = str(project["market_data_start"])

    membership = download_etf_membership_snapshots(
        fund_symbol=str(universe["etf_symbol"]),
        years=[int(value) for value in universe["holdings_years"]],
        cutoff=cutoff,
        top_n=int(universe["constituents_per_snapshot"]),
    )
    if membership.empty:
        raise RuntimeError("The ETF membership provider returned no usable snapshots")

    included_symbols = membership_union_symbols(membership)
    map_path = root / "data" / "manual" / "systematic_industry_groups.csv"
    excluded_symbols: list[str] = []
    if map_path.exists():
        mapping = pd.read_csv(map_path, dtype={"symbol": str})
        if "include" in mapping.columns:
            include = mapping["include"]
            if include.dtype != bool:
                include = include.astype(str).str.strip().str.lower().map(
                    {"true": True, "false": False, "1": True, "0": False}
                )
            if include.isna().any():
                raise ValueError(f"{map_path} contains invalid include values")
            excluded_symbols = sorted(
                mapping.loc[~include.astype(bool), "symbol"].astype(str).str.zfill(6).tolist()
            )
            included_symbols = [symbol for symbol in included_symbols if symbol not in excluded_symbols]

    benchmark_symbol = str(universe["benchmark_symbol"]).zfill(6)
    requested_market = sorted({*included_symbols, benchmark_symbol})
    yahoo_market = download_yfinance_ohlcv(
        requested_market,
        start=start,
        end=cutoff,
        strict=False,
    )
    observed = set(yahoo_market["symbol"].astype(str))
    missing = sorted(set(requested_market) - observed)
    tencent_market = download_tencent_ohlcv(
        missing,
        start=start,
        end=cutoff,
        strict=False,
    )
    market = pd.concat([yahoo_market, tencent_market], ignore_index=True)
    market = (
        market.drop_duplicates(["date", "symbol"], keep="last")
        .sort_values(["symbol", "date"], kind="mergesort")
        .reset_index(drop=True)
    )
    still_missing = sorted(set(requested_market) - set(market["symbol"].astype(str)))
    if still_missing:
        raise RuntimeError(f"No public OHLCV history was found for required symbols: {still_missing}")

    fundamentals = download_eastmoney_fundamentals(
        included_symbols,
        cutoff=cutoff,
        strict=True,
    )

    raw_dir = root / "data" / "raw"
    membership_path = raw_dir / "systematic_membership.parquet"
    market_path = raw_dir / "systematic_market_daily.parquet"
    fundamentals_path = raw_dir / "systematic_fundamentals_pit.parquet"
    write_frame(membership, membership_path)
    write_frame(market, market_path)
    write_frame(fundamentals, fundamentals_path)

    records = {
        "systematic_membership": build_source_record(
            membership,
            provider="Eastmoney ETF holdings via AkShare",
            url="https://fundf10.eastmoney.com/ccmx_561910.html",
            parameters={
                "fund_symbol": str(universe["etf_symbol"]),
                "years": list(universe["holdings_years"]),
                "snapshots": list(universe["snapshots"]),
                "top_n": int(universe["constituents_per_snapshot"]),
                "research_cutoff": cutoff,
                "availability_rule": "Q2 +60 calendar days; Q4 +90 calendar days",
                "path": str(membership_path.relative_to(root)),
            },
        ),
        "systematic_market_daily": build_source_record(
            market,
            provider="Yahoo Finance primary; Tencent via AkShare fallback",
            url="https://finance.yahoo.com/",
            parameters={
                "start": start,
                "end_inclusive": cutoff,
                "requested_symbols": requested_market,
                "tencent_fallback_symbols": missing,
                "excluded_symbols": excluded_symbols,
                "path": str(market_path.relative_to(root)),
            },
        ),
        "systematic_fundamentals_pit": build_source_record(
            fundamentals,
            provider="Eastmoney financial analysis via AkShare",
            url="https://emweb.securities.eastmoney.com/",
            parameters={
                "research_cutoff": cutoff,
                "notice_date_required": True,
                "symbols": included_symbols,
                "path": str(fundamentals_path.relative_to(root)),
            },
        ),
    }
    write_source_manifest(root / "data" / "source_manifest.json", records)
    return {
        "membership": membership,
        "market": market,
        "fundamentals": fundamentals,
    }
