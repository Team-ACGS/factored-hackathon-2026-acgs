---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Identity: product

Status: customer sign-up and sign-in built (task 0003); staff sign-in designed, not built.

## Purpose

A customer, an agent or an officer has to prove who they are before Clara shows them anything, and once they are in, each of them must only ever see their own data or the data their role is meant to see.
Identity is that gate: it decides who can sign in, through which door, and what a session is allowed to touch afterward.
It is also the proof the hackathon asks for that access control lives outside the model's reach, in AWS itself.

## User flows

### Customer sign-up and sign-in

1. A customer opens factoredai.sdfles.com and signs up with an email and a password.
2. Clara emails a verification code to that address to confirm it, once, at sign-up.
3. The customer enters the code, confirming the account, and lands in the chat already signed in.
4. From then on the customer signs in with email and password, like any password account; the emailed code never reappears at sign-in.

Errors and empty states: a wrong or expired verification code at sign-up can be resent; a wrong password at sign-in is rejected without saying which part was wrong.

### Staff sign-in

1. An agent or an officer is created by the team ahead of time, no self sign-up.
2. They sign in with email and password on their own subdomain: support.factoredai.sdfles.com for agents, backoffice.factoredai.sdfles.com for officers.
3. An agent trying to sign in on the officer subdomain, or the reverse, is rejected even with correct credentials, because the group does not match the door they used.

Errors and empty states: wrong credentials are rejected without saying which part was wrong; a staff account signing in on the wrong subdomain sees a generic access error, not a hint about which subdomain is correct.

### Data stays with its owner

1. Whatever a customer does in Clara (viewing their cards, their charges, their complaints) only ever reads that customer's own rows.
2. If anything, a bug or an attempt to reference another customer's data, tries to cross that line, it is refused and the refusal is recorded.
3. Agents and officers see the rows their role is meant to see (the conversation they are in, the queue for their area), never a customer's full record beyond what a complaint needs.

Errors and empty states: a cross-customer access attempt fails outright; the customer sees nothing different, because it never happened from where they are.

## Rules

- A customer signs up and signs in with email and password; the emailed code is a one-time sign-up verification, never a recurring login step and never a step-up inside the chat.
- Staff accounts are provisioned by the team, never self-registered, and never carry MFA in this design.
- A staff member's group (agent or officer) is fixed to the subdomain they use to sign in; using the wrong subdomain fails regardless of the account's real group.
- A fourth group, `analysts`, exists for a web that is not built yet (the improvement console on analysts.factoredai.sdfles.com); it has no members and no working sign-in flow today.
- A customer's session can only ever act on that customer's own rows, enforced independently of anything the assistant's model decides.

## Out of scope

- Password reset or account recovery flows; not specified for either population yet.
- Multi-factor authentication for staff.
- Any self-service way for staff to change their own group or request access to another area.
- A visible "why was I denied" explanation to the end user beyond a generic error; the detail lives in the logs, not the UI.
- The `analysts` group's actual sign-in flow, until the improvement console it belongs to is built.

## Open questions

None left open by this module; see ard.md for the decision trail.
