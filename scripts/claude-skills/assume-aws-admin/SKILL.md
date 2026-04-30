---
name: assume-aws-admin
description: |
  Use this skill whenever Claude Code needs AWS access beyond the
  default S3-only permissions on this repo: any aws-cli command that
  returns AccessDenied / UnauthorizedOperation, terraform plan/apply,
  CloudFormation deploy, EC2/IAM/Route53/EIP/Cost-Explorer/Pricing
  operations. (ELB and ACM are also covered for legacy ALB cleanup.) The skill
  obtains short-lived STS credentials for the imageuiapp-admin role,
  prompting the user for a fresh 6-digit MFA code only when the cached
  session is missing or near-expiry.
---

# Skill: assume-aws-admin

## Goal

Run an AWS command (or a chain of AWS commands) under the
`imageuiapp-admin` STS role without requiring the user to source any
script in their interactive shell. The skill collects an MFA code from
the user when needed, drives `aws sts assume-role` itself, caches the
short-lived credentials to `~/.cache/imageuiapp-admin/creds.env`, and
reuses that cache for follow-up commands within the role's session
lifetime (default 1 h).

## Workflow

1. **Try the cache first.** Run any AWS-touching command through the
   wrapper:

   ```bash
   bash scripts/aws/with_admin_role.sh <command> [args...]
   ```

   If the cache file exists and has > 60 s left, the wrapper sources it
   and exec's the command. No MFA prompt, no AWS API call.

2. **If the cache is stale, the wrapper sources `assume_admin.sh`,**
   which interactively reads a 6-digit code via `read -p`. That call
   blocks because Claude Code's Bash tool is non-interactive, and the
   wrapper exits with a "MFA code must be exactly 6 digits" error.

3. **When step 2 fails, ask the user for a fresh MFA code.** A plain
   text question is best because the code expires in ~30 s — do not
   route through long modal flows. Phrase it like:

   > Paste your current 6-digit MFA code (~30s validity).

4. **Re-run the wrapper non-interactively** with the user's code passed
   in via `MFA_CODE`. Use ONE Bash tool call so the env var reaches the
   wrapper:

   ```bash
   MFA_CODE=<the 6 digits> bash scripts/aws/with_admin_role.sh <command> [args...]
   ```

   On success the wrapper writes a fresh cache file. Subsequent
   commands in the same session can drop `MFA_CODE`:

   ```bash
   bash scripts/aws/with_admin_role.sh <next command>
   ```

5. **Chain commands when you can.** A multi-step AWS workflow (e.g.
   import + plan + apply) should run inside one bash invocation:

   ```bash
   MFA_CODE=<code> bash -c '
     source scripts/aws/assume_admin.sh \
       && cd infrastructure/terraform/imageuiapp \
       && terraform init \
       && terraform import aws_s3_bucket.imageuiapp rasp-pi-family-s3 \
       && terraform plan
   '
   ```

   This avoids re-asking the user for an MFA code mid-flow if the cache
   somehow expires between calls.

## What to do when the MFA code is wrong

`aws sts assume-role` returns an error containing
`MultiFactorAuthentication failed with invalid MFA one time pass code`.
Ask the user for a fresh code (the previous one likely expired during
the round-trip) and retry. Do not loop more than 2 times silently — if
the second code also fails, ask the user to verify the device is
enrolled and the clock on their phone is correct.

## What to do when the user lacks MFA / role

Symptoms:
* `An error occurred (AccessDenied) when calling AssumeRole: User: ... is not authorized to perform: sts:AssumeRole on resource: ...`
* `.env` missing `AWS_ADMIN_ROLE_ARN` or `AWS_MFA_SERIAL`.

Do **not** attempt the AWS command anyway. Tell the user to:

1. Deploy `infrastructure/cloudformation/admin-role/admin-role.yml`
   (one-time, account root).
2. Assign a virtual MFA device to the new IAM user.
3. Create one access key and run `aws configure` with it.
4. Fill `AWS_ADMIN_ROLE_ARN` and `AWS_MFA_SERIAL` in `.env`.

## Constraints

* `MFA_CODE` env var is one-shot. Do not store the code in any file.
* The cache file at `~/.cache/imageuiapp-admin/creds.env` has mode 600
  and contains short-lived STS credentials. Do not commit it (lives
  outside the repo) and do not echo its contents to the chat.
* Session length is bounded by `MaxSessionDuration` on the role
  (default 1 h, set in CloudFormation). If a long-running task pushes
  past that, request a new MFA code.
* The Claude Code Bash tool runs each command in a fresh subshell.
  `source` only persists env vars within a single Bash tool call. The
  wrapper handles re-sourcing the cache on every invocation.

## Installation note for the human user

The repo keeps the canonical copy of this skill at
`scripts/claude-skills/assume-aws-admin/SKILL.md` because `.claude/` is
gitignored. To activate:

```bash
mkdir -p ~/.claude/skills/assume-aws-admin
ln -sfn "$(pwd)/scripts/claude-skills/assume-aws-admin/SKILL.md" \
        ~/.claude/skills/assume-aws-admin/SKILL.md
```
