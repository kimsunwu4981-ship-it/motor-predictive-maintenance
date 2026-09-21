# -*- coding: utf-8 -*-
"""모듈 A(열 모델) 단위 테스트 — Isaac Sim 없이 실행된다."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.thermal_model import ThermalModel  # noqa: E402


@pytest.fixture
def model():
    return ThermalModel()


def _run(model, minutes, load=1.0, faults=None, dt=1.0):
    """시뮬레이션 시간 minutes 분 동안 적분 (듀티 사이클 비활성 = 연속 부하)."""
    steps = int(minutes * 60 / dt)
    st = None
    for _ in range(steps):
        st = model.step(dt_sim_s=dt, load=load, faults=faults or [], use_duty_cycle=False)
    return st


def test_초기온도는_주위온도(model):
    assert all(abs(v - model.t_amb) < 1e-9 for v in model.T)


def test_정격부하에서_온도가_정상상태로_수렴한다(model):
    """장시간 적분 결과가 해석적 정상상태 해와 일치해야 한다 (적분기 검증).

    프레임 열용량이 커서(36 kJ/K) 계 전체 시간상수가 약 20~30분이다.
    4시간이면 시간상수의 8배 이상이라 충분히 수렴한다.
    """
    st = _run(model, minutes=240, load=1.0, dt=2.0)
    ss = model.steady_state(load=1.0)
    for key, t_ss in ss.items():
        assert abs(st.temperature_C[key] - t_ss) < 1.5, f"{key}: 적분 {st.temperature_C[key]:.1f} vs 해석 {t_ss:.1f}"


def test_정격_정상운전은_모든부품이_정상또는주의(model):
    """CLAUDE.md §5.3 완료 기준: 정상 운전 시 정상~주의 범위에서 안정."""
    st = _run(model, minutes=60, load=1.0)
    for key, stage in st.stage.items():
        assert stage in ("normal", "caution"), f"{key} 가 {stage} ({st.temperature_C[key]:.1f}°C)"


def test_무부하는_정격보다_모든부품이_낮다(model):
    hot = model.steady_state(load=1.0)
    model.reset()
    cold = model.steady_state(load=0.0)
    for key in hot:
        assert cold[key] < hot[key], key


def test_DE베어링결함시_경고온도_초과(model):
    """결함 주입 시 베어링이 경고(danger) 단계에 도달해야 빨강 발광이 나온다."""
    st = _run(model, minutes=20, load=1.0, faults=["bearing_de_fault"])
    th = model.thresholds("bearing_de")
    assert st.temperature_C["bearing_de"] > th["warning"], f"{st.temperature_C['bearing_de']:.1f}°C"
    assert st.stage["bearing_de"] == "danger"


def test_DE베어링결함시_인접_엔드실드도_상승(model):
    """인접 하우징이 뒤따라 달아오르는 전도 경로가 동작해야 한다."""
    base = model.steady_state(load=1.0)
    faulty = model.steady_state(load=1.0, faults=["bearing_de_fault"])
    assert faulty["endshield_de"] > base["endshield_de"] + 5.0
    # DE 쪽이 NDE 쪽보다 더 많이 오른다 (국부성 확인)
    d_de = faulty["endshield_de"] - base["endshield_de"]
    d_nde = faulty["endshield_nde"] - base["endshield_nde"]
    assert d_de > d_nde


def test_결함해제시_온도가_하강한다(model):
    """CLAUDE.md §5.3: 결함 해제 시 식어서 복귀."""
    _run(model, minutes=30, load=1.0, faults=["bearing_de_fault"])
    hot = model.temperature("bearing_de") if hasattr(model, "temperature") else model.T[model.index["bearing_de"]]
    st = _run(model, minutes=30, load=1.0, faults=[])
    assert st.temperature_C["bearing_de"] < hot - 10.0


def test_결함은_수분내에_경고를_돌파한다(model):
    """'수 분(시뮬레이션 시간) 내 경고 온도 초과' 튜닝 목표 확인."""
    th = model.thresholds("bearing_de")
    crossed_min = None
    for minute in range(1, 31):
        _run(model, minutes=1, load=1.0, faults=["bearing_de_fault"])
        if model.T[model.index["bearing_de"]] > th["caution"]:
            crossed_min = minute
            break
    assert crossed_min is not None, "30분 내 주의 온도 미돌파"
    assert crossed_min <= 10, f"주의 돌파까지 {crossed_min}분 (목표 10분 이내)"


def test_냉각팬고장은_방열저하로_전체온도상승(model):
    base = model.steady_state(load=1.0)
    fan = model.steady_state(load=1.0, faults=["fan_failure"])
    assert fan["frame"] > base["frame"] + 15.0
    assert fan["winding"] > base["winding"] + 10.0


def test_과부하는_권선온도를_크게_올린다(model):
    base = model.steady_state(load=1.0)
    over = model.steady_state(load=1.0, faults=["overload"])
    assert over["winding"] > base["winding"] + 20.0


def test_전류연동시_권선손실이_전류제곱에_비례(model):
    """통합 모드: 모듈 B 전류비가 권선 동손을 지배한다."""
    p1 = model.losses(load=1.0, faults=[], winding_current_pu=1.0)[model.index["winding"]]
    p2 = model.losses(load=1.0, faults=[], winding_current_pu=2.0)[model.index["winding"]]
    assert abs(p2 / p1 - 4.0) < 1e-6


def test_듀티사이클은_평균부하를_낮춘다(model):
    """크레인 권상 듀티(lift/hold/lower/idle)는 연속 정격보다 온도가 낮아야 한다."""
    m2 = ThermalModel()
    cont = _run(model, minutes=45, load=1.0)
    st = None
    for _ in range(45 * 60):
        st = m2.step(dt_sim_s=1.0, load=1.0, faults=[], use_duty_cycle=True)
    assert st.temperature_C["winding"] < cont.temperature_C["winding"]


def test_rk4와_euler가_유사한_결과(model):
    """적분기 선택이 결과를 크게 바꾸지 않아야 한다 (스텝 크기 적정성)."""
    rk = _run(model, minutes=20, load=1.0)
    m2 = ThermalModel()
    m2.method = "euler"
    eu = _run(m2, minutes=20, load=1.0)
    for key in rk.temperature_C:
        assert abs(rk.temperature_C[key] - eu.temperature_C[key]) < 1.0, key


def test_표시온도는_EMA로_평활된다(model):
    """색 급변 방지: 표시 온도가 실제 온도를 지연 추종한다."""
    model.reset()
    st = model.step(dt_sim_s=5.0, load=1.0, faults=["brake_drag"], use_duty_cycle=False)
    assert st.display_C["shaft"] < st.temperature_C["shaft"]


def test_step_with_zero_dt_reports_state():
    """전기 전용 모드는 dt=0 으로 열을 멈춘다 — 그래도 상태를 반환해야 한다.

    과거에는 적분 루프를 돌지 않아 손실 배열이 None 으로 남아 TypeError 가 났다.
    """
    model = ThermalModel()
    before = model.step(dt_sim_s=60.0, load=1.0, faults=[], use_duty_cycle=False)
    st = model.step(dt_sim_s=0.0, load=1.0, faults=[], use_duty_cycle=False)
    assert st.loss_W["winding"] > 0.0
    # 온도가 그대로 멈춰 있어야 한다
    assert st.temperature_C["winding"] == pytest.approx(before.temperature_C["winding"], abs=1e-6)
