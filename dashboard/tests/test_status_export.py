# -*- coding: utf-8 -*-
"""상태 보드 데이터 검증 (TASK_다중모터 §7.3): export JSON 수치 = config·로그, 판정 결과 = engine/thresholds.py 결과,
데모 위치의 기대 상태, 정직성 라벨 네 줄, cause_chain 치환 변수."""
from __future__ import annotations

import csv
import json
import os
import re
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)
sys.path.insert(0, os.path.join(VIZ, "tools"))

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.thresholds import Judge  # noqa: E402
from run_fleet import bearing_index  # noqa: E402

FLEET_DATA = os.path.join(DASH, "public", "data", "fleet")
FLEET_LOGS = os.path.join(VIZ, "logs", "fleet")
MODES = ("mechanical", "electrical")


def _index():
    p = os.path.join(FLEET_DATA, "index.json")
    if not os.path.exists(p):
        pytest.skip("public/data/fleet/index.json 없음 — export_status_data.py 먼저")
    return json.load(open(p, encoding="utf-8"))


def _series(mid, mode):
    return json.load(open(os.path.join(FLEET_DATA, f"{mid}_{mode}.json"), encoding="utf-8"))


def _idx(t_list, t):
    i = 0
    for k, x in enumerate(t_list):
        if x <= t + 1e-9:
            i = k
    return i


# ---------------------------------------------------------------- 사양·임계값 = config
def test_motors_match_library_yaml():
    idx = _index()
    assert [m["id"] for m in idx["motors"]] == ml.list_ids()
    for m in idx["motors"]:
        y = yaml.safe_load(open(os.path.join(VIZ, "config", "motors", f"{m['id']}.yaml"), encoding="utf-8"))
        for k in ("rated_power_kw", "poles", "sync_rpm", "rated_rpm", "rated_line_current_a", "rated_phase_current_a", "frame", "connection"):
            assert m["spec"][k] == y[k], (m["id"], k)
        mo = ml.load_motor(m["id"])
        assert m["vibration"]["watch_mms"] == mo.vib_thresholds["watch_mms"] and m["vibration"]["act_mms"] == mo.vib_thresholds["act_mms"]
        assert m["derived"]["bpfo_hz"] == pytest.approx(mo.bpfo_hz(), abs=0.05)
    # 진동 규격은 출력 15 kW 를 경계로 갈린다 (M1~M3 1.8, M4·M5 1.4)
    w = {m["id"]: m["vibration"]["watch_mms"] for m in idx["motors"]}
    assert w["M1"] == w["M2"] == w["M3"] == 1.8 and w["M4"] == w["M5"] == 1.4


def test_thresholds_match_config():
    idx = _index(); cfg = load("thresholds")
    t = idx["thresholds"]
    for cls in ("bearing", "winding", "rotor", "default"):
        assert t["temperature"][cls]["safe_below"] == cfg["temperature"][cls]["safe_below"]
        assert t["temperature"][cls]["danger_from"] == cfg["temperature"][cls]["danger_from"]
    assert t["current_ratio"] == cfg["current_ratio"] and t["i2i1"] == cfg["i2i1"] and t["bearing_index"] == cfg["bearing_index"]
    assert t["hysteresis_fraction"] == cfg["hysteresis"]["fraction"] and t["persistence_s"] == cfg["persistence_s"]
    assert idx["labels_ko"] == cfg["labels_ko"] and idx["colors"] == cfg["colors"] and idx["icons"] == cfg["icons"]


def test_honesty_four_lines_and_phase_labels():
    idx = _index()
    lines = idx["honesty"]["lines"]
    assert len(lines) == 4
    for key in ("명판 아님", "프레임 비례", "M5 기준", "해석식 등가"):
        assert any(key in l for l in lines), key
    el = load("electrical")
    assert idx["phase_labels"] == el["phase_labels"]


# ---------------------------------------------------------------- 시계열 = 로그
@pytest.mark.parametrize("mid,mode", [("M1", "mechanical"), ("M3", "electrical"), ("M5", "mechanical")])
def test_series_equals_fleet_log(mid, mode):
    s = _series(mid, mode)
    rows = list(csv.DictReader(open(os.path.join(FLEET_LOGS, mid, mode, "demo_fleet.csv"), encoding="utf-8", newline="")))
    st = list(csv.DictReader(open(os.path.join(FLEET_LOGS, mid, mode, "status_fleet.csv"), encoding="utf-8", newline="")))
    assert s["n"] == len(rows) == len(s["t"]) == len(s["status"])
    i_line = ml.load_motor(mid).rated_line_current_a
    for k in range(0, len(rows), 37):
        r = rows[k]
        assert s["t"][k] == pytest.approx(float(r["t_real_s"]), abs=1e-3)
        assert s["temperature_C"]["bearing_de"][k] == float(r["T_bearing_de"]) and s["temperature_C"]["winding"][k] == float(r["T_winding"])
        assert s["current_rms_A"]["A"][k] == float(r["Ia_rms"])
        assert s["current_ratio"]["A"][k] == pytest.approx(float(r["Ia_rms"]) / i_line, abs=1e-4)
        assert s["i2i1"][k] == float(r["i2_over_i1"]) and s["vibration_mms"][k] == float(r["vibration_mms"])
        assert s["status"][k] == st[k]["status"] and s["cause_signal"][k] == st[k]["cause_signal"] and s["cause_component"][k] == st[k]["cause_component"]
        assert s["cause_value"][k] == float(st[k]["value"])


# ---------------------------------------------------------------- 판정 = thresholds.py 재실행
@pytest.mark.parametrize("mid,mode", [("M1", "mechanical"), ("M3", "mechanical"), ("M2", "electrical"), ("M5", "electrical")])
def test_status_equals_judge_recompute(mid, mode):
    s = _series(mid, mode)
    motor = ml.load_motor(mid)
    th_cfg = ml.thermal_cfg(motor)
    rows = list(csv.DictReader(open(os.path.join(FLEET_LOGS, mid, mode, "demo_fleet.csv"), encoding="utf-8", newline="")))
    judge = Judge(motor=motor)
    nodes = ("winding", "stator_core", "rotor", "shaft", "bearing_de", "bearing_nde", "endshield_de", "endshield_nde", "frame")
    mism = 0
    for k, r in enumerate(rows):
        v = judge.update(float(r["t_real_s"]), {
            "temperature": {n: float(r["T_" + n]) for n in nodes},
            "current_ratio": {p: float(r[f"I{p.lower()}_rms"]) / motor.rated_line_current_a for p in "ABC"},
            "i2i1": float(r["i2_over_i1"]), "vibration": float(r["vibration_mms"]),
            "bearing_index": bearing_index(th_cfg, [x for x in r["faults"].split(";") if x]),
        })
        if v.status != s["status"][k] or v.cause_signal != s["cause_signal"][k]:
            mism += 1
        assert s["bearing_index"][k] == bearing_index(th_cfg, [x for x in r["faults"].split(";") if x])
    assert mism == 0, f"{mid} {mode}: 판정 불일치 {mism} 행"


# ---------------------------------------------------------------- 데모 위치
def test_demo_positions_give_expected_mix():
    idx = _index()
    cfg = yaml.safe_load(open(os.path.join(VIZ, "config", "status_demo.yaml"), encoding="utf-8"))["positions"]
    seen = set()
    for m in idx["motors"]:
        d = m["demo"]
        assert d["mode"] == cfg[m["id"]]["mode"] and d["t_s"] == float(cfg[m["id"]]["t_s"])
        s = _series(m["id"], d["mode"])
        st = s["status"][_idx(s["t"], d["t_s"])]
        assert st == cfg[m["id"]]["expect"], (m["id"], st)
        seen.add(st)
    assert seen == {"SAFE", "WARN", "DANGER"}          # 첫 화면에 세 상태가 섞여 보인다


# ---------------------------------------------------------------- cause_chain 변수
@pytest.mark.parametrize("mode", MODES)
def test_cause_chain_variables_resolve_for_every_motor(mode):
    idx = _index()
    nar = yaml.safe_load(open(os.path.join(DASH, "public", "content", mode, "narration.yaml"), encoding="utf-8"))["scenes"]
    for m in idx["motors"]:
        s = _series(m["id"], mode)
        for step in idx["scenarios"][mode]["steps"]:
            cc = nar.get(step["id"], {}).get("cause_chain")
            if not cc:
                continue
            v = s["scene_values"][step["id"]]
            for text in cc.values():
                for var in re.findall(r"\{([a-zA-Z0-9_]+)\}", text):
                    assert var in v and v[var] is not None, (m["id"], mode, step["id"], var)
        # 모터별로 달라지는 값: 전기 a_rms_end 는 그 모터의 정격에 비례
        if mode == "electrical":
            ratio = s["scene_values"]["itsc_4turn"]["a_rms_end"] / m["spec"]["rated_line_current_a"]
            assert ratio == pytest.approx(1.32, abs=0.02)


def test_offline_build_has_no_external_urls():
    dist = os.path.join(DASH, "dist", "assets")
    if not os.path.isdir(dist):
        pytest.skip("dist 없음 — npm run build 먼저")
    for name in os.listdir(dist):
        if name.endswith((".js", ".css")):
            src = open(os.path.join(dist, name), encoding="utf-8", errors="ignore").read()
            for m in re.finditer(r"https?://[a-zA-Z0-9.\-]+", src):
                host = m.group(0)
                assert not any(h in host for h in ("fonts.googleapis", "cdn.", "unpkg", "jsdelivr", "cdnjs")), host
