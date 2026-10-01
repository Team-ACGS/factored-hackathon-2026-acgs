WITH labeled AS (
    SELECT CASE
               WHEN is_fraud AND fraud_score > 30 THEN 'flagged fraud'
               ELSE 'any other transaction'
           END AS population,
           transaction_status
    FROM transactions
)
SELECT population,
       count(*) AS transactions,
       count(*) FILTER (WHERE transaction_status = 'Approved') AS approved,
       round(100.0 * count(*) FILTER (WHERE transaction_status = 'Approved') / count(*), 1) AS approved_pct
FROM labeled
GROUP BY population
ORDER BY population DESC
