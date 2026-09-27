SELECT status,
       status IN ('Open', 'In Process', 'Escalated') AS is_open,
       count(*) AS cases,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM complaints
GROUP BY 1
ORDER BY cases DESC
