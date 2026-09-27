WITH per_claim AS (
    SELECT c.complaint_id,
           count(t.transaction_id) > 0 AS has_card_purchase_90d,
           count(t.transaction_id) FILTER (WHERE t.transaction_status IN ('Pending', 'Reversed', 'Declined')) > 0 AS has_explainable_status
    FROM complaints c
    LEFT JOIN transactions t
           ON t.customer_id = c.customer_id
          AND t.transaction_type = 'Purchase'
          AND t.transaction_date < c.creation_date
          AND t.transaction_date >= c.creation_date - INTERVAL 90 DAY
    WHERE c.subcategory = 'Cargo no reconocido'
    GROUP BY 1
)
SELECT count(*) AS claims,
       count(*) FILTER (WHERE has_card_purchase_90d) AS with_card_purchase_90d,
       round(100.0 * avg(has_card_purchase_90d::INT), 1) AS with_card_purchase_90d_pct,
       count(*) FILTER (WHERE has_explainable_status) AS with_explainable_status,
       round(100.0 * avg(has_explainable_status::INT), 1) AS with_explainable_status_pct
FROM per_claim
