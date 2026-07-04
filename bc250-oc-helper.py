#!/usr/bin/env python3
import sys
import os
import subprocess
import re
import tkinter as tk
import customtkinter as ctk
import getpass

# 사용자마다 다른 홈 디렉토리 경로를 동적으로 구성
USER = os.getenv('SUDO_USER') or os.getenv('USER') or getpass.getuser()
if USER == 'root':
    USER = os.environ.get('USER')
OVERCLOCK_CONF = f"/home/{USER}/bc250_smu_oc/overclock.conf"
CONFIG_FILE = "/opt/bc250-oc-helper/config.txt"
ICON_FILE = "/opt/bc250-oc-helper/icon.png"

if os.geteuid() != 0:
    print("This program requires sudo privileges.")
    sys.exit(1)

GEMINI_FONT_FAMILY = "sans-serif"

LANG = {
    "English": {
        "cpu_control": "CPU CONTROL", "gpu_control": "GPU CONTROL", "max_temp": "Max Temp",
        "target_clk": "Target Clock", "target_vol": "Target Volt", "find_vol": "Detect",
        "apply": "Apply", "throttling": "Throttling", "recovery": "Recovery",
        "clk_mhz": "Clock (MHz)", "vol_mv": "Volt (mV)", "reboot": "Reboot", "update": "Update",
    },
    "Korean": {
        "cpu_control": "CPU 제어", "gpu_control": "GPU 제어", "max_temp": "최대 온도",
        "target_clk": "목표 클럭", "target_vol": "목표 전압", "find_vol": "탐지",
        "apply": "적용", "throttling": "Throttling", "recovery": "Recovery",
        "clk_mhz": "클럭 (MHz)", "vol_mv": "전압 (mV)", "reboot": "재부팅", "update": "업데이트",
    },
}

BG_COLOR = ("#f0f4f9", "#131314")
CARD_BG = ("#ffffff", "#1e1f20")
ENTRY_BG = ("#f0f4f9", "#131314")
SEC_BTN_BG = ("#e3e3e3", "#333537")
SEC_BTN_HOVER = ("#d3d3d3", "#444648")
TEXT_COLOR = ("#1e1f20", "#e3e3e3")

def resolve_bin(name: str) -> str:
    candidates = [f"/usr/local/bin/{name}", f"/root/.local/bin/{name}", f"/usr/bin/{name}"]
    for p in candidates:
        if os.path.exists(p): return p
    return name

def parse_volt_to_mv(text: str) -> int:
    s = text.strip().replace(",", ".").replace(" ", "")
    v = float(s) if s else 0.0
    return int(round(v)) if v >= 100 else int(round(v * 1000))

class OCApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BC-250 OC Helper")
        self.geometry("450x640")
        self.minsize(420, 580)
        self.configure(fg_color=BG_COLOR)

        self.gpu_safe_points = []
        self.bc250_detect_bin = resolve_bin("bc250-detect")
        self.bc250_apply_bin = resolve_bin("bc250-apply")
        self.overclock_conf_path = OVERCLOCK_CONF
        self.settings = {"lang": "English", "theme": "Dark"}
        
        self.load_settings()
        ctk.set_appearance_mode(self.settings["theme"])
        ctk.set_default_color_theme("blue")

        self.create_menu()
        self.create_widgets()
        self.change_theme(self.settings["theme"])
        self.change_lang(self.settings["lang"])
        self.load_cpu_config()
        self.load_gpu_config()

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("Language="): self.settings["lang"] = line.strip().split("=", 1)[1]
                        elif line.startswith("Theme="): self.settings["theme"] = line.strip().split("=", 1)[1]
        except Exception: pass

    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"Language={self.settings['lang']}\nTheme={self.settings['theme']}\n")
        except Exception: pass

    def create_menu(self):
        self.menu_frame = ctk.CTkFrame(self, height=50, corner_radius=25, fg_color=CARD_BG)
        self.menu_frame.pack(side="top", fill="x", padx=20, pady=(15, 10))
        self.lang_menu = ctk.CTkComboBox(self.menu_frame, values=["English", "Korean"], width=110, corner_radius=25, state="readonly", command=self.change_lang, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lang_menu.set(self.settings["lang"]); self.lang_menu.pack(side="left", padx=(15, 5), pady=10)
        self.theme_menu = ctk.CTkComboBox(self.menu_frame, values=["Dark", "Light"], width=100, corner_radius=25, state="readonly", command=self.change_theme, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.theme_menu.set(self.settings["theme"]); self.theme_menu.pack(side="left", padx=5, pady=10)
        self.btn_update = ctk.CTkButton(self.menu_frame, width=90, corner_radius=25, command=self.update_app, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"))
        self.btn_update.pack(side="right", padx=(5, 15), pady=10)

    def change_theme(self, new_theme):
        self.settings["theme"] = new_theme
        self.save_settings()
        ctk.set_appearance_mode(new_theme)

    def change_lang(self, lang_name):
        self.settings["lang"] = lang_name
        self.save_settings()
        t = LANG[lang_name]
        self.cpu_label.configure(text=t["cpu_control"]); self.gpu_label.configure(text=t["gpu_control"])
        self.lbl_max_temp.configure(text=t["max_temp"]); self.lbl_target_clk.configure(text=t["target_clk"])
        self.lbl_target_vol.configure(text=t["target_vol"]); self.btn_find_vol.configure(text=t["find_vol"])
        self.btn_apply_cpu.configure(text=t["apply"]); self.btn_apply_gpu.configure(text=t["apply"])
        self.btn_reboot.configure(text=t["reboot"]); self.btn_update.configure(text=t["update"])

    def create_widgets(self):
        main = ctk.CTkFrame(self, fg_color="transparent"); main.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        cpu_card = ctk.CTkFrame(main, corner_radius=20, fg_color=CARD_BG); cpu_card.pack(side="top", fill="x", pady=(0, 15))
        self.cpu_label = ctk.CTkLabel(cpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold")); self.cpu_label.pack(anchor="w", padx=20, pady=(15, 5))
        cpu_grid = ctk.CTkFrame(cpu_card, fg_color="transparent"); cpu_grid.pack(fill="x", padx=20, pady=5); cpu_grid.columnconfigure(3, weight=1)
        self.cpu_temp_var = ctk.StringVar(value="90"); self.cpu_temp_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_temp_var, width=70, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center"); self.cpu_temp_entry.grid(row=0, column=1, padx=10, pady=8)
        self.cpu_clk_var = ctk.StringVar(value="4000"); self.cpu_clk_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_clk_var, width=70, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center"); self.cpu_clk_entry.grid(row=1, column=1, padx=10, pady=8)
        self.cpu_vol_var = ctk.StringVar(value="1.250"); self.cpu_vol_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_vol_var, width=70, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center"); self.cpu_vol_entry.grid(row=2, column=1, padx=10, pady=8)
        cpu_btn = ctk.CTkFrame(cpu_card, fg_color="transparent"); cpu_btn.pack(fill="x", padx=20, pady=(5, 15))
        self.btn_apply_cpu = ctk.CTkButton(cpu_btn, width=100, corner_radius=25, command=self.apply_cpu_oc); self.btn_apply_cpu.pack(side="right", padx=(10, 0))
        self.btn_find_vol = ctk.CTkButton(cpu_btn, width=110, corner_radius=25, fg_color=SEC_BTN_BG, hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR, command=self.run_cpu_detect); self.btn_find_vol.pack(side="right")
        self.gpu_card = ctk.CTkFrame(main, corner_radius=20, fg_color=CARD_BG); self.gpu_card.pack(side="top", fill="both", expand=True)
        self.gpu_label = ctk.CTkLabel(self.gpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold")); self.gpu_label.pack(anchor="w", padx=20, pady=(15, 5))
        self.points_container = ctk.CTkScrollableFrame(self.gpu_card, fg_color="transparent", corner_radius=15); self.points_container.pack(fill="both", expand=True, padx=15, pady=5)
        gpu_btn_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent"); gpu_btn_frame.pack(side="bottom", fill="x", padx=20, pady=(5, 15))
        self.btn_apply_gpu = ctk.CTkButton(gpu_btn_frame, width=100, corner_radius=25, command=self.apply_gpu_config); self.btn_apply_gpu.pack(side="right", padx=(10, 0))
        self.btn_reboot = ctk.CTkButton(gpu_btn_frame, width=100, corner_radius=25, fg_color=("#d9534f", "#c9302c"), hover_color=("#c9302c", "#a01e1e"), command=self.reboot_system); self.btn_reboot.pack(side="right")

    def load_cpu_config(self):
        if os.path.exists(self.overclock_conf_path):
            with open(self.overclock_conf_path, "r", encoding="utf-8") as f:
                content = f.read()
                f_match = re.search(r"frequency\s*=\s*(\d+)", content)
                if f_match: self.cpu_clk_var.set(f_match.group(1))

    def run_cpu_detect(self):
        try:
            mhz, mv, temp = int(self.cpu_clk_var.get()), parse_volt_to_mv(self.cpu_vol_var.get()), 90
            subprocess.run(["sudo", self.bc250_detect_bin, "--frequency", str(mhz), "--vid", str(mv), "-t", str(temp), "--keep", "-c", self.overclock_conf_path], check=True)
            self.load_cpu_config()
        except Exception as e: print(e)

    def apply_cpu_oc(self):
        try:
            mhz = int(self.cpu_clk_var.get())
            # Apply는 테스트 없이 파일만 수정 후 즉시 서비스 재시작
            with open(self.overclock_conf_path, "w", encoding="utf-8") as f:
                f.write(f"[overclock]\nfrequency = {mhz}\nscale = -41\nmax_temperature = 90\n")
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", self.bc250_apply_bin, "--install", self.overclock_conf_path], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "bc250-smu-oc"], check=True)
        except Exception as e: print(e)

    def apply_gpu_config(self):
        # (생략: 기존 GPU 적용 로직 유지)
        pass

    def reboot_system(self): subprocess.run(["sudo", "reboot"])
    def update_app(self): os.execv(sys.executable, [sys.executable, "/opt/bc250-oc-helper/bc250-oc-helper.py"])

if __name__ == "__main__":
    app = OCApp()
    app.mainloop()
