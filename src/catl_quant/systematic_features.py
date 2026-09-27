"""Point-in-time monthly features for systematic equity research.

The public entry point, :func:`build_monthly_systematic_features`, accepts
three long tables and returns one row per signal month and eligible security.
The timing convention is deliberately conservative:

* ``execution_date`` is the last trading day of a calendar month;
* ``signal_date`` is the configured number of trading days before execution
  (one day in the registered baseline and two days in the lag stress test);
* every price feature uses observations no later than ``signal_date``;
* membership ``available_date`` and fundamental ``notice_date`` (and optional
  ``available_date``) must be no later than ``signal_date``; and
* the one-month label is the adjusted-close return from ``execution_date`` to
  the next month's ``execution_date``.

The module contains no downloader and no global state.  It is consequently
safe to run against frozen vendor snapshots in a walk-forward backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


MARKET_COLUMNS = {
    "date",
    "symbol",
    "close_adj",
    "close_raw",
    "high_raw",
    "low_raw",
    "volume",
}
FUNDAMENTAL_COLUMNS = {"symbol", "report_date", "notice_date"}
MEMBERSHIP_COLUMNS = {
    "available_date",
    "snapshot_date",
    "symbol",
    "benchmark_weight",
}

PRICE_FEATURES = (
    "momentum_12_1",
    "momentum_6_1",
    "volatility_3m",
    "beta_6m",
    "idio_volatility_6m",
    "adv_20d",
    "amihud_20d",
)
FUNDAMENTAL_FEATURES = (
    "quality_raw",
    "growth_raw",
    "fundamental_momentum_raw",
)
NEUTRALIZED_FEATURES = (
    "momentum_12_1",
    "momentum_6_1",
    "volatility_3m",
    "beta_6m",
    "idio_volatility_6m",
    "amihud_20d",
    *FUNDAMENTAL_FEATURES,
)


@dataclass(frozen=True)
class FeatureConfig:
    """Window lengths and minimum-data rules for the monthly feature panel."""

    momentum_12m_days: int = 252
    momentum_6m_days: int = 126
    momentum_skip_days: int = 21
    volatility_window_days: int = 63
    beta_window_days: int = 126
    liquidity_window_days: int = 20
    min_volatility_observations: int = 50
    min_beta_observations: int = 100
    min_liquidity_observations: int = 15
    annualization_days: int = 252
    mad_clip: float = 5.0
    min_cross_section: int = 10
    min_cross_section_coverage: float = 0.60
    min_row_feature_coverage: float = 0.70
    signal_lag_trading_days: int = 1

    def __post_init__(self) -> None:
        positive = {
            "momentum_12m_days": self.momentum_12m_days,
            "momentum_6m_days": self.momentum_6m_days,
            "momentum_skip_days": self.momentum_skip_days,
            "volatility_window_days": self.volatility_window_days,
            "beta_window_days": self.beta_window_days,
            "liquidity_window_days": self.liquidity_window_days,
            "annualization_days": self.annualization_days,
            "min_cross_section": self.min_cross_section,
            "signal_lag_trading_days": self.signal_lag_trading_days,
        }
        if any(value <= 0 for value in positive.values()):
            raise ValueError(f"Window and count parameters must be positive: {positive}")
        if self.momentum_12m_days <= self.momentum_skip_days:
            raise ValueError("12-1 momentum lookback must exceed its skip window")
        if self.momentum_6m_days <= self.momentum_skip_days:
            raise ValueError("6-1 momentum lookback must exceed its skip window")
        if not 0 < self.min_cross_section_coverage <= 1:
            raise ValueError("min_cross_section_coverage must be in (0, 1]")
        if not 0 < self.min_row_feature_coverage <= 1:
            raise ValueError("min_row_feature_coverage must be in (0, 1]")
        if self.mad_clip <= 0:
            raise ValueError("mad_clip must be positive")


def robust_mad_zscore(series: pd.Series, clip: float = 5.0) -> pd.Series:
    """Return a median/MAD winsorized z-score while preserving missing values.

    The robust scale is ``1.4826 * median(abs(x - median(x)))``.  When the MAD
    is zero, the function falls back to the population standard deviation.  A
    constant non-missing series receives zero scores.
    """

    values = pd.to_numeric(series, errors="coerce").astype(float)
    result = pd.Series(np.nan, index=series.index, dtype=float)
    valid = values.dropna()
    if valid.empty:
        return result
    median = float(valid.median())
    mad = float((valid - median).abs().median())
    robust_scale = 1.4826 * mad
    if not np.isfinite(robust_scale) or robust_scale == 0:
        robust_scale = float(valid.std(ddof=0))
    if not np.isfinite(robust_scale) or robust_scale == 0:
        result.loc[valid.index] = 0.0
        return result
    clipped = valid.clip(median - clip * robust_scale, median + clip * robust_scale)
    scale = float(clipped.std(ddof=0))
    if not np.isfinite(scale) or scale == 0:
        result.loc[valid.index] = 0.0
    else:
        result.loc[valid.index] = (clipped - float(clipped.mean())) / scale
    return result


def cross_sectional_neutralize(
    feature: pd.Series,
    adv: pd.Series,
    *,
    groups: pd.Series | None = None,
    mad_clip: float = 5.0,
    min_observations: int = 10,
) -> pd.Series:
    """MAD-standardize and residualize a feature on log ADV and group dummies.

    The returned score has cross-sectional mean zero and population standard
    deviation one.  The simultaneous regression, rather than sequential group
    demeaning, ensures that liquidity neutralization does not reintroduce group
    exposure.  Rows with missing features or non-positive ADV remain missing.
    """

    initial = robust_mad_zscore(feature, clip=mad_clip)
    adv_numeric = pd.to_numeric(adv, errors="coerce").astype(float)
    valid = initial.notna() & adv_numeric.gt(0)
    if groups is not None:
        valid &= groups.notna()
    result = pd.Series(np.nan, index=feature.index, dtype=float)
    if int(valid.sum()) < min_observations:
        return result

    y = initial.loc[valid].to_numpy(dtype=float)
    log_adv = np.log(adv_numeric.loc[valid].to_numpy(dtype=float))
    columns = [np.ones(len(y)), log_adv - log_adv.mean()]
    if groups is not None:
        categorical = groups.loc[valid].astype(str)
        dummies = pd.get_dummies(categorical, drop_first=True, dtype=float)
        if not dummies.empty:
            columns.extend(dummies[column].to_numpy(dtype=float) for column in dummies.columns)
    design = np.column_stack(columns)
    if len(y) <= np.linalg.matrix_rank(design):
        return result
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coefficients
    scale = float(residual.std(ddof=0))
    if not np.isfinite(scale) or scale == 0:
        standardized = np.zeros_like(residual)
    else:
        standardized = (residual - residual.mean()) / scale
    result.loc[valid] = standardized
    return result


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def _prepare_inputs(
    market: pd.DataFrame,
    fundamentals: pd.DataFrame,
    memberships: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Accept the names emitted by ``systematic_data`` as a convenience while
    # keeping the public feature contract compact and vendor-independent.
    market = market.copy()
    market_aliases: dict[str, str] = {}
    if "close_adj" not in market.columns and "close_adjusted" in market.columns:
        market_aliases["close_adjusted"] = "close_adj"
    if "volume" not in market.columns and "volume_raw" in market.columns:
        market_aliases["volume_raw"] = "volume"
    market = market.rename(columns=market_aliases)
    memberships = memberships.copy()
    if "benchmark_weight" not in memberships.columns and "weight_pct" in memberships.columns:
        memberships["benchmark_weight"] = pd.to_numeric(
            memberships["weight_pct"], errors="coerce"
        ) / 100
    _require_columns(market, MARKET_COLUMNS, "market")
    _require_columns(fundamentals, FUNDAMENTAL_COLUMNS, "fundamentals")
    _require_columns(memberships, MEMBERSHIP_COLUMNS, "memberships")

    prices = market.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="raise")
    prices["symbol"] = prices["symbol"].astype(str)
    numeric_market = ["close_adj", "close_raw", "high_raw", "low_raw", "volume"]
    for column in numeric_market:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    if prices.duplicated(["date", "symbol"]).any():
        raise ValueError("market contains duplicate date/symbol observations")
    if (prices[["close_adj", "close_raw", "high_raw", "low_raw"]] <= 0).any().any():
        raise ValueError("market prices must be positive")
    if prices["volume"].lt(0).any():
        raise ValueError("market volume cannot be negative")
    prices = prices.sort_values(["symbol", "date"]).reset_index(drop=True)
    prices["simple_return"] = prices.groupby("symbol", sort=False)["close_adj"].pct_change(fill_method=None)
    prices["dollar_volume"] = prices["close_raw"] * prices["volume"]

    financials = fundamentals.copy()
    financials["symbol"] = financials["symbol"].astype(str)
    financials["report_date"] = pd.to_datetime(financials["report_date"], errors="raise")
    financials["notice_date"] = pd.to_datetime(financials["notice_date"], errors="raise")
    if "available_date" in financials.columns:
        financials["available_date"] = pd.to_datetime(financials["available_date"], errors="raise")
        financials["effective_date"] = financials[["notice_date", "available_date"]].max(axis=1)
    else:
        financials["effective_date"] = financials["notice_date"]
    if financials["report_date"].gt(financials["effective_date"]).any():
        raise ValueError("fundamental report_date cannot be after its effective date")
    if financials.duplicated(["symbol", "report_date", "effective_date"]).any():
        raise ValueError("fundamentals contain duplicate symbol/report/effective records")
    financials = financials.sort_values(["symbol", "report_date", "effective_date"]).reset_index(drop=True)

    members = memberships.copy()
    members["symbol"] = members["symbol"].astype(str)
    members["available_date"] = pd.to_datetime(members["available_date"], errors="raise")
    members["snapshot_date"] = pd.to_datetime(members["snapshot_date"], errors="raise")
    members["benchmark_weight"] = pd.to_numeric(members["benchmark_weight"], errors="coerce")
    if members["benchmark_weight"].lt(0).any():
        raise ValueError("benchmark_weight cannot be negative")
    if members.duplicated(["snapshot_date", "available_date", "symbol"]).any():
        raise ValueError("memberships contain duplicate version/symbol records")
    members = members.sort_values(["snapshot_date", "available_date", "symbol"]).reset_index(drop=True)
    return prices, financials, members


def _monthly_calendar(
    dates: Iterable[pd.Timestamp], signal_lag_trading_days: int = 1
) -> pd.DataFrame:
    trading_days = pd.DatetimeIndex(pd.to_datetime(pd.Index(dates)).dropna().unique()).sort_values()
    if len(trading_days) < 2:
        return pd.DataFrame(columns=["signal_date", "execution_date", "next_execution_date"])
    by_month = pd.Series(trading_days, index=trading_days).groupby(trading_days.to_period("M")).max()
    position = {date: idx for idx, date in enumerate(trading_days)}
    rows: list[dict[str, pd.Timestamp]] = []
    executions = by_month.tolist()
    for idx, execution in enumerate(executions):
        loc = position[pd.Timestamp(execution)]
        if loc < signal_lag_trading_days:
            continue
        rows.append(
            {
                "signal_date": trading_days[loc - signal_lag_trading_days],
                "execution_date": pd.Timestamp(execution),
                "next_execution_date": (
                    pd.Timestamp(executions[idx + 1]) if idx + 1 < len(executions) else pd.NaT
                ),
            }
        )
    return pd.DataFrame.from_records(rows)


def _membership_asof(memberships: pd.DataFrame, signal_date: pd.Timestamp) -> pd.DataFrame:
    eligible = memberships.loc[
        memberships["available_date"].le(signal_date)
        & memberships["snapshot_date"].le(signal_date)
    ]
    if eligible.empty:
        return eligible.copy()
    versions = (
        eligible[["snapshot_date", "available_date"]]
        .drop_duplicates()
        .sort_values(["snapshot_date", "available_date"])
    )
    latest = versions.iloc[-1]
    return eligible.loc[
        eligible["snapshot_date"].eq(latest["snapshot_date"])
        & eligible["available_date"].eq(latest["available_date"])
    ].copy()


def _first_numeric(row: pd.Series | None, names: tuple[str, ...]) -> float:
    if row is None:
        return float("nan")
    for name in names:
        if name in row.index:
            value = pd.to_numeric(pd.Series([row[name]]), errors="coerce").iloc[0]
            if pd.notna(value):
                return float(value)
    return float("nan")


def _safe_ratio(numerator: float, denominator: float, *, positive_denominator: bool = True) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator):
        return float("nan")
    if (positive_denominator and denominator <= 0) or (not positive_denominator and denominator == 0):
        return float("nan")
    return float(numerator / denominator)


def _quality_components(row: pd.Series | None) -> dict[str, float]:
    if row is None:
        return {
            "gross_profitability": float("nan"),
            "accrual_quality": float("nan"),
            "leverage_quality": float("nan"),
            "quality_raw": float("nan"),
        }
    assets = _first_numeric(row, ("total_assets", "assets"))
    revenue = _first_numeric(row, ("revenue", "total_revenue"))
    cogs = _first_numeric(row, ("cost_of_goods_sold", "cost_of_sales", "cogs"))
    gross_profit = _first_numeric(row, ("gross_profit",))
    if not np.isfinite(gross_profit) and np.isfinite(revenue) and np.isfinite(cogs):
        gross_profit = revenue - cogs
    net_income = _first_numeric(row, ("net_income", "net_profit"))
    cash_flow = _first_numeric(row, ("operating_cash_flow", "cfo"))
    liabilities = _first_numeric(row, ("total_liabilities", "liabilities"))

    gross_profitability = _safe_ratio(gross_profit, assets)
    accrual_quality = _safe_ratio(-(net_income - cash_flow), assets)
    leverage_quality = _safe_ratio(-liabilities, assets)
    canonical = [gross_profitability, accrual_quality, leverage_quality]
    valid_canonical = [value for value in canonical if np.isfinite(value)]

    if valid_canonical:
        quality = float(np.mean(valid_canonical))
    else:
        fallback = [
            _first_numeric(row, ("roe_pct",)) / 100,
            _first_numeric(row, ("gross_margin_pct",)) / 100,
            _first_numeric(row, ("net_margin_pct",)) / 100,
            -_first_numeric(row, ("debt_ratio_pct",)) / 100,
        ]
        valid_fallback = [value for value in fallback if np.isfinite(value)]
        quality = float(np.mean(valid_fallback)) if valid_fallback else float("nan")
    return {
        "gross_profitability": gross_profitability,
        "accrual_quality": accrual_quality,
        "leverage_quality": leverage_quality,
        "quality_raw": quality,
    }


def _fundamental_features(current: pd.Series | None, prior: pd.Series | None) -> dict[str, float]:
    current_quality = _quality_components(current)
    prior_quality = _quality_components(prior)
    current_revenue = _first_numeric(current, ("revenue", "total_revenue"))
    prior_revenue = _first_numeric(prior, ("revenue", "total_revenue"))
    revenue_growth = _safe_ratio(current_revenue, prior_revenue)
    if np.isfinite(revenue_growth):
        revenue_growth -= 1
    else:
        revenue_growth = _first_numeric(current, ("revenue_growth_pct", "revenue_yoy_pct")) / 100

    current_profit = _first_numeric(current, ("net_income", "net_profit"))
    prior_profit = _first_numeric(prior, ("net_income", "net_profit"))
    prior_assets = _first_numeric(prior, ("total_assets", "assets"))
    profit_change = _safe_ratio(current_profit - prior_profit, prior_assets)
    if not np.isfinite(profit_change):
        profit_change = _first_numeric(
            current, ("net_profit_growth_pct", "net_profit_yoy_pct")
        ) / 100
    growth_values = [value for value in (revenue_growth, profit_change) if np.isfinite(value)]
    growth = float(np.mean(growth_values)) if growth_values else float("nan")

    quality_momentum = (
        current_quality["quality_raw"] - prior_quality["quality_raw"]
        if np.isfinite(current_quality["quality_raw"]) and np.isfinite(prior_quality["quality_raw"])
        else float("nan")
    )
    return {
        **current_quality,
        "revenue_growth_yoy": revenue_growth,
        "profit_change_to_assets": profit_change,
        "growth_raw": growth,
        "fundamental_momentum_raw": quality_momentum,
    }


def _fundamentals_asof(
    fundamentals: pd.DataFrame,
    symbols: list[str],
    signal_date: pd.Timestamp,
) -> dict[str, tuple[pd.Series | None, pd.Series | None, int]]:
    eligible = fundamentals.loc[
        fundamentals["symbol"].isin(symbols)
        & fundamentals["effective_date"].le(signal_date)
        & fundamentals["report_date"].le(signal_date)
    ].copy()
    output: dict[str, tuple[pd.Series | None, pd.Series | None, int]] = {}
    for symbol in symbols:
        history = eligible.loc[eligible["symbol"].eq(symbol)].sort_values(
            ["report_date", "effective_date"]
        )
        if history.empty:
            output[symbol] = (None, None, 0)
            continue
        # The last available version of each report is the version known at the
        # signal date; no later restatement can enter this table.
        versions = history.drop_duplicates("report_date", keep="last")
        current = versions.iloc[-1]
        prior_date = current["report_date"] - pd.DateOffset(years=1)
        prior_rows = versions.loc[versions["report_date"].eq(prior_date)]
        prior = prior_rows.iloc[-1] if not prior_rows.empty else None
        output[symbol] = (current, prior, int(len(versions)))
    return output


def _benchmark_returns(
    market: pd.DataFrame,
    snapshot: pd.DataFrame,
    benchmark_symbol: str | None,
) -> pd.Series:
    returns = market.pivot(index="date", columns="symbol", values="simple_return").sort_index()
    if benchmark_symbol is not None:
        if benchmark_symbol not in returns.columns:
            raise ValueError(f"benchmark_symbol {benchmark_symbol!r} not found in market")
        return returns[benchmark_symbol].rename("benchmark_return")

    weights = snapshot.set_index("symbol")["benchmark_weight"].astype(float)
    available_symbols = [symbol for symbol in weights.index if symbol in returns.columns]
    if not available_symbols:
        return pd.Series(dtype=float, name="benchmark_return")
    weights = weights.loc[available_symbols]
    if not np.isfinite(weights.sum()) or weights.sum() <= 0:
        weights[:] = 1.0
    matrix = returns[available_symbols]
    numerator = matrix.mul(weights, axis=1).sum(axis=1, min_count=1)
    denominator = matrix.notna().mul(weights, axis=1).sum(axis=1)
    return numerator.div(denominator.where(denominator.gt(0))).rename("benchmark_return")


def _price_features_asof(
    security: pd.DataFrame,
    benchmark_returns: pd.Series,
    signal_date: pd.Timestamp,
    config: FeatureConfig,
) -> dict[str, float | int]:
    history = security.loc[security["date"].le(signal_date)].sort_values("date")
    prices = history["close_adj"].dropna()
    features: dict[str, float | int] = {"market_history_days": int(len(prices))}

    need_12m = config.momentum_12m_days + 1
    if len(prices) >= need_12m:
        recent = float(prices.iloc[-(config.momentum_skip_days + 1)])
        old = float(prices.iloc[-(config.momentum_12m_days + 1)])
        features["momentum_12_1"] = float(np.log(recent / old))
    else:
        features["momentum_12_1"] = float("nan")

    need_6m = config.momentum_6m_days + 1
    if len(prices) >= need_6m:
        recent = float(prices.iloc[-(config.momentum_skip_days + 1)])
        old = float(prices.iloc[-(config.momentum_6m_days + 1)])
        features["momentum_6_1"] = float(np.log(recent / old))
    else:
        features["momentum_6_1"] = float("nan")

    daily = history.set_index("date")["simple_return"].dropna()
    vol_sample = daily.tail(config.volatility_window_days)
    features["volatility_3m"] = (
        float(vol_sample.std(ddof=1) * np.sqrt(config.annualization_days))
        if len(vol_sample) >= config.min_volatility_observations
        else float("nan")
    )

    aligned = pd.concat(
        [daily.rename("asset"), benchmark_returns.loc[:signal_date]], axis=1, join="inner"
    ).dropna().tail(config.beta_window_days)
    if len(aligned) >= config.min_beta_observations and aligned["benchmark_return"].var(ddof=0) > 0:
        x = aligned["benchmark_return"].to_numpy(dtype=float)
        y = aligned["asset"].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(x)), x])
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        residual = y - design @ coefficients
        features["beta_6m"] = float(coefficients[1])
        features["idio_volatility_6m"] = float(
            residual.std(ddof=1) * np.sqrt(config.annualization_days)
        )
        features["beta_observations"] = int(len(aligned))
    else:
        features["beta_6m"] = float("nan")
        features["idio_volatility_6m"] = float("nan")
        features["beta_observations"] = int(len(aligned))

    liquidity = history.tail(config.liquidity_window_days).copy()
    valid_dollar = liquidity["dollar_volume"].gt(0)
    features["adv_20d"] = (
        float(liquidity.loc[valid_dollar, "dollar_volume"].mean())
        if int(valid_dollar.sum()) >= config.min_liquidity_observations
        else float("nan")
    )
    amihud_values = (
        liquidity.loc[valid_dollar, "simple_return"].abs()
        / liquidity.loc[valid_dollar, "dollar_volume"]
    ).dropna()
    features["amihud_20d"] = (
        float(amihud_values.mean())
        if len(amihud_values) >= config.min_liquidity_observations
        else float("nan")
    )
    features["liquidity_observations"] = int(len(amihud_values))
    return features


def _close_on(
    close_lookup: pd.Series,
    date: pd.Timestamp | pd.NaT,
    symbol: str,
) -> float:
    if pd.isna(date):
        return float("nan")
    try:
        value = close_lookup.loc[(pd.Timestamp(date), symbol)]
    except KeyError:
        return float("nan")
    return float(value) if pd.notna(value) else float("nan")


def build_monthly_systematic_features(
    market: pd.DataFrame,
    fundamentals: pd.DataFrame,
    memberships: pd.DataFrame,
    *,
    benchmark_symbol: str | None = None,
    group_col: str | None = None,
    config: FeatureConfig | None = None,
) -> pd.DataFrame:
    """Build a point-in-time monthly feature and one-month forward-label panel.

    Parameters
    ----------
    market:
        Long table with ``date,symbol,close_adj,close_raw,high_raw,low_raw,volume``.
        A dedicated benchmark series may be included and selected with
        ``benchmark_symbol``.  Otherwise the current snapshot's benchmark
        weights form a fixed-weight peer benchmark over each lookback window.
    fundamentals:
        Long filing table with ``symbol,report_date,notice_date`` and arbitrary
        numeric metrics.  An optional ``available_date`` is combined with the
        notice date by taking the later date.  Canonical accounting columns are
        documented in :func:`_quality_components`; common CATL-project aliases
        are supported as fallbacks.
    memberships:
        Versioned snapshots with ``available_date,snapshot_date,symbol`` and
        ``benchmark_weight``.  Extra columns, including ``group_col``, are
        retained.
    benchmark_symbol:
        Optional symbol used for six-month beta/idio-volatility and benchmark
        forward return.  It need not be a portfolio member.
    group_col:
        Optional membership column (for example ``subindustry``) included as
        dummies in the cross-sectional neutralization.
    config:
        Window and coverage settings.  Defaults represent 12-1/6-1 momentum,
        three-month volatility, six-month beta, and 20-day liquidity.

    Returns
    -------
    pandas.DataFrame
        One row per membership security and month.  The final month is retained
        with a missing forward label when no next execution month exists.
    """

    cfg = config or FeatureConfig()
    prices, financials, members = _prepare_inputs(market, fundamentals, memberships)
    if benchmark_symbol is not None:
        benchmark_symbol = str(benchmark_symbol)
    if group_col is not None and group_col not in members.columns:
        raise ValueError(f"group_col {group_col!r} not found in memberships")

    calendar = _monthly_calendar(prices["date"], cfg.signal_lag_trading_days)
    if calendar.empty:
        return pd.DataFrame()
    by_symbol = {symbol: group for symbol, group in prices.groupby("symbol", sort=False)}
    close_lookup = prices.set_index(["date", "symbol"])["close_adj"]
    rows: list[dict[str, object]] = []

    for dates in calendar.itertuples(index=False):
        signal_date = pd.Timestamp(dates.signal_date)
        execution_date = pd.Timestamp(dates.execution_date)
        next_execution_date = (
            pd.Timestamp(dates.next_execution_date) if pd.notna(dates.next_execution_date) else pd.NaT
        )
        snapshot = _membership_asof(members, signal_date)
        if snapshot.empty:
            continue
        benchmark_returns = _benchmark_returns(prices, snapshot, benchmark_symbol)
        member_symbols = snapshot["symbol"].astype(str).tolist()
        financial_history = _fundamentals_asof(financials, member_symbols, signal_date)

        if benchmark_symbol is not None:
            benchmark_start = _close_on(close_lookup, execution_date, benchmark_symbol)
            benchmark_end = _close_on(close_lookup, next_execution_date, benchmark_symbol)
            benchmark_forward = (
                benchmark_end / benchmark_start - 1
                if np.isfinite(benchmark_start) and np.isfinite(benchmark_end) and benchmark_start > 0
                else float("nan")
            )
        else:
            benchmark_forward = float("nan")

        month_rows: list[dict[str, object]] = []
        for _, membership in snapshot.iterrows():
            symbol = str(membership["symbol"])
            security = by_symbol.get(symbol)
            if security is None:
                continue
            record: dict[str, object] = {
                "signal_date": signal_date,
                "execution_date": execution_date,
                "next_execution_date": next_execution_date,
                "membership_snapshot_date": membership["snapshot_date"],
                "membership_available_date": membership["available_date"],
                "symbol": symbol,
                "benchmark_weight": float(membership["benchmark_weight"]),
            }
            if group_col is not None:
                record[group_col] = membership[group_col]
            record.update(_price_features_asof(security, benchmark_returns, signal_date, cfg))

            current, prior, report_count = financial_history[symbol]
            record.update(_fundamental_features(current, prior))
            record["financial_report_count"] = report_count
            record["financial_report_date"] = current["report_date"] if current is not None else pd.NaT
            record["financial_notice_date"] = current["notice_date"] if current is not None else pd.NaT
            record["financial_effective_date"] = current["effective_date"] if current is not None else pd.NaT
            record["prior_financial_report_date"] = prior["report_date"] if prior is not None else pd.NaT
            if current is not None:
                excluded = {"symbol", "report_date", "notice_date", "available_date", "effective_date"}
                for column in financials.columns:
                    if column not in excluded:
                        record[f"fin_{column}"] = current[column]

            start_close = _close_on(close_lookup, execution_date, symbol)
            end_close = _close_on(close_lookup, next_execution_date, symbol)
            record["label_start_close_adj"] = start_close
            record["label_end_close_adj"] = end_close
            record["forward_return_1m"] = (
                end_close / start_close - 1
                if np.isfinite(start_close) and np.isfinite(end_close) and start_close > 0
                else float("nan")
            )
            record["benchmark_forward_return_1m"] = benchmark_forward
            month_rows.append(record)

        if benchmark_symbol is None and month_rows:
            month_frame = pd.DataFrame.from_records(month_rows)
            valid = month_frame["forward_return_1m"].notna()
            weights = month_frame.loc[valid, "benchmark_weight"].astype(float)
            if not weights.empty:
                if weights.sum() <= 0:
                    weights[:] = 1.0
                benchmark_forward = float(
                    np.average(month_frame.loc[valid, "forward_return_1m"], weights=weights)
                )
                for record in month_rows:
                    record["benchmark_forward_return_1m"] = benchmark_forward
        for record in month_rows:
            forward = float(record["forward_return_1m"])
            benchmark_forward_value = float(record["benchmark_forward_return_1m"])
            record["forward_excess_return_1m"] = (
                forward - benchmark_forward_value
                if np.isfinite(forward) and np.isfinite(benchmark_forward_value)
                else float("nan")
            )
        rows.extend(month_rows)

    output = pd.DataFrame.from_records(rows)
    if output.empty:
        return output

    output["price_history_ok"] = output[list(PRICE_FEATURES)].notna().all(axis=1)
    output["fundamental_history_ok"] = output[list(FUNDAMENTAL_FEATURES)].notna().all(axis=1)
    output["minimum_history_ok"] = output["price_history_ok"] & output["fundamental_history_ok"]
    transform_inputs = [*NEUTRALIZED_FEATURES, "adv_20d"]
    output["raw_feature_coverage"] = output[transform_inputs].notna().mean(axis=1)
    output["row_coverage_ok"] = output["raw_feature_coverage"].ge(cfg.min_row_feature_coverage)

    transformed: list[pd.DataFrame] = []
    for _, month in output.groupby("execution_date", sort=True):
        sample = month.copy()
        total = len(sample)
        sample["adv_20d_z"] = robust_mad_zscore(sample["adv_20d"], clip=cfg.mad_clip)
        for feature in NEUTRALIZED_FEATURES:
            coverage = float(sample[feature].notna().sum() / total) if total else 0.0
            sample[f"cs_coverage_{feature}"] = coverage
            if coverage < cfg.min_cross_section_coverage:
                sample[f"{feature}_z"] = np.nan
                continue
            groups = sample[group_col] if group_col is not None else None
            sample[f"{feature}_z"] = cross_sectional_neutralize(
                sample[feature],
                sample["adv_20d"],
                groups=groups,
                mad_clip=cfg.mad_clip,
                min_observations=cfg.min_cross_section,
            )
        transformed.append(sample)
    output = pd.concat(transformed, ignore_index=True)
    output["eligible_for_scoring"] = (
        output["minimum_history_ok"]
        & output["row_coverage_ok"]
        & output[[f"{feature}_z" for feature in NEUTRALIZED_FEATURES]].notna().all(axis=1)
    )
    # Concise aliases match the evaluation module while the explicit ``_1m``
    # columns retain the label horizon in exported research tables.
    output["forward_return"] = output["forward_return_1m"]
    output["forward_excess_return"] = output["forward_excess_return_1m"]
    return output.sort_values(["execution_date", "symbol"]).reset_index(drop=True)
