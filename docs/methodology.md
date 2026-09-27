# Systematic Equity Research Methodology

## 1. Research object

The primary research object is a repeatable monthly cross-sectional decision in an A-share battery-value-chain universe—not a recommendation on CATL alone.

For security \(i\) and month-end execution date \(t\), the target is next-rebalance excess return:

\[
y_{i,t+1}=R_{i,t\rightarrow t+1}-R_{b,t\rightarrow t+1}.
\]

The registered baseline uses information through the trading day immediately before execution. The timing stress moves the feature cutoff back to two trading days before execution. In both cases the forward label starts at the execution close, so no execution-day close enters a feature.

The analytical cutoff is 2025-08-29. The repository was built later in 2026. An analytical cutoff limits the information admitted to a model; it is not evidence that the model existed by the cutoff.

## 2. Universe construction

### 2.1 Public proxy

The tracked CSI battery-theme index does not provide an immutable public constituent history through the current adapters. The baseline therefore uses disclosed holdings of ETF 561910 as a conservative membership proxy:

- select disclosed Q2 and Q4 holdings;
- sort by disclosed weight and retain the top 50;
- make Q2 usable 60 calendar days after June 30;
- make Q4 usable 90 calendar days after December 31;
- at each signal date select the latest snapshot whose `snapshot_date` and `available_date` are both no later than the signal date.

This produces 400 snapshot-security rows and 75 unique historical names. Snapshot weights are normalized inside each portfolio date because the disclosed top holdings need not sum exactly to one.

### 2.2 Exclusions and survivorship

The manual mapping records every historical symbol. BSE-listed 920185 is excluded before modeling because BSE price limits, liquidity, investor mix and public data coverage are not directly comparable with the Shanghai/Shenzhen baseline. The exclusion is visible and rule-based; the raw membership record is retained.

Delisted 300116 is retained. Yahoo lacks its full history, so Tencent/AkShare raw and back-adjusted prices are used. Removing it because it later failed would create survivorship bias.

An unavailable price at an execution or next-execution close produces a missing label; the observation is not assigned a zero return.

## 3. Data clock and schemas

### 3.1 Market data

The market table stores raw and adjusted OHLCV separately:

- adjusted close is used for return features and labels;
- raw close multiplied by raw volume is used for traded-value liquidity;
- the adjustment factor remains auditable;
- duplicate `(date, symbol)` observations are rejected;
- prices must be positive and volume non-negative.

CSI 300 ETF 510300 is the market-beta proxy because the public Yahoo index ticker was unavailable in the frozen download. ETF tracking error and distributions therefore remain a limitation.

### 3.2 Fundamentals

Each financial row contains:

- `report_date`: accounting period represented;
- `notice_date`: public announcement date;
- `available_date`: conservative usable date.

The effective date is the later of notice and availability. At signal date \(s\), the feature engine admits only records satisfying

\[
effective\_date \le s, \qquad report\_date \le s.
\]

If a provider later supplies multiple versions for the same period, the last version already available by \(s\) is selected. This prevents an explicitly later version from entering early, but cannot identify an undocumented vendor backfill inside an already downloaded history.

### 3.3 Broad groups

Every included symbol receives one manually curated group:

- battery cells and systems;
- battery materials;
- industrial equipment and components;
- power equipment and energy services.

These are broad neutralization controls, not a claim to an official GICS, CITIC or exchange classification.

## 4. Monthly calendar and labels

For each calendar month:

1. `execution_date` is the last available trading day;
2. baseline `signal_date` is the previous trading day;
3. `next_execution_date` is the last trading day of the next month;
4. all price histories are truncated at `signal_date`;
5. the forward return is

\[
R_{i,t\rightarrow t+1}=\frac{P^{adj}_{i,t+1}}{P^{adj}_{i,t}}-1.
\]

The signal date intentionally precedes execution. Changing a price on the execution date changes the label but not the feature vector; a unit test enforces this property.

## 5. Price and risk descriptors

### 5.1 Momentum

With daily adjusted closes and a 21-trading-day skip:

\[
MOM^{12-1}_{i,t}=\log\left(\frac{P_{i,t-21}}{P_{i,t-252}}\right),
\]

\[
MOM^{6-1}_{i,t}=\log\left(\frac{P_{i,t-21}}{P_{i,t-126}}\right).
\]

Skipping the most recent month separates medium-horizon continuation from very short-run reversal and microstructure effects.

### 5.2 Total volatility

Using the most recent 63 daily simple returns:

\[
\sigma^{63}_{i,t}=sd(r_{i,d})\sqrt{252}.
\]

At least 50 observations are required.

### 5.3 Market beta and idiosyncratic volatility

Over the latest 126 aligned daily returns:

\[
r_{i,d}=\alpha_i+\beta_i r^{510300}_d+\epsilon_{i,d}.
\]

The OLS slope is the beta descriptor. Annualized residual volatility is

\[
\sigma^{idio}_{i,t}=sd(\epsilon_{i,d})\sqrt{252}.
\]

At least 100 aligned observations are required. Beta is a risk control; negative total and idiosyncratic volatility form the low-risk alpha family.

### 5.4 Liquidity

Twenty-day average daily traded value is

\[
ADV20_{i,t}=\frac{1}{20}\sum_{d=t-19}^{t}P^{raw}_{i,d}V_{i,d}.
\]

The Amihud descriptor is

\[
ILLIQ_{i,t}=\frac{1}{20}\sum_{d=t-19}^{t}\frac{|r_{i,d}|}{P^{raw}_{i,d}V_{i,d}}.
\]

ADV is used for eligibility, neutralization and capacity. Amihud is a diagnostic and is not included in the baseline alpha composite.

## 6. Fundamental descriptors

The public Eastmoney adapter contains revenue, parent net profit, ROE, gross margin, net margin and debt ratio.

### 6.1 Operating quality

When full statements are available, the engine can use gross profitability, accrual quality and negative leverage scaled by assets. In the frozen public baseline those balance-sheet fields are absent, so the documented fallback is

\[
Q_{i,t}=\frac{ROE_{i,t}+GM_{i,t}+NM_{i,t}-DebtRatio_{i,t}}{4},
\]

with percentages converted to decimals before averaging. Cross-sectional robust standardization follows, so the raw level is not interpreted as a probability or score out of 100.

### 6.2 Fundamental growth

For the latest filing and prior comparable period:

\[
Growth_{i,t}=\frac{1}{2}\left(RevenueYoY_{i,t}+ProfitYoY_{i,t}\right).
\]

When canonical statement fields exist, profit change is scaled by prior assets; otherwise the provider's reported year-on-year profit growth is used.

### 6.3 Quality momentum

\[
\Delta Q_{i,t}=Q_{i,t}-Q_{i,t-1y}.
\]

Fundamental momentum averages the transformed growth and quality-change descriptors. No filing enters before its effective date.

## 7. Cross-sectional transformation

Each raw descriptor is transformed independently within each monthly cross-section.

### 7.1 Median/MAD clipping

For descriptor \(x\):

\[
m=median(x), \qquad MAD=median(|x-m|),
\]

\[
s_{robust}=1.4826\,MAD.
\]

Values are clipped to \(m\pm5s_{robust}\). If MAD is zero, population standard deviation is the fallback. The clipped values receive a conventional mean-zero, unit-standard-deviation z-score.

### 7.2 Simultaneous neutralization

The robust z-score is regressed on an intercept, demeaned log ADV and broad-group dummies:

\[
z_{i,t}=a_t+b_t\log(ADV20_{i,t})+\sum_g\gamma_{g,t}D_{i,g}+u_{i,t}.
\]

The residual \(u_{i,t}\) is re-standardized. A simultaneous regression avoids reintroducing a liquidity exposure through sequential group demeaning.

This step removes linear exposure to the chosen controls. It does not prove that all size, liquidity or industry effects are absent.

## 8. Signal families and composite

The definitions were fixed in `docs/signal_registry.md` before the end-to-end run:

\[
S^{mom}=\frac{z(MOM^{12-1})+z(MOM^{6-1})}{2},
\]

\[
S^{quality}=z(Q),
\]

\[
S^{fundmom}=\frac{z(Growth)+z(\Delta Q)}{2},
\]

\[
S^{lowrisk}=-\frac{z(\sigma^{63})+z(\sigma^{idio})}{2}.
\]

The baseline composite is

\[
S^{comp}=\frac{1}{4}\left(S^{mom}+S^{quality}+S^{fundmom}+S^{lowrisk}\right).
\]

At least three families and at least 60% component coverage within a family are required. The baseline data in practice have high coverage. Family weights are not estimated from IC because doing so on this short sample would amplify overfitting.

Eligibility additionally requires at least 252 price-history observations and RMB50 million ADV20.

## 9. Chronological research design

Random train/test shuffling is inappropriate because it mixes market regimes and can let future relationships inform earlier observations. The fixed partitions are:

- design: through 2023-06-30;
- validation: 2023-07-01 through 2024-06-30;
- final holdout: 2024-07-01 through 2025-08-29.

There are 15, 12 and 13 labeled months respectively. The August 2025 signal cross-section has no next-month return before the cutoff and remains unlabeled.

The final holdout cannot remain “untouched” after it has been viewed. Any revised signal must receive a new experiment ID and a new future holdout.

## 10. Signal evaluation

### 10.1 Information coefficient

For each month and signal, the engine calculates:

- Pearson correlation between signal and next-month excess return;
- Spearman Rank IC between their cross-sectional ranks.

Spearman IC is primary because the portfolio thesis is monotonic ranking rather than a precise linear return forecast.

### 10.2 Mean-IC inference

Monthly ICs can be serially correlated and heteroskedastic. The mean is estimated as the intercept in a constant-only regression with Newey–West/HAC covariance and three lags.

The repository reports mean IC, standard deviation, ICIR, positive-month ratio, HAC t-statistic and p-value.

### 10.3 Multiple testing

Five registered scores are evaluated: four families and the composite. Benjamini–Hochberg adjusted p-values control the false discovery rate within each chronological partition. This does not compensate for unrecorded experiments outside the registry.

### 10.4 Quantile diagnostics

Within each month, names are sorted by signal into five equal-count groups when the sample permits; otherwise three groups are used. The diagnostic spread is

\[
R^{spread}_{t}=\bar R^{top}_{t}-\bar R^{bottom}_{t}.
\]

It is not claimed as an executable A-share long-short strategy because historical borrow availability, recall risk and borrow fees are unavailable.

## 11. Portfolio construction

### 11.1 Raw benchmark-relative tilt

Let \(b_i\) be the normalized delayed ETF weight and \(s_i\) the composite score. The raw tilt is

\[
\tilde w_i=b_i\exp(0.35s_i).
\]

Each broad group's raw weights are first rescaled to its benchmark group weight.

### 11.2 Feasibility projection

The code then minimizes squared distance from the raw tilt:

\[
\min_w \sum_i(w_i-\tilde w_i)^2
\]

subject to

\[
\sum_i w_i=1,\quad w_i\ge0,
\]

\[
w_i\le12\%,\quad |w_i-b_i|\le3\%,
\]

and each broad group's weight equaling its benchmark group weight. SLSQP solves the projection. If the numerical solver fails, the code falls back to the benchmark rather than using an infeasible portfolio.

This is a transparent score-tilt projection, not a claim of a globally optimal expected-return model.

### 11.3 Covariance and tracking error

The 126-day sample covariance is shrunk toward its diagonal:

\[
\Sigma^{shrunk}=0.65\Sigma^{sample}+0.35\,diag(\Sigma^{sample}),
\]

then annualized by 252. Active tracking error is

\[
TE=\sqrt{(w-b)^\top\Sigma^{shrunk}(w-b)}.
\]

The active vector is scaled toward the benchmark if TE exceeds 10% or if

\[
|(w-b)^\top\beta|>0.10.
\]

### 11.4 Turnover and capacity

One-way turnover is documented as

\[
TO_t=\frac12\sum_i|w_{i,t}-w^{drift}_{i,t}|.
\]

It is capped at 25% per month. For RMB100 million assumed AUM, a trade cannot exceed 5% of ADV20. The whole discretionary trade vector is scaled by the tightest turnover or capacity constraint.

When a security leaves the current universe, its old holding is not silently dropped. It is explicitly set to zero, counted as a forced sell and charged transaction costs. Tests check this universe transition and NAV reconciliation.

## 12. Transaction-cost model

For trade weight \(\Delta w_i\):

### 12.1 Linear costs

\[
C^{commission}=\sum_i|\Delta w_i|\frac{3}{10,000},
\]

\[
C^{spread}=\sum_i|\Delta w_i|\frac{5}{10,000}.
\]

Sell-side stamp duty is 10 bps before 2023-08-28 and 5 bps on or after that date:

\[
C^{stamp}=\sum_i\max(-\Delta w_i,0)\frac{d_t}{10,000}.
\]

### 12.2 Square-root impact

Participation is

\[
p_i=\frac{|\Delta w_i|\cdot AUM}{ADV20_i}.
\]

The impact rate is

\[
c^{impact}_i=\eta\sigma^{daily}_i\sqrt{p_i},\qquad \eta=0.25,
\]

and impact cost is \(\sum_i|\Delta w_i|c^{impact}_i\).

Costs are paid from residual cash. If planned cash is insufficient, risky holdings are scaled pro rata and costs recomputed until risky weights plus cash plus costs equal opening NAV. This prevents implicit borrowing of the cost amount.

The full simulation is rerun at 0.5×, 1× and 2× all estimated costs.

## 13. Performance metrics

For each split and cost multiplier, the report includes:

- cumulative gross, net and benchmark return;
- geometric annualized return;
- annualized volatility and zero-rate Sharpe ratio;
- annualized active return;
- tracking error and information ratio;
- maximum drawdown and active-month hit rate;
- average turnover and gross traded weight;
- forced exits and cash weights;
- total and component cost drag.

Active return is the difference between annualized geometric strategy and benchmark returns. Information ratio uses the monthly active-return mean divided by its standard deviation, annualized by \(\sqrt{12}\).

## 14. Robustness and failure rules

The composite is not validated if any registered core gate fails:

- final-holdout mean Rank IC is non-positive;
- final-holdout top-minus-bottom spread is non-positive;
- final-holdout net active return or information ratio is non-positive;
- double costs make active return non-positive;
- an additional signal lag causes the relevant result to fail;
- one company or group dominates the apparent result;
- point-in-time rules are violated.

The holdings-based concentration audit sums absolute single-name active-return contributions. It is not a full leave-one-name-out re-optimization. CATL contributes about 7.1% of total absolute single-name activity in the final holdout; maximum broad-group active weight is about 1.5 bps.

## 15. Observed results

The final-holdout composite has mean Rank IC 0.047, but the HAC p-value is 0.167 and FDR-adjusted p-value 0.208. Its equal-weight top-minus-bottom return is -0.87% per month.

The cost-aware long-only simulation has:

- annualized net return 47.74%;
- battery-universe benchmark return 48.14%;
- annualized active return -0.41%;
- tracking error 1.22%;
- information ratio -0.43;
- annual arithmetic cost drag about 0.17%;
- average one-way turnover about 5.4% per month.

The high absolute returns reflect the battery-theme benchmark regime and are not alpha. The relevant measure is active return, which is negative.

At double costs, annualized active return is -0.66%. At the two-trading-day signal lag, it is -0.45%. The registered composite is rejected as persistent alpha.

## 16. Legacy CATL context

The repository retains the earlier single-name modules only as an economic layer:

- symmetric volume/ASP bridge: operating decomposition;
- market/peer/lithium regression: contemporaneous conditional attribution;
- rolling coefficients: parameter-stability diagnostic;
- six-company score: small-universe operating diagnostic;
- commodity simulation: assumption-dependent stress scenario.

None is called a tradable forecast or production factor. The old held-out attribution is particularly important: its coefficients are estimated on prior weeks, but the evaluation week uses already realized market, peer and lithium returns. It tests mapping stability, not information available before that week.

## 17. Known limitations

- delayed ETF holdings are not official historical index membership;
- the public sample has only 40 labeled months and 13 final-holdout months;
- public vendor fundamentals may be restated or backfilled;
- 510300 is an ETF proxy for CSI 300 market returns;
- industry groups are manual and broad;
- absent point-in-time valuation and analyst-revision data limit the signal library;
- the optimizer is a sequential transparent projection, not a joint alpha-risk-cost optimizer;
- bid/ask history, limit queues, suspensions and auction execution are not reconstructed;
- impact parameters are estimates rather than calibrated fills;
- long-short diagnostics omit borrow availability and fees;
- a public backtest is not live deployment or realized P&L.

The model should be described as a falsifiable public research prototype, not a production strategy.
