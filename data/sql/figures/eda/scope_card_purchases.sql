WITH same_day AS (
    SELECT product_id, merchant_name, amount, transaction_date::DATE AS d, count(*) AS n
    FROM transactions
    WHERE transaction_type = 'Purchase'
    GROUP BY ALL
    HAVING count(*) > 1
)
SELECT (SELECT count(*) FROM transactions WHERE transaction_type = 'Purchase') AS card_purchases,
       count(*) AS duplicate_charge_groups,
       coalesce(sum(n), 0) AS rows_in_duplicate_groups
FROM same_day
