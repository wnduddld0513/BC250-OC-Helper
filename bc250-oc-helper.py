import sys
import os
import subprocess
import re
import tkinter as tk
import customtkinter as ctk

if os.geteuid() != 0:
    print("This program requires sudo privileges.")
    sys.exit(1)

# 설정 파일 경로 및 포맷 변경
CONFIG_FILE = "/opt/bc250-oc-helper/config.txt"

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
        self.geometry("420x660")
        self.minsize(400, 600)
        
        self.gpu_safe_points = []
        self.config_toml_path = "/etc/cyan-skillfish-governor-smu/config.toml"
        self.overclock_conf_path = "/opt/bc250-oc-helper/overclock.conf"
        
        self.settings = {"lang": "English", "theme": "Dark"}
        self.load_settings()
        
        ctk.set_appearance_mode(self.settings["theme"])
        ctk.set_default_color_theme("blue")
        
        self.create_menu()
        self.create_widgets()
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
        # 상단 메뉴 바 레이아웃
        menu_frame = ctk.CTkFrame(self, height=40, corner_radius=0)
        menu_frame.pack(side="top", fill="x")
        
        # 언어 드롭다운 메뉴
        self.lang_menu = ctk.CTkOptionMenu(menu_frame, values=["English", "Korean"], width=110, command=self.change_lang)
        self.lang_menu.set(self.settings["lang"])
        self.lang_menu.pack(side="left", padx=10, pady=8)
        
        # 테마 드롭다운 메뉴
        self.theme_menu = ctk.CTkOptionMenu(menu_frame, values=["Dark", "Light"], width=110, command=self.change_theme)
        self.theme_menu.set(self.settings["theme"])
        self.theme_menu.pack(side="left", padx=5, pady=8)

    def change_theme(self, new_theme):
        self.settings["theme"] = new_theme
        self.save_settings()
        ctk.set_appearance_mode(new_theme)

    def change_lang(self, lang_name):
        self.settings["lang"] = lang_name
        self.save_settings()
        t = LANG[lang_name]
        
        self.cpu_label.configure(text=t["cpu_control"])
        self.gpu_label.configure(text=t["gpu_control"])
        self.lbl_max_temp.configure(text=t["max_temp"])
        self.lbl_target_clk.configure(text=t["target_clk"])
        self.lbl_target_vol.configure(text=t["target_vol"])
        
        self.btn_find_vol.configure(text=t["find_vol"])
        self.btn_apply_cpu.configure(text=t["apply"])
        self.btn_apply_gpu.configure(text=t["apply"])
        self.btn_reboot.configure(text=t["reboot"])
        
        self.lbl_throttling.configure(text=t["throttling"])
        self.lbl_recovery.configure(text=t["recovery"])
        self.lbl_clk_head.configure(text=t["clk_mhz"])
        self.lbl_vol_head.configure(text=t["vol_mv"])

    def create_widgets(self):
        # --- CPU ---
        cpu_card = ctk.CTkFrame(self)
        cpu_card.pack(side="top", fill="x", padx=15, pady=10)
        
        self.cpu_label = ctk.CTkLabel(cpu_card, text="", font=("Sans", 12, "bold"))
        self.cpu_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        cpu_grid = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_grid.pack(fill="x", padx=15, pady=5)
        cpu_grid.columnconfigure(3, weight=1)

        self.lbl_max_temp = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_max_temp.grid(row=0, column=0, sticky="w", pady=5)
        self.cpu_temp_var = ctk.StringVar(value="90")
        self.cpu_temp_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_temp_var, width=65, justify="center")
        self.cpu_temp_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(cpu_grid, text="°C").grid(row=0, column=2, sticky="w", pady=5)

        self.lbl_target_clk = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_clk.grid(row=1, column=0, sticky="w", pady=5)
        self.cpu_clk_var = ctk.StringVar(value="4000")
        self.cpu_clk_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_clk_var, width=65, justify="center")
        self.cpu_clk_entry.grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkLabel(cpu_grid, text="MHz").grid(row=1, column=2, sticky="w", pady=5)
        
        self.cpu_clk_slider = ctk.CTkSlider(cpu_grid, from_=1000, to=4500, command=self.on_cpu_clk_slider_move)
        self.cpu_clk_slider.grid(row=1, column=3, sticky="ew", padx=10, pady=5)

        self.lbl_target_vol = ctk.CTkLabel(cpu_grid, text="")
        self.lbl_target_vol.grid(row=2, column=0, sticky="w", pady=5)
        self.cpu_vol_var = ctk.StringVar(value="1.250")
        self.cpu_vol_entry = ctk.CTkEntry(cpu_grid, textvariable=self.cpu_vol_var, width=65, justify="center")
        self.cpu_vol_entry.grid(row=2, column=1, padx=5, pady=5)
        ctk.CTkLabel(cpu_grid, text="V").grid(row=2, column=2, sticky="w", pady=5)
        
        self.cpu_vol_slider = ctk.CTkSlider(cpu_grid, from_=0.800, to=1.325, command=self.on_cpu_slider_move)
        self.cpu_vol_slider.grid(row=2, column=3, sticky="ew", padx=10, pady=5)

        cpu_btn_frame = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_btn_frame.pack(fill="x", padx=15, pady=10)
        self.btn_apply_cpu = ctk.CTkButton(cpu_btn_frame, width=80, command=self.apply_cpu_oc)
        self.btn_apply_cpu.pack(side="right", padx=(5, 0))
        self.btn_find_vol = ctk.CTkButton(cpu_btn_frame, width=90, fg_color="#444444", hover_color="#555555", command=self.run_cpu_detect)
        self.btn_find_vol.pack(side="right", padx=(0, 5))

        # --- GPU ---
        self.gpu_card = ctk.CTkFrame(self)
        self.gpu_card.pack(side="top", fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.gpu_label = ctk.CTkLabel(self.gpu_card, text="", font=("Sans", 12, "bold"))
        self.gpu_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        temp_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        temp_frame.pack(side="top", fill="x", padx=15, pady=5)
        
        self.lbl_throttling = ctk.CTkLabel(temp_frame)
        self.lbl_throttling.grid(row=0, column=0, sticky="w", pady=3)
        self.gpu_throt_var = ctk.StringVar(value="90")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_throt_var, width=60, justify="center").grid(row=0, column=1, padx=5, pady=3)
        ctk.CTkLabel(temp_frame, text="°C").grid(row=0, column=2, sticky="w", pady=3)
        
        self.lbl_recovery = ctk.CTkLabel(temp_frame)
        self.lbl_recovery.grid(row=1, column=0, sticky="w", pady=3)
        self.gpu_recov_var = ctk.StringVar(value="85")
        ctk.CTkEntry(temp_frame, textvariable=self.gpu_recov_var, width=60, justify="center").grid(row=1, column=1, padx=5, pady=3)
        ctk.CTkLabel(temp_frame, text="°C").grid(row=1, column=2, sticky="w", pady=3)

        gpu_btn_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        gpu_btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)
        self.btn_apply_gpu = ctk.CTkButton(gpu_btn_frame, width=80, command=self.apply_gpu_config)
        self.btn_apply_gpu.pack(side="right", padx=(5, 0))
        self.btn_reboot = ctk.CTkButton(gpu_btn_frame, width=80, fg_color="#d9534f", hover_color="#c9302c", command=self.reboot_system)
        self.btn_reboot.pack(side="right", padx=(0, 5))

        list_label_frame = ctk.CTkFrame(self.gpu_card, fg_color="transparent")
        list_label_frame.pack(side="top", fill="x", padx=15, pady=(5,0))
        list_label_frame.columnconfigure(0, minsize=105)
        list_label_frame.columnconfigure(1, minsize=105)
        
        self.lbl_clk_head = ctk.CTkLabel(list_label_frame)
        self.lbl_clk_head.grid(row=0, column=0, sticky="w", padx=5)
        self.lbl_vol_head = ctk.CTkLabel(list_label_frame)
        self.lbl_vol_head.grid(row=0, column=1, sticky="w", padx=5)

        scroll_frame = ctk.CTkScrollableFrame(self.gpu_card, fg_color="transparent")
        scroll_frame.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        scroll_frame.columnconfigure(0, minsize=105)
        scroll_frame.columnconfigure(1, minsize=105)
        self.points_container = scroll_frame

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
            # sudo 환경에서 안전하게 작동하도록 다시 절대 경로로 원복
            subprocess.run(["sudo", "/root/.local/bin/bc250-detect", "--frequency", str(mhz), "--vid", str(mv), "--keep"], check=True)
            self.load_cpu_config()
        except Exception as e: print(e)

    def apply_cpu_oc(self):
        try:
            mhz = int(self.cpu_clk_var.get())
            mv = int(float(self.cpu_vol_var.get()) * 1000)
            temp = int(self.cpu_temp_var.get())
            with open(self.overclock_conf_path, "w") as f:
                f.write(f"[overclock]\nfrequency={mhz}\nvid={mv}\nmax_temperature={temp}\nkeep=true\n")
            # sudo 환경에서 안전하게 작동하도록 다시 절대 경로로 원복
            subprocess.run(["sudo", "/root/.local/bin/bc250-apply", "--install", self.overclock_conf_path], check=True)
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
            f_entry = ctk.CTkEntry(self.points_container, width=80, justify="center")
            f_entry.insert(0, pt["frequency"])
            f_entry.grid(row=i, column=0, padx=5, pady=3, sticky="w")
            f_entry.bind("<FocusOut>", lambda e, idx=i, entry=f_entry: self.update_gpu_val(idx, "frequency", entry.get()))
            
            v_entry = ctk.CTkEntry(self.points_container, width=80, justify="center")
            v_entry.insert(0, pt["voltage"])
            v_entry.grid(row=i, column=1, padx=5, pady=3, sticky="w")
            v_entry.bind("<FocusOut>", lambda e, idx=i, entry=v_entry: self.update_gpu_val(idx, "voltage", entry.get()))
            
            btn_frame = ctk.CTkFrame(self.points_container, fg_color="transparent")
            btn_frame.grid(row=i, column=2, padx=2, pady=3, sticky="w")
            ctk.CTkButton(btn_frame, text="+", width=28, height=26, command=lambda idx=i: self.add_gpu_row(idx)).pack(side="left", padx=1)
            ctk.CTkButton(btn_frame, text="-", width=28, height=26, fg_color="#555555", hover_color="#666666", command=lambda idx=i: self.remove_gpu_row(idx)).pack(side="left", padx=1)

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
            toml = [f"[frequency-range]\nmin = {min(freqs)}\nmax = {max(freqs)}\n[timing.ramp-rates]\nnormal = 1\nburst = 50\n[timing]\nburst-samples = 60\ndown-events = 5\n[frequency-thresholds]\nadjust = 10\n[load-target]\nupper = 0.65\nlower = 0.50\n[temperature]\nthrottling = {self.gpu_throt_var.get()}\nthrottling_recovery = {self.gpu_recov_var.get()}"]
            for pt in self.gpu_safe_points: toml.append(f"[[safe-points]]\nfrequency = {pt['frequency']}\nvoltage = {pt['voltage']}")
            with open(self.config_toml_path, "w") as f: f.write("\n".join(toml) + "\n")
            subprocess.run(["sudo", "systemctl", "restart", "cyan-skillfish-governor-smu"], check=True)
        except Exception as e: print(e)

    def reboot_system(self): subprocess.run(["sudo", "reboot"])

if __name__ == "__main__":
    app = OCApp()
    app.mainloop()
