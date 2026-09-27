SELECT transaction_status,
       count(*) AS purchases,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM transactions
WHERE transaction_type = 'Purchase'
  AND transaction_date::DATE >= getvariable('data_clock') - 90
GROUP BY 1
ORDER BY purchases DESC
