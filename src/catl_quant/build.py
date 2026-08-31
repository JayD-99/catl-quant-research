from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ResearchConfig
from .io import write_frame


def _assert_point_in_time(
    market: pd.DataFrame,
    lithium: pd.DataFrame,
    fundamentals: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> None:
    for label, frame, column in [
        ("market", market, "date"),
        ("lithium", lithium, "date"),
        ("fundamentals report", fundamentals, "report_date"),
        ("fundamentals notice", fundamentals, "notice_date"),
    ]:
        dates = pd.to_datetime(frame[column], errors="raise")
        if dates.max() > cutoff:
            raise ValueError(f"Point-in-time violation: {label} observations exceed research cutoff")


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() < 3:
        return pd.Series(np.nan, index=series.index)
    lower, upper = numeric.quantile([0.05, 0.95])
    clipped = numeric.clip(lower, upper)
    std = clipped.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=series.index)
    return (clipped - clipped.mean()) / std


def _score_fundamentals(frame: pd.DataFrame, core_symbols: set[str]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for report_date, group in frame.loc[frame["symbol"].isin(core_symbols)].groupby("report_date"):
        scored = group.copy()
        scored["z_roe"] = _zscore(scored["roe_pct"])
        scored["z_gross_margin"] = _zscore(scored["gross_margin_pct"])
        scored["z_net_margin"] = _zscore(scored["net_margin_pct"])
        scored["z_revenue_growth"] = _zscore(scored["revenue_growth_pct"])
        scored["z_net_profit_growth"] = _zscore(scored["net_profit_growth_pct"])
        scored["z_balance_sheet"] = _zscore(-scored["debt_ratio_pct"])
        scored["quality_score"] = scored[["z_roe", "z_gross_margin", "z_net_margin"]].mean(axis=1)
        scored["growth_score"] = scored[["z_revenue_growth", "z_net_profit_growth"]].mean(axis=1)
        scored["balance_score"] = scored["z_balance_sheet"]
        scored["operating_score"] = scored[["quality_score", "growth_score", "balance_score"]].mean(axis=1)
        scored["operating_rank"] = scored["operating_score"].rank(method="min", ascending=False).astype(int)
        scored["universe_size"] = len(scored)
        scored["report_date"] = report_date
        rows.append(scored)
    return pd.concat(rows, ignore_index=True)


def _build_operating_bridge(root: Path) -> pd.DataFrame:
    history = pd.read_csv(root / "data" / "manual" / "catl_operating_history.csv")
    prior = history.loc[history["year"].eq(2023)].iloc[0]
    current = history.loc[history["year"].eq(2024)].iloc[0]
    records: list[dict[str, float | str]] = []
    for prefix, label in [("ev", "EV batteries"), ("ess", "ESS batteries")]:
        volume_0 = float(prior[f"{prefix}_volume_gwh"])
        volume_1 = float(current[f"{prefix}_volume_gwh"])
        asp_0 = float(prior[f"{prefix}_asp_rmb_per_wh"])
        asp_1 = float(current[f"{prefix}_asp_rmb_per_wh"])
        volume_effect = (volume_1 - volume_0) * (asp_0 + asp_1) / 2 * 1000
        price_effect = (asp_1 - asp_0) * (volume_0 + volume_1) / 2 * 1000
        records.extend(
            [
                {"segment": label, "effect": "volume", "revenue_effect_rmb_mn": volume_effect},
                {"segment": label, "effect": "ASP", "revenue_effect_rmb_mn": price_effect},
                {
                    "segment": label,
                    "effect": "net_modelled",
                    "revenue_effect_rmb_mn": volume_effect + price_effect,
                },
            ]
        )
    return pd.DataFrame.from_records(records)


def build_datasets(config: ResearchConfig) -> None:
    root = config.root
    market = pd.read_parquet(root / "data" / "raw" / "market_daily.parquet")
    lithium = pd.read_parquet(root / "data" / "raw" / "gfex_lithium_continuous.parquet")
    fundamentals = pd.read_parquet(root / "data" / "raw" / "peer_fundamentals_point_in_time.parquet")
    cutoff = pd.Timestamp(config.as_of)
    _assert_point_in_time(market, lithium, fundamentals, cutoff)
    if market.duplicated(["date", "symbol"]).any() or lithium.duplicated("date").any():
        raise ValueError("Duplicate market observations found")

    rule = str(config.raw["model"]["weekly_rule"])
    prices = market.pivot(index="date", columns="symbol", values="close").sort_index()
    weekly_prices = prices.resample(rule).last()
    weekly_returns = np.log(weekly_prices / weekly_prices.shift(1))

    focal = str(config.raw["project"]["focal_symbol"])
    benchmark = str(config.raw["market"]["benchmark"]["symbol"])
    peers = [str(item["symbol"]) for item in config.raw["market"]["core_peers"]]
    panel = pd.DataFrame(index=weekly_returns.index)
    panel["catl_return"] = weekly_returns[focal]
    panel["market_return"] = weekly_returns[benchmark]
    panel["peer_return"] = weekly_returns[peers].mean(axis=1, skipna=True)
    panel["catl_excess_market"] = panel["catl_return"] - panel["market_return"]
    panel["peer_excess_market"] = panel["peer_return"] - panel["market_return"]

    lithium = lithium.set_index("date").sort_index()
    lithium_weekly = lithium["settle"].resample(rule).last()
    lithium_return = np.log(lithium_weekly / lithium_weekly.shift(1))
    panel["lithium_settle"] = lithium_weekly
    panel["lithium_return_raw"] = lithium_return
    lower, upper = lithium_return.dropna().quantile([0.01, 0.99])
    panel["lithium_return"] = lithium_return.clip(lower, upper)
    panel = panel.reset_index().rename(columns={"date": "week"})
    model_panel = panel.dropna(subset=["catl_return", "market_return", "peer_return", "lithium_return"]).copy()
    write_frame(panel, root / "data" / "processed" / "weekly_panel.parquet")
    write_frame(model_panel, root / "data" / "processed" / "weekly_model_panel.parquet")

    core_symbols = {focal, *peers}
    scored = _score_fundamentals(fundamentals, core_symbols)
    write_frame(scored, root / "data" / "processed" / "peer_operating_scores.csv")

    bridge = _build_operating_bridge(root)
    write_frame(bridge, root / "data" / "processed" / "catl_2024_revenue_bridge.csv")

    customer = pd.read_csv(root / "data" / "manual" / "catl_customer_concentration_2024.csv")
    hhi_top5 = float(((customer["revenue_share_pct"] / 100) ** 2).sum())
    diagnostics = {
        "research_as_of": config.as_of,
        "market_rows": int(len(market)),
        "weekly_model_rows": int(len(model_panel)),
        "weekly_model_start": model_panel["week"].min().date().isoformat(),
        "weekly_model_end": model_panel["week"].max().date().isoformat(),
        "lithium_raw_return_clip_1pct": float(lower),
        "lithium_raw_return_clip_99pct": float(upper),
        "customer_top5_hhi_contribution": hhi_top5,
        "customer_top5_share_pct": float(customer["revenue_share_pct"].sum()),
    }
    output = root / "data" / "processed" / "build_diagnostics.json"
    output.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
