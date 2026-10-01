WITH banded AS (
    SELECT CASE
               WHEN fraud_score IS NULL THEN 'no score'
               WHEN fraud_score > 30 THEN 'above 30'
               ELSE '30 or below'
           END AS score_band,
           is_fraud
    FROM transactions
)
SELECT score_band,
       count(*) FILTER (WHERE is_fraud) AS fraud_transactions,
       round(100.0 * count(*) FILTER (WHERE is_fraud) / sum(count(*) FILTER (WHERE is_fraud)) OVER (), 1)
           AS share_of_fraud_pct,
       count(*) AS transactions,
       round(100.0 * count(*) FILTER (WHERE is_fraud) / count(*), 2) AS fraud_in_band_pct
FROM banded
GROUP BY score_band
ORDER BY fraud_transactions DESC
