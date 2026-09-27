"""End-to-end integration pipeline for the systematic-equity prototype.

The pipeline consumes frozen raw Parquet assets, builds point-in-time monthly
features, evaluates the pre-registered signals, runs the benchmark-relative
portfolio under every configured cost multiplier, and writes deterministic
research artifacts.  Downloading remains a separate data-layer concern.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .io import write_frame
from .systematic_data import dataframe_sha256
from .systematic_evaluation import (
    assign_research_split,
    evaluate_signals,
    summarize_quantile_returns,
)
from .systematic_features import FeatureConfig, build_monthly_systematic_features
from .systematic_portfolio import run_long_only_backtest


SIGNAL_COLUMNS = [
    "price_momentum_score",
    "operating_quality_score",
    "fundamental_momentum_score",
    "low_risk_score",
    "composite_score",
]

FAMILY_COMPONENTS = {
    "price_momentum": ["momentum_12_1_z", "momentum_6_1_z"],
    "operating_quality": ["quality_raw_z"],
    "fundamental_momentum": ["growth_raw_z", "fundamental_momentum_raw_z"],
    "low_risk": ["volatility_3m_z", "idio_volatility_6m_z"],
}


def load_systematic_config(path: str | Path) -> tuple[dict[str, Any], Path, Path]:
    """Load and minimally validate the systematic YAML configuration."""

    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    required = {
        "project",
        "universe",
        "features",
        "evaluation",
        "portfolio",
        "transaction_costs",
    }
    if not isinstance(raw, dict) or required.difference(raw):
        raise ValueError(f"Invalid systematic configuration; missing {sorted(required.difference(raw or {}))}")
    root = config_path.parent.parent
    return raw, config_path, root


def _normalise_symbol(series: pd.Series) -> pd.Series:
    extracted = series.astype(str).str.extract(r"(\d{1,6})", expand=False)
    if extracted.isna().any():
        bad = series.loc[extracted.isna()].astype(str).unique().tolist()
        raise ValueError(f"Invalid security symbols: {bad[:10]}")
    return extracted.str.zfill(6)


def _canonical_market(market: pd.DataFrame) -> pd.DataFrame:
    aliases: dict[str, str] = {}
    if "close_adj" not in market.columns and "close_adjusted" in market.columns:
        aliases["close_adjusted"] = "close_adj"
    if "volume" not in market.columns and "volume_raw" in market.columns:
        aliases["volume_raw"] = "volume"
    result = market.rename(columns=aliases).copy()
    required = {"date", "symbol", "close_adj", "close_raw", "high_raw", "low_raw", "volume"}
    missing = required.difference(result.columns)
    if missing:
        raise ValueError(f"systematic market data missing columns: {sorted(missing)}")
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["symbol"] = _normalise_symbol(result["symbol"])
    return result.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)


def _load_industry_groups(root: Path, memberships: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = root / "data" / "manual" / "systematic_industry_groups.csv"
    members = memberships.copy()
    members["symbol"] = _normalise_symbol(members["symbol"])
    warning: str | None = None
    excluded_symbols: list[str] = []
    if path.exists():
        groups = pd.read_csv(path, dtype={"symbol": str})
        required = {"symbol", "industry_group"}
        missing = required.difference(groups.columns)
        if missing:
            raise ValueError(f"{path} missing columns: {sorted(missing)}")
        keep_columns = ["symbol", "industry_group"] + (
            ["include"] if "include" in groups.columns else []
        )
        groups = groups[keep_columns].copy()
        groups["symbol"] = _normalise_symbol(groups["symbol"])
        groups["industry_group"] = groups["industry_group"].astype("string").str.strip()
        if groups["symbol"].duplicated().any():
            duplicates = groups.loc[groups["symbol"].duplicated(keep=False), "symbol"].unique().tolist()
            raise ValueError(f"Duplicate industry mappings: {duplicates[:10]}")
        if "include" in groups.columns:
            include = groups["include"]
            if include.dtype != bool:
                include = include.astype(str).str.strip().str.lower().map(
                    {"true": True, "false": False, "1": True, "0": False}
                )
            if include.isna().any():
                raise ValueError(f"{path} contains invalid include values")
            groups["include"] = include.astype(bool)
            excluded_symbols = sorted(groups.loc[~groups["include"], "symbol"].tolist())
            members = members.loc[~members["symbol"].isin(excluded_symbols)].copy()
        members = members.merge(
            groups.drop(columns=["include"], errors="ignore"),
            on="symbol",
            how="left",
            validate="many_to_one",
        )
    else:
        members["industry_group"] = "unclassified"
        warning = (
            "data/manual/systematic_industry_groups.csv was absent; all securities were assigned "
            "to the explicit unclassified group and no industry-neutrality claim should be made."
        )
    members["industry_group"] = members["industry_group"].fillna("unclassified").astype(str)
    unmapped = int(members.loc[members["industry_group"].eq("unclassified"), "symbol"].nunique())
    metadata = {
        "path": str(path.relative_to(root)),
        "file_present": bool(path.exists()),
        "unique_groups": sorted(members["industry_group"].unique().tolist()),
        "unclassified_symbols": unmapped,
        "excluded_symbols": excluded_symbols,
        "warning": warning,
    }
    return members, metadata


def _feature_config(
    raw: Mapping[str, Any], *, signal_lag_trading_days: int = 1
) -> FeatureConfig:
    features = raw["features"]
    universe = raw["universe"]
    return FeatureConfig(
        momentum_12m_days=int(features["momentum_12_1_long_days"]),
        momentum_6m_days=int(features["momentum_6_1_long_days"]),
        momentum_skip_days=int(features["momentum_12_1_skip_days"]),
        volatility_window_days=int(features["volatility_days"]),
        beta_window_days=int(features["beta_days"]),
        liquidity_window_days=int(features["liquidity_days"]),
        mad_clip=float(features["mad_clip"]),
        min_cross_section=int(universe["min_cross_section"]),
        min_cross_section_coverage=float(features["min_family_coverage"]),
        min_row_feature_coverage=float(features["min_family_coverage"]),
        signal_lag_trading_days=signal_lag_trading_days,
    )


def build_composite_signals(panel: pd.DataFrame, raw: Mapping[str, Any]) -> pd.DataFrame:
    """Construct the four pre-registered families and equal-weight composite."""

    result = panel.copy()
    minimum_coverage = float(raw["features"]["min_family_coverage"])
    family_weights = {str(key): float(value) for key, value in raw["features"]["family_weights"].items()}
    missing_weights = set(FAMILY_COMPONENTS).difference(family_weights)
    if missing_weights:
        raise ValueError(f"Missing configured family weights: {sorted(missing_weights)}")
    if any(value < 0 for value in family_weights.values()) or sum(family_weights.values()) <= 0:
        raise ValueError("family weights must be non-negative with a positive sum")

    for family, components in FAMILY_COMPONENTS.items():
        missing = set(components).difference(result.columns)
        if missing:
            raise ValueError(f"Feature panel missing {family} components: {sorted(missing)}")
        values = result[components].copy()
        if family == "low_risk":
            values = -values
        coverage = values.notna().mean(axis=1)
        result[f"{family}_coverage"] = coverage
        result[f"{family}_score"] = values.mean(axis=1, skipna=True).where(coverage.ge(minimum_coverage))

    score_columns = [f"{family}_score" for family in FAMILY_COMPONENTS]
    result["available_signal_families"] = result[score_columns].notna().sum(axis=1)
    weighted_sum = pd.Series(0.0, index=result.index)
    available_weight = pd.Series(0.0, index=result.index)
    for family in FAMILY_COMPONENTS:
        column = f"{family}_score"
        available = result[column].notna()
        weighted_sum.loc[available] += result.loc[available, column] * family_weights[family]
        available_weight.loc[available] += family_weights[family]
    result["composite_score"] = weighted_sum.div(available_weight.where(available_weight.gt(0)))
    minimum_families = int(raw["features"]["min_composite_families"])
    result.loc[result["available_signal_families"].lt(minimum_families), "composite_score"] = np.nan

    minimum_history = int(raw["universe"]["min_price_history_days"])
    minimum_adv = float(raw["universe"]["min_adv20_rmb"])
    result["systematic_eligible"] = (
        result["market_history_days"].ge(minimum_history)
        & result["adv_20d"].ge(minimum_adv)
        & result["composite_score"].notna()
    )
    result["market_beta_126d"] = result["beta_6m"]
    result["adv20_rmb"] = result["adv_20d"]
    result["volatility_63d"] = result["volatility_3m"] / math.sqrt(252)
    return result


def _split_quantile_summary(quantiles: pd.DataFrame, hac_lags: int) -> pd.DataFrame:
    overall = summarize_quantile_returns(quantiles, hac_lags=hac_lags)
    if not overall.empty:
        overall.insert(0, "research_split", "all")
    pieces = [overall]
    if not quantiles.empty and "research_split" in quantiles.columns:
        for split, group in quantiles.groupby("research_split", sort=True):
            summary = summarize_quantile_returns(group, hac_lags=hac_lags)
            if not summary.empty:
                summary.insert(0, "research_split", str(split))
                pieces.append(summary)
    nonempty = [piece for piece in pieces if not piece.empty]
    return pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame()


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [_json_ready(record) for record in frame.to_dict("records")]


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def _metric(
    frame: pd.DataFrame,
    *,
    split: str,
    signal: str | None = None,
    leg: str | None = None,
    column: str,
) -> float | None:
    if frame.empty:
        return None
    mask = frame["research_split"].astype(str).eq(split)
    if signal is not None:
        mask &= frame["signal"].astype(str).eq(signal)
    if leg is not None:
        mask &= frame["leg"].astype(str).eq(leg)
    values = pd.to_numeric(frame.loc[mask, column], errors="coerce").dropna()
    return float(values.iloc[0]) if len(values) else None


def _failure_checks(
    signal_summary: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    *,
    lag_signal_summary: pd.DataFrame | None = None,
    lag_quantile_summary: pd.DataFrame | None = None,
    lag_portfolio_summary: pd.DataFrame | None = None,
) -> dict[str, Any]:
    rank_ic = _metric(
        signal_summary,
        split="final_holdout",
        signal="composite_score",
        column="mean_rank_ic",
    )
    spread = _metric(
        quantile_summary,
        split="final_holdout",
        signal="composite_score",
        leg="top_minus_bottom",
        column="mean_monthly_return",
    )
    baseline_active = _metric(
        portfolio_summary.loc[portfolio_summary["cost_multiplier"].eq(1.0)],
        split="final_holdout",
        column="annualized_active_return",
    )
    baseline_ir = _metric(
        portfolio_summary.loc[portfolio_summary["cost_multiplier"].eq(1.0)],
        split="final_holdout",
        column="information_ratio",
    )
    high_cost_active = _metric(
        portfolio_summary.loc[portfolio_summary["cost_multiplier"].eq(2.0)],
        split="final_holdout",
        column="annualized_active_return",
    )
    lag_rank_ic = (
        _metric(
            lag_signal_summary,
            split="final_holdout",
            signal="composite_score",
            column="mean_rank_ic",
        )
        if lag_signal_summary is not None
        else None
    )
    lag_spread = (
        _metric(
            lag_quantile_summary,
            split="final_holdout",
            signal="composite_score",
            leg="top_minus_bottom",
            column="mean_monthly_return",
        )
        if lag_quantile_summary is not None
        else None
    )
    lag_active = (
        _metric(
            lag_portfolio_summary,
            split="final_holdout",
            column="annualized_active_return",
        )
        if lag_portfolio_summary is not None
        else None
    )
    checks = {
        "final_holdout_mean_rank_ic_positive": rank_ic is not None and rank_ic > 0,
        "final_holdout_top_minus_bottom_positive": spread is not None and spread > 0,
        "baseline_final_holdout_active_return_positive": baseline_active is not None and baseline_active > 0,
        "baseline_final_holdout_information_ratio_positive": baseline_ir is not None and baseline_ir > 0,
        "double_cost_final_holdout_active_return_positive": high_cost_active is not None and high_cost_active > 0,
        "additional_lag_final_holdout_rank_ic_positive": lag_rank_ic is not None and lag_rank_ic > 0,
        "additional_lag_final_holdout_top_minus_bottom_positive": lag_spread is not None and lag_spread > 0,
        "additional_lag_final_holdout_active_return_positive": lag_active is not None and lag_active > 0,
    }
    passed = all(checks.values())
    return {
        "metrics": {
            "final_holdout_composite_mean_rank_ic": rank_ic,
            "final_holdout_composite_top_minus_bottom_mean_monthly_return": spread,
            "baseline_final_holdout_annualized_active_return": baseline_active,
            "baseline_final_holdout_information_ratio": baseline_ir,
            "double_cost_final_holdout_annualized_active_return": high_cost_active,
            "additional_lag_final_holdout_composite_mean_rank_ic": lag_rank_ic,
            "additional_lag_final_holdout_composite_top_minus_bottom_mean_monthly_return": lag_spread,
            "additional_lag_final_holdout_annualized_active_return": lag_active,
        },
        "checks": checks,
        "all_available_checks_passed": passed,
        "conclusion": (
            "preliminary evidence passed the registered numerical checks; public-data limitations still preclude a production-alpha claim"
            if passed
            else "the composite is not validated as persistent alpha under the pre-registered failure rules"
        ),
    }


def _active_contribution_diagnostics(
    weights: pd.DataFrame,
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attribute gross active returns and summarize concentration.

    This is a holdings-based contribution audit, not a counterfactual
    re-optimization.  It answers whether one name or one manually assigned
    broad group mechanically dominates the simulated active portfolio.
    """

    if weights.empty:
        return pd.DataFrame(), {}
    labels = panel[
        ["execution_date", "symbol", "forward_return", "research_split"]
    ].drop_duplicates(["execution_date", "symbol"])
    work = weights.merge(
        labels,
        on=["execution_date", "symbol"],
        how="left",
        validate="one_to_one",
    )
    work["active_return_contribution"] = (
        pd.to_numeric(work["active_weight"], errors="coerce")
        * pd.to_numeric(work["forward_return"], errors="coerce")
    ).fillna(0.0)
    final = work.loc[work["research_split"].eq("final_holdout")].copy()
    by_name = (
        final.groupby("symbol", as_index=False)
        .agg(
            signed_active_contribution=("active_return_contribution", "sum"),
            absolute_active_contribution=(
                "active_return_contribution",
                lambda values: float(values.abs().sum()),
            ),
            months=("execution_date", "nunique"),
        )
        .sort_values("absolute_active_contribution", ascending=False, kind="mergesort")
        .reset_index(drop=True)
    )
    total_absolute = float(by_name["absolute_active_contribution"].sum())
    by_name["share_of_absolute_active_contribution"] = (
        by_name["absolute_active_contribution"] / total_absolute
        if total_absolute > 0
        else 0.0
    )
    group_exposure = (
        final.groupby(["execution_date", "industry_group"], as_index=False)["active_weight"]
        .sum()
    )
    top = by_name.iloc[0] if len(by_name) else None
    summary = {
        "method": "sum of holdings-based gross active-return contributions; no re-optimization",
        "top_symbol": str(top["symbol"]) if top is not None else None,
        "top_symbol_share_of_absolute_active_contribution": (
            float(top["share_of_absolute_active_contribution"]) if top is not None else None
        ),
        "maximum_absolute_single_name_active_weight": (
            float(final["active_weight"].abs().max()) if len(final) else None
        ),
        "maximum_absolute_group_active_weight": (
            float(group_exposure["active_weight"].abs().max()) if len(group_exposure) else None
        ),
    }
    return by_name, summary


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    available = [column for column in columns if column in frame.columns]
    if frame.empty or not available:
        return "No eligible observations were available."
    return frame[available].to_markdown(index=False, floatfmt=".4f")


def _write_systematic_figures(
    root: Path,
    monthly_ic: pd.DataFrame,
    signal_summary: pd.DataFrame,
    portfolio_monthly: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
) -> dict[str, str]:
    """Create compact deterministic figures for GitHub rendering."""

    figure_dir = root / "reports" / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    plt.rcParams.update({"figure.dpi": 140, "font.size": 9})

    baseline = portfolio_monthly.loc[portfolio_monthly["cost_multiplier"].eq(1.0)].copy()
    baseline = baseline.sort_values("execution_date")
    if not baseline.empty:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        observed_dates = pd.to_datetime(baseline["execution_date"])
        dates = pd.DatetimeIndex([observed_dates.iloc[0] - pd.Timedelta(days=1), *observed_dates])
        gross_curve = np.r_[1.0, (1 + baseline["strategy_gross_return"]).cumprod().to_numpy()]
        net_curve = np.r_[1.0, (1 + baseline["strategy_net_return"]).cumprod().to_numpy()]
        benchmark_curve = np.r_[1.0, (1 + baseline["benchmark_return"]).cumprod().to_numpy()]
        ax.plot(dates, gross_curve, label="Strategy gross", lw=1.5)
        ax.plot(dates, net_curve, label="Strategy net", lw=1.8)
        ax.plot(dates, benchmark_curve, label="Battery-universe benchmark", lw=1.5)
        for boundary in [pd.Timestamp("2023-06-30"), pd.Timestamp("2024-06-30")]:
            ax.axvline(boundary, color="0.55", lw=0.8, ls="--")
        ax.set_title("Benchmark-relative long-only simulation (baseline costs)")
        ax.set_ylabel("Growth of RMB 1")
        ax.grid(alpha=0.2)
        ax.legend(frameon=False, ncol=3, loc="best")
        fig.autofmt_xdate()
        fig.tight_layout()
        path = figure_dir / "systematic_cumulative_performance.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        outputs["cumulative_performance_figure"] = str(path.relative_to(root))

    ic = signal_summary.loc[
        signal_summary["research_split"].isin(["design", "validation", "final_holdout"])
    ].copy()
    if not ic.empty:
        pivot = ic.pivot(index="signal", columns="research_split", values="mean_rank_ic")
        pivot = pivot.reindex(columns=["design", "validation", "final_holdout"])
        fig, ax = plt.subplots(figsize=(9, 5.2))
        pivot.plot(kind="bar", ax=ax, width=0.78)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title("Mean monthly Rank IC by chronological split")
        ax.set_ylabel("Mean Spearman Rank IC")
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.2)
        ax.legend(title="", frameon=False)
        fig.tight_layout()
        path = figure_dir / "systematic_rank_ic_by_split.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        outputs["rank_ic_split_figure"] = str(path.relative_to(root))

    composite_ic = monthly_ic.loc[monthly_ic["signal"].eq("composite_score")].copy()
    if not composite_ic.empty:
        composite_ic = composite_ic.sort_values("execution_date")
        fig, ax = plt.subplots(figsize=(9, 4.4))
        dates = pd.to_datetime(composite_ic["execution_date"])
        values = composite_ic["rank_ic"]
        colors = np.where(values.ge(0), "#2a9d8f", "#e76f51")
        ax.bar(dates, values, width=18, color=colors, alpha=0.85)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title("Composite signal: monthly cross-sectional Rank IC")
        ax.set_ylabel("Spearman Rank IC")
        ax.grid(axis="y", alpha=0.2)
        fig.autofmt_xdate()
        fig.tight_layout()
        path = figure_dir / "systematic_composite_monthly_rank_ic.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        outputs["monthly_rank_ic_figure"] = str(path.relative_to(root))

    cost = portfolio_summary.loc[
        portfolio_summary["research_split"].eq("final_holdout")
    ].sort_values("cost_multiplier")
    if not cost.empty:
        fig, ax = plt.subplots(figsize=(7.2, 4.5))
        ax.bar(
            cost["cost_multiplier"].astype(str),
            cost["annualized_active_return"] * 100,
            color="#457b9d",
        )
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title("Final-holdout active return under cost sensitivity")
        ax.set_xlabel("Cost multiplier")
        ax.set_ylabel("Annualized active return (%)")
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        path = figure_dir / "systematic_cost_sensitivity.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        outputs["cost_sensitivity_figure"] = str(path.relative_to(root))
    return outputs


def _write_report(
    path: Path,
    summary: Mapping[str, Any],
    signal_summary: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
) -> None:
    project = summary["project"]
    splits = summary["time_splits"]
    limitations = summary["disclosures"]
    failure_metrics = summary["pre_registered_failure_checks"]["metrics"]
    concentration = summary["active_contribution_concentration"]
    top_share = concentration.get("top_symbol_share_of_absolute_active_contribution")
    max_group = concentration.get("maximum_absolute_group_active_weight")
    lines = [
        f"# {project['title']}",
        "",
        f"**Research cutoff:** {project['research_as_of']}  ",
        "**Status:** independent public-data systematic-research prototype.",
        "",
        "## Executive conclusion",
        "",
        str(summary["pre_registered_failure_checks"]["conclusion"]).capitalize() + ".",
        "",
        f"Final-holdout composite mean Rank IC is "
        f"{failure_metrics['final_holdout_composite_mean_rank_ic']:.3f}, but the "
        f"top-minus-bottom diagnostic is "
        f"{failure_metrics['final_holdout_composite_top_minus_bottom_mean_monthly_return']:.2%} per month "
        f"and baseline-cost annualized active return is "
        f"{failure_metrics['baseline_final_holdout_annualized_active_return']:.2%}.",
        "",
        "This report distinguishes signal diagnostics from an implementable long-only simulation. "
        "The top-minus-bottom portfolios are diagnostics only; historical borrow data are unavailable.",
        "",
        "## Point-in-time design",
        "",
        f"- Design period ends {splits['design_end']}.",
        f"- Validation period ends {splits['validation_end']}.",
        f"- Final holdout ends {splits['final_holdout_end']}.",
        f"- Features use data no later than the signal date; execution is the following month-end trading date.",
        f"- Eligible panel: {summary['panel']['eligible_rows']} rows across "
        f"{summary['panel']['eligible_months']} months and {summary['panel']['eligible_symbols']} securities.",
        "",
        "## Signal IC results",
        "",
        _markdown_table(
            signal_summary,
            [
                "research_split",
                "signal",
                "months",
                "mean_rank_ic",
                "rank_ic_ir",
                "hac_t_stat",
                "hac_p_value",
                "bh_fdr_p_value",
            ],
        ),
        "",
        "## Quantile diagnostics",
        "",
        _markdown_table(
            quantile_summary.loc[quantile_summary.get("leg", pd.Series(dtype=str)).eq("top_minus_bottom")],
            [
                "research_split",
                "signal",
                "months",
                "mean_monthly_return",
                "annualized_arithmetic_return",
                "hac_t_stat",
            ],
        ),
        "",
        "## Long-only portfolio and cost sensitivity",
        "",
        _markdown_table(
            portfolio_summary,
            [
                "cost_multiplier",
                "research_split",
                "months",
                "annualized_net_return",
                "annualized_active_return",
                "information_ratio",
                "max_drawdown",
                "average_one_way_turnover",
                "annualized_cost_drag_arithmetic",
            ],
        ),
        "",
        "## Timing and concentration robustness",
        "",
        f"- The timing stress moves the signal cutoff to {summary['additional_signal_lag']['signal_lag_trading_days']} "
        "trading days before execution without moving the return window.",
        f"- Largest final-holdout single-name share of absolute active contribution: "
        f"{top_share:.1%}.",
        f"- Maximum absolute final-holdout broad-group active weight: "
        f"{max_group:.2%}.",
        "- The contribution audit is holdings-based and does not claim a full leave-one-name-out re-optimization.",
        "",
        "## Pre-registered checks",
        "",
    ]
    for name, passed in summary["pre_registered_failure_checks"]["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL / UNAVAILABLE'}: `{name}`")
    lines.extend(["", "## Limitations and disclosures", ""])
    lines.extend(f"- {item}" for item in limitations)
    industry_warning = summary["industry_groups"].get("warning")
    if industry_warning:
        lines.append(f"- {industry_warning}")
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "Input and processed-panel hashes are stored in `reports/systematic_summary.json`. "
            "The report contains no runtime timestamp, and all exported tables are deterministically sorted.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_systematic_pipeline(config_path: str | Path = "config/systematic.yaml") -> dict[str, Any]:
    """Run the frozen-data systematic research workflow and write all artifacts."""

    raw, resolved_config, root = load_systematic_config(config_path)
    market_path = root / "data" / "raw" / "systematic_market_daily.parquet"
    fundamentals_path = root / "data" / "raw" / "systematic_fundamentals_pit.parquet"
    membership_path = root / "data" / "raw" / "systematic_membership.parquet"
    for path in [market_path, fundamentals_path, membership_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required systematic data asset is missing: {path}")

    market = _canonical_market(pd.read_parquet(market_path))
    fundamentals = pd.read_parquet(fundamentals_path)
    memberships = pd.read_parquet(membership_path)
    fundamentals["symbol"] = _normalise_symbol(fundamentals["symbol"])
    memberships["symbol"] = _normalise_symbol(memberships["symbol"])
    for column in ["report_date", "notice_date", "available_date"]:
        fundamentals[column] = pd.to_datetime(fundamentals[column], errors="raise").dt.normalize()
    for column in ["snapshot_date", "available_date"]:
        memberships[column] = pd.to_datetime(memberships[column], errors="raise").dt.normalize()

    cutoff = pd.Timestamp(raw["project"]["research_as_of"]).normalize()
    start = pd.Timestamp(raw["project"]["market_data_start"]).normalize()
    market = market.loc[market["date"].between(start, cutoff)].copy()
    fundamentals = fundamentals.loc[
        fundamentals["report_date"].le(cutoff)
        & fundamentals["notice_date"].le(cutoff)
        & fundamentals["available_date"].le(cutoff)
    ].copy()
    memberships = memberships.loc[memberships["available_date"].le(cutoff)].copy()
    memberships, industry_metadata = _load_industry_groups(root, memberships)

    benchmark_symbol = str(raw["universe"]["benchmark_symbol"]).zfill(6)
    if benchmark_symbol not in set(market["symbol"]):
        raise ValueError(f"Configured benchmark {benchmark_symbol} is absent from systematic market data")
    panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol=benchmark_symbol,
        group_col="industry_group",
        config=_feature_config(raw),
    )
    panel = build_composite_signals(panel, raw)

    evaluation_config = raw["evaluation"]
    design_end = str(evaluation_config["design_end"])
    validation_end = str(evaluation_config["validation_end"])
    final_holdout_end = str(evaluation_config["final_holdout_end"])
    if not pd.Timestamp(design_end) < pd.Timestamp(validation_end) < pd.Timestamp(final_holdout_end):
        raise ValueError("Research split dates must satisfy design < validation < final holdout")
    if pd.Timestamp(final_holdout_end) > cutoff:
        raise ValueError("final_holdout_end cannot exceed research_as_of")
    panel = panel.loc[panel["execution_date"].le(pd.Timestamp(final_holdout_end))].copy()
    panel["research_split"] = assign_research_split(panel["execution_date"], design_end, validation_end)
    panel = panel.sort_values(["execution_date", "symbol"], kind="mergesort").reset_index(drop=True)

    eligible = panel.loc[panel["systematic_eligible"]].copy()
    minimum_cross_section = int(raw["universe"]["min_cross_section"])
    evaluation = evaluate_signals(
        eligible,
        SIGNAL_COLUMNS,
        design_end=design_end,
        validation_end=validation_end,
        hac_lags=int(evaluation_config["hac_lags"]),
        requested_quantiles=int(evaluation_config["quantiles"]),
        min_cross_section=minimum_cross_section,
    )
    quantile_summary = _split_quantile_summary(
        evaluation.quantile_returns, int(evaluation_config["hac_lags"])
    )

    # Registered timing stress: move every feature cutoff back by one
    # additional trading day while retaining the same month-end execution and
    # forward-return window.  This catches results that depend on the final
    # pre-rebalance observation.
    lag_days = int(
        raw.get("robustness", {}).get("additional_signal_lag_trading_days", 2)
    )
    if lag_days <= 1:
        raise ValueError("additional_signal_lag_trading_days must exceed the baseline lag of one")
    lag_panel = build_monthly_systematic_features(
        market,
        fundamentals,
        memberships,
        benchmark_symbol=benchmark_symbol,
        group_col="industry_group",
        config=_feature_config(raw, signal_lag_trading_days=lag_days),
    )
    lag_panel = build_composite_signals(lag_panel, raw)
    lag_panel = lag_panel.loc[
        lag_panel["execution_date"].le(pd.Timestamp(final_holdout_end))
    ].copy()
    lag_panel["research_split"] = assign_research_split(
        lag_panel["execution_date"], design_end, validation_end
    )
    lag_panel = lag_panel.sort_values(
        ["execution_date", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
    lag_eligible = lag_panel.loc[lag_panel["systematic_eligible"]].copy()
    lag_evaluation = evaluate_signals(
        lag_eligible,
        SIGNAL_COLUMNS,
        design_end=design_end,
        validation_end=validation_end,
        hac_lags=int(evaluation_config["hac_lags"]),
        requested_quantiles=int(evaluation_config["quantiles"]),
        min_cross_section=minimum_cross_section,
    )
    lag_quantile_summary = _split_quantile_summary(
        lag_evaluation.quantile_returns, int(evaluation_config["hac_lags"])
    )
    lag_portfolio = run_long_only_backtest(
        lag_eligible,
        market,
        raw["portfolio"],
        raw["transaction_costs"],
        cost_multiplier=1.0,
    )

    portfolio_monthly: list[pd.DataFrame] = []
    portfolio_summaries: list[pd.DataFrame] = []
    baseline_weights = pd.DataFrame()
    baseline_trades = pd.DataFrame()
    multipliers = [float(value) for value in raw["transaction_costs"]["cost_sensitivity_multipliers"]]
    for multiplier in multipliers:
        result = run_long_only_backtest(
            eligible,
            market,
            raw["portfolio"],
            raw["transaction_costs"],
            cost_multiplier=multiplier,
        )
        monthly = result.monthly_returns.copy()
        monthly.insert(0, "cost_multiplier", multiplier)
        summary_frame = result.summary.copy()
        summary_frame.insert(0, "cost_multiplier", multiplier)
        portfolio_monthly.append(monthly)
        portfolio_summaries.append(summary_frame)
        if math.isclose(multiplier, 1.0):
            baseline_weights = result.weights.copy()
            baseline_trades = result.trades.copy()
    all_portfolio_monthly = pd.concat(portfolio_monthly, ignore_index=True) if portfolio_monthly else pd.DataFrame()
    all_portfolio_summary = pd.concat(portfolio_summaries, ignore_index=True) if portfolio_summaries else pd.DataFrame()

    contribution_table, contribution_summary = _active_contribution_diagnostics(
        baseline_weights, eligible
    )

    processed_path = root / "data" / "processed" / "systematic_monthly_panel.parquet"
    write_frame(panel, processed_path)
    lag_processed_path = (
        root
        / "data"
        / "processed"
        / f"systematic_monthly_panel_lag{lag_days}.parquet"
    )
    write_frame(lag_panel, lag_processed_path)
    tables = {
        "monthly_ic": evaluation.monthly_ic,
        "signal_summary": evaluation.signal_summary,
        "quantile_returns": evaluation.quantile_returns,
        "quantile_summary": quantile_summary,
        "portfolio_monthly": all_portfolio_monthly,
        "portfolio_summary": all_portfolio_summary,
        "portfolio_weights": baseline_weights,
        "portfolio_trades": baseline_trades,
        "active_contribution_by_name": contribution_table,
        f"lag{lag_days}_signal_summary": lag_evaluation.signal_summary,
        f"lag{lag_days}_quantile_summary": lag_quantile_summary,
        f"lag{lag_days}_portfolio_summary": lag_portfolio.summary,
    }
    table_paths: dict[str, str] = {}
    for name, frame in tables.items():
        output = root / "reports" / "tables" / f"systematic_{name}.csv"
        sortable = [column for column in ["cost_multiplier", "execution_date", "research_split", "signal", "leg", "symbol"] if column in frame.columns]
        ordered = frame.sort_values(sortable, kind="mergesort").reset_index(drop=True) if sortable else frame
        write_frame(ordered, output)
        tables[name] = ordered
        table_paths[name] = str(output.relative_to(root))
    figure_paths = _write_systematic_figures(
        root,
        tables["monthly_ic"],
        tables["signal_summary"],
        tables["portfolio_monthly"],
        tables["portfolio_summary"],
    )

    split_counts = (
        eligible.groupby("research_split", observed=True)
        .agg(rows=("symbol", "size"), months=("execution_date", "nunique"), symbols=("symbol", "nunique"))
        .reset_index()
    )
    failure_checks = _failure_checks(
        tables["signal_summary"],
        tables["quantile_summary"],
        tables["portfolio_summary"],
        lag_signal_summary=tables[f"lag{lag_days}_signal_summary"],
        lag_quantile_summary=tables[f"lag{lag_days}_quantile_summary"],
        lag_portfolio_summary=tables[f"lag{lag_days}_portfolio_summary"],
    )
    summary: dict[str, Any] = {
        "schema_version": 1,
        "project": {
            "title": raw["project"]["title"],
            "research_type": raw["project"]["research_type"],
            "research_as_of": str(raw["project"]["research_as_of"]),
        },
        "config": str(resolved_config.relative_to(root)),
        "time_splits": {
            "design_end": design_end,
            "validation_end": validation_end,
            "final_holdout_end": final_holdout_end,
            "counts": _records(split_counts),
        },
        "inputs": {
            "market_rows": int(len(market)),
            "fundamental_rows": int(len(fundamentals)),
            "membership_rows": int(len(memberships)),
            "market_sha256": dataframe_sha256(market),
            "fundamentals_sha256": dataframe_sha256(fundamentals),
            "memberships_sha256": dataframe_sha256(memberships),
        },
        "industry_groups": industry_metadata,
        "panel": {
            "rows": int(len(panel)),
            "eligible_rows": int(len(eligible)),
            "eligible_months": int(eligible["execution_date"].nunique()),
            "eligible_symbols": int(eligible["symbol"].nunique()),
            "start": panel["execution_date"].min().date().isoformat() if len(panel) else None,
            "end": panel["execution_date"].max().date().isoformat() if len(panel) else None,
            "sha256": dataframe_sha256(panel),
            "path": str(processed_path.relative_to(root)),
        },
        "additional_signal_lag": {
            "signal_lag_trading_days": lag_days,
            "eligible_rows": int(len(lag_eligible)),
            "eligible_months": int(lag_eligible["execution_date"].nunique()),
            "sha256": dataframe_sha256(lag_panel),
            "path": str(lag_processed_path.relative_to(root)),
            "signal_summary": _records(tables[f"lag{lag_days}_signal_summary"]),
            "quantile_summary": _records(tables[f"lag{lag_days}_quantile_summary"]),
            "portfolio_summary": _records(tables[f"lag{lag_days}_portfolio_summary"]),
        },
        "active_contribution_concentration": contribution_summary,
        "registered_signals": SIGNAL_COLUMNS,
        "signal_summary": _records(tables["signal_summary"]),
        "quantile_summary": _records(tables["quantile_summary"]),
        "portfolio_cost_sensitivity": _records(tables["portfolio_summary"]),
        "pre_registered_failure_checks": failure_checks,
        "outputs": {**table_paths, **figure_paths},
        "disclosures": list(raw.get("disclosures", [])),
    }
    summary_path = root / "reports" / "systematic_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(_json_ready(summary), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    report_path = root / "reports" / "generated" / "systematic_research_report.md"
    _write_report(
        report_path,
        summary,
        tables["signal_summary"],
        tables["quantile_summary"],
        tables["portfolio_summary"],
    )
    return summary
