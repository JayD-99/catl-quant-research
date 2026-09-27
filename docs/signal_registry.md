# Systematic Signal Registry

Registered before the first end-to-end systematic backtest on 25 September 2026.

This registry prevents the public reconstruction from testing many definitions and reporting only the winner. Every signal below has an economic rationale, a fixed direction, a fixed lookback, and a declared role. Failed signals remain in the report.

## Research target

At each monthly signal date, rank the then-available members of the public battery-theme universe by their next-rebalance relative return:

\[
y_{i,t+1}=R_{i,t\rightarrow t+1}-R_{b,t\rightarrow t+1}.
\]

Signals use information available no later than the trading day before the month-end execution date. Financial statements enter only after their recorded notice date. Portfolio returns begin at the execution close and end at the following month-end execution close.

## Pre-registered signal families

| Family | Inputs | Fixed direction | Economic hypothesis | Composite role |
|---|---|---|---|---|
| Price momentum | 12–1 month and 6–1 month adjusted-price returns | Higher is better | Medium-horizon information and trend continuation persist after skipping the most recent month | 25% |
| Operating quality | ROE, gross margin, net margin, and negative debt ratio from the latest available filing | Higher is better | More profitable, less levered firms have more resilient cash-generation capacity | 25% |
| Fundamental momentum | Reported revenue growth, profit growth, and year-on-year changes in ROE and gross margin | Higher is better | Improvements relative to the prior comparable reporting period matter more than static levels | 25% |
| Low risk | Negative 63-day volatility and negative 126-day idiosyncratic volatility | Lower risk is better | Within a volatile thematic universe, low-risk names may deliver better risk-adjusted subsequent returns | 25% |

The four family scores are equal weighted. No IC-optimized or machine-learned family weights are allowed in the baseline.

## Risk and liquidity descriptors—not alpha

The following are controls, portfolio constraints, or diagnostics and are not included in the baseline alpha score:

- 126-day market beta;
- 20-day average daily traded value;
- 63-day Amihud illiquidity;
- broad value-chain group;
- benchmark weight;
- lithium-price exposure.

Lithium exposure remains a risk descriptor because the old single-name project established only contemporaneous association, not ex-ante predictive power.

## Fixed transformations

For each monthly cross-section:

1. require the configured minimum history and information availability;
2. clip each raw descriptor at median plus or minus five median absolute deviations;
3. standardize cross-sectionally;
4. neutralize each signal against log 20-day ADV and, where group coverage permits, broad value-chain groups;
5. re-standardize the residual;
6. average descriptors within a family;
7. require at least three of the four families before calculating the composite score.

No future return enters clipping, scaling, neutralization, missing-value treatment, or family construction.

## Validation plan

The chronological partitions are fixed in `config/systematic.yaml`:

- design: through 30 June 2023;
- validation: 1 July 2023 through 30 June 2024;
- final holdout: 1 July 2024 through 29 August 2025.

The final holdout is short. It is evidence about this public prototype, not proof of persistent institutional alpha.

For every signal and for the composite, report:

- monthly Pearson IC and Spearman Rank IC;
- mean Rank IC, ICIR, positive-month ratio, Newey–West t-statistic, and Benjamini–Hochberg adjusted p-value;
- equal-weight quantile returns and top-minus-bottom spread;
- design, validation, final-holdout, and full-period results;
- coverage, turnover, concentration, and subperiod behavior.

## Portfolio plan fixed before results

Two different portfolios answer different questions:

1. A top-minus-bottom equal-weight portfolio is a **factor diagnostic only**. It is not presented as executable A-share shorting because historical borrow availability and fees are unavailable.
2. A benchmark-relative long-only portfolio is the implementation simulation. It uses an exponential score tilt, broad-group neutrality, single-name and active-weight caps, beta and tracking-error scaling, turnover and ADV participation limits, and explicit transaction costs.

The baseline cost model includes commission, sell-side stamp duty with its dated 2023 rate change, a spread allowance, and volatility/participation-dependent market impact. Results are also rerun at half and double baseline costs.

## Pre-registered failure conditions

The composite is not described as a validated alpha signal if any of the following occurs:

- final-holdout mean Rank IC is non-positive;
- final-holdout top-minus-bottom spread is non-positive;
- long-only final-holdout net active return or Information Ratio is non-positive;
- apparent performance is dominated by one company, one value-chain group, or an unconstrained liquidity exposure;
- the sign reverses under double costs or a one-day additional signal lag;
- the result depends on using information before its notice or membership availability date.

Even if the signal passes these checks, the public-data and historical-membership limitations prevent a claim of production readiness.

## Experiment log

| Experiment ID | Status before run | Allowed decision after result |
|---|---|---|
| `single_price_momentum_v1` | Registered | Report; do not change sign or window |
| `single_operating_quality_v1` | Registered | Report; do not change components after seeing IC |
| `single_fundamental_momentum_v1` | Registered | Report; retain negative profit-growth behavior if present |
| `single_low_risk_v1` | Registered | Report separately from alpha/risk controls |
| `equal_weight_composite_v1` | Registered primary signal | Freeze through final holdout |
| `benchmark_tilt_long_only_v1` | Registered primary portfolio | Report gross, net, costs, risk and capacity |

Any later change creates a new experiment ID and cannot reuse the current final holdout as untouched evidence.

## Post-run disposition — 26 September 2026

This section records the frozen baseline's outcome; it does not alter the rules above.

| Experiment ID | Observed final-holdout result | Disposition |
|---|---|---|
| `single_price_momentum_v1` | Mean Rank IC -0.060; top-minus-bottom -2.35% per month | Failed final holdout |
| `single_operating_quality_v1` | Mean Rank IC 0.014; top-minus-bottom -1.05% per month | Not validated |
| `single_fundamental_momentum_v1` | Mean Rank IC 0.052; top-minus-bottom -0.57% per month | Not validated |
| `single_low_risk_v1` | Mean Rank IC 0.098; top-minus-bottom +1.41% per month, but short sample and weak inference | Research lead only; not production evidence |
| `equal_weight_composite_v1` | Mean Rank IC 0.047 but top-minus-bottom -0.87% per month | Failed registered spread gate |
| `benchmark_tilt_long_only_v1` | -0.41% annualized net active return and -0.43 information ratio | Failed registered portfolio gates |

At double baseline costs, the final-holdout annualized active return is -0.66%. Moving the signal cutoff back from one to two trading days before execution produces -0.45% annualized active return. The composite therefore remains rejected.

The validation interval's stronger numbers are retained as a warning about regime dependence, not selected as the headline result. Any revised signal—such as a low-risk-only model, new valuation data or different family weights—must receive a new experiment ID and cannot reuse July 2024–August 2025 as an untouched final holdout.
