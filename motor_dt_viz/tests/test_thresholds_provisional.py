# -*- coding: utf-8 -*-
"""P1-3 테스트: 출처·상태·정책 (규칙 worst-of·히스테리시스·지속은 그대로).
① live 정책: provisional 지표가 DANGER 여도 종합 상태는 다른 지표로만 (advisory 로 분리)
② simulation 정책: provisional 지표 포함 + 라벨(provisional_in_status)
③ baseline_multiple 전환: 경계 = baseline × 배수 (yaml 수정만으로)
④ 전압 보정 on/off 차이
⑤ M1 7개 시나리오 판정이 변경 전(0.03)/후(0.05)로 어떻게 달라지는지 표 — 4턴이 WARN 경계 안인지
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.thresholds import Judge  # noqa: E402


def cfg():
    return copy.deepcopy(load("thresholds"))


def test_meta_fields_present():
    c = cfg()
    ns = c["current"]["negative_sequence"]
    assert ns["status"] == "provisional" and ns["mode"] == "absolute" and ns["warn"] == 0.05 and ns["danger"] == 0.10
    assert ns["baseline"] is None, "baseline 은 실측 전까지 null"
    assert c["i2i1"]["safe_below"] == ns["warn"] and c["i2i1"]["danger_from"] == ns["danger"], "호환 블록 i2i1 은 negative_sequence 와 같아야"
    assert c["judgment"]["provisional_policy"] == {"simulation": "include_with_label", "live": "advisory_only"}
    assert c["current"]["rated_ratio"]["status"] == "provisional" and c["temperature"]["status"] == "confirmed"


def test_live_policy_provisional_is_advisory_only():
    j = Judge(cfg(), stream="live")
    v = j.update(0.0, {"temperature": {"winding": 60.0}, "i2i1": 0.30, "current_ratio": {"A": 1.5}})
    assert v.status == "SAFE", v.as_dict()                       # 온도만 판정(confirmed) → SAFE
    kinds = {s.kind for s in v.advisory}
    assert kinds == {"i2i1", "current_ratio"} and all(s.level == "DANGER" for s in v.advisory)
    assert all(s.advisory for s in v.advisory) and v.stream == "live"
    v2 = j.update(1.0, {"temperature": {"winding": 150.0}, "i2i1": 0.30})
    assert v2.status == "DANGER" and v2.cause_signal == "temperature"


def test_simulation_policy_includes_with_label():
    j = Judge(cfg(), stream="simulation")
    for t in (0.0, 1.0, 2.0, 3.5):                                 # 지속 3 s
        v = j.update(t, {"temperature": {"winding": 60.0}, "i2i1": 0.30})
    assert v.status == "DANGER" and v.cause_signal == "i2i1" and v.provisional_in_status is True and not v.advisory
    assert next(s for s in v.signals if s.kind == "i2i1").status == "provisional"


def test_baseline_multiple_switch_by_yaml_only():
    c = cfg(); ns = c["current"]["negative_sequence"]
    ns["mode"] = "baseline_multiple"; ns["baseline"] = {"value": 0.02, "measured_at": "test", "n_windows": 600, "p95": 0.02}
    j = Judge(c)
    lo, hi, mode = j.i2i1_bounds()
    assert mode == "baseline_multiple" and lo == pytest.approx(0.02 * ns["warn_multiple"]) and hi == pytest.approx(0.02 * ns["danger_multiple"])
    assert j.raw("i2i1", 0.03)[0] == "SAFE" and j.raw("i2i1", 0.05)[0] == "WARN" and j.raw("i2i1", 0.081)[0] == "DANGER"
    assert "기준선 배수" in j.raw("i2i1", 0.05)[1]
    # 절대 모드로 되돌리면 0.05/0.10
    ns["mode"] = "absolute"
    assert Judge(c).i2i1_bounds()[:2] == (0.05, 0.10)


def test_voltage_compensation_on_off():
    c = cfg(); ns = c["current"]["negative_sequence"]
    j_off = Judge(c)
    s_off = j_off.judge_signal(0.0, "i2i1", 0.08, v2_v1=0.04)
    assert s_off.compensated is False and s_off.value == pytest.approx(0.08) and s_off.raw_level == "WARN"
    ns["voltage_unbalance_compensation"] = {"enabled": True, "k": 1.0}
    j_on = Judge(c)
    s_on = j_on.judge_signal(0.0, "i2i1", 0.08, v2_v1=0.04)
    assert s_on.compensated is True and s_on.value == pytest.approx(0.04) and s_on.raw_level == "SAFE"
    s_none = j_on.judge_signal(0.0, "i2i1", 0.08)                 # v2_v1 없음 → 보정 안 함
    assert s_none.compensated is False and s_none.value == pytest.approx(0.08)
    v = j_on.update(0.0, {"i2i1": {"value": 0.08, "v2_v1": 0.04}})
    assert next(s for s in v.signals if s.kind == "i2i1").compensated is True


def test_m1_seven_scenarios_before_after_table():
    """변경 전(0.03)/후(0.05) 비교표 — 시뮬레이션 정책(stateless). 4턴(0.0726)은 양쪽 모두 WARN(경계 0.05 바로 위)."""
    m = ml.load_motor("M1")
    cm = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m))
    c_new = cfg(); c_old = cfg(); c_old["current"]["negative_sequence"]["warn"] = 0.03; c_old["i2i1"]["safe_below"] = 0.03
    rows = []
    for case in ("healthy", "itsc_4turn", "itsc_12turn", "overload", "voltage_unbalance", "single_phasing", "no_load"):
        st = cm.evaluate_case(case)
        sig = {"current_ratio": {p: st.rms_A[i] / m.rated_line_current_a for i, p in enumerate("ABC")}, "i2i1": st.i2_over_i1}
        vo, vn = Judge(c_old, motor=m).stateless(sig), Judge(c_new, motor=m).stateless(sig)
        i2o = next(s for s in vo.signals if s.kind == "i2i1").level; i2n = next(s for s in vn.signals if s.kind == "i2i1").level
        rows.append((case, round(st.i2_over_i1, 4), i2o, i2n, vo.status, vn.status))
    print("\n| 케이스 | I₂/I₁ | i2i1 전(0.03) | 후(0.05) | 종합 전 | 후 |")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    d = {r[0]: r for r in rows}
    assert d["healthy"][2] == "SAFE" and d["healthy"][3] == "SAFE"
    assert d["itsc_4turn"][1] > 0.05 and d["itsc_4turn"][2] == "WARN" and d["itsc_4turn"][3] == "WARN"   # 0.0726: 경계 0.05 위 → WARN 유지
    assert d["itsc_12turn"][3] == "DANGER" and d["voltage_unbalance"][3] == "WARN"
    assert d["overload"][5] == "DANGER" and d["single_phasing"][5] == "DANGER"   # 종합(index 5)은 current_ratio 가 끈다
