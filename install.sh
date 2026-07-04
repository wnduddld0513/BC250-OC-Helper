#!/bin/bash

echo "========================================================="
echo " Starting BC-250 OC Helper installation..."
echo "========================================================="

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
REAL_HOME="$(eval echo "~${REAL_USER}")"

get_aur_helper() {
    if command -v paru >/dev/null 2>&1; then echo "paru"
    elif command -v yay >/dev/null 2>&1; then echo "yay"
    elif command -v shelly >/dev/null 2>&1; then echo "shelly"
    else return 1; fi
}

# 1. System packages
echo -e "\n[1/9] Checking required system packages..."
sudo pacman -S --needed --noconfirm python python-pip python-pillow curl git python-pipx stress

# 2. Python library
echo -e "\n[2/9] Checking Python module installation..."
if python3 -c "import customtkinter" &>/dev/null; then
    echo "  -> ✔ customtkinter is already installed (Skipped)."
else
    echo "  -> ⚠ Installing customtkinter..."
    sudo python3 -m pip install customtkinter --break-system-packages
fi

# 3. CPU Governor
echo -e "\n[3/9] Checking CPU governor installation..."
if systemctl list-unit-files | grep -q 'bc250-smu-oc.service' || command -v bc250-apply &>/dev/null || sudo pipx list 2>/dev/null | grep -q 'bc250-smu-oc'; then
    echo "  -> ✔ Already installed (Skipped)."
else
    echo "  -> ⚠ CPU governor not found. Installing from GitHub..."
    cd /tmp
    rm -rf bc250_smu_oc
    git clone https://github.com/bc250-collective/bc250_smu_oc.git
    cd bc250_smu_oc
    sudo pipx install .
    sudo pipx ensurepath || true
    
    sudo ln -sf /root/.local/bin/bc250-detect /usr/local/bin/bc250-detect
    sudo ln -sf /root/.local/bin/bc250-apply /usr/local/bin/bc250-apply
    
    export PATH="$PATH:/usr/local/bin:/root/.local/bin"
    sudo bc250-detect --frequency 3500 --vid 1000 --keep
    sudo bc250-apply --install overclock.conf
    sudo systemctl enable bc250-smu-oc
    echo "  -> ✔ CPU governor installed and service enabled."
fi

# 4. GPU Governor
echo -e "\n[4/9] Checking GPU governor installation..."
if systemctl list-unit-files | grep -q 'cyan-skillfish-governor-smu.service' || command -v cyan-skillfish-governor-smu &>/dev/null; then
    echo "  -> ✔ Already installed (Skipped)."
else
    echo "  -> ⚠ GPU governor not found. Installing..."
    AUR_HELPER=$(get_aur_helper)
    if [ -z "$AUR_HELPER" ]; then
        echo "  -> ✘ [Error] No AUR helper found. Skipping GPU governor install."
    else
        echo "  -> Using ${AUR_HELPER} to build/install official package..."
        sudo -u "$REAL_USER" $AUR_HELPER -S --noconfirm cyan-skillfish-governor-smu
        sudo systemctl enable --now cyan-skillfish-governor-smu.service
        echo "  -> ✔ GPU governor installed and service started."
    fi
fi

# 5. App Directory
echo -e "\n[5/9] Creating application directory..."
sudo mkdir -p /opt/bc250-oc-helper

# 6. Python script download
echo -e "\n[6/9] Downloading latest OC Helper script..."
if [ -f "./bc250-oc-helper.py" ]; then
    sudo cp ./bc250-oc-helper.py /opt/bc250-oc-helper/bc250-oc-helper.py
else
    sudo curl -sSL -o /opt/bc250-oc-helper/bc250-oc-helper.py https://raw.githubusercontent.com/wnduddld0513/BC250-OC-Helper/main/bc250-oc-helper.py
fi
sudo chmod +x /opt/bc250-oc-helper/bc250-oc-helper.py

# 7. Icon creation
echo -e "\n[7/9] Creating application icon..."
sudo python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (512, 512), (0,0,0,0))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 492, 492], fill='#3daee9')
try:
    draw.text((256, 240), 'B', fill='#ffffff', font_size=280, anchor='mm')
except Exception: pass
img.save('/opt/bc250-oc-helper/icon.png')
"

# 8. Desktop entry
echo -e "\n[8/9] Registering in system menu..."
sudo tee /usr/share/applications/bc250-oc-helper.desktop > /dev/null <<EOF
[Desktop Entry]
Type=Application
Name=BC-250 OC Helper
Comment=simple gui bc-250 overclock tool
Exec=sudo python3 /opt/bc250-oc-helper/bc250-oc-helper.py
Icon=/opt/bc250-oc-helper/icon.png
Terminal=false
Categories=Utility;System;
EOF

# 9. Desktop shortcut
echo -e "\n[9/9] Creating desktop shortcut..."
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "${REAL_HOME}/Desktop")"

if [ -d "$DESKTOP_DIR" ]; then
    sudo cp /usr/share/applications/bc250-oc-helper.desktop "$DESKTOP_DIR/"
    sudo chown $REAL_USER:$REAL_USER "$DESKTOP_DIR/bc250-oc-helper.desktop"
    sudo chmod +x "$DESKTOP_DIR/bc250-oc-helper.desktop"
    echo "  -> ✔ Desktop shortcut created."
else
    echo "  -> ⚠ Desktop directory not found. Skipping shortcut creation."
fi

echo "========================================================="
echo " Installation completed successfully!"
echo " Launch 'BC-250 OC Helper' from your app menu or desktop."
echo "========================================================="
