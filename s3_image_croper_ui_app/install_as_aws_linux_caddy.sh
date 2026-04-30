#!/usr/bin/env bash
#
# Install ImageUiApp on Amazon Linux 2023 (or AL2) behind Caddy.
#
# Topology:
#   Internet :80,:443 -> Caddy (auto Let's Encrypt) -> 127.0.0.1:8051 (Streamlit)
#   Streamlit performs OIDC login natively against Microsoft Entra ID via
#   .streamlit/secrets.toml. No ALB, no oauth2-proxy.
#
# Required env (set before running, e.g. in /home/ec2-user/repo/pi_project/.env):
#   APP_DOMAIN          public hostname, e.g. app.your-domain.example
#   ADMIN_EMAIL         email for ACME / Let's Encrypt account registration
#   S3_BUCKET           target S3 bucket
#   AWS_DEFAULT_REGION  e.g. eu-central-1
#   AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (or use IAM role)
#
# Required secrets file (created by this script as an empty stub; you must edit
# it after install before starting the service):
#   /etc/imageuiapp/secrets.toml   (chmod 640, owned root:ec2-user)
#
# Usage:
#   sudo bash install_as_aws_linux_caddy.sh

set -euo pipefail

APP_USER="ec2-user"
HOME_DIR="/home/${APP_USER}"
SECRETS_DIR="/etc/imageuiapp"
SECRETS_FILE="${SECRETS_DIR}/secrets.toml"
CADDY_VERSION="${CADDY_VERSION:-2.8.4}"

########################################
# 0) Load .env from repo root
########################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_ENV="${SCRIPT_DIR}/../.env"
if [ ! -f "$ROOT_ENV" ]; then
  echo "ERROR: .env not found at ${ROOT_ENV}"
  echo "Copy .env.example to .env and fill in your values first."
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ROOT_ENV"
set +a

for var in S3_BUCKET AWS_DEFAULT_REGION APP_DOMAIN ADMIN_EMAIL; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: ${var} is not set in ${ROOT_ENV}"
    exit 1
  fi
done

# Persist app env vars for ec2-user shells (does not write secrets here).
for line in \
  "export S3_BUCKET=\"${S3_BUCKET}\"" \
  "export AWS_REGION=\"${AWS_DEFAULT_REGION}\"" \
  "export AWS_DEFAULT_REGION=\"${AWS_DEFAULT_REGION}\"" \
  "export APP_DOMAIN=\"${APP_DOMAIN}\""
do
  if ! grep -qxF "$line" "${HOME_DIR}/.bashrc" 2>/dev/null; then
    echo "$line" >> "${HOME_DIR}/.bashrc"
  fi
done

########################################
# 1) System packages
########################################

if command -v dnf >/dev/null 2>&1; then
  PKG_MGR=dnf
elif command -v yum >/dev/null 2>&1; then
  PKG_MGR=yum
else
  echo "Neither dnf nor yum found. Are you sure this is Amazon Linux?"
  exit 1
fi

echo "==> Updating system packages..."
sudo "$PKG_MGR" -y update

echo "==> Installing python3, python3.11, pip, awscli, tar..."
sudo "$PKG_MGR" -y install python3 python3-pip awscli tar
if "$PKG_MGR" list python3.11 >/dev/null 2>&1; then
  sudo "$PKG_MGR" -y install python3.11
else
  echo "ERROR: python3.11 not in repos. Required for ImageUiApp (>=3.11)."
  exit 1
fi

########################################
# 2) Install Caddy (static binary, official release)
########################################

if command -v caddy >/dev/null 2>&1 && \
   caddy version 2>/dev/null | grep -q "v${CADDY_VERSION}"; then
  echo "==> Caddy v${CADDY_VERSION} already installed, skipping."
else
  echo "==> Installing Caddy v${CADDY_VERSION}..."
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64)  CADDY_ARCH=amd64 ;;
    aarch64) CADDY_ARCH=arm64 ;;
    *) echo "ERROR: unsupported arch ${ARCH}"; exit 1 ;;
  esac
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fsSL -o "${TMP}/caddy.tar.gz" \
    "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_${CADDY_ARCH}.tar.gz"
  tar -xzf "${TMP}/caddy.tar.gz" -C "${TMP}" caddy
  sudo install -m 0755 "${TMP}/caddy" /usr/local/bin/caddy
fi

# Dedicated caddy user/group (idempotent)
if ! id caddy >/dev/null 2>&1; then
  echo "==> Creating caddy system user..."
  sudo useradd --system --home /var/lib/caddy --shell /usr/sbin/nologin \
    --comment "Caddy web server" caddy
fi
sudo install -d -o caddy -g caddy -m 0750 /var/lib/caddy
sudo install -d -o caddy -g caddy -m 0750 /var/log/caddy
sudo install -d -o root  -g root  -m 0755 /etc/caddy

########################################
# 3) Render Caddyfile
########################################

echo "==> Writing /etc/caddy/Caddyfile for domain ${APP_DOMAIN}..."
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
{
    email ${ADMIN_EMAIL}
}

${APP_DOMAIN} {
    encode gzip
    reverse_proxy 127.0.0.1:8051 {
        # Streamlit uses websockets for live page updates.
        transport http {
            keepalive 5m
        }
    }
}
EOF

sudo tee /etc/systemd/system/caddy.service >/dev/null <<'EOF'
[Unit]
Description=Caddy web server
Documentation=https://caddyserver.com/docs/
After=network-online.target
Wants=network-online.target

[Service]
User=caddy
Group=caddy
ExecStart=/usr/local/bin/caddy run --environ --config /etc/caddy/Caddyfile
ExecReload=/usr/local/bin/caddy reload --config /etc/caddy/Caddyfile --force
TimeoutStopSec=5s
LimitNOFILE=1048576
PrivateTmp=true
ProtectSystem=full
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

########################################
# 4) Poetry + ImageUiApp install
########################################

if ! sudo -u "${APP_USER}" bash -lc 'command -v poetry >/dev/null 2>&1'; then
  echo "==> Installing Poetry (using python3.11 — installer pins recent Poetry that needs >=3.10)..."
  sudo -u "${APP_USER}" bash -lc 'curl -sSL https://install.python-poetry.org | python3.11 -'
else
  echo "==> Poetry already installed."
fi

if ! grep -q '.local/bin' "${HOME_DIR}/.bashrc"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME_DIR}/.bashrc"
fi
export PATH="${HOME_DIR}/.local/bin:${PATH}"

IMAGE_APP_DIR="${SCRIPT_DIR}/ImageUiApp"
if [ ! -d "${IMAGE_APP_DIR}" ]; then
  echo "ERROR: ${IMAGE_APP_DIR} not found."
  exit 1
fi

echo "==> Configuring Poetry env for ImageUiApp with Python 3.11..."
sudo -u "${APP_USER}" bash -lc "
  cd '${IMAGE_APP_DIR}' \
  && poetry env use /usr/bin/python3.11 \
  && poetry install
"

########################################
# 5) Streamlit secrets file (out-of-tree, never committed)
########################################

# Create /etc/imageuiapp/ owned by root:ec2-user, only readable by group.
sudo install -d -o root -g "${APP_USER}" -m 0750 "${SECRETS_DIR}"

if [ ! -f "${SECRETS_FILE}" ]; then
  echo "==> Creating empty ${SECRETS_FILE}. Edit it before starting imageuiapp."
  sudo install -o root -g "${APP_USER}" -m 0640 /dev/null "${SECRETS_FILE}"
  TEMPLATE="${IMAGE_APP_DIR}/.streamlit/secrets.toml.example"
  if [ -f "${TEMPLATE}" ]; then
    sudo tee "${SECRETS_FILE}" >/dev/null < "${TEMPLATE}"
    sudo chmod 0640 "${SECRETS_FILE}"
    sudo chown root:"${APP_USER}" "${SECRETS_FILE}"
  fi
else
  echo "==> ${SECRETS_FILE} already exists, leaving as-is."
fi

# Symlink working-dir .streamlit/secrets.toml -> /etc/imageuiapp/secrets.toml
sudo -u "${APP_USER}" mkdir -p "${IMAGE_APP_DIR}/.streamlit"
LINK="${IMAGE_APP_DIR}/.streamlit/secrets.toml"
if [ -L "${LINK}" ] || [ ! -e "${LINK}" ]; then
  sudo -u "${APP_USER}" ln -sfn "${SECRETS_FILE}" "${LINK}"
else
  echo "WARNING: ${LINK} exists and is not a symlink; leaving alone."
fi

########################################
# 6) imageuiapp.service (bound to 127.0.0.1)
########################################

SERVICE_FILE="/etc/systemd/system/imageuiapp.service"
sudo tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=ImageUiApp (Streamlit, behind Caddy)
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${IMAGE_APP_DIR}
ExecStart=/bin/bash -lc 'cd "${IMAGE_APP_DIR}" && poetry run imageuiapp --address 127.0.0.1 --port 8051'
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

# --- Sandboxing ---
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
RestrictSUIDSGID=true
PrivateDevices=true

[Install]
WantedBy=multi-user.target
EOF

########################################
# 7) Enable + start
########################################

echo "==> Reloading systemd and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable caddy imageuiapp

echo "==> Starting caddy (will request Let's Encrypt cert on first request)..."
sudo systemctl restart caddy

echo "==> Starting imageuiapp..."
sudo systemctl restart imageuiapp || true

cat <<EOM

==============================================
Install done.

NEXT STEPS:
  1. Edit ${SECRETS_FILE} with real Entra OIDC values
     (client_id, client_secret, tenant in server_metadata_url, cookie_secret).
  2. In Entra ID App Registration -> Authentication, add redirect URI:
        https://${APP_DOMAIN}/oauth2callback
  3. In Route 53, point A record ${APP_DOMAIN} to this instance's public IP
     (use an Elastic IP).
  4. Open Security Group inbound: 80/tcp and 443/tcp from 0.0.0.0/0.
  5. Restart imageuiapp:
        sudo systemctl restart imageuiapp
  6. Verify:
        sudo systemctl status caddy imageuiapp
        curl -I https://${APP_DOMAIN}/
        journalctl -u caddy -n 100
        journalctl -u imageuiapp -n 100
==============================================
EOM
