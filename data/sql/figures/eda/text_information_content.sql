SELECT 'complaints.description' AS column_name, count(*) AS rows, count(DISTINCT description) AS distinct_values FROM complaints
UNION ALL SELECT 'complaints.resolution', count(*), count(DISTINCT resolution) FROM complaints
UNION ALL SELECT 'call_transcripts.full_text', count(*), count(DISTINCT full_text) FROM call_transcripts
UNION ALL SELECT 'call_transcripts.customer_text', count(*), count(DISTINCT customer_text) FROM call_transcripts
UNION ALL SELECT 'call_transcripts.detected_intents', count(*), count(DISTINCT detected_intents) FROM call_transcripts
UNION ALL SELECT 'call_transcripts.detected_language', count(*), count(DISTINCT detected_language) FROM call_transcripts
UNION ALL SELECT 'call_center_interactions.contact_reason', count(*), count(DISTINCT contact_reason) FROM call_center_interactions
UNION ALL SELECT 'transactions.merchant_name', count(*), count(DISTINCT merchant_name) FROM transactions
ORDER BY distinct_values
