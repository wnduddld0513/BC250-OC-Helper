#!/bin/bash

echo "========================================================="
echo " BC-250 OC Helper 및 Core Governor 설치를 시작합니다... "
echo "========================================================="

# 실제 명령을 내린 유저 확인 (AUR 헬퍼는 root로 실행 불가)
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"

# AUR 헬퍼 감지 함수
get_aur_helper() {
    if command -v paru >/dev/null 2>&1; then echo "paru"
    elif command -v yay >/dev/null 2>&1; then echo "yay"
    elif command -v shelly >/dev/null 2>&1; then echo "shelly"
    else return 1; fi
}

# 1. 필수 시스템 패키지 설치
echo -e "\n[1/7] 필수 시스템 패키지 및 파이썬 모듈을 설치합니다."
sudo pacman -S --needed python python-pip python-pillow curl git python-pipx stress --noconfirm
sudo python -m pip install customtkinter --break-system-packages

# 2. CPU 가버너 설치 (bc250-collective/bc250_smu_oc)
echo -e "\n[2/7] CPU 가버너 설치 여부를 확인합니다."
# 툴킷 설치, 수동 pipx 설치, 수동 전역 설치를 모두 감지
if systemctl list-unit-files | grep -q 'bc250-smu-oc.service' || command -v bc250-apply &>/dev/null || sudo pipx list 2>/dev/null | grep -q 'bc250-smu-oc'; then
    echo "  -> ✔ 이미 설치되어 있습니다 (건너뜀)."
else
    echo "  -> ⚠ CPU 가버너가 없습니다. GitHub 원본에서 설치를 진행합니다..."
    cd /tmp
    rm -rf bc250_smu_oc
    git clone https://github.com/bc250-collective/bc250_smu_oc.git
    cd bc250_smu_oc
    sudo pipx install .
    sudo pipx ensurepath || true
    
    # GUI 툴에서 절대 경로 없이 접근할 수 있도록 공용 경로에 링크 생성
    sudo ln -sf /root/.local/bin/bc250-detect /usr/local/bin/bc250-detect
    sudo ln -sf /root/.local/bin/bc250-apply /usr/local/bin/bc250-apply
    
    export PATH="$PATH:/usr/local/bin:/root/.local/bin"
    # GitHub README 가이드라인에 따른 초기 3.5GHz 안전값 세팅 및 서비스 등록
    sudo bc250-detect --frequency 3500 --vid 1000 --keep
    sudo bc250-apply --install overclock.conf
    sudo systemctl enable bc250-smu-oc
    echo "  -> ✔ CPU 가버너 설치 및 서비스 등록 완료."
fi

# 3. GPU 가버너 설치 (filippor/cyan-skillfish-governor)
echo -e "\n[3/7] GPU 가버너 설치 여부를 확인합니다."
# AUR 설치, Cargo 소스 빌드 수동 설치 여부 모두 감지
if systemctl list-unit-files | grep -q 'cyan-skillfish-governor-smu.service' || command -v cyan-skillfish-governor-smu &>/dev/null; then
    echo "  -> ✔ 이미 설치되어 있습니다 (건너뜀)."
else
    echo "  -> ⚠ GPU 가버너가 없습니다. 설치를 진행합니다..."
    AUR_HELPER=$(get_aur_helper)
    if [ -z "$AUR_HELPER" ]; then
        echo "  -> ✘ [오류] paru, yay 등의 AUR 헬퍼가 설치되어 있지 않아 자동 설치를 진행할 수 없습니다."
        echo "  -> 수동으로 소스(cargo)를 빌드하거나 AUR 헬퍼를 설치해 주세요."
    else
        echo "  -> $AUR_HELPER 헬퍼를 사용하여 공식 패키지를 빌드/설치합니다..."
        sudo -u "$REAL_USER" $AUR_HELPER -S --noconfirm cyan-skillfish-governor-smu
        sudo systemctl enable --now cyan-skillfish-governor-smu.service
        echo "  -> ✔ GPU 가버너 설치 및 서비스 시작 완료."
    fi
fi

# 4. 프로그램 폴더 생성
echo -e "\n[4/7] GUI 툴 프로그램 폴더를 생성합니다."
sudo mkdir -p /opt/oci/bc250-oc-helper

# 5. 파이썬 스크립트 복사 또는 원격 다운로드
echo -e "\n[5/7] 최신 버전의 OC Helper 툴을 다운로드합니다."
if [ -f "./bc250-oc-helper.py" ]; then
    sudo cp ./bc250-oc-helper.py /opt/oci/bc250-oc-helper/bc250-oc-helper.py
else
    sudo curl -sSL -o /opt/oci/bc250-oc-helper/bc250-oc-helper.py https://raw.githubusercontent.com/wnduddld0513/BC-250-OC-Helper/main/bc250-oc-helper.py
fi
sudo chmod +x /opt/oci/bc250-oc-helper/bc250-oc-helper.py

# 6. G-Helper 스타일 전용 고해상도 아이콘 생성
echo -e "\n[6/7] 전용 바로가기 아이콘을 생성합니다."
sudo python -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (512, 512), (0,0,0,0))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 492, 492], fill='#3daee9')
try:
    draw.text((256, 240), 'B', fill='#ffffff', font_size=280, anchor='mm')
except Exception:
    pass
img.save('/opt/oci/bc250-oc-helper/icon.png')
"

# 7. 시스템 유틸리티 메뉴 등록
echo -e "\n[7/7] 시스템 메뉴에 앱을 등록합니다."
sudo cat <<EOF > /usr/share/applications/bc250-oc-helper.desktop
[Desktop Entry]
Type=Application
Name=BC-250 OC Helper
Comment=simple gui bc-250 overclock tool
Exec=sudo python /opt/oci/bc250-oc-helper/bc250-oc-helper.py
Icon=/opt/oci/bc250-oc-helper/icon.png
Terminal=true
Categories=Utility;System;
EOF

echo "========================================================="
echo " 설치가 모두 완료되었습니다!"
echo " 작업 표시줄의 시스템 유틸리티 메뉴에서 'BC-250 OC Helper'를 실행하세요."
echo "========================================================="
