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

