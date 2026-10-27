# -*- coding: utf-8 -*-
"""ui_font_probe.py — omni.ui 에서 한글 라벨이 그려지는지 실측 (패널 Q1 사전 조사). Isaac python 으로 GUI 실행:
  C:\\ISSACS~1\\python.bat tools\\live\\ui_font_probe.py [--font C:/Windows/Fonts/malgun.ttf] [--out logs/ui_font_probe.png]
창 하나에 (a) 기본 스타일 한글 (b) style font 지정 한글 (c) 영문 라벨을 띄우고 3 s 뒤 화면(PIL ImageGrab, 창 영역)을 저장한다.
"""
import argparse
import os
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("--font", default="C:/Windows/Fonts/malgun.ttf")
ap.add_argument("--out", default="logs/ui_font_probe.png")
ap.add_argument("--app_font", action="store_true", help="/app/font/file 설정으로 앱 전체 폰트를 바꿔 본다")
a = ap.parse_args()

from isaacsim import SimulationApp  # noqa: E402
cfg = {"headless": False, "width": 1280, "height": 720}
if a.app_font:
    cfg["extra_args"] = [f"--/app/font/file={a.font}"]
app = SimulationApp(cfg)
import omni.ui as ui  # noqa: E402

w = ui.Window("VIGENT font probe", width=620, height=360)
w.position_x, w.position_y = 40, 80
PROBES = {}
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ui.ko_text import ko_png_size, render_text
path, pw, ph = ko_png_size("(d) 전기 결함 주입 · 단락 턴수 4 / 32 턴 · 판정 경고", 18)
print("[font_probe] png", path, pw, ph, os.path.getsize(path), flush=True)
with w.frame:
    with ui.VStack(spacing=8):
        try:
            PROBES["label"] = ui.Label("(c) ASCII reference label", style={"font_size": 18})
            PROBES["int"] = ui.Image(path, width=pw, height=ph)
            PROBES["pixel"] = ui.Image(path, width=ui.Pixel(pw), height=ui.Pixel(ph))
            PROBES["nosize_h"] = ui.Image(path, height=ph)
            img = render_text("(e) ByteImageProvider 비트맵", 18)
            prov = ui.ByteImageProvider(); prov.set_bytes_data(list(img.tobytes()), [img.width, img.height])
            PROBES["provider"] = ui.ImageWithProvider(prov, width=img.width, height=img.height)
            PROBES["x2"] = ui.Image(path, width=pw * 2, height=ph * 2)
            print("[font_probe] widgets built", flush=True)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc(); print("[font_probe] BUILD ERROR", repr(e), flush=True)
t0 = time.time()
while app.is_running() and time.time() - t0 < 4.0:
    app.update()
print(f"[font_probe] window {w.width}x{w.height} visible={w.visible} frame computed {w.frame.computed_width:.0f}x{w.frame.computed_height:.0f}", flush=True)
for k, wd in PROBES.items():
    try:
        print(f"[font_probe] {k}: computed {wd.computed_width:.0f}x{wd.computed_height:.0f} at ({wd.screen_position_x:.0f},{wd.screen_position_y:.0f}) visible={wd.visible}", flush=True)
    except Exception as e:
        print(f"[font_probe] {k}: ?", e, flush=True)
try:
    import ctypes
    from ctypes import wintypes
    from PIL import ImageGrab
    u = ctypes.windll.user32
    hwnd = u.FindWindowW(None, "Isaac Sim Python 4.5.0")
    r = wintypes.RECT()
    if hwnd and u.GetWindowRect(hwnd, ctypes.byref(r)):
        u.SetForegroundWindow(hwnd); time.sleep(0.3)
        for _ in range(5):
            app.update()
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    else:
        img = ImageGrab.grab()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    img.save(a.out)
    print("[font_probe] saved", a.out, img.size, flush=True)
except Exception as e:  # noqa: BLE001
    print("[font_probe] grab failed:", e, flush=True)
app.close()
