# -*- coding: utf-8 -*-
"""demo_current.py — Phase 3: 모듈 B(전류 흐름) 데모.

공급 케이블 3상 + 고정자 권선 오버레이 + ITSC 단락 루프를 절차 생성하고,
전류 입자를 흘리며 상태(과전류 빨강 / 정상 초록 / 저전류 파랑)로 칠한다.
HUD 에 상별 I_rms 와 I₂/I₁ 을 표시한다.

실행:
  C:\\ISSACS~1\\python.bat motor_dt_viz\\app\\demo_current.py --gui
  C:\\ISSACS~1\\python.bat motor_dt_viz\\app\\demo_current.py --gui --shots
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")
LOG_DIR = os.path.join(ROOT, "logs")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def _hook(t, v, tb):
    with open(os.path.join(LOG_DIR, "demo_current_error.txt"), "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = _hook

ap = argparse.ArgumentParser()
ap.add_argument("--gui", action="store_true")
ap.add_argument("--shots", action="store_true")
ap.add_argument("--xray", action="store_true", help="하우징 반투명 (권선 오버레이가 보이게)")
ap.add_argument("--quick", action="store_true", help="케이스당 12초로 단축")
args = ap.parse_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": not args.gui, "width": 1600, "height": 900})
import carb  # noqa: E402

carb.settings.get_settings().set("/physics/cudaDevice", -1)

import numpy as np  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.utils.stage import get_current_stage, open_stage  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from pxr import Gf, UsdGeom, UsdLux  # noqa: E402

from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from viz.colormap import ElectricalColormap  # noqa: E402
from viz.current_particles import CurrentParticles  # noqa: E402
from viz.current_paths import CurrentPathBuilder  # noqa: E402
from viz.material_driver import MaterialDriver  # noqa: E402

open_stage(os.path.join(ROOT, "assets", "motor_physics.usd"))
world = World(stage_units_in_meters=1.0, physics_dt=1 / 240, rendering_dt=1 / 60,
              physics_prim_path="/physicsScene")
stage = get_current_stage()

# ------------------------------------------------------------------ 조명·카메라
dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
dome.CreateIntensityAttr(350.0)
dome.CreateColorAttr(Gf.Vec3f(0.10, 0.12, 0.16))
key = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
key.CreateIntensityAttr(1500.0)
UsdGeom.Xformable(key).AddRotateXYZOp().Set(Gf.Vec3f(-40, 25, 0))
for L in (dome, key):
    UsdLux.ShadowAPI.Apply(L.GetPrim()).CreateShadowEnableAttr(False)
# 케이블(전원 x≈−0.53, z≈0.97) ~ 팬커버(x 0.89) 전체가 프레임에 들어오는 3/4 뷰
set_camera_view(eye=[-1.70, -2.30, 1.45], target=[0.18, 0.0, 0.28])

world.reset()

# ------------------------------------------------------------------ 경로·입자
builder = CurrentPathBuilder(stage)
made = builder.build_all()
particles = CurrentParticles(stage, builder)
tracks = builder.names("cable") + builder.names("winding") + ["short_loop"]
particles.attach(tracks)

cm = CurrentModel()
ecmap = ElectricalColormap()
driver = MaterialDriver(stage, prefer_omnipbr=True)
driver.setup()
driver.housing_transparent(True, opacity=0.30 if args.xray else 0.68)  # 권선이 보이도록 기본 반투명

hud = None
if args.gui:
    try:
        from viz.hud import MotorHUD
        hud = MotorHUD()
    except Exception as e:
        print("[demo] HUD 생성 실패:", e, flush=True)

i_line = cm.motor.rated_current("rated_line_A")
i_phase = cm.motor.rated_current("rated_phase_A")
RATED = {**{f"cable_{p}": i_line for p in "ABC"}, **{f"winding_{p}": i_phase for p in "ABC"},
         "short_loop": i_phase}
SLOWMO = float(load("electrical")["slowmo"]["factor"])

# ------------------------------------------------------------------ 시나리오
# 케이스 지속시간: 외부 캡처 도구가 각 구간을 놓치지 않도록 넉넉히 (--quick 로 단축)
_D = 12.0 if "--quick" in sys.argv else 45.0
CASES = [("healthy", _D), ("itsc_4turn", _D), ("itsc_12turn", _D),
         ("overload", _D * 0.8), ("single_phasing", _D * 0.8), ("no_load", _D * 0.6)]
# HUD 는 영문 표기 (omni.ui 한글 미지원)
CASE_EN = {"healthy": "Healthy", "itsc_4turn": "Inter-turn short (4 turns)",
           "itsc_12turn": "Inter-turn short (12 turns)", "overload": "Overload 135%",
           "single_phasing": "Single phasing (phase R lost)", "no_load": "No load",
           "voltage_unbalance": "Supply voltage unbalance"}
SHOTS = {"healthy": "p3_01_healthy", "itsc_4turn": "p3_02_itsc4", "itsc_12turn": "p3_03_itsc12",
         "overload": "p3_04_overload", "single_phasing": "p3_05_single_phasing"}
STATUS_FILE = os.path.join(LOG_DIR, "demo_current_status.json")

fs_analyze = cm.f0 * 256
t_analyze = np.arange(0, 4 / cm.f0, 1 / fs_analyze)      # 분석용 4주기 윈도우

t_wall = 0.0
_t0 = time.time()
records = []
shot_done: set[str] = set()
case_idx = 0
case_t = 0.0
_fps = []

while simulation_app.is_running():
    case, dur = CASES[case_idx]
    # --- 전류 상태 (슬로모션 시간축으로 파형 샘플링) ---
    t_slow = t_wall * SLOWMO
    state_line = cm.analyze(t_analyze, cm.waveform(t_analyze + t_slow, case, "rated_line_A"),
                            case, "rated_line_A")
    state_phase = cm.analyze(t_analyze, cm.waveform(t_analyze + t_slow, case, "rated_phase_A"),
                             case, "rated_phase_A")

    inst_line = cm.sample(t_slow, case, "rated_line_A")
    inst_phase = cm.sample(t_slow, case, "rated_phase_A")
    loop = cm.short_loop(case)

    cur = {}
    st = {}
    for i, ph in enumerate("ABC"):
        cur[f"cable_{ph}"] = inst_line[i]
        st[f"cable_{ph}"] = state_line.status[i]
        cur[f"winding_{ph}"] = inst_phase[i]
        st[f"winding_{ph}"] = state_phase.status[i]
    if loop:
        amp = float(loop["current_pu"]) * i_phase
        cur["short_loop"] = amp * math.sin(2 * math.pi * cm.f0 * t_slow)
        st["short_loop"] = "short_loop"
    else:
        cur["short_loop"] = 0.0
        st["short_loop"] = "normal"

    # --- 경로 색 + 입자 ---
    for name in tracks:
        builder.set_color(name, ecmap.sample(st[name], t_wall)["diffuse"])
    builder.set_visible("short_loop", loop is not None)
    particles.update(1 / 60, cur, st, t_wall, RATED)

    if hud:
        hud.update_current(state_line)
        hud.update_scenario(CASE_EN.get(case, case),
                            "Cable = line current basis / Winding = phase current basis (delta)")

    world.render()
    t_wall += 1 / 60
    case_t += 1 / 60

    if int(t_wall * 60) % 30 == 0:
        wall = time.time() - _t0
        fps = t_wall / wall * 60.0 if wall > 0.5 else 0.0
        _fps.append(fps)
        rec = {"t": round(t_wall, 2), "case": case, "fps": round(fps, 1),
               "i2i1": round(state_line.i2_over_i1, 4),
               "rms_line": [round(v, 1) for v in state_line.rms_A],
               "status": list(state_line.status), "particles": particles.count}
        records.append(rec)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)

    if args.shots and case in SHOTS and SHOTS[case] not in shot_done and case_t > 6.0:
        shot_done.add(SHOTS[case])
        print(f"[demo] {case}: I2/I1={state_line.i2_over_i1:.4f} "
              f"rms={[round(v,1) for v in state_line.rms_A]} status={state_line.status}", flush=True)

    if case_t >= dur:
        case_idx += 1
        case_t = 0.0
        if case_idx >= len(CASES):
            break

steady = [f for f in _fps[5:] if f > 0]
with open(os.path.join(LOG_DIR, "demo_current.json"), "w", encoding="utf-8") as f:
    json.dump({"paths": made, "tracks": tracks, "particle_count": particles.count,
               "fps": {"mean": round(sum(steady) / len(steady), 1) if steady else None,
                       "min": round(min(steady), 1) if steady else None, "pass": bool(steady and min(steady) >= 30)},
               "records": records}, f, ensure_ascii=False, indent=2)
print("[demo] DONE", flush=True)
simulation_app.close()
