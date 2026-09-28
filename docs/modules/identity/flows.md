---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Identity: flows

Status: the customer flow and the role assumption run since task 0003; staff sign-in is designed, not built.

## Customer sign-up and sign-in (email and password)

Sign-up runs once per customer; sign-in runs every time a customer opens factoredai.sdfles.com without a valid session.
The emailed code below is a one-time sign-up verification, not a login step: it never appears again on later sign-ins and never appears as a step-up on a write.

```mermaid
stateDiagram-v2
  [*] --> Registered: sign up with email + password
  Registered --> Verified: correct verification code
  Registered --> Registered: wrong or expired code
  Verified --> SignedIn: sign in with email + password
  SignedIn --> [*]
```

```mermaid
sequenceDiagram
  participant C as Customer (apps/customer)
  participant CUP as Cognito pool: customers
  participant SES as Amazon SES
  C->>CUP: sign up, email + password
  CUP->>SES: send sign-up verification code
  SES-->>C: one-time code
  C->>CUP: submit code
  CUP-->>C: account confirmed, signed in (Amplify auto sign-in)
  Note over C,CUP: later, any sign-in
  C->>CUP: sign in, email + password
  CUP-->>C: JWT (pool = customers, no groups)
```

## A lambda assumes a role to read the customer's own data

Runs on every authenticated request that needs DynamoDB, after API Gateway's Cognito authorizer has already validated the JWT.
This replaces the older "Engine (FastAPI)" framing in `docs/product/02-technical-flows.md`: the caller here is a Python lambda behind API Gateway, and it performs the `AssumeRole` itself, not a separate IdP or engine process.

```mermaid
sequenceDiagram
  participant U as Customer session (JWT, sub = C1)
  participant L as Request lambda (core / chatbot / crud)
  participant STS as AWS STS
  participant DDB as DynamoDB
  U->>L: request, JWT already verified by the Cognito authorizer
  L->>STS: AssumeRole role-customer, session tag customer_id=C1
  STS-->>L: temporary credentials tagged C1
  L->>DDB: Query PK = C1
  DDB-->>L: C1's rows
  Note over L,DDB: a bug or an injected instruction asks for C2's rows
  L->>DDB: Query PK = C2 (same tagged credentials)
  DDB-->>L: AccessDeniedException (LeadingKeys policy)
```

The denial comes from the IAM `LeadingKeys` policy on `role-customer`, not from the lambda's own code.
An agent or officer request follows the same shape, assuming `role-agent` or `role-officer` instead, tagged from `cognito:groups` rather than `customer_id`.
A `role-analyst` exists for the same reason but is unused until the improvement console (analysts.factoredai.sdfles.com) is built.
