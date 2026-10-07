# -*- coding: utf-8 -*-
"""run_fleet.py — 모터 5종 × 모드(기계·전기) 배치 시뮬레이션 (TASK_다중모터 §6). 엔진만으로 돌린다 (Isaac Sim 불필요).

  python tools/run_fleet.py                          # M1..M5 × mechanical,electrical → logs/fleet/<id>/<mode>/
  python tools/run_fleet.py --motors M3 --modes electrical

출력 (모터·모드마다):
  demo_fleet.csv     데모(demo_integrated.py)와 같은 컬럼 — 기존 export 도구가 그대로 읽는다
  status_fleet.csv   판정 엔진(engine/thresholds.py) 결과: 시각별 상태·원인 신호·신호별 등급
  meta.json          모터·모드·시간 간격·시나리오·엔진 버전

왜 엔진만으로 하나 (P0 결정): 열·전류 수치의 정본은 엔진이고 Isaac 로그는 프레임 시각 흔들림만 더한다
(M5 실측: 엔진 재실행 ↔ Isaac 로그 차이 ≤2.3 °C / 0.05 A). 시나리오 타임라인·결함 파라미터는 공통, 결과는 모터별로 다르다.
M5 는 끝에서 기존 Isaac 로그와 대조해 회귀를 확인한다.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, VIZ)

from engine import motor_library as ml  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.fault_injector import FaultInjector  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402
from engine.thresholds import Judge  # noqa: E402

COLS = ["t_s", "t_real_s", "mode", "step", "case", "faults", "load", "rpm",
        "T_winding", "T_stator_core", "T_rotor", "T_shaft", "T_bearing_de", "T_bearing_nde", "T_endshield_de", "T_endshield_nde", "T_frame",
        "Ia_rms", "Ib_rms", "Ic_rms", "i2_over_i1", "vibration_mms", "iso_zone", "fps"]
STATUS_COLS = ["t_real_s", "status", "label", "cause_signal", "cause_component", "value", "threshold",
               "temperature", "current_ratio", "i2i1", "vibration", "bearing_index"]
H = 1.0 / 60.0        # 적분 간격 (데모 프레임과 같음)
RATE_HZ = 4.0         # 로그 간격 (데모 로그 ≈ 4 Hz)
TAIL_S = 5.0          # 시나리오 끝 뒤 여유 (데모와 같음)


def bearing_index(thermal_cfg: dict, faults: list[str]) -> float:
    """시뮬레이션용 베어링 결함 지표 = 베어링을 겨냥한 결함의 손실 배율 (정상 1.0). 실측 후 포락선 BPFO 피크비로 교체."""
    idx = 1.0
    for f in faults:
        fc = thermal_cfg["faults"].get(f) or {}
        if str(fc.get("target", "")).startswith("bearing") and "loss_multiplier" in fc:
            idx = max(idx, float(fc["loss_multiplier"]))
    return idx


def run_one(motor: ml.Motor, mode: str, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    player = ScenarioPlayer.for_mode(mode)
    th_cfg, el_cfg = ml.thermal_cfg(motor), ml.electrical_cfg(motor)
    tm = ThermalModel(th_cfg)
    cm = CurrentModel(el_cfg, ml.motor_spec(motor))
    inj = FaultInjector(th_cfg, el_cfg, vib_thresholds=motor.vib_thresholds)
    judge = Judge(motor=motor)
    cases = {c: cm.evaluate_case(c) for c in cm.cases}            # 해석식: 케이스별 상수
    i_line = motor.rated_line_current_a
    total = player.total_duration + TAIL_S
    rows, srows = [], []
    t, next_log = 0.0, 0.0
    st = tm.step(0.0, 1.0, [], use_duty_cycle=False)
    while t <= total + 1e-9:
        f = player.frame_at(min(t, player.total_duration - 1e-6)) if t < player.total_duration else player.frame_at(player.total_duration - 1e-6)
        step_id = f.step_id if t < player.total_duration else "manual"
        case = f.electrical_case if mode == "electrical" else "healthy"
        faults = list(f.thermal_faults) if mode == "mechanical" else []
        load = f.load
        if mode == "mechanical":
            st = tm.step(H * f.time_scale, load, faults, winding_current_pu=None, use_duty_cycle=False)
        else:
            st = tm.step(0.0, load, [], use_duty_cycle=False)
        if t + 1e-9 >= next_log:
            cs = cases[case]
            vib = st.vibration_mms
            rpm = motor.sync_rpm - (motor.sync_rpm - motor.rated_rpm) * (load if mode == "electrical" else 1.0)
            T = st.temperature_C
            rows.append([round(t, 2), round(t, 3), mode, step_id, case, ";".join(faults), load, round(rpm, 1)]
                        + [round(T[k], 1) for k in ("winding", "stator_core", "rotor", "shaft", "bearing_de", "bearing_nde", "endshield_de", "endshield_nde", "frame")]
                        + [round(x, 1) for x in cs.rms_A] + [round(cs.i2_over_i1, 4), round(vib, 1), inj.iso_zone(vib), 60.0])
            v = judge.update(t, {
                "temperature": {k: T[k] for k in T},
                "current_ratio": {p: cs.rms_A[k] / i_line for k, p in enumerate("ABC")},
                "i2i1": cs.i2_over_i1, "vibration": vib,
                "bearing_index": bearing_index(th_cfg, faults),
            })
            worst = {k: "SAFE" for k in ("temperature", "current_ratio", "i2i1", "vibration", "bearing_index")}
            for s in v.signals:
                if ("SAFE", "WARN", "DANGER").index(s.level) > ("SAFE", "WARN", "DANGER").index(worst[s.kind]):
                    worst[s.kind] = s.level
            srows.append([round(t, 3), v.status, v.label_ko, v.cause_signal, v.cause_component, round(v.value, 4), v.threshold]
                         + [worst[k] for k in ("temperature", "current_ratio", "i2i1", "vibration", "bearing_index")])
            next_log += 1.0 / RATE_HZ
        t += H
    with open(os.path.join(out_dir, "demo_fleet.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(COLS); w.writerows(rows)
    with open(os.path.join(out_dir, "status_fleet.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(STATUS_COLS); w.writerows(srows)
    meta = {"motor": motor.id, "name": motor.name, "mode": mode, "source": "engine", "h_s": H, "log_hz": RATE_HZ,
            "scenario": ScenarioPlayer.CONFIG_BY_MODE[mode], "total_duration_s": player.total_duration,
            "thermal_scaled_from": th_cfg.get("scaled_from"), "vibration": motor.vib_thresholds,
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": len(rows)}
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    return meta


def regression_m5(out_root: str) -> dict:
    """M5 엔진 로그 ↔ 기존 Isaac 로그 (장면 종료 −0.3 s 시점, 경계 ±1 s 제외) 최대 차이."""
    res = {}
    for mode, cols, tol in (("mechanical", ["T_winding", "T_bearing_de", "T_shaft", "T_frame"], 2.5),
                            ("electrical", ["Ia_rms", "Ib_rms", "Ic_rms", "i2_over_i1"], 0.06)):
        isaac = sorted(glob.glob(os.path.join(VIZ, "logs", mode, "demo_*.csv")))
        if not isaac:
            res[mode] = {"skipped": "Isaac 로그 없음"}; continue
        a = list(csv.DictReader(open(isaac[-1], encoding="utf-8", newline="")))
        b = list(csv.DictReader(open(os.path.join(out_root, "M5", mode, "demo_fleet.csv"), encoding="utf-8", newline="")))
        player = ScenarioPlayer.for_mode(mode)
        worst = 0.0
        acc = 0.0
        for s in player.steps:
            acc += float(s["duration_s"]); te = acc - 0.3
            ra = max((r for r in a if float(r["t_real_s"]) <= te), key=lambda r: float(r["t_real_s"]))
            rb = max((r for r in b if float(r["t_real_s"]) <= te), key=lambda r: float(r["t_real_s"]))
            for c in cols:
                worst = max(worst, abs(float(ra[c]) - float(rb[c])))
        res[mode] = {"max_diff": round(worst, 3), "tolerance": tol, "pass": worst <= tol, "isaac_log": os.path.basename(isaac[-1])}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--motors", default=",".join(ml.list_ids()))
    ap.add_argument("--modes", default="mechanical,electrical")
    ap.add_argument("--out", default=os.path.join(VIZ, "logs", "fleet"))
    a = ap.parse_args()
    motors = [m.strip() for m in a.motors.split(",") if m.strip()]
    modes = [m.strip() for m in a.modes.split(",") if m.strip()]
    t0 = time.time()
    for mid in motors:
        motor = ml.load_motor(mid)
        for mode in modes:
            meta = run_one(motor, mode, os.path.join(a.out, mid, mode))
            print(f"[fleet] {mid} {mode}: {meta['rows']} 행 → {os.path.join(a.out, mid, mode)}")
    if "M5" in motors:
        reg = regression_m5(a.out)
        with open(os.path.join(a.out, "regression_M5.json"), "w", encoding="utf-8") as fh:
            json.dump(reg, fh, ensure_ascii=False, indent=1)
        print("[fleet] M5 회귀 (엔진 ↔ Isaac 로그):", json.dumps(reg, ensure_ascii=False))
    print(f"[fleet] 완료 {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
