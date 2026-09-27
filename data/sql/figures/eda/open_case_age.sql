WITH open_cases AS (
    SELECT subcategory, getvariable('data_clock') - creation_date::DATE AS age_days
    FROM complaints
    WHERE status IN ('Open', 'In Process', 'Escalated')
)
SELECT CASE WHEN grouping(subcategory) = 1 THEN 'all' ELSE subcategory END AS scope,
       count(*) AS open_cases,
       median(age_days) AS median_age_days,
       quantile_disc(age_days, 0.9) AS p90_age_days,
       count(*) FILTER (WHERE age_days > 365) AS older_than_one_year
FROM open_cases
GROUP BY GROUPING SETS ((), (subcategory))
HAVING grouping(subcategory) = 1 OR subcategory = 'Cargo no reconocido'
ORDER BY open_cases DESC
