# Resume Wording and Claim Ledger

## Recommended resume structure

### Work Experience

**UBS Asset Management** — Shanghai, China  
*[Official HR title]* | Jun 2025 – Aug 2025

- Researched **[contemporaneously verified company/sector question]** using **[verified data and tool]** and prepared **[verified output]** for **[verified audience]**.
- Analyzed **[verified subject]** and communicated **[verified finding]** through **[verified memo, model or presentation]**.

The brackets cannot be filled with results created only by this 2026 repository.

### Selected Quantitative Research Projects

**A-Share Battery-Value-Chain Systematic Equity Research**  
*Independent Public-Data Reconstruction | Python, pandas, statsmodels, SciPy | 2026 | GitHub*

- Reconstructed a point-in-time monthly panel from delayed ETF-holding snapshots, 148K public daily observations and notice-dated fundamentals; retained a delisted constituent and documented provider fallbacks to reduce survivorship and look-ahead bias.
- Evaluated four pre-registered cross-sectional signal families across chronological design, validation and final-holdout periods using Rank IC, HAC/FDR inference and quantile diagnostics; rejected the equal-weight composite after its holdout top-minus-bottom return fell to -0.9% per month.
- Built a benchmark-relative long-only simulation with group, weight, beta, tracking-error, turnover and ADV constraints plus explicit commission, spread, dated stamp duty and square-root impact; final-holdout net active return was approximately -0.4% annualized, so the signal was not promoted as alpha.
- Added half/double-cost sensitivity, an additional signal-lag rerun, explicit forced-exit accounting, contribution concentration, deterministic reports and automated timing, calculation and NAV-reconciliation tests.

## Two-bullet space-constrained version

- Reconstructed a point-in-time A-share battery-value-chain panel from delayed ETF holdings, 148K public daily observations and notice-dated fundamentals; researched four pre-registered monthly signal families using chronological Rank IC, HAC/FDR and quantile tests.
- Built a risk-, turnover-, capacity- and cost-constrained long-only benchmark enhancement; rejected the composite after final-holdout spread and net active return turned negative (-0.9% monthly diagnostic spread; approximately -0.4% annualized active return).

## Why the negative result belongs on the resume

The result demonstrates research judgment. A positive-looking validation result existed, but the final holdout contradicted it. Writing `rejected the composite` shows that the candidate knows the difference between factor discovery, statistical evidence and implementable alpha.

If a target role strongly prefers positive production impact, use the two-bullet version and emphasize the research system rather than hiding or reversing the result. Do not claim profitability.

## Claim ledger template

| ID | Exact proposed claim | Layer | Completion date | Evidence | Personal contribution | Tool/AI assistance | Allowed wording | Status |
|---|---|---|---|---|---|---|---|---|
| P-01 | 148K public daily observations | 2026 public project | 2026-09-26 | source manifest and summary | Verify/reproduce | Public adapters and coding assistance | `148K public daily observations` | Verified |
| P-02 | Four pre-registered signal families | 2026 public project | 2026-09-25 | signal registry and config | Verify/reproduce | Coding assistance documented | `evaluated four pre-registered families` | Verified |
| P-03 | -0.4% annualized active return | 2026 public project | 2026-09-26 | portfolio summary | Verify/reproduce | Coding assistance documented | `approximately -0.4% final-holdout annualized active return` | Verified |
| W-01 | CATL assignment at UBS | 2025 internship | [date] | assignment email or mentor confirmation | [fill truthfully] | [fill truthfully] | only after evidence | Pending |
| W-02 | Delivered memo to PM | 2025 internship | [date] | dated memo plus delivery evidence | [fill truthfully] | [fill truthfully] | only after evidence | Pending |
| W-03 | Built current systematic pipeline at UBS | 2025 internship | n/a | contradicted by later repository timeline absent separate proof | n/a | n/a | prohibited | Excluded |

## Formatting notes

- Introduce CATL on first use as `Contemporary Amperex Technology Co., Limited (CATL)`, or avoid using the company name in the project title if space is tight.
- Write `ranked first among six battery manufacturers`, not `#1/6`.
- Distinguish `annualized active return` from absolute strategy return.
- Use `simulation`, `research portfolio` or `backtest`; do not use `deployed`, `managed` or `traded` without evidence.
- Use `independent public-data reconstruction` in the heading or first bullet so the timeline is unmistakable.
