SELECT CASE
           WHEN fraud_score IS NULL THEN 'no score'
           WHEN fraud_score > 30 THEN 'above 30'
           ELSE '30 or below'
       END AS score_band,
       count(*) AS fraud_transactions,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM transactions
WHERE is_fraud
GROUP BY 1
ORDER BY fraud_transactions DESC
