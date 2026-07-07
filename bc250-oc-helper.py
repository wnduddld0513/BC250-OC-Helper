#!/usr/bin/env python3
import sys
import os
import subprocess
import re
import tkinter as tk
import customtkinter as ctk


if os.geteuid() != 0:
    print("This program requires sudo privileges.")
    sys.exit(1)


CONFIG_FILE = "/opt/bc250-oc-helper/config.txt"
ICON_FILE = "/opt/bc250-oc-helper/icon.png"

GEMINI_FONT_FAMILY = "sans-serif"

LANG = {
    "English": {
        "cpu_control": "CPU CONTROL",
        "gpu_control": "GPU CONTROL",
        "max_temp": "Max Temp",
        "target_clk": "Target Clock",
        "target_vol": "Target Volt",
        "find_vol": "Detect",
        "apply": "Apply",
        "throttling": "Throttling",
        "recovery": "Recovery",
        "clk_mhz": "Clock (MHz)",
        "vol_mv": "Volt (mV)",
        "reboot": "Reboot",
        "update": "Update",
    },
    "Korean": {
        "cpu_control": "CPU 제어",
        "gpu_control": "GPU 제어",
        "max_temp": "최대 온도",
        "target_clk": "목표 클럭",
        "target_vol": "목표 전압",
        "find_vol": "탐지",
        "apply": "적용",
        "throttling": "Throttling",
        "recovery": "Recovery",
        "clk_mhz": "클럭 (MHz)",
        "vol_mv": "전압 (mV)",
        "reboot": "재부팅",
        "update": "업데이트",
    },
}

BG_COLOR = ("#f0f4f9", "#131314")
CARD_BG = ("#ffffff", "#1e1f20")
ENTRY_BG = ("#f0f4f9", "#131314")
SEC_BTN_BG = ("#e3e3e3", "#333537")
SEC_BTN_HOVER = ("#d3d3d3", "#444648")
TEXT_COLOR = ("#1e1f20", "#e3e3e3")


def resolve_bin(name: str) -> str:
    candidates = [
        f"/usr/local/bin/{name}",
        f"/root/.local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return name


def parse_volt_to_mv(text: str) -> int:
    s = text.strip().replace(",", ".").replace(" ", "")
    if not s:
        raise ValueError("Empty voltage value")
    v = float(s)
    if v >= 100:  # 사용자가 mV로 넣은 경우(예: 1250)
        return int(round(v))
    return int(round(v * 1000))


def vid_predict(clock: int, scale: int) -> float:
    if clock < 3000:
        raise ValueError("cannot predict vid for clocks below 3 GHz")
    p = -1.519 + scale * 0.004325
    q = 2800.0 - (scale * 10.0)
    return 0.0003 * clock * clock + p * clock + q


def nearest_scale_for_vid(clock: int, target_mv: int, scale_min: int, scale_max: int, current_scale: int) -> int:
    return min(
        range(scale_min, scale_max + 1),
        key=lambda s: (abs(vid_predict(clock, s) - target_mv), abs(s - current_scale)),
    )


class OCApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BC-250 OC Helper")
        self.geometry("450x640")
        self.minsize(420, 580)

        try:
            if os.path.exists(ICON_FILE):
                icon_img = tk.PhotoImage(file=ICON_FILE)
                self.iconphoto(False, icon_img)
        except Exception:
            pass

        self.gpu_safe_points = []
        self.config_toml_path = "/etc/cyan-skillfish-governor-smu/config.toml"
        self.overclock_conf_path = "/etc/bc250-smu-oc.conf"

        self.bc250_detect_bin = resolve_bin("bc250-detect")
        self.bc250_apply_bin = resolve_bin("bc250-apply")

        self.scale_min = -60
        self.scale_max = 20
        self.current_scale = -30

        self.settings = {"lang": "English", "theme": "Dark"}
        self.load_settings()

        self.configure(fg_color=BG_COLOR)
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
                        if line.startswith("Language="):
                            self.settings["lang"] = line.strip().split("=", 1)[1]
                        elif line.startswith("Theme="):
                            self.settings["theme"] = line.strip().split("=", 1)[1]
        except Exception:
            pass

    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"Language={self.settings['lang']}\n")
                f.write(f"Theme={self.settings['theme']}\n")
        except Exception:
            pass

    def create_menu(self):
        self.menu_frame = ctk.CTkFrame(self, height=50, corner_radius=25, fg_color=CARD_BG)
        self.menu_frame.pack(side="top", fill="x", padx=20, pady=(15, 10))

        self.lang_menu = ctk.CTkComboBox(
            self.menu_frame,
            values=["English", "Korean"],
            width=110,
            corner_radius=25,
            state="readonly",
            command=self.change_lang,
            font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13),
        )
        self.lang_menu.set(self.settings["lang"])
        self.lang_menu.pack(side="left", padx=(15, 5), pady=10)

        self.theme_menu = ctk.CTkComboBox(
            self.menu_frame,
            values=["Dark", "Light"],
            width=100,
            corner_radius=25,
            state="readonly",
            command=self.change_theme,
            font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13),
        )
        self.theme_menu.set(self.settings["theme"])
        self.theme_menu.pack(side="left", padx=5, pady=10)

        self.btn_update = ctk.CTkButton(
            self.menu_frame,
            width=90,
            corner_radius=25,
            command=self.update_app,
            font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"),
        )
        self.btn_update.pack(side="right", padx=(5, 15), pady=10)

    def change_theme(self, new_theme):
        self.settings["theme"] = new_theme
        self.save_settings()
        ctk.set_appearance_mode(new_theme)

        self.lang_menu.configure(
            fg_color=SEC_BTN_BG,
            button_color=SEC_BTN_BG,
            button_hover_color=SEC_BTN_HOVER,
            text_color=TEXT_COLOR,
            border_width=0,
            dropdown_fg_color=CARD_BG,
        )
        self.theme_menu.configure(
            fg_color=SEC_BTN_BG,
            button_color=SEC_BTN_BG,
            button_hover_color=SEC_BTN_HOVER,
            text_color=TEXT_COLOR,
            border_width=0,
            dropdown_fg_color=CARD_BG,
        )
        self.btn_update.configure(fg_color=SEC_BTN_BG, hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR)

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
        self.btn_update.configure(text=t["update"])

        self.lbl_throttling.configure(text=t["throttling"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_recovery.configure(text=t["recovery"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_clk_head.configure(text=t["clk_mhz"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.lbl_vol_head.configure(text=t["vol_mv"], font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))

    def update_app(self):
        try:
            url = "https://raw.githubusercontent.com/wnduddld0513/BC250-OC-Helper/main/bc250-oc-helper.py"
            target_path = "/opt/bc250-oc-helper/bc250-oc-helper.py"
            temp_path = "/tmp/bc250-oc-helper-update.py"

            subprocess.run(["curl", "-sSL", "-o", temp_path, url], check=True)
            subprocess.run(["mv", temp_path, target_path], check=True)
            subprocess.run(["chmod", "+x", target_path], check=True)

            os.execv(sys.executable, [sys.executable, target_path])
        except Exception as e:
            print(f"Update failed: {e}")

    def create_widgets(self):
        main_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        main_wrapper.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        cpu_card = ctk.CTkFrame(main_wrapper, corner_radius=20, fg_color=CARD_BG)
        cpu_card.pack(side="top", fill="x", pady=(0, 15))

        self.cpu_label = ctk.CTkLabel(cpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"))
        self.cpu_label.pack(anchor="w", padx=20, pady=(15, 5))

        cpu_grid = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_grid.pack(fill="x", padx=20, pady=5)
        cpu_grid.columnconfigure(3, weight=1)

        self.lbl_max_temp = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_max_temp.grid(row=0, column=0, sticky="w", pady=8)
        self.cpu_temp_var = ctk.StringVar(value="90")
        self.cpu_temp_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_temp_var, width=70, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.cpu_temp_entry.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(cpu_grid, text="°C", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=0, column=2, sticky="w", pady=8)

        self.lbl_target_clk = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_clk.grid(row=1, column=0, sticky="w", pady=8)
        self.cpu_clk_var = ctk.StringVar(value="4000")
        self.cpu_clk_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_clk_var, width=70, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.cpu_clk_entry.grid(row=1, column=1, padx=10, pady=8)
        ctk.CTkLabel(cpu_grid, text="MHz", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=1, column=2, sticky="w", pady=8)

        self.cpu_clk_slider = ctk.CTkSlider(cpu_grid, from_=1000, to=4500, corner_radius=15, command=self.on_cpu_clk_slider_move)
        self.cpu_clk_slider.grid(row=1, column=3, sticky="ew", padx=15, pady=8)

        self.lbl_target_vol = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_vol.grid(row=2, column=0, sticky="w", pady=8)
        self.cpu_vol_var = ctk.StringVar(value="1.250")
        self.cpu_vol_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_vol_var, width=70, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.cpu_vol_entry.grid(row=2, column=1, padx=10, pady=8)
        ctk.CTkLabel(cpu_grid, text="V", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=2, column=2, sticky="w", pady=8)

        self.cpu_vol_slider = ctk.CTkSlider(cpu_grid, from_=0.800, to=1.325, corner_radius=15, command=self.on_cpu_slider_move)
        self.cpu_vol_slider.grid(row=2, column=3, sticky="ew", padx=15, pady=8)

        cpu_btn_frame = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_btn_frame.pack(fill="x", padx=20, pady=(5, 15))
        self.btn_apply_cpu = ctk.CTkButton(cpu_btn_frame, width=100, corner_radius=25)
        self.btn_apply_cpu.pack(side="right", padx=(10, 0))
        self.btn_find_vol = ctk.CTkButton(cpu_btn_frame, width=110, corner_radius=25, fg_color=SEC_BTN_BG, hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR)
        self.btn_find_vol.pack(side="right", padx=(0, 0))

        self.btn_apply_cpu.configure(command=self.apply_cpu_oc)
        self.btn_find_vol.configure(command=self.run_cpu_detect)

        self.gpu_card = ctk.CTkFrame(main_wrapper, corner_radius=20, fg_color=CARD_BG)
        self.gpu_card.pack(side="top", fill="both", expand=True)

        self.gpu_label = ctk.CTkLabel(self.gpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=14, weight="bold"))
        self.gpu_label.pack(anchor="w", padx=20, pady=(15, 5))

        temp_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        temp_frame.pack(side="top", fill="x", padx=20, pady=5)

        self.lbl_throttling = ctk.CTkLabel(temp_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_throttling.grid(row=0, column=0, sticky="w", pady=5)
        self.gpu_throt_var = ctk.StringVar(value="90")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_throt_var, width=65, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=0, column=1, padx=10, pady=5)
        ctk.CTkLabel(temp_frame, text="°C", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=0, column=2, sticky="w", pady=5)

        self.lbl_recovery = ctk.CTkLabel(temp_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13))
        self.lbl_recovery.grid(row=1, column=0, sticky="w", pady=5)
        self.gpu_recov_var = ctk.StringVar(value="85")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_recov_var, width=65, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=1, column=1, padx=10, pady=5)
        ctk.CTkLabel(temp_frame, text="°C", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12)).grid(row=1, column=2, sticky="w", pady=5)

        list_label_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        list_label_frame.pack(side="top", fill="x", padx=20, pady=(10, 0))
        list_label_frame.columnconfigure(0, minsize=115)
        list_label_frame.columnconfigure(1, minsize=115)

        self.lbl_clk_head = ctk.CTkLabel(list_label_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.lbl_clk_head.grid(row=0, column=0, sticky="w", padx=5)
        self.lbl_vol_head = ctk.CTkLabel(list_label_frame, font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
        self.lbl_vol_head.grid(row=0, column=1, sticky="w", padx=5)

        gpu_btn_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        gpu_btn_frame.pack(side="bottom", fill="x", padx=20, pady=(5, 15))
        self.btn_apply_gpu = ctk.CTkButton(gpu_btn_frame, width=100, corner_radius=25)
        self.btn_apply_gpu.pack(side="right", padx=(10, 0))
        self.btn_reboot = ctk.CTkButton(gpu_btn_frame, width=100, corner_radius=25, fg_color=("#d9534f", "#c9302c"), hover_color=("#c9302c", "#a01e1e"))
        self.btn_reboot.pack(side="right", padx=(0, 0))

        self.btn_apply_gpu.configure(command=self.apply_gpu_config)
        self.btn_reboot.configure(command=self.reboot_system)

        self.points_container = ctk.CTkScrollableFrame(self.gpu_card, fg_color="transparent", corner_radius=15)
        self.points_container.pack(side="top", fill="both", expand=True, padx=15, pady=5)

    def on_cpu_clk_slider_move(self, val):
        self.cpu_clk_var.set(str(int(val)))

    def on_cpu_slider_move(self, val):
        self.cpu_vol_var.set(f"{val:.3f}")

    def load_cpu_config(self):
        self.current_scale = -30
        if os.path.exists(self.overclock_conf_path):
            with open(self.overclock_conf_path, "r", encoding="utf-8") as f:
                content = f.read()

            f_match = re.search(r"frequency\s*=\s*(\d+)", content)
            s_match = re.search(r"scale\s*=\s*(-?\d+)", content)
            t_match = re.search(r"max_temperature\s*=\s*(\d+)", content)

            if f_match:
                mhz = int(f_match.group(1))
                self.cpu_clk_var.set(str(mhz))
                self.cpu_clk_slider.set(mhz)

            if s_match:
                self.current_scale = int(s_match.group(1))
                try:
                    f_now = int(self.cpu_clk_var.get())
                    pred_mv = vid_predict(f_now, self.current_scale)
                    self.cpu_vol_var.set(f"{pred_mv / 1000.0:.3f}")
                    self.cpu_vol_slider.set(max(0.8, min(1.325, pred_mv / 1000.0)))
                except Exception:
                    pass

            if t_match:
                self.cpu_temp_var.set(t_match.group(1))

    def run_cpu_detect(self):
        try:
            mhz = int(self.cpu_clk_var.get())
            mv = parse_volt_to_mv(self.cpu_vol_var.get())
            temp = int(self.cpu_temp_var.get())

            detect_cmd = [
                "sudo",
                self.bc250_detect_bin,
                "--frequency",
                str(mhz),
                "--vid",
                str(mv),
                "-t",
                str(temp),
                "--keep",
                "-c",
                self.overclock_conf_path,
            ]
            subprocess.run(detect_cmd, check=True)
            self.load_cpu_config()
        except Exception as e:
            print(e)

    def apply_cpu_oc(self):
        try:
            mhz = int(self.cpu_clk_var.get())
            temp = int(self.cpu_temp_var.get())
            target_mv = parse_volt_to_mv(self.cpu_vol_var.get())

            scale = nearest_scale_for_vid(
                clock=mhz,
                target_mv=target_mv,
                scale_min=self.scale_min,
                scale_max=self.scale_max,
                current_scale=self.current_scale,
            )

            pred_mv = vid_predict(mhz, scale)

            with open(self.overclock_conf_path, "w", encoding="utf-8") as f:
                f.write(
                    "[overclock]\n"
                    f"frequency = {mhz}\n"
                    f"scale = {scale}\n"
                    f"max_temperature = {temp}\n"
                )

            subprocess.run(["sudo", self.bc250_apply_bin, "--install", self.overclock_conf_path], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "bc250-smu-oc"], check=True)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)

            self.current_scale = scale
            self.cpu_vol_var.set(f"{pred_mv / 1000.0:.3f}")
            self.cpu_vol_slider.set(max(0.8, min(1.325, pred_mv / 1000.0)))

            print(f"Applied: {mhz} MHz, target={target_mv} mV, scale={scale}, predicted={pred_mv:.1f} mV")
        except Exception as e:
            print(e)

    def load_gpu_config(self):
        if not os.path.exists(self.config_toml_path):
            return

        with open(self.config_toml_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.gpu_safe_points = []

        throt = re.search(r"throttling\s*=\s*(\d+)", content)
        recov = re.search(r"throttling_recovery\s*=\s*(\d+)", content)
        if throt:
            self.gpu_throt_var.set(throt.group(1))
        if recov:
            self.gpu_recov_var.set(recov.group(1))

        matches = re.findall(r"\[\[safe-points\]\]\s*frequency\s*=\s*(\d+)\s*voltage\s*=\s*(\d+)", content)
        for clk, vol in matches:
            self.gpu_safe_points.append({"frequency": clk, "voltage": vol})

        if not self.gpu_safe_points:
            self.gpu_safe_points = [{"frequency": "500", "voltage": "700"}]

        self.render_gpu_rows()

    def render_gpu_rows(self):
        for widget in self.points_container.winfo_children():
            widget.destroy()

        for i, pt in enumerate(self.gpu_safe_points):
            f_entry = ctk.CTkEntry(self.points_container, width=80, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
            f_entry.insert(0, pt["frequency"])
            f_entry.grid(row=i, column=0, padx=5, pady=3, sticky="w")
            f_entry.bind("<FocusOut>", lambda e, idx=i, entry=f_entry: self.update_gpu_val(idx, "frequency", entry.get()))

            v_entry = ctk.CTkEntry(self.points_container, width=80, corner_radius=10, border_width=0, fg_color=ENTRY_BG, justify="center", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=12))
            v_entry.insert(0, pt["voltage"])
            v_entry.grid(row=i, column=1, padx=5, pady=3, sticky="w")
            v_entry.bind("<FocusOut>", lambda e, idx=i, entry=v_entry: self.update_gpu_val(idx, "voltage", entry.get()))

            btn_frame = ctk.CTkFrame(self.points_container, fg_color="transparent")
            btn_frame.grid(row=i, column=2, padx=2, pady=3, sticky="w")

            ctk.CTkButton(
                btn_frame,
                text="+",
                width=36,
                height=36,
                corner_radius=18,
                fg_color=SEC_BTN_BG,
                hover_color=SEC_BTN_HOVER,
                text_color=TEXT_COLOR,
                font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=20, weight="bold"),
                command=lambda idx=i: self.add_gpu_row(idx),
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                btn_frame,
                text="−",
                width=36,
                height=36,
                corner_radius=18,
                fg_color=SEC_BTN_BG,
                hover_color=SEC_BTN_HOVER,
                text_color=TEXT_COLOR,
                font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=20, weight="bold"),
                command=lambda idx=i: self.remove_gpu_row(idx),
            ).pack(side="left", padx=3)

    def update_gpu_val(self, idx, key, val):
        self.gpu_safe_points[idx][key] = val.strip()

    def add_gpu_row(self, idx):
        base_pt = self.gpu_safe_points[idx]
        try:
            nf = str(int(base_pt["frequency"]) + 100)
            nv = str(int(base_pt["voltage"]) + 25)
        except Exception:
            nf, nv = "1000", "800"
        self.gpu_safe_points.insert(idx + 1, {"frequency": nf, "voltage": nv})
        self.render_gpu_rows()

    def remove_gpu_row(self, idx):
        if len(self.gpu_safe_points) <= 1:
            return
        del self.gpu_safe_points[idx]
        self.render_gpu_rows()

    def apply_gpu_config(self):
        try:
            freqs = [int(pt["frequency"]) for pt in self.gpu_safe_points if pt["frequency"].isdigit()]
            if not freqs:
                print("No valid GPU safe-points frequency values.")
                return

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
                f"throttling_recovery = {self.gpu_recov_var.get()}",
            ]

            for pt in self.gpu_safe_points:
                toml.append("[[safe-points]]")
                toml.append(f"frequency = {pt['frequency']}")
                toml.append(f"voltage = {pt['voltage']}")

            with open(self.config_toml_path, "w", encoding="utf-8") as f:
                f.write("\n".join(toml) + "\n")

            subprocess.run(["sudo", "systemctl", "restart", "cyan-skillfish-governor-smu"], check=True)
        except Exception as e:
            print(e)

    def reboot_system(self):
        subprocess.run(["sudo", "reboot"])


if __name__ == "__main__":
    app = OCApp()
    app.mainloop()
