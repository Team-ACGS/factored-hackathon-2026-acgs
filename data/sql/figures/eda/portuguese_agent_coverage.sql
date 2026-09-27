SELECT 'all agents' AS scope,
       count(*) AS agents,
       count(*) FILTER (WHERE languages LIKE '%portugués%') AS portuguese_speaking
FROM service_agents
UNION ALL
SELECT 'active fraud agents, ' || coalesce(lower(work_shift), 'all shifts'),
       count(*),
       count(*) FILTER (WHERE languages LIKE '%portugués%')
FROM service_agents
WHERE specialty = 'Fraudes' AND agent_status = 'Active'
GROUP BY ROLLUP (work_shift)
ORDER BY agents DESC
