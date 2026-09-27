SELECT getvariable('data_clock') - transaction_date::DATE > 7 AS older_than_7_days,
       count(*) AS pending_transactions,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM transactions
WHERE transaction_status = 'Pending'
GROUP BY 1
ORDER BY 1 DESC
