WITH amounts AS (
    SELECT DISTINCT customer_id, amount FROM transactions
)
SELECT count(*) AS complaints,
       count(c.origin_interaction_id) AS with_origin_interaction,
       count(c.affected_product_id) AS with_affected_product,
       count(*) FILTER (WHERE p.customer_id = c.customer_id) AS affected_product_owned_by_claimant,
       count(c.claimed_amount) AS with_claimed_amount,
       count(*) FILTER (WHERE a.amount IS NOT NULL) AS claimed_amount_matches_a_charge
FROM complaints c
LEFT JOIN products p ON p.product_id = c.affected_product_id
LEFT JOIN amounts a ON a.customer_id = c.customer_id AND a.amount = c.claimed_amount
