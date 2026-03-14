#!/usr/bin/env bash
set -e
# Load S3_BUCKET and REGION from the root .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_ENV="${SCRIPT_DIR}/../.env"
if [ -f "$ROOT_ENV" ]; then
  set -a; source "$ROOT_ENV"; set +a
else
  echo "ERROR: .env not found at $ROOT_ENV"
  echo "Copy .env.example to .env and fill in your values first."
  exit 1
fi
echo "export S3_BUCKET=\"${S3_BUCKET}\"" >> "$HOME/.bashrc"
echo "export REGION=\"${AWS_DEFAULT_REGION:-eu-central-1}\"" >> "$HOME/.bashrc"
# 1) System packages (need sudo)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv curl awscli

# 2) Install Poetry for *pi* user (NO sudo here!)
curl -sSL https://install.python-poetry.org | python3 -

# 3) Add Poetry to PATH if not already there
if ! grep -q 'HOME/.local/bin' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

# Make sure PATH is available in this script run too
export PATH="$HOME/.local/bin:$PATH"

echo "==> Installing ImageUiApp with Poetry"
# Figure out where the script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/ImageUiApp"

# If you went with Option A (no package):
# poetry install --no-root
# OR if you set package-mode = false, just:
# poetry install

# If you went with Option B (proper package + CLI):
poetry install

# Figure out where the script lives
cd "$SCRIPT_DIR/SettingsApp"

# If you went with Option A (no package):
# poetry install --no-root
# OR if you set package-mode = false, just:
# poetry install

# If you went with Option B (proper package + CLI):
poetry install

echo "Installation done. Open a *new* terminal or run:"
echo "  source ~/.bashrc"
echo "then test with: poetry --version"
echo "please run aws configure now"
