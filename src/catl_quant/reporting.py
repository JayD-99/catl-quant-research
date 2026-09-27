from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", ".matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .config import ResearchConfig


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _make_figures(config: ResearchConfig) -> None:
    root = config.root
    sns.set_theme(style="whitegrid")
    panel = pd.read_parquet(root / "data" / "processed" / "weekly_model_panel.parquet")
    cumulative = panel.set_index("week")[["catl_return", "market_return", "peer_return"]].cumsum().pipe(np.exp)
    cumulative = cumulative.div(cumulative.iloc[0])
    cumulative = cumulative.rename(
        columns={"catl_return": "CATL", "market_return": "CSI 300", "peer_return": "Battery peers"}
    )
    ax = cumulative.plot(figsize=(10, 5), linewidth=2)
    ax.set_title("Growth of RMB 1: CATL, CSI 300, and Equal-Weighted Battery Peers")
    ax.set_ylabel("Growth multiple")
    ax.set_xlabel("")
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(root / "reports" / "figures" / "cumulative_returns.png", dpi=180)
    plt.close(fig)

    rolling = pd.read_csv(root / "reports" / "tables" / "rolling_betas.csv", parse_dates=["week"])
    beta_columns = [column for column in rolling.columns if column.startswith("beta_") and column != "beta_const"]
    rolling_plot = rolling.set_index("week")[beta_columns].rename(
        columns={
            "beta_market_return": "Market",
            "beta_peer_excess_market": "Peer excess",
            "beta_lithium_return": "Lithium",
        }
    )
    ax = rolling_plot.plot(figsize=(10, 5), linewidth=1.8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("52-Week Rolling CATL Exposures")
    ax.set_ylabel("Regression beta")
    ax.set_xlabel("")
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(root / "reports" / "figures" / "rolling_betas.png", dpi=180)
    plt.close(fig)

    bridge = pd.read_csv(root / "data" / "processed" / "catl_2024_revenue_bridge.csv")
    bridge_plot = (
        bridge.loc[bridge["effect"].isin(["volume", "ASP"])]
        .pivot(index="segment", columns="effect", values="revenue_effect_rmb_mn")
        .loc[:, ["volume", "ASP"]]
        .div(1000)
        .rename(columns={"volume": "Volume effect", "ASP": "ASP effect"})
    )
    bridge_plot.columns.name = None
    ax = bridge_plot.plot.bar(figsize=(8, 4.8), color=["#4C78A8", "#E45756"], rot=0)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("2024 Segment Revenue Change: Volume vs ASP")
    ax.set_ylabel("RMB bn")
    ax.set_xlabel("")
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(root / "reports" / "figures" / "revenue_bridge.png", dpi=180)
    plt.close(fig)

    scenarios = pd.read_csv(root / "reports" / "tables" / "commodity_scenarios.csv")
    heat = scenarios.pivot(index="lithium_to_material_beta", columns="pass_through", values="pbt_impact_q05_rmb_mn")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.heatmap(heat / 1000, annot=True, fmt=".1f", cmap="RdYlGn", center=0, ax=ax)
    ax.set_title("5th-Percentile PBT Impact (RMB bn)")
    ax.set_xlabel("Pass-through ratio")
    ax.set_ylabel("Lithium-to-total-material beta")
    fig.tight_layout()
    fig.savefig(root / "reports" / "figures" / "commodity_downside_heatmap.png", dpi=180)
    plt.close(fig)


def generate_report(config: ResearchConfig) -> None:
    root = config.root
    _make_figures(config)
    summary = json.loads((root / "reports" / "analysis_summary.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((root / "data" / "processed" / "build_diagnostics.json").read_text(encoding="utf-8"))
    attribution = summary["return_attribution"]
    full = attribution["full"]
    oos = attribution["oos_validation"]
    commodity = summary["commodity_model"]
    peer_ic = pd.read_csv(root / "reports" / "tables" / "peer_rank_ic.csv")
    latest_scores = pd.read_csv(
        root / "data" / "processed" / "peer_operating_scores.csv", dtype={"symbol": str}
    )
    latest_scores = latest_scores.loc[latest_scores["report_date"].eq(latest_scores["report_date"].max())]
    catl = latest_scores.loc[latest_scores["symbol"].astype(str).str.zfill(6).eq("300750")].iloc[0]
    bridge = pd.read_csv(root / "data" / "processed" / "catl_2024_revenue_bridge.csv")
    h1 = pd.read_csv(root / "data" / "manual" / "catl_2025_h1_checkpoint.csv")
    h1_total = h1.loc[h1["segment"].eq("Total")].iloc[0]
    h1_ev = h1.loc[h1["segment"].eq("EV batteries")].iloc[0]
    h1_ess = h1.loc[h1["segment"].eq("ESS batteries")].iloc[0]
    internship = attribution["internship_window_attribution"]
    factor_contributions = {
        row["factor"]: row["cumulative_log_return_contribution"]
        for row in internship["factor_contributions"]
    }
    rank_ic_values = peer_ic["rank_ic"].dropna()

    lines = [
        "# CATL Quantitative Equity Research",
        "",
        "**Status:** legacy single-name economic-context module within a later independent public-data reconstruction. It is not UBS work product and is not the repository's systematic alpha strategy.",
        f"**Research cutoff:** {config.as_of}  ",
        "**Role of CATL:** historical research anchor; the models explain and test CATL rather than claim it was discovered by a screen.",
        "",
        "## Executive conclusion",
        "",
        "**Investment stance at the cutoff: operating-quality positive, equity view valuation-dependent.** CATL's 2024 revenue pressure was primarily an ASP problem, not a volume problem: battery volumes rose while reported EV and ESS ASPs fell sharply. Direct-material costs fell and segment margins improved. The July 2025 interim report then showed total revenue returning to growth, led by EV batteries, but with a modest year-on-year decline in EV segment margin. The evidence supports operating resilience; without clean point-in-time valuation and consensus-revision data, it does not support an unconditional Buy or target price.",
        "",
        f"The full weekly return-attribution model explains **{full['adjusted_r_squared']:.1%}** of in-sample variation. Its lithium coefficient is **{full['coefficients']['lithium_return']:.3f}** with a HAC p-value of **{full['p_values']['lithium_return']:.3f}**. In the rolling held-out comparison, the full-model RMSE is **{oos['full_rmse']:.4f}**, versus **{oos['market_only_rmse']:.4f}** for market-only, equivalent to **{oos['incremental_oos_r2_vs_market_model']:.1%}** lower squared error. Each held-out week is excluded from coefficient estimation, but its realized contemporaneous factor returns are used as explanatory inputs; this tests attribution stability rather than ex-ante tradable forecasting. The result is evidence that lithium adds conditional equity-return information, not evidence that higher lithium prices improve CATL's earnings.",
        "",
        f"Within the six-company battery-manufacturer comparison set, CATL's 2024 operating score ranks **{int(catl['operating_rank'])}/{int(catl['universe_size'])}**. But the three forward Rank IC observations range from **{rank_ic_values.min():.3f}** to **{rank_ic_values.max():.3f}** and are not robust. The score identifies relative operating quality, not a validated return factor. It deliberately excludes valuation because a clean point-in-time valuation history was unavailable in the public baseline.",
        "",
        "## 1. Research design",
        "",
        "The project combines four linked layers:",
        "",
        "1. revenue and cost decomposition from official CATL filings;",
        "2. weekly CATL return attribution against CSI 300, equal-weighted battery peers, and GFEX lithium carbonate;",
        "3. peer operating-quality validation using only annual reports released by each rebalance date;",
        "4. commodity downside scenarios with explicit pass-through and lithium-to-material-cost assumptions.",
        "",
        f"The model panel contains **{diagnostics['weekly_model_rows']} weekly observations** from {diagnostics['weekly_model_start']} through {diagnostics['weekly_model_end']}. No observation after the cutoff is accepted.",
        "",
        "## 2. Earnings-driver result",
        "",
    ]
    for _, row in bridge.iterrows():
        if row["effect"] in {"volume", "ASP"}:
            lines.append(f"- {row['segment']} {row['effect']} effect: RMB {row['revenue_effect_rmb_mn'] / 1000:.1f}bn (symmetric volume-price decomposition).")
    lines.extend(
        [
            "",
            "![Revenue bridge](../figures/revenue_bridge.png)",
            "",
            "CATL's H-share prospectus reports RMB202.7bn of 2024 direct-material costs, equal to 74.1% of cost of sales. It also gives a no-pass-through sensitivity of approximately RMB2.027bn of pre-tax profit for a 1% average direct-material-price move. This is the calibration anchor for deterministic scenarios; it is not presented as an internally estimated coefficient.",
            "",
            f"The top-five customers represented {diagnostics['customer_top5_share_pct']:.2f}% of revenue. Their disclosed shares contribute {diagnostics['customer_top5_hhi_contribution']:.4f} to HHI. This is explicitly a **top-five HHI contribution**, not full-company HHI.",
            "",
            "## 3. 2025H1 information-cutoff checkpoint",
            "",
            f"CATL reported 2025H1 revenue of RMB{h1_total['revenue_rmb_mn'] / 1000:.1f}bn, up {h1_total['revenue_yoy_pct']:.2f}% year on year. EV-battery revenue rose {h1_ev['revenue_yoy_pct']:.2f}% to RMB{h1_ev['revenue_rmb_mn'] / 1000:.1f}bn, while its gross margin fell {abs(h1_ev['gross_margin_yoy_ppt']):.2f}ppt to {h1_ev['gross_margin_pct']:.2f}%. ESS revenue fell {abs(h1_ess['revenue_yoy_pct']):.2f}% to RMB{h1_ess['revenue_rmb_mn'] / 1000:.1f}bn, while its margin improved {h1_ess['gross_margin_yoy_ppt']:.2f}ppt to {h1_ess['gross_margin_pct']:.2f}%.",
            "",
            "This checkpoint supports a differentiated view: EV demand/revenue momentum improved after 2024's price-led contraction, but margin normalization had begun; ESS retained stronger margin resilience despite softer revenue.",
            "",
            "## 4. Equity-return attribution",
            "",
            "![Cumulative returns](../figures/cumulative_returns.png)",
            "",
            "![Rolling betas](../figures/rolling_betas.png)",
            "",
            "The regression uses Newey-West/HAC standard errors. The equal-weighted peer factor excludes CATL. Lithium weekly returns are winsorized only at their 1st and 99th percentiles for the regression, while raw observations remain stored.",
            "",
            f"During the configured {internship['weeks']}-week summer analysis window, CATL's cumulative log return was **{_fmt_pct(internship['catl_cumulative_log_return'])}**. The fitted contributions were market **{_fmt_pct(factor_contributions['market_return'])}**, peer excess **{_fmt_pct(factor_contributions['peer_excess_market'])}**, lithium **{_fmt_pct(factor_contributions['lithium_return'])}**, and intercept **{_fmt_pct(internship['model_intercept_contribution'])}**; the remaining company-specific residual was **{_fmt_pct(internship['residual_contribution'])}**. The summer gain was therefore associated mainly with common market/sector/commodity states, while the residual was negative.",
            "",
            f"Directional accuracy is reported only as a secondary diagnostic: full model **{_fmt_pct(oos['full_directional_accuracy'])}**, market-only **{_fmt_pct(oos['market_only_directional_accuracy'])}**, naive always-positive **{_fmt_pct(oos['naive_positive_directional_accuracy'])}**. RMSE and incremental OOS R-squared are the primary tests.",
            "",
            "## 5. Peer-score validation",
            "",
            "The peer score uses equal weights across quality, growth, and balance-sheet categories. It is tested against subsequent excess returns from May 1 after annual-report season. With only six direct peers, Rank IC is descriptive evidence, not proof of a production factor.",
            "",
            peer_ic.to_markdown(index=False),
            "",
            "The validation does **not** support using the operating score as a standalone long-short signal. That negative result is retained rather than optimized away.",
            "",
            "## 6. Commodity scenarios",
            "",
            f"ADF p-value on weekly log lithium prices: **{commodity['adf_p_value_log_price']:.3f}**. AR(1) out-of-sample RMSE: **{commodity['ar1_oos_rmse']:.4f}**; random-walk RMSE: **{commodity['random_walk_oos_rmse']:.4f}**. Selected method: **{commodity['selected_simulation_method']}**.",
            "",
            "![Commodity downside heatmap](../figures/commodity_downside_heatmap.png)",
            "",
            "The heatmap is conditional. The mapping from a lithium-price shock to total direct-material cost is a scenario beta, and customer pass-through is also a scenario parameter. Neither is mislabeled as a disclosed CATL fact. The AR(1) RMSE advantage over a random walk is small, so the simulated quantiles should be treated as model-sensitive ranges rather than precise forecasts.",
            "",
            "## 7. Decision framework",
            "",
            "- **Positive evidence:** top-ranked operating quality in the direct peer set, 2025H1 return to revenue growth, and a lower 2024 direct-material burden.",
            "- **Watch items:** EV margin normalization, ESS revenue softness, customer concentration, and the residual share of material shocks not passed through.",
            "- **Equity discipline:** require contemporaneous valuation and earnings-revision data before converting operating strength into a rating or target price.",
            "- **Model discipline:** use market/peer/lithium exposures for attribution and monitoring, not as causal earnings coefficients.",
            "",
            "## 8. Defensible interpretation of this legacy module",
            "",
            "- The filing-based operating result is pricing pressure despite volume growth.",
            "- The return model separates broad-market, peer-sector, commodity, and residual components.",
            "- The earnings model translates material-cost shocks into conditional PBT impacts using a filing-derived sensitivity anchor.",
            "- The stochastic model is selected by diagnostics; an OU/AR(1) process is not forced when stationarity and out-of-sample tests do not support it.",
            "- The score backtest is validation of a research ranking, not a claim of a profitable trading strategy.",
            "- These statements describe the later public reconstruction. Attribution to a 2025 internship requires separate contemporaneous evidence.",
            "",
            "## 9. Data limitations and next upgrade",
            "",
            "The public baseline uses Eastmoney/Sina adapters and official CATL filings. A production-quality rerun should replace vendor proxies with point-in-time Wind/Bloomberg market and valuation exports, an SMM/Fastmarkets spot lithium series, and dated monthly industry data. The import contracts are documented in `data/README.md`.",
            "",
            "## Sources",
            "",
            "- [CATL 2024 Annual Report](https://www.catl.com/uploads/1/file/public/202503/20250317094543_6ig9e0mwng.pdf)",
            "- [CATL 2025 H-share Prospectus](https://www.catl.com/en/uploads/1/file/public/202505/20250512071033_9of2dqw816.pdf)",
            "- [CATL 2025 Interim Report](https://www.catl.com/uploads/1/file/public/202507/20250730224404_1re4ofju1s.pdf)",
            "- [GFEX historical market-data reference](https://www.gfex.com.cn/en/MarketData/HistoricalData.shtml)",
        ]
    )
    generated = root / "reports" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    (generated / "research_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
