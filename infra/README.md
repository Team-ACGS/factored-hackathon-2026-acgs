# Infra

Terraform for Clara on AWS account `975050033628`, us-east-1, one environment (`prd`).
Terraform owns infrastructure and configuration; GitHub Actions owns code, deploying the lambda bundles and the web on every merge to `main`.
A person runs `terraform apply`; CI only runs `fmt`, `validate` and `plan`.
The architecture diagram is in the [root README](../README.md#architecture).

| Path | What |
|---|---|
| `environments/core/` | Account singletons that outlive `prd`: the API Gateway logging role and the admin users |
| `environments/prd/` | The root: providers, state, the GitHub OIDC lookup; it wires the two stacks |
| `stacks/backend/` | Cognito pools, DynamoDB tables, access roles, lambdas, API Gateway, the messages stream, AppSync Events, SES, the events bus, dashboards, deploy roles |
| `stacks/frontend/` | S3, CloudFront, Route 53 records, deploy roles and Actions environments of the web |
| `modules/aws/*` | One leaf module per AWS service |
| `modules/github/` | The Actions environment module |
| `docs/setup.md` | Bootstrap, apply, verify and destroy, step by step |

## Validate

Needs Terraform 1.10 or newer and no credentials.

```bash
cd environments/prd
terraform init -backend=false
terraform validate
cd ../..
terraform fmt -check -recursive
```

## Plan

A real `terraform plan` reads the remote state and the live account, so it needs:

- the AWS profile `personal`, an admin of account `975050033628` (`export AWS_PROFILE=personal`, or `source .env` after copying `.env.example` in the environment folder), which also reaches the state bucket `clara-terraform-state-975050033628`;
- for `environments/prd` only, the private key of the GitHub App `acs-terraform` in the untracked `environments/prd/terraform.tfvars`, in the format of `terraform.tfvars.example`;
- the AWS CLI on the path, which the SES module uses to poll domain verification.

```bash
cd environments/core && terraform init && terraform plan
cd ../prd && terraform init && terraform plan
```

`terraform.tfvars` and `.env` files are ignored by git and never committed.
Never run `apply` outside the procedure in [docs/setup.md](docs/setup.md).

## Flows

Every flow runs on this stack; the ones that exist because of it:

- [Authenticate an API request](../docs/modules/identity/flows.md#authenticate-an-api-request)
- [Assume role-customer for the customer's data](../docs/modules/identity/flows.md#assume-role-customer-for-the-customers-data)
- [Authorize a room subscription](../docs/modules/messaging/flows.md#authorize-a-room-subscription)
- [Publish a stored message to the room](../docs/modules/messaging/flows.md#publish-a-stored-message-to-the-room)
- [Emit turn events](../docs/modules/assistant/flows.md#emit-turn-events)
- [Publish the policy corpus](../docs/modules/data/flows.md#publish-the-policy-corpus)
