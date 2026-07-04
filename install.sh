#!/bash/bin
echo "BC-250 OC Helper 설치를 시작합니다..."

# 1. 필요 패키지 및 파이썬 모듈 설치
sudo pacman -S --needed python python-pip python-pillow --noconfirm
sudo python -m pip install customtkinter --break-system-packages

# 2. 프로그램 경로 디렉토리 생성
sudo mkdir -p /opt/oci/bc250-oc-helper

# 3. 임시로 생성된 파이썬 코드를 설치 폴더로 복사 이동 명령
# (스크립트 실행 디렉토리에 소스가 있다고 가정하거나 다운로드 처리)
sudo cp bc250-oc-helper.py /opt/oci/bc250-oc-helper/bc250-oc-helper.py
sudo chmod +x /opt/oci/bc250-oc-helper/bc250-oc-helper.py

# 4. G-Helper 스타일의 전용 고해상도 아이콘 생성 (파란 원형 바탕 내부 흰색 B 디자인)
sudo python -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGBA', (512, 512), (0,0,0,0))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 492, 492], fill='#3daee9')
draw.text((256, 240), 'B', fill='#ffffff', font_size=280, anchor='mm')
img.save('/opt/oci/bc250-oc-helper/icon.png')
"

# 5. 시스템 유틸리티 칸(데스크톱 메뉴 파트)에 정식 애플리케이션으로 등록
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

echo "설치가 완료되었습니다! 이제 시스템 작업 표시줄 및 유틸리티 메뉴에서 실행할 수 있습니다."
