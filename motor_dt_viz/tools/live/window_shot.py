# -*- coding: utf-8 -*-
"""window_shot.py — 제목으로 창을 찾아 앞으로 올리고 그 영역을 PNG 로 저장 (시스템 파이썬 + PIL ImageGrab, 데스크톱 캡처 — 캡처 중 다른 창을 올리면 그 창이 찍힌다).
  py -3.12 -X utf8 tools/live/window_shot.py --title "Isaac Sim Python 4.5.0" --out docs/isaac_panel_q1/img/panel_healthy.png [--crop x,y,w,h]
"""
import argparse
import ctypes
import os
import time
from ctypes import wintypes

from PIL import ImageGrab

ap = argparse.ArgumentParser()
ap.add_argument("--title", default="Isaac Sim Python 4.5.0")
ap.add_argument("--out", required=True)
ap.add_argument("--crop", default="", help="창 클라이언트 기준 x,y,w,h (비우면 창 전체)")
ap.add_argument("--delay", type=float, default=0.8)
a = ap.parse_args()
u = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:  # noqa: BLE001
    pass
hwnd = u.FindWindowW(None, a.title)
if not hwnd:
    raise SystemExit(f"window not found: {a.title}")
u.ShowWindow(hwnd, 9)
u.SetForegroundWindow(hwnd)
time.sleep(a.delay)
r = wintypes.RECT()
u.GetWindowRect(hwnd, ctypes.byref(r))
box = (r.left, r.top, r.right, r.bottom)
img = ImageGrab.grab(bbox=box, all_screens=True)
if a.crop:
    x, y, w, h = [int(v) for v in a.crop.split(",")]
    img = img.crop((x, y, x + w, y + h))
os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
img.save(a.out)
print("[window_shot]", a.out, img.size, box, flush=True)
