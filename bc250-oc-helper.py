import sys
import os
import subprocess
import re
import tkinter as tk
import customtkinter as ctk

if os.geteuid() != 0:
    print("This program requires sudo privileges.")
    sys.exit(1)

# 설정 파일 경로
CONFIG_FILE = "/opt/bc250-oc-helper/config.txt"
ICON_FILE = "/opt/bc250-oc-helper/icon.png"

# Gemini 폰트 느낌 산세리프 정의
# (시스템 폰트 중에서 가장 유사한 것을 사용하여 Gemini 느낌을 극대화합니다.)
GEMINI_FONT_FAMILY = "sans-serif" # 리눅스 시스템에서 가장 유사한 산세리프 유도

LANG = {
    "English": {
        "cpu_control": "CPU CONTROL",
        "gpu_control": "GPU CONTROL",
        "max_temp": "Max Temp",
        "target_clk": "Target Clock",
        "target_vol": "Target Volt",
        "find_vol": "Find Volt",
        "apply": "Apply",
        "throttling": "Throttling",
        "recovery": "Recovery",
        "clk_mhz": "Clock (MHz)",
        "vol_mv": "Volt (mV)",
        "reboot": "Reboot"
    },
    "Korean": {
        "cpu_control": "CPU 제어",
        "gpu_control": "GPU 제어",
        "max_temp": "최대 온도",
        "target_clk": "목표 클럭",
        "target_vol": "목표 전압",
        "find_vol": "전압 찾기",
        "apply": "적용",
        "throttling": "Throttling",
        "recovery": "Recovery",
        "clk_mhz": "클럭 (MHz)",
        "vol_mv": "전압 (mV)",
        "reboot": "재부팅"
    }
}

class OCApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BC-250 OC Helper")
        self.geometry("460x700") # 둥근 디자인에 맞춰 크기 보정
        self.minsize(440, 640)
        
        # 윈도우 프로그램 아이콘(좌측 상단) 적용
        try:
            if os.path.exists(ICON_FILE):
                icon_img = tk.PhotoImage(file=ICON_FILE)
                self.iconphoto(False, icon_img)
        except Exception:
            pass
        
        self.gpu_safe_points = []
        self.config_toml_path = "/etc/cyan-skillfish-governor-smu/config.toml"
        self.overclock_conf_path = "/opt/bc250-oc-helper/overclock.conf"
        
        self.settings = {"lang": "English", "theme": "Dark"}
        self.load_settings()
        
        ctk.set_appearance_mode(self.settings["theme"])
        ctk.set_default_color_theme("blue")
        
        self.create_menu()
        self.create_widgets()
        
        # 초기 테마/언어 색상 및 텍스트 적용
        self.change_theme(self.settings["theme"])
        self.change_lang(self.settings["lang"])
        
        self.load_cpu_config()
        self.load_gpu_config()

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    for line in f:
                        if line.startswith("Language="):
                            self.settings["lang"] = line.strip().split("=")[1]
                        elif line.startswith("Theme="):
                            self.settings["theme"] = line.strip().split("=")[1]
        except Exception:
            pass

    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                f.write(f"Language={self.settings['lang']}\n")
                f.write(f"Theme={self.settings['theme']}\n")
        except Exception:
            pass

    def create_menu(self):
        # 상단바: 완전히 둥근 Gemini 스타일
        self.menu_frame = ctk.CTkFrame(self, height=50, corner_radius=25, fg_color=("gray85", "gray17"))
        self.menu_frame.pack(side="top", fill="x", padx=20, pady=(15, 10))
        
        self.lang_menu = ctk.CTkOptionMenu(self.menu_frame, values=["English", "Korean"], width=130, corner_radius=25, command=self.change_lang, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lang_menu.set(self.settings["lang"])
        self.lang_menu.pack(side="left", padx=15, pady=10)
        
        self.theme_menu = ctk.CTkOptionMenu(self.menu_frame, values=["Dark", "Light"], width=130, corner_radius=25, command=self.change_theme, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.theme_menu.set(self.settings["theme"])
        self.theme_menu.pack(side="left", padx=5, pady=10)

    def change_theme(self, new_theme):
        self.settings["theme"] = new_theme
        self.save_settings()
        ctk.set_appearance_mode(new_theme)
        
        # [오류 해결 로직]
        # Gemini 색상 체계 업데이트: 다크모드일 때 배경 `#1e1f20`, 버튼 `#2a2c2d`. 라이트모드일 때 배경 `#f0f4f9`, 버튼 `#e3e3e3`.
        if new_theme == "Dark":
            bg_color = "#1e1f20"
            btn_color = "#2a2c2d"
            btn_hover_color = "#333333"
            text_color = "#e3e3e3"
            slider_color = "#8ab4f8"
            self.configure(fg_color=bg_color)
            self.menu_frame.configure(fg_color=("gray85", "gray17"))
        else:
            bg_color = "#f0f4f9"
            btn_color = "#e3e3e3"
            btn_hover_color = "#cccccc"
            text_color = "#1e1f20"
            slider_color = "#1a73e8"
            self.configure(fg_color=bg_color)
            self.menu_frame.configure(fg_color=("gray85", "gray17"))
            
        self.lang_menu.configure(fg_color=btn_color, button_color=btn_color, button_hover_color=btn_hover_color, text_color=text_color)
        self.theme_menu.configure(fg_color=btn_color, button_color=btn_color, button_hover_color=btn_hover_color, text_color=text_color)

    def change_lang(self, lang_name):
        self.settings["lang"] = lang_name
        self.save_settings()
        t = LANG[lang_name]
        
        self.cpu_label.configure(text=t["cpu_control"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"))
        self.gpu_label.configure(text=t["gpu_control"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"))
        self.lbl_max_temp.configure(text=t["max_temp"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_target_clk.configure(text=t["target_clk"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_target_vol.configure(text=t["target_vol"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        
        self.btn_find_vol.configure(text=t["find_vol"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"))
        self.btn_apply_cpu.configure(text=t["apply"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"))
        self.btn_apply_gpu.configure(text=t["apply"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"))
        self.btn_reboot.configure(text=t["reboot"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"))
        
        self.lbl_throttling.configure(text=t["throttling"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_recovery.configure(text=t["recovery"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_clk_head.configure(text=t["clk_mhz"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.lbl_vol_head.configure(text=t["vol_mv"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))

    def create_widgets(self):
        # 메인 래퍼
        main_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        main_wrapper.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        # --- CPU 영역 ---
        # Gemini 카드 스타일: 둥근 모서리
        cpu_card = ctk.CTkFrame(main_wrapper, corner_radius=20, fg_color=("gray95", "gray13"))
        cpu_card.pack(side="top", fill="x", pady=(0, 15))
        
        self.cpu_label = ctk.CTkLabel(cpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"))
        self.cpu_label.pack(anchor="w", padx=20, pady=(15, 5))
        
        cpu_grid = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_grid.pack(fill="x", padx=20, pady=5)
        cpu_grid.columnconfigure(3, weight=1)

        # Gemini 스타일 입력창: 둥근 모서리
        self.lbl_max_temp = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_max_temp.grid(row=0, column=0, sticky="w", pady=8)
        self.cpu_temp_var = ctk.StringVar(value="90")
        self.cpu_temp_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_temp_var, width=70, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.cpu_temp_entry.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(cpu_grid, text="°C", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=0, column=2, sticky="w", pady=8)

        self.lbl_target_clk = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_clk.grid(row=1, column=0, sticky="w", pady=8)
        self.cpu_clk_var = ctk.StringVar(value="4000")
        self.cpu_clk_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_clk_var, width=70, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.cpu_clk_entry.grid(row=1, column=1, padx=10, pady=8)
        ctk.CTkLabel(cpu_grid, text="MHz", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=1, column=2, sticky="w", pady=8)
        
        # Gemini 스타일 슬라이더
        self.cpu_clk_slider = ctk.CTkSlider(cpu_grid, from_=1000, to=4500, corner_radius=15, command=self.on_cpu_clk_slider_move)
        self.cpu_clk_slider.grid(row=1, column=3, sticky="ew", padx=15, pady=8)

        self.lbl_target_vol = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_vol.grid(row=2, column=0, sticky="w", pady=8)
        self.cpu_vol_var = ctk.StringVar(value="1.250")
        self.cpu_vol_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_vol_var, width=70, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.cpu_vol_entry.grid(row=2, column=1, padx=10, pady=8)
        ctk.CTkLabel(cpu_grid, text="V", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=2, column=2, sticky="w", pady=8)
        
        self.cpu_vol_slider = ctk.CTkSlider(cpu_grid, from_=0.800, to=1.325, corner_radius=15, command=self.on_cpu_slider_move)
        self.cpu_vol_slider.grid(row=2, column=3, sticky="ew", padx=15, pady=8)

        # Gemini 스타일 버튼: 완전히 둥근 모서리
        cpu_btn_frame = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_btn_frame.pack(fill="x", padx=20, pady=(5, 15))
        self.btn_apply_cpu = ctk.CTkButton(cpu_btn_frame, width=100, corner_radius=25, fg_color=None) # [오류 해결 로직] 재미나이 스타일 회색 버튼
        self.btn_apply_cpu.pack(side="right", padx=(10, 0))
        self.btn_find_vol = ctk.CTkButton(cpu_btn_frame, width=110, corner_radius=25, fg_color=("gray90", "gray17"), hover_color=("gray85", "gray19"))
        self.btn_find_vol.pack(side="right", padx=(0, 0))
        
        # 버튼 커맨드 연결
        self.btn_apply_cpu.configure(command=self.apply_cpu_oc)
        self.btn_find_vol.configure(command=self.run_cpu_detect)

        # --- GPU 영역 ---
        self.gpu_card = ctk.CTkFrame(main_wrapper, corner_radius=20, fg_color=("gray95", "gray13"))
        self.gpu_card.pack(side="top", fill="both", expand=True)
        
        self.gpu_label = ctk.CTkLabel(self.gpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"))
        self.gpu_label.pack(anchor="w", padx=20, pady=(15, 5))
        
        temp_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        temp_frame.pack(side="top", fill="x", padx=20, pady=5)
        
        self.lbl_throttling = ctk.CTkLabel(temp_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_throttling.grid(row=0, column=0, sticky="w", pady=5)
        self.gpu_throt_var = ctk.StringVar(value="90")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_throt_var, width=65, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=0, column=1, padx=10, pady=5)
        ctk.CTkLabel(temp_frame, text="°C", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=0, column=2, sticky="w", pady=5)
        
        self.lbl_recovery = ctk.CTkLabel(temp_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_recovery.grid(row=1, column=0, sticky="w", pady=5)
        self.gpu_recov_var = ctk.StringVar(value="85")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_recov_var, width=65, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=1, column=1, padx=10, pady=5)
        ctk.CTkLabel(temp_frame, text="°C", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=1, column=2, sticky="w", pady=5)

        list_label_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        list_label_frame.pack(side="top", fill="x", padx=20, pady=(10, 0))
        list_label_frame.columnconfigure(0, minsize=115)
        list_label_frame.columnconfigure(1, minsize=115)
        
        self.lbl_clk_head = ctk.CTkLabel(list_label_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.lbl_clk_head.grid(row=0, column=0, sticky="w", padx=5)
        self.lbl_vol_head = ctk.CTkLabel(list_label_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.lbl_vol_head.grid(row=0, column=1, sticky="w", padx=5)

        scroll_frame = ctk.CTkScrollableFrame(self.gpu_card, fg_color="transparent", corner_radius=15)
        scroll_frame.pack(side="top", fill="both", expand=True, padx=15, pady=5)
        scroll_frame.columnconfigure(0, minsize=115)
        scroll_frame.columnconfigure(1, minsize=115)
        self.points_container = scroll_frame

        gpu_btn_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        gpu_btn_frame.pack(side="bottom", fill="x", padx=20, pady=(5, 15))
        self.btn_apply_gpu = ctk.CTkButton(gpu_btn_frame, width=100, corner_radius=25, fg_color=None) # 재미나이 스타일 회색 버튼
        self.btn_apply_gpu.pack(side="right", padx=(10, 0))
        self.btn_reboot = ctk.CTkButton(gpu_btn_frame, width=100, corner_radius=25, fg_color=("#d9534f", "#c9302c"), hover_color=("#c9302c", "#a01e1e")) # 재부팅/삭제는 Gemini 빨간색
        self.btn_reboot.pack(side="right", padx=(0, 0))

    def on_cpu_clk_slider_move(self, val):
        self.cpu_clk_var.set(str(int(val)))

    def on_cpu_slider_move(self, val):
        self.cpu_vol_var.set(f"{val:.3f}")

    def load_cpu_config(self):
        if os.path.exists(self.overclock_conf_path):
            with open(self.overclock_conf_path, "r") as f:
                content = f.read()
                f_match = re.search(r"frequency\s*=\s*(\d+)", content)
                v_match = re.search(r"(?:vid|scale)\s*=\s*(-?\d+)", content)
                t_match = re.search(r"max_temperature\s*=\s*(\d+)", content)
                if f_match:
                    self.cpu_clk_var.set(f_match.group(1))
                    self.cpu_clk_slider.set(int(f_match.group(1)))
                if v_match:
                    raw_val = float(v_match.group(1))
                    if raw_val >= 800:
                        self.cpu_vol_var.set(f"{raw_val / 1000.0:.3f}")
                        self.cpu_vol_slider.set(raw_val / 1000.0)
                if t_match: self.cpu_temp_var.set(t_match.group(1))

    def run_cpu_detect(self):
        try:
            mhz = int(self.cpu_clk_var.get())
            mv = int(float(self.cpu_vol_var.get()) * 1000)
            subprocess.run(["sudo", "/root/.local/bin/bc250-detect", "--frequency", str(mhz), "--vid", str(mv), "--keep", "-c", self.overclock_conf_path], check=True)
            self.load_cpu_config()
        except Exception as e: print(e)

    def apply_cpu_oc(self):
        try:
            mhz = int(self.cpu_clk_var.get())
            mv = int(float(self.cpu_vol_var.get()) * 1000)
            temp = int(self.cpu_temp_var.get())
            
            # [오류 해결 로직]
            # scale 값이 없는 설정 파일이 쓰여지는 것을 방지하기 위해
            # apply 전 강제로 bc250-detect를 돌려 올바른 scale 값을 찾아 overclock.conf를 생성하게 유도함
            detect_cmd = ["sudo", "/root/.local/bin/bc250-detect", "--frequency", str(mhz), "--vid", str(mv), "-t", str(temp), "--keep", "-c", self.overclock_conf_path]
            subprocess.run(detect_cmd, check=True)
            
            # 제대로 생성된 설정 파일로 서비스 재시작
            apply_cmd = ["sudo", "/root/.local/bin/bc250-apply", "--install", self.overclock_conf_path]
            subprocess.run(apply_cmd, check=True)
            
        except Exception as e: print(e)

    def load_gpu_config(self):
        if not os.path.exists(self.config_toml_path): return
        with open(self.config_toml_path, "r") as f: content = f.read()
        throt = re.search(r"throttling\s*=\s*(\d+)", content)
        recov = re.search(r"throttling_recovery\s*=\s*(\d+)", content)
        if throt: self.gpu_throt_var.set(throt.group(1))
        if recov: self.gpu_recov_var.set(recov.group(1))
        matches = re.findall(r"\[\[safe-points\]\]\s*frequency\s*=\s*(\d+)\s*voltage\s*=\s*(\d+)", content)
        for clk, vol in matches: self.gpu_safe_points.append({"frequency": clk, "voltage": vol})
        self.render_gpu_rows()

    def render_gpu_rows(self):
        for widget in self.points_container.winfo_children(): widget.destroy()
        for i, pt in enumerate(self.gpu_safe_points):
            f_entry = ctk.CTkEntry(self.points_container, width=80, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=11))
            f_entry.insert(0, pt["frequency"])
            f_entry.grid(row=i, column=0, padx=5, pady=3, sticky="w")
            f_entry.bind("<FocusOut>", lambda e, idx=i, entry=f_entry: self.update_gpu_val(idx, "frequency", entry.get()))
            
            v_entry = ctk.CTkEntry(self.points_container, width=80, corner_radius=10, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=11))
            v_entry.insert(0, pt["voltage"])
            v_entry.grid(row=i, column=1, padx=5, pady=3, sticky="w")
            v_entry.bind("<FocusOut>", lambda e, idx=i, entry=v_entry: self.update_gpu_val(idx, "voltage", entry.get()))
            
            # [오류 해결 로직] Gemini 스타일 완전히 둥근 원형 +/- 버튼
            btn_frame = ctk.CTkFrame(self.points_container, fg_color="transparent")
            btn_frame.grid(row=i, column=2, padx=2, pady=3, sticky="w")
            ctk.CTkButton(btn_frame, text="+", width=34, height=34, corner_radius=17, fg_color=None, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"), command=lambda idx=i: self.add_gpu_row(idx)).pack(side="left", padx=3)
            
            # 마이너스 버튼도 동일하게 완전히 둥글고 회색으로 변경 (삭제가 아닌 행 제거)
            ctk.CTkButton(btn_frame, text="−", width=34, height=34, corner_radius=17, fg_color=None, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"), command=lambda idx=i: self.remove_gpu_row(idx)).pack(side="left", padx=3)

    def update_gpu_val(self, idx, key, val): self.gpu_safe_points[idx][key] = val

    def add_gpu_row(self, idx):
        base_pt = self.gpu_safe_points[idx]
        self.gpu_safe_points.insert(idx + 1, {"frequency": str(int(base_pt["frequency"])+100), "voltage": str(int(base_pt["voltage"])+25)})
        self.render_gpu_rows()

    def remove_gpu_row(self, idx):
        if len(self.gpu_safe_points) <= 1: return
        del self.gpu_safe_points[idx]
        self.render_gpu_rows()

    def apply_gpu_config(self):
        try:
            freqs = [int(pt["frequency"]) for pt in self.gpu_safe_points if pt["frequency"].isdigit()]
            # GPU 가버너 최신 버전에 필요한 TOML 헤더 속성 추가
            toml = [
                "[gpu]",
                'set-method = "smu"',
                "[frequency-range]",
                f"min = {min(freqs)}",
                f"max = {max(freqs)}",
                "[timing.ramp-rates]",
                "normal = 1",
                "burst = 50",
                "[timing]",
                "burst-samples = 60",
                "down-events = 5",
                "[frequency-thresholds]",
                "adjust = 10",
                "[load-target]",
                "upper = 0.65",
                "lower = 0.50",
                "[temperature]",
                f"throttling = {self.gpu_throt_var.get()}",
                f"throttling_recovery = {self.gpu_recov_var.get()}"
            ]
            for pt in self.gpu_safe_points: 
                toml.append(f"[[safe-points]]\nfrequency = {pt['frequency']}\nvoltage = {pt['voltage']}")
                
            with open(self.config_toml_path, "w") as f: 
                f.write("\n".join(toml) + "\n")
            subprocess.run(["sudo", "systemctl", "restart", "cyan-skillfish-governor-smu"], check=True)
        except Exception as e: print(e)

    def reboot_system(self): subprocess.run(["sudo", "reboot"])

if __name__ == "__main__":
    app = OCApp()
    app.mainloop()
