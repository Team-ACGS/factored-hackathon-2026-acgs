# Legal deadlines for complaints and unrecognized charges

Status: cited from memory on 2026-09-26, NOT verified against the current legal texts.
Every figure below must be checked against the primary source before it appears in the product, a slide or the video.

| Country | Rule | Deadline to answer a complaint | Rules specific to unrecognized charges |
| --- | --- | --- | --- |
| Mexico | Ley de Protección y Defensa al Usuario de Servicios Financieros (Condusef), art. 50 Bis; Ley para la Transparencia y Ordenamiento de los Servicios Financieros, art. 23; Banxico and CNBV provisions | The bank's specialized unit must answer in writing within 30 business days | The customer may object to charges within 90 days; the bank resolves within 45 business days (domestic) or 180 calendar days (international); provisional credit within 2 business days for some electronic charges |
| Colombia | Ley 1328 de 2009 (financial consumer protection), Circular Básica Jurídica of the Superintendencia Financiera, Ley 1755 de 2015 | 15 business days, extendable with notice for complex cases | Payment reversal in e-commerce (Ley 1480 art. 51, Decreto 587 de 2016): the customer requests within 5 business days; the Defensor del Consumidor Financiero is the second instance |
| Argentina | Comunicación "A" 5460 of the BCRA and amendments (financial user protection); Ley 25.065 de Tarjetas de Crédito, arts. 26 to 30 | 10 business days, extendable to 20 when third parties are involved | The cardholder challenges the statement within 30 days of receipt; the issuer acknowledges within 7 days and resolves within 15 (extendable by 60 for international operations); the disputed amount is not payable while the challenge is open |

Card network rules run in parallel: Visa and Mastercard give the issuer up to 120 days from the transaction to start a chargeback.

## Why this matters for the system

- The dataset knows nothing about it: `sla_breached` is 20% in every country and `resolution_days` is 15.5 everywhere, which is uniform noise.
- Recomputing the breach with each country's legal deadline over `creation_date`, `country` and `first_response_date` is a data-quality finding no other team will have; the median resolution of 16 calendar days (about 11 business days) already breaches Argentina's 10.
- The bot must quote the right deadline or none: "we will answer within 10 business days" is true in Argentina and false in Mexico.
- Product rule: a deterministic regulatory clock takes country, product, channel and creation date and returns the due date in business days on that country's holiday calendar; any deadline the composer mentions must come from that function, and the grounding validator checks it like any other number.

## Day-1 task

- Verify every row of the table against the primary text and record the source URL and the date of verification here.
- Build `legal_deadlines.yaml` from the verified table.
- Run the query that recomputes `sla_breached` per country and compare with the dataset's flag.
