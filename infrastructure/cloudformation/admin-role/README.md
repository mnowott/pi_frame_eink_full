# CloudFormation: ImageUiApp admin user + role

Bootstrap stack. Creates **both**:

1. A **programmatic-only** IAM user (default `imageuiapp-admin`). No
   console password is created — daily AWS work is exclusively through
   AWS CLI / SDK using an access key the user creates after deploy.
2. The admin IAM role (default `imageuiapp-admin`) that the user above
   can assume via STS. The role grants the scoped permissions Terraform
   actually needs.

The trust policy on the role names the new user as the only allowed
principal. With `RequireMFA=true` (default), AssumeRole also needs a
valid MFA code at call time.

## Why programmatic-only? Why no password?

* The admin user never logs in to the console. Console operations are
  rare for our case (CFN console for the initial stack deploy, IAM
  console for one-time MFA assignment); root handles those once.
* Removing the console login profile removes a whole attack surface
  (password leak, session cookie theft, password reuse).
* Daily work is `aws sts assume-role` with `--serial-number` and
  `--token-code` — long-lived access key on disk + MFA code from the
  authenticator app. That second factor is exactly the protection
  console password + MFA gives, minus the password.

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
* Write/delete S3 objects (the EC2 instance role does that).
* Create new IAM users, change account password policy, manage MFA
  devices for any user other than itself.
* Touch IAM resources outside the `imageuiapp*` name pattern.

## Deploy (console flow recommended on first run)

While signed in as **root**:

1. AWS Console → CloudFormation → eu-central-1 → Create stack with new
   resources.
2. Upload `admin-role.yml`.
3. Stack name: `imageuiapp-admin-role`.
4. Parameters:
   * `AdminUserName`: `imageuiapp-admin` (default fine)
   * `RequireMFA`: `true`
   * `S3BucketArn`: `arn:aws:s3:::rasp-pi-family-s3`
   * `RoleName`: `imageuiapp-admin` (default)
   * `MaxSessionDurationSeconds`: `3600`
5. Capabilities: check **CAPABILITY_NAMED_IAM**.
6. Create stack. Wait ~30 s for `CREATE_COMPLETE`.
7. Outputs tab gives you: `AdminUserArn`, `ExpectedMfaSerial`, `RoleArn`.

## Post-deploy (still signed in as root, one-time)

### 1. Assign a virtual MFA device

* IAM → Users → `imageuiapp-admin` → **Security credentials** tab
* **Multi-factor authentication (MFA)** → **Assign MFA device**
* Device name: `imageuiapp-admin` (must match the suffix in
  `ExpectedMfaSerial` so the ARN we already know is correct)
* MFA device: Authenticator app
* Open Google Authenticator / Authy / Microsoft Authenticator → scan QR
* Enter two consecutive 6-digit codes → Add MFA

### 2. Create one access key for the user

* Same Security credentials tab → **Access keys** → **Create access key**
* Use case: "Command Line Interface (CLI)"
* Tick the confirmation
* Save **Access Key ID** and **Secret Access Key** (last time you see
  the secret)

### 3. Configure AWS CLI on the laptop

Replace any default profile (e.g. the old `pi-programmatic-user`):

```bash
aws configure
# AWS Access Key ID:    <paste from step 2>
# AWS Secret Access Key: <paste from step 2>
# Default region:        eu-central-1
# Default output:        json
```

The new keys belong to the very-low-permission `imageuiapp-admin` user.
Direct API calls with these keys can do almost nothing without first
calling `sts:AssumeRole` with MFA — which is exactly the point.

### 4. Fill `.env` at the repo root

```
AWS_ADMIN_ROLE_ARN=<RoleArn from stack output>
AWS_MFA_SERIAL=<ExpectedMfaSerial from stack output>
```

### 5. Sign root out and lock it away

* Enable hardware MFA on root if not already.
* Store root credentials offline (password manager, paper in a safe).
* Daily IaC work no longer touches root.

### 6. Test the flow

```bash
source scripts/aws/assume_admin.sh
# Enter the current 6-digit MFA code from your authenticator app.
aws sts get-caller-identity
# Expect: ...:assumed-role/imageuiapp-admin/imageuiapp-admin-...
```

## Deploy via CLI (alternative)

```bash
cd infrastructure/cloudformation/admin-role

cp parameters.example.json parameters.json
# Edit parameters.json. parameters.json is gitignored.

aws cloudformation deploy \
  --stack-name imageuiapp-admin-role \
  --template-file admin-role.yml \
  --parameter-overrides $(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' parameters.json) \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1
```

You still complete steps 1-6 above (MFA + access key + .env + test).

## Rotate the access key

1. Sign in as root.
2. IAM → Users → `imageuiapp-admin` → Security credentials.
3. Create a new access key. Update the laptop's `~/.aws/credentials`.
4. Test `source scripts/aws/assume_admin.sh && aws sts get-caller-identity`.
5. Deactivate, then delete the old access key.

CloudFormation does not manage the access key, so rotation does not
touch the stack.

## Tear down

```bash
aws cloudformation delete-stack --stack-name imageuiapp-admin-role --region eu-central-1
```

Before delete:
* Detach the virtual MFA device from the user (IAM → Users → Security
  credentials → Remove device). The stack delete fails on
  `AWS::IAM::User` while a device is attached.
* Delete the user's access keys. Same Security credentials tab → delete
  every active or inactive key. The stack delete fails on
  `AWS::IAM::User` while keys exist.

## Threat model notes

* `RequireMFA=true` blocks role assume without a current MFA code.
* The user's bootstrap policy lets them only resync their own MFA
  device and call `sts:AssumeRole` on this one role. Without MFA they
  can do nothing else.
* No console login attached to this user, so no password to phish or
  guess.
* Trust principal is locked to this account's IAM user only — no
  cross-account or external trust.
* Role session is short (default 1 h, max 12 h).
* Access key lives only on the laptop in `~/.aws/credentials`. It is
  long-lived; rotate it on any suspicion of compromise.
