# -*- coding: utf-8 -*-
"""verify_lut_integration.py — TASK A D6: LUT 연동 검증 → docs/electrical/lut_integration_report.md

검사 (하나라도 실패하면 종료 코드 1, 보고서에는 모두 기록):
  V1  LUT 격자 ↔ mccm_results.json 케이스 (C1·C3·C4·C1-R·C1-L) I₂/I₁·I₂/I_n ±1 %
  V2  M1 LUT 방식: 고유 비대칭 OFF 로 합성한 파형의 I₂/I₁ 이 LUT 값 ±1 % · 위상 ±1°
  V3  고유 비대칭 ON: I₂/I₁ 이 범위 [|r−h|, r+h] 안 (4턴·12턴), 값 기록
  V4  legacy 회귀: method legacy 로 M1 → 0.104 / 0.269 ±0.1 %, 기준 모터(M5·기본)도 같음
  V5  부하 50 % vs 100 % (4턴·R_f 0.1): I₂/I₁ 과 I₂/I_n 의 변화율 비교
  V6  config/thresholds.yaml i2i1 경계로 케이스별 판정 (최소/설계/최대) — 판정 코드는 바꾸지 않는다
  V7  라이브 10 s: Isaac Sim demo_integrated --live --motor M1 --mode electrical 을 띄워 state 에 새 키가 오고 값이 맞는지 (--skip-live 로 생략)
  V8  금지 파일 git diff 없음: config/thresholds.yaml, config/motors/*, engine/thresholds.py, config/live.yaml, tools/firewall_rules.ps1

실행: py -3.12 tools/electrical/verify_lut_integration.py [--skip-live] [--live-timeout 240]
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ)

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.lut_source import LutSource, default_lut_path  # noqa: E402

MCCM_RESULTS = r"C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\mccm_results.json"
REPORT = os.path.join(VIZ, "docs", "electrical", "lut_integration_report.md")
FORBIDDEN = ["motor_dt_viz/config/thresholds.yaml", "motor_dt_viz/config/motors", "motor_dt_viz/engine/thresholds.py",
             "motor_dt_viz/config/live.yaml", "motor_dt_viz/tools/firewall_rules.ps1"]
ISAAC_PY = r"C:\ISSACS~1\python.bat"

results: list[dict] = []
lines: list[str] = []


def check(vid: str, name: str, ok: bool, detail: str) -> bool:
    results.append({"id": vid, "name": name, "ok": bool(ok), "detail": detail})
    print(f"[{vid}] {'PASS' if ok else 'FAIL'} {name} — {detail}")
    return bool(ok)


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def f(v, n=4):
    return "—" if v is None else f"{v:.{n}f}"


def level(v: float, th: dict) -> str:
    if v >= float(th["danger_from"]):
        return "DANGER"
    if v >= float(th["safe_below"]):
        return "WARN"
    return "SAFE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-live", action="store_true")
    ap.add_argument("--live-timeout", type=float, default=240.0, help="Isaac 기동 + 접속 대기 [s]")
    ap.add_argument("--live-port", type=int, default=8766, help="검증용 포트 (운영 8765 와 분리)")
    a = ap.parse_args()

    el_cfg = load("electrical")
    lut_path = os.path.join(VIZ, el_cfg["source"]["lut"])
    lut = LutSource(lut_path)
    m1 = ml.load_motor("M1")
    cm = CurrentModel(ml.electrical_cfg(m1), ml.motor_spec(m1))
    lines.append(f"# LUT 연동 검증 보고 (TASK A D6) — {time.strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"- electrical.yaml version {el_cfg.get('version')} · method `{el_cfg.get('method')}` → M1 실제 동작 **{cm.method}** ({cm.method_reason})")
    lines.append(f"- LUT `{os.path.relpath(lut_path, VIZ)}` sha256 `{cm.lut_sha256[:12]}…` · 원본 mccm_lut sha `{lut.provenance.get('source_sha256', '')[:12]}…` · "
                 f"grade {lut.provenance.get('grade')} · status {lut.provenance.get('status')} · fem_verified {lut.provenance.get('fem_verified')} · "
                 f"R_fe 보정 {lut.provenance.get('rfe_calibration')}")
    lines.append(f"- 정격 전류: electrical.yaml rated_current_A **{cm.rated_current_A} A** (LUT I_n) vs config/motors/M1.yaml rated_line_current_a **{cm.motor.rated_line_A} A** "
                 f"→ 차이 {cm.rated_current_mismatch_pct:+.1f} % (2026-10-19 결정 (A): M1.yaml 을 카탈로그 4.73 A·Y·η 0.895·pf 0.79 로 통일 → 0 % 여야 한다)")
    lines.append(f"- 고유 비대칭 inherent: enabled {cm.inherent_enabled}, I₂/I₁ {cm.inherent_i2i1}, 위상 {cm.inherent_angle_deg}° (AI Hub 정상 중앙값)\n")

    # ---------------- V1
    lines.append("## V1. LUT 격자 ↔ mccm_results 케이스 (±1 %)\n")
    if os.path.exists(MCCM_RESULTS):
        res = json.load(open(MCCM_RESULTS, encoding="utf-8"))["cases"]
        cases = {"C1": (4, 0.1, 100), "C3": (12, 0.1, 100), "C4": (16, 0.1, 100), "C1-R": (4, 1.0, 100), "C1-L": (4, 0.1, 50)}
        rows, ok = [], True
        for name, (turns, rf, ld) in cases.items():
            q = lut.query(lut.turns_to_frac(turns), rf, ld)
            r0 = res[name]["I2_over_I1"]; rn0 = res[name]["I2"] / lut.rated_current_A
            d1 = (q["i2_over_i1"] / r0 - 1) * 100; d2 = (q["i2_over_in"] / rn0 - 1) * 100
            good = abs(d1) <= 1.0 and abs(d2) <= 1.0
            ok &= good
            rows.append([name, turns, rf, ld, f(r0), f(q["i2_over_i1"]), f"{d1:+.2f} %", f(rn0), f(q["i2_over_in"]), f"{d2:+.2f} %", f(q["i_f_A"], 2), f(q["p_loop_total_W"], 1), "✓" if good else "✗"])
        lines.append(md_table(["케이스", "턴", "R_f Ω", "부하 %", "mccm I₂/I₁", "LUT", "Δ", "mccm I₂/I_n", "LUT", "Δ", "I_f A", "P_loop_total W", "판정"], rows))
        check("V1", "LUT ↔ mccm_results ±1 %", ok, f"{len(rows)} 케이스")
    else:
        lines.append("mccm_results.json 없음 — 건너뜀")
        check("V1", "LUT ↔ mccm_results", False, "mccm_results.json 없음")

    # ---------------- V2 / V3
    lines.append("\n## V2·V3. M1 합성 파형의 I₂/I₁ — 고유 비대칭 OFF (LUT 재현 ±1 %) / ON (범위 [|r−h|, r+h])\n")
    cfg_off = copy.deepcopy(ml.electrical_cfg(m1)); cfg_off["inherent"]["enabled"] = False
    cm_off = CurrentModel(cfg_off, ml.motor_spec(m1))
    rows, ok2, ok3 = [], True, True
    h = cm.inherent_i2i1
    for case in ("healthy", "itsc_4turn", "itsc_12turn"):
        q = cm.lut_point(case)
        st_off = cm_off.evaluate_case(case); st_on = cm.evaluate_case(case)
        r = q["i2_over_i1"]; ang = q["i2_angle_deg"]
        if r < 1e-6:                      # 0 % 행: 수치 잔차(1e-10 급) — 0 으로 본다
            r = 0.0
        d = (st_off.i2_over_i1 / r - 1) * 100 if r > 0 else st_off.i2_over_i1
        dang = abs(((st_off.i2_angle_deg or 0) - ang + 180) % 360 - 180) if r > 0 else 0.0
        g2 = (abs(d) <= 1.0 if r > 0 else st_off.i2_over_i1 < 1e-9) and dang <= 1.0
        lo, hi = abs(r - h), r + h
        g3 = lo - 1e-6 <= st_on.i2_over_i1 <= hi + 1e-6 and abs(st_on.i2_over_i1 - cm.expected_i2i1(case)) < 1e-3
        ok2 &= g2; ok3 &= g3
        rows.append([case, q["turns"], f(r), f(ang, 1), f(st_off.i2_over_i1), f"{d:+.2f} %" if r > 0 else "0", f(dang, 2), "✓" if g2 else "✗",
                     f(lo), f(st_on.i2_over_i1), f(hi), f(cm.expected_i2i1(case)), f(st_on.i2_over_in), f(st_on.i2_angle_deg, 1), "✓" if g3 else "✗"])
    lines.append(md_table(["케이스", "턴", "LUT I₂/I₁", "LUT 위상°", "합성(OFF)", "Δ", "위상차°", "V2", "최소 |r−h|", "합성(ON)", "최대 r+h", "설계값", "I₂/I_n(ON)", "위상(ON)°", "V3"], rows))
    lines.append(f"\n4턴 고유 비대칭 범위: **{f(abs(cm.lut_point('itsc_4turn')['i2_over_i1'] - h))} ~ {f(cm.lut_point('itsc_4turn')['i2_over_i1'] + h)}** "
                 f"(위상 0° 가정 합성값 {f(cm.expected_i2i1('itsc_4turn'))}; LUT I₂ 위상 {f(cm.lut_point('itsc_4turn')['i2_angle_deg'], 1)}° 라 최대값보다 조금 작다)")
    check("V2", "합성 파형 ↔ LUT ±1 % (inherent OFF)", ok2, "healthy/4T/12T")
    check("V3", "inherent ON 범위", ok3, f"h={h}")

    # ---------------- V4 legacy
    lines.append("\n## V4. legacy 회귀 (±0.1 %)\n")
    cfg_leg = copy.deepcopy(ml.electrical_cfg(m1)); cfg_leg["method"] = "legacy"
    cm_leg = CurrentModel(cfg_leg, ml.motor_spec(m1))
    cm_ref = CurrentModel()        # 기준 모터(config/motor.yaml) — method lut 라도 M1 아님 → legacy
    cm_m5 = CurrentModel(ml.electrical_cfg(ml.load_motor("M5")), ml.motor_spec(ml.load_motor("M5")))
    rows, ok4 = [], True
    for label, m in (("M1 method:legacy", cm_leg), ("기본 CurrentModel()", cm_ref), ("M5 (transfer false)", cm_m5)):
        for case, tgt in (("healthy", 0.006), ("itsc_4turn", 0.104), ("itsc_12turn", 0.269)):
            v = m.evaluate_case(case).i2_over_i1
            d = (v / tgt - 1) * 100
            g = abs(d) <= 0.1 and m.method == "legacy"
            ok4 &= g
            rows.append([label, m.method, case, tgt, f(v), f"{d:+.3f} %", "✓" if g else "✗"])
    lines.append(md_table(["모델", "method", "케이스", "목표", "값", "Δ", "판정"], rows))
    check("V4", "legacy 0.104/0.269 ±0.1 %", ok4, "M1 legacy · 기본 · M5")

    # ---------------- V5 load
    lines.append("\n## V5. 부하 50 % vs 100 % (4턴 · R_f 0.1 Ω) — I₂/I₁ 은 부하에 따라 흔들리고 I₂/I_n 은 덜 흔들린다\n")
    rows = []
    for turns in (4, 8, 12):
        q50 = lut.query(lut.turns_to_frac(turns), 0.1, 50); q100 = lut.query(lut.turns_to_frac(turns), 0.1, 100); q115 = lut.query(lut.turns_to_frac(turns), 0.1, 115)
        rows.append([turns, f(q50["i2_over_i1"]), f(q100["i2_over_i1"]), f(q115["i2_over_i1"]), f"{(q50['i2_over_i1'] / q100['i2_over_i1'] - 1) * 100:+.1f} %",
                     f(q50["i2_over_in"]), f(q100["i2_over_in"]), f(q115["i2_over_in"]), f"{(q50['i2_over_in'] / q100['i2_over_in'] - 1) * 100:+.1f} %"])
    lines.append(md_table(["턴", "I₂/I₁ 50 %", "100 %", "115 %", "50 vs 100", "I₂/I_n 50 %", "100 %", "115 %", "50 vs 100"], rows))
    q50 = lut.query(lut.turns_to_frac(4), 0.1, 50); q100 = lut.query(lut.turns_to_frac(4), 0.1, 100)
    v5 = abs(q50["i2_over_in"] / q100["i2_over_in"] - 1) < abs(q50["i2_over_i1"] / q100["i2_over_i1"] - 1)
    check("V5", "I₂/I_n 이 I₂/I₁ 보다 부하 의존 작음 (4턴)", v5, f"I₂/I₁ {(q50['i2_over_i1'] / q100['i2_over_i1'] - 1) * 100:+.1f} % vs I₂/I_n {(q50['i2_over_in'] / q100['i2_over_in'] - 1) * 100:+.1f} %")

    # ---------------- V6 thresholds
    th = load("thresholds")["i2i1"]
    lines.append(f"\n## V6. config/thresholds.yaml i2i1 (safe_below {th['safe_below']}, danger_from {th['danger_from']}) 로 본 케이스 판정 — 임계값·판정 코드 무변경, 기록만\n")
    rows = []
    for c in cm.cases_summary():
        key = c["key"]; q = cm.lut_point(key)
        if q:
            r = q["i2_over_i1"]; lo, hi = abs(r - h), r + h; des = cm.expected_i2i1(key)
            rows.append([c["label"], f"LUT {c['turns']:g}T" + (f"/{c['R_f_ohm']}Ω" if c["R_f_ohm"] else ""), f(lo), level(lo, th), f(des), level(des, th), f(hi), level(hi, th), f(q["i2_over_in"])])
        else:
            v = cm.evaluate_case(key).i2_over_i1
            rows.append([c["label"], "legacy", "—", "—", f(v), level(v, th), "—", "—", "—"])
    for turns in (8,):
        q = lut.query(lut.turns_to_frac(turns), 0.1, 100); r = q["i2_over_i1"]
        rows.append([f"(참고) {turns}턴 R_f 0.1", "LUT", f(abs(r - h)), level(abs(r - h), th), f(r), level(r, th), f(r + h), level(r + h, th), f(q["i2_over_in"])])
    lines.append(md_table(["케이스", "근거", "최소", "판정", "설계값", "판정", "최대", "판정", "LUT I₂/I_n"], rows))
    lines.append("\n해석: 4턴은 고유 비대칭 위상에 따라 SAFE~WARN(최소 0.018)·WARN(설계 0.071) 사이, 12턴은 모든 위상에서 DANGER. 확실한 탐지(최소값 ≥ danger_from)는 8턴부터 — "
                 "분석 보고(권상모터_3D모델링/docs/maxwell/analysis_report.md 표 G)와 같다. 임계값 변경은 제안으로만(docs/judgment_basis.md).")
    check("V6", "thresholds 판정표 기록", True, f"{len(rows)} 행")

    # ---------------- V7 live
    lines.append("\n## V7. 라이브 10 s (Isaac Sim `demo_integrated --live --motor M1 --mode electrical`, 검증 포트)\n")
    if a.skip_live:
        lines.append("`--skip-live` 로 생략")
        check("V7", "라이브 10 s", True, "생략(--skip-live)")
    else:
        ok7, detail7, rows7 = run_live(a.live_port, a.live_timeout, cm)
        lines.extend(rows7)
        check("V7", "라이브 10 s", ok7, detail7)

    # ---------------- V8 forbidden diff
    lines.append("\n## V8. 금지 파일 변경 없음 (git diff --stat)\n")
    try:
        out = subprocess.run(["git", "diff", "--stat", "--", *FORBIDDEN], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        out2 = subprocess.run(["git", "status", "--short", "--", *FORBIDDEN], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        clean = (out == "" and out2 == "")
        lines.append("```\n" + (out or out2 or "(변경 없음)") + "\n```")
        lines.append("대상: " + ", ".join(f"`{p}`" for p in FORBIDDEN))
        check("V8", "금지 파일 무변경", clean, "clean" if clean else out or out2)
    except Exception as e:  # noqa: BLE001
        check("V8", "금지 파일 무변경", False, str(e))

    # ---------------- 요약
    n_ok = sum(1 for r in results if r["ok"])
    summary = ["## 요약\n", md_table(["#", "검사", "결과", "비고"], [[r["id"], r["name"], "PASS" if r["ok"] else "**FAIL**", r["detail"]] for r in results]),
               f"\n**{n_ok}/{len(results)} 통과.** 변경 파일: config/electrical.yaml(v2), engine/current_model.py, engine/lut_source.py, engine/thermal_model.py(extra_loss_W 훅), "
               "app/demo_integrated.py(state 키 추가·열 연동·CSV 열), viz/hud.py, tools/electrical/*, tests/test_lut_source.py, data/electrical/*, dashboard(src 5개·css·dist 빌드). "
               "WebSocket 포트·스키마 번호·명령 목록은 그대로 (state 에 키만 덧붙임).\n"]
    text = "\n".join(lines[:5] + summary + lines[5:]) + "\n"
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w", encoding="utf-8").write(text)
    print(f"\n보고서: {REPORT}  ({n_ok}/{len(results)} PASS)")
    return 0 if n_ok == len(results) else 1


# ------------------------------------------------------------------------- V7
def run_live(port: int, timeout: float, cm: CurrentModel):
    """Isaac Sim 데모를 headless 로 띄우고(--live_port), 10 s 동안 state 를 받아 새 키와 값을 확인한다."""
    try:
        import websockets  # noqa: F401
    except ImportError:
        return False, "websockets 모듈 없음", ["websockets 모듈 없음 — 생략"]
    if not os.path.exists(r"C:\issac sim\python.bat"):
        return False, "Isaac Sim python.bat 없음", ["Isaac Sim 없음 — 생략"]
    log_dir = os.path.join(VIZ, "logs", "verify_lut"); os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "demo_stdout.log")
    cmd = f'"{ISAAC_PY}" app\\demo_integrated.py --mode electrical --motor M1 --live --live_port {port} --max_s 45 --log_subdir verify_lut'
    print("[V7] launching:", cmd, flush=True)
    logf = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(cmd, cwd=VIZ, shell=True, stdout=logf, stderr=subprocess.STDOUT)
    rows: list[str] = []
    states: list[dict] = []
    acks: list[dict] = []
    t0 = time.time()

    async def session():
        import websockets
        url = f"ws://127.0.0.1:{port}"
        ws = None
        while time.time() - t0 < timeout:
            try:
                ws = await websockets.connect(url, open_timeout=3)
                break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(2)
        if ws is None:
            return "접속 실패 (기동 시간 초과)"
        t_conn = time.time()
        rows.append(f"- 접속까지 {t_conn - t0:.1f} s")
        injected = False
        async for raw in ws:
            m = json.loads(raw)
            if m.get("type") == "state":
                states.append(m)
                if not injected and len(states) >= 20:          # 2 s 정상 → 4턴 주입
                    await ws.send(json.dumps({"type": "command", "id": "v7", "name": "inject_fault", "args": {"fault": "itsc_4turn", "on": True}}))
                    injected = True
            elif m.get("type") == "ack":
                acks.append(m)
            if time.time() - t_conn >= 10.0:
                break
        await ws.close()
        return None

    err = asyncio.run(session())
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
    logf.close()
    if err:
        return False, err, rows + [f"- {err} (로그 {os.path.relpath(log_path, VIZ)})"]
    if not states:
        return False, "state 없음", rows + ["- state 수신 없음"]
    first, last = states[0], states[-1]
    keys_ok = all(k in last for k in ("i2_over_in", "electrical_source", "i2i1_marks", "p_loop_total_W"))
    src = last.get("electrical_source") or {}
    healthy = [s for s in states if s.get("case") == "healthy"]
    itsc = [s for s in states if s.get("case") == "itsc_4turn"]
    exp_h = cm.expected_i2i1("healthy"); exp_4 = cm.expected_i2i1("itsc_4turn")
    h_ok = bool(healthy) and abs(healthy[-1]["i2_over_i1"] - exp_h) <= 0.002
    i_ok = bool(itsc) and abs(itsc[-1]["i2_over_i1"] - exp_4) <= 0.002
    ack_ok = any(a_.get("id") == "v7" and a_.get("ok") for a_ in acks)
    rows += [f"- state {len(states)} 건 / 10 s (schema {last.get('schema')}, motor {last.get('motor_id')}, mode {last.get('mode')}), ack {len(acks)} 건",
             f"- 새 키 존재: {'✓' if keys_ok else '✗'} (i2_over_in, electrical_source, i2i1_marks, p_loop_total_W)",
             f"- electrical_source: method {src.get('method')} · grade {src.get('grade')} · status {src.get('status')} · fem_verified {src.get('fem_verified')} · {src.get('lut_version')} · cases {len(src.get('cases') or [])}",
             f"- healthy: I₂/I₁ {healthy[-1]['i2_over_i1'] if healthy else '—'} (설계 {exp_h:.4f}) · I₂/I_n {healthy[-1].get('i2_over_in') if healthy else '—'} → {'✓' if h_ok else '✗'}",
             f"- itsc_4turn 주입 ack {'✓' if ack_ok else '✗'}: I₂/I₁ {itsc[-1]['i2_over_i1'] if itsc else '—'} (설계 {exp_4:.4f}) · I₂/I_n {itsc[-1].get('i2_over_in') if itsc else '—'} · "
             f"P_loop_total {itsc[-1].get('p_loop_total_W') if itsc else '—'} W · Ia/Ib/Ic {[itsc[-1].get(k) for k in ('Ia_rms', 'Ib_rms', 'Ic_rms')] if itsc else '—'} → {'✓' if i_ok else '✗'}",
             f"- i2i1_marks: {last.get('i2i1_marks')}",
             f"- 로그: {os.path.relpath(log_path, VIZ)}"]
    ok = keys_ok and h_ok and i_ok and ack_ok and src.get("method") == "lut"
    json.dump({"states": states[-5:], "acks": acks, "n_states": len(states)}, open(os.path.join(log_dir, "live_sample.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return ok, f"{len(states)} states, healthy {healthy[-1]['i2_over_i1'] if healthy else '—'}, 4T {itsc[-1]['i2_over_i1'] if itsc else '—'}", rows


if __name__ == "__main__":
    sys.exit(main())
