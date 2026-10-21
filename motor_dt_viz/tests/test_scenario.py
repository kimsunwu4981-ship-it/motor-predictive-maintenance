# -*- coding: utf-8 -*-
"""결함 주입기·시나리오 플레이어·통합 연동 테스트."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.current_model import CurrentModel  # noqa: E402
from engine.fault_injector import FaultInjector  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402


# ----------------------------------------------------------------- 결함 주입기
def test_결함토글():
    fi = FaultInjector()
    fi.toggle("bearing_de_fault", True)
    assert "bearing_de_fault" in fi.state.thermal_faults
    fi.toggle("bearing_de_fault")          # 반전 → 해제
    assert "bearing_de_fault" not in fi.state.thermal_faults


def test_알수없는_결함은_거부된다():
    fi = FaultInjector()
    with pytest.raises(KeyError):
        fi.toggle("존재하지_않는_결함")
    with pytest.raises(KeyError):
        fi.set_case("없는_케이스")


def test_부하슬라이더는_0에서150퍼센트로_제한된다():
    fi = FaultInjector()
    assert fi.set_load(-1.0) == 0.0
    assert fi.set_load(9.9) == 1.5
    assert fi.set_load(1.2) == pytest.approx(1.2)


def test_ISO20816_판정():
    """기본 모터 M1 = ISO 10816-1 Class I: Watch 1.8 / (Plan = Act) 4.5 mm/s (config/motor.yaml vibration_iso20816_3 키, 값은 M1 규격)"""
    fi = FaultInjector()
    assert fi.iso_zone(1.0) == "Normal"
    assert fi.iso_zone(1.7) == "Normal" and fi.iso_zone(2.0) == "Watch"
    assert fi.iso_zone(3.0) == "Watch"          # 10816-1 에는 '정비 계획' 중간 경계가 없다 (plan = act)
    assert fi.iso_zone(4.8) == "Act"
    fi.toggle("bearing_de_fault", True)
    assert fi.iso_zone() == "Act"          # 베어링 결함 4.8 mm/s → Act


# ------------------------------------------------------------- 시나리오 플레이어
def test_시나리오_총길이가_목표시간과_비슷하다():
    sp = ScenarioPlayer()
    target = float(sp.cfg["playback"]["total_target_s"])
    assert abs(sp.total_duration - target) < 1.0


def test_시나리오_단계가_순서대로_진행된다():
    sp = ScenarioPlayer()
    sp.start()
    ids, t = [], 0.0
    while t < sp.total_duration:
        f = sp.advance(5.0)
        t += 5.0
        if not ids or ids[-1] != f.step_id:
            ids.append(f.step_id)
    assert ids == ["normal", "bearing_fault", "itsc_4turn", "itsc_12turn", "conclusion"]


def test_시나리오는_끝나면_finished():
    sp = ScenarioPlayer()
    sp.start()
    f = sp.advance(sp.total_duration + 10.0)
    assert f.finished and f.total_progress == pytest.approx(1.0)


def test_시나리오_단계가_결함상태를_준다():
    sp = ScenarioPlayer()
    f = sp.frame_at(60.0)                   # 2단계(베어링) 구간
    st = f.to_fault_state()
    assert "bearing_de_fault" in st.thermal_faults


def test_시나리오_전기케이스가_단계별로_바뀐다():
    sp = ScenarioPlayer()
    cases = [sp.frame_at(t).electrical_case for t in (10, 50, 90, 130, 160)]
    assert cases == ["healthy", "healthy", "itsc_4turn", "itsc_12turn", "itsc_12turn"]


# ----------------------------------------------------------------- 통합 연동
def test_ITSC가_권선온도를_올린다():
    """CLAUDE.md §6.3 핵심 스토리: ITSC → 과전류 → 권선 과열."""
    cm = CurrentModel()
    tm_ok, tm_itsc = ThermalModel(), ThermalModel()
    pu_ok = cm.winding_current_pu(cm.evaluate_case("healthy"))
    pu_itsc = cm.winding_current_pu(cm.evaluate_case("itsc_12turn"))
    assert pu_itsc > pu_ok

    for _ in range(600):                    # 10분
        tm_ok.step(1.0, 1.0, [], winding_current_pu=pu_ok, use_duty_cycle=False)
        tm_itsc.step(1.0, 1.0, [], winding_current_pu=pu_itsc, use_duty_cycle=False)
    assert tm_itsc.T[tm_itsc.index["winding"]] > tm_ok.T[tm_ok.index["winding"]] + 20.0


def test_통합시나리오_전구간_실행():
    """자동 재생 전 구간을 돌려 예외 없이 끝나고, 마지막에 경고 이상이 뜨는지 확인."""
    sp, fi, cm, tm = ScenarioPlayer(), FaultInjector(), CurrentModel(), ThermalModel()
    sp.start()
    dt_wall = 1.0 / 15.0                    # HUD 갱신 15 Hz
    last = None
    while not (last and last.finished):
        f = sp.advance(dt_wall)
        cs = cm.evaluate_case(f.electrical_case)
        pu = cm.winding_current_pu(cs)
        tm.step(dt_wall * f.time_scale, f.load, f.thermal_faults, winding_current_pu=pu)
        last = f
    assert tm.T[tm.index["bearing_de"]] > tm.thresholds("bearing_de")["caution"]
    assert tm.T[tm.index["winding"]] > 100.0


# ---------------------------------------------------------------- 모드별 시나리오 분리
def test_mode_scenarios_load_and_match_declared_length():
    """기계/전기 시나리오가 각자 파일에서 로드되고, 총 길이가 선언값과 일치한다."""
    for mode, expect_s in (("mechanical", 180.0), ("electrical", 165.0)):
        p = ScenarioPlayer.for_mode(mode)
        assert p.name == ScenarioPlayer.CONFIG_BY_MODE[mode]
        assert p.total_duration == pytest.approx(expect_s)
        assert p.cfg["playback"]["total_target_s"] == pytest.approx(expect_s)


def test_mechanical_scenario_has_no_electrical_faults():
    """기계 전용 시나리오는 전기 케이스를 healthy 로만 유지한다."""
    p = ScenarioPlayer.for_mode("mechanical")
    for step in p.steps:
        assert step["electrical_case"] == "healthy", step["id"]
        assert step["mode"] == "mechanical", step["id"]


def test_electrical_scenario_has_no_thermal_faults():
    """전기 전용 시나리오는 기계 결함을 주입하지 않는다."""
    p = ScenarioPlayer.for_mode("electrical")
    for step in p.steps:
        assert step["faults"] == [], step["id"]
        assert step["mode"] == "electrical", step["id"]


def test_every_step_declares_a_data_source():
    """정직성 표기: 모든 장면이 데이터 출처를 갖는다 (한글·영문 모두)."""
    for mode in ("mechanical", "electrical"):
        p = ScenarioPlayer.for_mode(mode)
        for step in p.steps:
            f = p.frame_at(0.0) if False else None
            assert step.get("source"), f"{mode}/{step['id']} 에 source 없음"
            assert step.get("source_en"), f"{mode}/{step['id']} 에 source_en 없음"


def test_electrical_sources_do_not_claim_fem():
    """ITSC 를 Maxwell/FEM 해석 결과처럼 표기하지 않는다 (실제로는 해석식 모델)."""
    p = ScenarioPlayer.for_mode("electrical")
    for step in p.steps:
        text = (step["source"] + " " + step["source_en"]).lower()
        assert "maxwell" not in text, step["id"]
        assert "fem" not in text, step["id"]


def test_mechanical_winding_heats_without_current_coupling():
    """기계 전용 모드는 전류 연동 없이도 권선이 정상적으로 가열된다.

    thermal_model.losses 가 winding_current_pu=None 일 때 부하율로 대체하는지 확인한다.
    """
    from engine.thermal_model import ThermalModel
    tm = ThermalModel()
    for _ in range(400):
        st = tm.step(dt_sim_s=30.0, load=1.0, faults=[], winding_current_pu=None,
                     use_duty_cycle=False)
    t = st.temperature_C["winding"]
    assert t > tm.t_amb + 20.0, f"권선이 거의 가열되지 않음: {t:.1f} C"
    assert t < 200.0, f"권선 온도가 비정상적으로 높음: {t:.1f} C"
