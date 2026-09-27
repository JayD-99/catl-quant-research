# Systematic Equity QR Interview Defense

## First rule: keep the timeline truthful

The public systematic project was created after the internship. The analytical cutoff is 2025-08-29, but the repository and systematic results were produced in 2026.

Never answer as if the current pipeline was an UBS deliverable unless contemporaneous evidence separately proves that. The defensible story has two parts:

1. **2025 UBS internship:** only tasks, tools and outputs verified by dated evidence;
2. **2026 independent project:** the public universe, signals, backtests, cost model, code and current results.

If an interviewer asks directly:

> The CATL topic originated around my internship, but the public systematic pipeline was a later independent reconstruction and extension. It is not UBS work product and contains no UBS proprietary data or views.

If AI coding assistance was material:

> I used AI coding assistance in the public reconstruction. I do not claim unaided line-by-line authorship. I take responsibility for understanding the design, checking the timing and formulas, running the tests and being able to reproduce and critique every reported result.

## 90-second English answer

> The earlier CATL work was closer to quantitative fundamental research, so I later rebuilt the question as a genuine systematic-equity QR project using public data.
>
> I first reconstructed a changing battery-theme universe from delayed ETF-holding disclosures instead of applying today's constituents to the past. The raw universe contained 75 historical names; I retained a delisted constituent through a fallback data source and excluded one BSE name under a documented pre-model comparability rule. I then built a point-in-time monthly panel using adjusted prices and notice-dated fundamentals, with every feature cut off before the month-end execution close.
>
> I pre-registered four interpretable signal families—price momentum, operating quality, fundamental momentum and low risk. I used robust cross-sectional standardization and neutralized descriptors against liquidity and broad value-chain groups. I evaluated them with monthly Rank IC, Newey-West inference, false-discovery-rate control and quantile portfolios across design, validation and final-holdout periods.
>
> I then translated the equal-weight composite into a benchmark-relative long-only simulation with single-name, active-weight, beta, tracking-error, turnover and ADV constraints. Costs included commission, spread, the dated A-share stamp-duty change and square-root market impact, with explicit costs for forced constituent exits.
>
> The key result was negative. Final-holdout composite Rank IC was mildly positive at about 0.047, but the top-minus-bottom return was negative 0.87% per month and the cost-aware long-only active return was about negative 0.4% annualized with a negative information ratio. Double costs and an additional signal lag remained negative. I therefore rejected the composite rather than presenting it as validated alpha. That distinction—between a complete QR process and a successful signal—is the main lesson.

## 90秒中文答案

> 原来的 CATL 项目本质上更接近量化辅助的基本面研究，所以我后来用公开数据把研究对象重新定义成真正的系统化股票量化研究。
>
> 我先用 ETF 历史持仓披露重建随时间变化的电池主题股票池，而不是拿今天的成分股回看过去。原始股票池共有 75 个历史证券；我通过备用数据源保留了一家后来退市的公司，降低幸存者偏差，并在建模前按公开规则排除了一只北交所股票。然后我用复权行情和带公告日的财务数据建立月度 point-in-time 面板，所有特征都截止到月末执行日前。
>
> 我事先登记了四类信号：价格动量、经营质量、基本面动量和低风险。每个月对因子做 MAD 异常值处理、横截面标准化，并对成交额和宽泛产业链分组做中性化。我用 Rank IC、Newey–West 均值检验、FDR 多重检验修正和分组收益，分别检查 design、validation 和 final holdout。
>
> 接着我把等权综合分数转成基准相对的纯多头组合，加入单票和主动权重上限、beta、跟踪误差、换手率、ADV 容量约束，以及佣金、价差、印花税和平方根冲击成本；成分股退出也要真实卖出并计费。
>
> 最终结果是负面的。留出期综合 Rank IC 约为 0.047，但多空诊断月均收益是负 0.87%，计入基准成本后的年化主动收益约为负 0.4%，信息比率也是负的；双倍成本和额外一天信号滞后仍然为负。所以我拒绝了这个综合信号，没有把它包装成有效 alpha。这个项目最能体现 QR 的地方，不是回测赚钱，而是研究链完整、失败条件预先确定，而且结果不好时真的停止。

## 30-second version

> I independently rebuilt a CATL-related topic into a monthly A-share systematic-equity research project. I reconstructed a delayed historical battery universe, engineered four point-in-time signal families, tested them with chronological IC and quantile analysis, and ran a benchmark-relative long-only portfolio with risk, turnover, capacity and explicit cost constraints. The final holdout failed: Rank IC was mildly positive, but the return spread and net active return were negative. I rejected the signal rather than claiming alpha.

---

## A. Role and research design

### Q1. Is this Quant Research or Equity Research?

The old CATL layer is quant-assisted single-name Equity Research. The rebuilt main project is Systematic Equity QR because the repeated decision is cross-sectional stock ranking and portfolio construction across a changing universe. I keep both classifications explicit.

### Q2. Why is it not Quant Trader work?

I do not use intraday quotes, order books, fill probabilities, queue position, market-making inventory or live orders. I estimate monthly implementation costs, but that belongs in a credible QR backtest. It does not prove trading or execution experience.

### Q3. What exact decision does the model support?

At each month-end, it asks which then-eligible battery-value-chain stocks should receive positive or negative active weights relative to the delayed battery-universe benchmark for the next month.

### Q4. What is the target?

\[
y_{i,t+1}=R_{i,t\rightarrow t+1}-R_{b,t\rightarrow t+1}.
\]

It is next-month relative return. Features stop before the execution close. The target starts at that execution close and ends at the next month-end execution close.

### Q5. Why monthly frequency?

The core public fundamentals update quarterly or semiannually, the universe proxy updates from periodic holdings disclosures, and the strategy is a medium-frequency stock-selection exercise. Monthly rebalancing is more consistent with the data clock and keeps turnover more plausible than daily trading.

### Q6. Did the model discover CATL?

No. CATL was an economic research anchor and one historical constituent. The systematic model ranks every eligible stock each month. I never present CATL as an ex-post winner discovered by the signal.

---

## B. Universe and data

### Q7. Why use ETF holdings rather than today's peer list?

Using today's names historically creates membership and survivorship bias. Public ETF Q2/Q4 disclosures give a time-varying proxy. I impose 60- and 90-day delays so a snapshot cannot be used before a conservative public-availability date.

### Q8. Is ETF membership the same as official index membership?

No. It is a transparent public proxy. ETF holdings can reflect cash, tracking differences or disclosure conventions. A production version should license an official immutable constituent history.

### Q9. What did you do about delisted stocks?

I retained 300116 while it was historically present. Yahoo had no usable series, so the download layer falls back to Tencent via AkShare. Deleting it after delisting would improve the historical universe with information not available at the time.

### Q10. Why exclude 920185?

It is BSE-listed. BSE trading rules, liquidity and public-data coverage differ from the Shanghai/Shenzhen baseline. I made the exclusion before signal modeling, recorded it in the manual mapping and retained the raw membership record. The limitation is visible rather than silently deleting the name.

### Q11. Why use both raw and adjusted prices?

Adjusted prices are needed for economically meaningful returns across splits and dividends. Raw close and raw volume are needed for traded value and cost capacity. Using adjusted price times raw volume could distort historical ADV.

### Q12. How did you control fundamental look-ahead?

Every row has a report period and public notice/availability date. At a signal date, I select only versions whose effective date is no later than the signal date. A later vendor revision has its own availability date and cannot enter early.

### Q13. Does that fully solve point-in-time bias?

No. The data were downloaded later, so a vendor might restate or backfill a historical field without exposing its revision history. Notice-date filtering blocks obvious leakage but is weaker than a contemporaneously archived vendor snapshot.

### Q14. Why 510300 instead of the CSI 300 index itself?

The frozen Yahoo run did not return the public CSI index ticker reliably, while the 510300 ETF did. It is used only as a market-beta proxy. Tracking error and distributions are documented limitations.

### Q15. What is the data scale?

The frozen inputs contain 400 membership rows, 147,955 daily market rows and 3,838 notice-dated fundamental rows. The baseline monthly panel contains 2,037 security-month rows; 1,984 pass the systematic eligibility filter across 41 signal months and 73 securities. Forty months have a forward label.

---

## C. Feature engineering

### Q16. Define 12–1 momentum.

\[
MOM^{12-1}=\log(P_{t-21}/P_{t-252}).
\]

It measures medium-horizon continuation while skipping roughly the most recent month.

### Q17. Why also include 6–1 momentum?

It checks a shorter continuation horizon without changing the registered direction. Averaging 12–1 and 6–1 reduces dependence on one arbitrary lookback. The equal averaging was fixed before the final run.

### Q18. How do you calculate low risk?

I estimate 63-day annualized total volatility and 126-day idiosyncratic volatility from a market regression. I z-score them cross-sectionally, multiply by negative one and average them, so a safer stock receives a higher low-risk score.

### Q19. How do you estimate beta and idiosyncratic volatility?

Using 126 aligned daily observations:

\[
r_i=\alpha_i+\beta_i r_{510300}+\epsilon_i.
\]

The slope is beta; the annualized standard deviation of residuals is idiosyncratic volatility. Beta is a risk control, not part of the alpha composite.

### Q20. What is operating quality in the public baseline?

Because the public adapter lacks full asset and cash-flow statements, the fallback combines ROE, gross margin, net margin and negative debt ratio. I treat it as a relative descriptor after cross-sectional transformation, not an absolute quality probability.

### Q21. What is fundamental momentum?

It averages transformed revenue/profit growth and the year-on-year change in operating quality. The economic idea is that improving fundamentals can matter beyond static quality.

### Q22. How do you handle outliers?

Within each month I use the median and 1.4826 times MAD as a robust scale, clip at plus or minus five robust scales, then standardize. This limits one distressed firm's extreme accounting ratio without deleting it.

### Q23. What exactly does neutralization do?

For every descriptor I regress its robust z-score on demeaned log ADV and broad-group dummies. I retain and re-standardize the residual. This removes linear liquidity and broad-group exposure inside that month.

### Q24. Why neutralize simultaneously?

Sequential group demeaning and then liquidity regression can reintroduce group exposure. A single design matrix estimates both controls together.

### Q25. Are neutralized scores automatically alpha?

No. Neutralization only changes exposure. Predictive validity must come from forward IC, return spreads and portfolio results.

---

## D. Validation and statistics

### Q26. Why not randomly split observations?

Random splitting mixes future and past regimes and overstates generalization. I use chronological design, validation and final holdout intervals.

### Q27. How many months are in each split?

There are 15 labeled design months, 12 validation months and 13 final-holdout months. This is a short sample, so conclusions remain preliminary.

### Q28. What is Rank IC?

It is the cross-sectional Spearman correlation between the signal and next-month excess return each month. It measures whether higher-score names tend to rank above lower-score names in subsequent return.

### Q29. Why can positive Rank IC coexist with a negative top-minus-bottom return?

Rank IC uses ordering only. The spread uses return magnitudes in the extreme groups. Many small correctly ordered observations can create a mildly positive Rank IC while a few large losses in the top group make the economic spread negative.

That is exactly what prevents me from using the positive 0.047 holdout Rank IC as the headline claim.

### Q30. Why Newey–West/HAC for mean IC?

Monthly ICs can be heteroskedastic and serially correlated. I estimate a constant-only mean-IC regression with three HAC lags. HAC improves inference but cannot fix model misspecification or the short sample.

### Q31. Why Benjamini–Hochberg FDR?

I evaluate four families plus a composite. Testing several hypotheses increases false positives. BH adjusts p-values within each research split. It cannot account for unrecorded specifications, which is why the signal registry matters.

### Q32. What happened across the splits?

Validation looked strong: composite mean Rank IC was about 0.172 and the top-minus-bottom return about 2.77% per month. In the final holdout, composite Rank IC fell to 0.047 and the spread reversed to -0.87% per month. Price momentum's Rank IC reversed from +0.163 in validation to -0.060 in the holdout.

This suggests regime dependence and shows why reporting validation alone would be misleading.

### Q33. Which signal looked best in the final holdout?

Low risk had mean Rank IC around 0.098 and a positive 1.41% monthly top-minus-bottom diagnostic. But there are only 13 holdout months, its inference is weak, and the low-risk-only model was not the registered primary portfolio. It is a new research lead, not a validated replacement.

### Q34. Why not immediately switch to low risk and claim success?

Because I saw that choice after opening the final holdout. Selecting the best family now would reuse the holdout as training data. A low-risk-only specification needs a new experiment ID and new future holdout.

---

## E. Portfolio construction and costs

### Q35. How do scores become weights?

I start from normalized delayed benchmark weights and multiply by \(\exp(0.35s_i)\). Then I project the raw tilt to a feasible long-only portfolio while preserving broad-group weights and applying single-name and active-weight bounds.

### Q36. Why an exponential tilt?

It is monotonic and always positive, so it translates higher scores into higher weights without directly treating a z-score as an expected return in percent. The 0.35 intensity is fixed in configuration.

### Q37. Is this mean-variance optimization?

No. The first stage minimizes distance to a score-tilted benchmark subject to transparent constraints. Covariance enters later to scale active risk. I describe it as a benchmark-relative projection, not a fully optimal expected-return portfolio.

### Q38. How is covariance estimated?

I use 126 daily returns and shrink the sample covariance 35% toward its diagonal, then annualize it. Shrinkage reduces unstable off-diagonal estimates in a short rolling window.

### Q39. What risk constraints are enforced?

Long-only weights, 12% maximum name weight, ±3% maximum active name weight, broad-group neutrality, 10% annualized ex-ante tracking-error cap and ±0.10 active market beta.

### Q40. How is turnover defined?

\[
TO=\frac12\sum_i|w_i^{new}-w_i^{drift}|.
\]

The cap is 25% per month. The trade ledger also reports gross traded weight, which is twice the one-way definition for a fully invested stock-to-stock rebalance.

### Q41. What happens when a constituent leaves?

Its old holding is explicitly sold to zero. The sale appears in turnover, stamp duty, spread, commission and impact. An earlier implementation bug could have lost old holdings during reindexing; the final code retains both sides of the transition and has a dedicated test.

### Q42. What capacity assumption do you use?

RMB100 million AUM and maximum trade size of 5% of ADV20. If any desired trade exceeds the limit, the discretionary trade vector is scaled down.

### Q43. What costs are included?

Three basis points of commission per traded side, five basis points of spread allowance, sell-side stamp duty of 10 bps before 2023-08-28 and 5 bps afterward, plus square-root impact:

\[
impact_i=0.25\,\sigma_i^{daily}\sqrt{\frac{|\Delta w_i|AUM}{ADV_i}}.
\]

### Q44. Are these realized costs?

No. They are explicit estimates. There are no archived executable quotes or fills. The sensitivity run at half and double costs shows how dependent the result is on the assumptions.

### Q45. How do you prevent costs from creating implicit leverage?

Costs are funded from residual cash. If cash is insufficient, risky holdings are scaled down and costs recomputed until risky weights, cash and costs reconcile to opening NAV.

---

## F. Results and decision

### Q46. What is the final result?

The registered composite fails. Final-holdout mean Rank IC is about 0.047, but the top-minus-bottom diagnostic is -0.87% per month. At baseline costs, the long-only portfolio's annualized active return is -0.41% and information ratio -0.43.

### Q47. Why is the strategy's absolute annualized return so high?

The battery-theme benchmark itself returned about 48.1% annualized during the short final-holdout interval. The strategy returned about 47.7%. The absolute return is a market/theme regime result; the relevant alpha question is the negative active return.

### Q48. What happens at double costs?

Final-holdout annualized active return declines to about -0.66%. This fails the registered high-cost gate.

### Q49. What happens with an additional signal lag?

Moving the feature cutoff from one to two trading days before execution leaves mean Rank IC mildly positive at about 0.042, but the spread remains negative at -1.15% per month and annualized active return remains negative at about -0.45%.

### Q50. Is failure caused by CATL alone?

No. CATL is the largest name by absolute active-return contribution, but its share is only about 7.1%. The maximum broad-group active weight is around 1.5 bps. Concentration is not the simple explanation for failure.

### Q51. Did operating quality predict returns?

Not robustly. Its holdout Rank IC is about 0.014 and top-minus-bottom return about -1.05% per month. This reinforces the original lesson: operational strength and future stock return are different questions.

### Q52. What do you do after a failed signal?

I archive the frozen experiment and diagnose the failure. I may propose new data—such as point-in-time valuation or earnings revisions—or a new hypothesis, but it receives a new experiment ID and new untouched future data. I do not change signs or weights until the old holdout becomes positive.

---

## G. Legacy CATL questions

### Q53. What was the old CATL return regression?

It regressed CATL weekly returns on CSI 300, battery-peer excess return and lithium return, with HAC inference. It is a contemporaneous conditional-attribution model.

### Q54. Was its 78-week held-out test a forecast?

No. Coefficients used only prior weeks, but the held-out week's already realized market, peer and lithium returns were inputs. It tested stability of the mapping. Calling it a week-ahead tradable forecast would be wrong.

### Q55. What did the old operating rank show?

CATL ranked first in a six-company operating diagnostic, but forward Rank IC observations were too few and unstable. The new broad-universe research confirms that static quality is not enough to establish alpha.

### Q56. Why retain the old modules?

They provide economic interpretation, stress scenarios and a documented path from company research to falsifiable systematic hypotheses. They are labeled as context rather than strategy.

---

## H. Authorship, limitations and next steps

### Q57. Did you write every line yourself?

Answer according to the actual contribution ledger. If AI assistance was used, say so. A safe truthful answer is:

> I used AI coding assistance in the public build. I do not claim unaided line-by-line authorship. I reviewed the architecture and results, ran the test suite, traced the formulas to code and can explain the design choices and limitations. The repository records the assistance boundary.

Do not memorize this answer unless it is true.

### Q58. What are the largest model risks?

The short 13-month holdout, ETF holdings as a proxy for official membership, later-downloaded vendor fundamentals, manual industry groups, missing valuation/revision data, estimated rather than realized trading costs, and unmodeled A-share limit queues and suspensions.

### Q59. What would you build next?

I would obtain official historical membership, immutable point-in-time valuation and consensus revisions, and archived tradability data. I would define a new signal experiment before seeing new returns, use a joint alpha-risk-cost optimizer, add regime and provider robustness, and paper trade before any production recommendation.

### Q60. What is the strongest honest takeaway?

> I can turn an economic question into an auditable QR pipeline, distinguish diagnostics from executable portfolios, and reject a model when holdout economics fail. I am not claiming live trading or a profitable production alpha.
