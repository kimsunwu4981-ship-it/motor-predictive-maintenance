# -*- coding: utf-8 -*-
"""capture_all.py — 보고용 미디어 팩 (2026-10-26): Isaac Sim 사진·HUD 합성 사진·영상·GIF·그림·index/meta/README/contact_sheet.

원칙: 장면·엔진·대시보드 코드는 바꾸지 않는다. 숫자는 전부 엔진 출력(state.csv)·검증 산출물에서 가져오고, 연출용 숫자는 없다.
Isaac Sim 은 PowerShell/cmd 에서만 띄워야 한다(Git Bash 자식은 조용히 종료) → `plan` 이 만든 run_isaac.cmd 를 PowerShell 에서 실행한다.

사용 (motor_dt_viz 에서, py -3.12 -X utf8):
  tools\\media\\capture_all.py plan                 # Isaac 실행 배치(logs/media/run_isaac.cmd) 작성
  (PowerShell) cmd /c logs\\media\\run_isaac.cmd    # 사진 2회·영상 4회 Isaac 자동 재생 (~20 분)
  tools\\media\\capture_all.py isaac                # 사진 13장 → docs/media/<날짜>/isaac
  tools\\media\\capture_all.py hud                  # HUD 합성 9장 + state.csv 대조 → hud/
  tools\\media\\capture_all.py video                # 영상 자르기·1920×1080·제목 자막·GIF·대시보드 webm→mp4·side-by-side → video/
  tools\\media\\capture_all.py figures              # Maxwell·검증 그림 복사(ASCII 이름) → figures/
  tools\\media\\capture_all.py dashboard            # Playwright 사진 12장 + 워크스루 (서버 4173 필요)
  tools\\media\\capture_all.py index                # index.md · meta.json · README.md · contact_sheet.png
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys

def _maxwell_root() -> str:
    """Maxwell 저장소 위치: MAXWELL_ROOT 환경변수 → 바탕 화면\\권상모터_3D모델링 → 바탕 화면\\모터\\권상모터_3D모델링 (2026-10-26 바탕화면 정리로 이동)."""
    env = os.environ.get("MAXWELL_ROOT")
    if env:
        return env
    desk = os.path.join(os.path.expanduser("~"), "OneDrive", "바탕 화면")
    for c in (os.path.join(desk, "권상모터_3D모델링"), os.path.join(desk, "모터", "권상모터_3D모델링")):
        if os.path.isdir(c):
            return c
    return os.path.join(desk, "모터", "권상모터_3D모델링")

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ)
ISAAC_PY = r"C:\ISSACS~1\python.bat"
MAXWELL = _maxwell_root()
FONT = r"C:\Windows\Fonts\malgun.ttf"
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"
DATE = "20261026"
LOGS = os.path.join(VIZ, "logs", "media")
FPS = 30
W, H = 1920, 1080
LEVEL_KO = {"SAFE": "안전", "WARN": "경고", "DANGER": "위험"}

# ---------------------------------------------------------------- 계획 (시각은 config/scenarios_M1.yaml 장면 안쪽; 판정 지속 3 s 뒤)
# Isaac 사진 13장: (t, view, cam, 파일, 해상도, 캡션)
ISAAC_SHOTS = {
    "electrical": [
        (6.0, "full", "iso", "isaac_01_exterior_iso", (2560, 1440), "모터 외형 등각 — 정상 운전 (M1 HLP-2.2/4, 100L 프레임)"),
        (8.0, "full", "side", "isaac_02_exterior_side", (1920, 1080), "모터 외형 측면 (−Y 방향)"),
        (10.0, "full", "front_shaft", "isaac_03_front_shaft", (1920, 1080), "축단 정면 (+X 에서 본 DE 축단·엔드실드)"),
        (14.0, "cutaway", "iso", "isaac_04_cutaway_healthy_iso", (2560, 1440), "절단 뷰 등각 — 정상 (고정자 권선·로터·DE/NDE 베어링)"),
        (16.0, "cutaway", "rotor_closeup", "isaac_05_cutaway_rotor_closeup", (1920, 1080), "절단 뷰 상부 근접 — 코일 엔드·로터 코어·엔드링 (DE 쪽)"),
        (18.0, "windings_only", "iso", "isaac_06_windings_only", (1920, 1080), "권선만 — 36슬롯 2층 권선 코일 배치 (Coil_01 단락 루프 포함)"),
        (19.5, "half_translucent", "side", "isaac_07_half_translucent_side", (1920, 1080), "반절 반투명 뷰 측면 — 정상 (한쪽 반이 비침, 절단 없음)"),
        (36.0, "cutaway", "fault_focus", "isaac_08_cutaway_itsc_4turn", (2560, 1440), "턴간 단락 4턴 — Coil_01 단락 루프 발광, I₂/I₁ 경계(경고)"),
        (62.0, "cutaway", "fault_focus", "isaac_09_cutaway_itsc_12turn", (1920, 1080), "턴간 단락 12턴 — 위험 (단락 루프 발광 강함)"),
        (64.0, "cutaway", "close", "isaac_10_cutaway_itsc_12turn_close", (1920, 1080), "턴간 단락 12턴 근접 — 전류 경로·권선 발열 색"),
    ],
    "mechanical": [
        (52.0, "cutaway", "bearing_de", "isaac_11_cutaway_bearing_de", (1920, 1080), "DE 베어링 열화 — 절단 뷰 베어링 근접 (온도 색)"),
        (55.0, "half_translucent", "bearing_de", "isaac_12_half_translucent_bearing_de", (1920, 1080), "DE 베어링 열화 — 반절 반투명 뷰 (DE 엔드실드·하우징 너머 내부가 비침)"),
        (78.0, "cutaway", "close", "isaac_13_cutaway_misalignment_close", (1920, 1080), "축 정렬 불량 — 근접 (양쪽 베어링·축 온도)"),
    ],
}
# HUD 합성 9장: (파일, t, view, cam, 설명) — 뷰포트 캡처 + 같은 시각 state.csv 값 (새 계산 없음)
HUD_SHOTS = {
    "electrical": [
        ("hud_01_healthy", 12.0, "cutaway", "wide", "정상 (3상 균형, 고유 비대칭만)"),
        ("hud_02_itsc_4turn", 36.5, "cutaway", "fault_focus", "턴간 단락 4턴 — I₂/I₁ 경계(경고)"),
        ("hud_03_itsc_12turn", 62.5, "cutaway", "fault_focus", "턴간 단락 12턴 — 위험"),
        ("hud_04_overload", 88.0, "full", "wide", "과부하 운전 — 전류/정격 상한"),
        ("hud_05_single_phasing", 138.0, "cutaway", "wide", "결상 (R상 끊김) — 결상 의심 위험"),
        ("hud_06_no_load", 158.0, "full", "wide", "무부하 저전류 — 경부하(참고) 규칙 (세 상 함께 낮고 균형)"),
        ("hud_07_itsc_4turn_resistive", 218.0, "cutaway", "fault_focus", "저항성 4턴 (R_f 1.0 Ω) — 전류로 탐지 불가"),
    ],
    "mechanical": [
        ("hud_08_bearing_de", 52.5, "cutaway", "bearing_de", "DE 베어링 열화 — 진동·베어링 온도"),
        ("hud_09_misalignment", 78.5, "cutaway", "close", "축 정렬 불량 — 양쪽 베어링·축 온도"),
    ],
}
PHOTO_RUNS = {"electrical": ("media_elec", 222), "mechanical": ("media_mech", 82)}       # (log_subdir, max_s)
# 영상 녹화 4회: 이름 → (mode, cam_plan, max_s, no_timecode)
VIDEO_RUNS = {
    "orbit": ("electrical", "0:full:orbit;24:cutaway:orbit;48:half_translucent:orbit", 72, True),
    "vid_elec": ("electrical", "0:full:iso;10:cutaway:iso;21:cutaway:fault_focus;46:cutaway:fault_focus;64:cutaway:close", 78, False),
    "vid_mech": ("mechanical", "0:full:iso;26:cutaway:bearing_de;61:cutaway:close", 86, False),
    "vid_int": ("integrated", "0:full:iso;31:cutaway:bearing_de;71:cutaway:fault_focus;106:cutaway:fault_focus;151:full:iso", 168, False),
}
# 산출 영상: 파일 → (녹화 run, 장면 시각 시작, 끝, 제목 자막, 캡션)
CLIPS = [
    ("01_exterior_orbit", "orbit", 2.0, 22.0, "M1 모터 외형 — 축 중심 360° 궤도 (20 s)", "외형 360° 궤도 1회전 (전기 시나리오 정상 구간, HUD 포함)"),
    ("02_cutaway_orbit", "orbit", 26.0, 46.0, "절단 뷰 — 360° 궤도 (턴간 단락 4턴 구간)", "절단 뷰 360° 궤도 — 20~45 s 는 4턴 장면이라 Coil_01 단락 루프가 발광한다"),
    ("03_electrical_fault", "vid_elec", 0.0, 76.0, "전기 시나리오 — 정상 → 턴간 단락 4턴 → 12턴", "전기 시나리오 0~76 s: 정상(0~20)·4턴 경고(20~45)·12턴 위험(45~75), 카메라 외형→절단→fault_focus→근접"),
    ("04_half_translucent_orbit", "orbit", 50.0, 70.0, "반절 반투명 뷰 — 360° 궤도 (12턴 구간)", "반절 반투명 뷰 360° 궤도 — 45 s 이후 12턴 장면"),
    ("05_mechanical_bearing", "vid_mech", 10.0, 85.0, "기계 시나리오 — 정상 → DE 베어링 열화 → 축 정렬 불량", "기계 시나리오 10~85 s: 정상(~25)·DE 베어링 열화(25~60)·축 정렬 불량(60~85)"),
    ("06_integrated_full", "vid_int", 0.0, 166.0, "통합 시나리오 — 베어링 열화 + 턴간 단락 4턴 → 12턴", "통합 시나리오 전체 0~166 s: 정상·베어링·4턴·12턴·결론"),
]
GIFS = [("gif_01_orbit", "01_exterior_orbit", 0.0, 10.0, 800), ("gif_02_itsc_glow", "03_electrical_fault", 18.0, 28.0, 800)]   # (파일, 원본 clip, 시작, 길이, 폭)
# 그림: (원본 상대경로(저장소 키), ASCII 이름, 캡션)
FIGURES = [
    ("MX", "docs/maxwell/img/render_01_full_iso.png", "fig_01_maxwell_render_full_iso", "Maxwell 3D 모델 전체 등각 렌더"),
    ("MX", "docs/maxwell/img/render_02_quarter_cut.png", "fig_02_maxwell_render_quarter_cut", "Maxwell 3D 1/4 절단 렌더"),
    ("MX", "docs/maxwell/img/render_03_windings.png", "fig_03_maxwell_render_windings", "Maxwell 고정자 권선 렌더"),
    ("MX", "docs/maxwell/img/render_04_rotor_cage.png", "fig_04_maxwell_render_rotor_cage", "Maxwell 로터 케이지 렌더"),
    ("MX", "docs/maxwell/img/render_05_coil01_itsc.png", "fig_05_maxwell_render_coil01_itsc", "Maxwell Coil_01 턴간 단락 분할 렌더"),
    ("MX", "docs/maxwell/img/m2_full_section_xy.png", "fig_06_maxwell_section_xy", "Maxwell 2D 단면 (XY)"),
    ("MX", "docs/maxwell/img/s1_lite_q_geometry.png", "fig_07_maxwell_2d_lite_geometry", "2D-eddy-lite 해석 형상 (1/4)"),
    ("MX", "docs/maxwell/img/s3_fault_rf0p1_B.png", "fig_08_maxwell_fault_rf0p1_B", "턴간 단락 R_f 0.1 Ω 자속밀도 B (2D)"),
    ("MX", "docs/maxwell/img/s3_fault_rf0p1_J.png", "fig_09_maxwell_fault_rf0p1_J", "턴간 단락 R_f 0.1 Ω 전류밀도 J (2D)"),
    ("MX", "docs/maxwell/img/s3_fault_rf1p0_B.png", "fig_10_maxwell_fault_rf1p0_B", "턴간 단락 R_f 1.0 Ω 자속밀도 B (2D)"),
    ("MX", "docs/maxwell/img/m6_torque_speed.png", "fig_11_maxwell_torque_speed", "RMxprt 토크–속도 곡선"),
    ("MX", "docs/maxwell/img/m6_current_speed.png", "fig_12_maxwell_current_speed", "RMxprt 전류–속도 곡선"),
    ("MX", "docs/maxwell/img/m6_loss_breakdown.png", "fig_13_maxwell_loss_breakdown", "RMxprt 손실 분해"),
    ("MX", "docs/maxwell/img/e3_severity_rf.png", "fig_14_lut_severity_rf", "LUT: 단락 턴수·R_f 별 I₂/I₁ (결함분)"),
    ("MX", "docs/maxwell/img/e3_severity_load.png", "fig_15_lut_severity_load", "LUT: 부하별 I₂/I₁"),
    ("MX", "docs/maxwell/img/e3_i2_over_in_load.png", "fig_16_lut_i2_over_in_load", "LUT: 부하별 I₂/I_n"),
    ("MX", "docs/maxwell/img/e3_cases_i2i1.png", "fig_17_lut_cases_i2i1", "시나리오 케이스별 I₂/I₁ (LUT)"),
    ("DT", "docs/verification/img/i2i1_timeseries.png", "fig_18_dt_i2i1_timeseries", "DT 검증: I₂/I₁ 시계열 (시뮬 vs 해석 기준)"),
    ("DT", "docs/verification/img/sim_vs_analysis_bars.png", "fig_19_dt_sim_vs_analysis_bars", "DT 검증: 시뮬 vs 해석 차이 막대"),
    ("DT", "docs/verification/img/waveform_spectrum.png", "fig_20_dt_waveform_spectrum", "DT 검증: 상전류 파형·스펙트럼"),
    ("DT", "docs/verification/img/winding_temperature.png", "fig_21_dt_winding_temperature", "DT 검증: 권선 온도 (열회로)"),
    ("DT", "docs/verification/img/status_board_4turn_warn.png", "fig_22_dt_status_board_4turn", "검증 당시 상태 보드 4턴 경고 캡처"),
    ("DT", "docs/verification/img/status_board_12turn_danger.png", "fig_23_dt_status_board_12turn", "검증 당시 상태 보드 12턴 위험 캡처"),
]


def out_dir(date: str) -> str:
    return os.path.join(REPO, "docs", "media", date)


def rel(p: str) -> str:
    return os.path.relpath(p, VIZ).replace("/", "\\")


def rated_current() -> float:
    import yaml
    m = yaml.safe_load(open(os.path.join(VIZ, "config", "motors", "M1.yaml"), encoding="utf-8"))
    v = m.get("rated_line_current_a")
    if isinstance(v, dict):
        v = v.get("value", v.get("a"))
    return float(v)


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("[cmd] " + " ".join(cmd)[:300], flush=True)
    return subprocess.run(cmd, check=True, **kw)


def ffprobe_dur(p: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def img_size(p: str):
    from PIL import Image
    with Image.open(p) as im:
        return im.size


# ---------------------------------------------------------------- plan
def photo_plan(mode: str) -> str:
    items = [(t, v, c, f"{name}.png@{r[0]}x{r[1]}") for t, v, c, name, r, _ in ISAAC_SHOTS[mode]]
    items += [(t, v, c, f"{name}_t{t:.1f}.png@{W}x{H}") for name, t, v, c, _ in HUD_SHOTS[mode]]
    items.sort(key=lambda e: e[0])
    return ";".join(f"{t}:{v}:{c}:{f}" for t, v, c, f in items)


def cmd_plan(a):
    """배치 안에서 .bat 를 부를 때는 반드시 `call` — 없으면 첫 python.bat 가 끝나는 순간 배치가 끝난다(1차 실행에서 실측: 전기 사진 뒤 종료)."""
    os.makedirs(LOGS, exist_ok=True)
    skip = set((a.skip or "").split(",")) - {""}
    lines = ["@echo off", "chcp 65001 >nul", f'cd /d "{VIZ}"']
    if a.retake:
        # 1차 캡처 뒤 카메라를 고친 사진만 다시 (같은 shots 폴더에 덮어씀): 전기 모드 정상 구간
        names = set(a.retake.split(",")); items = [(t, v, c, f"{n}.png@{r[0]}x{r[1]}") for t, v, c, n, r, _ in ISAAC_SHOTS["electrical"] if n in names]
        d = os.path.join(LOGS, "electrical")
        lines.append(f'echo [media] retake && call {ISAAC_PY} app\\demo_integrated.py --gui --autoplay --mode electrical --motor M1 --view full --res {W} {H} '
                     f'--m1_shots "{rel(os.path.join(d, "shots"))}" --shot_plan "{";".join(f"{t}:{v}:{c}:{f}" for t, v, c, f in items)}" --max_s {max(t for t, *_ in items) + 3:.0f} --log_subdir media_retake > "{rel(os.path.join(d, "retake.txt"))}" 2>&1')
    for mode, (sub, max_s) in PHOTO_RUNS.items():
        if mode in skip:
            continue
        d = os.path.join(LOGS, mode); os.makedirs(os.path.join(d, "shots"), exist_ok=True)
        lines.append(f'echo [media] photos {mode} && call {ISAAC_PY} app\\demo_integrated.py --gui --autoplay --mode {mode} --motor M1 --view full --res {W} {H} '
                     f'--m1_shots "{rel(os.path.join(d, "shots"))}" --shot_plan "{photo_plan(mode)}" --verify_dir "{rel(d)}" --max_s {max_s} --log_subdir {sub} > "{rel(os.path.join(d, "run.txt"))}" 2>&1')
    for name, (mode, plan, max_s, notc) in VIDEO_RUNS.items():
        if name in skip:
            continue
        d = os.path.join(LOGS, name); os.makedirs(d, exist_ok=True)
        lines.append(f'echo [media] video {name} && call {ISAAC_PY} app\\demo_integrated.py --gui --autoplay --mode {mode} --motor M1 --view full --res {W} {H} '
                     f'--cam_plan "{plan}" --record "{rel(os.path.join(d, f"rec_{name}.mp4"))}" --verify_dir "{rel(d)}" --max_s {max_s} --log_subdir media_{name} --capture_layout{" --no_timecode" if notc else ""} > "{rel(os.path.join(d, "run.txt"))}" 2>&1')
    lines.append(f'echo done > "{rel(os.path.join(LOGS, "ALL_DONE.txt"))}"')
    p = os.path.join(LOGS, "run_isaac.cmd")
    open(p, "w", encoding="utf-8").write("\r\n".join(lines) + "\r\n")
    print(f"→ {p}\n(PowerShell 에서)  cmd /c \"{p}\"")


# ---------------------------------------------------------------- isaac photos
def cmd_isaac(a):
    from PIL import Image
    od = os.path.join(out_dir(a.date), "isaac"); os.makedirs(od, exist_ok=True)
    caps, missing = [], []
    for mode, shots in ISAAC_SHOTS.items():
        for t, v, c, name, r, cap in shots:
            src = os.path.join(LOGS, mode, "shots", f"{name}.png")
            if not os.path.exists(src):
                missing.append((name, "캡처 파일 없음 (Isaac 실행 로그 확인)")); continue
            dst = os.path.join(od, f"{name}.png")
            with Image.open(src) as im:
                size = im.size
                if size != r:
                    im = im.convert("RGB").resize(r, Image.LANCZOS); im.save(dst, optimize=True); note = f"뷰포트 {size[0]}x{size[1]} → {r[0]}x{r[1]} 리샘플"
                else:
                    im.convert("RGB").save(dst, optimize=True); note = ""
            caps.append({"file": f"{name}.png", "caption": cap, "mode": mode, "t_session_s": t, "view": v, "camera": c, "resolution": f"{r[0]}x{r[1]}", "raw_resolution": f"{size[0]}x{size[1]}", "note": note,
                         "size_kb": round(os.path.getsize(dst) / 1024)})
    json.dump({"captions": caps, "missing": missing}, open(os.path.join(od, "captions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"isaac: {len(caps)} 장, 누락 {len(missing)} {missing}")


# ---------------------------------------------------------------- hud
def nearest_row(rows, t):
    return min(rows, key=lambda x: abs(float(x["t_session_s"]) - t))


def hud_lines(r: dict, ref: dict | None, i_n: float) -> list[str]:
    st = r["status"]; mode = r["mode"]
    lines = [f"{LEVEL_KO.get(st, st)} {st}   원인 {r['cause_signal']} {r['cause_value']}   [{r['threshold']}]",
             f"t = {float(r['t_session_s']):.1f} s   장면 {r['step']}   부하 {r['load']}   {r['rpm']} rpm"]
    if mode in ("electrical", "integrated"):
        lines += [f"I R/S/T = {float(r['Ia_rms']):.2f} / {float(r['Ib_rms']):.2f} / {float(r['Ic_rms']):.2f} A  (정격 {i_n:.2f} A)   I₁ {float(r['i1_A']):.3f} A",
                  f"I₂/I₁ = {float(r['i2_over_i1']):.4f}   I₂/I_n = {r['i2_over_in'] or '-'}   I_f = {r['i_f_A'][:6] if r['i_f_A'] else '-'} A   P_loop = {r['p_loop_total_W']} W"]
        if r.get("advisory"):
            lines.append(f"참고(advisory): {r['advisory']}")
    if mode in ("mechanical", "integrated"):
        lines += [f"온도 권선 {float(r['T_winding']):.1f} · DE 베어링 {float(r['T_bearing_de']):.1f} · 축 {float(r['T_shaft']):.1f} · 프레임 {float(r['T_frame']):.1f} °C   진동 {r['vibration_mms']} mm/s",
                  f"등급 온도 {r['lvl_temperature']} · 진동 {r['lvl_vibration']} · 베어링 {r['lvl_bearing']}"]
    if ref is not None:
        R = ref["scenarios"].get(r["case"])
        if mode == "mechanical":
            lines.append("근거: Maxwell 근거 없음 — 진동·베어링 상수(ISO 10816-1 / AI Hub 참고)")
        elif R:
            exp = R["i2_over_i1_composite"]["expected_by_angle"]["angle_0"]; dev = (float(r["i2_over_i1"]) / exp - 1) * 100 if exp else 0.0
            lines.append(f"근거: I₂/I₁ 해석 {exp:.4f} (표시 {float(r['i2_over_i1']):.4f}, {dev:+.2f} %)  I_f MCCM {R['i_f_A']['mccm'] or R['i_f_A']['lut']} A  — 등가회로 LUT + 2D FEM (provisional)")
        else:
            lines.append("근거: LUT 밖 장면(legacy 해석식) — 해석 기준 없음")
    return lines


def compose_hud(raw_png: str, lines: list[str], status: str, out: str):
    from PIL import Image, ImageDraw, ImageFont
    col = {"SAFE": (38, 242, 89), "WARN": (255, 115, 26), "DANGER": (255, 20, 13)}
    im = Image.open(raw_png).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    f = ImageFont.truetype(FONT, 26); fb = ImageFont.truetype(FONT_B, 28); fs = ImageFont.truetype(FONT, 20)
    y = 24
    for k, ln in enumerate(lines):
        font = fb if k == 0 else f
        bb = d.textbbox((28, y), ln, font=font)
        d.rounded_rectangle((bb[0] - 10, bb[1] - 6, bb[2] + 10, bb[3] + 6), radius=6, fill=(0, 0, 0, 175))
        d.text((28, y), ln, font=font, fill=col.get(status, (255, 255, 255)) + (255,) if k == 0 else (255, 255, 255, 255))
        y = bb[3] + 16
    note = "HUD 합성 (뷰포트 캡처 + state.csv) — 시뮬레이션 기반 추정값, 실측 아님"
    bb = d.textbbox((0, 0), note, font=fs); x = W - (bb[2] - bb[0]) - 28; yy = H - (bb[3] - bb[1]) - 28
    d.rounded_rectangle((x - 8, yy - 5, x + bb[2] - bb[0] + 8, yy + bb[3] - bb[1] + 7), radius=6, fill=(0, 0, 0, 160))
    d.text((x, yy), note, font=fs, fill=(255, 204, 102, 255))
    Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB").save(out, optimize=True)


def cmd_hud(a):
    od = os.path.join(out_dir(a.date), "hud"); os.makedirs(od, exist_ok=True)
    ref_p = os.path.join(VIZ, "data", "electrical", "analysis_reference.json")
    ref = json.load(open(ref_p, encoding="utf-8")) if os.path.exists(ref_p) else None
    i_n = rated_current(); caps, missing, checks = [], [], []
    keys = ("status", "cause_signal", "cause_value", "threshold", "step", "case", "load", "rpm", "Ia_rms", "Ib_rms", "Ic_rms", "i1_A", "i2_over_i1", "i2_over_in", "i_f_A", "p_loop_total_W",
            "T_winding", "T_bearing_de", "T_shaft", "T_frame", "vibration_mms", "lvl_temperature", "lvl_vibration", "lvl_bearing", "advisory")
    for mode, shots in HUD_SHOTS.items():
        st_p = os.path.join(LOGS, mode, "state.csv")
        if not os.path.exists(st_p):
            missing += [(n, "state.csv 없음") for n, *_ in shots]; continue
        rows = list(csv.DictReader(open(st_p, encoding="utf-8")))
        for name, t, v, c, desc in shots:
            raw = os.path.join(LOGS, mode, "shots", f"{name}_t{t:.1f}.png")
            if not os.path.exists(raw):
                missing.append((name, "캡처 파일 없음")); continue
            r = nearest_row(rows, t); lines = hud_lines(r, ref, i_n)
            out = os.path.join(od, f"{name}.png"); compose_hud(raw, lines, r["status"], out)
            open(os.path.join(od, f"{name}.txt"), "w", encoding="utf-8").write("\n".join(lines) + f"\n\n{desc}\n")
            caps.append({"file": f"{name}.png", "caption": desc, "mode": mode, "t_planned_s": t, "t_session_s": float(r["t_session_s"]), "view": v, "camera": c, "resolution": f"{W}x{H}",
                         "values": {k: r.get(k, "") for k in keys}, "hud_lines": lines, "state_csv": os.path.relpath(st_p, REPO), "size_kb": round(os.path.getsize(out) / 1024)})
    json.dump({"captions": caps, "missing": missing}, open(os.path.join(od, "captions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ---- 대조 1회: 캡션(values·hud_lines)의 숫자가 state.csv 그 행과 같은가 — 독립 재판독
    for cp in caps:
        rows = list(csv.DictReader(open(os.path.join(REPO, cp["state_csv"]), encoding="utf-8")))
        r = nearest_row(rows, cp["t_planned_s"]); bad = []
        for k, v in cp["values"].items():
            if r.get(k, "") != v:
                bad.append((k, v, r.get(k, "")))
        txt = "\n".join(cp["hud_lines"])
        for k, fmt in (("i2_over_i1", "{:.4f}"), ("Ia_rms", "{:.2f}"), ("Ib_rms", "{:.2f}"), ("Ic_rms", "{:.2f}"), ("T_winding", "{:.1f}"), ("T_bearing_de", "{:.1f}")):
            if r.get(k, "") not in ("", None) and (k.startswith("I") or k.startswith("i")) == (r["mode"] in ("electrical", "integrated")):
                s = fmt.format(float(r[k]))
                if s not in txt:
                    bad.append((f"text:{k}", s, "HUD 줄에 없음"))
        checks.append({"file": cp["file"], "t_session_s": cp["t_session_s"], "dt_s": round(abs(float(r["t_session_s"]) - cp["t_planned_s"]), 3), "ok": not bad, "mismatch": bad})
    n_ok = sum(1 for c in checks if c["ok"])
    json.dump({"result": "PASS" if n_ok == len(checks) and checks else "FAIL", "n": len(checks), "ok": n_ok, "checks": checks, "method": "captions.json 의 values·hud_lines 를 state.csv 에서 독립 재판독한 행(|Δt| 최소)과 문자열 비교"},
              open(os.path.join(od, "check_vs_state.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"hud: {len(caps)} 장, 누락 {len(missing)} {missing}; 대조 {n_ok}/{len(checks)}")


# ---------------------------------------------------------------- video
def rec_offset(run: str):
    """녹화 시작 → 시나리오 시작 오프셋(s). recording_*.json 의 wall clock."""
    js = glob.glob(os.path.join(VIZ, "logs", f"media_{run}", "recording_*.json"))
    if not js:
        return None, None
    m = json.load(open(js[0], encoding="utf-8"))
    if "scenario_start_wall" not in m:
        return None, m
    return m["scenario_start_wall"] - m["ffmpeg_start_wall"], m


def drawtext(title: str, tf: str, show_s: float = 5.0) -> str:
    open(tf, "w", encoding="utf-8").write(title)
    ff = FONT.replace("\\", "/").replace(":", "\\:"); tfe = tf.replace("\\", "/").replace(":", "\\:")
    foot = "Isaac Sim 4.5 · M1 (HLP-2.2/4) · 시뮬레이션 기반 추정값, 실측 아님"
    ft = tf + ".foot.txt"; open(ft, "w", encoding="utf-8").write(foot); fte = ft.replace("\\", "/").replace(":", "\\:")
    return (f"drawtext=fontfile='{ff}':textfile='{tfe}':x=40:y=36:fontsize=40:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14:enable='lt(t,{show_s})',"
            f"drawtext=fontfile='{ff}':textfile='{fte}':x=w-tw-28:y=h-th-24:fontsize=22:fontcolor=#ffcc66:box=1:boxcolor=black@0.5:boxborderw=8")


def encode(src: str, dst: str, ss: float, to: float, vf: str, crf: int = 21):
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{ss:.3f}", "-to", f"{to:.3f}", "-i", src, "-vf", vf, "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst])


def cmd_video(a):
    od = os.path.join(out_dir(a.date), "video"); os.makedirs(od, exist_ok=True)
    tmp = os.path.join(LOGS, "tmp"); os.makedirs(tmp, exist_ok=True)
    caps, missing = [], []
    scale = f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black"
    only = set((a.only or "").split(",")) - {""}
    for name, run, t0, t1, title, cap in CLIPS:
        src = os.path.join(LOGS, run, f"rec_{run}.mp4")
        if not os.path.exists(src):
            missing.append((name, f"녹화 없음 {run}")); continue
        off, meta = rec_offset(run)
        if off is None:
            missing.append((name, "recording json 에 scenario_start_wall 없음")); continue
        dur = ffprobe_dur(src); ss = off + t0; to = min(off + t1, dur)
        dst = os.path.join(od, f"{name}.mp4")
        if not (only and name not in only and os.path.exists(dst)):          # --only: 지정한 것만 다시 인코딩, 나머지는 있는 파일 그대로
            encode(src, dst, ss, to, scale + "," + drawtext(title, os.path.join(tmp, f"{name}.txt")))
        mb = os.path.getsize(dst) / 1e6
        if mb > 60:
            encode(src, dst, ss, to, scale + "," + drawtext(title, os.path.join(tmp, f"{name}.txt")), crf=26); mb = os.path.getsize(dst) / 1e6
        caps.append({"file": f"{name}.mp4", "caption": cap, "title": title, "run": run, "mode": VIDEO_RUNS[run][0], "scenario_t_s": [t0, t1], "video_ss_s": round(ss, 3), "duration_s": round(to - ss, 2),
                     "offset_rec_to_scenario_s": round(off, 3), "window_rect": meta.get("window_rect"), "timecode_burned_in": meta.get("timecode_burned_in"), "resolution": f"{W}x{H}", "fps": FPS, "size_mb": round(mb, 1),
                     "speed": 1.0, "source_log": os.path.relpath(meta.get("log_csv", ""), REPO) if meta.get("log_csv") else ""})
    # GIF 2
    for g, srcclip, s0, ln, width in GIFS:
        src = os.path.join(od, f"{srcclip}.mp4")
        if not os.path.exists(src):
            missing.append((g, f"원본 clip 없음 {srcclip}")); continue
        dst = os.path.join(od, f"{g}.gif"); wd = width
        if only and g not in only and os.path.exists(dst):
            mb = os.path.getsize(dst) / 1e6; caps.append({"file": f"{g}.gif", "caption": f"{srcclip} 의 {s0:.0f}~{s0 + ln:.0f} s (12 fps)", "source": f"{srcclip}.mp4", "size_mb": round(mb, 2)}); continue
        while True:
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{s0}", "-t", f"{ln}", "-i", src,
                "-vf", f"fps=12,scale={wd}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4", dst])
            mb = os.path.getsize(dst) / 1e6
            if mb <= 8 or wd <= 480:
                break
            wd -= 160
        caps.append({"file": f"{g}.gif", "caption": f"{srcclip} 의 {s0:.0f}~{s0 + ln:.0f} s (12 fps, 폭 {wd})", "source": f"{srcclip}.mp4", "size_mb": round(mb, 2), "width": wd})
    # 07 대시보드 워크스루 (dashboard_shots.mjs 가 gdigrab 으로 찍은 원본 mp4 → 제목 자막 넣어 재인코딩, 한 번만)
    raw07 = os.path.join(od, "07_dashboard_walkthrough.mp4"); tmp07 = os.path.join(tmp, "07_raw.mp4"); done07 = os.path.join(tmp, "07.done")
    if os.path.exists(raw07) and not os.path.exists(done07):
        shutil.move(raw07, tmp07)
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp07, "-vf", scale + "," + drawtext("상태 보드 워크스루 — M1 (대시보드 #/status)", os.path.join(tmp, "07.txt")),
            "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", raw07])
        open(done07, "w").write("encoded\n")
    if os.path.exists(raw07):
        caps.append({"file": "07_dashboard_walkthrough.mp4", "caption": "대시보드 워크스루 — 첫 화면(15 s) → 4턴 칩 → 게이지 → 해석 근거 비교 → 근거 보기 → 12턴 칩 → 맨 위 (Edge 창 화면 녹화, 1920×1080)",
                     "duration_s": round(ffprobe_dur(raw07), 1), "resolution": f"{W}x{H}", "fps": FPS, "size_mb": round(os.path.getsize(raw07) / 1e6, 1), "speed": 1.0})
    else:
        missing.append(("07_dashboard_walkthrough", "대시보드 녹화 없음 (dashboard 단계 먼저)"))
    # 08 side-by-side (+1): Isaac 전기 녹화 + 상태 보드 재생을 같은 장면 시각으로 나란히
    sb = os.path.join(od, "08_dashboard_sync.mp4"); sbj = os.path.join(od, "08_dashboard_sync.json")
    isaac = os.path.join(LOGS, "vid_elec", "rec_vid_elec.mp4")
    if os.path.exists(sb) and os.path.exists(sbj) and os.path.exists(isaac):
        m = json.load(open(sbj, encoding="utf-8")); off_i, _ = rec_offset("vid_elec")
        off_d = float(m["play_offset_s"])                                                  # gdigrab 시작 → ▶ 재생 클릭 (그 순간 대시보드 t = dash_t0_s)
        t0, t1 = m["dash_t0_s"], m["dash_t0_s"] + 60.0
        if off_i is not None:
            dst = os.path.join(od, "08_side_by_side.mp4")
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{off_i + t0:.3f}", "-t", "60", "-i", isaac, "-ss", f"{max(off_d, 0):.3f}", "-t", "60", "-i", sb,
                "-filter_complex", f"[0:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[a];[1:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[b];"
                f"[a][b]hstack[v];[v]pad={W}:{H}:0:(oh-ih)/2:color=black," + drawtext(f"Isaac Sim (왼쪽) ↔ 상태 보드 (오른쪽) — 전기 시나리오 {t0:.0f}~{t1:.0f} s, 시각 동기 ±0.5 s", os.path.join(tmp, "08.txt")) + "[o]",
                "-map", "[o]", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst])
            caps.append({"file": "08_side_by_side.mp4", "caption": f"Isaac 전기 시나리오 녹화(왼쪽, 장면 {t0:.0f}~{t1:.0f} s)와 대시보드 상태 보드 재생(오른쪽, 같은 시각) 나란히 — 동기는 재생 클릭 벽시계 기준 ±0.5 s",
                         "sync_method": "Isaac: recording json 의 scenario_start_wall; 대시보드: gdigrab 시작 벽시계 → ▶ 재생 클릭 벽시계 (08_dashboard_sync.json play_offset_s)", "dashboard_offset_s": round(off_d, 3),
                         "resolution": f"{W}x{H}", "fps": FPS, "size_mb": round(os.path.getsize(dst) / 1e6, 1), "speed": 1.0})
            shutil.move(sb, os.path.join(tmp, "08_dashboard_sync_raw.mp4"))
    elif not os.path.exists(os.path.join(od, "08_side_by_side.mp4")):
        missing.append(("08_side_by_side", "대시보드 동기 녹화(08_dashboard_sync.mp4) 또는 Isaac 전기 녹화 없음"))
    json.dump({"captions": caps, "missing": missing}, open(os.path.join(od, "captions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"video: {len(caps)} 편, 누락 {len(missing)} {missing}")


# ---------------------------------------------------------------- figures
def cmd_figures(a):
    od = os.path.join(out_dir(a.date), "figures"); os.makedirs(od, exist_ok=True)
    caps, missing = [], []
    for repo, relp, name, cap in FIGURES:
        src = os.path.join(MAXWELL if repo == "MX" else REPO, relp)
        if not os.path.exists(src):
            missing.append((name, f"원본 없음 {relp}")); continue
        dst = os.path.join(od, f"{name}.png"); shutil.copyfile(src, dst); w, h = img_size(dst)
        caps.append({"file": f"{name}.png", "caption": cap, "source_repo": "hoist-motor-maxwell" if repo == "MX" else "motor-predictive-maintenance", "source_path": relp, "resolution": f"{w}x{h}", "size_kb": round(os.path.getsize(dst) / 1024)})
    json.dump({"captions": caps, "missing": missing}, open(os.path.join(od, "captions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"figures: {len(caps)} 장, 누락 {len(missing)} {missing}")


# ---------------------------------------------------------------- dashboard
def cmd_dashboard(a):
    od = os.path.join(out_dir(a.date), "dashboard"); vd = os.path.join(out_dir(a.date), "video"); os.makedirs(od, exist_ok=True); os.makedirs(vd, exist_ok=True)
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:4173/", timeout=3).read(10)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"대시보드 서버 없음 (dashboard> node serve.cjs): {e}")
    sh(["node", os.path.join(HERE, "dashboard_shots.mjs"), od, vd], cwd=os.path.join(REPO, "dashboard"))


# ---------------------------------------------------------------- index / meta / README / contact sheet
def load_caps(d: str) -> dict:
    p = os.path.join(d, "captions.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"captions": [], "missing": []}


def git_head(path: str) -> str:
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def contact_sheet(root: str, out: str):
    from PIL import Image, ImageDraw, ImageFont
    files = []
    for sub in ("isaac", "hud", "dashboard", "figures"):
        files += sorted(glob.glob(os.path.join(root, sub, "*.png")))
    if not files:
        return 0
    tw, th, cols = 320, 180, 6; rows = (len(files) + cols - 1) // cols; pad = 8; lab = 22
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + lab + pad) + pad), (24, 24, 28)); d = ImageDraw.Draw(sheet); f = ImageFont.truetype(FONT, 12)
    for i, p in enumerate(files):
        r, c = divmod(i, cols); x = pad + c * (tw + pad); y = pad + r * (th + lab + pad)
        with Image.open(p) as im:
            im = im.convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        d.text((x, y + th + 3), f"{os.path.basename(os.path.dirname(p))}/{os.path.basename(p)}"[:46], font=f, fill=(220, 220, 220))
    sheet.save(out, optimize=True); return len(files)


def cmd_index(a):
    root = out_dir(a.date); sections = {}
    for sub in ("isaac", "hud", "dashboard", "figures", "video"):
        sections[sub] = load_caps(os.path.join(root, sub))
    hud_chk = os.path.join(root, "hud", "check_vs_state.json"); chk = json.load(open(hud_chk, encoding="utf-8")) if os.path.exists(hud_chk) else None
    n_sheet = contact_sheet(root, os.path.join(root, "contact_sheet.png"))
    # meta.json
    runs = {}
    for mode, (sub, max_s) in PHOTO_RUNS.items():
        mp = os.path.join(LOGS, mode, "meta.json"); runs[f"photos_{mode}"] = {"log_subdir": sub, "max_s": max_s, "shot_plan": photo_plan(mode), "verify_meta": json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else None}
    for name, (mode, plan, max_s, notc) in VIDEO_RUNS.items():
        off, m = rec_offset(name); runs[f"video_{name}"] = {"mode": mode, "cam_plan": plan, "max_s": max_s, "no_timecode": notc, "recording": m, "offset_rec_to_scenario_s": off}
    ffv = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    pw = ""
    try:
        pw = json.load(open(os.path.join(REPO, "dashboard", "node_modules", "playwright", "package.json"), encoding="utf-8"))["version"]
    except Exception:  # noqa: BLE001
        pass
    meta = {"date": a.date, "generated": dt.datetime.now().isoformat(timespec="seconds"), "git_commit_dt_repo": git_head(REPO), "git_commit_maxwell_repo": git_head(MAXWELL),
            "seed": None, "seed_note": "엔진·장면에 난수 없음 (engine/·viz/·app/ 에 random/np.random 사용 없음) — 같은 시나리오 시각이면 같은 값", "playback_speed": 1.0, "speed_note": "실시간 1× (time_scale 1), 영상 배속 없음",
            "video": {"resolution": f"{W}x{H}", "fps": FPS, "codec": "H.264 (libx264 crf 21, 60 MB 초과 시 crf 26)", "capture": "ffmpeg gdigrab 데스크톱 창 영역 (HUD 포함) → 장면 시각으로 자르고 1920×1080 scale/pad, 제목 자막 5 s"},
            "photos": {"isaac": "capture_viewport_to_file (뷰포트 텍스처 해상도 지정, omni.ui HUD 미포함)", "hud": "뷰포트 캡처 + 같은 시각 state.csv 값 합성 (새 계산 없음)", "dashboard": "Playwright Chromium 1920×1080 (네이티브 title 툴팁은 DOM 오버레이로 표시)"},
            "tools": {"isaac_sim": "4.5.0", "ffmpeg": ffv, "playwright": pw, "python": sys.version.split()[0]}, "isaac_runs": runs, "window_resolution": [W, H], "motor": "M1 (HLP-2.2/4)",
            "hud_check_vs_state": {"result": chk["result"], "ok": chk["ok"], "n": chk["n"]} if chk else None, "excluded_22kW": sections["dashboard"].get("excluded", [])}
    json.dump(meta, open(os.path.join(root, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # index.md
    L = [f"# 보고용 미디어 팩 — {a.date[:4]}-{a.date[4:6]}-{a.date[6:]}", "",
         f"M1 (HLP-2.2/4) 디지털 트윈 — Isaac Sim 4.5 장면·HUD·대시보드·해석 그림. 커밋 DT `{meta['git_commit_dt_repo']}` · Maxwell `{meta['git_commit_maxwell_repo']}` · 시드 없음(결정적) · 배속 1×.",
         "모든 숫자는 엔진 출력(state.csv)·검증 산출물·LUT 값이며 연출용 숫자는 없다. 파일명은 ASCII, 설명은 이 표의 캡션. 규격·재현·수동 캡처 체크리스트는 `README.md`.", "",
         f"![contact sheet](contact_sheet.png)  ({n_sheet} 장 썸네일)", ""]
    def table(title, caps, cols):
        L.extend([f"## {title}", "", "| " + " | ".join(h for h, _ in cols) + " |", "|" + "---|" * len(cols)])
        for c in caps:
            L.append("| " + " | ".join(str(fn(c)) for _, fn in cols) + " |")
        L.append("")
    sub = "isaac"; table(f"Isaac Sim 사진 ({len(sections[sub]['captions'])} 장) — `isaac/`", sections[sub]["captions"],
                        [("파일", lambda c: f"[{c['file']}]({sub}/{c['file']})"), ("해상도", lambda c: c["resolution"]), ("모드·t(s)·뷰·카메라", lambda c: f"{c['mode']} · {c['t_session_s']} · {c['view']} · {c['camera']}"), ("캡션", lambda c: c["caption"] + (f" ({c['note']})" if c.get("note") else "")), ("KB", lambda c: c["size_kb"])])
    sub = "hud"; table(f"HUD 합성 사진 ({len(sections[sub]['captions'])} 장) — `hud/`" + (f" · state.csv 대조 {chk['ok']}/{chk['n']} {chk['result']}" if chk else ""), sections[sub]["captions"],
                      [("파일", lambda c: f"[{c['file']}]({sub}/{c['file']})"), ("t(s)", lambda c: c["t_session_s"]), ("판정", lambda c: f"{c['values']['status']} ({c['values']['cause_signal']} {c['values']['cause_value']})"),
                       ("I₂/I₁ · I R/S/T [A] · 권선 °C", lambda c: f"{c['values']['i2_over_i1']} · {c['values']['Ia_rms'][:5]}/{c['values']['Ib_rms'][:5]}/{c['values']['Ic_rms'][:5]} · {c['values']['T_winding'][:5]}"), ("캡션", lambda c: c["caption"]), ("KB", lambda c: c["size_kb"])])
    sub = "dashboard"; table(f"대시보드 사진 ({len(sections[sub]['captions'])} 장) — `dashboard/`", sections[sub]["captions"],
                            [("파일", lambda c: f"[{c['file']}]({sub}/{c['file']})"), ("해상도", lambda c: c.get("resolution", "")), ("URL", lambda c: f"`{c.get('url', '')}`"), ("캡션", lambda c: c["caption"] + (f" — 툴팁 원문: “{c['tooltip']}”" if c.get("tooltip") else "")), ("22 kW 문구", lambda c: "보임" if c.get("kw22_visible") else "없음")])
    if sections["dashboard"].get("excluded"):
        L.extend(["제외(22 kW 자산·문구): " + "; ".join(f"{e['name']} — {e['reason']}" for e in sections["dashboard"]["excluded"]), ""])
    sub = "video"; table(f"영상·GIF ({len(sections[sub]['captions'])} 편) — `video/`", sections[sub]["captions"],
                        [("파일", lambda c: f"[{c['file']}]({sub}/{c['file']})"), ("길이 s", lambda c: c.get("duration_s", "")), ("장면 시각", lambda c: f"{c['scenario_t_s'][0]:.0f}~{c['scenario_t_s'][1]:.0f} s" if c.get("scenario_t_s") else c.get("source", "")), ("캡션", lambda c: c["caption"]), ("MB", lambda c: c.get("size_mb", ""))])
    sub = "figures"; table(f"해석·검증 그림 ({len(sections[sub]['captions'])} 장) — `figures/`", sections[sub]["captions"],
                          [("파일", lambda c: f"[{c['file']}]({sub}/{c['file']})"), ("원본", lambda c: f"{c['source_repo']}: `{c['source_path']}`"), ("해상도(원본 그대로)", lambda c: c["resolution"]), ("캡션", lambda c: c["caption"])])
    miss = [(s, m) for s in sections for m in sections[s].get("missing", [])]
    L.extend(["## 못 찍은 것", ""] + ([f"- `{s}` {m[0]}: {m[1]}" for s, m in miss] or ["- 없음"]) + [""])
    open(os.path.join(root, "index.md"), "w", encoding="utf-8").write("\n".join(L))
    write_readme(root, a.date, meta, sections)
    print(f"index: isaac {len(sections['isaac']['captions'])} hud {len(sections['hud']['captions'])} dashboard {len(sections['dashboard']['captions'])} video {len(sections['video']['captions'])} figures {len(sections['figures']['captions'])}; 누락 {len(miss)}; contact {n_sheet}")


def write_readme(root: str, date: str, meta: dict, sections: dict):
    big = [c for c in sections["video"]["captions"] if c.get("size_mb", 0) > 60]
    L = [f"# docs/media/{date} — 보고용 미디어 팩", "",
         "## 규격", "- 영상: 1920×1080 · 30 fps · H.264 mp4 · 무음 · 60 MB 이하 (초과분은 `.gitignore`, 경로는 `docs/media/README.md`) · 배속 1×(실시간)",
         "- 사진: 1920×1080 PNG (isaac_01·04·08 은 2560×1440) · 파일명 ASCII · 한글은 `index.md` 캡션", "- 숫자: 전부 엔진 출력(state.csv)·검증 산출물·LUT. 연출용 숫자 없음. 22 kW 자산 미사용(22 kW 문구가 보이는 화면은 `index.md` 에 표시·제외 사유 기록)", "",
         "## 재현 (motor_dt_viz 에서, PowerShell)", "```", "py -3.12 -X utf8 tools\\media\\capture_all.py plan", "cmd /c logs\\media\\run_isaac.cmd          # Isaac 사진 2회 + 영상 4회 (~20 분, 창을 가리지 말 것 — gdigrab 데스크톱 캡처)",
         "py -3.12 -X utf8 tools\\media\\capture_all.py isaac", "py -3.12 -X utf8 tools\\media\\capture_all.py hud", "cd ..\\dashboard; node serve.cjs      # 다른 창", "py -3.12 -X utf8 tools\\media\\capture_all.py dashboard",
         "py -3.12 -X utf8 tools\\media\\capture_all.py video", "py -3.12 -X utf8 tools\\media\\capture_all.py figures", "py -3.12 -X utf8 tools\\media\\capture_all.py index", "```",
         "Isaac 은 PowerShell/cmd 에서만 (Git Bash 자식은 Startup 직후 조용히 종료). 카메라 프리셋은 `tools/media/cameras.yaml` = `viz/m1_model.py` 의 값, 캡처용 인자는 `--res W H`·`--cam_plan`·`--shot_plan`(파일명 `@WxH`).", "",
         "## 한계", "- Isaac 뷰포트 캡처(`capture_viewport_to_file`)에는 omni.ui HUD 가 찍히지 않는다 → `hud/` 는 같은 시각 state.csv 값을 합성한 것(`check_vs_state.json` 으로 1회 대조). 영상(`--record`)은 데스크톱 창 캡처라 HUD 가 그대로 들어간다.",
         "- 대시보드 네이티브 title 툴팁은 스크린샷에 안 찍혀 같은 문장을 DOM 오버레이로 그렸다(페이지 코드 변경 없음, 캡션에 원문).", "- 해설 화면(#/electrical, #/mechanical)은 이전 22 kW 녹화 영상을 재생하므로 제외했다 — 상태 보드(#/status) 기준으로 대체.",
         "- 대시보드 사진·영상은 상태 보드 **단순 보기**(2026-10-26 `dashboard: simple view (3-layer IA)` 이후) 기준이다. 전문가 보기는 10번 사진 한 장. 22 kW 문구는 근거 서랍·전문가 보기의 정직성 주석에만 보인다(index.md 표시).",
         "- 영상의 창 캡처는 창 테두리를 포함할 수 있어 1920×1080 으로 scale/pad 했다(검은 여백 가능).", ""]
    if big:
        L += ["## 60 MB 초과 영상(저장소 밖)", ""] + [f"- {c['file']} {c['size_mb']} MB → 로컬 `docs/media/{date}/video/` 에만 둠" for c in big] + [""]
    L += ["## 수동 캡처 체크리스트 (자동화 불가 — 사람이 찍어 이 폴더에 넣고 index.md 에 한 줄 추가)", "",
          "| # | 항목 | 어디서 | 파일명(ASCII) | 규격 | 비고 |", "|---|---|---|---|---|---|",
          "| 1 | Maxwell 2D 자속밀도(B) 컬러맵 — 정상 / 4턴 R_f 0.1 Ω | Ansys Electronics Desktop → 2D 설계 → Field Overlays → Mag_B, 같은 스케일 | `manual_01_maxwell_B_healthy.png`, `manual_02_maxwell_B_itsc4.png` | 1920×1080 PNG | Student 에디션은 Export 금지 → 화면 캡처(Win+Shift+S). 범례 포함 |",
          "| 2 | Maxwell 전류밀도(J) 단락 루프 | 같은 곳, Field Overlays → Jz | `manual_03_maxwell_J_itsc4.png` | 1920×1080 PNG | |",
          "| 3 | Maxwell 메시·3D 형상 | Mesh → Plot | `manual_04_maxwell_mesh.png` | 1920×1080 PNG | |",
          "| 4 | 라이브 모드 화면 (Isaac `--live` + 대시보드 `#/status?live=ws://…`) | Isaac 창과 브라우저를 한 화면에 | `manual_05_live_mode.png` | 1920×1080 PNG | 포트·live.yaml 은 바꾸지 않는다. 라이브 세션 중 HUD 와 보드 시각이 같은지 보이게 |",
          "| 5 | 실물 모터 사진 (현장) — 명판·DE 축단·전체 | 현장 | `manual_06_photo_nameplate.jpg`, `manual_07_photo_shaft_de.jpg`, `manual_08_photo_overall.jpg` | 원본 해상도 | 명판은 글자가 읽히게. 결선(Y)·정격 전류 확인용 |",
          "| 6 | (선택) 발표장 화면 — 대시보드 + Isaac 동시 투사 | 발표 리허설 | `manual_09_stage.jpg` | 원본 | |", ""]
    open(os.path.join(root, "README.md"), "w", encoding="utf-8").write("\n".join(L))


def cmd_desktop(a):
    """바탕화면 사본: ~/OneDrive/바탕 화면/M1_미디어팩_<날짜>/ (사용자 요청 2026-10-26, 저장소 사본과 같은 내용)."""
    src = out_dir(a.date); desk = os.path.join(os.path.expanduser("~"), "OneDrive", "바탕 화면")
    dst = next((d for d in (os.path.join(desk, "모터", f"M1_미디어팩_{a.date}"), os.path.join(desk, f"M1_미디어팩_{a.date}")) if os.path.isdir(d)), os.path.join(desk, "모터", f"M1_미디어팩_{a.date}"))   # 사용자가 옮긴 폴더가 있으면 거기에
    shutil.copytree(src, dst, dirs_exist_ok=True)
    n = sum(len(f) for _, _, f in os.walk(dst)); mb = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dst) for f in fs) / 1e6
    print(f"desktop: {dst} ({n} files, {mb:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("plan", "isaac", "hud", "video", "figures", "dashboard", "index", "desktop"))
    ap.add_argument("--date", default=DATE)
    ap.add_argument("--only", default="", help="video: 다시 인코딩할 clip/gif 이름만 (쉼표) — 나머지는 기존 파일 유지")
    ap.add_argument("--skip", default="", help="plan: 건너뛸 run (electrical,mechanical,orbit,vid_elec,vid_mech,vid_int)")
    ap.add_argument("--retake", default="", help="plan: 다시 찍을 전기 사진 이름 (예: isaac_03_front_shaft,isaac_05_cutaway_rotor_closeup)")
    a = ap.parse_args()
    {"plan": cmd_plan, "isaac": cmd_isaac, "hud": cmd_hud, "video": cmd_video, "figures": cmd_figures, "dashboard": cmd_dashboard, "index": cmd_index, "desktop": cmd_desktop}[a.cmd](a)


if __name__ == "__main__":
    main()
