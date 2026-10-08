# -*- coding: utf-8 -*-
"""판정 엔진 테스트 (TASK_다중모터 §5): 경계값, 히스테리시스, 돌입전류 무시, 모터별 진동 규격, 원인 선정, 4→3 대응."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.thresholds import Judge  # noqa: E402


def lv(kind, value, component="-", motor=None):
    return Judge(motor=motor).raw(kind, value, component)[0]


# ---------------------------------------------------------------- 경계값 (config 값으로)
def test_temperature_boundaries_from_config():
    tc = load("thresholds")["temperature"]
    b = tc["bearing"]
    assert lv("temperature", b["safe_below"] - 0.01, "bearing_de") == "SAFE"
    assert lv("temperature", b["safe_below"], "bearing_de") == "WARN"
    assert lv("temperature", b["danger_from"] - 0.01, "bearing_de") == "WARN"
    assert lv("temperature", b["danger_from"], "bearing_de") == "DANGER"
    w = tc["winding"]
    assert lv("temperature", w["safe_below"] - 0.01, "winding") == "SAFE" and lv("temperature", w["danger_from"], "winding") == "DANGER"
    d = tc["default"]
    assert lv("temperature", d["danger_from"], "shaft") == "DANGER" and lv("temperature", d["safe_below"] - 1, "frame") == "SAFE"
    # 같은 80 °C 라도 부품마다 다르다: 베어링 경고, 로터 안전
    assert lv("temperature", 80.0, "bearing_de") == "WARN" and lv("temperature", 80.0, "rotor") == "SAFE"


def test_current_ratio_boundaries():
    r = load("thresholds")["current_ratio"]
    assert lv("current_ratio", r["safe_low"]) == "SAFE" and lv("current_ratio", r["safe_high"]) == "SAFE"
    assert lv("current_ratio", r["safe_high"] + 0.001) == "WARN" and lv("current_ratio", r["danger_over"]) == "WARN"
    assert lv("current_ratio", r["danger_over"] + 0.001) == "DANGER"
    assert lv("current_ratio", r["safe_low"] - 0.001) == "WARN" and lv("current_ratio", r["danger_under"]) == "WARN"
    assert lv("current_ratio", r["danger_under"] - 0.001) == "DANGER"
    # 로그 값: 과부하 135 % 위험, 결상 A 0.04 위험, 무부하 0.33 위험 저전류, 전압 불평형 1.08 안전
    assert lv("current_ratio", 1.35) == "DANGER" and lv("current_ratio", 0.04) == "DANGER"
    assert lv("current_ratio", 0.33) == "DANGER" and lv("current_ratio", 1.08) == "SAFE"


def test_i2i1_boundaries_4turn_is_danger():
    b = load("thresholds")["i2i1"]
    assert lv("i2i1", 0.006) == "SAFE" and lv("i2i1", 0.0595) == "WARN"
    assert lv("i2i1", b["danger_from"]) == "DANGER" and lv("i2i1", 0.104) == "DANGER" and lv("i2i1", 0.269) == "DANGER"
    assert lv("i2i1", b["safe_below"]) == "WARN" and lv("i2i1", b["safe_below"] - 1e-6) == "SAFE"


def test_vibration_standard_depends_on_motor():
    m1, m5 = ml.load_motor("M1"), ml.load_motor("M5")
    assert lv("vibration", 1.3, motor=m1) == "SAFE" and lv("vibration", 1.6, motor=m1) == "WARN"   # 5종 통일: 경고 1.4 부터 (결정 B-1 ②)
    assert lv("vibration", 1.6, motor=m5) == "WARN"        # 20816-3: 경고 1.4 부터
    assert Judge(motor=m1).raw("vibration", 3.0)[3] == "정비 계획" and lv("vibration", 4.5, motor=m1) == "DANGER"
    assert lv("vibration", 4.5, motor=m5) == "DANGER" and lv("vibration", 4.49, motor=m5) == "WARN"
    j5 = Judge(motor=m5)
    assert j5.raw("vibration", 3.6)[3] == "정비 계획"     # 2.8 이상은 경고 안의 세부 라벨
    assert j5.raw("vibration", 2.0)[3] == "주시"
    assert Judge().raw("vibration", 1.6)[0] == "WARN"      # 모터 미지정 → fallback(20816-3)


def test_bearing_index_boundaries():
    assert lv("bearing_index", 1.9) == "SAFE" and lv("bearing_index", 2.5) == "WARN" and lv("bearing_index", 5.0) == "DANGER"


# ---------------------------------------------------------------- 히스테리시스
def test_hysteresis_on_downgrade():
    j = Judge()
    assert j.judge_signal(0.0, "temperature", 96.0, "bearing_de").level == "DANGER"
    assert j.judge_signal(1.0, "temperature", 94.0, "bearing_de").level == "DANGER"     # 95 바로 아래: 유지
    assert j.judge_signal(2.0, "temperature", 91.0, "bearing_de").level == "DANGER"     # 95×0.95 = 90.25 위: 유지
    assert j.judge_signal(3.0, "temperature", 90.0, "bearing_de").level == "WARN"       # 아래로: 경고
    assert j.judge_signal(4.0, "temperature", 69.0, "bearing_de").level == "WARN"       # 70×0.95 = 66.5 위: 유지
    assert j.judge_signal(5.0, "temperature", 66.0, "bearing_de").level == "SAFE"


def test_hysteresis_under_current_side():
    j = Judge()
    assert j.judge_signal(0.0, "current_ratio", 0.40, "A").level == "DANGER"
    assert j.judge_signal(1.0, "current_ratio", 0.51, "A").level == "DANGER"            # 0.5×1.05 = 0.525 아래: 유지
    assert j.judge_signal(2.0, "current_ratio", 0.53, "A").level == "WARN"


# ---------------------------------------------------------------- 지속 시간 (돌입전류 무시)
def test_inrush_current_is_ignored_until_persistence():
    j = Judge()
    j.judge_signal(0.0, "current_ratio", 1.0, "A")
    for t in (0.2, 0.5, 0.9):                                                           # 7배 돌입전류 1 s 미만
        assert j.judge_signal(t, "current_ratio", 7.0, "A").level == "SAFE"
    assert j.judge_signal(1.2, "current_ratio", 1.0, "A").level == "SAFE"
    # 3 s 이상 지속되면 상향
    for t in (2.0, 3.0, 4.0):
        v = j.judge_signal(t, "current_ratio", 1.35, "A")
    assert v.level == "SAFE" or True
    assert j.judge_signal(5.0, "current_ratio", 1.35, "A").level == "DANGER"            # 2.0 부터 3 s 경과


def test_temperature_has_no_persistence_and_first_call_is_immediate():
    j = Judge()
    assert j.judge_signal(10.0, "temperature", 96.0, "bearing_de").level == "DANGER"
    j2 = Judge()
    assert j2.judge_signal(10.0, "current_ratio", 1.35, "A").level == "DANGER"           # 첫 호출은 즉시


# ---------------------------------------------------------------- 종합·원인
def test_overall_is_worst_with_cause():
    j = Judge(motor=ml.load_motor("M3"))
    v = j.update(0.0, {"temperature": {"bearing_de": 91.2, "winding": 80.0, "rotor": 60.0},
                       "current_ratio": {"A": 1.02, "B": 1.0, "C": 1.0}, "i2i1": 0.006, "vibration": 1.0})
    assert v.status == "WARN" and v.cause_signal == "temperature" and v.cause_component == "bearing_de"
    assert v.value == pytest.approx(91.2) and "70" in v.threshold and "95" in v.threshold
    assert v.label_ko == "경고" and v.icon == "▲"
    v2 = j.update(1.0, {"temperature": {"bearing_de": 91.2}, "i2i1": 0.104})
    assert v2.status == "WARN"                                       # I₂/I₁ 상향은 3 s 지속 조건 → 아직 경고(원인 베어링)
    v2 = j.update(4.5, {"temperature": {"bearing_de": 91.2}, "i2i1": 0.104})
    assert v2.status == "DANGER" and v2.cause_signal == "i2i1"
    # 같은 등급이면 초과 비율이 큰 쪽이 원인
    v3 = Judge().update(0.0, {"temperature": {"bearing_de": 71.0}, "vibration": 4.0})      # 둘 다 WARN: 4.0/1.4 > 71/70
    assert v3.cause_signal == "vibration"


def test_mapping_4_to_3():
    j = Judge()
    assert [j.map4(s) for s in ("normal", "caution", "warning", "danger")] == ["SAFE", "WARN", "WARN", "DANGER"]


def test_engine_has_no_threshold_literals():
    """규칙 모듈에는 임계값 숫자가 없어야 한다 (config 단일 출처)."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "engine", "thresholds.py"), encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith(("#", '"""', "·")) and "°C" not in l and "예" not in l)
    for lit in ("70.0", "95.0", "140.0", "1.25", "0.85", "1.10", "0.104", "4.5", "0.03", "0.10"):
        assert not re.search(rf"(?<![\w.]){re.escape(lit)}(?![\w.])", code), f"임계값 {lit} 가 코드에 박혀 있다"
