---
updated: 2026-09-28
source: 0006_customer_data_onboarding
---

# Identity: architecture and debt

Status: designed, not built.
These are design-time decisions, taken from `docs/tasks/_drafts/architecture_and_layout.md` (decided 2026-09-27) before any identity code exists, not decisions extracted from a diff.

## Decisions

## 2026-09-27: Two Cognito user pools instead of one

- Decision: separate `customers` (self sign-up, email + password, no groups) and `staff` (invited, email + password, groups `agents`/`officers`/`analysts`) pools rather than one pool with a role attribute.
- Alternatives rejected: a single pool with a custom role attribute driving both flows.
- Reason: the two populations have different trust levels and different sign-up flows; mixing a self-serve flow with an invite-only flow in one pool would put both behind the same set of defaults.
- Debt created: none.
- Revisit when: a third population appears that does not cleanly fit either pool.
- Source: setup

## 2026-09-27: Customer sign-in moves from a mock IdP to real Cognito, email and password

- Decision: customer sign-up and sign-in use Cognito's standard email + password flow; the emailed code (through SES on `notifications.factoredai.sdfles.com`) is only Cognito's one-time sign-up verification, not a passwordless login and not a step-up inside the chat.
- Alternatives rejected: `docs/product/03-architecture.md`'s earlier "Mock IdP with OTP issuing session claims"; a first pass of this module also considered Cognito's native passwordless `EMAIL_OTP` sign-in, which Sebastian corrected in round 2 (2026-09-27): login is password-based, OTP is sign-up verification only.
- Reason: real Cognito replaces the demo-only mock IdP; password-based login was chosen over passwordless sign-in, reason not stated beyond the correction itself.
- Debt created: `docs/product/03-architecture.md`'s security controls table still describes the mock IdP and STS tags coming from it; that row is superseded and should not be read as current.
- Revisit when: `docs/product/03-architecture.md` is edited or retired.
- Source: setup

## 2026-09-27: No Cognito Identity Pool, the lambda assumes the role itself

- Decision: the Cognito group to IAM role mapping field stays empty; each request-handling lambda reads `pool` and `cognito:groups` from the verified JWT and calls STS `AssumeRole` with a `customer_id` session tag to get `role-customer`, `role-agent`, `role-officer` or `role-analyst` credentials, relying on an IAM `LeadingKeys` policy for the per-customer boundary.
- Alternatives rejected: a Cognito Identity Pool mapping groups to roles automatically.
- Reason: keeps the isolation proof in an application-controlled STS call plus an IAM policy, which produces the `AccessDeniedException` log evidence the product wants, and avoids a second identity configuration surface for a single-environment hackathon project.
- Debt created: the lambda itself becomes trusted to pick the right role from the token; a bug in that mapping is not caught by Identity Pool's own role-mapping rules.
- Revisit when: a second environment or a second region makes the manual mapping harder to audit by hand.
- Source: setup

## 2026-09-27: Wrong-pool sign-in is rejected twice

- Decision: a `pre_token_generation` trigger rejects a group signing in through the wrong app client (an officer on the support app client, for example), and the lambda re-validates pool and group again server-side rather than trusting the trigger alone.
- Alternatives rejected: relying on the trigger only.
- Reason: defense in depth; a trigger misconfiguration or a stale token should not be the only thing standing between an officer and the agent console.
- Debt created: the same check now lives in two places and both need to change together if the group model changes.
- Revisit when: a fifth staff group is added.
- Source: setup

## 2026-09-27: No MFA for staff, no OTP step-up for customer writes

- Decision: staff sign-in carries no MFA; a customer write (blocking a card, for example) relies on the signed-in email + password session alone, with no second OTP requested at write time.
- Alternatives rejected: an OTP step-up on writes, which `docs/kickoff-compliance.md` and the write flow in `docs/product/02-technical-flows.md` both described; Sebastian settled this in round 2 (2026-09-27): no passwordless login, no OTP step-up inside the chat.
- Reason: not stated beyond the correction itself; recorded as a settled decision, not a considered security position argued for elsewhere.
- Debt created: neither population has a second factor beyond its single credential once signed in.
- Revisit when: this design is carried past the hackathon toward a production bank system.
- Source: setup

## 2026-09-27: Four IAM roles, one per group plus the customer

- Decision: `role-customer`, `role-agent`, `role-officer`, `role-analyst`; the fourth exists for the `analysts` group and its improvement console, reserved but not built, so it stays unused until that web exists.
- Alternatives rejected: three roles, `analyst` and `officer` collapsed into one, which was this module's first pass before the round 2 naming correction; officers (bank staff reviewing complaints, backoffice.factoredai.sdfles.com) and analysts (the future improvement console) are distinct groups.
- Reason: naming now matches the four actual audiences instead of conflating the backoffice queue reviewer with the not-yet-built improvement console.
- Debt created: `role-analyst` and the `analysts` group sit unused in Terraform until their web is built.
- Revisit when: the improvement console (analysts.factoredai.sdfles.com) is built.
- Source: setup

## 2026-09-27: Identity infra follows the auvral Terraform/Actions split

- Decision: Terraform owns the Cognito pools, app clients, groups and the four IAM roles; GitHub Actions owns the two trigger lambdas' code, uploaded by commit SHA, calling `update-function-code` only when `CodeSha256` changes. The DynamoDB tables themselves are defined in a separate `infra/` leaf module, not this one; identity only owns the roles that govern them, and a still-undecided process seeds their data.
- Alternatives rejected: a bespoke deploy pattern for identity alone; identity owning the tables it grants access to.
- Reason: reuses a pattern the team already trusts (auvral's `infra` module), rather than inventing a new one for a 10-day hackathon; keeping table ownership separate from role ownership matches how the rest of the project splits infra by resource type.
- Debt created: none beyond what the general infra module already carries.
- Revisit when: the auvral pattern itself changes, or the seed process gets an owner.
- Source: setup

## 2026-09-27: one AssumeRole per request or stream record, no credentials cache

- Decision: `core.access` calls STS for every API request and every chatbot record, with 15 minute credentials, and builds a fresh boto3 session from them.
- Alternatives rejected: caching credentials per customer in the warm container.
- Reason: no cache means no bound, eviction or expiry logic, and no way for one customer's credentials to serve another's request.
- Debt created: every request pays an STS call and a boto3 session, tens of milliseconds.
- Revisit when: API latency or STS throttling shows in the metrics.
- Source: 0003_walking_skeleton

## 2026-09-27: a staff token maps to a role only with exactly one group

- Decision: `core.access.session_for` assumes `role-agent`, `role-officer` or `role-analyst` from `cognito:groups` and denies a staff token with no group or several.
- Alternatives rejected: a precedence order among groups.
- Reason: a person in two groups is a provisioning mistake; guessing which role they meant would hand out the wider one silently.
- Debt created: none.
- Revisit when: someone legitimately needs two staff roles.
- Source: 0003_walking_skeleton

## 2026-09-27: post_confirmation creates the customer through role-customer

- Decision: the `post_confirmation` trigger assumes `role-customer` tagged with the `sub` of Cognito's event and creates the `customers` row only if absent; its own role may only assume `role-customer`, and `role-customer` gains `PutItem` on `customers` under the same `LeadingKeys` condition (`UpdateItem` followed in task 0005 for the setup profile). The event joins the JWT and the stream record as a trusted source of the session tag.
- Alternatives rejected: `PutItem` on `customers` in the trigger's own role (task 0004), which broke "no lambda touches a table with its own role".
- Reason: one rule for every table access, and IAM still refuses a row whose key is not the tagged `sub`; the event comes from Cognito, never from a client.
- Debt created: `terraform apply` of the role changes must land before the lambda deploy that uses them, or sign-up confirmation fails on `AssumeRole`.
- Revisit when: a second writer of `customers` appears, such as the seed.
- Source: 0003_walking_skeleton

## 2026-09-28: Cognito emails in the user's language, no trilingual fallback

- Decision: a `custom_message` trigger on both pools writes each Cognito email in the user's `locale` (`en`, `es`, `pt-BR`, English by default); the trilingual templates of task 0004 are removed, and the bootstrap fails instead of falling back.
- Alternatives rejected: one trilingual template per pool (task 0004); keeping it as the fallback.
- Reason: the customer picks the language on the login and sign-up screens; a silent fallback would hide a broken handler.
- Debt created: until task 0006 deploys the handler, no Cognito email is sent: sign-up, password reset and staff invitations fail.
- Resolved by: 0006_customer_data_onboarding, 2026-09-28
- Revisit when: never, unless a language is added.
- Source: task 0005

## 2026-09-28: custom_message has one text per kind of email and never leaves one empty

- Decision: the handler maps every trigger source to one of three texts per language (code for sign-up, resend, attribute verification and authentication; password reset; staff invitation with `{username}` and the temporary password); `locale` matches only exactly, and an unknown trigger source gets the code text, which always carries the code.
- Alternatives rejected: one verification sentence for every email, as the task 0004 template had; leaving an unknown source to Cognito's default text.
- Reason: a reset or an invitation should say what it is, and with no fallback template an email must never go out empty or without its code.
- Debt created: none.
- Revisit when: a fourth language, or SMS messages, appear.
- Source: 0006_customer_data_onboarding
