# Interview defense notes

## The 60-second project answer

My mentor assigned CATL as the anchor company. I rebuilt the question into four linked pieces: a volume/ASP earnings bridge from official filings, a weekly return-attribution model against CSI 300, battery peers and lithium carbonate, a point-in-time peer operating score, and a commodity stress test with explicit pass-through assumptions. The main operating finding was that 2024 weakness was pricing-led rather than volume-led; EV and ESS volumes rose, but ASP declines more than offset that growth. By 2025H1, EV revenue was recovering, although its segment margin was slightly lower year on year. CATL ranked first in the six-company 2024 operating comparison, but the score did not predict subsequent returns robustly. During the internship window the stock's gain was largely associated with market, peer, and commodity exposures, while the model residual was negative. So my conclusion was positive on operating quality but valuation-dependent on the stock, not an unconditional Buy.

## What I personally did

- defined the research cutoff and point-in-time controls;
- assembled and cleaned daily market, peer fundamental, and lithium futures data;
- extracted filing-based operating and sensitivity inputs with dated source records;
- implemented the revenue bridge, HAC return regressions, rolling betas, out-of-sample validation, peer-score diagnostics, and Monte Carlo commodity scenarios;
- reconciled the quantitative outputs into an investment view and documented limitations.

## Numbers worth remembering

- 2024 EV battery volume: 381 GWh; revenue: RMB253.0bn; reported ASP: RMB0.66/Wh.
- 2024 ESS battery volume: 93 GWh; revenue: RMB57.3bn; reported ASP: RMB0.62/Wh.
- Symmetric 2024 bridge: EV volume +RMB46.5bn, EV ASP -RMB80.7bn; ESS volume +RMB17.9bn, ESS ASP -RMB20.3bn.
- 2024 direct materials: RMB202.7bn, 74.1% of cost of sales.
- Full weekly model adjusted R-squared: 61.8%; incremental out-of-sample R-squared versus market-only: 20.0%.
- 2024 operating score: CATL ranked 1/6, but the three subsequent Rank IC tests were unstable and mostly negative.
- 2025H1 revenue: RMB178.9bn, +7.27% year on year; EV revenue +16.8% with gross margin down 1.07ppt; ESS revenue -1.47% with gross margin up 1.11ppt.

## Questions and defensible answers

### Why use weekly returns?

The lithium series starts only in July 2023 and daily battery names contain substantial idiosyncratic noise. Weekly sampling reduces microstructure noise while preserving enough observations for rolling and out-of-sample analysis.

### Why HAC standard errors?

Weekly residuals can be heteroskedastic and serially correlated. Newey-West inference addresses both without changing the OLS coefficient interpretation.

### Is the lithium coefficient causal?

No. It is a conditional equity-return exposure. A positive coefficient can reflect the battery-sector state or demand expectations, while a positive lithium cost shock can still hurt earnings when it is not passed through. The return model and earnings scenario answer different questions.

### Why no valuation factor or target price?

A clean, dated, point-in-time public history was not available for the baseline. Using today's multiples would introduce look-ahead bias. The correct conclusion is operating-quality positive and valuation-dependent; Wind or Bloomberg exports are the next upgrade.

### Did the peer score work?

Not as a robust return signal. CATL ranked highly on operations, but the small-sample forward Rank IC was unstable and often negative. I retained that negative result because the score is a diagnostic, not a backtest story to optimize after the fact.

### What would you improve with institutional data?

I would add point-in-time consensus revisions and valuation multiples, SMM or Fastmarkets spot lithium, dated monthly battery installations and market share, and corporate-action-verified total-return series. I would then run walk-forward model selection and transaction-cost-aware portfolio tests only if the mandate became strategy research.

## Claims not to make

- Do not say CATL was discovered by a screen; it was assigned.
- Do not call the top-five customer calculation full-company HHI.
- Do not say the lithium return beta proves commodity causality.
- Do not claim the operating score is a profitable factor.
- Do not quote any old resume metric that is not generated in this repository.
