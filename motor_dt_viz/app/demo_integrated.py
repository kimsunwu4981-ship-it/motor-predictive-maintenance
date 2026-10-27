# -*- coding: utf-8 -*-
"""demo_integrated.py — 전기 결함 전용 데모 + 전기 결함 조작 패널(Q1) + 자동 재생 (2026-10-27: 기계·통합 모드는 _legacy/app/demo_integrated_modes.py, 파일 이름은 이력 호환으로 유지).

모듈 A(발열 색상) + 모듈 B(전류 흐름)를 한 화면에서 구동한다.
통합 모드에서는 모듈 B 의 상전류가 모듈 A 의 권선 동손(I²R) 입력이 된다
  → ITSC 발생 → 과전류(빨간 흐름) → 수십 초 뒤 권선 과열 (CLAUDE.md §6.3 핵심 스토리)

실행:
  C:\\ISSACS~1\\python.bat motor_dt_viz\\app\\demo_integrated.py --gui
  C:\\ISSACS~1\\python.bat motor_dt_viz\\app\\demo_integrated.py --gui --autoplay   # 즉시 자동 재생
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
LOG_DIR = os.path.join(ROOT, "logs")
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


def _hook(t, v, tb):
    with open(os.path.join(LOG_DIR, "demo_integrated_error.txt"), "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = _hook

ap = argparse.ArgumentParser()
ap.add_argument("--gui", action="store_true")
ap.add_argument("--autoplay", action="store_true", help="기동 직후 자동 재생 시작")
ap.add_argument("--mode", default="electrical",
                help="전기 전용(패널 Q1, 2026-10-27). electrical 외 값은 경고 뒤 electrical 로 강제 — 기계·통합 모드 코드는 _legacy/app/demo_integrated_modes.py")
ap.add_argument("--max_s", type=float, default=0.0, help="지정 시간 후 종료 (0=무제한)")
ap.add_argument("--profile", action="store_true", help="구간별 소요 시간을 측정해 로그에 남긴다")
ap.add_argument("--low", action="store_true",
                help="저사양 PC 프리셋 (해상도·입자 수·물리 서브스텝 절반)")
ap.add_argument("--record", metavar="MP4",
                help="ffmpeg 로 Isaac Sim 창을 녹화하고 영상↔로그 오프셋을 기록한다")
ap.add_argument("--no_timecode", action="store_true",
                help="HUD 타임코드를 숨긴다 (오프셋 확정 후 발표용 녹화에 쓴다)")
ap.add_argument("--log_subdir", default="", help="CSV·녹화 메타를 logs/<subdir>/ 에 둔다 (예: panel_q1)")
ap.add_argument("--motor", default="M1", metavar="M1",
                help="모터 라이브러리 ID (기본 M1 = 현대 HLP-2.2/4, 유일한 등록 모터). 열회로·전류 모델·진동 규격·HUD 문구를 그 모터로")
ap.add_argument("--switch_seq", metavar="mode:sec,...", help="(이력) 모드 전환 검증 — 전기 전용 빌드에서는 무시")
ap.add_argument("--panel_selftest", type=int, default=0, metavar="N", help="패널 Q1 지연 자동 측정: 턴수 0→4→12→0 을 N 회 (USD 속성 경로) — logs/<subdir>/panel_selftest.json")
ap.add_argument("--panel_selftest_hold", type=float, default=4.0, help="자동 측정에서 각 턴수 값을 유지하는 시간 [s] (스크린샷용으로 길게)")
ap.add_argument("--panel_burst", action="store_true", help="2 Hz 제한 검사: t≈3 s 부터 3 s 동안 매 프레임 턴수를 바꿔 쓰고 마지막 값(4)이 반영되는지 로그")
ap.add_argument("--no_panel_notice", action="store_true", help="패널 상단 '모드 항목 삭제됨' 안내줄 숨김")
ap.add_argument("--view_probe", default="", metavar="MODE", help="진단: t≈8 s 에 패널 버튼과 같은 경로로 뷰를 MODE 로 바꾸고 그 프레임·다음 3 프레임의 USD variant 선택값을 로그 (fix/panel-view-switch §1)")
ap.add_argument("--live", action="store_true",
                help="라이브 모드: WebSocket 브리지(config/live.yaml)로 state 송신·명령 수신. 없으면 기존 동작과 완전히 같다")
ap.add_argument("--live_port", type=int, default=0, help="live.yaml 의 포트를 덮어쓴다 (0 = config)")
ap.add_argument("--preset", default="", metavar="demo|full", help="config/render_demo.yaml 프리셋 (해상도·RTX 모드·물리 서브스텝·입자·뷰포트). --low 보다 우선")
# P4 (2026-10-21): M1 전체 3D 모델 장면 — 22 kW USD 는 숨기고(물리는 그대로 rpm 생성) assets/motors/M1/M1.usd 에 상태 JSON 값만 색·회전으로 매핑 (viz/m1_model.py)
ap.add_argument("--m1_model", action="store_true", default=None, help="M1 전체 3D 모델(assets/motors/M1/M1.usd)을 장면에 올리고 22 kW 모델·전류 경로는 숨긴다 (--motor M1 이면 기본 켜짐)")
ap.add_argument("--no_m1_model", action="store_true", help="M1 모델을 쓰지 않고 22 kW USD 그대로 (이력 비교용)")
ap.add_argument("--view", default=None, choices=("full", "cutaway", "windings_only", "half_translucent", "half_translucent_front"),
                help="--m1_model 의 USD variant view (half_translucent*: 한쪽 반을 반투명으로 — 자르지 않음, H2). 기본 full, 스트림 송출 때는 half_translucent")
# 레이아웃 A (2026-10-27): 뷰포트 JPEG 를 WebSocket(config/live.yaml server.stream_port, 127.0.0.1) 으로 송출 — --live 면 기본 켜짐 (--no_stream 으로 끔)
ap.add_argument("--stream", action="store_true", default=None, help="뷰포트 JPEG 스트림 송출 (viz/stream_viewport.py). --live 가 있으면 기본 켜짐")
ap.add_argument("--no_stream", action="store_true", help="--live 여도 스트림을 켜지 않는다")
ap.add_argument("--stream_fps", type=float, default=30.0, help="스트림 캡처 주기 [fps] (기본 30)")
ap.add_argument("--stream_size", type=int, nargs=2, default=(1280, 720), metavar=("W", "H"), help="스트림 해상도 (기본 1280 720, 뷰포트와 다르면 리사이즈)")
ap.add_argument("--stream_quality", type=int, default=80, help="JPEG 품질 (기본 80)")
ap.add_argument("--judge_stream", default="auto", choices=("auto", "simulation", "live"),
                help="판정 정책 스트림 라벨(config/thresholds.yaml judgment.provisional_policy): auto = --live 면 live(실측 정책, provisional 지표 advisory) 아니면 simulation. "
                     "레이아웃 A 상태 보드처럼 Isaac 합성 신호를 배치 verify 와 같은 정책으로 판정하려면 simulation")
ap.add_argument("--cam", default="", metavar="PRESET", help="--m1_model 기본 카메라 프리셋(iso|side|close|fault_focus|bearing_de|front_shaft|rotor_closeup). 비우면 기존 wide(=iso)")
ap.add_argument("--m1_shots", default="", metavar="DIR", help="--m1_model: 전기 시나리오 재생 중 스크린샷 6장을 DIR 에 저장")
ap.add_argument("--mount", default="B3", choices=("B3", "B35"), help="--m1_model 의 USD variant mount (B3 발 장착 기본 / B35 플랜지)")
# V1 검증 로깅 훅 (2026-10-21, tools/verify): 값은 전부 기존 엔진 — 기록만 늘린다
ap.add_argument("--verify_dir", default="", metavar="DIR", help="검증 로그: DIR/state.csv(10 Hz 전 필드)·events.csv(판정 변화)·waveform_<t>_<pre|post>_<case>.csv(장면 전환 전후 1 s·2 kHz)·meta.json")
ap.add_argument("--inherent_angle_deg", type=float, default=None, help="고유 비대칭 I₂ 위상 [deg] — 이 실행의 메모리 설정만 덮어쓴다 (electrical.yaml 불변, 민감도 0/90/180° 용)")
ap.add_argument("--scenario_yaml", default="", metavar="PATH", help="검증 전용 시나리오 파일(steps 포함)로 자동 재생 — 기존 장면 파일 불변")
ap.add_argument("--shot_plan", default="", help="--m1_shots 캡처 계획을 직접 지정: 't:view:cam:file;t:view:cam:file' (D3 tools/viz/shot_with_hud.py)")
# 보고용 미디어 팩 (2026-10-26, tools/media): 캡처 전용 인자 — 장면·엔진 불변
ap.add_argument("--res", type=int, nargs=2, default=None, metavar=("W", "H"), help="창(뷰포트) 해상도 덮어쓰기 (예: 1920 1080, 2560 1440) — 캡처용")
ap.add_argument("--capture_layout", action="store_true", help="캡처용 레이아웃: 창 클라이언트 영역을 --res 크기로 (0,0) 에 맞추고 Kit 패널(Stage/Content/Console/툴바)·제어 패널을 숨긴다. 장면·엔진 불변")
ap.add_argument("--cam_plan", default="", help="카메라·뷰 일정 't:view:cam;…' — cam 은 프리셋 이름 또는 orbit(축 중심 360°/20 s). 그 시각부터 다음 항목까지 적용 (--m1_model)")
args = ap.parse_args()
if args.mode != "electrical":
    print(f"[demo] WARNING: --mode {args.mode} is not supported in the electrical-only build - forcing electrical", flush=True)
    args.mode = "electrical"
if args.m1_model is None:
    args.m1_model = (args.motor == "M1") and not args.no_m1_model      # 파트 C: M1 이 기본 모터·기본 모델
STREAM_ON = bool(args.stream) or (bool(args.live) and not args.no_stream)
if args.view is None:
    args.view = "half_translucent" if STREAM_ON else "full"          # 스트림 기본 뷰 = 반절 반투명 (레이아웃 A). --view 를 주면 그대로
PRESET = None
if args.preset:
    import yaml as _yaml
    with open(os.path.join(ROOT, "config", "render_demo.yaml"), encoding="utf-8") as _f:
        PRESET = _yaml.safe_load(_f)["presets"][args.preset]
    print(f"[demo] preset {args.preset}: {PRESET}", flush=True)

from isaacsim import SimulationApp  # noqa: E402

# 프로파일 실측: render 8.9 ms / physics 2.6 ms / 나머지 2.1 ms (RTX 4060 기준 68.9 fps).
# 병목은 렌더링이므로 --low 는 해상도를 먼저 낮추고, 물리 서브스텝과 입자 수를 함께 줄인다.
_W, _H = (1280, 720) if args.low else (1600, 900)
PHYSICS_SUBSTEPS = 2 if args.low else 4
if PRESET:
    _W, _H = int(PRESET["width"]), int(PRESET["height"]); PHYSICS_SUBSTEPS = int(PRESET["physics_substeps"])
if args.res:
    _W, _H = int(args.res[0]), int(args.res[1])          # 캡처용 해상도 (미디어 팩)
PHYSICS_DT = 1.0 / (60 * PHYSICS_SUBSTEPS)         # 서브스텝을 줄여도 프레임당 총 1/60 s 는 유지
PARTICLES_PER_PATH = 12 if args.low else None      # None = config 값 사용
if PRESET:
    PARTICLES_PER_PATH = PRESET.get("particles_per_path")

simulation_app = SimulationApp({"headless": not args.gui, "width": _W, "height": _H})
import carb  # noqa: E402

carb.settings.get_settings().set("/physics/cudaDevice", -1)
if PRESET:
    carb.settings.get_settings().set("/rtx/rendermode", str(PRESET.get("render_mode", "RaytracedLighting")))   # RTX Real-Time
    for _ext in PRESET.get("disable_extensions") or []:
        try:
            import omni.kit.app as _oka
            _oka.get_app().get_extension_manager().set_extension_enabled_immediate(_ext, False)
        except Exception as _e:
            print("[demo] extension disable failed:", _ext, _e, flush=True)

import numpy as np  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.prims import SingleArticulation  # noqa: E402
from isaacsim.core.utils.stage import get_current_stage, open_stage  # noqa: E402
from isaacsim.core.utils.types import ArticulationAction  # noqa: E402
from isaacsim.core.utils.viewports import set_camera_view  # noqa: E402
from omni.physx import get_physx_simulation_interface  # noqa: E402
from pxr import Gf, UsdGeom, UsdLux  # noqa: E402

from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.fault_injector import FaultInjector  # noqa: E402
from engine.scenario_player import ScenarioPlayer, fill_vars  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402
from engine import motor_library as ml  # noqa: E402

# ------------------------------------------------------------------ 모터 선택 (라이브러리)
MOTOR = ml.load_motor(args.motor) if args.motor else None
TH_CFG = ml.thermal_cfg(MOTOR) if MOTOR else None
EL_CFG = ml.electrical_cfg(MOTOR) if MOTOR else None
GEOM_SCALE = float(MOTOR.geometry_scale) if MOTOR else 1.0
VIB_STD = str(MOTOR.vibration["standard"]).split(" (")[0] if MOTOR else "ISO 20816-3"
if MOTOR:
    print(f"[demo] motor library {MOTOR.id}: {MOTOR.name}, geometry x{GEOM_SCALE}, {VIB_STD}", flush=True)
if args.inherent_angle_deg is not None and EL_CFG is not None:
    EL_CFG.setdefault("inherent", {})["angle_deg"] = float(args.inherent_angle_deg)     # 이 프로세스의 dict 만 — 파일은 그대로
    print(f"[verify] inherent angle override {args.inherent_angle_deg:g} deg (memory only)", flush=True)
from viz.colormap import ElectricalColormap  # noqa: E402
from viz.current_particles import CurrentParticles  # noqa: E402
from viz.current_paths import CurrentPathBuilder  # noqa: E402
from viz.material_driver import MaterialDriver  # noqa: E402

# ------------------------------------------------------------------ 스테이지
open_stage(os.path.join(ROOT, "assets", "motor_physics.usd"))
world = World(stage_units_in_meters=1.0, physics_dt=1 / 240, rendering_dt=1 / 60,
              physics_prim_path="/physicsScene")
stage = get_current_stage()
m1 = None
VIEW = None
if args.m1_model:
    from viz.m1_model import M1Model  # noqa: E402
    m1 = M1Model(stage, os.path.join(ROOT, "..", "assets", "motors", "M1"), view=args.view, shots_dir=args.m1_shots or None)
    m1.set_mount(args.mount)
    from viz.view_mode import ViewMode  # noqa: E402   (뷰 전환 유일 진입점 — 패널·시나리오·cam_plan·xray 전부 이것)
    VIEW = ViewMode(m1, log=lambda m: print(m, flush=True)); VIEW.set(args.view, "startup")


def _player_for(mode_: str):
    """M1 모델이면 config/scenarios_M1.yaml 의 모드 절(있을 때)로, 아니면 기존 모드별 파일. --scenario_yaml 이면 그 파일(steps)로."""
    if args.scenario_yaml:
        import yaml as _yaml
        _cfg = _yaml.safe_load(open(args.scenario_yaml, encoding="utf-8"))
        _cfg = _cfg.get(mode_, _cfg) if "steps" not in _cfg else _cfg
        return ScenarioPlayer(_cfg, name=f"verify:{os.path.basename(args.scenario_yaml)}")
    if m1:
        cfg_ = M1Model.scenario_cfg(ROOT, mode_)
        if cfg_:
            return ScenarioPlayer(cfg_, name=f"scenarios_M1:{mode_}")
    return ScenarioPlayer.for_mode(mode_)

dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
dome.CreateIntensityAttr(380.0)
dome.CreateColorAttr(Gf.Vec3f(0.11, 0.13, 0.17))
keyl = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
keyl.CreateIntensityAttr(1600.0)
UsdGeom.Xformable(keyl).AddRotateXYZOp().Set(Gf.Vec3f(-40, 25, 0))
filll = UsdLux.DistantLight.Define(stage, "/World/FillLight")
filll.CreateIntensityAttr(650.0)
UsdGeom.Xformable(filll).AddRotateXYZOp().Set(Gf.Vec3f(-55, -130, 0))
for L in (dome, keyl, filll):
    UsdLux.ShadowAPI.Apply(L.GetPrim()).CreateShadowEnableAttr(False)

# 모터가 화면을 채워야 결함 부위(베어링 발광·권선 색)를 심사위원이 알아본다.
# 케이블은 화면 왼쪽 위로 뻗어나가며 일부만 보이면 충분하다.
CAM_WIDE = ([-1.15, -1.55, 0.95], [0.15, -0.05, 0.22])    # 모터 중심 + 케이블 일부
CAM_CLOSE = ([-0.62, -0.86, 0.42], [0.30, 0.0, 0.02])     # 모터 클로즈업(베어링·단락루프)
# 모터 라이브러리: 외형은 프레임 비례(geometry_scale)로 보이게 카메라를 1/scale 만큼 멀리 둔다.
# USD·물리 바디를 스케일하면 관절·입자 경로가 깨지므로 원본은 그대로 두고 보는 거리만 바꾼다 (정직성 라벨 "외형은 프레임 비례 스케일").
def _scaled(cam):
    eye, tgt = cam
    return ([t + (e - t) / GEOM_SCALE for e, t in zip(eye, tgt)], list(tgt))
CAM_WIDE0, CAM_CLOSE0 = CAM_WIDE, CAM_CLOSE          # 스케일 전 기준값 (핫 모터 스위치가 다시 쓴다)
CAM_WIDE, CAM_CLOSE = _scaled(CAM_WIDE0), _scaled(CAM_CLOSE0)
if m1:                                                 # M1 모델은 실치수(370 mm)라 전용 카메라
    CAM_WIDE, CAM_CLOSE = m1.CAM_WIDE, m1.CAM_CLOSE
    if args.cam:
        CAM_WIDE = m1.cam(args.cam)                      # --cam: 기본(넓은) 카메라를 프리셋으로 (스트림 기본 화면용, 레이아웃 A)
set_camera_view(eye=CAM_WIDE[0], target=CAM_WIDE[1])
world.reset()
if PRESET and PRESET.get("single_viewport") and args.gui:
    try:
        import omni.ui as _ui
        for _name in ("Viewport 2", "Layer", "Semantics Schema Editor"):
            _w = _ui.Workspace.get_window(_name)
            if _w:
                _w.visible = False
    except Exception as _e:
        print("[demo] single_viewport:", _e, flush=True)

# ------------------------------------------------------------------ 시각화 구성
driver = MaterialDriver(stage, prefer_omnipbr=True,
                        update_hz=float(load("electrical")["rms"]["update_hz"]))
driver.setup()
builder = CurrentPathBuilder(stage)
builder.build_all()
particles = CurrentParticles(stage, builder, per_path=PARTICLES_PER_PATH)
tracks = builder.names("cable") + builder.names("winding") + ["short_loop"]
particles.attach(tracks)
if m1:
    m1.hide_prims(["/World/CurrentPaths"])      # 22 kW 기하에 맞춘 전류 경로·입자는 M1 장면에서 숨김 (HUD 숫자는 그대로)
ecmap = ElectricalColormap()

# ------------------------------------------------------------------ 엔진
tm = ThermalModel(TH_CFG)
cm = CurrentModel(EL_CFG, ml.motor_spec(MOTOR) if MOTOR else None)
from live_signals import CaseSignalCache  # noqa: E402  (app/ — 레이아웃 A: state 에 I₁·I₂·I₀·2주기 파형 덧붙임, 케이스별 1회 계산)
case_sig = CaseSignalCache(cm)
injector = FaultInjector(TH_CFG, EL_CFG, vib_thresholds=MOTOR.vib_thresholds if MOTOR else None)
player = _player_for(args.mode)
# 판정은 한 곳에서 (TASK 실시간 §5.2): fleet 배치·상태 보드와 같은 엔진. HUD 색·CSV 판정 열·라이브 state 가 모두 이 결과를 쓴다.
from engine.thresholds import Judge, bearing_level  # noqa: E402
from engine.fault_injector import bearing_signals  # noqa: E402
judge = Judge(motor=MOTOR)
THRESHOLDS = {k: tm.thresholds(k) for k in tm.node_keys}
NODE_LABELS = {n.key: n.label for n in tm.nodes}
HUD_TEMP_KEYS = ["bearing_de", "winding", "rotor", "frame"]
HUD_TEMP_EN = {"bearing_de": "DE bearing", "winding": "Stator winding",
               "rotor": "Rotor", "frame": "Housing"}

i_line = cm.motor.rated_current("rated_line_A")
i_phase = cm.motor.rated_current("rated_phase_A")

# ------------------------------------------------------------------ V1 검증 로깅 훅 (--verify_dir): 기존 엔진 값만 기록
def _git_head() -> str | None:
    """실행 시점의 저장소 커밋(검증 로그 meta.json 에 기록 — 어느 엔진으로 돌렸는지 추적, C0 2026-10-21)."""
    try:
        import subprocess as _sp
        return _sp.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


class _VerifyLog:
    FS = 2000.0; DUR = 1.0
    COLS = ["t_session_s", "t_real_s", "mode", "step", "case", "load", "time_scale", "rpm",
            "Ia_rms", "Ib_rms", "Ic_rms", "i1_A", "i2_A", "i2_over_i1", "i2_angle_deg", "i2_over_in", "i_f_A", "p_loop_total_W", "method",
            "T_winding", "T_stator_core", "T_rotor", "T_shaft", "T_bearing_de", "T_bearing_nde", "T_frame", "stage_winding", "stage_bearing_de",
            "vibration_mms", "status", "label", "cause_signal", "cause_component", "cause_value", "threshold", "stream", "provisional_in_status",
            "lvl_temperature", "lvl_current_ratio", "lvl_i2i1", "lvl_vibration", "lvl_bearing", "advisory", "fps"]

    def __init__(self, d):
        import hashlib
        self.d = d; os.makedirs(d, exist_ok=True)
        self.f_state = open(os.path.join(d, "state.csv"), "w", newline="", encoding="utf-8"); self.w_state = csv.writer(self.f_state); self.w_state.writerow(self.COLS)
        self.f_ev = open(os.path.join(d, "events.csv"), "w", newline="", encoding="utf-8"); self.w_ev = csv.writer(self.f_ev)
        self.w_ev.writerow(["t_session_s", "t_real_s", "step", "case", "kind", "from", "to", "cause_signal", "cause_component", "cause_value", "threshold"])
        self.prev_status = None; self.prev_step = None; self.n = 0; self.scenes = []
        def sha(p):
            return hashlib.sha256(open(p, "rb").read()).hexdigest()
        lut_p = os.path.join(ROOT, (EL_CFG or {}).get("source", {}).get("lut", "") or "")
        self.meta = {"argv": sys.argv[1:], "motor": MOTOR.id if MOTOR else None, "mode": args.mode, "scenario": player.name,
                     "inherent": dict((EL_CFG or {}).get("inherent") or {}), "inherent_angle_override": args.inherent_angle_deg,
                     "method": cm.method, "rated_line_A": i_line, "rated_phase_A": i_phase,
                     "lut_file": (EL_CFG or {}).get("source", {}).get("lut"), "lut_sha256": sha(lut_p) if lut_p and os.path.exists(lut_p) else None,
                     "electrical_yaml_sha256": sha(os.path.join(ROOT, "config", "electrical.yaml")), "thresholds_yaml_sha256": sha(os.path.join(ROOT, "config", "thresholds.yaml")),
                     "thermal_yaml_sha256": sha(os.path.join(ROOT, "config", "thermal.yaml")), "motor_yaml_sha256": sha(os.path.join(ROOT, "config", "motors", f"{MOTOR.id}.yaml")) if MOTOR else None,
                     "state_hz": round(1.0 / STATE_PERIOD_S, 2), "waveform_fs_hz": self.FS, "waveform_s": self.DUR,
                     "steps": [{"id": s_["id"], "t0_s": sum(float(x["duration_s"]) for x in player.steps[:k]), "duration_s": s_["duration_s"], "time_scale": s_.get("time_scale"),
                                "load": s_.get("load"), "electrical_case": s_.get("electrical_case"), "faults": s_.get("faults", [])} for k, s_ in enumerate(player.steps)],
                     "started": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": _git_head()}
        self._save_meta()
        print(f"[verify] logging → {d}", flush=True)

    def _save_meta(self):
        with open(os.path.join(self.d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=1)

    def waveform(self, t_s, case_, tag):
        t_ = np.arange(0, self.DUR, 1.0 / self.FS)
        I_ = cm.waveform(t_, case_, "rated_line_A")                      # 엔진 생성기 그대로 (슬로모션 없음, fs 2 kHz)
        p = os.path.join(self.d, f"waveform_{t_s:07.2f}_{tag}_{case_}.csv")
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["t_s", "ia_A", "ib_A", "ic_A"])
            for k in range(len(t_)):
                w.writerow([f"{t_[k]:.5f}", f"{I_[0, k]:.6f}", f"{I_[1, k]:.6f}", f"{I_[2, k]:.6f}"])
        return p

    def tick(self, t_session_, t_real_, mode_, frame_, case_, load_, st_, th_, vib_, verdict_, kind_worst_, fps_, rpm_):
        step_ = frame_.step_id if frame_ else "manual"
        if step_ != self.prev_step:                                      # 장면 전환: 전환 전 케이스·후 케이스 파형 1 s 씩
            if self.prev_step is not None and self.prev_case is not None:
                self.waveform(t_session_, self.prev_case, "pre")
            self.waveform(t_session_, case_, "post")
            self.scenes.append({"t_session_s": round(t_session_, 2), "t_real_s": round(t_real_, 3), "step": step_, "case": case_, "load": load_})
            self.meta["scene_changes"] = self.scenes; self._save_meta()
            self.prev_step = step_
        self.prev_case = case_
        loop_ = cm.short_loop(case_) or {}
        adv_ = ";".join(f"{a.kind}:{a.level}" for a in verdict_.advisory)
        self.w_state.writerow([round(t_session_, 2), round(t_real_, 3), mode_, step_, case_, load_, frame_.time_scale if frame_ else "", round(rpm_, 1),
                               *[round(v, 4) for v in st_.rms_A], round(st_.i1_A, 5), round(st_.i2_A, 5), round(st_.i2_over_i1, 5),
                               "" if st_.i2_angle_deg is None else round(st_.i2_angle_deg, 3), "" if st_.i2_over_in is None else round(st_.i2_over_in, 5),
                               loop_.get("I_f_A", ""), round(cm.loop_loss_W(case_), 2), cm.method,
                               *[round(th_.temperature_C[k], 3) for k in ("winding", "stator_core", "rotor", "shaft", "bearing_de", "bearing_nde", "frame")],
                               th_.stage["winding"], th_.stage["bearing_de"], round(vib_, 3),
                               verdict_.status, verdict_.label_ko, verdict_.cause_signal, verdict_.cause_component, round(verdict_.value, 5), verdict_.threshold,
                               verdict_.stream, verdict_.provisional_in_status,
                               *[kind_worst_.get(k, "") for k in ("temperature", "current_ratio", "i2i1", "vibration", "bearing")], adv_, round(fps_, 1)])
        key_ = (verdict_.status, verdict_.cause_signal)
        if key_ != self.prev_status:
            self.w_ev.writerow([round(t_session_, 2), round(t_real_, 3), step_, case_, "status", self.prev_status[0] if self.prev_status else "", verdict_.status,
                                verdict_.cause_signal, verdict_.cause_component, round(verdict_.value, 5), verdict_.threshold])
            self.prev_status = key_
        self.n += 1
        if self.n % 50 == 0:
            self.f_state.flush(); self.f_ev.flush()

    def close(self):
        self.meta["rows"] = self.n; self.meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S"); self._save_meta()
        self.f_state.close(); self.f_ev.close()


# 전기 결함 신호의 근거 (TASK A D3/D4): lut(M1, 등가회로 LUT) | legacy(해석식 역산). 정격 전류 불일치는 보고만 한다.
print(f"[demo] electrical method={cm.method} ({cm.method_reason})"
      + (f"; rated_current_A {cm.rated_current_A} vs motor {i_line} A ({cm.rated_current_mismatch_pct:+.1f} %)" if cm.method == "lut" else ""), flush=True)
RATED = {**{f"cable_{p}": i_line for p in "ABC"}, **{f"winding_{p}": i_phase for p in "ABC"},
         "short_loop": i_phase}
M1_PLOOP_MAX = cm.loop_loss_W("itsc_12turn") if m1 else 0.0        # Coil_01_short 발광 정규화 분모 (12턴 LUT 값)
if m1:
    _added = M1Model.register_extra_cases(cm, ROOT)                 # 8턴·16턴·저항성·반부하 — electrical.yaml 템플릿 복사(런타임), 파일 불변
    print(f"[m1] extra cases {_added}: " + ", ".join(f"{k} I2/I1 {cm.expected_i2i1(k):.4f}" for k in _added), flush=True)
if m1 and args.m1_shots:
    # 시나리오 시각(t_session)에 맞춘 스크린샷 계획 — 모드별 (파트 C S2: 기계·통합 장면 추가)
    _SHOT_PLANS = {   # 전기 전용 (기계·통합 계획은 _legacy/app/demo_integrated_modes.py)
        "electrical": [(6.0, "full", "wide", "01_exterior.png"), (12.0, "cutaway", "wide", "02_cutaway_healthy.png"), (36.0, "cutaway", "fault_focus", "03_cutaway_itsc_4turn.png"),
                       (62.0, "cutaway", "fault_focus", "04_cutaway_itsc_12turn.png"), (66.0, "windings_only", "wide", "05_windings_only.png"), (70.0, "full", "shaft", "06_shaft_end.png")],
    }
    if args.verify_dir:
        # V4: HUD 합성용 4장 (전기 시나리오: 4턴 주입 직후 20.6 s, WARN 전환 23.6 s, 12턴 DANGER 전환 48.6 s, 정상 상태 70 s) — 이름에 시각을 넣어 state.csv 와 합성
        _SHOT_PLANS = {m_: [(20.6, args.view, "wide", "hud_01_injection_t20.6.png"), (23.6, args.view, "fault_focus", "hud_02_warn_t23.6.png"),
                            (48.6, args.view, "fault_focus", "hud_03_danger_t48.6.png"), (70.0, args.view, "wide", "hud_04_steady_t70.0.png")] for m_ in ("electrical",)}
    if args.view.startswith("half_translucent"):
        # H3: 반투명 뷰 4장 — 정상 측면·정상 등각(통합 0~30 s), DE 베어링(30~70), 4턴 fault_focus(70~105)
        _v = args.view
        _SHOT_PLANS = {m_: [(14.0, _v, "side", "01_half_side_normal.png"), (18.0, _v, "wide", "02_half_iso_normal.png"),
                            (58.0, _v, "bearing_de", "04_half_bearing_de.png"), (92.0, _v, "fault_focus", "03_half_itsc_4turn.png")] for m_ in ("electrical",)}
    if args.shot_plan:
        _SHOT_PLANS = {args.mode: [(float(t_), v_, c_, f_) for t_, v_, c_, f_ in (item.split(":", 3) for item in args.shot_plan.split(";") if item.strip())]}
    m1.plan_shots(_SHOT_PLANS.get(args.mode) or _SHOT_PLANS.get("electrical") or [])   # --shot_plan 은 그 모드 키만 있다 — 기본값 표현식을 미리 평가하면 KeyError (D3 실측: 기계 모드가 기동 직후 조용히 종료)

# ------------------------------------------------------------------ 회전 구동
art = SingleArticulation(prim_path="/World/Motor", name="motor")
art.initialize()
ctrl = art.get_articulation_controller()
av = art._articulation_view
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0]))
av.set_max_efforts(np.array([[1.0e4]]))
av.set_joint_velocities(np.array([[0.0]]))

mc = ml.motor_spec_cfg(MOTOR) if MOTOR else load("motor")
V = lambda d: d["value"] if isinstance(d, dict) else d  # noqa: E731
w_sync = float(V(mc["rating"]["sync_rpm"])) * 2 * math.pi / 60
s_rated = float(V(mc["rating"]["slip"]))
T_rated = float(V(mc["rating"]["torque_Nm"]))
T_max = T_rated * 2.5
sim = get_physx_simulation_interface()

# ------------------------------------------------------------------ UI
from ui.demo_state import DemoState, MODE  # noqa: E402   (전기 전용 — 모드 선택 없음)
from fault_controller import ManualFaultController, MANUAL_CASE  # noqa: E402

state = DemoState()
state.mode = MODE
panel = hud = None
fault_ctrl = None
PHASE_LABELS = dict((EL_CFG or {}).get("phase_labels") or {"A": "R", "B": "S", "C": "T"})
try:
    fault_ctrl = ManualFaultController(stage, cm, m1.phase_coils() if m1 else {"A": ["Coil_01"]}, rate_hz=2.0, log=lambda m: print(m, flush=True))
    print(f"[panel] fault controller {fault_ctrl.prim.GetPath()} max_turns {fault_ctrl.max_turns} R_f {fault_ctrl.rf_values} coils {fault_ctrl.phase_coils}", flush=True)
except Exception as e:
    print("[panel] fault controller failed:", e, flush=True)
if args.gui and fault_ctrl is not None:
    try:
        from ui.fault_control_window import FaultControlWindow  # noqa: E402
        panel = FaultControlWindow(state, fault_ctrl, PHASE_LABELS, m1=m1, view=VIEW, streamer=None, log=lambda m: print(m, flush=True), show_notice=not args.no_panel_notice)
    except Exception as e:
        print("[demo] 패널 생성 실패:", e, flush=True)
if args.gui:
    try:
        from viz.hud import MotorHUD
        hud = MotorHUD()
        if MOTOR:
            hud.basis_motor = (f"{MOTOR.rated_power_kw:g} kW {MOTOR.poles}-pole hoist motor ({MOTOR.id} Hyundai HLP-2.2/4, {MOTOR.source} spec, "
                               f"{MOTOR.rated_rpm:g} rpm, {MOTOR.rated_line_current_a:g} A, {MOTOR.bearing_de}/{MOTOR.bearing_nde})")
            hud.vib_standard = VIB_STD
        hud.set_mode(MODE)
    except Exception as e:
        print("[demo] HUD 생성 실패:", e, flush=True)

# ------------------------------------------------------------------ 라이브 모드 (LiveBridge)
bridge = None
if args.live:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from live_bridge import LiveBridge  # noqa: E402
    try:
        bridge = LiveBridge(port=args.live_port or None).start()
    except Exception as e:
        print("[live] bridge start failed - continuing without live:", e, flush=True)   # 콘솔이 cp949 라 ASCII 로
        bridge = None
streamer = None
if STREAM_ON:
    from viz.stream_viewport import ViewportStreamer  # noqa: E402
    try:
        streamer = ViewportStreamer(port=int(load("live")["server"].get("stream_port", 8766)), fps=args.stream_fps, size=tuple(args.stream_size),
                                    quality=args.stream_quality, log=print).start()
        if panel is not None:
            panel.streamer = streamer
            panel.bridge = bridge
        if bridge is not None:
            bridge.extra_hello["stream_ws"] = streamer.url          # 대시보드가 hello 에서 스트림 주소를 읽는다
            bridge.extra_hello["stream"] = {"fps": args.stream_fps, "size": list(args.stream_size), "quality": args.stream_quality, "view": VIEW.mode if VIEW else args.view}
    except Exception as e:
        print("[stream] start failed - continuing without stream:", e, flush=True)
        streamer = None
if bridge is not None:                                      # 레이아웃 A: 장면 목록을 hello 에 (play_scenario {scene: n} 의 n 과 같은 순서). 모드 전환 때 _refresh_hello_scenes()
    def _refresh_hello_scenes():
        bridge.extra_hello["scenes"] = [{"n": k + 1, "id": st_.get("id"), "label": st_.get("label"), "duration_s": float(st_.get("duration_s", 0)),
                                         "electrical_case": st_.get("electrical_case"), "mode": st_.get("mode", args.mode)} for k, st_ in enumerate(player.steps)]
    _refresh_hello_scenes()
_STREAM_VP = [None]
judge.set_stream(args.judge_stream if args.judge_stream != "auto" else ("live" if bridge is not None else "simulation"))     # P1: 실측 스트림이면 provisional 지표는 advisory (config judgment.provisional_policy). --judge_stream 으로 고정 가능
print(f"[judge] stream={judge.stream} policy={judge.policy.get(judge.stream)}", flush=True)
LIVE_CFG = load("live")
LIVE_THERMAL = set(LIVE_CFG["commands"]["inject_fault"]["thermal"])
LIVE_ELECTRICAL = set(LIVE_CFG["commands"]["inject_fault"]["electrical"])
LIVE_JUMP = {"scene": None}          # play_scenario {scene: n} → request_play 처리 때 그 장면 시작으로 점프
LIVE_RESTART = {"motor_id": None}    # select_motor → 루프를 끝내고 같은 인자로 새 모터 재기동 (R3 자동 재시작)


def _load_reveal_timing() -> dict:
    """대시보드 해설(narration.yaml)의 장면별 reveal_timing — 라이브 state 의 narration_key.reveal 을 Isaac 쪽에서 평가한다 (§5.1)."""
    out = {}
    try:
        import yaml
        for m in ("electrical",):
            p = os.path.join(ROOT, "..", "dashboard", "public", "content", m, "narration.yaml")
            if os.path.exists(p):
                sc = (yaml.safe_load(open(p, encoding="utf-8")) or {}).get("scenes") or {}
                out[m] = {k: dict(v.get("reveal_timing") or {}) for k, v in sc.items() if isinstance(v, dict)}
    except Exception as e:
        print("[live] reveal_timing 로드 실패:", e, flush=True)
    return out


REVEAL = _load_reveal_timing()


def _reveal_stage(mode_: str, frame_) -> str | None:
    if frame_ is None:
        return None
    rt = (REVEAL.get(mode_) or {}).get(frame_.step_id) or {"why": 0.0, "visible": 0.4, "result": 0.8}
    p = frame_.step_progress
    stage_ = None
    for k, v in sorted(rt.items(), key=lambda kv: float(kv[1])):
        if p >= float(v):
            stage_ = k
    return stage_


def hot_switch_motor(mid: str) -> dict:
    """프로세스 안에서 모터만 교체 (R4): 모터 라이브러리 → 열회로·전류 모델·결함 주입기·판정·임계값·정격·물리 상수·카메라 거리·HUD 문구.
    USD 스테이지·물리 바디·머티리얼·입자는 그대로(외형은 카메라 거리로 비례 표현 — 정직성 라벨 '외형은 프레임 비례 스케일'). 결함·케이스는 해제, 열 상태 초기화."""
    global MOTOR, TH_CFG, EL_CFG, GEOM_SCALE, VIB_STD, tm, cm, injector, judge, THRESHOLDS, i_line, i_phase, RATED
    global mc, w_sync, s_rated, T_rated, T_max, CAM_WIDE, CAM_CLOSE, player, t_real
    t0 = time.perf_counter()
    MOTOR = ml.load_motor(mid)
    TH_CFG, EL_CFG = ml.thermal_cfg(MOTOR), ml.electrical_cfg(MOTOR)
    GEOM_SCALE = float(MOTOR.geometry_scale)
    VIB_STD = str(MOTOR.vibration["standard"]).split(" (")[0]
    tm = ThermalModel(TH_CFG)
    cm = CurrentModel(EL_CFG, ml.motor_spec(MOTOR))
    case_sig.cm = cm; case_sig.invalidate()
    injector = FaultInjector(TH_CFG, EL_CFG, vib_thresholds=MOTOR.vib_thresholds)
    judge = Judge(motor=MOTOR, stream=judge.stream)
    THRESHOLDS = {k: tm.thresholds(k) for k in tm.node_keys}
    i_line = cm.motor.rated_current("rated_line_A"); i_phase = cm.motor.rated_current("rated_phase_A")
    RATED = {**{f"cable_{p}": i_line for p in "ABC"}, **{f"winding_{p}": i_phase for p in "ABC"}, "short_loop": i_phase}
    mc = ml.motor_spec_cfg(MOTOR)
    w_sync = float(V(mc["rating"]["sync_rpm"])) * 2 * math.pi / 60
    s_rated = float(V(mc["rating"]["slip"])); T_rated = float(V(mc["rating"]["torque_Nm"])); T_max = T_rated * 2.5
    CAM_WIDE, CAM_CLOSE = _scaled(CAM_WIDE0), _scaled(CAM_CLOSE0)
    set_camera_view(eye=CAM_WIDE[0], target=CAM_WIDE[1])
    player = _player_for(MODE)
    if bridge is not None:
        _refresh_hello_scenes()
    state.playing_scenario = False; state.thermal_faults.clear(); state.electrical_case = "healthy"; state.dirty = True
    driver.reset_to_base()
    t_real = 0.0
    if panel:
        panel.sync_from_state()
    if hud:
        hud.basis_motor = (f"{MOTOR.rated_power_kw:g} kW {MOTOR.poles}-pole hoist motor ({MOTOR.id} Hyundai HLP-2.2/4, {MOTOR.source} spec, {MOTOR.rated_rpm:g} rpm, {MOTOR.rated_line_current_a:g} A, {MOTOR.bearing_de}/{MOTOR.bearing_nde})")
        hud.vib_standard = VIB_STD
        hud.set_mode(MODE)
    dt = time.perf_counter() - t0
    print(f"[live] hot switch -> {mid} in {dt * 1000:.0f} ms", flush=True)
    return {"hot": True, "motor_id": mid, "switch_ms": round(dt * 1000)}


def apply_command(cmd: dict) -> tuple[bool, object]:
    """메인 루프에서 명령을 DemoState 에 적용한다 (브리지가 허용 목록·범위는 이미 검사했다). (ok, applied|reason)."""
    name, a = cmd["name"], cmd.get("args") or {}
    if name == "inject_fault":
        if state.playing_scenario:
            return False, "scenario is playing — send stop_scenario first"
        f, on = a["fault"], bool(a.get("on", True))
        applied = {}
        if f in LIVE_ELECTRICAL:
            state.electrical_case = f if on else "healthy"
            applied["electrical_case"] = state.electrical_case
            if fault_ctrl is not None:
                fault_ctrl.mark_scenario(state)                     # 대시보드/명령이 결함을 쥐면 수동 사양은 정상으로
            if m1:
                m1.set_short_coil("A", None)
        if not applied:
            return False, f"fault {f} is not an electrical case (electrical-only build)"
        state.dirty = True
        if panel:
            panel.sync_from_state()
        return True, applied
    if name == "set_load":
        state.load = float(a["pct"]) / 100.0; state.dirty = True
        if panel:
            panel.sync_from_state()
        return True, {"load": state.load}
    if name == "set_time_scale":
        state.time_scale = float(a["x"]); state.dirty = True
        return True, {"time_scale": state.time_scale}
    if name == "set_slowmo":
        state.slowmo = 1.0 / float(a["x"]); state.dirty = True
        return True, {"slowmo": state.slowmo}
    if name == "set_mode":
        if str(a.get("mode")) == MODE:
            return True, {"mode": MODE, "note": "electrical-only build"}
        return False, "electrical-only build - mode is fixed to electrical (set_mode is legacy)"
    if name == "play_scenario":
        LIVE_JUMP["scene"] = a.get("scene")
        state.request_play = True
        if fault_ctrl is not None:
            fault_ctrl.mark_scenario(state)                         # 시나리오 ▾ 를 다시 고르면 scenario 로 복귀
        if m1:
            m1.set_short_coil("A", None)
        if panel:
            panel.sync_from_state()
        return True, {"scene": a.get("scene") or 1}
    if name == "stop_scenario":
        state.playing_scenario = False
        player.stop()
        return True, {"playing": False}
    if name == "reset":
        state.request_reset = True; state.thermal_faults.clear(); state.electrical_case = "healthy"
        if fault_ctrl is not None:
            fault_ctrl.mark_scenario(state)
        if panel:
            panel.reset_to_healthy()
        return True, {"reset": True}
    if name == "select_motor":
        mid = str(a["motor_id"]).upper()
        cur = MOTOR.id if MOTOR else ml.REFERENCE_ID
        if mid == cur:
            return False, f"already running motor {cur}"
        sm_cfg = LIVE_CFG["commands"].get("select_motor") or {}
        if str(sm_cfg.get("switch_mode", "hot")) == "hot":
            try:
                info = hot_switch_motor(mid)
            except Exception as e:
                return False, f"hot switch failed: {e}"
            info.update({"from": cur, "eta_s": float(sm_cfg.get("switch_banner_min_s", 10))})
            return True, info
        LIVE_RESTART["motor_id"] = mid
        eta = float(sm_cfg.get("restart_eta_s", 45))
        if hud:
            hud.set_live(f"RESTARTING -> {mid}  (about {eta:.0f} s)")
        return True, {"restart": True, "motor_id": mid, "from": cur, "eta_s": eta}
    return False, f"unhandled command {name}"


def restart_args(argv: list[str], motor_id: str) -> list[str]:
    """재기동 인자: 원래 인자에서 --motor/--autoplay/--max_s/--record/--no_timecode/--switch_seq 를 빼고 --motor <id> 를 붙인다 (수동 모드로 시작)."""
    out, skip = [], 0
    for i, a in enumerate(argv):
        if skip:
            skip -= 1; continue
        if a in ("--motor", "--max_s", "--record", "--switch_seq"):
            skip = 1; continue
        if a.startswith(("--motor=", "--max_s=", "--record=", "--switch_seq=")) or a in ("--autoplay", "--no_timecode"):
            continue
        out.append(a)
    return out + ["--motor", motor_id]


CASE_EN = {"healthy": "Healthy", "itsc_4turn": "Inter-turn short (4 turns)",
           "itsc_12turn": "Inter-turn short (12 turns)", "overload": "Overload 135%",
           "single_phasing": "Single phasing (phase R lost)", "no_load": "No load",
           "voltage_unbalance": "Supply voltage unbalance"}
SIGNAL_EN = {"temperature": "temp", "current_ratio": "current", "i2i1": "I2/I1", "vibration": "vibration",
             "bearing_kurtosis": "bearing kurtosis", "bearing_hf_ratio": "bearing HF ratio"}
PHASE_EN = {"A": "Ph R", "B": "Ph S", "C": "Ph T"}
STEP_EN_BY_MODE = {    # 전기 전용 (기계·통합 표는 _legacy/app/demo_integrated_modes.py)
    "electrical": {"healthy": "1. Healthy (balanced)", "itsc_4turn": "2. Inter-turn short (4T)",
                   "itsc_12turn": "3. Inter-turn short (12T)", "overload": "4. Overload",
                   "voltage_unbalance": "5. Supply voltage unbalance",
                   "single_phasing": "6. Single phasing (phase R lost)", "no_load": "7. No load"},
}

# ------------------------------------------------------------------ 로깅
RUN_LOG_DIR = os.path.join(LOG_DIR, args.log_subdir) if args.log_subdir else LOG_DIR
os.makedirs(RUN_LOG_DIR, exist_ok=True)
csv_path = os.path.join(RUN_LOG_DIR, f"demo_{time.strftime('%Y%m%d_%H%M%S')}.csv")
csv_file = open(csv_path, "w", newline="", encoding="utf-8")
writer = csv.writer(csv_file)
writer.writerow(["t_s", "t_real_s", "mode", "step", "case", "faults", "load", "rpm",
                 *[f"T_{k}" for k in tm.node_keys], "Ia_rms", "Ib_rms", "Ic_rms",
                 "i2_over_i1", "vibration_mms", "iso_zone", "fps",
                 "status", "cause_signal", "cause_component", "cause_value",      # Judge 판정 (R1, 기존 독자는 이름으로 읽는다)
                 "i2_over_in", "electrical_method"])                               # D4: 부하 무관 지표(LUT 방식만, 아니면 빈칸)·근거

fs_a = cm.f0 * 256
t_win = np.arange(0, 4 / cm.f0, 1 / fs_a)

# ------------------------------------------------------------------ 프로파일
# --profile 일 때만 구간 시간을 누적한다. 평소에는 _prof 가 아무것도 하지 않는다.
_prof_sum: dict[str, float] = {}
_prof_n = 0


class _Prof:
    """with _prof("physics"): ... 로 구간 시간을 ms 단위로 누적한다."""

    __slots__ = ("key", "t0")

    def __init__(self, key: str):
        self.key = key

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        _prof_sum[self.key] = _prof_sum.get(self.key, 0.0) + (time.perf_counter() - self.t0) * 1e3
        return False


class _NoProf:
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


_NOPROF = _NoProf()
_prof = _Prof if args.profile else (lambda key: _NOPROF)

# t_wall 은 프레임 수 × 1/60 이라 렌더가 60 fps 보다 빠르면 실제 시간보다 빨리 흐른다.
# scenario.yaml 의 duration_s 는 '실제 발표 시간'이므로 시나리오와 열 적분은
# 벽시계 dt 로 진행해야 한다. 영상↔로그 동기화도 실제 시간축이라야 성립한다.
t_wall = 0.0          # 렌더 프레임 기준 (기존 CSV 호환용)
t_real = 0.0          # 실제 경과 시간 — 시나리오·열·영상 동기화의 기준 (모드 전환·재생 시 0 으로)
t_session = 0.0       # 기동 후 누적 시간 — 절대 리셋하지 않는다. --max_s / --switch_seq 의 기준
_t0 = time.time()
_prev_wall = _t0
_fps_hist: list[float] = []
_last_log_t = -1.0
_last_judge_t = -1.0
_perf_logged = False
_last_fps_warn_t = -1.0
FPS_WARN_BELOW = float((PRESET or {}).get("fps_warn_below", 30))
PERF_LOG_AFTER_S = float((PRESET or {}).get("perf_log_after_s", 8))
STATE_PERIOD_S = 0.5 / float(load("live")["server"].get("state_hz", 10))   # 판정·state 갱신 주기 = 송신 주기의 절반 (브리지가 매 틱 새 state 를 보게 — 같으면 9.2 Hz 로 떨어졌다)
LOG_PERIOD_S = 0.25      # CSV·status 기록 주기 (실제 시간)
verify_log = _VerifyLog(args.verify_dir) if args.verify_dir else None     # V1 훅 (STATE_PERIOD_S 뒤)
CAM_PLAN = sorted([(float(t_), v_, c_) for t_, v_, c_ in (item.split(":", 2) for item in args.cam_plan.split(";") if item.strip())], key=lambda e: e[0]) if args.cam_plan else []
CAM_PLAN_APPLIED = [None]
# V6: 해석 근거 비교 (data/electrical/analysis_reference.json — tools/verify/build_analysis_reference.py 산출, 없으면 HUD 줄 생략)
try:
    with open(os.path.join(ROOT, "data", "electrical", "analysis_reference.json"), encoding="utf-8") as _f:
        ANALYSIS_REF = json.load(_f)
except Exception:  # noqa: BLE001
    ANALYSIS_REF = None


def analysis_ref_line(mode_: str, case_: str, st_) -> tuple[str, bool | None]:
    """HUD 한 줄: 표시값 | 해석 기준 | 차이 % | 출처 (전기 전용)."""
    if ANALYSIS_REF is None:
        return "", None
    R = ANALYSIS_REF["scenarios"].get(case_)
    if not R:
        if case_ == MANUAL_CASE:
            return "ref: manual case - LUT interpolation (turns/R_f/load grid), no scenario reference row", None
        return f"ref: {case_} outside LUT (legacy analytic) - no analysis reference", None
    exp = float(R["i2_over_i1_composite"]["expected_by_angle"]["angle_0"]); shown = float(st_.i2_over_i1)
    dev = (shown / exp - 1) * 100 if exp else 0.0
    ok = abs(dev) <= 1.0
    i_f = R["i_f_A"]["mccm"] or R["i_f_A"]["lut"]; fem = (R["i_f_A"].get("fem_corrected") or {}).get("I_f_A")
    return (f"ref: I2/I1 {exp:.4f} (shown {shown:.4f}, {dev:+.2f} %) | I_f {i_f:.1f} A" + (f" (FEM {fem:.1f})" if fem else "") +
            f" | P_loop {R['p_loop_total_W']['lut']:.0f} W | LUT v2 + 2D FEM, provisional"), ok
status_path = os.path.join(LOG_DIR, "demo_integrated_status.json")

# ------------------------------------------------------------------ 녹화
# 영상과 로그 CSV 의 시간축을 맞추는 것이 대시보드 동기 재생의 전제다.
#   video_offset_s = 시나리오 t=0 이 영상에서 몇 초 지점인가
# ffmpeg 기동 시각과 시나리오 시작 시각의 차이로 자동 계산하고,
# HUD 타임코드로 영상에서 직접 눈으로 검증할 수 있게 한다.
recorder = None
rec_meta: dict = {}
RECORD_PREROLL_S = 2.0          # 녹화 시작 후 시나리오를 시작하기까지의 여유
WINDOW_TITLE = "Isaac Sim Python 4.5.0"


def _focus_window(title: str, size=None):
    """Isaac Sim 창을 앞으로 가져오고 화면 좌표를 돌려준다.

    size=(w, h) 이면(미디어 팩 --capture_layout) 창을 (0,0) 으로 옮기고 클라이언트 영역을 정확히 그 크기로 맞춘 뒤
    클라이언트 영역(제목줄·테두리 제외)의 화면 좌표를 돌려준다 → 녹화가 정확히 w×h.
    반환: (x, y, w, h) 또는 None
    """
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.FindWindowW(None, title)
    if not hwnd:
        return None
    u.ShowWindow(hwnd, 9)          # SW_RESTORE — 최소화 상태면 되돌린다
    u.SetForegroundWindow(hwnd)
    u.BringWindowToTop(hwnd)
    time.sleep(0.5)
    if size:
        def _client():
            c = wintypes.RECT(); u.GetClientRect(hwnd, ctypes.byref(c))
            pt = wintypes.POINT(0, 0); u.ClientToScreen(hwnd, ctypes.byref(pt))
            return pt.x, pt.y, c.right - c.left, c.bottom - c.top
        w, h = int(size[0]), int(size[1])
        u.MoveWindow(hwnd, 0, 0, w, h, True); time.sleep(0.4)
        _, _, cw, ch = _client()
        u.MoveWindow(hwnd, 0, 0, w + (w - cw), h + (h - ch), True); time.sleep(0.4)
        cx, cy, cw, ch = _client()
        print(f"[media] window client {cw}x{ch} at ({cx},{cy})", flush=True)
        return max(cx, 0), max(cy, 0), cw & ~1, ch & ~1
    r = wintypes.RECT()
    if not u.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    # libx264 는 짝수 해상도를 요구한다
    w = (r.right - r.left) & ~1
    h = (r.bottom - r.top) & ~1
    return max(r.left, 0), max(r.top, 0), w, h


def _start_recording(path: str, rect):
    """데스크톱을 캡처해 창 영역만 잘라낸다.

    gdigrab 의 `title=` 캡처는 Isaac Sim 에서 쓸 수 없다. Vulkan 으로 직접
    그리기 때문에 창 DC 가 갱신되지 않아, 녹화 내내 기동 직후의 첫 화면만
    반복해서 찍힌다(실측: 62초 지점에도 시나리오가 시작되지 않은 화면).
    데스크톱 DC 는 합성 결과라서 정상적으로 갱신된다.
    """
    import subprocess
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "gdigrab", "-framerate", "30"]
    if rect:
        x, y, w, h = rect
        cmd += ["-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}"]
    cmd += ["-i", "desktop",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p, time.time()


def _stop_recording(p) -> None:
    """ffmpeg 에 q 를 보내 moov atom 까지 정상적으로 쓰게 한다 (kill 하면 파일이 깨진다)."""
    try:
        p.stdin.write(b"q")
        p.stdin.flush()
        p.wait(timeout=20)
    except Exception:
        p.kill()


if args.capture_layout and args.gui:
    # 미디어 팩(2026-10-26): 녹화 화면에서 Kit 기본 패널을 치우고 HUD 패널을 오른쪽 가장자리에 — 장면·HUD 내용은 그대로
    try:
        import omni.ui as _ui
        _hide = {"Stage", "Layer", "Render Settings", "Content", "Console", "Main ToolBar", "Property", "Semantics Schema Editor", "Viewport 2", "VIGENT - Control",
                 "Isaac Sim Assets [Beta]", "Isaac Sim Assets", "Extensions", "Script Editor", "Physics Debug", "Simulation Settings"}
        try:
            _names = list(_ui.Workspace.get_windows()) if hasattr(_ui.Workspace, "get_windows") else []
        except Exception:  # noqa: BLE001
            _names = []
        try:
            print("[media] ui windows: " + ", ".join(f"{w.title}{'*' if w.visible else ''}" for w in _names), flush=True)   # 숨길 이름 확인용 (1차 실측: 'Isaac Sim Assets [Beta]' 가 아래 1/3)
        except Exception:  # noqa: BLE001
            pass
        for _name in _hide:
            _w = _ui.Workspace.get_window(_name)
            if _w:
                _w.visible = False
        if "hud" in globals() and hud is not None:
            try:
                hud.window.position_x, hud.window.position_y = _W - 445, 10
            except Exception:  # noqa: BLE001
                pass
        for _ in range(10):
            world.render()
    except Exception as _e:  # noqa: BLE001
        print("[media] capture_layout:", _e, flush=True)

if args.record:
    # 창이 뜬 직후에는 렌더가 아직 안정되지 않아 몇 프레임 돌려준다
    for _ in range(30):
        world.render()
    _rect = _focus_window(WINDOW_TITLE, size=(_W, _H) if args.capture_layout else None)
    recorder, _rec_t0 = _start_recording(args.record, _rect)
    rec_meta = {"video": os.path.abspath(args.record), "fps": 30,
                "ffmpeg_start_wall": _rec_t0, "window_rect": _rect}
    # 프리롤 동안에도 계속 렌더한다. time.sleep 으로 멈추면 창이 응답 없음 상태가 되어
    # gdigrab 가 낡은 화면을 캡처한다.
    _preroll_end = time.time() + RECORD_PREROLL_S
    while time.time() < _preroll_end:
        world.render()

if args.switch_seq:
    print("[demo] --switch_seq ignored (electrical-only build; see _legacy/app/demo_integrated_modes.py)", flush=True)
# 패널 Q1 자동 측정 (--panel_selftest N): 턴수 0→4→12→0 을 USD 속성에 써서 속성→적용→발광→state 송신 지연을 잰다
SELFTEST = {"n": int(args.panel_selftest), "seq": [4, 12, 0], "i": 0, "next_t": 6.0 + (3.5 if args.panel_burst else 0.0), "pending": None, "events": [], "done": int(args.panel_selftest) <= 0, "hold": float(args.panel_selftest_hold)}
BURST = {"on": bool(args.panel_burst), "t0": 3.0, "t1": 6.0, "writes": 0, "done": False}

if args.autoplay:
    state.request_play = True

while simulation_app.is_running():
    # ---------- 실제 경과 시간 ----------
    _now = time.time()
    dt_real = _now - _prev_wall
    _prev_wall = _now
    dt_real = min(max(dt_real, 1e-4), 0.1)     # 첫 프레임·끊김 구간의 스파이크를 막는다
    t_real += dt_real
    t_session += dt_real

    # ---------- 진단 --view_probe: 패널 경로로 뷰 전환 뒤 USD variant 를 몇 프레임 읽는다 ----------
    if args.view_probe and m1:
        _vp = globals().setdefault("_VP", {"plan": [((lambda a: (a[0], float(a[1]) if len(a) > 1 else 8.0))(it.split("@"))) for it in args.view_probe.split(";") if it.strip()], "i": 0, "k": -1, "hold": []})
        _vs = m1.prim.GetVariantSet("view")
        if _vp["k"] < 0 and _vp["i"] < len(_vp["plan"]) and t_session >= _vp["plan"][_vp["i"]][1]:
            _mode = _vp["plan"][_vp["i"]][0]
            if _vp["i"] == 0:
                print(f"[view_probe] usd={os.path.join(m1.asset_dir, 'M1.usd')} variants={list(_vs.GetVariantNames()) if _vs else None}", flush=True)
            print(f"[view_probe] before click: variant={_vs.GetVariantSelection() if _vs else None} m1.view={m1.view} control_source={state.control_source} scenario_playing={state.playing_scenario}", flush=True)
            (panel.set_view if panel else (lambda k: VIEW.set(k, "manual")))(_mode)
            print(f"[view_probe] click frame: variant={_vs.GetVariantSelection() if _vs else None} m1.view={m1.view} state.view_mode={VIEW.mode}", flush=True)
            _vp["k"] = 0; _vp["hold"].append((t_session + 30.0, _mode))
        elif _vp["k"] >= 0:
            _vp["k"] += 1
            print(f"[view_probe] +{_vp['k']} frame: variant={_vs.GetVariantSelection() if _vs else None} m1.view={m1.view}", flush=True)
            if _vp["k"] >= 3:
                _vp["k"] = -1; _vp["i"] += 1
        for _h in list(_vp["hold"]):
            if t_session >= _h[0]:
                _vp["hold"].remove(_h)
                print(f"[view_probe] +30 s after {_h[1]}: variant={_vs.GetVariantSelection() if _vs else None} scenario_playing={state.playing_scenario} step={frame.step_id if frame else 'manual'}", flush=True)

    # ---------- 패널 Q1 2 Hz 제한 검사 (--panel_burst): 3 s 동안 매 프레임 속성을 바꿔 쓴다 → 마지막 값만 남아야 한다 ----------
    if BURST["on"] and not BURST["done"] and fault_ctrl is not None and t_session >= BURST["t0"]:
        if t_session < BURST["t1"]:
            fault_ctrl.write(turns=int(1 + (BURST["writes"] % 30)), phase="A"); BURST["writes"] += 1
        else:
            fault_ctrl.write(turns=2, phase="A"); BURST["writes"] += 1; BURST["done"] = True; BURST["t_last"] = time.perf_counter()   # 마지막 값 2턴 (뒤 자동 측정의 4턴과 구분)
    if BURST["on"] and BURST["done"] and not BURST.get("reported") and fault_ctrl is not None and fault_ctrl._applied and fault_ctrl._applied.get("turns") == 2 and fault_ctrl._pending is None:
        BURST["reported"] = True
        _rep = {"writes": BURST["writes"], "applies_during_burst": fault_ctrl.stats["applied"], "coalesced": fault_ctrl.stats["coalesced"], "final_turns": fault_ctrl._applied["turns"],
                "last_write_to_apply_ms": round((time.perf_counter() - BURST["t_last"]) * 1000)}
        print("[panel] burst " + json.dumps(_rep), flush=True)
        with open(os.path.join(RUN_LOG_DIR, "panel_burst.json"), "w", encoding="utf-8") as _f:
            json.dump(_rep, _f, indent=1)

    # ---------- 패널 Q1 자동 측정: 속성 쓰기 ----------
    if not SELFTEST["done"] and fault_ctrl is not None and t_session >= SELFTEST["next_t"] and SELFTEST["pending"] is None:
        _turns = SELFTEST["seq"][SELFTEST["i"] % len(SELFTEST["seq"])]
        fault_ctrl.write(turns=_turns, R_f_ohm=0.1, phase="A", coil=(fault_ctrl.phase_coils.get("A") or ["Coil_01"])[0])
        SELFTEST["pending"] = {"turns": _turns, "expect_case": MANUAL_CASE if _turns > 0 else "healthy", "t_attr": time.perf_counter(), "t_apply": None, "t_glow": None, "t_state": None}
        SELFTEST["i"] += 1
        SELFTEST["next_t"] = t_session + SELFTEST["hold"]
        if SELFTEST["i"] >= SELFTEST["n"] * len(SELFTEST["seq"]):
            SELFTEST["done"] = True

    # ---------- 잔상 제거 요청 (핫 모터 스위치 뒤; 모드 전환은 없다) ----------
    if state.request_mode_reset:
        state.mode = MODE
        player = _player_for(MODE)
        if bridge is not None:
            _refresh_hello_scenes()
        tm.reset()
        judge.reset()
        driver.reset_to_base()                 # 발열 색·발광 제거
        driver.set_opacity(["endshield_de"], 1.0)
        driver.set_opacity(["housing_frame"], 1.0)
        particles.set_visible(False)           # 전류 입자 제거
        for _nm in tracks:                     # 전류 경로 커브 제거
            builder.set_visible(_nm, False)
        if hud:
            hud.set_mode(MODE)
        state.playing_scenario = False
        state.request_mode_reset = False
        state.dirty = True
        t_real = 0.0

    # ---------- 패널 요청 처리 ----------
    if state.request_reset:
        tm.reset()
        judge.reset()
        player.reset()
        state.playing_scenario = False
        state.request_reset = False
        t_real = 0.0
    if state.request_play:
        tm.reset()
        judge.reset()
        player.start()
        if LIVE_JUMP["scene"]:                                 # 라이브 play_scenario {scene: n}: 그 장면 시작으로 점프
            player.elapsed = min(sum(float(s["duration_s"]) for s in player.steps[:int(LIVE_JUMP["scene"]) - 1]), player.total_duration - 1e-3)
            LIVE_JUMP["scene"] = None
        state.playing_scenario = True
        state.request_play = False
        state.control_source = "scenario"
        t_real = 0.0                 # 시나리오 t=0 을 실제 시간축의 원점으로 삼는다
        if recorder is not None and "scenario_start_wall" not in rec_meta:
            # 시나리오 t=0 의 벽시계 시각. 영상 오프셋의 기준점이다.
            rec_meta["scenario_start_wall"] = time.time()
            rec_meta["video_offset_s"] = round(
                rec_meta["scenario_start_wall"] - rec_meta["ffmpeg_start_wall"], 3)

    # ---------- 라이브 명령 (브리지 큐 → DemoState, ack) ----------
    if bridge is not None:
        for _cmd in bridge.poll_commands():
            try:
                _ok, _info = apply_command(_cmd)
            except Exception as _e:                           # 명령 하나가 루프를 죽이면 안 된다
                _ok, _info = False, f"error: {_e}"
            bridge.ack(_cmd, _ok, _info)
            print(f"[live] {_cmd['name']} {_cmd.get('args')} → {'ok' if _ok else 'rejected'} {_info}", flush=True)

    # ---------- 시나리오 재생이면 상태를 시나리오가 결정 ----------
    frame = None
    if state.playing_scenario:
        frame = player.advance(dt_real)
        if VIEW is not None and frame.step_id != globals().get("_LAST_STEP_VIEW"):     # 장면 전환 시 1회만: 장면 config 에 view 키가 있으면 그 뷰 (없으면 그대로 — 패널 선택 유지)
            globals()["_LAST_STEP_VIEW"] = frame.step_id
            _sv = next((st_.get("view") for st_ in player.steps if st_.get("id") == frame.step_id), None)
            if _sv:
                VIEW.set(str(_sv), "scenario")
        state.load = frame.load
        state.time_scale = frame.time_scale
        state.electrical_case = frame.electrical_case
        state.thermal_faults = list(frame.thermal_faults)
        if frame.finished:
            state.playing_scenario = False
            if panel:
                panel.set_status("시나리오 종료")
        if panel:
            panel.sync_from_state()

    # ---------- 패널 Q1: USD 속성 → 수동 결함 (2 Hz 제한, 마지막 값 보장) ----------
    if fault_ctrl is not None:
        _spec = fault_ctrl.poll(time.perf_counter())
        if _spec is not None:
            fault_ctrl.apply(_spec, state, cm, player=player, case_cache=case_sig)
            if m1:
                m1.set_short_coil(state.fault_phase, state.manual.coil if state.electrical_case == MANUAL_CASE else None)
            if panel:
                panel.sync_from_state()
            if SELFTEST["pending"] is not None and SELFTEST["pending"]["t_apply"] is None:
                SELFTEST["pending"]["t_apply"] = time.perf_counter()

    mode = MODE
    case = state.electrical_case
    faults = []                                                 # 전기 전용: 열 결함 없음

    # ---------- 전류 ----------
    with _prof("current"):
        t_slow = t_real * state.slowmo
        _shift = {"A": 0, "B": 1, "C": 2}.get(state.fault_phase, 0)      # 패널 Q1 결함 상 B/C = 엔진 파형의 상 순서 순환 (새 수치 없음, 대칭 성분 크기 불변)
        _I_line = cm.waveform(t_win + t_slow, case, "rated_line_A"); _I_phase = cm.waveform(t_win + t_slow, case, "rated_phase_A")
        if _shift:
            _I_line = np.roll(_I_line, _shift, axis=0); _I_phase = np.roll(_I_phase, _shift, axis=0)
        st_line = cm.analyze(t_win, _I_line, case, "rated_line_A")
        st_phase = cm.analyze(t_win, _I_phase, case, "rated_phase_A")

    # ---------- 열 (통합 모드에서만 전류 연동) ----------
    with _prof("thermal"):
        th = tm.step(dt_sim_s=0.0, load=state.load, faults=[], use_duty_cycle=False)     # 전기 전용: 열 적분 없음(온도 상수) — 통합 열 연동은 _legacy

    # ---------- 회전 ----------
    with _prof("physics"):
        for _ in range(PHYSICS_SUBSTEPS):
            w = float(art.get_joint_velocities()[0])
            s = (w_sync - w) / w_sync
            T_m = max(-T_max, min(T_rated * s / s_rated, T_max))
            T_l = -T_rated * state.load * (1.0 if w > 1.0 else max(w, 0.0))
            ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T_m + T_l - 0.015 * w])))
            sim.simulate(PHYSICS_DT, t_wall)
            sim.fetch_results()

    # ---------- 시각: 부품 색 ----------
    with _prof("materials"):
        xray_on = state.highlight_short_loop                   # 전기 전용: 단락루프 강조만 (베어링 투시는 _legacy)
        driver.set_opacity(["endshield_de"], 0.40 if xray_on else 1.0)
        if VIEW is not None:                        # M1 모델: 단락루프 강조는 임시 cutaway — 켜짐/꺼짐이 바뀔 때만 (매 프레임 재적용이 패널 전환을 되돌리던 버그, fix/panel-view-switch)
            VIEW.xray(bool(xray_on))
        if state.highlight_short_loop:
            driver.housing_transparent(True, opacity=0.25)
        else:
            driver.set_opacity(["housing_frame"], 0.68)

    # ---------- 시각: 전류 경로·입자 ----------
    with _prof("paths"):
        show_current = True
        particles.set_visible(show_current)
        loop = cm.short_loop(case)
        cur, stt = {}, {}
        inst_l = cm.sample(t_slow, case, "rated_line_A")
        inst_p = cm.sample(t_slow, case, "rated_phase_A")
        for i, ph in enumerate("ABC"):
            cur[f"cable_{ph}"], stt[f"cable_{ph}"] = inst_l[i], st_line.status[i]
            cur[f"winding_{ph}"], stt[f"winding_{ph}"] = inst_p[i], st_phase.status[i]
        if loop:
            cur["short_loop"] = float(loop["current_pu"]) * i_phase * math.sin(2 * math.pi * cm.f0 * t_slow)
            stt["short_loop"] = "short_loop"
        else:
            cur["short_loop"], stt["short_loop"] = 0.0, "normal"
        for name in tracks:
            builder.set_visible(name, show_current and (name != "short_loop" or loop is not None))
            if show_current:
                builder.set_color(name, ecmap.sample(stt[name], t_real)["diffuse"])
    with _prof("particles"):
        if show_current:
            particles.update(dt_real, cur, stt, t_real, RATED)

    # ---------- M1 전체 모델: 회전(ω 적분)·열 색·단락 루프 발광 — 새 계산 없음 ----------
    if m1:
        m1.step_rotation(w, dt_real)
        m1.update(None, th.stage, t_real, THRESHOLDS, cm.loop_loss_W(case), M1_PLOOP_MAX, thermal_on=False)   # 전기 전용: 단락 발광만
        if SELFTEST["pending"] is not None and SELFTEST["pending"]["t_apply"] is not None and SELFTEST["pending"]["t_glow"] is None and case == SELFTEST["pending"]["expect_case"]:
            SELFTEST["pending"]["t_glow"] = time.perf_counter()
        m1.hide_prims(["/World/CurrentPaths"])      # 경로 set_visible(MakeVisible)이 매 프레임 조상을 다시 보이게 하므로 뒤에서 다시 숨긴다
        m1.run_shots(t_session, set_camera_view, world.render)

    # ---------- 카메라 일정 (--cam_plan, 캡처용) ----------
    if m1 and CAM_PLAN:
        _cur = None
        for _e in CAM_PLAN:
            if t_session >= _e[0]:
                _cur = _e
        if _cur is not None:
            if _cur[1] and _cur[1] != VIEW.base:
                args.view = _cur[1]; VIEW.set(_cur[1], "cam_plan")
            if _cur[2] == "orbit":
                _eye, _tgt = m1.orbit_cam(t_session - _cur[0]); set_camera_view(eye=_eye, target=_tgt)
            elif _cur is not CAM_PLAN_APPLIED[0]:
                _eye, _tgt = m1.cam(_cur[2]); set_camera_view(eye=_eye, target=_tgt)
            CAM_PLAN_APPLIED[0] = _cur
            state.dirty = False
    # ---------- 카메라 ----------
    if m1 and CAM_PLAN and CAM_PLAN_APPLIED[0] is not None:
        pass                                                   # 캡처 일정이 카메라를 쥔다
    elif state.highlight_short_loop:
        set_camera_view(eye=CAM_CLOSE[0], target=CAM_CLOSE[1])
    elif state.dirty:
        set_camera_view(eye=CAM_WIDE[0], target=CAM_WIDE[1])
    state.dirty = False

    # ---------- 판정 (Judge — fleet 배치와 같은 신호·같은 반올림) ----------
    vib = th.vibration_mms
    zone = injector.iso_zone(vib)
    # 판정·state 는 live.yaml state_hz(10 Hz)로만 갱신한다 — 매 프레임 돌리면 FPS 가 −8 % (R1 실측). HUD 는 캐시된 등급을 매 프레임 쓴다.
    _judge_due = (t_session - _last_judge_t) >= STATE_PERIOD_S or _last_judge_t < 0
    with _prof("judge"):
        if _judge_due:
            _last_judge_t = t_session
            brg = bearing_signals(tm.cfg, faults)
            verdict = judge.update(t_session, {
                "temperature": {k: round(th.temperature_C[k], 1) for k in tm.node_keys},
                "current_ratio": {p: round(st_line.rms_A[i], 1) / i_line for i, p in enumerate("ABC")},
                "i2i1": round(st_line.i2_over_i1, 4), "vibration": round(vib, 1), **brg,
            })
            levels = {(s_.kind, s_.component): s_.level for s_ in verdict.signals}
            kind_worst = {}
            for s_ in verdict.signals:
                if ("SAFE", "WARN", "DANGER").index(s_.level) >= ("SAFE", "WARN", "DANGER").index(kind_worst.get(s_.kind, "SAFE")):
                    kind_worst[s_.kind] = s_.level
            kind_worst["bearing"] = bearing_level(verdict.signals)

    # ---------- HUD ----------
    with _prof("hud"):
        if hud:
            hud.update_current(st_line, levels={p: levels.get(("current_ratio", p), "SAFE") for p in "ABC"},
                               i2i1_level=levels.get(("i2i1", "-"), "SAFE"))
            _rl, _rok = analysis_ref_line(mode, case, st_line)
            if _rl:
                hud.update_reference(_rl, _rok)
            if verdict.status == "SAFE":
                _cause = "all signals within safe range"
            else:
                _comp = HUD_TEMP_EN.get(verdict.cause_component, NODE_LABELS.get(verdict.cause_component, verdict.cause_component))
                _comp = PHASE_EN.get(verdict.cause_component, _comp) if verdict.cause_signal == "current_ratio" else _comp
                _cause = f"{_comp + ' ' if verdict.cause_component != '-' else ''}{SIGNAL_EN.get(verdict.cause_signal, verdict.cause_signal)} {verdict.value:g}"
            hud.update_status(verdict, _cause)
            if bridge is not None:
                hud.set_live(f"LIVE  {bridge.url}   clients {bridge.clients}")
            _steps_en = STEP_EN_BY_MODE.get(mode, {})
            if case == MANUAL_CASE:
                title = f"Manual inter-turn short {state.manual.turns}T  R_f {state.manual.R_f_ohm:g} ohm  ({PHASE_EN.get(state.fault_phase, state.fault_phase)} {state.manual.coil})"
            else:
                title = _steps_en.get(frame.step_id, frame.label) if frame else CASE_EN.get(case, case)
            sub = (frame.subtitle_en if frame else
                   f"Electrical only / {'manual (panel)' if state.control_source == 'manual' else 'scenario'} / load {state.load * 100:.0f}% / time x{state.time_scale:.0f}")
            if MOTOR:
                sub = sub.replace("ISO 20816-3", VIB_STD)      # 시나리오 자막의 규격 이름을 모터 규격으로
            if "{" in sub:                                     # 자막 변수 (모터별 전류 수치, D-1 ②)
                _cs = cm.evaluate_case(case)
                sub = fill_vars(sub, {"rated_line_A": i_line, "a_rms_end": round(_cs.rms_A[0], 1), "a_pct_end": round(_cs.ratio[0] * 100),
                                      "i2i1": f"{_cs.i2_over_i1:.3f}"})      # {i2i1}: 그 케이스의 I₂/I₁ (M1 은 LUT 값) — 문자열이라 1자리 반올림을 피한다
            hud.update_scenario(title, sub if not frame else f"[{CASE_EN.get(case, case)}]  {sub}",
                                source=frame.source_en if frame else "")
            # 타임코드는 CSV 의 t_s 와 같은 값이다 (영상에서 오프셋을 눈으로 검증할 때 쓴다)
            hud.update_timecode(None if args.no_timecode else t_real)

    with _prof("render"):
        world.render()
    if streamer is not None:                                # 레이아웃 A: 뷰포트 캡처 예약 (클라이언트 없으면 비용 0)
        if _STREAM_VP[0] is None:
            try:
                from omni.kit.viewport.utility import get_active_viewport
                _STREAM_VP[0] = get_active_viewport()
            except Exception as _e:  # noqa: BLE001
                print("[stream] no active viewport:", _e, flush=True); streamer = None
        if streamer is not None:
            streamer.tick(_STREAM_VP[0], t_session)
    _prof_n += 1
    t_wall += 1 / 60

    # ---------- state dict (CSV 로깅과 라이브 송신이 같은 것을 쓴다 — 키 = CSV 컬럼, docs/live_r0_report.md §5) ----------
    if _judge_due:
        _rpm = w * 60 / (2 * math.pi)
        state_dict = {
            "t_s": round(t_wall, 2), "t_real_s": round(t_real, 3), "t_session_s": round(t_session, 2),
            "motor_id": MOTOR.id if MOTOR else ml.REFERENCE_ID, "mode": mode, "step": frame.step_id if frame else "manual", "case": case,
            "scene": ({"id": frame.step_id, "label": frame.label, "elapsed_s": round(frame.step_elapsed_s, 1), "duration_s": frame.step_duration_s,
                       "progress": round(frame.step_progress, 3), "total_elapsed_s": round(frame.total_elapsed_s, 1), "time_scale": frame.time_scale,
                       "playing": state.playing_scenario} if frame else None),
            "faults": list(faults), "load": round(state.load, 2), "time_scale": state.time_scale, "slowmo": state.slowmo, "rpm": round(_rpm, 1),
            "T": {k: round(th.temperature_C[k], 1) for k in tm.node_keys}, "stage": dict(th.stage),
            "loss_W": {k: round(float(th.loss_W.get(k, 0.0)), 1) for k in tm.node_keys},        # 부품별 손실열 (대시보드 원인 패널)
            "Ia_rms": round(st_line.rms_A[0], 2), "Ib_rms": round(st_line.rms_A[1], 2), "Ic_rms": round(st_line.rms_A[2], 2),   # 송신 정밀도 0.01 A (패널 Q1 §4.8; 엔진·판정 입력은 그대로)
            "i2_over_i1": round(st_line.i2_over_i1, 4), "rated_line_A": i_line, "current_status": list(st_line.status),
            # D4/D5 추가 키 (schema 1 유지 — 기존 키·구조는 그대로, 아래는 덧붙임): 부하 무관 지표·근거 배지·단락 루프 손실·게이지 눈금
            "i2_over_in": None if st_line.i2_over_in is None else round(st_line.i2_over_in, 4),
            "electrical_source": {**cm.electrical_source(case), "cases": cm.cases_summary()},
            "p_loop_total_W": round(cm.loop_loss_W(case), 1),
            "i2i1_marks": cm.i2i1_marks(),
            "vibration_mms": round(vib, 2), "iso_zone": zone,
            "bearing_kurtosis": brg["bearing_kurtosis"], "bearing_hf_ratio": brg["bearing_hf_ratio"],
            "status": {"status": verdict.status, "label": verdict.label_ko, "cause_signal": verdict.cause_signal, "cause_component": verdict.cause_component,
                       "value": round(verdict.value, 4), "threshold": verdict.threshold, "levels": kind_worst,
                       "stream": verdict.stream, "provisional_in_status": verdict.provisional_in_status,
                       "signals": [{"kind": s_.kind, "component": s_.component, "level": s_.level, "value": round(s_.value, 4), "status": s_.status, "advisory": s_.advisory} for s_ in verdict.signals],
                       "advisory": [{"kind": s_.kind, "component": s_.component, "level": s_.level, "value": round(s_.value, 4)} for s_ in verdict.advisory]},
            "narration_key": {"mode": mode, "scene": frame.step_id if frame else None, "reveal": _reveal_stage(mode, frame)},
            "perf": {"fps": round(_fps_hist[-1], 1) if _fps_hist else None,
                     "stream": ({"clients": streamer.clients, "sent": streamer.stats["sent"], "encode_ms": streamer.stats["encode_ms"], "capture_ms": streamer.stats["capture_ms"]} if streamer is not None else None)},
        }
        _sig = case_sig.get(case)                           # 레이아웃 A (schema 1 유지 — 덧붙임): 케이스별 I₁·I₂·I₀ [A RMS] + 2주기 파형 (export case_signals 와 같은 식)
        if _sig:
            if _shift:                                           # 결함 상 순환은 파형·성분 표시에도 같은 순서로
                _wf = dict(_sig["waveform_last_2cycles"]); _abc = [_wf["A"], _wf["B"], _wf["C"]]
                _wf["A"], _wf["B"], _wf["C"] = _abc[-_shift % 3], _abc[(1 - _shift) % 3], _abc[(2 - _shift) % 3]
                _sig = {**_sig, "waveform_last_2cycles": _wf}
            state_dict.update(_sig)
        # 패널 Q1 (덧붙임, 계산 없음): 조작 주체·수동 사양·I₂/I₁ 지속 시계(Judge 내부 시계 노출)
        _pk = ("i2i1", "-"); _since = judge._since.get(_pk); _curlv = judge._state.get(_pk)
        state_dict["control_source"] = state.control_source
        if VIEW is not None:
            state_dict.update(VIEW.state())                 # view_mode·view_source·view_label (USD readback, 계산 없음)
        state_dict["manual_fault"] = ({**state.manual.to_dict(), "phase_label": PHASE_LABELS.get(state.manual.phase, state.manual.phase), "case": case} if state.control_source == "manual" else None)
        state_dict["persistence"] = {"kind": "i2i1", "need_s": float(judge.persist.get("i2i1", 0.0)), "level": _curlv or "SAFE", "raw_level": _since[0] if _since else "SAFE",
                                     "pending_s": round(max(0.0, t_session - _since[1]), 2) if (_since and _since[0] != (_curlv or "SAFE")) else 0.0}
        if panel:
            panel.update_readings(state_dict, state_dict["persistence"], streamer.clients if streamer is not None else 0, bridge.clients if bridge is not None else 0)
        if SELFTEST["pending"] is not None and SELFTEST["pending"]["t_apply"] is not None and SELFTEST["pending"]["t_state"] is None and case == SELFTEST["pending"]["expect_case"]:
            _e = SELFTEST["pending"]; _e["t_state"] = time.perf_counter()
            SELFTEST["events"].append({"turns": _e["turns"], "case": case, "attr_to_apply_ms": round((_e["t_apply"] - _e["t_attr"]) * 1000, 1),
                                       "attr_to_glow_ms": round(((_e["t_glow"] or _e["t_state"]) - _e["t_attr"]) * 1000, 1), "attr_to_state_ms": round((_e["t_state"] - _e["t_attr"]) * 1000, 1),
                                       "i2i1": state_dict["i2_over_i1"], "status": state_dict["status"]["status"]})
            SELFTEST["pending"] = None
            if SELFTEST["done"] and not SELFTEST.get("saved"):
                SELFTEST["saved"] = True
                import statistics as _st
                _ms = [x["attr_to_state_ms"] for x in SELFTEST["events"]]; _gl = [x["attr_to_glow_ms"] for x in SELFTEST["events"]]
                _summary = {"n": len(_ms), "attr_to_state_ms": {"p50": _st.median(_ms), "p95": sorted(_ms)[max(0, int(len(_ms) * 0.95) - 1)], "max": max(_ms)},
                            "attr_to_glow_ms": {"p50": _st.median(_gl), "p95": sorted(_gl)[max(0, int(len(_gl) * 0.95) - 1)], "max": max(_gl)}, "events": SELFTEST["events"]}
                with open(os.path.join(RUN_LOG_DIR, "panel_selftest.json"), "w", encoding="utf-8") as _f:
                    json.dump(_summary, _f, ensure_ascii=False, indent=1)
                print("[panel] selftest " + json.dumps({k: v for k, v in _summary.items() if k != "events"}), flush=True)
        if bridge is not None:
            bridge.publish(state_dict)
        if verify_log is not None:
            verify_log.tick(t_session, t_real, mode, frame, case, state.load, st_line, th, vib, verdict, kind_worst, _fps_hist[-1] if _fps_hist else 0.0, _rpm)

    # ---------- 로깅 ----------
    # 기록 주기는 t_session 기준 — t_real 은 모드 전환·재생 시 0 으로 돌아가 기록이 멈춘다(실측)
    if t_session - _last_log_t >= LOG_PERIOD_S:
        _last_log_t = t_session
        wall = time.time() - _t0
        fps = t_wall / wall * 60.0 if wall > 0.5 else 0.0
        _fps_hist.append(fps)
        # 기동 성능 로그(한 번) + FPS 경고 (R4): 숫자는 render_demo.yaml fps_warn_below / perf_log_after_s
        if not _perf_logged and t_session >= PERF_LOG_AFTER_S and fps > 0:
            _perf_logged = True
            _perf = {"t_session_s": round(t_session, 1), "fps": round(fps, 1), "preset": args.preset or ("low" if args.low else "default"),
                     "resolution": [_W, _H], "ram_mb": None, "vram_mb": None, "motor": MOTOR.id if MOTOR else ml.REFERENCE_ID}
            try:
                import psutil
                _perf["ram_mb"] = round(psutil.Process().memory_info().rss / 1048576)
            except Exception:
                pass
            try:
                import subprocess as _sp
                _perf["vram_mb"] = float(_sp.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3).stdout.strip().splitlines()[0])
            except Exception:
                pass
            print(f"[perf] start: {json.dumps(_perf)}", flush=True)
            with open(os.path.join(RUN_LOG_DIR, "perf_start.json"), "w", encoding="utf-8") as _f:
                json.dump(_perf, _f, indent=1)
        if t_session - _last_fps_warn_t >= 5.0:
            _last_fps_warn_t = t_session
            if 0 < fps < FPS_WARN_BELOW and t_session > PERF_LOG_AFTER_S:
                print(f"[perf] WARNING fps {fps:.1f} < {FPS_WARN_BELOW:g} (t={t_session:.0f}s)", flush=True)
        rpm = float(art.get_joint_velocities()[0]) * 60 / (2 * math.pi)
        writer.writerow([round(t_wall, 2), round(t_real, 3), mode, frame.step_id if frame else "manual", case,
                         "|".join(faults), round(state.load, 2), round(rpm, 1),
                         *[round(th.temperature_C[k], 1) for k in tm.node_keys],
                         *[round(v, 1) for v in st_line.rms_A], round(st_line.i2_over_i1, 4),
                         round(vib, 2), zone, round(fps, 1),
                         verdict.status, verdict.cause_signal, verdict.cause_component, round(verdict.value, 4),
                         "" if st_line.i2_over_in is None else round(st_line.i2_over_in, 4), cm.method])
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump({"t": round(t_wall, 2), "t_real": round(t_real, 2), "t_session": round(t_session, 2),
                       "mode": mode, "case": case,
                       "step": frame.step_id if frame else "manual",
                       "scenario": state.playing_scenario,
                       "i2i1": round(st_line.i2_over_i1, 4),
                       "bearing_de": round(th.temperature_C["bearing_de"], 1),
                       "winding": round(th.temperature_C["winding"], 1),
                       "stage_bearing": th.stage["bearing_de"], "stage_winding": th.stage["winding"],
                       "fps": round(fps, 1)}, f, ensure_ascii=False)

    if args.max_s and t_session >= args.max_s:
        break
    if LIVE_RESTART["motor_id"]:
        # ack 가 클라이언트에 나갈 시간을 준 뒤 루프를 끝낸다 (대시보드는 끊김을 '모터 전환 중' 띠로 보여주고 재접속 대기)
        for _ in range(20):
            world.render()
        print(f"[live] restarting with motor {LIVE_RESTART['motor_id']}", flush=True)
        break

if verify_log is not None:
    verify_log.close()
if recorder is not None:
    _stop_recording(recorder)
    rec_meta["ffmpeg_stop_wall"] = time.time()
    rec_meta["duration_s"] = round(rec_meta["ffmpeg_stop_wall"] - rec_meta["ffmpeg_start_wall"], 2)
    rec_meta["log_csv"] = csv_path
    rec_meta["timecode_burned_in"] = not args.no_timecode
    rec_name = os.path.splitext(os.path.basename(args.record))[0]
    with open(os.path.join(RUN_LOG_DIR, f"recording_{rec_name}.json"), "w", encoding="utf-8") as f:
        json.dump(rec_meta, f, ensure_ascii=False, indent=2)

if streamer is not None:
    print("[stream] stats", json.dumps(streamer.stats), flush=True)
    streamer.stop()
if bridge is not None:
    print("[live] stats", json.dumps(bridge.stats), flush=True)
    bridge.stop()                                   # 포트를 먼저 놓는다 — 새 인스턴스가 bind_retry_s 안에 잡는다
if LIVE_RESTART["motor_id"]:
    import subprocess
    _argv = restart_args(sys.argv[1:], LIVE_RESTART["motor_id"])
    _script = os.path.abspath(__file__)
    print(f"[live] spawn: {sys.executable} {_script} {' '.join(_argv)}", flush=True)
    with open(os.path.join(LOG_DIR, "live_restart.json"), "w", encoding="utf-8") as f:
        json.dump({"t_wall": time.time(), "motor_id": LIVE_RESTART["motor_id"], "argv": _argv}, f, ensure_ascii=False)
    # python.bat 이 만든 환경(CARB_APP_PATH 등)을 그대로 물려받으므로 kit.exe 를 바로 띄운다. 부모가 닫혀도 살도록 분리한다.
    # 콘솔 없이(DETACHED) 띄우면 sys.stderr 가 None 이라 SimulationApp 의 faulthandler.enable() 이 죽는다(실측) → 표준 출력을 로그 파일로 준다.
    _flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    _logf = open(os.path.join(LOG_DIR, f"live_restart_{LIVE_RESTART['motor_id']}.log"), "a", encoding="utf-8")
    subprocess.Popen([sys.executable, _script] + _argv, cwd=os.getcwd(), creationflags=_flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=_logf, stderr=subprocess.STDOUT)
csv_file.close()
steady = [f for f in _fps_hist[5:] if f > 0]
summary = {"csv": csv_path, "duration_s": round(t_real, 1), "frames_t_wall_s": round(t_wall, 1),
           "fps": {"mean": round(sum(steady) / len(steady), 1) if steady else None,
                   "min": round(min(steady), 1) if steady else None,
                   "pass": bool(steady and min(steady) >= 30)}}
if args.profile and _prof_n:
    per_frame = {k: round(v / _prof_n, 3) for k, v in sorted(_prof_sum.items(),
                                                             key=lambda kv: -kv[1])}
    summary["profile_ms_per_frame"] = {**per_frame, "_measured": round(sum(per_frame.values()), 3),
                                       "_frames": _prof_n}
with open(os.path.join(RUN_LOG_DIR, "demo_integrated.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("[demo] DONE", csv_path, flush=True)
simulation_app.close()
