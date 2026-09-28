# Infra setup

Terraform for Clara on AWS account `975050033628`, us-east-1, one environment `prd`.
Terraform owns infrastructure and configuration; GitHub Actions owns code.
An apply is run by a person; CI only plans.

```
environments/core/  Account singletons that outlive prd: API Gateway logging role, admin users
environments/prd/   The root: providers, locals, state, the OIDC lookup
stacks/backend/     Cognito, DynamoDB and access roles, lambdas, API, messages stream, AppSync, SES, events, dashboards, deploy roles
stacks/frontend/    The three webs: S3, CloudFront, Route 53, deploy roles and Actions environments
modules/aws/*       One leaf module per service
modules/github/     actions_environment
```

## Prerequisites

- Terraform `>= 1.10` (S3 native locking) and the AWS CLI on the path: the SES module polls verification with it.
- AWS profile `personal`: `cp environments/prd/.env.example environments/prd/.env`.
- The Route 53 zone `sdfles.com` exists and stays outside Terraform.
- The GitHub OIDC provider exists and belongs to the my-napkin Terraform; `oidc.tf` only reads it. Do not create a second one: there is one per URL per account.

## Bootstrap, once

State bucket, by hand, because Terraform cannot create the bucket that holds its own state:

```bash
export AWS_PROFILE=personal
B=clara-terraform-state-975050033628
aws s3api create-bucket --bucket $B --region us-east-1
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket $B \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

GitHub App `acs-terraform` in Team-ACGS, installed only on `factored-hackathon-2026-acgs`.
Repository permissions: Metadata and Actions read-only; Administration, Environments, Variables and Secrets read and write; no organisation permissions.
Actions read is the one that is easy to miss: without it the first apply succeeds and every later plan fails with a bare 403.
App id and installation id are literals in `locals.tf`; the private key goes in the untracked `terraform.tfvars`:

```bash
cd environments/prd
{ echo 'github_app_pem = <<-PEM'; sed 's/^/  /' /path/to/acs-terraform.private-key.pem; echo 'PEM'; } > terraform.tfvars
```

## Apply

`core` first, once: API Gateway cannot write stage logs until the account has its CloudWatch role.

```bash
cd environments/core && source .env && terraform init && terraform apply
cd ../prd && source .env && terraform init && terraform apply
```

The first apply takes a while: ACM validation, the SES domain verification (Cognito refuses an unverified identity, so the apply waits for it, up to 15 minutes) and CloudFront.
Every lambda starts on a bootstrap bundle: the API ones answer 503, the Cognito triggers return the event unchanged.
A second `terraform apply` must be a no-op.

## Verify

```bash
for host in factoredai support.factoredai backoffice.factoredai; do curl -sI https://$host.sdfles.com | head -1; done
```

Isolation, without data or code: `role-customer` only reaches items whose partition key equals its `customer_id` session tag.

```bash
ROLE=$(terraform output -json access_role_arns | jq -r .customer)
aws iam simulate-principal-policy --policy-source-arn $ROLE \
  --action-names dynamodb:Query \
  --resource-arns "arn:aws:dynamodb:us-east-1:975050033628:table/clara-prd-transactions" \
  --context-entries ContextKeyName=aws:PrincipalTag/customer_id,ContextKeyValues=C1,ContextKeyType=string \
                    ContextKeyName=dynamodb:LeadingKeys,ContextKeyValues=C2,ContextKeyType=stringList
```

`implicitDeny` is the expected answer; the same call with `C1` twice answers `allowed`.

## Destroy

```bash
terraform destroy
```

Everything goes, data included: buckets force destroy, tables and pools have no deletion protection, every log group is managed here.
Only `core`, the state bucket, the Route 53 zone and the shared OIDC provider survive.

## Admin users

`core` creates the console users in `local.admins`, in group `clara-core-admins`: `AdministratorAccess` and everything denied outside us-east-1 except global services.
The region deny is a guardrail between teammates, not a boundary: an administrator can remove it.
Passwords never go through Terraform, because this repository is public:

```bash
aws iam create-login-profile --user-name <user> --password '<initial>' --password-reset-required
```

First sign-in at `https://975050033628.signin.aws.amazon.com/console` asks for a new password.

## Manual steps

- Bedrock model access for Claude Sonnet 5; `chatbot` invokes the `us.anthropic.claude-sonnet-5` inference profile.
- SES production access for `notifications.factoredai.sdfles.com`; until then Cognito only emails verified addresses.
- Activate `Project`, `Environment` and `ManagedBy` as cost allocation tags in Billing after the first apply.

## What the workflows get

Terraform writes every value a workflow needs into an Actions environment, so no workflow holds an ARN, URL or key.
Each role trusts one environment through the OIDC subject `repo:Team-ACGS/factored-hackathon-2026-acgs:environment:<name>`, and every deploy environment only accepts jobs from `main`.

| Environment | Used by | Variables |
|---|---|---|
| `prd` | Lambda deploy on merge | `AWS_REGION`, `AWS_ROLE_ARN`, `ARTIFACTS_BUCKET`, `FUNCTION_PREFIX`, `API_URL` |
| `customer-prd`, `support-prd`, `backoffice-prd` | Web deploy on merge | `AWS_REGION`, `AWS_ROLE_ARN`, `SITE_BUCKET`, `DISTRIBUTION_ID`, `SITE_URL`, `VITE_API_URL`, `VITE_USER_POOL_ID`, `VITE_USER_POOL_CLIENT_ID`, `VITE_REALTIME_URL`, `VITE_REALTIME_HTTP_URL`, `VITE_REALTIME_NAMESPACE` |
| `terraform` | `fmt`, `validate`, `plan` on pull requests, any branch | `AWS_REGION`, `AWS_ROLE_ARN`, secret `TF_GITHUB_APP_PEM` |

Lambda deploys follow auvral: build one zip per function with pinned mtimes, upload to `s3://$ARTIFACTS_BUCKET/functions/<sha>/<function>.zip`, and call `update-function-code` on `$FUNCTION_PREFIX-<function>` only when its `CodeSha256` differs.
Functions are `crud`, `messages`, `chat-notifier`, `chatbot`, `auth-post-confirmation` and `auth-pre-token-generation`; Terraform ignores their code after creation, so an apply never rolls a deploy back.
Every API and stream lambda has handler `handler.handler`; the triggers have `post_confirmation.handler` and `pre_token_generation.handler`.
Web deploys run `aws s3 sync --delete` into `SITE_BUCKET` and invalidate `DISTRIBUTION_ID`; the build always writes `index.html`, which replaces the placeholder Terraform created.
The plan role is `ReadOnlyAccess` minus customer data (table items, users, logs, queue messages, turn events) plus the state lock; fork pull requests get no environment secrets and no OIDC token, so they cannot plan.
