# -*- coding: utf-8 -*-
"""모터 라이브러리 테스트 (TASK_다중모터 §4.4) — Isaac Sim 비의존.

  · 5종 YAML 스키마 검증 통과, 파생값(fr, BPFO Hz, 상전류, 슬립)이 수계산과 일치
  · M5 = 기존 motor.yaml / thermal.yaml 과 완전히 동일 (회귀)
  · 5종 정상 운전 수렴 온도가 모터별 '정상' 범위 안
  · 진동 규격이 출력에 따라 바뀐다 (15 kW 미만 10816-1, 이상 20816-3)
"""
import copy
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import MotorSpec, load, val  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.fault_injector import FaultInjector  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

IDS = ["M1", "M2", "M3", "M4", "M5"]


def test_library_has_five_motors_and_validates():
    assert ml.list_ids() == IDS
    for mid in IDS:
        m = ml.load_motor(mid)
        assert m.id == mid and m.source in ("nameplate", "representative")


@pytest.mark.parametrize("mid", IDS)
def test_derived_values_match_hand_calculation(mid):
    m = ml.load_motor(mid)
    assert m.sync_rpm == pytest.approx(120 * m.frequency_hz / m.poles)
    assert m.rotor_freq_hz == pytest.approx(m.rated_rpm / 60)
    assert m.slip == pytest.approx((m.sync_rpm - m.rated_rpm) / m.sync_rpm)
    assert m.rated_phase_current_a == pytest.approx(m.rated_line_current_a / math.sqrt(3), rel=0.03)
    assert m.bpfo_hz() == pytest.approx(m.bpfo_mult * m.rated_rpm / 60)
    assert m.bpfi_hz() == pytest.approx(m.bpfi_mult * m.rated_rpm / 60)
    calc = m.rated_power_kw * 1000 / (math.sqrt(3) * m.voltage_v * m.efficiency * m.power_factor)
    assert m.rated_line_current_a == pytest.approx(calc, rel=0.05)


def test_specific_numbers_m3():
    """M3 (7.5 kW 4극): fr 29.08 Hz, 상전류 9.24 A, BPFO 3.607×fr = 104.9 Hz."""
    m = ml.load_motor("M3")
    assert m.rotor_freq_hz == pytest.approx(1745 / 60, abs=1e-6)
    assert m.rated_line_current_a / math.sqrt(3) == pytest.approx(9.24, abs=0.01)
    assert m.bpfo_hz() == pytest.approx(3.607 * 1745 / 60, abs=0.05)


def test_bearing_multiplier_formula():
    bpfo, bpfi = ml.bearing_multipliers(9, 11.91, 60.0)
    assert bpfo == pytest.approx(3.607, abs=0.002) and bpfi == pytest.approx(5.393, abs=0.002)
    assert bpfo + bpfi == pytest.approx(9.0)


def test_schema_rejects_bad_values():
    d = copy.deepcopy(ml.load_motor("M3").raw)
    d["rated_phase_current_a"] = d["rated_line_current_a"]      # Δ 인데 선전류 = 상전류
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)
    d = copy.deepcopy(ml.load_motor("M1").raw)
    d["vibration"]["standard"] = "ISO 20816-3 Group 2"          # 2.2 kW 에 20816-3 → 규칙 4 위반
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)
    d = copy.deepcopy(ml.load_motor("M1").raw)
    del d["frame"]
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)


# ---------------------------------------------------------------- M5 회귀: 기존 경로와 완전히 같아야 한다
def test_m5_equals_existing_motor_yaml():
    lib = ml.motor_spec(ml.load_motor("M5"))
    old = MotorSpec()
    for attr in ("power_kW", "poles", "voltage_LL", "frequency", "connection", "sync_rpm", "rated_rpm",
                 "efficiency", "power_factor", "rated_line_A", "rated_phase_A", "bpfo_mult", "bpfi_mult", "mass_kg", "rotor_inertia"):
        assert getattr(lib, attr) == pytest.approx(getattr(old, attr)), attr
    assert lib.bearing_name == old.bearing_name
    assert ml.load_motor("M5").vib_thresholds["act_mms"] == val(load("motor")["vibration_iso20816_3"]["act_mms"])


def test_m5_thermal_cfg_identical_and_steady_state_regression():
    cfg = ml.thermal_cfg(ml.load_motor("M5"))
    base = load("thermal")
    for k, n in base["nodes"].items():
        for key in ("mass_kg", "R_amb", "loss_W_rated"):
            assert cfg["nodes"][k][key] == pytest.approx(float(n[key]), rel=1e-9), (k, key)
    assert [[a, b, pytest.approx(float(r))] for a, b, r in base["couplings"]] == [[a, b, r] for a, b, r in cfg["couplings"]]
    assert cfg["faults"]["brake_drag"]["extra_loss_W"] == pytest.approx(float(base["faults"]["brake_drag"]["extra_loss_W"]))
    ss_lib, ss_old = ThermalModel(cfg).steady_state(1.0, ["bearing_de_fault"]), ThermalModel().steady_state(1.0, ["bearing_de_fault"])
    for k in ss_old:
        assert ss_lib[k] == pytest.approx(ss_old[k], abs=1e-9)
    # 180 s 시간 적분도 동일 (시나리오 2 장면 상당)
    a, b = ThermalModel(cfg), ThermalModel()
    for _ in range(90):
        sa, sb = a.step(2.0, 1.0, ["bearing_de_fault"], use_duty_cycle=False), b.step(2.0, 1.0, ["bearing_de_fault"], use_duty_cycle=False)
    for k in sb.temperature_C:
        assert sa.temperature_C[k] == pytest.approx(sb.temperature_C[k], abs=1e-9)


def test_m5_current_model_regression():
    cm_lib = CurrentModel(ml.electrical_cfg(ml.load_motor("M5")), ml.motor_spec(ml.load_motor("M5")))
    cm_old = CurrentModel()
    for case in cm_old.cases:
        a, b = cm_lib.evaluate_case(case), cm_old.evaluate_case(case)
        assert a.rms_A == pytest.approx(b.rms_A, abs=1e-9) and a.i2_over_i1 == pytest.approx(b.i2_over_i1, abs=1e-12)


# ---------------------------------------------------------------- 5종 스케일 결과
@pytest.mark.parametrize("mid", IDS)
def test_steady_state_within_normal_range(mid):
    """정격 100 % 연속 운전(듀티 없음) 수렴 온도: 권선·베어링은 '정상' 상한 아래, 모든 부품은 '경고' 아래 (F종 155 °C 범위 안).
    M5 의 축·코어는 원래 튜닝에서도 연속 운전 시 73~74 °C(주의 띠, 상한 70)라 '정상' 을 강제하지 않는다 (docs/thermal_scaling.md)."""
    m = ml.load_motor(mid)
    tm = ThermalModel(ml.thermal_cfg(m))
    ss = tm.steady_state(1.0, [])
    for key, t in ss.items():
        th = tm.thresholds(key)
        assert tm.t_amb < t < th["caution"], f"{mid} {key} {t:.1f} °C ≥ 경고 {th['caution']}"
        if key in ("winding", "bearing_de", "bearing_nde"):
            assert t < th["normal"], f"{mid} {key} {t:.1f} °C ≥ 정상 상한 {th['normal']}"
        assert t < 155.0


def test_scaling_monotonic_and_rule():
    """작은 모터일수록 손실이 작고 R 이 크며 C 가 작다 (규칙 §4.2)."""
    ref = ml.load_motor("M5")
    for mid in ("M1", "M3"):
        m = ml.load_motor(mid)
        cfg = ml.thermal_cfg(m)
        s = m.geometry_scale
        n5, n = load("thermal")["nodes"]["winding"], cfg["nodes"]["winding"]
        assert n["mass_kg"] == pytest.approx(float(n5["mass_kg"]) * s ** 3, rel=1e-3)
        assert n["R_amb"] == pytest.approx(float(n5["R_amb"]) / s ** 2, rel=1e-3)
        assert n["loss_W_rated"] == pytest.approx(float(n5["loss_W_rated"]) * m.loss_w / ref.loss_w, rel=1e-3)
    ss = {mid: ThermalModel(ml.thermal_cfg(ml.load_motor(mid))).steady_state(1.0, [])["winding"] for mid in IDS}
    assert ss["M1"] < ss["M3"] < ss["M5"]


def test_vibration_standard_by_power():
    assert ml.load_motor("M1").vib_thresholds["watch_mms"] == pytest.approx(1.8)
    assert ml.load_motor("M3").vib_thresholds["standard"].startswith("ISO 10816-1")
    assert ml.load_motor("M4").vib_thresholds["watch_mms"] == pytest.approx(1.4)
    assert ml.load_motor("M5").vib_thresholds["standard"].startswith("ISO 20816-3")
    # FaultInjector 가 모터 규격을 쓴다: 1.6 mm/s 는 M1 에선 정상, M5 에선 Watch
    assert FaultInjector(vib_thresholds=ml.load_motor("M1").vib_thresholds).iso_zone(1.6) == "Normal"
    assert FaultInjector(vib_thresholds=ml.load_motor("M5").vib_thresholds).iso_zone(1.6) == "Watch"
    assert FaultInjector().iso_zone(1.6) == "Watch"      # 기본값(motor.yaml = M5) 유지
