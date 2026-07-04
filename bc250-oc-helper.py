#!/usr/bin/env python3
import os
import re
import sys
import shutil
import tempfile
import subprocess
import tkinter as tk
import customtkinter as ctk

APP_NAME = "bc250-oc-helper"
USER_CONFIG_FILE = os.path.expanduser(f"~/.config/{APP_NAME}/config.txt")
ICON_FILE = "/opt/bc250-oc-helper/icon.png"
GPU_CONFIG_PATH = "/etc/cyan-skillfish-governor-smu/config.toml"
OVERCLOCK_CONF_FALLBACK = os.path.expanduser(f"~/.config/{APP_NAME}/overclock.conf")

GEMINI_FONT_FAMILY = "sans-serif"

LANG = {
    "English": {
        "cpu_control": "CPU CONTROL",
        "gpu_control": "GPU CONTROL",
        "terminal": "Terminal",
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
        "terminal": "터미널",
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


def find_cmd(name: str):
    p = shutil.which(name)
    if p:
        return p
    for c in (f"/usr/local/bin/{name}", f"/usr/bin/{name}", f"/root/.local/bin/{name}"):
        if os.path.exists(c):
            return c
    return None


def parse_volt_to_mv(txt: str) -> int:
    s = txt.strip().replace(",", ".").replace(" ", "")
    if not s:
        raise ValueError("Voltage is empty")
    v = float(s)
    if v >= 100:
        return int(round(v))
    return int(round(v * 1000))


def vid_predict(clock: int, scale: int) -> float:
    if clock < 3000:
        raise ValueError("clock must be >= 3000 MHz")
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
        self.geometry("1060x640")
        self.minsize(940, 580)

        try:
            if os.path.exists(ICON_FILE):
                icon_img = tk.PhotoImage(file=ICON_FILE)
                self.iconphoto(False, icon_img)
        except Exception:
            pass

        self.settings = {"lang": "English", "theme": "Dark"}
        self.gpu_safe_points = []
        self.current_scale = -30
        self.scale_min = -60
        self.scale_max = 20

        self.bc250_detect = find_cmd("bc250-detect")
        self.bc250_apply = find_cmd("bc250-apply")
        self.systemctl = find_cmd("systemctl") or "/usr/bin/systemctl"

        self.config_toml_path = GPU_CONFIG_PATH
        self.overclock_conf_path = self.resolve_overclock_conf_path()

        self.load_settings()

        self.configure(fg_color=BG_COLOR)
        ctk.set_appearance_mode(self.settings["theme"])
        ctk.set_default_color_theme("blue")

        self.create_menu()
        self.create_widgets()

        self.change_theme(self.settings["theme"])
        self.change_lang(self.settings["lang"])

        self.log(f"Python: {sys.version.split()[0]}")
        self.log(f"bc250-detect: {self.bc250_detect or 'NOT FOUND'}")
        self.log(f"bc250-apply: {self.bc250_apply or 'NOT FOUND'}")
        self.log(f"CPU conf: {self.overclock_conf_path}")
        self.log(f"GPU conf: {self.config_toml_path}")

        self.load_cpu_config()
        self.load_gpu_config()

    def resolve_overclock_conf_path(self):
        user = os.environ.get("SUDO_USER") or os.environ.get("USER")
        if user:
            p = os.path.join("/home", user, "bc250_smu_oc", "overclock.conf")
            if os.path.exists(os.path.dirname(p)):
                return p
        os.makedirs(os.path.dirname(OVERCLOCK_CONF_FALLBACK), exist_ok=True)
        return OVERCLOCK_CONF_FALLBACK

    def log(self, msg: str):
        self.term_box.configure(state="normal")
        self.term_box.insert("end", msg.rstrip() + "\n")
        self.term_box.see("end")
        self.term_box.configure(state="disabled")
        self.update_idletasks()

    def run_cmd_live(self, cmd, need_sudo=False):
        final_cmd = cmd[:]
        if need_sudo and os.geteuid() != 0:
            final_cmd = ["sudo", "-n"] + final_cmd

        self.log("$ " + " ".join(final_cmd))

        p = subprocess.Popen(
            final_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if p.stdout:
            for line in p.stdout:
                self.log(line.rstrip())

        rc = p.wait()
        if rc != 0:
            if need_sudo and os.geteuid() != 0:
                self.log("[HINT] sudoers NOPASSWD 설정 필요")
            raise RuntimeError(f"Command failed (exit={rc})")
        return rc

    def load_settings(self):
        try:
            if os.path.exists(USER_CONFIG_FILE):
                with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("Language="):
                            self.settings["lang"] = line.strip().split("=", 1)[1]
                        elif line.startswith("Theme="):
                            self.settings["theme"] = line.strip().split("=", 1)[1]
        except Exception:
            pass

    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)
            with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"Language={self.settings['lang']}\n")
                f.write(f"Theme={self.settings['theme']}\n")
        except Exception as e:
            self.log(f"[WARN] save_settings: {e}")

    def create_menu(self):
        self.menu_frame = ctk.CTkFrame(self, height=48, corner_radius=24, fg_color=CARD_BG)
        self.menu_frame.pack(side="top", fill="x", padx=18, pady=(12, 8))

        self.lang_menu = ctk.CTkComboBox(
            self.menu_frame,
            values=["English", "Korean"],
            width=120,
            corner_radius=24,
            state="readonly",
            command=self.change_lang,
            font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13),
        )
        self.lang_menu.set(self.settings["lang"])
        self.lang_menu.pack(side="left", padx=(12, 6), pady=8)

        self.theme_menu = ctk.CTkComboBox(
            self.menu_frame,
            values=["Dark", "Light"],
            width=100,
            corner_radius=24,
            state="readonly",
            command=self.change_theme,
            font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13),
        )
        self.theme_menu.set(self.settings["theme"])
        self.theme_menu.pack(side="left", padx=6, pady=8)

        self.btn_update = ctk.CTkButton(
            self.menu_frame,
            width=92,
            corner_radius=24,
            command=self.update_app,
            font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=13, weight="bold"),
        )
        self.btn_update.pack(side="right", padx=(6, 12), pady=8)

    def create_widgets(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=18, pady=(8, 14))

        main.grid_columnconfigure(0, weight=9, uniform="col")
        main.grid_columnconfigure(1, weight=11, uniform="col")
        main.grid_rowconfigure(0, weight=5)
        main.grid_rowconfigure(1, weight=3)

        cpu_card = ctk.CTkFrame(main, corner_radius=18, fg_color=CARD_BG)
        cpu_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=(0, 7))

        self.cpu_label = ctk.CTkLabel(cpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=15, weight="bold"))
        self.cpu_label.pack(anchor="w", padx=16, pady=(12, 6))

        cpu_grid = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_grid.pack(fill="x", padx=16, pady=4)
        cpu_grid.grid_columnconfigure(3, weight=1)

        self.lbl_max_temp = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_max_temp.grid(row=0, column=0, sticky="w", pady=8)
        self.cpu_temp_var = ctk.StringVar(value="90")
        self.cpu_temp_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_temp_var, width=76, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center")
        self.cpu_temp_entry.grid(row=0, column=1, padx=9, pady=8)
        ctk.CTkLabel(cpu_grid, text="°C").grid(row=0, column=2, sticky="w", pady=8)

        self.lbl_target_clk = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_clk.grid(row=1, column=0, sticky="w", pady=8)
        self.cpu_clk_var = ctk.StringVar(value="3500")
        self.cpu_clk_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_clk_var, width=76, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center")
        self.cpu_clk_entry.grid(row=1, column=1, padx=9, pady=8)
        ctk.CTkLabel(cpu_grid, text="MHz").grid(row=1, column=2, sticky="w", pady=8)

        self.cpu_clk_slider = ctk.CTkSlider(cpu_grid, from_=1000, to=4500, corner_radius=14, command=self.on_cpu_clk_slider_move)
        self.cpu_clk_slider.grid(row=1, column=3, sticky="ew", padx=10, pady=8)

        self.lbl_target_vol = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_vol.grid(row=2, column=0, sticky="w", pady=8)
        self.cpu_vol_var = ctk.StringVar(value="1.250")
        self.cpu_vol_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_vol_var, width=76, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center")
        self.cpu_vol_entry.grid(row=2, column=1, padx=9, pady=8)
        ctk.CTkLabel(cpu_grid, text="V").grid(row=2, column=2, sticky="w", pady=8)

        self.cpu_vol_slider = ctk.CTkSlider(cpu_grid, from_=0.800, to=1.325, corner_radius=14, command=self.on_cpu_slider_move)
        self.cpu_vol_slider.grid(row=2, column=3, sticky="ew", padx=10, pady=8)

        cpu_btn = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_btn.pack(fill="x", padx=16, pady=(6, 12))
        self.btn_apply_cpu = ctk.CTkButton(cpu_btn, width=108, corner_radius=22, command=self.apply_cpu_oc)
        self.btn_apply_cpu.pack(side="right", padx=(8, 0))
        self.btn_find_vol = ctk.CTkButton(cpu_btn, width=108, corner_radius=22, fg_color=SEC_BTN_BG, hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR, command=self.run_cpu_detect)
        self.btn_find_vol.pack(side="right")

        term_card = ctk.CTkFrame(main, corner_radius=18, fg_color=CARD_BG)
        term_card.grid(row=1, column=0, sticky="nsew", padx=(0, 7), pady=(7, 0))

        self.term_label = ctk.CTkLabel(term_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=15, weight="bold"))
        self.term_label.pack(anchor="w", padx=16, pady=(10, 6))

        self.term_box = ctk.CTkTextbox(term_card, wrap="word")
        self.term_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.term_box.configure(state="disabled")

        self.gpu_card = ctk.CTkFrame(main, corner_radius=18, fg_color=CARD_BG)
        self.gpu_card.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(7, 0), pady=0)

        self.gpu_label = ctk.CTkLabel(self.gpu_card, text="", font=ctk.CTkFont(family=GEMINI_FONT_FAMILY, size=15, weight="bold"))
        self.gpu_label.pack(anchor="w", padx=16, pady=(12, 6))

        gpu_top = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        gpu_top.pack(side="top", fill="both", expand=True, padx=12, pady=4)
        gpu_top.grid_columnconfigure(0, weight=4)
        gpu_top.grid_columnconfigure(1, weight=6)
        gpu_top.grid_rowconfigure(0, weight=1)

        temp_frame = ctk.CTkFrame(gpu_top, fg_color="transparent")
        temp_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.lbl_throttling = ctk.CTkLabel(temp_frame, text="")
        self.lbl_throttling.grid(row=0, column=0, sticky="w", pady=7)
        self.gpu_throt_var = ctk.StringVar(value="90")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_throt_var, width=72, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center").grid(row=0, column=1, padx=8, pady=7)
        ctk.CTkLabel(temp_frame, text="°C").grid(row=0, column=2, sticky="w", pady=7)

        self.lbl_recovery = ctk.CTkLabel(temp_frame, text="")
        self.lbl_recovery.grid(row=1, column=0, sticky="w", pady=7)
        self.gpu_recov_var = ctk.StringVar(value="85")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_recov_var, width=72, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center").grid(row=1, column=1, padx=8, pady=7)
        ctk.CTkLabel(temp_frame, text="°C").grid(row=1, column=2, sticky="w", pady=7)

        table_wrap = ctk.CTkFrame(gpu_top, fg_color="transparent")
        table_wrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        table_wrap.grid_columnconfigure(0, weight=1)
        table_wrap.grid_rowconfigure(1, weight=1)

        list_label = ctk.CTkFrame(table_wrap, fg_color="transparent")
        list_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        list_label.grid_columnconfigure(0, minsize=92)
        list_label.grid_columnconfigure(1, minsize=92)
        list_label.grid_columnconfigure(2, minsize=40)
        list_label.grid_columnconfigure(3, minsize=40)

        self.lbl_clk_head = ctk.CTkLabel(list_label, text="", anchor="w")
        self.lbl_clk_head.grid(row=0, column=0, sticky="w", padx=4)
        self.lbl_vol_head = ctk.CTkLabel(list_label, text="", anchor="w")
        self.lbl_vol_head.grid(row=0, column=1, sticky="w", padx=4)

        self.points_container = ctk.CTkScrollableFrame(table_wrap, fg_color="transparent", corner_radius=10)
        self.points_container.grid(row=1, column=0, sticky="nsew")
        self.points_container.grid_columnconfigure(0, minsize=92)
        self.points_container.grid_columnconfigure(1, minsize=92)
        self.points_container.grid_columnconfigure(2, minsize=40)
        self.points_container.grid_columnconfigure(3, minsize=40)

        gpu_btn = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        gpu_btn.pack(side="bottom", fill="x", padx=16, pady=(6, 12))
        self.btn_apply_gpu = ctk.CTkButton(gpu_btn, width=104, corner_radius=22, command=self.apply_gpu_config)
        self.btn_apply_gpu.pack(side="right", padx=(8, 0))
        self.btn_reboot = ctk.CTkButton(gpu_btn, width=104, corner_radius=22, fg_color=("#d9534f", "#c9302c"), hover_color=("#c9302c", "#a01e1e"), command=self.reboot_system)
        self.btn_reboot.pack(side="right")

    def change_theme(self, new_theme):
        self.settings["theme"] = new_theme
        self.save_settings()
        ctk.set_appearance_mode(new_theme)
        self.lang_menu.configure(fg_color=SEC_BTN_BG, button_color=SEC_BTN_BG, button_hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR, border_width=0, dropdown_fg_color=CARD_BG)
        self.theme_menu.configure(fg_color=SEC_BTN_BG, button_color=SEC_BTN_BG, button_hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR, border_width=0, dropdown_fg_color=CARD_BG)
        self.btn_update.configure(fg_color=SEC_BTN_BG, hover_color=SEC_BTN_HOVER, text_color=TEXT_COLOR)

    def change_lang(self, lang_name):
        self.settings["lang"] = lang_name
        self.save_settings()
        t = LANG[lang_name]
        self.cpu_label.configure(text=t["cpu_control"])
        self.gpu_label.configure(text=t["gpu_control"])
        self.term_label.configure(text=t["terminal"])
        self.lbl_max_temp.configure(text=t["max_temp"])
        self.lbl_target_clk.configure(text=t["target_clk"])
        self.lbl_target_vol.configure(text=t["target_vol"])
        self.btn_find_vol.configure(text=t["find_vol"])
        self.btn_apply_cpu.configure(text=t["apply"])
        self.btn_apply_gpu.configure(text=t["apply"])
        self.btn_reboot.configure(text=t["reboot"])
        self.btn_update.configure(text=t["update"])
        self.lbl_throttling.configure(text=t["throttling"])
        self.lbl_recovery.configure(text=t["recovery"])
        self.lbl_clk_head.configure(text=t["clk_mhz"])
        self.lbl_vol_head.configure(text=t["vol_mv"])

    def update_app(self):
        try:
            url = "https://raw.githubusercontent.com/wnduddld0513/BC250-OC-Helper/main/bc250-oc-helper.py"
            target = "/opt/bc250-oc-helper/bc250-oc-helper.py"
            temp = "/tmp/bc250-oc-helper-update.py"
            self.run_cmd_live(["curl", "-sSL", "-o", temp, url], need_sudo=False)
            self.run_cmd_live(["cp", temp, target], need_sudo=True)
            self.run_cmd_live(["chmod", "+x", target], need_sudo=True)
            self.log("[OK] Updated. Restarting...")
            os.execv(sys.executable, [sys.executable, target])
        except Exception as e:
            self.log(f"[ERROR] Update failed: {e}")

    def on_cpu_clk_slider_move(self, val):
        self.cpu_clk_var.set(str(int(val)))

    def on_cpu_slider_move(self, val):
        self.cpu_vol_var.set(f"{val:.3f}")

    def load_cpu_config(self):
        self.current_scale = -30
        if not os.path.exists(self.overclock_conf_path):
            return
        try:
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
                pred_mv = vid_predict(int(self.cpu_clk_var.get()), self.current_scale)
                v = max(0.800, min(1.325, pred_mv / 1000.0))
                self.cpu_vol_var.set(f"{v:.3f}")
                self.cpu_vol_slider.set(v)

            if t_match:
                self.cpu_temp_var.set(t_match.group(1))
        except Exception as e:
            self.log(f"[WARN] load_cpu_config: {e}")

    def run_cpu_detect(self):
        try:
            if not self.bc250_detect:
                raise RuntimeError("bc250-detect not found")

            mhz = int(self.cpu_clk_var.get())
            mv = parse_volt_to_mv(self.cpu_vol_var.get())
            temp = int(self.cpu_temp_var.get())

            os.makedirs(os.path.dirname(self.overclock_conf_path), exist_ok=True)

            cmd = [
                self.bc250_detect,
                "--frequency", str(mhz),
                "--vid", str(mv),
                "-t", str(temp),
                "--keep",
                "-c", self.overclock_conf_path,
            ]
            self.run_cmd_live(cmd, need_sudo=True)
            self.load_cpu_config()
            self.log("[OK] Detect done")
        except Exception as e:
            self.log(f"[ERROR] Detect failed: {e}")

    def apply_cpu_oc(self):
        try:
            if not self.bc250_apply:
                raise RuntimeError("bc250-apply not found")

            mhz = int(self.cpu_clk_var.get())
            temp = int(self.cpu_temp_var.get())
            target_mv = parse_volt_to_mv(self.cpu_vol_var.get())

            scale = nearest_scale_for_vid(mhz, target_mv, self.scale_min, self.scale_max, self.current_scale)
            pred_mv = vid_predict(mhz, scale)

            os.makedirs(os.path.dirname(self.overclock_conf_path), exist_ok=True)
            with open(self.overclock_conf_path, "w", encoding="utf-8") as f:
                f.write(
                    "[overclock]\n"
                    f"frequency = {mhz}\n"
                    f"scale = {scale}\n"
                    f"max_temperature = {temp}\n"
                )

            self.run_cmd_live([self.bc250_apply, "--install", self.overclock_conf_path], need_sudo=True)
            self.run_cmd_live([self.systemctl, "restart", "bc250-smu-oc"], need_sudo=True)

            self.current_scale = scale
            v = max(0.800, min(1.325, pred_mv / 1000.0))
            self.cpu_vol_var.set(f"{v:.3f}")
            self.cpu_vol_slider.set(v)
            self.log(f"[OK] Applied CPU: {mhz} MHz, target={target_mv} mV, scale={scale}, predicted={pred_mv:.1f} mV")
        except Exception as e:
            self.log(f"[ERROR] Apply CPU failed: {e}")

    def load_gpu_config(self):
        if not os.path.exists(self.config_toml_path):
            self.gpu_safe_points = [{"frequency": "500", "voltage": "700"}]
            self.render_gpu_rows()
            return
        try:
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
        except Exception as e:
            self.log(f"[WARN] load_gpu_config: {e}")

    def render_gpu_rows(self):
        for widget in self.points_container.winfo_children():
            widget.destroy()

        for i, pt in enumerate(self.gpu_safe_points):
            f_entry = ctk.CTkEntry(self.points_container, width=88, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center")
            f_entry.insert(0, pt["frequency"])
            f_entry.grid(row=i, column=0, padx=(4, 4), pady=3, sticky="w")
            f_entry.bind("<FocusOut>", lambda e, idx=i, ent=f_entry: self.update_gpu_val(idx, "frequency", ent.get()))

            v_entry = ctk.CTkEntry(self.points_container, width=88, corner_radius=9, border_width=0, fg_color=ENTRY_BG, justify="center")
            v_entry.insert(0, pt["voltage"])
            v_entry.grid(row=i, column=1, padx=(4, 4), pady=3, sticky="w")
            v_entry.bind("<FocusOut>", lambda e, idx=i, ent=v_entry: self.update_gpu_val(idx, "voltage", ent.get()))

            plus_btn = ctk.CTkButton(
                self.points_container,
                text="+",
                width=34,
                height=30,
                corner_radius=15,
                fg_color=SEC_BTN_BG,
                hover_color=SEC_BTN_HOVER,
                text_color=TEXT_COLOR,
                command=lambda idx=i: self.add_gpu_row(idx),
            )
            plus_btn.grid(row=i, column=2, padx=(2, 2), pady=3, sticky="w")

            minus_btn = ctk.CTkButton(
                self.points_container,
                text="−",
                width=34,
                height=30,
                corner_radius=15,
                fg_color=SEC_BTN_BG,
                hover_color=SEC_BTN_HOVER,
                text_color=TEXT_COLOR,
                command=lambda idx=i: self.remove_gpu_row(idx),
            )
            minus_btn.grid(row=i, column=3, padx=(2, 2), pady=3, sticky="w")

    def update_gpu_val(self, idx, key, val):
        self.gpu_safe_points[idx][key] = val.strip()

    def add_gpu_row(self, idx):
        base = self.gpu_safe_points[idx]
        try:
            nf = str(int(base["frequency"]) + 100)
            nv = str(int(base["voltage"]) + 25)
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
                raise RuntimeError("No valid GPU frequencies")

            toml_lines = [
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
                toml_lines.append("[[safe-points]]")
                toml_lines.append(f"frequency = {pt['frequency']}")
                toml_lines.append(f"voltage = {pt['voltage']}")

            tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
            try:
                tmp.write("\n".join(toml_lines) + "\n")
                tmp.close()
                self.run_cmd_live(["cp", tmp.name, self.config_toml_path], need_sudo=True)
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

            self.run_cmd_live([self.systemctl, "restart", "cyan-skillfish-governor-smu"], need_sudo=True)
            self.log("[OK] Applied GPU config")
        except Exception as e:
            self.log(f"[ERROR] Apply GPU failed: {e}")

    def reboot_system(self):
        try:
            self.run_cmd_live(["reboot"], need_sudo=True)
        except Exception as e:
            self.log(f"[ERROR] Reboot failed: {e}")


if __name__ == "__main__":
    app = OCApp()
    app.mainloop()
