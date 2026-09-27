# Role Positioning: Systematic Equity QR, Not QT

## Bottom line

The rebuilt public project belongs closest to:

> **Systematic Equity Quantitative Research — medium-frequency, cross-sectional A-share signal research and benchmark-relative portfolio simulation.**

It does not belong to Quantitative Trading, market making or execution research. The distinction comes from the decision process and data—not from whether the project contains formulas or Python.

The 2026 project and the 2025 UBS internship are separate evidence layers. `Systematic Equity Quantitative Research` describes the public project's methodology. It must not be used to replace the internship's official HR title or imply that later work was delivered at UBS.

---

## 1. Why the old project looked like Equity Research with quant packaging

The original research object was one company: Contemporary Amperex Technology Co., Limited, or CATL. Its questions were:

- did volume or average selling price drive reported revenue;
- how did CATL co-move with the market, battery peers and lithium;
- where did CATL rank on a six-company operating score;
- how could commodity and pass-through assumptions affect profit;
- did the evidence support a stock view?

Those are fundamental-equity-research questions. A volume/ASP bridge, OLS, Newey–West errors, Rank IC or Monte Carlo engine can make the evidence more disciplined, but they do not change the research object. A technical interviewer correctly recognizes this as quant-assisted single-name research.

Several old labels also overstated what the methods could prove:

- the 78-week held-out attribution uses the held-out week's realized factor returns, so it is not an ex-ante weekly forecast;
- the six-company operating score has too few cross-sections to establish a factor;
- an AR(1) commodity scenario is not a reliable lithium forecast;
- a scenario mapping from lithium to total material cost is not an estimated CATL cost function;
- a strong company is not automatically an underpriced stock.

These modules remain useful as economic context. They are no longer presented as the alpha engine.

---

## 2. Why the new project is genuine Systematic Equity QR

A project becomes systematic equity QR when the unit of research is a repeatable stock-selection and portfolio decision across many securities and dates.

The rebuilt workflow now contains the full research chain:

| QR responsibility | Implementation in this repository |
|---|---|
| Define a decision | Rank next-month relative returns and test a long-only benchmark enhancement |
| Reconstruct an investable universe | Delayed Q2/Q4 ETF-holding snapshots; former constituents retained |
| Build point-in-time data | Signal dates, notice dates, membership availability dates, cutoff checks |
| Form economic hypotheses | Momentum, operating quality, fundamental momentum and low risk |
| Engineer cross-sectional features | MAD clipping, standardization, ADV and broad-group neutralization |
| Prevent research leakage | Fixed directions, equal family weights, chronological splits and registered failure rules |
| Test alpha | Monthly Pearson/Spearman IC, HAC mean tests, FDR and quantile spreads |
| Construct a portfolio | Benchmark-relative score tilt, long-only constraints and group neutrality |
| Control risk | Single-name/active caps, covariance shrinkage, tracking-error and beta scaling |
| Model implementability | Turnover, ADV capacity, forced exits, commission, spread, stamp duty and impact |
| Run robustness checks | Half/double costs, additional signal lag and contribution concentration |
| Decide whether to deploy | Reject the current composite after final-holdout failure |

The output is therefore not a CATL recommendation. It is evidence about whether a repeatable signal survives implementation.

---

## 3. Why this is not Quantitative Trading

Quantitative Trading normally requires one or more of the following:

- intraday quote, trade or order-book events;
- forecasts at execution-relevant horizons;
- order generation and order-state handling;
- venue, queue, fill and slippage models;
- market-making inventory and pricing controls;
- live limits, kill switches and monitoring;
- paper or live realized P&L;
- post-trade implementation-shortfall analysis.

This repository has daily data, monthly rebalancing and estimated transaction costs. Cost modeling makes QR results more realistic, but it does not make the author a QT. No orders are routed, no spreads are quoted and no intraday inventory is managed.

Safe interview answer:

> The project is closer to systematic equity QR because my main work is hypothesis design, point-in-time data construction, cross-sectional signal validation and portfolio-level falsification. I model implementation costs, but I do not have order-book, execution or live-trading evidence, so I would not call it QT.

---

## 4. The exact research mandate

At monthly frequency, the project asks:

> Among companies in a delayed public battery-theme membership proxy, can signals observable before month-end execution rank next-month relative returns, and do those rankings survive a constrained long-only portfolio after costs?

The target is

\[
y_{i,t+1}=R_{i,t\rightarrow t+1}-R_{b,t\rightarrow t+1}.
\]

This target makes four things explicit:

1. the unit is security \(i\), not CATL alone;
2. the horizon is one rebalance month;
3. the decision is relative to a battery-universe benchmark;
4. a signal must be observable before \(R_{i,t\rightarrow t+1}\) begins.

CATL is one historical constituent and an economic anchor, not an ex-post winner selected by the model.

---

## 5. Research result and the professional decision

The final holdout contains 13 labeled months. The registered composite produces:

- mean Rank IC of 0.047, HAC p-value 0.167 and FDR p-value 0.208;
- a top-minus-bottom diagnostic of -0.87% per month;
- long-only annualized active return of -0.41% after baseline costs;
- information ratio of -0.43;
- annualized active return of -0.66% at double costs;
- annualized active return of -0.45% after moving the signal date back one additional trading day.

The positive mean Rank IC does not overrule the negative return spread and portfolio. Rank correlation records order, not economic magnitude. A few large returns can make the spread negative even when the average ordering correlation is mildly positive. The signal is also statistically weak in the short final holdout.

The professional QR decision is:

> Do not promote the composite to a production candidate. Archive the experiment, diagnose the breakdown and require new data plus a new untouched holdout before testing a revised specification.

This is a successful research process with a failed alpha hypothesis. Those are not contradictory statements.

---

## 6. What can be said on a resume

### Recommended placement

Place this under **Selected Projects**, dated 2026:

> **A-Share Battery-Value-Chain Systematic Equity Research — Independent Public-Data Reconstruction**  
> Python, pandas, statsmodels, SciPy | 2026 | GitHub

Safe bullets after verifying the generated artifacts:

- Reconstructed a point-in-time monthly panel from delayed ETF-holding snapshots, 148K public daily observations and notice-dated fundamentals; retained a delisted constituent and documented provider fallbacks to reduce survivorship and look-ahead bias.
- Researched four pre-registered cross-sectional signal families across chronological design, validation and final-holdout periods using Rank IC, HAC/FDR inference and quantile diagnostics; rejected the equal-weight composite after its final-holdout top-minus-bottom spread turned negative.
- Built a benchmark-relative long-only simulation with group, weight, beta, tracking-error, turnover and ADV constraints plus commission, spread, dated stamp duty and square-root impact; final-holdout net active return was approximately -0.4% annualized, so the signal was not promoted as alpha.
- Added cost sensitivity, an additional signal-lag rerun, forced-constituent-exit accounting, contribution concentration, deterministic reports and 26 automated tests.

The last test count must be updated if the suite changes.

### UBS Work Experience

The UBS entry may contain only contemporaneously verified 2025 work. Use the official title. Do not move the 2026 universe, code, tests or backtest results into that entry unless dated evidence shows they existed and were delivered during the internship.

Safe structure:

> **UBS Asset Management** — *[official HR title]*  
> - Researched **[verified 2025 question]** using **[verified 2025 data/tool]** and prepared **[verified 2025 output]** for **[verified audience]**.

See [claim_boundary.md](claim_boundary.md) for the evidence ledger.

---

## 7. Interview framing

### 30-second answer

> The original CATL topic was closer to quantitative fundamental research than pure quant. I later rebuilt it independently as a systematic equity QR project. I reconstructed a delayed historical battery-stock universe, created point-in-time monthly signals, tested IC and quantile returns across design, validation and final holdout, and translated the composite into a risk- and cost-constrained long-only portfolio. The important result was negative: validation strength did not survive the final holdout, where the spread and net active return were negative. I therefore rejected the signal instead of relabeling it as alpha.

### If asked “What makes this QR?”

> The object is a repeated cross-sectional forecast and portfolio decision, not one company's story. Each feature has an information date, every month has a then-available universe, the target is next-month relative return, and the final decision depends on holdout IC, net active return, risk and costs.

### If asked “Why did your mentor initially say it was ER?”

> That criticism was correct for the earlier version. The earlier work used quant tools to answer CATL operating and stock-attribution questions. In the extension I changed the research object itself: a changing multi-stock universe, ex-ante signals, chronological validation and portfolio implementation. I keep the two layers separate.

### If asked “Did it work?”

> The validation period looked promising, but the final holdout did not. Composite Rank IC remained mildly positive, yet the top-minus-bottom return and the cost-aware long-only active return were negative. The signal failed the registered promotion rules. My conclusion is about the research process and why the hypothesis was rejected, not a claim of profitable alpha.

---

## 8. What would be needed for a production-grade next version

- official historical index membership and corporate-action masters;
- immutable point-in-time fundamentals, consensus revisions and valuation data;
- longer history and more independent regimes;
- archived executable spreads, limit queues, suspensions and borrow data;
- a formal optimizer with transaction-cost-aware objectives rather than sequential scaling;
- provider reconciliation and daily data-quality monitoring;
- model registry, experiment lineage and retirement criteria;
- paper trading before any production recommendation;
- a genuinely new holdout after every material signal redesign.

Until those exist, `research prototype` is the strongest defensible label.
