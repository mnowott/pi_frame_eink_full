# Secure Streamlit App on EC2 with Caddy + Entra ID OIDC (Runbook)

This replaces the previous ALB + Entra OIDC setup. The ALB cost (~$18-22/mo
base) is removed; auth is performed inside Streamlit using its native OIDC
support (>=1.42), TLS is terminated by Caddy with automatic Let's Encrypt
certificates, and DNS still points at a single EC2 instance.

## 1. Architecture Overview

```
Internet :80,:443
        |
        v
   EC2 t4g.micro (Amazon Linux 2023)
   +-----------------------------------------------------+
   | caddy.service       :80,:443  (auto Let's Encrypt) |
   |   reverse_proxy --> 127.0.0.1:8051                 |
   | imageuiapp.service  127.0.0.1:8051                 |
   |   Streamlit + [auth] block -> Microsoft Entra ID   |
   +-----------------------------------------------------+
                           |
                           v
                    Microsoft Entra ID
                    (App Registration, OIDC)
```

* **Domain:** `app.your-domain.example`
* **DNS:** Route 53 A record -> EC2 Elastic IP (no ALB alias)
* **TLS:** Let's Encrypt via Caddy ACME HTTP-01 (port 80 must be reachable)
* **Auth:** Microsoft Entra ID OIDC, validated inside Streamlit
* **Backend:** Streamlit on `127.0.0.1:8051` (not exposed to the internet)

## 2. EC2 Provisioning

Recommended path: use the Terraform module under
`infrastructure/terraform/imageuiapp/` (assume admin role first via
`scripts/aws/assume_admin.sh`). It provisions exactly the resources below
and imports the existing S3 bucket without recreating it.

| Item | Value |
|------|-------|
| Instance type | `t4g.micro` (1 GB RAM, ARM, ~$6/mo) |
| AMI | Amazon Linux 2023 ARM (auto-discovered via `data.aws_ami`) |
| EBS | 30 GB gp3, encrypted (AL2023 ARM AMI snapshot floor is 30 GiB) |
| IMDS | v2 required |
| Elastic IP | Allocated and associated |
| Security Group inbound | 22/tcp from `ssh_admin_cidr`, 80/tcp + 443/tcp from `0.0.0.0/0` |
| Security Group outbound | All (default) |
| IAM role | `imageuiapp-ec2`, S3 access to the image bucket; no AWS keys on disk |

If image processing at the 4000 px slider maximum runs out of memory, upgrade
to `t4g.small` (2 GB).

## 3. DNS

Route 53 hosted zone for `your-domain.example`:

* **Name:** `app.your-domain.example`
* **Type:** `A`
* **Value:** Elastic IP of the EC2 instance
* **TTL:** 60 s during cutover, then back to 300 s

There is no ALB alias and no ACM certificate.

## 4. Microsoft Entra ID App Registration

In Azure Portal -> Entra ID -> App registrations:

* Note the **Application (client) ID** and **Directory (tenant) ID**.
* **Certificates & secrets**: create a client secret. Record it once.
* **Authentication**: add redirect URI

  ```
  https://app.your-domain.example/oauth2callback
  ```

  (Streamlit native auth uses the path `/oauth2callback`. The old ALB used
  `/oauth2/idpresponse`; remove that URI after cutover.)
* **API permissions**: `openid`, `profile`, `email`.

In Entra ID -> Enterprise applications -> *your app*:

* **Properties -> User assignment required:** **Yes**
* **Users and groups:** assign exactly the people allowed to access the app.

## 5. Secrets file on the EC2 host

The Streamlit `[auth]` block lives in `/etc/imageuiapp/secrets.toml`, owned
`root:ec2-user`, mode `640`. The repo working directory has a symlink at
`s3_image_croper_ui_app/ImageUiApp/.streamlit/secrets.toml` pointing to it.
The repository contains only `.streamlit/secrets.toml.example` (placeholders).

```toml
[auth]
redirect_uri = "https://app.your-domain.example/oauth2callback"
cookie_secret = "<32-byte url-safe random>"
client_id = "<entra application client id>"
client_secret = "<entra client secret>"
server_metadata_url = "https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration"
client_kwargs = { scope = "openid profile email", prompt = "select_account" }
```

Generate the cookie secret with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never commit this file. The root `.gitignore` excludes
`**/.streamlit/secrets.toml` so accidental `git add -A` cannot pull it in.

## 6. Install

On the EC2 instance, as a user with sudo:

```bash
git clone <your repo url> ~/pi_project
cd ~/pi_project
cp .env.example .env
# Edit .env: set APP_DOMAIN, ADMIN_EMAIL, S3_BUCKET, AWS_DEFAULT_REGION,
# AWS_ACCESS_KEY_ID/SECRET (or rely on the IAM role -- in that case leave
# the access key vars unset and the Streamlit app will use the role).

sudo bash s3_image_croper_ui_app/install_as_aws_linux_caddy.sh
```

This script:

1. Installs Python 3.11, Poetry, awscli.
2. Installs Caddy v2 as a static binary, creates the `caddy` system user, and
   writes `/etc/caddy/Caddyfile` for `${APP_DOMAIN}` reverse-proxying to
   `127.0.0.1:8051`.
3. Creates `/etc/imageuiapp/secrets.toml` (mode 640, root:ec2-user) seeded
   from the example template, and symlinks
   `s3_image_croper_ui_app/ImageUiApp/.streamlit/secrets.toml` to it.
4. Creates `imageuiapp.service` bound to `127.0.0.1:8051` with the same
   sandboxing block used elsewhere in the project.
5. Enables and starts both `caddy.service` and `imageuiapp.service`.

After install, edit `/etc/imageuiapp/secrets.toml` with real Entra OIDC
values, then:

```bash
sudo systemctl restart imageuiapp
```

## 7. Verification

```bash
# 1. Caddy obtained the LE cert and is listening
sudo systemctl status caddy
journalctl -u caddy -n 100 --no-pager

# 2. Streamlit listening locally only
ss -tlnp | grep 8051        # bound to 127.0.0.1, not 0.0.0.0

# 3. End-to-end: opens Microsoft sign-in, then the app
curl -I https://app.your-domain.example/
# In a browser: incognito, expect Microsoft login -> app.
```

If `st.user.is_logged_in` is unavailable, the in-app gate falls through and
the app loads without auth -- this happens only if `[auth]` is missing or
malformed in `secrets.toml`. Fix the file and restart.

## 8. Cutover from ALB (big-bang)

1. Pre-step: lower R53 TTL on `app.your-domain.example` to 60 s, wait for the
   old TTL to expire.
2. Provision the new EC2 + Elastic IP. Run the install script.
3. Edit `/etc/imageuiapp/secrets.toml`. Restart `imageuiapp`.
4. Verify locally with an `/etc/hosts` override:
   `<EIP>  app.your-domain.example`. Walk the full Microsoft login flow.
5. In Entra App Registration, **add** the new redirect URI
   `https://app.your-domain.example/oauth2callback` (keep the old
   `/oauth2/idpresponse` URI temporarily in case you have to roll back).
6. Update the R53 record from "Alias to ALB" to "A -> EIP". Wait for DNS.
7. Confirm production traffic is healthy.
8. Tear down the ALB, its target group, and the ACM cert (if it was only
   used by this ALB).
9. Remove the obsolete `/oauth2/idpresponse` redirect URI from Entra.

## 9. Rollback

If anything is broken after the DNS flip:

* Revert the R53 record back to the ALB alias.
* `imageuiapp.service` and Caddy can stay up; nothing will reach them.
* Investigate, fix, re-flip when ready.

## 10. Cost comparison

Numbers below are the **actual** pre-cutover bill from AWS Cost
Explorer (April 2026), and the projected steady-state post-cutover.
The original `~$28-32` estimate missed Public IPv4 charges (introduced
Feb 2024), idle EIPs, the second EC2 that was still running, and DE
VAT.

| Item | Before (ALB, actual) | After (Caddy, projected) |
|------|----------------------|--------------------------|
| ALB base + LCU | $18.84 | $0 |
| EC2 compute | $16.68 (two instances) | ~$6 (t4g.micro) |
| EBS / EC2-Other | $1.84 | ~$2.40 |
| Public IPv4 (VPC) | $15.37 (4 EIPs total) | $0 (1 in-use EIP) |
| ACM cert | $0 | $0 (LE via Caddy) |
| Route 53 | $1.01 | $0.50 |
| S3 | $0.03 | <$0.10 |
| Tax (DE 19% VAT) | $10.26 | ~$1.70 |
| **Monthly total** | **~$64** | **~$10.70** |

Realised saving: **~83 %**, ~$640/year. See
[`docs/audits/AUD_004_post_cutover_cleanup.md`](../docs/audits/AUD_004_post_cutover_cleanup.md)
for the full bill audit and decommission record.
