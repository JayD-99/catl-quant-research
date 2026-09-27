# Claim Boundary: 2025 Internship vs 2026 Independent Reconstruction

## Purpose

This document separates verifiable facts about the public repository from claims about the 2025 UBS internship. It applies to resumes, interviews, portfolio descriptions, README language, and conversations with mentors or recruiters.

The controlling rule is simple:

> A later public reconstruction can demonstrate later research ability. It cannot prove that the same work was completed during an earlier internship.

The analytical cutoff date, the code-development date, and the employment date are different facts.

---

## 1. Three evidence layers

### Layer A: 2025 UBS internship

Only work supported by contemporaneous evidence belongs in this layer. Examples of acceptable evidence include:

- the official HR title and employment dates;
- a dated assignment email or meeting note;
- files or code that existed during the internship;
- a dated presentation or memo actually delivered at the time;
- contemporaneous evidence of the data sources and tools used;
- confirmation from the mentor or team.

The public repository does not by itself establish any of these internship facts.

### Layer B: 2026 independent research extension

This layer covers research questions, models, validation, code, and conclusions developed after the internship. These may be strong evidence of initiative and current technical ability, but they must be dated and presented as independent work.

Safe lead-in:

> After the internship, I independently revisited the CATL topic and extended it into a systematic public-data research project.

### Layer C: 2026 public-data reconstruction

This layer covers the reproducible public implementation: public filings, public market-data adapters, configuration, source manifests, Python modules, tests, tables, figures, and generated reports.

The repository records a historical analytical cutoff of 2025-08-29. That cutoff limits the observations admitted by the model. It does not mean the repository or its results existed by that date.

Recommended disclosure:

> This is an independent post-internship public-data reconstruction and extension. It was not created for, endorsed by, or submitted to UBS, and it contains no UBS proprietary data, code, methodology, or investment views.

---

## 2. Claims supported by the public repository

Subject to rerun and review of the relevant generated artifacts, the repository can support claims such as:

- an independent public-data research repository was created in 2026;
- the research configuration uses 2025-08-29 as an analytical information cutoff;
- the public implementation records source metadata and separates manual inputs from downloaded and processed data;
- the project contains code for data construction, systematic features, evaluation, portfolio simulation, reporting, and selected tests;
- historical ETF holdings are used as a delayed public membership proxy in the systematic extension;
- the industry mapping is an analyst-curated broad grouping for research controls rather than an official GICS or CITIC classification;
- 920185 is retained in the membership audit trail but excluded from the baseline because BSE microstructure and public price coverage are not comparable with the Shanghai-Shenzhen baseline;
- 300116 is retained as a historical member despite delisting so that the universe does not remove a failed issuer ex post;
- limitations and negative results can be reported when they are generated and verified.
- the frozen run contains 147,955 daily market rows and 1,984 eligible security-month rows;
- the final-holdout composite Rank IC is approximately 0.047, while its top-minus-bottom return and cost-aware long-only active return are negative;
- the registered composite was rejected rather than presented as validated alpha.

These claims describe the independent public project. They do not describe UBS work unless separate contemporaneous evidence exists.

---

## 3. Claims the repository does not prove

Do not attribute any of the following to the 2025 internship without separate evidence:

- building the current point-in-time or systematic panel at UBS;
- writing the current Python package, tests, CLI, Makefile, or GitHub repository during the internship;
- using the current 75-symbol ETF-membership universe during the internship;
- defining the current signal families, research splits, portfolio constraints, or transaction-cost model during the internship;
- producing any current generated coefficient, IC, backtest, portfolio, risk, or stress-test result during the internship;
- delivering the current Markdown report or a recommendation memo to a UBS PM;
- using UBS proprietary data, infrastructure, models, or research templates in the public repository;
- deploying a production model, managing money, trading a live portfolio, or producing realized P&L;
- creating a validated alpha signal before the relevant evaluation is complete;
- personally writing every line of code if libraries, collaborators, or AI coding assistants generated material portions.

An exact result produced by the 2026 code cannot be moved into a 2025 work-experience bullet merely because its data end in 2025.

---

## 4. Claim ledger

Maintain one row for every resume or interview claim before using it.

| Field | Required content |
|---|---|
| Claim ID | Stable identifier |
| Exact wording | The complete proposed sentence |
| Layer | 2025 internship; 2026 independent extension; or public reconstruction |
| Completion date | When the work or result actually existed |
| Evidence | Email; dated file; commit; report; calculation; or mentor confirmation |
| Personal contribution | What was personally specified; written; reviewed; tested; and presented |
| Tool assistance | Data vendors; libraries; collaborators; and AI or coding assistants |
| Confidentiality | Public; confidential; or cannot disclose |
| Reproducibility | What another person can regenerate and under what conditions |
| Allowed wording | Strongest wording directly supported by the evidence |
| Prohibited wording | Stronger wording that would mislead |
| Status | Verified; pending verification; or excluded |

### Example entries

| Proposed claim | Layer | Evidence required | Safe status |
|---|---|---|---|
| The public repository was created after the internship | 2026 public reconstruction | Git metadata | Verifiable |
| The model uses a 2025-08-29 information cutoff | 2026 public reconstruction | Configuration and build controls | Verifiable; do not imply development by that date |
| I was assigned CATL during the UBS internship | 2025 internship | Contemporaneous assignment evidence or mentor confirmation | Pending unless separately verified |
| I built the current systematic pipeline at UBS | 2025 internship | Contemporaneous code and delivery evidence | Excluded unless separately verified |
| I delivered an investment memo to a PM | 2025 internship | The dated memo and evidence of delivery | Pending unless separately verified |
| I independently reconstructed and extended the CATL topic with public data in 2026 | 2026 extension and reconstruction | Repository metadata and personal contribution record | Verifiable within the recorded contribution boundary |

---

## 5. Resume-safe structure

### Work Experience

Use the official UBS title and include only Layer A claims marked `Verified`.

Template:

> **UBS Asset Management** — *[official HR title]*  
> - Researched **[verified company or sector question]** using **[verified data and tools]** to support **[verified deliverable or discussion]**.  
> - Prepared **[verified analysis]** and communicated **[verified finding]** to **[verified audience]**.

Do not fill the brackets with results generated only by the 2026 repository.

### Selected Projects

List the public work separately with its real date.

Template:

> **A-Share Battery-Value-Chain Systematic Equity Research — Independent Public-Data Reconstruction**  
> Python; pandas; statsmodels; public filings and market data | 2026 | GitHub  
> - Built a documented public-data research pipeline using delayed ETF-holding snapshots as a historical-universe proxy and explicit information-availability rules.  
> - Designed interpretable signal diagnostics and a benchmark-relative portfolio simulation with stated liquidity; risk; and cost assumptions.  
> - Reported validation and final-holdout results with their limitations; did not present the simulation as live trading or UBS work product.

Numerical results may now be added only from `reports/systematic_summary.json`. A failed validation check must be described as a failure, not omitted or rewritten as a successful alpha claim.

The 2026 reconstruction received material AI coding and documentation assistance. See `docs/ai_assistance.md`. Repository ownership must not be converted into an unaided line-by-line authorship claim.

---

## 6. Interview-safe timeline

### Short answer

> During the 2025 internship, my verified work was **[state only contemporaneously supported tasks]**. After the internship, I independently revisited the research topic. In 2026 I rebuilt and extended it with public data into a reproducible systematic-equity prototype. The repository is not UBS work product and contains no proprietary UBS data or views.

### If asked whether the GitHub project was completed at UBS

> No. The internship and the later public project are separate. The internship established **[verified problem or task]**. The public Python pipeline; systematic universe; validation; and portfolio simulation were later independent work.

### If asked who wrote the code

> I distinguish what I personally designed; wrote; reviewed; tested; and modified from what libraries; collaborators; or AI coding assistants generated. I do not claim line-by-line authorship beyond that evidence.

### If asked why the project is relevant to QR

> The project demonstrates research design; point-in-time discipline; source provenance; feature construction; benchmark comparison; validation; portfolio constraints; and model-risk disclosure. It remains a public research prototype rather than a production or live-trading system.

---

## 7. Current public-prototype limitations

### Universe and membership

- ETF holdings are a delayed public proxy for historical index membership rather than an official immutable constituent database.
- The union of disclosed holdings can contain issuers that later delist; removing them after the fact would create survivorship bias.
- BSE securities can have different price limits; liquidity; investor composition; and public-data coverage. The baseline excludes 920185 for comparability while retaining its membership record for audit.
- The broad industry groups are manual research controls. They are not an official industry taxonomy and should receive sensitivity checks.

### Data timing and revisions

- Public data were reconstructed after the analytical period.
- Notice-date filtering cannot prevent a vendor from later restating or backfilling historical fields.
- Public API behavior and historical values can change; raw vendor snapshots are not permanently versioned in the repository.
- Cross-provider adjustment conventions can differ.

### Signals and validation

- Feature definitions; clipping; family weights; and split dates are research choices rather than natural constants.
- A signal is not validated merely because it works in the design sample.
- Validation and final holdout must remain untouched by iterative tuning.
- Multiple signals and specifications create data-mining risk; statistical significance should account for repeated testing where applicable.
- Long-short portfolios are diagnostics only when historical borrow availability and fees are unavailable.

### Portfolio and costs

- Benchmark-relative optimization and transaction-cost estimates are simulations.
- ADV; volatility; spread; impact; turnover; and tracking-error assumptions may not match executable historical conditions.
- A simulated portfolio does not prove production deployment; capacity; operational readiness; or live P&L.

### Engineering and authorship

- Passing selected unit tests does not constitute complete data-quality or model validation.
- Public-data downloads need monitoring; retry; schema-change; and snapshot controls for production use.
- Personal authorship claims must reflect actual contribution and tool assistance.

---

## 8. Final rule

> Use the 2025 internship to describe what was genuinely done in 2025. Use the 2026 project to demonstrate how the candidate later deepened the question. Never use the later reconstruction to manufacture an earlier employment history.
