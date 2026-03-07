Here’s a compact “runbook” you can keep for later. I’ll write it as a Markdown doc you can drop into a repo or a wiki.

---

# Secure Streamlit App on AWS with Entra ID Auth (Runbook)

## 1. Architecture Overview

* **Domain:** `example.com`
* **Public app URL:** `https://app.example.com`
* **DNS:** Route 53 hosted zone for `example.com`

  * `A` record (Alias) → ALB DNS
* **Load Balancer:** Application Load Balancer (ALB), internet-facing, in `eu-central-1`

  * Listener 80 (HTTP) → redirects to HTTPS
  * Listener 443 (HTTPS) → does:

    1. OIDC authentication against Microsoft Entra ID
    2. Forwards authenticated requests to the target group
* **Backend:** EC2 (Amazon Linux) running a Streamlit app on port **8051**
* **Auth:** Microsoft Entra ID (Azure AD) OIDC; only assigned users can access

---

## 2. DNS & TLS (Route 53 + ACM + ALB)

### 2.1 Route 53

Hosted zone: `example.com`

Record for the app:

* **Name:** `app.example.com`
* **Type:** `A`
* **Alias:** Yes
* **Target:** `dualstack.<your-alb-name>.<region>.elb.amazonaws.com.` (ALB DNS name)

Make sure your domain registrar uses the Route 53 name servers for `example.com`.

### 2.2 ACM Certificate

* Request a certificate in **the same region as the ALB** (`eu-central-1`).
* Domain: `*.example.com`
* Validate (DNS validation recommended).
* Attach this cert to the ALB HTTPS listener:

  * Listener 443 → **Standard-SSL/TLS-Serverzertifikat**: `*.example.com`

---

## 3. EC2 Instance & Streamlit Hello World

### 3.1 Setup Script (Amazon Linux)

Run on the EC2 instance (Amazon Linux 2023, as `ec2-user`):

```bash
#!/usr/bin/env bash
set -e

APP_DIR="/opt/streamlit-app"
APP_USER="ec2-user"
PORT="8051"

echo "Updating system packages..."
if command -v dnf >/dev/null 2>&1; then
  sudo dnf -y update
elif command -v yum >/dev/null 2>&1; then
  sudo yum -y update
else
  echo "Neither dnf nor yum found. Exiting."
  exit 1
fi

echo "Installing Python3 and pip..."
if command -v dnf >/dev/null 2>&1; then
  sudo dnf -y install python3 python3-pip
else
  sudo yum -y install python3 python3-pip
fi

echo "Creating app directory at ${APP_DIR}..."
sudo mkdir -p "${APP_DIR}"
sudo chown "${APP_USER}:${APP_USER}" "${APP_DIR}"

cd "${APP_DIR}"

echo "Creating virtual environment..."
sudo -u "${APP_USER}" python3 -m venv venv

echo "Activating venv and installing Streamlit..."
sudo -u "${APP_USER}" bash -c "
  source venv/bin/activate
  pip install --upgrade pip
  pip install streamlit
"

echo "Creating Streamlit app (app.py)..."
sudo -u "${APP_USER}" tee "${APP_DIR}/app.py" >/dev/null << 'EOF'
import streamlit as st

st.set_page_config(page_title="Hello from Streamlit", page_icon="👋")

st.title("Hello, Streamlit on EC2 👋")
st.write("If you see this, your app is running on port 8051 behind your EC2 instance.")

st.subheader("Next steps")
st.markdown(
    """
    - The app is listening on **port 8051**  
    - Point your ALB Target Group to this instance/port  
    - Allow inbound 8051 from the ALB security group in the EC2 SG  
    """
)
EOF

echo "Creating systemd service for Streamlit..."
SERVICE_FILE="/etc/systemd/system/streamlit-app.service"
sudo tee "${SERVICE_FILE}" >/dev/null << EOF
[Unit]
Description=Streamlit Hello World App
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/streamlit run ${APP_DIR}/app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd and enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable streamlit-app
sudo systemctl start streamlit-app

echo "Done!"
echo "Check status with: sudo systemctl status streamlit-app"
echo "The app is listening on port ${PORT} (0.0.0.0)."
```

### 3.2 Managing the Streamlit Service

* **Stop (temporary):**

  ```bash
  sudo systemctl stop streamlit-app
  ```

* **Disable (no auto-start on boot, but still startable manually):**

  ```bash
  sudo systemctl disable streamlit-app
  ```

* **Re-enable + start:**

  ```bash
  sudo systemctl enable streamlit-app
  sudo systemctl start streamlit-app
  ```

* **Completely remove:**

  ```bash
  sudo systemctl stop streamlit-app
  sudo systemctl disable streamlit-app
  sudo rm /etc/systemd/system/streamlit-app.service
  sudo systemctl daemon-reload
  sudo systemctl reset-failed
  sudo rm -rf /opt/streamlit-app
  ```

---

## 4. Security Groups

### 4.1 ALB Security Group (e.g. `alb-streamlit-sg`)

* **Inbound:**

  * HTTP (80) from `0.0.0.0/0`
  * HTTPS (443) from `0.0.0.0/0`
* **Outbound:**

  * Allow all (or at least HTTPS 443 to Internet for Entra endpoints)

### 4.2 EC2 Security Group

* **Inbound (minimal):**

  * SSH (22) from your IP (not 0.0.0.0/0 in production)
  * Custom TCP `8051` **from the ALB security group** (`alb-streamlit-sg`)
* **Outbound:**

  * Allow all (typical default)

---

## 5. Target Group & ALB Listeners

### 5.1 Target Group

* **Type:** Instance (IPv4)
* **Protocol:** HTTP
* **Port:** 8051
* **Targets:** EC2 instance(s)
* **Health checks:**

  * Protocol: HTTP
  * Port: 8051
  * Path: `/` (or whatever path your app responds to)

### 5.2 HTTP Listener (Port 80) – Redirect to HTTPS

Listener 80:

* **Standardaktion:** `Umleitung zu URL`
* Settings for the redirect:

  * Protocol: `HTTPS`
  * Port: `443`
  * Host: `#{host}`
  * Pfad: `/#{path}`
  * Query: `#{query}`
  * Status code: `301`

This forces all `http://app.example.com` → `https://app.example.com`.

### 5.3 HTTPS Listener (Port 443) – OIDC + Forward

Listener 443:

* **Protocol:** HTTPS
* **Port:** 443
* **SSL certificate:** `*.example.com` (ACM)
* **Vorab-Weiterleitungsaktion (Pre-auth action):**

  * `Benutzer authentifizieren` (Authenticate user)
  * **OIDC** with Microsoft Entra ID (see next section)
* **Routing-Aktion (after auth):**

  * `Zur Zielgruppe weiterleiten`
  * Zielgruppe: `tg-streamlit-8501`
  * Weight: 1 (100 %)
  * Stickiness: off (optional)

---

## 6. Microsoft Entra ID (Azure AD) Configuration

### 6.1 OIDC Discovery Metadata

From:

```text
https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration
```

You get (example with your values):

* **Issuer:**

  ```text
  https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
  ```

* **Authorization endpoint:**

  ```text
  https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/authorize
  ```

* **Token endpoint:**

  ```text
  https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/token
  ```

* **Userinfo endpoint:**

  ```text
  https://graph.microsoft.com/oidc/userinfo
  ```

### 6.2 App Registration

In Azure Portal → **Entra ID → App registrations → your app**:

* Note the **Application (client) ID**
* Create a **client secret**
* Under **Authentication**:

  * Add redirect URI:

    ```text
    https://app.example.com/oauth2/idpresponse
    ```

  * Enable **ID tokens** (if there’s an implicit/hybrid section)
* Under **API permissions**:

  * At minimum: `openid`, `profile`, `email` scopes (standard OIDC)

### 6.3 Enterprise Application – Restrict Access

In Entra ID → **Enterprise applications**:

* Open the enterprise app linked to your registration
* **Properties:**

  * **User assignment required?** → **Yes**
* **Users and groups:**

  * Assign only the users/groups allowed to access `app.example.com`

Result: only assigned users can obtain valid tokens → only they pass ALB auth.

---

## 7. ALB OIDC Auth Configuration (Field-by-Field)

In the ALB HTTPS (443) listener configuration:

**Vorab-Weiterleitungsaktion:**
`Benutzer authentifizieren` → Provider: OIDC

Fill in:

* **Aussteller (Issuer):**

  ```text
  https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
  ```

* **Autorisierungs-Endpunkt (Authorization endpoint):**

  ```text
  https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/authorize
  ```

* **Token-Endpunkt (Token endpoint):**

  ```text
  https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/token
  ```

* **Benutzer-Info-Endpunkt (User info endpoint):**

  ```text
  https://graph.microsoft.com/oidc/userinfo
  ```

* **Client-ID:**

  * The Entra **Application (client) ID**

* **Client-Schlüssel:**

  * The client secret from Entra

* **Scope:**

  ```text
  openid profile email
  ```

* **Session cookie name:**

  * Something like: `AWSELBAuthSessionCookie`

* **On unauthenticated request:**

  * Choose **Authenticate** (not “Allow” or “Deny”)

After this “Authenticate” action, add the **forward** action to `tg-streamlit-8501`.

---

## 8. Testing & Troubleshooting

### 8.1 DNS

From your local machine:

```bash
dig app.example.com
# or
nslookup app.example.com
```

* Should resolve to the ALB IPs.

### 8.2 TLS & Cert

```bash
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer
```

* Subject should show `CN=*.example.com`
* Issuer should be Amazon

### 8.3 HTTP Flow

* Open `http://app.example.com`:

  * Should redirect to `https://app.example.com`
* Open `https://app.example.com` (Incognito):

  * Should redirect to Microsoft login (Entra)
  * After login (if assigned) → Streamlit app
  * If not assigned → error from Microsoft (“no access to this application”), no backend access

### 8.4 EC2 App

On the instance:

```bash
sudo systemctl status streamlit-app
journalctl -u streamlit-app -n 50
```

In Target Group -> Targets:

* Instances should be `healthy`

---

If you ever change the domain, port, or IdP, you can reuse this as a checklist and just swap out the values. If you want, I can also turn this into a shorter “one-page cheat sheet” version.
