from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


@dataclass(frozen=True)
class EvaluationResult:
    monthly_ic: pd.DataFrame
    signal_summary: pd.DataFrame
    quantile_returns: pd.DataFrame
    quantile_summary: pd.DataFrame


def assign_research_split(
    dates: pd.Series,
    design_end: str,
    validation_end: str,
) -> pd.Series:
    """Label chronological research partitions without random shuffling."""

    values = pd.to_datetime(dates)
    design_cut = pd.Timestamp(design_end)
    validation_cut = pd.Timestamp(validation_end)
    return pd.Series(
        np.select(
            [values.le(design_cut), values.le(validation_cut)],
            ["design", "validation"],
            default="final_holdout",
        ),
        index=dates.index,
        dtype="string",
    )


def _hac_mean_test(values: pd.Series, lags: int) -> tuple[float, float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) < max(6, lags + 3):
        return float(clean.mean()) if len(clean) else float("nan"), float("nan"), float("nan")
    result = sm.OLS(clean.to_numpy(), np.ones((len(clean), 1))).fit(
        cov_type="HAC", cov_kwds={"maxlags": min(lags, len(clean) - 2)}
    )
    return float(result.params[0]), float(result.tvalues[0]), float(result.pvalues[0])


def _benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    """Benjamini-Hochberg adjusted p-values for the documented signal set."""

    result = pd.Series(np.nan, index=p_values.index, dtype=float)
    valid = p_values.dropna().clip(0, 1)
    if valid.empty:
        return result
    ordered = valid.sort_values()
    n = len(ordered)
    adjusted = ordered.to_numpy() * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result.loc[ordered.index] = np.minimum(adjusted, 1.0)
    return result


def monthly_information_coefficients(
    panel: pd.DataFrame,
    signal_columns: list[str],
    *,
    date_column: str = "execution_date",
    target_column: str = "forward_excess_return",
    min_cross_section: int = 10,
) -> pd.DataFrame:
    """Compute cross-sectional Pearson and Spearman ICs month by month."""

    required = {date_column, target_column, *signal_columns}
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"IC panel is missing columns: {sorted(missing)}")

    records: list[dict[str, object]] = []
    for date, group in panel.groupby(date_column, sort=True):
        for signal in signal_columns:
            sample = group[[signal, target_column]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(sample) < min_cross_section or sample[signal].nunique() < 3:
                continue
            pearson, pearson_p = stats.pearsonr(sample[signal], sample[target_column])
            rank_ic, rank_p = stats.spearmanr(sample[signal], sample[target_column])
            records.append(
                {
                    date_column: pd.Timestamp(date),
                    "signal": signal,
                    "observations": int(len(sample)),
                    "pearson_ic": float(pearson),
                    "pearson_p_value": float(pearson_p),
                    "rank_ic": float(rank_ic),
                    "rank_ic_p_value": float(rank_p),
                }
            )
    return pd.DataFrame.from_records(records)


def summarize_information_coefficients(
    monthly_ic: pd.DataFrame,
    *,
    hac_lags: int = 3,
    split_column: str | None = None,
) -> pd.DataFrame:
    if monthly_ic.empty:
        return pd.DataFrame()
    grouping = ["signal"] if split_column is None else [split_column, "signal"]
    records: list[dict[str, object]] = []
    for keys, group in monthly_ic.groupby(grouping, dropna=False, sort=True):
        keys_tuple = keys if isinstance(keys, tuple) else (keys,)
        rank = group["rank_ic"].dropna()
        mean_ic, t_stat, p_value = _hac_mean_test(rank, hac_lags)
        record: dict[str, object] = {
            "months": int(len(rank)),
            "mean_rank_ic": mean_ic,
            "rank_ic_std": float(rank.std(ddof=1)) if len(rank) > 1 else float("nan"),
            "rank_ic_ir": float(rank.mean() / rank.std(ddof=1))
            if len(rank) > 1 and rank.std(ddof=1) > 0
            else float("nan"),
            "positive_rank_ic_ratio": float((rank > 0).mean()) if len(rank) else float("nan"),
            "hac_t_stat": t_stat,
            "hac_p_value": p_value,
        }
        for name, value in zip(grouping, keys_tuple, strict=True):
            record[name] = value
        records.append(record)
    summary = pd.DataFrame.from_records(records)
    if not summary.empty:
        summary["bh_fdr_p_value"] = np.nan
        if split_column is None:
            adjusted = _benjamini_hochberg(summary.set_index("signal")["hac_p_value"])
            summary["bh_fdr_p_value"] = adjusted.reindex(summary["signal"]).to_numpy()
        else:
            # Multiple-testing control belongs inside each chronological
            # research partition.  Pooling design and untouched holdout
            # p-values would make the holdout threshold depend on earlier
            # exploratory observations.
            for split, rows in summary.groupby(split_column, dropna=False).groups.items():
                block = summary.loc[rows].set_index("signal")["hac_p_value"]
                adjusted = _benjamini_hochberg(block)
                summary.loc[rows, "bh_fdr_p_value"] = adjusted.reindex(
                    summary.loc[rows, "signal"]
                ).to_numpy()
    return summary


def quantile_portfolio_returns(
    panel: pd.DataFrame,
    signal_columns: list[str],
    *,
    date_column: str = "execution_date",
    return_column: str = "forward_return",
    requested_quantiles: int = 5,
    min_cross_section: int = 15,
) -> pd.DataFrame:
    """Create equal-weight signal-sorted portfolios for research diagnostics."""

    records: list[dict[str, object]] = []
    for date, group in panel.groupby(date_column, sort=True):
        for signal in signal_columns:
            sample = group[["symbol", signal, return_column]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(sample) < min_cross_section or sample[signal].nunique() < 3:
                continue
            quantiles = requested_quantiles if len(sample) >= requested_quantiles * 5 else 3
            ranked = sample[signal].rank(method="first")
            sample = sample.assign(quantile=pd.qcut(ranked, q=quantiles, labels=False) + 1)
            by_quantile = sample.groupby("quantile")[return_column].mean()
            for quantile, value in by_quantile.items():
                records.append(
                    {
                        date_column: pd.Timestamp(date),
                        "signal": signal,
                        "quantiles": int(quantiles),
                        "leg": f"Q{int(quantile)}",
                        "return": float(value),
                        "names": int((sample["quantile"] == quantile).sum()),
                    }
                )
            records.append(
                {
                    date_column: pd.Timestamp(date),
                    "signal": signal,
                    "quantiles": int(quantiles),
                    "leg": "top_minus_bottom",
                    "return": float(by_quantile.loc[quantiles] - by_quantile.loc[1]),
                    "names": int(len(sample)),
                }
            )
    return pd.DataFrame.from_records(records)


def summarize_quantile_returns(
    quantile_returns: pd.DataFrame,
    *,
    hac_lags: int = 3,
    split_column: str | None = None,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    if quantile_returns.empty:
        return pd.DataFrame()
    grouping = ["signal", "leg"] if split_column is None else [split_column, "signal", "leg"]
    for keys, group in quantile_returns.groupby(grouping, dropna=False, sort=True):
        keys_tuple = keys if isinstance(keys, tuple) else (keys,)
        values = group["return"].dropna()
        mean_return, t_stat, p_value = _hac_mean_test(values, hac_lags)
        record: dict[str, object] = {
            "months": int(len(values)),
            "mean_monthly_return": mean_return,
            "annualized_arithmetic_return": float(mean_return * 12),
            "annualized_volatility": float(values.std(ddof=1) * np.sqrt(12)) if len(values) > 1 else float("nan"),
            "hac_t_stat": t_stat,
            "hac_p_value": p_value,
            "positive_month_ratio": float((values > 0).mean()) if len(values) else float("nan"),
        }
        for name, value in zip(grouping, keys_tuple, strict=True):
            record[name] = value
        records.append(record)
    return pd.DataFrame.from_records(records)


def evaluate_signals(
    panel: pd.DataFrame,
    signal_columns: list[str],
    *,
    design_end: str,
    validation_end: str,
    hac_lags: int = 3,
    requested_quantiles: int = 5,
    min_cross_section: int = 15,
) -> EvaluationResult:
    work = panel.copy()
    work["research_split"] = assign_research_split(work["execution_date"], design_end, validation_end)
    monthly_ic = monthly_information_coefficients(
        work,
        signal_columns,
        min_cross_section=min_cross_section,
    )
    if not monthly_ic.empty:
        split_map = work[["execution_date", "research_split"]].drop_duplicates("execution_date")
        monthly_ic = monthly_ic.merge(split_map, on="execution_date", how="left", validate="many_to_one")
    overall = summarize_information_coefficients(monthly_ic, hac_lags=hac_lags)
    by_split = summarize_information_coefficients(monthly_ic, hac_lags=hac_lags, split_column="research_split")
    overall.insert(0, "research_split", "all")
    signal_summary = pd.concat([overall, by_split], ignore_index=True, sort=False)

    quantiles = quantile_portfolio_returns(
        work,
        signal_columns,
        requested_quantiles=requested_quantiles,
        min_cross_section=min_cross_section,
    )
    if not quantiles.empty:
        split_map = work[["execution_date", "research_split"]].drop_duplicates("execution_date")
        quantiles = quantiles.merge(split_map, on="execution_date", how="left", validate="many_to_one")
    quantile_overall = summarize_quantile_returns(quantiles, hac_lags=hac_lags)
    if not quantile_overall.empty:
        quantile_overall.insert(0, "research_split", "all")
    quantile_by_split = summarize_quantile_returns(
        quantiles,
        hac_lags=hac_lags,
        split_column="research_split",
    )
    quantile_summary = pd.concat(
        [quantile_overall, quantile_by_split], ignore_index=True, sort=False
    )
    return EvaluationResult(monthly_ic, signal_summary, quantiles, quantile_summary)
