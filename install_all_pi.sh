#!/usr/bin/env bash
set -euo pipefail

# Directory where this script itself lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# in case internet is crappy
export POETRY_HTTP_TIMEOUT=30        # default is 15s, make it 2 minutes
export POETRY_HTTP_RETRIES=5         # more retries for Poetry's own downloads

export PIP_DEFAULT_TIMEOUT=120        # pip’s own timeout
export PIP_RETRIES=10                 # pip’s extra retries
export PIP_TIMEOUT=120                # some tools look at this name, too


run_install() {
    local script_path="$1"

    # Resolve to absolute path
    local full_path="$SCRIPT_DIR/$script_path"
    if [[ ! -f "$full_path" ]]; then
        echo "❌ Script not found: $full_path" >&2
        return 1
    fi

    local dir
    local file
    dir="$(dirname "$full_path")"
    file="$(basename "$full_path")"

    echo "========================================"
    echo "▶ Running installer: $full_path"
    echo "========================================"

    (
        cd "$dir"
        chmod +x "$file"
        "./$file"
    )

    echo "✅ Finished: $full_path"
    echo
}

# --- List your installers here, in order ---
run_install "install_env.sh"
run_install "install_sd_card_reader.sh"
run_install "pi-s3-sync/install.sh"
run_install "s3_image_croper_ui_app/install_settings.sh"
# this step needs confirmation all prior steps were successfull
#run_install "eInkFrameWithStreamlitMananger/setup.sh"   # <--- add this
