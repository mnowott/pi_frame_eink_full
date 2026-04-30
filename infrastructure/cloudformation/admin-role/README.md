# CloudFormation: ImageUiApp admin user + role

Bootstrap stack. Creates **both**:

1. An IAM user (default `imageuiapp-admin`) with console access, a forced
   password reset on first login, and minimal bootstrap permissions
   (manage own MFA, change own password, `sts:AssumeRole` on the role
   below).
2. An IAM role (default `imageuiapp-admin`) that the user above can
   assume via STS. The role grants the scoped permissions Terraform
   actually needs to manage ImageUiApp infrastructure.

The trust policy on the role names the new user as the only allowed
principal. With `RequireMFA=true` (default), the AssumeRole call also
needs a valid MFA code.

## Why this shape?

* Daily IaC work (`terraform apply`, `aws ec2 ...`) goes through the
  short-lived STS session of the admin role, not through long-lived
  programmatic access keys.
* The admin user has almost no direct permissions; everything live is
  routed through assume-role with MFA. Stolen user password alone
  cannot drive AWS API actions, MFA is required.
* The bootstrap user is created **inside** the stack. You do not need
  any pre-existing IAM admin user — the AWS account root deploys this
  stack once, and afterwards root is no longer needed for daily work.

## Permissions on the admin role

| Service | Scope |
|---------|-------|
| EC2 | Full (instances, EIPs, SGs, volumes) |
| IAM | Limited to roles + instance profiles named `imageuiapp*` |
| S3 | Read-only on the configured bucket; bucket tagging allowed |
| Route 53 | Read all zones; modify records |
| ACM | Read; delete (for old ALB cert cleanup) |
| ELBv2 | Read; delete listener/target-group/load-balancer (ALB teardown) |

The role explicitly cannot:
* Write/delete S3 objects (the EC2 instance role does that)
* Create new IAM users, change account password policy, manage MFA
  devices for any user other than itself
* Touch IAM resources outside the `imageuiapp*` name pattern

## Deploy (console flow recommended on first run)

1. AWS Console → CloudFormation → eu-central-1 → Create stack with new
   resources.
2. Upload `admin-role.yml`.
3. Stack name: `imageuiapp-admin-role`.
4. Parameters:
   * `AdminUserName`: `imageuiapp-admin` (default fine)
   * `InitialPassword`: a strong one-time password (12+ chars, mixed
     case, digits, symbol). NoEcho — not saved by CloudFormation, you
     will not see it again. **Write it down briefly until first login.**
   * `RequireMFA`: `true`
   * `S3BucketArn`: `arn:aws:s3:::rasp-pi-family-s3`
   * `RoleName`: `imageuiapp-admin` (default)
   * `MaxSessionDurationSeconds`: `3600`
5. Capabilities: check **CAPABILITY_NAMED_IAM**.
6. Create stack. Wait ~30 s for `CREATE_COMPLETE`.
7. Outputs tab gives you: AdminUserArn, ConsoleSignInUrl,
   ExpectedMfaSerial, RoleArn.

## After deploy

1. Sign out of root.
2. Sign in at the `ConsoleSignInUrl` from the stack output, as
   `imageuiapp-admin`, with the InitialPassword. AWS forces a reset.
3. IAM → Users → `imageuiapp-admin` → Security credentials → **Assign
   MFA device** → virtual MFA → name it the same as the user
   (`imageuiapp-admin`). Use Google Authenticator, Authy, etc.
4. Put into `.env` at the repo root:
   ```
   AWS_ADMIN_ROLE_ARN=<RoleArn from stack output>
   AWS_MFA_SERIAL=<ExpectedMfaSerial from stack output>
   ```
5. From a terminal:
   ```bash
   source scripts/aws/assume_admin.sh
   # Enter MFA code from the authenticator app.
   aws sts get-caller-identity
   # Should print  ...:assumed-role/imageuiapp-admin/...
   ```

## Deploy via CLI (alternative)

```bash
cd infrastructure/cloudformation/admin-role

cp parameters.example.json parameters.json
# Edit parameters.json. parameters.json is gitignored.
# DO NOT put the InitialPassword value into a committed file.

aws cloudformation deploy \
  --stack-name imageuiapp-admin-role \
  --template-file admin-role.yml \
  --parameter-overrides $(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' parameters.json) \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1
```

## Rotate the user's password

Sign in as the user → Security credentials → Change password.

The CloudFormation `LoginProfile` is created once on stack creation and
not refreshed on stack updates. Don't change `InitialPassword` in CFN
parameters after the first deploy; rotate via IAM directly.

## Tear down

```bash
aws cloudformation delete-stack --stack-name imageuiapp-admin-role --region eu-central-1
```

This removes both the user and the role. Detach any virtual MFA device
from the user **first** (otherwise stack deletion fails on
`AWS::IAM::User` because the device is attached). IAM → Users →
`imageuiapp-admin` → Security credentials → Remove the MFA device.

## Threat model notes

* `RequireMFA=true` blocks role assume without a current MFA code.
* The user's bootstrap policy lets them only manage their own MFA
  device, change their own password, and call `sts:AssumeRole` on this
  one role. Without MFA they can do nothing else.
* Trust principal is locked to this account's IAM user only — no
  cross-account or external trust.
* Role session is short (default 1 h, max 12 h).
* InitialPassword is `NoEcho`, never saved by CloudFormation, and a
  password reset is forced on first login. The plaintext you typed at
  deploy time exists only in your clipboard / scratch note until first
  sign-in; clear it then.
