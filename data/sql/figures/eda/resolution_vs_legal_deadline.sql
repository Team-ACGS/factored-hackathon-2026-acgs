WITH legal (country, deadline_business_days) AS (
    VALUES ('Argentina', 10), ('Colombia', 15), ('México', 30)
),
cases AS (
    SELECT cu.country,
           c.sla_breached,
           c.first_response_date IS NOT NULL AS has_first_response,
           c.resolution_date::DATE - c.creation_date::DATE AS calendar_days,
           CASE WHEN c.resolution_date IS NOT NULL THEN
               (SELECT count(*) FROM range(c.creation_date::DATE, c.resolution_date::DATE, INTERVAL 1 DAY) r(d)
                WHERE dayofweek(d) NOT IN (0, 6))
           END AS business_days
    FROM complaints c
    JOIN customers cu USING (customer_id)
)
SELECT country,
       l.deadline_business_days,
       count(*) AS cases,
       count(calendar_days) AS resolved,
       median(calendar_days) AS median_calendar_days,
       median(business_days) AS median_business_days,
       round(100.0 * avg((business_days > l.deadline_business_days)::INT), 1) AS resolved_over_legal_deadline_pct,
       round(100.0 * avg(sla_breached::INT), 1) AS sla_breached_flag_pct,
       round(100.0 * avg(has_first_response::INT), 1) AS first_response_recorded_pct
FROM cases
JOIN legal l USING (country)
GROUP BY ALL
ORDER BY 2
