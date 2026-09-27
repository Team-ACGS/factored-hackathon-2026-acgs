WITH recent AS (
    SELECT i.interaction_id, i.was_resolved, i.duration_seconds,
           EXISTS (
               SELECT 1 FROM complaints c
               WHERE c.customer_id = i.customer_id
                 AND c.creation_date < i.interaction_date
                 AND (c.resolution_date IS NULL OR c.resolution_date > i.interaction_date)
           ) AS has_open_case
    FROM call_center_interactions i
    WHERE i.interaction_date::DATE >= getvariable('data_clock') - 90
)
SELECT has_open_case,
       count(*) AS contacts,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct,
       round(100.0 * avg(was_resolved::INT), 1) AS first_contact_resolution_pct,
       round(avg(duration_seconds)) AS avg_duration_s
FROM recent
GROUP BY 1
ORDER BY 1 DESC
