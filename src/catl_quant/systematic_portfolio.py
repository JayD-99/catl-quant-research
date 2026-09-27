from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass(frozen=True)
class BacktestResult:
    monthly_returns: pd.DataFrame
    weights: pd.DataFrame
    trades: pd.DataFrame
    summary: pd.DataFrame


def _normalise_nonnegative(values: pd.Series) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0:
        return pd.Series(1.0 / len(clean), index=clean.index) if len(clean) else clean
    return clean / total


def estimate_shrunk_covariance(
    market: pd.DataFrame,
    symbols: list[str],
    signal_date: pd.Timestamp,
    *,
    lookback_days: int = 126,
    diagonal_shrinkage: float = 0.35,
) -> pd.DataFrame:
    """Estimate an annualized sample covariance shrunk toward its diagonal."""

    sample = market.loc[
        market["date"].le(pd.Timestamp(signal_date)) & market["symbol"].isin(symbols),
        ["date", "symbol", "close_adj"],
    ]
    prices = sample.pivot(index="date", columns="symbol", values="close_adj").sort_index().tail(lookback_days + 1)
    returns = prices.pct_change(fill_method=None).tail(lookback_days)
    covariance = returns.cov(min_periods=max(20, lookback_days // 2)).reindex(index=symbols, columns=symbols)
    variances = returns.var(ddof=1).reindex(symbols)
    fallback_variance = float(variances.dropna().median()) if variances.notna().any() else 0.0004
    variances = variances.fillna(fallback_variance).clip(lower=1e-8)
    covariance = covariance.fillna(0.0)
    # pandas 3 may expose a read-only NumPy view; build an owned array before
    # replacing the diagonal with the individually estimated variances.
    covariance_values = covariance.to_numpy(dtype=float, copy=True)
    np.fill_diagonal(covariance_values, variances.to_numpy())
    covariance = pd.DataFrame(covariance_values, index=symbols, columns=symbols)
    diagonal = pd.DataFrame(np.diag(np.diag(covariance)), index=symbols, columns=symbols)
    shrunk = (1 - diagonal_shrinkage) * covariance + diagonal_shrinkage * diagonal
    return shrunk * 252


def _project_score_tilt(
    benchmark: pd.Series,
    score: pd.Series,
    groups: pd.Series,
    *,
    score_tilt: float,
    max_weight: float,
    max_active_weight: float,
) -> pd.Series:
    """Find the closest feasible group-neutral portfolio to an exponential score tilt."""

    benchmark = _normalise_nonnegative(benchmark)
    score = pd.to_numeric(score, errors="coerce").fillna(0.0).clip(-4, 4)
    groups = groups.fillna("unknown").astype(str)
    raw = benchmark * np.exp(score_tilt * score)
    # Preserve each broad industry's benchmark weight before the numerical projection.
    for group in groups.unique():
        mask = groups.eq(group)
        group_benchmark = float(benchmark.loc[mask].sum())
        group_raw = float(raw.loc[mask].sum())
        if group_raw > 0:
            raw.loc[mask] *= group_benchmark / group_raw
    raw = _normalise_nonnegative(raw)

    lower = np.maximum(0.0, benchmark.to_numpy() - max_active_weight)
    upper = np.minimum(max_weight, benchmark.to_numpy() + max_active_weight)
    if upper.sum() < 1 - 1e-8:
        upper = np.maximum(upper, benchmark.to_numpy())
    constraints: list[dict[str, object]] = [
        {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}
    ]
    unique_groups = list(groups.unique())
    # The last group equality is implied by full investment and the other groups.
    for group in unique_groups[:-1]:
        mask = groups.eq(group).to_numpy(dtype=float)
        target = float(benchmark.loc[groups.eq(group)].sum())
        constraints.append(
            {
                "type": "eq",
                "fun": lambda w, mask=mask, target=target: float(np.dot(mask, w) - target),
            }
        )
    result = minimize(
        lambda w: float(np.sum((w - raw.to_numpy()) ** 2)),
        x0=benchmark.to_numpy(),
        method="SLSQP",
        bounds=list(zip(lower, upper, strict=True)),
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-12},
    )
    if not result.success:
        return benchmark
    return pd.Series(result.x, index=benchmark.index)


def _scale_active_risk(
    target: pd.Series,
    benchmark: pd.Series,
    covariance: pd.DataFrame,
    beta: pd.Series,
    *,
    tracking_error_cap: float,
    active_beta_cap: float,
) -> tuple[pd.Series, float, float]:
    symbols = target.index.tolist()
    active = target - benchmark
    cov = covariance.reindex(index=symbols, columns=symbols).fillna(0.0).to_numpy()
    active_values = active.to_numpy()
    tracking_error = float(np.sqrt(max(active_values @ cov @ active_values, 0.0)))
    beta_values = pd.to_numeric(beta.reindex(symbols), errors="coerce").fillna(1.0).to_numpy()
    active_beta = float(active_values @ beta_values)
    scale = 1.0
    if tracking_error > tracking_error_cap > 0:
        scale = min(scale, tracking_error_cap / tracking_error)
    if abs(active_beta) > active_beta_cap > 0:
        scale = min(scale, active_beta_cap / abs(active_beta))
    scaled = benchmark + scale * active
    scaled_active = scaled - benchmark
    scaled_te = float(np.sqrt(max(scaled_active.to_numpy() @ cov @ scaled_active.to_numpy(), 0.0)))
    scaled_beta = float(scaled_active.to_numpy() @ beta_values)
    return scaled, scaled_te, scaled_beta


def _apply_turnover_and_capacity(
    target: pd.Series,
    current: pd.Series,
    adv20: pd.Series,
    *,
    turnover_cap: float,
    aum_rmb: float,
    max_adv_participation: float,
) -> tuple[pd.Series, float, float]:
    # Keep both sides of the rebalance.  Reindexing current holdings only to
    # the new target universe silently deletes exiting securities and makes
    # their liquidation turnover and costs disappear.
    symbols = target.index.union(current.index, sort=False)
    target = pd.to_numeric(target.reindex(symbols), errors="coerce").fillna(0.0)
    current = pd.to_numeric(current.reindex(symbols), errors="coerce").fillna(0.0)
    adv20 = pd.to_numeric(adv20.reindex(symbols), errors="coerce")
    delta = target - current
    # One-way turnover is one half of gross traded risky weight.  Cash is the
    # funding residual and is not added again, which would double-count a
    # stock-to-stock switch.
    desired_turnover = float(0.5 * delta.abs().sum())
    scale = 1.0
    if desired_turnover > max(turnover_cap, 0.0):
        scale = min(scale, max(turnover_cap, 0.0) / desired_turnover)
    capacity = max_adv_participation * adv20.fillna(0.0) / aum_rmb
    required = delta.abs()
    ratios = (capacity / required.replace(0, np.nan)).dropna()
    if not ratios.empty:
        scale = min(scale, float(ratios.min()), 1.0)
    implemented = current + max(scale, 0.0) * delta
    implemented_turnover = float(0.5 * (implemented - current).abs().sum())
    return implemented, desired_turnover, implemented_turnover


def transaction_cost_breakdown(
    trades: pd.Series,
    adv20: pd.Series,
    daily_volatility: pd.Series,
    date: pd.Timestamp,
    config: dict[str, float],
    *,
    aum_rmb: float,
    multiplier: float = 1.0,
) -> dict[str, float]:
    """Return portfolio-return costs, not currency amounts."""

    trades = pd.to_numeric(trades, errors="coerce").fillna(0.0)
    abs_trade = trades.abs()
    commission = abs_trade.sum() * float(config["commission_bps_each_side"]) / 10_000
    spread = abs_trade.sum() * float(config["spread_bps_each_side"]) / 10_000
    stamp_bps = (
        float(config["stamp_duty_sell_bps_from_2023_08_28"])
        if pd.Timestamp(date) >= pd.Timestamp("2023-08-28")
        else float(config["stamp_duty_sell_bps_before_2023_08_28"])
    )
    stamp = float((-trades.clip(upper=0)).sum()) * stamp_bps / 10_000
    adv = pd.to_numeric(adv20, errors="coerce").replace(0, np.nan)
    participation = pd.Series(0.0, index=trades.index, dtype=float)
    traded = abs_trade.gt(0)
    participation.loc[traded] = (
        abs_trade.loc[traded] * aum_rmb / adv.reindex(trades.index).loc[traded]
    ).clip(lower=0).fillna(1.0)
    sigma = pd.to_numeric(daily_volatility, errors="coerce").fillna(0.03).clip(lower=0.005)
    impact_rate = float(config["market_impact_eta"]) * sigma * np.sqrt(participation)
    impact = float((abs_trade * impact_rate).sum())
    components = {
        "commission_cost": float(commission * multiplier),
        "spread_cost": float(spread * multiplier),
        "stamp_duty_cost": float(stamp * multiplier),
        "market_impact_cost": float(impact * multiplier),
    }
    components["total_cost"] = float(sum(components.values()))
    components["max_adv_participation"] = float(participation.max()) if len(participation) else 0.0
    return components


def _fund_transaction_costs(
    planned: pd.Series,
    current: pd.Series,
    adv20: pd.Series,
    daily_volatility: pd.Series,
    date: pd.Timestamp,
    config: dict[str, float],
    *,
    aum_rmb: float,
    multiplier: float,
) -> tuple[pd.Series, pd.Series, dict[str, float], float]:
    """Pay estimated costs from residual cash or a pro-rata risky-asset sale.

    Weights are expressed as fractions of opening NAV.  If planned cash is not
    sufficient, risky holdings are scaled down and costs are recomputed until
    ``risky weights + cash + costs == 1`` within numerical tolerance.  This
    prevents the next-period state from implicitly borrowing the cost amount.
    """

    symbols = planned.index.union(current.index, sort=False)
    implemented = pd.to_numeric(planned.reindex(symbols), errors="coerce").fillna(0.0).clip(lower=0.0)
    starting = pd.to_numeric(current.reindex(symbols), errors="coerce").fillna(0.0).clip(lower=0.0)
    adv = pd.to_numeric(adv20.reindex(symbols), errors="coerce")
    volatility = pd.to_numeric(daily_volatility.reindex(symbols), errors="coerce")

    for _ in range(100):
        trades = implemented - starting
        costs = transaction_cost_breakdown(
            trades,
            adv,
            volatility,
            date,
            config,
            aum_rmb=aum_rmb,
            multiplier=multiplier,
        )
        maximum_risky_weight = 1.0 - costs["total_cost"]
        if maximum_risky_weight < 0:
            raise ValueError("Transaction costs exceed opening portfolio NAV")
        risky_weight = float(implemented.sum())
        if risky_weight <= maximum_risky_weight + 1e-12:
            break
        if risky_weight <= 0:
            break
        implemented *= maximum_risky_weight / risky_weight
    else:
        raise RuntimeError("Transaction-cost funding did not converge")

    trades = implemented - starting
    costs = transaction_cost_breakdown(
        trades,
        adv,
        volatility,
        date,
        config,
        aum_rmb=aum_rmb,
        multiplier=multiplier,
    )
    cash = 1.0 - float(implemented.sum()) - costs["total_cost"]
    if cash < -1e-9:
        raise RuntimeError("Post-trade portfolio is not self-financing")
    return implemented, trades, costs, max(cash, 0.0)


def _performance_record(returns: pd.DataFrame, split: str) -> dict[str, object]:
    sample = returns if split == "all" else returns.loc[returns["research_split"].eq(split)]
    if sample.empty:
        return {"research_split": split, "months": 0}
    net = sample["strategy_net_return"].fillna(0.0)
    gross = sample["strategy_gross_return"].fillna(0.0)
    benchmark = sample["benchmark_return"].fillna(0.0)
    active = net - benchmark
    equity = (1 + net).cumprod()
    gross_equity = (1 + gross).cumprod()
    benchmark_equity = (1 + benchmark).cumprod()
    years = len(sample) / 12
    ann_return = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else float("nan")
    ann_gross = float(gross_equity.iloc[-1] ** (1 / years) - 1) if years > 0 else float("nan")
    ann_benchmark = float(benchmark_equity.iloc[-1] ** (1 / years) - 1) if years > 0 else float("nan")
    ann_vol = float(net.std(ddof=1) * np.sqrt(12)) if len(net) > 1 else float("nan")
    tracking_error = float(active.std(ddof=1) * np.sqrt(12)) if len(active) > 1 else float("nan")
    drawdown = equity / equity.cummax() - 1
    return {
        "research_split": split,
        "months": int(len(sample)),
        "cumulative_gross_return": float(gross_equity.iloc[-1] - 1),
        "cumulative_net_return": float(equity.iloc[-1] - 1),
        "cumulative_benchmark_return": float(benchmark_equity.iloc[-1] - 1),
        "annualized_gross_return": ann_gross,
        "annualized_net_return": ann_return,
        "annualized_benchmark_return": ann_benchmark,
        "annualized_net_volatility": ann_vol,
        "net_sharpe_zero_rf": float(net.mean() / net.std(ddof=1) * np.sqrt(12))
        if len(net) > 1 and net.std(ddof=1) > 0
        else float("nan"),
        "annualized_active_return": float(ann_return - ann_benchmark),
        "tracking_error": tracking_error,
        "information_ratio": float(active.mean() / active.std(ddof=1) * np.sqrt(12))
        if len(active) > 1 and active.std(ddof=1) > 0
        else float("nan"),
        "max_drawdown": float(drawdown.min()),
        "active_month_hit_rate": float((active > 0).mean()),
        "average_one_way_turnover": float(sample["implemented_one_way_turnover"].mean()),
        "average_gross_traded_weight": float(sample["gross_traded_weight"].mean()),
        "total_forced_exit_sell_weight": float(sample["forced_exit_sell_weight"].sum()),
        "months_with_forced_exits": int(sample["forced_exit_count"].gt(0).sum()),
        "average_cash_weight": float(sample["cash_weight"].mean()),
        "maximum_cash_weight": float(sample["cash_weight"].max()),
        "total_cost_arithmetic": float(sample["total_cost"].sum()),
        "annualized_cost_drag_arithmetic": float(sample["total_cost"].mean() * 12),
        "annualized_cost_drag_geometric": float(ann_gross - ann_return),
        "annualized_commission_drag": float(sample["commission_cost"].mean() * 12),
        "annualized_spread_drag": float(sample["spread_cost"].mean() * 12),
        "annualized_stamp_duty_drag": float(sample["stamp_duty_cost"].mean() * 12),
        "annualized_market_impact_drag": float(sample["market_impact_cost"].mean() * 12),
    }


def run_long_only_backtest(
    panel: pd.DataFrame,
    market: pd.DataFrame,
    portfolio_config: dict[str, float],
    cost_config: dict[str, float],
    *,
    cost_multiplier: float = 1.0,
) -> BacktestResult:
    """Run a monthly benchmark-relative, cost-aware long-only simulation."""

    required = {
        "execution_date",
        "signal_date",
        "symbol",
        "benchmark_weight",
        "composite_score",
        "forward_return",
        "market_beta_126d",
        "adv20_rmb",
        "volatility_63d",
        "industry_group",
        "research_split",
    }
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"Backtest panel is missing columns: {sorted(missing)}")

    work = panel.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"], errors="raise")
    work["signal_date"] = pd.to_datetime(work["signal_date"], errors="raise")
    work["symbol"] = work["symbol"].astype(str)
    if work.duplicated(["execution_date", "symbol"]).any():
        raise ValueError("Backtest panel contains duplicate execution_date/symbol rows")
    market_work = market.copy()
    market_work["date"] = pd.to_datetime(market_work["date"], errors="raise")
    market_work["symbol"] = market_work["symbol"].astype(str)

    current = pd.Series(dtype=float)
    current_cash = 0.0
    last_adv = pd.Series(dtype=float)
    last_volatility = pd.Series(dtype=float)
    last_group = pd.Series(dtype=object)
    last_score = pd.Series(dtype=float)
    monthly_records: list[dict[str, object]] = []
    weight_records: list[dict[str, object]] = []
    trade_records: list[dict[str, object]] = []

    for execution_date, group in work.groupby("execution_date", sort=True):
        group = group.dropna(subset=["forward_return", "composite_score"]).copy()
        if len(group) < int(portfolio_config["min_holdings"]):
            continue
        group = group.set_index("symbol", drop=False)
        benchmark = _normalise_nonnegative(group["benchmark_weight"])
        if current.empty:
            # An enhanced-index mandate is assumed to start from the benchmark;
            # first-month costs therefore reflect only the active tilt.
            current = benchmark.copy()
            current_cash = 0.0
        else:
            total = float(current.sum() + current_cash)
            if total > 0:
                current /= total
                current_cash /= total

        pre_trade_current = current.copy()
        pre_trade_cash = float(current_cash)
        exiting_symbols = pre_trade_current.index.difference(group.index, sort=False)
        forced_exit_sell_weight = float(pre_trade_current.reindex(exiting_symbols).fillna(0.0).sum())
        forced_exit_count = int(pre_trade_current.reindex(exiting_symbols).fillna(0.0).gt(1e-12).sum())
        # Mandatory universe exits are completed before discretionary tilts.
        # Their stock-sale leg consumes half their weight under the documented
        # 0.5 * sum(abs(stock trades)) one-way-turnover convention.
        forced_exit_turnover_contribution = 0.5 * forced_exit_sell_weight
        current_in_universe = pre_trade_current.reindex(group.index).fillna(0.0)
        cash_after_forced_exits = pre_trade_cash + forced_exit_sell_weight

        # ``.loc[new_labels] =`` raises on an empty Series in pandas 3.0.
        # Expand the descriptor ledgers explicitly before updating them; the
        # retained observations are needed to cost mandatory exits after a
        # security leaves the current membership snapshot.
        ledger_index = last_adv.index.union(group.index, sort=False)
        last_adv = last_adv.reindex(ledger_index)
        last_volatility = last_volatility.reindex(ledger_index)
        last_group = last_group.reindex(ledger_index)
        last_score = last_score.reindex(ledger_index)
        last_adv.loc[group.index] = pd.to_numeric(group["adv20_rmb"], errors="coerce").to_numpy()
        last_volatility.loc[group.index] = pd.to_numeric(
            group["volatility_63d"], errors="coerce"
        ).to_numpy()
        last_group.loc[group.index] = group["industry_group"].astype(str).to_numpy()
        last_score.loc[group.index] = pd.to_numeric(
            group["composite_score"], errors="coerce"
        ).to_numpy()

        target = _project_score_tilt(
            benchmark,
            group["composite_score"],
            group["industry_group"],
            score_tilt=float(portfolio_config["score_tilt"]),
            max_weight=float(portfolio_config["max_weight"]),
            max_active_weight=float(portfolio_config["max_active_weight"]),
        )
        covariance = estimate_shrunk_covariance(
            market_work,
            group.index.tolist(),
            pd.Timestamp(group["signal_date"].iloc[0]),
            lookback_days=int(portfolio_config["covariance_lookback_days"]),
            diagonal_shrinkage=float(portfolio_config["covariance_diagonal_shrinkage"]),
        )
        target, target_ex_ante_te, target_active_beta = _scale_active_risk(
            target,
            benchmark,
            covariance,
            group["market_beta_126d"],
            tracking_error_cap=float(portfolio_config["annualized_tracking_error_cap"]),
            active_beta_cap=float(portfolio_config["max_active_beta"]),
        )
        turnover_cap = float(portfolio_config["monthly_one_way_turnover_cap"])
        remaining_turnover_cap = max(0.0, turnover_cap - forced_exit_turnover_contribution)
        planned_in_universe, _, _ = _apply_turnover_and_capacity(
            target,
            current_in_universe,
            group["adv20_rmb"],
            turnover_cap=remaining_turnover_cap,
            aum_rmb=float(portfolio_config["aum_rmb"]),
            max_adv_participation=float(portfolio_config["max_adv_participation"]),
        )
        # ``planned_in_universe`` plus cash remains self-financing after the
        # forced exits.  Exited names are explicitly retained at zero so their
        # sale appears in the trade and cost ledgers.
        all_symbols = pre_trade_current.index.union(group.index, sort=False)
        planned = planned_in_universe.reindex(all_symbols).fillna(0.0)
        starting = pre_trade_current.reindex(all_symbols).fillna(0.0)
        adv_all = last_adv.reindex(all_symbols)
        volatility_all = last_volatility.reindex(all_symbols)
        implemented, trades, costs, implemented_cash = _fund_transaction_costs(
            planned,
            starting,
            adv_all,
            volatility_all,
            pd.Timestamp(execution_date),
            cost_config,
            aum_rmb=float(portfolio_config["aum_rmb"]),
            multiplier=cost_multiplier,
        )
        target_all = target.reindex(all_symbols).fillna(0.0)
        desired_turnover = float(0.5 * (target_all - starting).abs().sum())
        implemented_turnover = float(0.5 * trades.abs().sum())
        gross_traded_weight = float(trades.abs().sum())

        implemented_in_universe = implemented.reindex(group.index).fillna(0.0)
        future = group["forward_return"].fillna(0.0)
        gross_return = float((implemented_in_universe * future).sum())
        benchmark_return = float((benchmark * future).sum())
        net_return = gross_return - costs["total_cost"]
        active = implemented_in_universe - benchmark
        cov_values = covariance.reindex(index=group.index, columns=group.index).fillna(0.0).to_numpy()
        active_values = active.to_numpy(dtype=float)
        ex_ante_te = float(np.sqrt(max(active_values @ cov_values @ active_values, 0.0)))
        beta_values = pd.to_numeric(group["market_beta_126d"], errors="coerce").fillna(1.0)
        active_beta = float(active_values @ beta_values.to_numpy(dtype=float))
        ending_risky_values = implemented * (1 + future.reindex(all_symbols).fillna(0.0))
        ending_nav = float(ending_risky_values.sum() + implemented_cash)
        if not np.isclose(ending_nav, 1 + net_return, atol=1e-10):
            raise RuntimeError("Portfolio NAV does not reconcile to net return")
        if ending_nav <= 0:
            raise RuntimeError("Portfolio NAV became non-positive")
        ending_cash_weight = float(implemented_cash / ending_nav)
        monthly_records.append(
            {
                "execution_date": pd.Timestamp(execution_date),
                "research_split": str(group["research_split"].iloc[0]),
                "holdings": int((implemented > 1e-8).sum()),
                "strategy_gross_return": gross_return,
                "strategy_net_return": net_return,
                "benchmark_return": benchmark_return,
                "gross_active_return": gross_return - benchmark_return,
                "net_active_return": net_return - benchmark_return,
                "desired_one_way_turnover": desired_turnover,
                "implemented_one_way_turnover": implemented_turnover,
                "gross_traded_weight": gross_traded_weight,
                "turnover_definition": "0.5 * sum(abs(stock_weight_change))",
                "forced_exit_count": forced_exit_count,
                "forced_exit_sell_weight": forced_exit_sell_weight,
                "forced_exit_turnover_contribution": forced_exit_turnover_contribution,
                "turnover_cap": turnover_cap,
                "turnover_cap_breached": bool(implemented_turnover > turnover_cap + 1e-10),
                "pre_trade_cash_weight": pre_trade_cash,
                "cash_after_forced_exits": cash_after_forced_exits,
                "post_trade_risky_weight": float(implemented.sum()),
                "ex_ante_tracking_error": ex_ante_te,
                "active_market_beta": active_beta,
                "target_ex_ante_tracking_error": target_ex_ante_te,
                "target_active_market_beta": target_active_beta,
                "cash_weight": implemented_cash,
                "ending_cash_weight": ending_cash_weight,
                **costs,
            }
        )
        for symbol in all_symbols:
            in_universe = symbol in group.index
            weight_records.append(
                {
                    "execution_date": pd.Timestamp(execution_date),
                    "symbol": symbol,
                    "in_current_universe": in_universe,
                    "forced_exit": bool(symbol in exiting_symbols),
                    "benchmark_weight": float(benchmark.get(symbol, 0.0)),
                    "pre_trade_weight": float(starting.loc[symbol]),
                    "target_weight": float(target_all.loc[symbol]),
                    "implemented_weight": float(implemented.loc[symbol]),
                    "active_weight": float(implemented.loc[symbol] - benchmark.get(symbol, 0.0)),
                    "composite_score": float(last_score.get(symbol, np.nan)),
                    "industry_group": str(last_group.get(symbol, "unknown")),
                }
            )
            trade_records.append(
                {
                    "execution_date": pd.Timestamp(execution_date),
                    "symbol": symbol,
                    "trade_weight": float(trades.loc[symbol]),
                    "trade_value_rmb": float(trades.loc[symbol] * float(portfolio_config["aum_rmb"])),
                    "forced_exit": bool(symbol in exiting_symbols),
                    "adv20_rmb": float(adv_all.get(symbol, np.nan)),
                }
            )

        current = (ending_risky_values / ending_nav).loc[lambda values: values.gt(1e-14)]
        current_cash = ending_cash_weight

    monthly = pd.DataFrame.from_records(monthly_records)
    summaries = [_performance_record(monthly, split) for split in ["all", "design", "validation", "final_holdout"]]
    return BacktestResult(
        monthly_returns=monthly,
        weights=pd.DataFrame.from_records(weight_records),
        trades=pd.DataFrame.from_records(trade_records),
        summary=pd.DataFrame.from_records(summaries),
    )
