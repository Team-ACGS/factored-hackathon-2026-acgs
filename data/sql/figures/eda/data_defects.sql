SELECT 'USD transactions with null amount_usd' AS defect, count(*) AS rows FROM transactions WHERE amount_usd IS NULL AND currency = 'USD'
UNION ALL SELECT 'non-USD transactions with null amount_usd', count(*) FROM transactions WHERE amount_usd IS NULL AND currency <> 'USD'
UNION ALL SELECT 'transactions spelled Mexico without accent', count(*) FROM transactions WHERE transaction_country = 'Mexico'
UNION ALL SELECT 'transactions in MXN', count(*) FROM transactions WHERE currency = 'MXN'
UNION ALL SELECT 'transactions before customer registration', count(*) FROM transactions t JOIN customers c USING (customer_id) WHERE t.transaction_date < c.registration_date
UNION ALL SELECT 'card purchases on the ATM channel', count(*) FROM transactions WHERE transaction_type = 'Purchase' AND channel = 'ATM'
UNION ALL SELECT 'customers updated after the data clock', count(*) FROM customers WHERE last_updated::DATE > getvariable('data_clock')
UNION ALL SELECT 'Mexican customers with document type DNI', count(*) FROM customers WHERE country = 'México' AND document_type = 'DNI'
ORDER BY rows DESC
