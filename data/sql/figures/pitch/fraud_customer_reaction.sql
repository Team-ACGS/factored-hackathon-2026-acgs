WITH charges AS (
    SELECT customer_id,
           transaction_date::DATE AS d,
           CASE WHEN is_fraud THEN 'fraud' ELSE 'any other transaction' END AS population
    FROM transactions
),
contacts AS (
    SELECT customer_id, interaction_date::DATE AS d FROM call_center_interactions
),
claims AS (
    SELECT customer_id, creation_date::DATE AS d FROM complaints
),
next_contact AS (
    SELECT charges.*, contacts.d AS contact_d
    FROM charges ASOF LEFT JOIN contacts
        ON charges.customer_id = contacts.customer_id AND contacts.d >= charges.d
),
next_both AS (
    SELECT next_contact.*, claims.d AS claim_d
    FROM next_contact ASOF LEFT JOIN claims
        ON next_contact.customer_id = claims.customer_id AND claims.d >= next_contact.d
)
SELECT population,
       count(*) AS transactions,
       count(*) FILTER (WHERE contact_d <= d + 30) AS followed_by_contact_30d,
       round(100.0 * count(*) FILTER (WHERE contact_d <= d + 30) / count(*), 1) AS contact_pct,
       count(*) FILTER (WHERE claim_d <= d + 30) AS followed_by_claim_30d,
       round(100.0 * count(*) FILTER (WHERE claim_d <= d + 30) / count(*), 1) AS claim_pct
FROM next_both
GROUP BY population
ORDER BY population DESC
