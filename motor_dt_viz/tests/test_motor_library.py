# -*- coding: utf-8 -*-
"""모터 라이브러리 테스트 — 단일 모터 M1(현대 HLP-2.2/4) 전환 (파트 C P2′, 2026-10-21). Isaac Sim 비의존.

  · 등록 모터는 M1 하나 (config/motors/*.yaml), _retired/ 는 로더가 읽지 않는다, source: representative 는 불허
  · M1 파생값(fr, BPFO Hz, 상전류=선전류(Y), 슬립)이 수계산과 일치, config/motor.yaml 은 M1 과 같은 값
  · 열회로: thermal.yaml reference 절(옛 M5 22 kW)에서 손실비·geometry_scale 로 스케일, 정상 운전 수렴 온도가 '정상' 범위 안
  · 진동 규격: < 15 kW 는 ISO 10816-1 Class I (1.8/4.5) — 2026-10-21 결정
"""
import copy
import math
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import MotorSpec, load, val  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

IDS = ["M1"]
RETIRED = os.path.join(ml.MOTORS_DIR, ml.RETIRED_DIR)


def test_library_has_single_motor_and_validates():
    assert ml.list_ids() == IDS
    m = ml.load_motor("M1")
    assert m.id == "M1" and m.source in ("nameplate", "catalog") and "HLP-2.2/4" in m.name


def test_retired_dir_is_ignored_but_kept():
    assert os.path.isdir(RETIRED)
    assert {f for f in os.listdir(RETIRED) if f.endswith(".yaml")} >= {"M2.yaml", "M3.yaml", "M4.yaml", "M5.yaml", "motor_M5_reference.yaml"}
    for mid in ("M2", "M3", "M4", "M5"):
        assert mid not in ml.list_ids()
        with pytest.raises(ml.MotorLibraryError):
            ml.load_motor(mid)


def test_representative_grade_rejected():
    d = copy.deepcopy(ml.load_motor("M1").raw)
    d["source"] = "representative"
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)
    retired = yaml.safe_load(open(os.path.join(RETIRED, "M3.yaml"), encoding="utf-8"))
    assert retired["source"] == "representative"
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(retired)


@pytest.mark.parametrize("mid", IDS)
def test_derived_values_match_hand_calculation(mid):
    m = ml.load_motor(mid)
    assert m.sync_rpm == pytest.approx(120 * m.frequency_hz / m.poles)
    assert m.rotor_freq_hz == pytest.approx(m.rated_rpm / 60)
    assert m.slip == pytest.approx((m.sync_rpm - m.rated_rpm) / m.sync_rpm)
    expect_ip = m.rated_line_current_a / math.sqrt(3) if m.connection == "delta" else m.rated_line_current_a   # Y 결선(M1)은 상전류 = 선전류
    assert m.rated_phase_current_a == pytest.approx(expect_ip, rel=0.03)
    assert m.bpfo_hz() == pytest.approx(m.bpfo_mult * m.rated_rpm / 60)
    assert m.bpfi_hz() == pytest.approx(m.bpfi_mult * m.rated_rpm / 60)
    calc = m.rated_power_kw * 1000 / (math.sqrt(3) * m.voltage_v * m.efficiency * m.power_factor)
    assert m.rated_line_current_a == pytest.approx(calc, rel=0.05)


def test_specific_numbers_m1():
    """M1 (현대 HLP-2.2/4, 2.2 kW 4극 1760 rpm): fr 29.33 Hz, 상전류 = 선전류 4.73 A (Y), BPFO 3.568×fr = 104.7 Hz, BPFI 5.432×fr = 159.3 Hz (6206)."""
    m = ml.load_motor("M1")
    assert m.rotor_freq_hz == pytest.approx(1760 / 60, abs=1e-6)
    assert m.rated_line_current_a == pytest.approx(4.73) and m.rated_phase_current_a == pytest.approx(4.73) and m.connection == "star"
    assert m.bpfo_hz() == pytest.approx(104.67, abs=0.1) and m.bpfi_hz() == pytest.approx(159.33, abs=0.1)
    assert m.bearing_de == "6206ZZC3" and m.bearing_nde == "6206ZZC3" and m.rated_rpm == 1760


def test_bearing_multiplier_formula():
    bpfo, bpfi = ml.bearing_multipliers(9, 11.91, 60.0)
    assert bpfo == pytest.approx(3.607, abs=0.002) and bpfi == pytest.approx(5.393, abs=0.002)
    assert bpfo + bpfi == pytest.approx(9.0)


def test_schema_rejects_bad_values():
    d = copy.deepcopy(ml.load_motor("M1").raw)
    d["connection"] = "delta"                                     # Δ 인데 상전류 = 선전류
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)
    d = copy.deepcopy(ml.load_motor("M1").raw)
    d["vibration"]["standard"] = "ISO 20816-3 Group 2"            # < 15 kW 는 ISO 10816-1 이어야 (규칙 4)
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)
    d = copy.deepcopy(ml.load_motor("M1").raw)
    del d["frame"]
    with pytest.raises(ml.MotorLibraryError):
        ml.validate(d)


# ---------------------------------------------------------------- 기본 모터 = M1: config/motor.yaml 과 라이브러리가 같아야 한다
def test_motor_yaml_equals_m1_library():
    lib = ml.motor_spec(ml.load_motor("M1"))
    old = MotorSpec()
    assert load("motor")["library_default"] == "M1"
    for attr in ("power_kW", "poles", "voltage_LL", "frequency", "connection", "sync_rpm", "rated_rpm",
                 "efficiency", "power_factor", "rated_line_A", "rated_phase_A", "bpfo_mult", "bpfi_mult", "mass_kg", "rotor_inertia"):
        assert getattr(lib, attr) == pytest.approx(getattr(old, attr)), attr
    assert lib.bearing_name == old.bearing_name
    assert ml.load_motor("M1").vib_thresholds["act_mms"] == val(load("motor")["vibration_iso20816_3"]["act_mms"])


def test_m1_current_model_default_equals_library():
    """config/motor.yaml 경로(CurrentModel())와 라이브러리 경로는 같은 M1 정격(4.73 A)을 쓴다.
    차이는 방법뿐: 라이브러리 경로는 motor_id=M1 이라 healthy·ITSC 가 LUT(고유 불평형 0.027 포함), 기본 경로는 legacy 해석식.
    legacy 전용 케이스(single_phasing)는 두 경로가 정확히 같고, LUT 케이스도 3상 평균은 1 % 안이다."""
    m = ml.load_motor("M1")
    cm_lib = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m))
    cm_old = CurrentModel()
    assert cm_lib.motor.rated_line_A == cm_old.motor.rated_line_A == pytest.approx(4.73)
    a, b = cm_lib.evaluate_case("single_phasing"), cm_old.evaluate_case("single_phasing")
    assert a.rms_A == pytest.approx(b.rms_A, abs=1e-9)
    for case in ("healthy", "overload"):
        a, b = cm_lib.evaluate_case(case), cm_old.evaluate_case(case)
        assert sum(a.rms_A) / 3 == pytest.approx(sum(b.rms_A) / 3, rel=0.02), case   # D3(2026-10-21): LUT 경로 I₁ = LUT 정상분 RMS(정상 4.695 A, MCCM 정합값) vs legacy 정격 4.73 A → 약 1.4 %
    assert cm_lib.evaluate_case("healthy").i1_A == pytest.approx(4.6946, abs=0.002)   # D3: 정상 I₁ = LUT 격자 I1_A (MCCM 물리 보정 전류), 정격 4.73 A 가 아니다
    assert cm_lib.evaluate_case("itsc_12turn").i1_A > 5.5                              # D3: 결함 시 I₁ 상승 (LUT 5.92 A)
    assert cm_lib.evaluate_case("healthy").source["method"] == "lut" and cm_old.evaluate_case("healthy").source["method"] == "legacy"


# ---------------------------------------------------------------- 열회로: thermal.yaml reference 절(옛 M5)에서 스케일
def test_thermal_reference_block_matches_retired_m5():
    ref = load("thermal")["reference"]
    old = yaml.safe_load(open(os.path.join(RETIRED, "motor_M5_reference.yaml"), encoding="utf-8"))
    assert float(ref["power_kW"]) == float(old["rating"]["power_kW"]["value"])
    assert float(ref["efficiency"]) == float(old["current"]["efficiency"]["value"])
    assert float(ref["loss_W"]) == pytest.approx(float(ref["power_kW"]) * 1000 * (1 - float(ref["efficiency"])) / float(ref["efficiency"]), rel=1e-3)
    assert "M5" not in ml.list_ids()


def test_m1_thermal_cfg_scaled_from_reference():
    m = ml.load_motor("M1"); cfg = ml.thermal_cfg(m); ref = load("thermal")["reference"]
    ref_loss = float(ref["power_kW"]) * 1000 * (1 - float(ref["efficiency"])) / float(ref["efficiency"])
    s = m.geometry_scale / float(ref["geometry_scale"])
    base = load("thermal")["nodes"]["winding"]; n = cfg["nodes"]["winding"]
    assert cfg["scaled_from"]["loss_ratio"] == pytest.approx(m.loss_w / ref_loss, rel=1e-3)
    assert n["mass_kg"] == pytest.approx(float(base["mass_kg"]) * s ** 3, rel=1e-3)
    assert n["R_amb"] == pytest.approx(float(base["R_amb"]) / s ** 2, rel=1e-3)
    assert n["loss_W_rated"] == pytest.approx(float(base["loss_W_rated"]) * m.loss_w / ref_loss, rel=1e-3)
    # 작은 모터가 더 차갑다: M1 스케일 vs 기준(thermal.yaml 원본 = 22 kW)
    ss1 = ThermalModel(cfg).steady_state(1.0, [])["winding"]; ss_ref = ThermalModel().steady_state(1.0, [])["winding"]
    assert ss1 < ss_ref


@pytest.mark.parametrize("mid", IDS)
def test_steady_state_within_normal_range(mid):
    """정격 100 % 연속 운전(듀티 없음) 수렴 온도: 권선·베어링은 '정상' 상한 아래, 모든 부품은 '경고' 아래 (F종 155 °C 범위 안)."""
    m = ml.load_motor(mid)
    tm = ThermalModel(ml.thermal_cfg(m))
    ss = tm.steady_state(1.0, [])
    for key, t in ss.items():
        th = tm.thresholds(key)
        assert tm.t_amb < t < th["caution"], f"{mid} {key} {t:.1f} °C ≥ 경고 {th['caution']}"
        if key in ("winding", "bearing_de", "bearing_nde"):
            assert t < th["normal"], f"{mid} {key} {t:.1f} °C ≥ 정상 상한 {th['normal']}"
        assert t < 155.0


def test_vibration_standard_by_power():
    """< 15 kW 는 ISO 10816-1 Class I (경고 1.8 / 위험 4.5 mm/s) — 2026-10-21 파트 C 결정 (2026-10-08 5종 통일 20816-3 은 라이브러리 퇴역과 함께 해제)."""
    assert ml.VIB_STANDARD_SPLIT_KW == pytest.approx(15.0)
    v = ml.load_motor("M1").vib_thresholds
    assert v["standard"].startswith("ISO 10816-1")
    assert v["watch_mms"] == pytest.approx(1.8) and v["act_mms"] == pytest.approx(4.5) and v["plan_mms"] <= v["act_mms"]
