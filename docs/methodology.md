# Methodology and research controls

## Research clock

The project is frozen at 29 August 2025. Market observations after that date are rejected. Fundamental records have both a fiscal period and a public notice date; only information released on or before the cutoff is eligible. CATL's 2025 interim report, released on 31 July 2025, is therefore included as an in-internship checkpoint.

## Universe

CATL is the mentor-assigned focal company. The direct operating comparison set contains BYD, EVE Energy, Gotion High-Tech, Sunwoda, and Farasis Energy. A broader value-chain list is downloaded for extension work but is not mixed into the six-company battery-manufacturer score.

## Data pipeline

1. Download adjusted A-share prices and CSI 300 history through public adapters, with a per-symbol fallback recorded in `data/source_manifest.json`.
2. Download the GFEX lithium-carbonate main continuous contract. This is a vendor-constructed continuous series, not an official spot price; the distinction is retained in the source manifest.
3. Download annual fundamental metrics and retain only records whose notice dates are no later than the cutoff.
4. Record filing-derived CATL facts in small manual tables with document, release-date, and page references. Official PDFs can be downloaded and checksum-verified with `scripts/download_filings.py`.
5. Resample prices to Friday weeks and compute log returns. Winsorize lithium returns at the 1st and 99th percentiles only in the regression copy.

## Earnings bridge

For a segment with volume \(V\) and ASP \(P\), the symmetric two-factor decomposition is:

\[
\Delta R_V=(V_1-V_0)(P_0+P_1)/2
\]

\[
\Delta R_P=(P_1-P_0)(V_0+V_1)/2
\]

This avoids assigning the interaction term arbitrarily to volume or price. Rounding in reported GWh and RMB/Wh creates a small gap from disclosed revenue changes.

## Return attribution

The weekly model is:

\[
r^{CATL}_t=\alpha+\beta_m r^{CSI300}_t+\beta_p(r^{Peers}_t-r^{CSI300}_t)+\beta_{Li}r^{Li}_t+\epsilon_t
\]

The peer return is equal weighted and excludes CATL. Inference uses Newey-West/HAC standard errors with four lags. The model is compared with a market-only baseline in a 78-week rolling out-of-sample exercise. It is an attribution model, not a causal model or trading strategy.

## Peer score

The score gives equal category weights to quality, growth, and balance sheet. Quality averages ROE, gross margin, and net margin z-scores; growth averages revenue and net-profit growth z-scores; balance sheet uses the negative debt-ratio z-score. Cross-sectional inputs are 5th/95th percentile clipped. Valuation is excluded because a clean point-in-time public valuation history was unavailable.

Each annual score is validated against excess returns beginning 1 May after the reporting season. With six firms and three evaluation windows, the resulting Rank IC values are diagnostics only.

## Commodity stress test

Weekly lithium log prices are tested for a unit root. An AR(1) simulation is used only if the ADF test, coefficient bounds, and out-of-sample RMSE jointly support it; otherwise the code uses a four-week moving-block bootstrap.

CATL disclosed RMB202.7bn of 2024 direct-material cost and a roughly RMB2.027bn no-pass-through PBT sensitivity to a 1% average direct-material-price change. The stress test maps simulated lithium moves to total materials using explicit scenario betas and customer pass-through ratios. These are assumptions, not estimated causal coefficients.

## Controls and limitations

- The code rejects post-cutoff market and filing dates and duplicate observations.
- Raw vendor files are not committed; their providers and retrieval metadata are recorded.
- A positive lithium coefficient in the stock-return model does not mean higher lithium prices improve CATL's earnings. It can proxy for battery-sector demand, risk appetite, or other common states.
- No valuation data means the repository can defend relative operating quality, but not an unconditional target price or rating.
- Public adapters are suitable for a transparent baseline, not a substitute for Wind/Bloomberg/SMM point-in-time production data.
