import os
import re
import subprocess
from decimal import Decimal, ROUND_HALF_DOWN

SCALE_MIN = -60   # bc250_limits.scale_min에 맞춰 조정
SCALE_MAX = 20    # bc250_limits.scale_max에 맞춰 조정

def parse_volt_to_mv(v_text: str) -> int:
    s = v_text.strip().replace(",", ".").replace(" ", "")
    v = float(s)
    return int(round(v * 1000))

def vid_predict(clock: int, scale: int) -> float:
    if clock < 3000:
        raise ValueError("clock must be >= 3000")
    p = -1.519 + scale * 0.004325
    q = 2800.0 - (scale * 10.0)
    return 0.0003 * clock * clock + p * clock + q

def nearest_scale_for_vid(clock: int, target_mv: int, scale_min: int, scale_max: int, cur_scale: int = 0) -> int:
    candidates = range(scale_min, scale_max + 1)
    # 오차 최소, 동률이면 현재 scale과 가까운 값 우선
    best = min(
        candidates,
        key=lambda s: (abs(vid_predict(clock, s) - target_mv), abs(s - cur_scale))
    )
    return int(best)

def round_half_down_int(x: float) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_DOWN))

def apply_cpu_oc(self):
    try:
        mhz = int(self.cpu_clk_var.get())
        temp = int(self.cpu_temp_var.get())
        target_mv = parse_volt_to_mv(self.cpu_vol_var.get())

        cur_scale = getattr(self, "current_scale", -30)
        scale = nearest_scale_for_vid(mhz, target_mv, SCALE_MIN, SCALE_MAX, cur_scale=cur_scale)

        # 선택된 scale 기준 예측 전압 표시(선택사항)
        pred_mv = vid_predict(mhz, scale)
        self.cpu_vol_var.set(f"{pred_mv/1000:.3f}")

        with open(self.overclock_conf_path, "w") as f:
            f.write(
                "[overclock]\n"
                f"frequency = {mhz}\n"
                f"scale = {scale}\n"
                f"max_temperature = {temp}\n"
            )

        subprocess.run(["sudo", "bc250-apply", "--install", self.overclock_conf_path], check=True)
        subprocess.run(["sudo", "systemctl", "restart", "bc250-smu-oc"], check=True)

        self.current_scale = scale
        print(f"Applied: {mhz} MHz, target {target_mv} mV -> scale {scale}, predicted {pred_mv:.1f} mV")

    except Exception as e:
        print(f"apply_cpu_oc failed: {e}")

