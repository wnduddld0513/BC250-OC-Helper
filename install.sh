#!/usr/bin/env bash
set -euo pipefail

echo "========================================================="
echo " Starting BC-250 OC Helper installation..."
echo "========================================================="

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
REAL_HOME="$(eval echo "~${REAL_USER}")"

APP_DIR="/opt/bc250-oc-helper"
APP_FILE="${APP_DIR}/bc250-oc-helper.py"
ICON_FILE="${APP_DIR}/icon.png"
DESKTOP_FILE="/usr/share/applications/bc250-oc-helper.desktop"
SUDOERS_FILE="/etc/sudoers.d/bc250-oc-helper"

HELPER_URL="https://raw.githubusercontent.com/wnduddld0513/BC250-OC-Helper/main/bc250-oc-helper.py"

get_aur_helper() {
    if command -v paru >/dev/null 2>&1; then echo "paru"
    elif command -v yay >/dev/null 2>&1; then echo "yay"
    elif command -v shelly >/dev/null 2>&1; then echo "shelly"
    else return 1
    fi
}

echo ""
echo "[1/9] Installing required packages..."
sudo pacman -S --needed --noconfirm python python-pip python-pillow curl git python-pipx stress

echo ""
echo "[2/9] Installing customtkinter..."
sudo python -m pip install --break-system-packages customtkinter

echo ""
echo "[3/9] Checking CPU governor (bc250_smu_oc)..."
if systemctl list-unit-files | grep -q '^bc250-smu-oc\.service' || command -v bc250-apply >/dev/null 2>&1; then
    echo "  -> CPU governor already installed. Skipping."
else
    echo "  -> CPU governor not found. Installing from GitHub..."
    cd /tmp
    rm -rf bc250_smu_oc
    git clone https://github.com/bc250-collective/bc250_smu_oc.git
    cd bc250_smu_oc

    sudo pipx install .
    sudo pipx ensurepath || true

    BC250_DETECT_BIN="$(sudo find /root/.local/bin /usr/local/bin /usr/bin -maxdepth 1 -type f -name bc250-detect 2>/dev/null | head -n1 || true)"
    BC250_APPLY_BIN="$(sudo find /root/.local/bin /usr/local/bin /usr/bin -maxdepth 1 -type f -name bc250-apply 2>/dev/null | head -n1 || true)"

    if [[ -z "${BC250_DETECT_BIN}" || -z "${BC250_APPLY_BIN}" ]]; then
        echo "  -> ERROR: bc250-detect or bc250-apply not found after install."
        exit 1
    fi

    sudo ln -sf "${BC250_DETECT_BIN}" /usr/local/bin/bc250-detect
    sudo ln -sf "${BC250_APPLY_BIN}" /usr/local/bin/bc250-apply

    export PATH="$PATH:/usr/local/bin:/root/.local/bin"
    sudo bc250-detect --frequency 3500 --vid 1000 --keep
    sudo bc250-apply --install overclock.conf
    sudo systemctl enable bc250-smu-oc

    echo "  -> CPU governor installed and service enabled."
fi

echo ""
echo "[4/9] Checking GPU governor (cyan-skillfish-governor-smu)..."
if systemctl list-unit-files | grep -q '^cyan-skillfish-governor-smu\.service' || command -v cyan-skillfish-governor-smu >/dev/null 2>&1; then
    echo "  -> GPU governor already installed. Skipping."
else
    echo "  -> GPU governor not found. Installing..."
    AUR_HELPER="$(get_aur_helper || true)"
    if [[ -z "${AUR_HELPER}" ]]; then
        echo "  -> ERROR: No AUR helper found (paru/yay/shelly)."
        echo "  -> Please install an AUR helper or build manually."
        exit 1
    fi
    echo "  -> Using ${AUR_HELPER}..."
    sudo -u "${REAL_USER}" "${AUR_HELPER}" -S --noconfirm cyan-skillfish-governor-smu
    sudo systemctl enable --now cyan-skillfish-governor-smu.service
    echo "  -> GPU governor installed and started."
fi

echo ""
echo "[5/9] Creating application directory..."
sudo mkdir -p "${APP_DIR}"

echo ""
echo "[6/9] Downloading BC-250 OC Helper from GitHub..."
sudo curl -sSL -o "${APP_FILE}" "${HELPER_URL}"
sudo chmod +x "${APP_FILE}"

echo ""
echo "[7/9] Creating icon..."
sudo python - <<'PY'
from PIL import Image, ImageDraw
img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 492, 492], fill="#3daee9")
draw.text((256, 256), "B", fill="#ffffff", anchor="mm")
img.save("/opt/bc250-oc-helper/icon.png")
PY

echo ""
echo "[8/9] Registering desktop entry..."
sudo tee "${DESKTOP_FILE}" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Name=BC-250 OC Helper
Comment=BC-250 CPU/GPU overclock helper
Exec=python3 ${APP_FILE}
Icon=${ICON_FILE}
Terminal=false
Categories=Utility;System;
EOF
sudo chmod 644 "${DESKTOP_FILE}"

DESKTOP_DIR="$(sudo -u "${REAL_USER}" xdg-user-dir DESKTOP 2>/dev/null || true)"
if [[ -z "${DESKTOP_DIR}" ]]; then
    DESKTOP_DIR="${REAL_HOME}/Desktop"
fi

if [[ -d "${DESKTOP_DIR}" ]]; then
    sudo cp "${DESKTOP_FILE}" "${DESKTOP_DIR}/"
    sudo chown "${REAL_USER}:${REAL_USER}" "${DESKTOP_DIR}/bc250-oc-helper.desktop"
    sudo chmod +x "${DESKTOP_DIR}/bc250-oc-helper.desktop"
    echo "  -> Desktop shortcut created at: ${DESKTOP_DIR}"
else
    echo "  -> Desktop directory not found. Skipping desktop shortcut copy."
fi

echo ""
echo "[9/9] Configuring sudoers for passwordless helper commands..."
sudo tee "${SUDOERS_FILE}" >/dev/null <<EOF
${REAL_USER} ALL=(root) NOPASSWD: /usr/local/bin/bc250-detect
${REAL_USER} ALL=(root) NOPASSWD: /usr/local/bin/bc250-apply
${REAL_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl restart bc250-smu-oc
${REAL_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl restart cyan-skillfish-governor-smu
${REAL_USER} ALL=(root) NOPASSWD: /usr/bin/cp
${REAL_USER} ALL=(root) NOPASSWD: /usr/bin/reboot
EOF
sudo chmod 440 "${SUDOERS_FILE}"
sudo visudo -cf "${SUDOERS_FILE}" >/dev/null

echo ""
echo "========================================================="
echo " Installation completed."
echo " Run from app menu: BC-250 OC Helper"
echo "========================================================="
