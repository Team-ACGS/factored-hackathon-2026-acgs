SELECT reason_category,
       count(*) AS contacts,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct,
       round(100.0 * avg(was_resolved::INT), 1) AS first_contact_resolution_pct,
       round(100.0 * avg(requires_followup::INT), 1) AS followup_pct,
       round(avg(duration_seconds)) AS avg_duration_s
FROM call_center_interactions
GROUP BY 1
ORDER BY first_contact_resolution_pct DESC
