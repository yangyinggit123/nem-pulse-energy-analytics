# Expanded-history forecast evaluation

Data: November 2025–October 2026. Monthly-frozen models trained on eligible earlier months only; August, September and October evaluated separately.
Earlier experiments already examined these periods. This is retrospective development evaluation, not a new independent test. Parameters were fixed before this run and not selected using these results.
The models do not train on all twelve months and then score those same months. October models train through September. No final production model is fitted through October.
Both trees use identical training targets. Excluded from training: first 24 hours for lag-24 construction and two stale-report origins per region in March. Completed-hour actual availability and generated-time proxies remain limitations.

| Region | Month | Training hours | Baseline MAE | AEMO MAE | History tree MAE | Augmented tree MAE |
|---|---|---:|---:|---:|---:|---:|
| TAS1 | 2026-08 | 6526 | 11.12 | 10.33 | 12.81 | 11.62 |
| TAS1 | 2026-09 | 7270 | 11.75 | 12.65 | 12.86 | 13.31 |
| TAS1 | 2026-10 | 7990 | 11.77 | 15.00 | 14.66 | 13.46 |
| VIC1 | 2026-08 | 6526 | 12.12 | 10.06 | 11.04 | 9.57 |
| VIC1 | 2026-09 | 7270 | 11.36 | 9.82 | 9.88 | 8.17 |
| VIC1 | 2026-10 | 7990 | 13.88 | 13.51 | 13.69 | 11.16 |

All errors are AUD/MWh. Hourly averaging hides five-minute spikes. High-price hours use an illustrative actual hourly mean >300 AUD/MWh threshold; small counts do not establish reliable tail forecasting.
These are point forecasts. Earlier interval estimates are not automatically transferable to this refitted model. Procurement savings, hedging benefits and risk alerts have not been validated.
V0.5 will add simulated retailer customer loads and unhedged cost exposure. V1.0 will automate data quality checks and reporting.