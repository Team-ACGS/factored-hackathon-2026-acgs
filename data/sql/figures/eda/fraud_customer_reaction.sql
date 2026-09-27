WITH fraud AS (
    SELECT transaction_id, customer_id, transaction_date::DATE AS d
    FROM transactions
    WHERE is_fraud
)
SELECT count(*) AS fraud_transactions,
       count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM call_center_interactions i
           WHERE i.customer_id = f.customer_id AND i.interaction_date::DATE BETWEEN f.d AND f.d + 30
       )) AS followed_by_contact_30d,
       count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM complaints c
           WHERE c.customer_id = f.customer_id AND c.creation_date::DATE BETWEEN f.d AND f.d + 30
       )) AS followed_by_claim_30d
FROM fraud f
