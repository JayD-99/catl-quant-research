# A-Share Battery-Value-Chain Systematic Equity Research

**Research cutoff:** 2025-08-29  
**Status:** independent public-data systematic-research prototype.

## Executive conclusion

The composite is not validated as persistent alpha under the pre-registered failure rules.

Final-holdout composite mean Rank IC is 0.047, but the top-minus-bottom diagnostic is -0.87% per month and baseline-cost annualized active return is -0.41%.

This report distinguishes signal diagnostics from an implementable long-only simulation. The top-minus-bottom portfolios are diagnostics only; historical borrow data are unavailable.

## Point-in-time design

- Design period ends 2023-06-30.
- Validation period ends 2024-06-30.
- Final holdout ends 2025-08-29.
- Features use data no later than the signal date; execution is the following month-end trading date.
- Eligible panel: 1984 rows across 41 months and 73 securities.

## Signal IC results

| research_split   | signal                     |   months |   mean_rank_ic |   rank_ic_ir |   hac_t_stat |   hac_p_value |   bh_fdr_p_value |
|:-----------------|:---------------------------|---------:|---------------:|-------------:|-------------:|--------------:|-----------------:|
| all              | composite_score            |       40 |         0.0955 |       0.4190 |       2.8739 |        0.0041 |           0.0093 |
| all              | fundamental_momentum_score |       40 |         0.0616 |       0.3737 |       2.7711 |        0.0056 |           0.0093 |
| all              | low_risk_score             |       40 |         0.1026 |       0.4168 |       2.8314 |        0.0046 |           0.0093 |
| all              | operating_quality_score    |       40 |         0.0015 |       0.0091 |       0.0740 |        0.9410 |           0.9410 |
| all              | price_momentum_score       |       40 |         0.0512 |       0.2334 |       1.3950 |        0.1630 |           0.2038 |
| design           | composite_score            |       15 |         0.0765 |       0.3911 |       1.3075 |        0.1911 |           0.3184 |
| design           | fundamental_momentum_score |       15 |         0.0320 |       0.2803 |       1.3173 |        0.1877 |           0.3184 |
| design           | low_risk_score             |       15 |         0.0644 |       0.3406 |       0.9297 |        0.3525 |           0.4407 |
| design           | operating_quality_score    |       15 |        -0.0176 |      -0.0957 |      -0.7498 |        0.4534 |           0.4534 |
| design           | price_momentum_score       |       15 |         0.0587 |       0.3082 |       1.6543 |        0.0981 |           0.3184 |
| final_holdout    | composite_score            |       13 |         0.0467 |       0.1730 |       1.3835 |        0.1665 |           0.2081 |
| final_holdout    | fundamental_momentum_score |       13 |         0.0516 |       0.2522 |       1.4473 |        0.1478 |           0.2081 |
| final_holdout    | low_risk_score             |       13 |         0.0977 |       0.3013 |       1.6583 |        0.0973 |           0.2081 |
| final_holdout    | operating_quality_score    |       13 |         0.0142 |       0.1082 |       0.5810 |        0.5613 |           0.5613 |
| final_holdout    | price_momentum_score       |       13 |        -0.0603 |      -0.3001 |      -1.4319 |        0.1522 |           0.2081 |
| validation       | composite_score            |       12 |         0.1720 |       0.8014 |       3.7955 |        0.0001 |           0.0002 |
| validation       | fundamental_momentum_score |       12 |         0.1095 |       0.6285 |       2.6054 |        0.0092 |           0.0115 |
| validation       | low_risk_score             |       12 |         0.1556 |       0.6999 |       4.4115 |        0.0000 |           0.0000 |
| validation       | operating_quality_score    |       12 |         0.0115 |       0.0653 |       0.2362 |        0.8133 |           0.8133 |
| validation       | price_momentum_score       |       12 |         0.1625 |       0.7137 |       5.0554 |        0.0000 |           0.0000 |

## Quantile diagnostics

| research_split   | signal                     |   months |   mean_monthly_return |   annualized_arithmetic_return |   hac_t_stat |
|:-----------------|:---------------------------|---------:|----------------------:|-------------------------------:|-------------:|
| all              | composite_score            |       40 |                0.0058 |                         0.0702 |       0.7003 |
| all              | fundamental_momentum_score |       40 |                0.0084 |                         0.1010 |       1.1682 |
| all              | low_risk_score             |       40 |                0.0114 |                         0.1365 |       1.1902 |
| all              | operating_quality_score    |       40 |               -0.0024 |                        -0.0288 |      -0.3790 |
| all              | price_momentum_score       |       40 |                0.0113 |                         0.1355 |       1.1469 |
| design           | composite_score            |       15 |                0.0010 |                         0.0124 |       0.0765 |
| design           | fundamental_momentum_score |       15 |                0.0046 |                         0.0556 |       0.4266 |
| design           | low_risk_score             |       15 |                0.0006 |                         0.0069 |       0.0297 |
| design           | operating_quality_score    |       15 |               -0.0020 |                        -0.0240 |      -0.2706 |
| design           | price_momentum_score       |       15 |                0.0282 |                         0.3383 |       3.1530 |
| final_holdout    | composite_score            |       13 |               -0.0087 |                        -0.1047 |      -0.8335 |
| final_holdout    | fundamental_momentum_score |       13 |               -0.0057 |                        -0.0680 |      -0.6017 |
| final_holdout    | low_risk_score             |       13 |                0.0141 |                         0.1698 |       1.1906 |
| final_holdout    | operating_quality_score    |       13 |               -0.0105 |                        -0.1260 |      -1.0247 |
| final_holdout    | price_momentum_score       |       13 |               -0.0235 |                        -0.2815 |      -1.6310 |
| validation       | composite_score            |       12 |                0.0277 |                         0.3319 |       3.1734 |
| validation       | fundamental_momentum_score |       12 |                0.0284 |                         0.3407 |       3.6087 |
| validation       | low_risk_score             |       12 |                0.0219 |                         0.2625 |       2.0523 |
| validation       | operating_quality_score    |       12 |                0.0059 |                         0.0706 |       0.4946 |
| validation       | price_momentum_score       |       12 |                0.0278 |                         0.3337 |       3.5750 |

## Long-only portfolio and cost sensitivity

|   cost_multiplier | research_split   |   months |   annualized_net_return |   annualized_active_return |   information_ratio |   max_drawdown |   average_one_way_turnover |   annualized_cost_drag_arithmetic |
|------------------:|:-----------------|---------:|------------------------:|---------------------------:|--------------------:|---------------:|---------------------------:|----------------------------------:|
|            0.5000 | all              |       40 |                 -0.0122 |                     0.0061 |              0.4174 |        -0.5849 |                     0.0540 |                            0.0009 |
|            0.5000 | design           |       15 |                 -0.0282 |                    -0.0014 |             -0.2096 |        -0.3454 |                     0.0577 |                            0.0010 |
|            0.5000 | final_holdout    |       13 |                  0.4786 |                    -0.0028 |             -0.3606 |        -0.1249 |                     0.0537 |                            0.0009 |
|            0.5000 | validation       |       12 |                 -0.3487 |                     0.0157 |              2.4463 |        -0.2920 |                     0.0497 |                            0.0008 |
|            1.0000 | all              |       40 |                 -0.0131 |                     0.0052 |              0.3285 |        -0.5858 |                     0.0540 |                            0.0018 |
|            1.0000 | design           |       15 |                 -0.0292 |                    -0.0024 |             -0.3191 |        -0.3461 |                     0.0577 |                            0.0021 |
|            1.0000 | final_holdout    |       13 |                  0.4774 |                    -0.0041 |             -0.4342 |        -0.1250 |                     0.0537 |                            0.0017 |
|            1.0000 | validation       |       12 |                 -0.3492 |                     0.0152 |              2.3504 |        -0.2922 |                     0.0497 |                            0.0015 |
|            2.0000 | all              |       40 |                 -0.0148 |                     0.0034 |              0.1535 |        -0.5874 |                     0.0540 |                            0.0036 |
|            2.0000 | design           |       15 |                 -0.0312 |                    -0.0044 |             -0.5371 |        -0.3474 |                     0.0577 |                            0.0042 |
|            2.0000 | final_holdout    |       13 |                  0.4748 |                    -0.0066 |             -0.5776 |        -0.1252 |                     0.0537 |                            0.0035 |
|            2.0000 | validation       |       12 |                 -0.3502 |                     0.0142 |              2.1609 |        -0.2926 |                     0.0497 |                            0.0031 |

## Timing and concentration robustness

- The timing stress moves the signal cutoff to 2 trading days before execution without moving the return window.
- Largest final-holdout single-name share of absolute active contribution: 7.1%.
- Maximum absolute final-holdout broad-group active weight: 0.02%.
- The contribution audit is holdings-based and does not claim a full leave-one-name-out re-optimization.

## Pre-registered checks

- PASS: `final_holdout_mean_rank_ic_positive`
- FAIL / UNAVAILABLE: `final_holdout_top_minus_bottom_positive`
- FAIL / UNAVAILABLE: `baseline_final_holdout_active_return_positive`
- FAIL / UNAVAILABLE: `baseline_final_holdout_information_ratio_positive`
- FAIL / UNAVAILABLE: `double_cost_final_holdout_active_return_positive`
- PASS: `additional_lag_final_holdout_rank_ic_positive`
- FAIL / UNAVAILABLE: `additional_lag_final_holdout_top_minus_bottom_positive`
- FAIL / UNAVAILABLE: `additional_lag_final_holdout_active_return_positive`

## Limitations and disclosures

- This is an independent post-internship public-data reconstruction, not UBS work product.
- ETF holdings are a delayed public proxy for historical index membership, not an official immutable constituent database.
- Public vendor financial histories can contain later restatements despite notice-date filtering.
- Long-short portfolios are signal diagnostics only because historical borrow availability and fees are unavailable.
- The long-only backtest is a research simulation, not evidence of live trading or production deployment.
- The 2026 public reconstruction received material AI coding and documentation assistance; repository ownership is not a claim of unaided line-by-line authorship.

## Reproducibility

Input and processed-panel hashes are stored in `reports/systematic_summary.json`. The report contains no runtime timestamp, and all exported tables are deterministically sorted.
