from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.tsa.stattools import adfuller

from .config import ResearchConfig
from .io import write_frame


def _fit_hac(data: pd.DataFrame, y: str, x: list[str], lags: int):
    model = sm.OLS(data[y], sm.add_constant(data[x]), missing="drop")
    return model.fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def _model_record(name: str, result) -> dict[str, object]:
    return {
        "model": name,
        "nobs": int(result.nobs),
        "r_squared": float(result.rsquared),
        "adjusted_r_squared": float(result.rsquared_adj),
        "aic": float(result.aic),
        "coefficients": {key: float(value) for key, value in result.params.items()},
        "hac_standard_errors": {key: float(value) for key, value in result.bse.items()},
        "p_values": {key: float(value) for key, value in result.pvalues.items()},
    }


def _run_return_models(config: ResearchConfig, panel: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    lags = int(config.raw["model"]["hac_lags"])
    specifications = {
        "market_only": ["market_return"],
        "market_plus_peers": ["market_return", "peer_excess_market"],
        "full": ["market_return", "peer_excess_market", "lithium_return"],
    }
    fitted = {name: _fit_hac(panel, "catl_return", factors, lags) for name, factors in specifications.items()}
    summary = {name: _model_record(name, result) for name, result in fitted.items()}

    window = int(config.raw["model"]["rolling_window_weeks"])
    rolling_rows: list[dict[str, object]] = []
    factors = specifications["full"]
    for end in range(window, len(panel) + 1):
        sample = panel.iloc[end - window : end]
        result = _fit_hac(sample, "catl_return", factors, lags)
        rolling_rows.append({"week": sample.iloc[-1]["week"], **{f"beta_{k}": float(v) for k, v in result.params.items()}})
    rolling = pd.DataFrame.from_records(rolling_rows)

    train = int(config.raw["model"]["oos_train_weeks"])
    predictions: list[dict[str, object]] = []
    for idx in range(train, len(panel)):
        sample = panel.iloc[idx - train : idx]
        observation = panel.iloc[[idx]]
        row: dict[str, object] = {"week": observation.iloc[0]["week"], "actual": float(observation.iloc[0]["catl_return"])}
        for name in ["market_only", "full"]:
            factors = specifications[name]
            result = sm.OLS(sample["catl_return"], sm.add_constant(sample[factors], has_constant="add")).fit()
            exog = sm.add_constant(observation[factors], has_constant="add")
            row[f"predicted_{name}"] = float(result.predict(exog).iloc[0])
        predictions.append(row)
    oos = pd.DataFrame.from_records(predictions)
    if not oos.empty:
        sse_market = float(((oos["actual"] - oos["predicted_market_only"]) ** 2).sum())
        sse_full = float(((oos["actual"] - oos["predicted_full"]) ** 2).sum())
        summary["oos_validation"] = {
            "observations": int(len(oos)),
            "market_only_rmse": float(np.sqrt(sse_market / len(oos))),
            "full_rmse": float(np.sqrt(sse_full / len(oos))),
            "incremental_oos_r2_vs_market_model": float(1 - sse_full / sse_market),
            "market_only_directional_accuracy": float(
                (np.sign(oos["actual"]) == np.sign(oos["predicted_market_only"])).mean()
            ),
            "full_directional_accuracy": float(
                (np.sign(oos["actual"]) == np.sign(oos["predicted_full"])).mean()
            ),
            "naive_positive_directional_accuracy": float((oos["actual"] > 0).mean()),
        }

    internship_start = pd.Timestamp(config.raw["project"]["internship_start"])
    internship = panel.loc[panel["week"].between(internship_start, pd.Timestamp(config.as_of))].copy()
    full = fitted["full"]
    contributions = []
    for factor in specifications["full"]:
        contributions.append(
            {
                "factor": factor,
                "cumulative_log_return_contribution": float((internship[factor] * full.params[factor]).sum()),
            }
        )
    summary["internship_window_attribution"] = {
        "weeks": int(len(internship)),
        "catl_cumulative_log_return": float(internship["catl_return"].sum()),
        "model_intercept_contribution": float(full.params["const"] * len(internship)),
        "factor_contributions": contributions,
        "residual_contribution": float(
            internship["catl_return"].sum()
            - full.params["const"] * len(internship)
            - sum(item["cumulative_log_return_contribution"] for item in contributions)
        ),
    }
    return summary, rolling, oos


def _forward_return(prices: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float:
    available = prices.dropna()
    start_values = available.loc[available.index >= start]
    end_values = available.loc[available.index <= end]
    if start_values.empty or end_values.empty:
        return float("nan")
    start_price = float(start_values.iloc[0])
    end_price = float(end_values.iloc[-1])
    return end_price / start_price - 1


def _validate_peer_scores(config: ResearchConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = config.root
    scores = pd.read_csv(
        root / "data" / "processed" / "peer_operating_scores.csv",
        parse_dates=["report_date", "notice_date"],
        dtype={"symbol": str},
    )
    market = pd.read_parquet(root / "data" / "raw" / "market_daily.parquet")
    prices = market.pivot(index="date", columns="symbol", values="close").sort_index()
    benchmark = str(config.raw["market"]["benchmark"]["symbol"])
    cutoff = pd.Timestamp(config.as_of)
    evaluated: list[pd.DataFrame] = []
    validations: list[dict[str, object]] = []
    for report_date, group in scores.groupby("report_date"):
        start = pd.Timestamp(year=report_date.year + 1, month=5, day=1)
        if start > cutoff:
            continue
        end = min(start + pd.Timedelta(days=183), cutoff)
        market_return = _forward_return(prices[benchmark], start, end)
        sample = group.copy()
        sample["evaluation_start"] = start
        sample["evaluation_end"] = end
        sample["forward_return"] = [
            _forward_return(prices[str(symbol)], start, end) for symbol in sample["symbol"]
        ]
        sample["forward_excess_return"] = sample["forward_return"] - market_return
        valid = sample.dropna(subset=["operating_score", "forward_excess_return"])
        rho, p_value = stats.spearmanr(valid["operating_score"], valid["forward_excess_return"])
        validations.append(
            {
                "report_date": report_date,
                "evaluation_start": start,
                "evaluation_end": end,
                "companies": int(len(valid)),
                "rank_ic": float(rho),
                "p_value": float(p_value),
            }
        )
        evaluated.append(sample)
    return pd.concat(evaluated, ignore_index=True), pd.DataFrame.from_records(validations)


def _moving_block_bootstrap(returns: np.ndarray, simulations: int, horizon: int, seed: int, block: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    starts = np.arange(0, len(returns) - block + 1)
    draws = np.empty((simulations, horizon))
    for sim in range(simulations):
        path: list[float] = []
        while len(path) < horizon:
            start = int(rng.choice(starts))
            path.extend(returns[start : start + block].tolist())
        draws[sim] = path[:horizon]
    return draws


def _map_price_shock_to_pbt(
    direct_materials_rmb_mn: float,
    lithium_to_material_beta: float,
    endpoint_price_shock: np.ndarray,
    pass_through: float,
) -> np.ndarray:
    return (
        -direct_materials_rmb_mn
        * lithium_to_material_beta
        * endpoint_price_shock
        * (1 - pass_through)
    )


def _run_commodity_model(config: ResearchConfig) -> tuple[dict[str, object], pd.DataFrame]:
    root = config.root
    lithium = pd.read_parquet(root / "data" / "raw" / "gfex_lithium_continuous.parquet")
    weekly = lithium.set_index("date")["settle"].resample(str(config.raw["model"]["weekly_rule"])).last().dropna()
    log_price = np.log(weekly)
    returns = log_price.diff().dropna()
    adf_stat, adf_p, *_ = adfuller(log_price, autolag="AIC", result_object=False)

    lagged = log_price.shift(1).dropna()
    aligned = log_price.loc[lagged.index]
    ar1 = sm.OLS(aligned, sm.add_constant(lagged, has_constant="add")).fit()
    phi = float(ar1.params.iloc[1])
    half_life = float(-math.log(2) / math.log(phi)) if 0 < phi < 1 else float("nan")

    split = max(20, int(len(log_price) * 0.8))
    test = log_price.iloc[split:]
    train = log_price.iloc[:split]
    train_lag = train.shift(1).dropna()
    train_fit = sm.OLS(train.loc[train_lag.index], sm.add_constant(train_lag, has_constant="add")).fit()
    ar_predictions = train_fit.params.iloc[0] + train_fit.params.iloc[1] * log_price.shift(1).loc[test.index]
    random_walk_predictions = log_price.shift(1).loc[test.index]
    ar_rmse = float(np.sqrt(np.mean((test - ar_predictions) ** 2)))
    rw_rmse = float(np.sqrt(np.mean((test - random_walk_predictions) ** 2)))
    use_ar1 = bool(adf_p < 0.10 and ar_rmse < rw_rmse and 0 < phi < 1)

    simulations = int(config.raw["model"]["simulations"])
    horizon = int(config.raw["model"]["horizon_weeks"])
    seed = int(config.raw["project"]["random_seed"])
    if use_ar1:
        rng = np.random.default_rng(seed)
        sigma = float(ar1.resid.std(ddof=1))
        paths = np.empty((simulations, horizon + 1))
        paths[:, 0] = float(log_price.iloc[-1])
        for step in range(1, horizon + 1):
            paths[:, step] = ar1.params.iloc[0] + phi * paths[:, step - 1] + rng.normal(0, sigma, simulations)
        endpoint_shock = np.exp(paths[:, -1] - paths[:, 0]) - 1
        method = "AR(1) log-price simulation"
    else:
        draws = _moving_block_bootstrap(returns.to_numpy(), simulations, horizon, seed)
        endpoint_shock = np.exp(draws.sum(axis=1)) - 1
        method = "four-week moving-block bootstrap of log returns"

    base = pd.read_csv(root / "data" / "manual" / "catl_operating_history.csv")
    direct_materials = float(base.loc[base["year"].eq(2024), "direct_materials_rmb_mn"].iloc[0])
    scenario_rows: list[dict[str, float]] = []
    for beta in config.raw["model"]["lithium_to_total_material_cost_beta"]:
        for pass_through in config.raw["model"]["pass_through_scenarios"]:
            impact = _map_price_shock_to_pbt(
                direct_materials,
                float(beta),
                endpoint_shock,
                float(pass_through),
            )
            q05, q50, q95 = np.quantile(impact, [0.05, 0.50, 0.95])
            scenario_rows.append(
                {
                    "lithium_to_material_beta": float(beta),
                    "pass_through": float(pass_through),
                    "pbt_impact_q05_rmb_mn": float(q05),
                    "pbt_impact_q50_rmb_mn": float(q50),
                    "pbt_impact_q95_rmb_mn": float(q95),
                }
            )
    summary = {
        "observations_weekly": int(len(log_price)),
        "adf_statistic_log_price": float(adf_stat),
        "adf_p_value_log_price": float(adf_p),
        "ar1_phi": phi,
        "ar1_half_life_weeks": half_life,
        "ar1_oos_rmse": ar_rmse,
        "random_walk_oos_rmse": rw_rmse,
        "selected_simulation_method": method,
        "endpoint_price_shock_quantiles": {
            "q05": float(np.quantile(endpoint_shock, 0.05)),
            "q50": float(np.quantile(endpoint_shock, 0.50)),
            "q95": float(np.quantile(endpoint_shock, 0.95)),
        },
        "important_limitation": "Lithium-price shocks are mapped to total direct-material costs through explicit scenario betas, not an estimated causal coefficient.",
    }
    return summary, pd.DataFrame.from_records(scenario_rows)


def run_analysis(config: ResearchConfig) -> None:
    root = config.root
    panel = pd.read_parquet(root / "data" / "processed" / "weekly_model_panel.parquet")
    return_summary, rolling, oos = _run_return_models(config, panel)
    evaluated_scores, validation = _validate_peer_scores(config)
    commodity_summary, commodity_scenarios = _run_commodity_model(config)

    write_frame(rolling, root / "reports" / "tables" / "rolling_betas.csv")
    write_frame(oos, root / "reports" / "tables" / "oos_predictions.csv")
    write_frame(evaluated_scores, root / "reports" / "tables" / "peer_score_validation.csv")
    write_frame(validation, root / "reports" / "tables" / "peer_rank_ic.csv")
    write_frame(commodity_scenarios, root / "reports" / "tables" / "commodity_scenarios.csv")
    summary = {
        "return_attribution": return_summary,
        "peer_score_validation": validation.assign(
            report_date=validation["report_date"].astype(str),
            evaluation_start=validation["evaluation_start"].astype(str),
            evaluation_end=validation["evaluation_end"].astype(str),
        ).to_dict("records"),
        "commodity_model": commodity_summary,
    }
    output = root / "reports" / "analysis_summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=True) + "\n", encoding="utf-8")
