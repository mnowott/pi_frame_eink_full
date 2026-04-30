# CloudFormation: ImageUiApp admin role

Creates an IAM role (`imageuiapp-admin`) that an existing IAM principal
(typically your IAM user) can assume via STS to manage the Terraform
infrastructure under `infrastructure/terraform/imageuiapp/`.

## Why a CloudFormation stack and not Terraform itself?

Bootstrap problem: Terraform needs permissions to create roles, but you
do not want to keep long-lived programmatic access keys with
`AdministratorAccess` on disk for daily use. So:

1. **Once**, with your existing admin credentials (root or
   AdministratorAccess IAM user), deploy this CloudFormation stack. It
   creates the scoped `imageuiapp-admin` role.
2. **Daily** Terraform/IaC work goes through `scripts/aws/assume_admin.sh`,
   which uses STS (with MFA) to obtain short-lived credentials in the role.
3. The original admin credentials are kept off the laptop for daily work.

CloudFormation is a deliberate choice over Terraform here:
* Self-contained — no Terraform state file in play before any role exists.
* Drift-aware — `cloudformation describe-stacks` shows whether anything
  changed out-of-band.
* Easy teardown — `aws cloudformation delete-stack` undoes everything.

## Permissions granted

The role can do exactly what Terraform needs:

| Service | Scope |
|---------|-------|
| EC2 | Full (instances, EIPs, SGs, volumes) |
| IAM | Limited to roles + instance profiles named `imageuiapp*` |
| S3 | Read-only on the configured bucket; bucket tagging allowed |
| Route 53 | Read all zones; modify records |
| ACM | Read; delete (for old ALB cert cleanup) |
| ELBv2 | Read; delete listener/target-group/load-balancer (ALB teardown) |

The role explicitly does NOT have:
* Object writes/deletes on the S3 bucket (the EC2 instance role does that).
* Permissions to create new IAM users, change account password policy, or
  manage MFA devices.
* `iam:*` outside the `imageuiapp*` name pattern.

## Deploy

```bash
cd infrastructure/cloudformation/admin-role

# Make a real parameter file from the template (gitignored).
cp parameters.example.json parameters.json
# Edit parameters.json:
#   - TrustedPrincipalArn: your IAM user ARN (or SSO permission set role ARN)
#   - S3BucketArn:         arn:aws:s3:::<your-bucket>

aws cloudformation deploy \
  --stack-name imageuiapp-admin-role \
  --template-file admin-role.yml \
  --parameter-overrides $(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' parameters.json) \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

# Get the role ARN to put into .env:
aws cloudformation describe-stacks \
  --stack-name imageuiapp-admin-role \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text \
  --region eu-central-1
```

Put the printed ARN into `.env` as `AWS_ADMIN_ROLE_ARN`.

## Update

Edit `admin-role.yml` and rerun the same `aws cloudformation deploy` command.

## Tear down

```bash
aws cloudformation delete-stack --stack-name imageuiapp-admin-role --region eu-central-1
```

This removes the role. Anyone whose AWS CLI was using `assume_admin.sh`
will get an `AccessDenied` on the next attempt. Existing STS sessions
remain valid until their TTL expires.

## Threat model notes

* `RequireMFA=true` is the default. Without MFA the assume-role call fails.
* Trusted principal is your account's IAM user/SSO role only. No external
  account trust.
* Role session is short (default 1 h, max 12 h via `MaxSessionDurationSeconds`).
* The role has no permission to escalate privileges (cannot create new IAM
  users, attach policies outside `imageuiapp*`, or change MFA settings).
