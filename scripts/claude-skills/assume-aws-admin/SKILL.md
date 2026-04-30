---
name: assume-aws-admin
description: |
  Use this skill when the user asks Claude Code to perform an AWS operation
  that requires more than the default S3-only IAM access (e.g. running
  `terraform apply`, describing EC2/ELB/IAM, deploying the CloudFormation
  admin-role stack, tearing down the old ALB). Triggers: any aws-cli call
  that returns "AccessDenied" / "UnauthorizedOperation", or upfront when
  the user requests EC2/IAM/Route53/CloudFormation/Terraform actions in
  this repo. The skill sources `scripts/aws/assume_admin.sh` to obtain
  short-lived STS credentials for the imageuiapp-admin role (MFA or SSO,
  whichever is configured in .env).
---

# Skill: assume-aws-admin

## When to use

Run this skill BEFORE any AWS command that needs more than the default
`pi-programmatic-user` IAM permissions (S3 read/write on
`rasp-pi-family-s3`). Symptoms that mean you should run it now:

* `aws ec2 describe-instances` returns `UnauthorizedOperation`.
* `terraform plan` says `AccessDenied` on `iam:*`, `ec2:*`, etc.
* User asks to "deploy", "apply terraform", "describe the ALB",
  "list certificates", "tear down the ALB", or anything similar.

## How to use

The script `scripts/aws/assume_admin.sh` MUST be **sourced** in the same
shell that will run the AWS command. Do this in a single Bash tool call so
the env vars survive into the next command:

```bash
source scripts/aws/assume_admin.sh && aws sts get-caller-identity
```

If you split the source call from the consuming command into two
separate Bash invocations, the credentials are lost — each tool call
starts a fresh shell. Always combine with `&&` in one Bash call, or run
the consuming command immediately after with `&&`.

## Setup the user must do once

Before this skill works, the user must have:

1. Deployed `infrastructure/cloudformation/admin-role/admin-role.yml`
   (creates the `imageuiapp-admin` role).
2. Filled in `.env` at the repo root with at least:
   * `AWS_ADMIN_ROLE_ARN`
   * One of `AWS_SSO_PROFILE` or `AWS_MFA_SERIAL`
3. Have `jq` and the AWS CLI v2 on `$PATH`.

If the user has not done these, do not silently fail. Ask them to run the
CloudFormation deploy first, or fall back to documenting the AWS console
steps without trying to call AWS APIs.

## Failure modes

* "ERROR: this script must be SOURCED, not executed" — you ran it instead
  of sourcing it. Use `source scripts/aws/assume_admin.sh && <command>`.
* "AWS_ADMIN_ROLE_ARN not set" — the user has not filled `.env`. Ask them
  to run the CloudFormation deploy and copy the role ARN out.
* "MFA code must be exactly 6 digits" — the script needs an interactive
  TOTP code. Skill cannot supply it; ask the user.
* SSO browser flow can be non-interactive only after `aws sso login` was
  done within the SSO session TTL. If it expired, the user must complete
  the browser confirmation again.

## Installation note for the human user

The repo keeps the canonical copy of this skill at
`scripts/claude-skills/assume-aws-admin/SKILL.md` because `.claude/` is
gitignored. To activate it for Claude Code, symlink:

```bash
mkdir -p ~/.claude/skills/assume-aws-admin
ln -sfn "$(pwd)/scripts/claude-skills/assume-aws-admin/SKILL.md" \
        ~/.claude/skills/assume-aws-admin/SKILL.md
```

Or copy the file. After that, Claude Code can invoke the skill by name.
