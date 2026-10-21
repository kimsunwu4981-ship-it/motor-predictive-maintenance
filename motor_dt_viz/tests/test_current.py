# -*- coding: utf-8 -*-
"""모듈 B(전류 모델) 단위 테스트 — Isaac Sim 없이 실행된다."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.current_model import (  # noqa: E402
    CurrentModel,
    phasors_from_waveform,
    symmetrical_components,
    unbalance_scale_for_ratio,
)

# CLAUDE.md §1.3 에 명시된 기준값
TARGET_I2I1 = {"healthy": 0.006, "itsc_4turn": 0.104, "itsc_12turn": 0.269}
TOLERANCE = 0.10   # ±10 %


@pytest.fixture
def model():
    return CurrentModel()


def test_평형3상은_역상분이_0이다():
    i1, i2, i0 = symmetrical_components(1.0 + 0j, np.exp(-2j * np.pi / 3), np.exp(2j * np.pi / 3))
    assert abs(i1) == pytest.approx(1.0, abs=1e-12)
    assert abs(i2) == pytest.approx(0.0, abs=1e-12)
    assert abs(i0) == pytest.approx(0.0, abs=1e-12)


def test_역산공식_위상0에서_해석해와_일치():
    for r in (0.006, 0.05, 0.104, 0.269, 0.4):
        k_num = unbalance_scale_for_ratio(r, 0.0)
        k_ana = (1 + 2 * r) / (1 - r)
        assert k_num == pytest.approx(k_ana, rel=1e-12)


def test_역산공식이_목표비율을_실제로_만든다():
    """위상 shift 가 있어도 k 역산이 목표 I₂/I₁ 을 정확히 만들어야 한다.

    단, 위상 shift 자체가 역상분을 만들기 때문에 작은 I₂/I₁ 은 큰 위상과 양립하지 않는다.
    (예: φ=10° 에서는 I₂/I₁ 이 아무리 작아도 0.03 이하로 내려갈 수 없다)
    그런 물리적 불가 조합은 ValueError 로 거부되는 것이 옳은 동작이다.
    """
    checked = 0
    for r in (0.006, 0.104, 0.269):
        for phase in (0.0, -6.0, -14.0, 10.0):
            try:
                k = unbalance_scale_for_ratio(r, phase)
            except ValueError:
                continue                      # 해가 없는 조합 — 정상적인 거부
            ia = k * np.exp(1j * math.radians(phase))
            i1, i2, _ = symmetrical_components(ia, np.exp(-2j * np.pi / 3), np.exp(2j * np.pi / 3))
            assert abs(i2) / abs(i1) == pytest.approx(r, rel=1e-9)
            checked += 1
    assert checked >= 6, f"검증된 조합이 {checked}개뿐"


def test_실제_config_케이스는_해가_존재한다():
    """config 의 (target_i2i1, phase_shift) 조합이 모두 물리적으로 성립해야 한다."""
    m = CurrentModel()
    assert set(m.calibration) == {"healthy", "itsc_4turn", "itsc_12turn"}
    for name, c in m.calibration.items():
        assert c["calibrated_scale"] > 1.0, name


def test_페이저_추출_정확도():
    fs, f0 = 60 * 256, 60.0
    t = np.arange(0, 4 / f0, 1 / fs)
    amp, phi = 10.0, math.radians(-30)
    sig = amp * np.sin(2 * np.pi * f0 * t + phi)
    ph = phasors_from_waveform(sig, fs, f0)
    assert abs(ph) == pytest.approx(amp, rel=0.02)


@pytest.mark.parametrize("case", list(TARGET_I2I1))
def test_케이스별_I2I1이_기준값과_일치(model, case):
    """CLAUDE.md §10: 기존 확인값(0.006/0.104/0.269)과 ±10 % 이내."""
    st = model.evaluate_case(case)
    target = TARGET_I2I1[case]
    assert st.i2_over_i1 == pytest.approx(target, rel=TOLERANCE), f"{case}: {st.i2_over_i1:.4f} vs {target}"


def test_정상케이스는_3상모두_정상상태(model):
    st = model.evaluate_case("healthy")
    assert st.status == ("normal", "normal", "normal")


def test_ITSC는_고장상만_과전류(model):
    """A상만 과전류, B·C상은 정상 — 불평형이 화면에 드러나야 한다."""
    for case in ("itsc_4turn", "itsc_12turn"):
        st = model.evaluate_case(case)
        assert st.status[0] in ("over_caution", "over_danger"), case
        assert st.status[1] == "normal" and st.status[2] == "normal", case


def test_ITSC_심각도가_커지면_I2I1도_커진다(model):
    a = model.evaluate_case("itsc_4turn").i2_over_i1
    b = model.evaluate_case("itsc_12turn").i2_over_i1
    assert b > a > model.evaluate_case("healthy").i2_over_i1


def test_과부하는_3상모두_빨강(model):
    st = model.evaluate_case("overload")
    assert all(s == "over_danger" for s in st.status)


def test_무부하는_3상모두_파랑(model):
    st = model.evaluate_case("no_load")
    assert all(s in ("under_caution", "under_danger") for s in st.status)


def test_결상은_해당상만_저전류(model):
    st = model.evaluate_case("single_phasing")
    assert st.status[0] == "under_danger"
    assert st.status[1] != "under_danger" and st.status[2] != "under_danger"


def test_델타결선_기준을_섞지_않는다(model):
    """케이블(선전류)과 권선(상전류)의 정격 기준이 √3 배 차이나야 한다."""
    line = model.motor.rated_current("rated_line_A")
    phase = model.motor.rated_current("rated_phase_A")
    expect = math.sqrt(3) if model.motor.connection == "delta" else 1.0      # Y 결선(M1)은 같다 — 기준 분리는 유지
    assert line / phase == pytest.approx(expect, rel=0.02)


def test_같은파형이라도_기준에따라_판정이_다르다(model):
    """동일한 실제 파형을 선전류/상전류 기준으로 판정하면 결과가 달라야 한다.

    Δ결선에서 기준을 혼용하면 정상 전류가 과전류로 오판된다 — 그 위험을 명시적으로 고정한다.
    """
    fs, f0 = model.f0 * 256, model.f0
    t = np.arange(0, 4 / f0, 1 / fs)
    I = model.waveform(t, "healthy", basis="rated_line_A")   # 케이블에 흐르는 선전류 파형

    st_line = model.analyze(t, I, "healthy", basis="rated_line_A")
    st_phase = model.analyze(t, I, "healthy", basis="rated_phase_A")

    assert st_line.status[1] == "normal"                      # 올바른 기준 → 정상
    if model.motor.connection == "delta":
        assert st_phase.ratio[1] > st_line.ratio[1] * 1.7     # √3 배 부풀려짐
        assert st_phase.status[1] == "over_danger"            # 기준 혼용 시 오판
    else:                                                     # Y(M1): 두 기준이 같아 판정도 같다 (혼용 위험 없음)
        assert st_phase.ratio[1] == pytest.approx(st_line.ratio[1]) and st_phase.status[1] == "normal"


def test_권선전류_pu는_3상_제곱평균(model):
    st = model.evaluate_case("healthy")
    pu = model.winding_current_pu(st)
    expected = math.sqrt(np.mean(np.asarray(st.ratio) ** 2))
    assert pu == pytest.approx(expected, rel=1e-12)


def test_ITSC는_단락루프_파라미터를_제공한다(model):
    assert model.short_loop("healthy") is None
    for case in ("itsc_4turn", "itsc_12turn"):
        loop = model.short_loop(case)
        assert loop and loop["turns"] > 0 and loop["current_pu"] > 1.0


def test_RMS가_이론값과_일치(model):
    """정현파 RMS = 피크/√2."""
    st = model.evaluate_case("healthy")
    i_rated = model.motor.rated_line_A
    assert st.rms_A[1] == pytest.approx(i_rated, rel=0.01)


def test_npz재생_인터페이스(model, tmp_path):
    """기존 Isaac 데이터셋 형식(Ia/Ib/Ic)을 읽을 수 있어야 한다."""
    fs, f0 = 2560.0, 60.0
    t = np.arange(0, 0.5, 1 / fs)
    I = model.waveform(t, "itsc_4turn")
    p = tmp_path / "sample.npz"
    np.savez(p, t=t, Ia=I[0], Ib=I[1], Ic=I[2])
    info = model.load_npz(str(p))
    assert info["fs_Hz"] == pytest.approx(fs, rel=1e-6)
    tw, Iw = model.npz_window(0.1, 0.1)
    st = model.analyze(tw, Iw, "itsc_4turn")
    assert st.i2_over_i1 == pytest.approx(0.104, rel=TOLERANCE)
