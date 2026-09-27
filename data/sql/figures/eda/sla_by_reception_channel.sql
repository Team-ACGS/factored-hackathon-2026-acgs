SELECT reception_channel,
       count(*) AS cases,
       round(100.0 * avg(sla_breached::INT), 1) AS sla_breached_pct
FROM complaints
GROUP BY 1
ORDER BY sla_breached_pct DESC
