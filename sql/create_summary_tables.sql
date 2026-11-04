-- Materialized summaries. Recompute after changing source data.
BEGIN;

CREATE TABLE monthly_summary AS
SELECT
    region,
    strftime(
        '%Y-%m',
        datetime(settlement_date, '-5 minutes')
    ) AS month,
    COUNT(*) AS intervals,
    ROUND(AVG(rrp), 2) AS mean_price,
    ROUND(MAX(rrp), 2) AS peak_price
FROM price_demand
GROUP BY region, month
ORDER BY month, region;

CREATE UNIQUE INDEX idx_monthly_summary_key ON monthly_summary (region, month);

CREATE TABLE hourly_risk_summary AS
SELECT
    region,
    strftime(
        '%H',
        datetime(settlement_date, '-5 minutes')
    ) AS hour,
    COUNT(*) AS intervals,
    ROUND(AVG(total_demand), 2) AS mean_demand_mw,
    ROUND(AVG(rrp), 2) AS mean_price,
    ROUND(MAX(rrp), 2) AS peak_price,
    SUM(CASE WHEN rrp > 300 THEN 1 ELSE 0 END)
        AS high_intervals,
    ROUND(
        100.0 * SUM(CASE WHEN rrp > 300 THEN 1 ELSE 0 END)
        / COUNT(*),
        2
    ) AS high_pct
FROM price_demand
GROUP BY region, hour
ORDER BY region, hour;

CREATE UNIQUE INDEX idx_hourly_risk_summary_key ON hourly_risk_summary (region, hour);

COMMIT;
