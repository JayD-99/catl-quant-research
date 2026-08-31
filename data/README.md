# Data contract

## Public baseline

- A-share and index prices: downloaded through AkShare's Eastmoney adapters.
- Lithium carbonate futures: Sina's GFEX LC0 main-continuous series downloaded through AkShare. It is a vendor-constructed continuous series; the official GFEX historical-data page is retained as the exchange reference.
- CATL filings: official CATL investor-relations PDFs; the repository stores URLs, hashes, release dates, and extracted facts rather than committing large PDFs.

Run `make filings` to download the official PDFs to the ignored `data/external/filings/` directory and verify every file against `data/manual/filing_sources.csv`.

## Optional paid-source imports

Place exports in `data/external/`. These files are ignored by Git.

### `wind_market_daily.csv`

Required columns: `date, symbol, close, volume`. Optional: `open, high, low, amount, market_cap, pe_ttm, pb, ev_ebitda`.

### `smm_lithium_daily.csv`

Required columns: `date, series, price, unit`. Use a stable battery-grade lithium-carbonate series and do not splice methodologies without a documented break.

### `industry_monthly.csv`

Required columns: `month, metric, value, unit, source, release_date`. Candidate metrics include China NEV sales, global battery installations, CATL installation share, and ESS shipments.

Every external row must have a source and a release date. The build step will reject data released after the research cutoff.
