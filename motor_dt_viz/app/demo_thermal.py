# -*- coding: utf-8 -*-
"""demo_thermal.py — Phase 2: 모듈 A(발열 색상) 데모.

부품별 prim USD 를 열고 전용 머티리얼을 바인딩한 뒤, 열 모델 온도로 색·발광을 갱신한다.
회전은 기존에 검증된 토크 제어 루프를 그대로 쓴다 (정격 부하 → 약 1,170 rpm).

실행:
  C:\\ISSACS~1\\python.bat motor_dt_viz\\app\\demo_thermal.py --shots     # headless 스크린샷 4장
  C:\\ISSACS~1\\python.bat motor_dt_viz\\app\\demo_thermal.py --gui       # 실시간 확인
옵션:
  --opaque      하우징을 불투명으로 (기본: 반투명 — 내부 베어링이 보이게)
  --preview     UsdPreviewSurface 강제 (기본: OmniPBR 우선)
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
    with open(os.path.join(LOG_DIR, "demo_thermal_error.txt"), "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = _hook

ap = argparse.ArgumentParser()
ap.add_argument("--gui", action="store_true")
ap.add_argument("--shots", action="store_true")
ap.add_argument("--xray", action="store_true", help="하우징 전체 반투명")
ap.add_argument("--opaque", action="store_true", help="결함 시에도 엔드실드를 불투명 유지")
ap.add_argument("--preview", action="store_true", help="UsdPreviewSurface 강제")
ap.add_argument("--time_scale", type=float, default=120.0)
args = ap.parse_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": not args.gui, "width": 1600, "height": 900})
import carb  # noqa: E402

carb.settings.get_settings().set("/physics/cudaDevice", -1)

import numpy as np  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.prims import SingleArticulation  # noqa: E402
from isaacsim.core.utils.stage import get_current_stage, open_stage  # noqa: E402
from isaacsim.core.utils.types import ArticulationAction  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from omni.physx import get_physx_simulation_interface  # noqa: E402
from pxr import Gf, UsdGeom, UsdLux  # noqa: E402

from engine.config_loader import load  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402
from viz.material_driver import MaterialDriver  # noqa: E402

USD = os.path.join(ROOT, "assets", "motor_physics.usd")
open_stage(USD)

PHYS_HZ = 240
dt = 1.0 / PHYS_HZ
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60,
              physics_prim_path="/physicsScene")
stage = get_current_stage()

# ------------------------------------------------------------------ 조명·카메라
dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
dome.CreateIntensityAttr(400.0)
dome.CreateColorAttr(Gf.Vec3f(0.12, 0.14, 0.18))
key = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
key.CreateIntensityAttr(1800.0)
UsdGeom.Xformable(key).AddRotateXYZOp().Set(Gf.Vec3f(-40, 25, 0))
fill = UsdLux.DistantLight.Define(stage, "/World/FillLight")
fill.CreateIntensityAttr(700.0)
UsdGeom.Xformable(fill).AddRotateXYZOp().Set(Gf.Vec3f(-55, -130, 0))
for L in (dome, key, fill):
    UsdLux.ShadowAPI.Apply(L.GetPrim()).CreateShadowEnableAttr(False)

# DE 베어링(x≈0.136)이 잘 보이는 3/4 뷰
set_camera_view(eye=[-0.55, -0.95, 0.42], target=[0.32, 0.0, 0.0])

world.reset()

# ------------------------------------------------------------------ 머티리얼
driver = MaterialDriver(stage, prefer_omnipbr=not args.preview,
                        update_hz=float(load("electrical")["rms"]["update_hz"]))
setup_info = driver.setup()
# 기본은 불투명(모터 외형 유지). 결함이 나면 해당 부위 엔드실드만 반투명으로 바꿔
# 내부 베어링의 발열 색이 비치게 한다 — 어디가 문제인지 한눈에 보이도록.
XRAY_OPACITY = 0.40
if args.xray:
    driver.housing_transparent(True, opacity=XRAY_OPACITY)
_endshield_xray = False
print("[demo] 머티리얼:", json.dumps(setup_info, ensure_ascii=False), flush=True)

# ------------------------------------------------------------------ 구동(회전)
art = SingleArticulation(prim_path="/World/Motor", name="motor")
art.initialize()
ctrl = art.get_articulation_controller()
av = art._articulation_view
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0]))
av.set_max_efforts(np.array([[1.0e4]]))
av.set_joint_velocities(np.array([[0.0]]))

motor_cfg = load("motor")
V = lambda d: d["value"] if isinstance(d, dict) else d  # noqa: E731
w_sync = float(V(motor_cfg["rating"]["sync_rpm"])) * 2 * math.pi / 60
s_rated = float(V(motor_cfg["rating"]["slip"]))
T_rated = float(V(motor_cfg["rating"]["torque_Nm"]))
T_max = T_rated * 2.5
b_mech = float(V(load("thermal")["torque"] if "torque" in load("thermal") else {"value": 0.015}))

tm = ThermalModel()
THRESHOLDS = {k: tm.thresholds(k) for k in tm.node_keys}   # 부품별 허용 온도 기준 색 정규화
sim = get_physx_simulation_interface()

# 시나리오: 정상 정착 → 베어링 결함 → 해제. 각 구간을 외부 캡처가 가능하도록 넉넉히 유지한다.
PHASES = [(0.0, 30.0, [], "정상 운전"),
          (30.0, 80.0, ["bearing_de_fault"], "DE 베어링 결함"),
          (80.0, 130.0, [], "결함 해제")]
SHOTS = {28.0: "p2_01_normal", 42.0: "p2_02_fault_rising", 78.0: "p2_03_fault_peak", 128.0: "p2_04_recovered"}
STATUS_FILE = os.path.join(LOG_DIR, "demo_thermal_status.json")

t_wall = 0.0
_t0 = time.time()
_fps_hist = []
sub = max(1, int(round((1 / 60) / dt)))
records = []
shot_done: set[str] = set()


def faults_at(t: float) -> tuple[list[str], str]:
    for a, b, f, label in PHASES:
        if a <= t < b:
            return f, label
    return [], "종료"


def capture(name: str) -> str | None:
    """뷰포트를 PNG 로 저장 (headless 에서도 동작하도록 렌더를 여러 번 돌린다)."""
    path = os.path.join(OUT_DIR, name + ".png")
    try:
        import omni.kit.viewport.utility as vu
        vp = vu.get_active_viewport()
        for _ in range(12):
            world.render()
        vu.capture_viewport_to_file(vp, path)
        for _ in range(40):          # 비동기 저장 완료 대기
            world.render()
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                break
        return path if os.path.exists(path) else None
    except Exception as e:
        print("[demo] 캡처 실패:", e, flush=True)
        return None


while simulation_app.is_running():
    faults, label = faults_at(t_wall)
    # 회전: 토크-슬립 선형 근사 + 정격 부하
    for _ in range(sub):
        w = float(art.get_joint_velocities()[0])
        s = (w_sync - w) / w_sync
        T_motor = max(-T_max, min(T_rated * s / s_rated, T_max))
        T_load = -T_rated * (1.0 if w > 1.0 else max(w, 0.0))
        ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T_motor + T_load - 0.015 * w])))
        sim.simulate(dt, t_wall)
        sim.fetch_results()

    st = tm.step(dt_sim_s=(1 / 60) * args.time_scale, load=1.0, faults=faults, use_duty_cycle=False)

    # 결함 부위 하우징만 선택적으로 투명화 (발표 시 내부 발열이 보이게)
    if not args.opaque and not args.xray:
        want_xray = ("bearing_de_fault" in faults) and st.stage["bearing_de"] in ("warning", "danger")
        if want_xray != _endshield_xray:
            driver.set_opacity(["endshield_de"], XRAY_OPACITY if want_xray else 1.0)
            _endshield_xray = want_xray
    driver.update(st.temperature_C, st.stage, t_wall, thresholds=THRESHOLDS)
    world.render()
    t_wall += 1 / 60

    if int(t_wall * 60) % 30 == 0:
        rpm = float(art.get_joint_velocities()[0]) * 60 / (2 * math.pi)
        wall = time.time() - _t0
        fps = (t_wall / wall * 60.0) if wall > 0.5 else 0.0     # 목표 60 프레임/초 대비 실제
        _fps_hist.append(fps)
        rec = {"t": round(t_wall, 2), "wall_s": round(wall, 2), "fps": round(fps, 1),
               "phase": label, "rpm": round(rpm, 1),
               **{k: round(v, 1) for k, v in st.temperature_C.items()},
               "stage_bearing_de": st.stage["bearing_de"]}
        records.append(rec)
        # 외부 캡처 도구가 현재 단계를 알 수 있도록 상태를 파일로 노출
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({**rec, "shot_due": next((n for tt, n in sorted(SHOTS.items())
                                                if n not in shot_done and t_wall >= tt), None)},
                      f, ensure_ascii=False)

    if args.shots:
        for tm_shot, name in sorted(SHOTS.items()):
            if name not in shot_done and t_wall >= tm_shot:
                # GUI 모드에서는 외부 캡처 도구(ffmpeg)가 status 파일을 보고 찍는다.
                p = None if args.gui else capture(name)
                shot_done.add(name)
                print(f"[demo] t={t_wall:.1f}s {label} bearing_de={st.temperature_C['bearing_de']:.1f}°C "
                      f"({st.stage['bearing_de']}) → {p or 'external capture'}", flush=True)
        if len(shot_done) == len(SHOTS) and not args.gui:
            break
    if t_wall > PHASES[-1][1]:
        break

with open(os.path.join(LOG_DIR, "demo_thermal.json"), "w", encoding="utf-8") as f:
    steady = [f for f in _fps_hist[5:] if f > 0]
    json.dump({"backend": driver.backend, "setup": setup_info,
               "fps": {"mean": round(sum(steady) / len(steady), 1) if steady else None,
                       "min": round(min(steady), 1) if steady else None,
                       "target": 30.0, "pass": bool(steady and min(steady) >= 30.0)},
               "records": records}, f, ensure_ascii=False, indent=2)
print("[demo] DONE", flush=True)
simulation_app.close()
