# -*- coding: utf-8 -*-
"""컬러맵 테스트 — USD 비의존이라 Isaac Sim 없이 실행된다.

핵심 회귀 방지: 색은 절대 온도가 아니라 **부품별 임계값 기준**으로 정해져야 한다.
(로터 81 °C 는 정상, 베어링 81 °C 는 주의 — 같은 온도라도 색이 달라야 한다)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.thermal_model import ThermalModel  # noqa: E402
from viz.colormap import ElectricalColormap, ThermalColormap, blend  # noqa: E402


@pytest.fixture
def cmap():
    return ThermalColormap()


@pytest.fixture
def thresholds():
    tm = ThermalModel()
    return {k: tm.thresholds(k) for k in tm.node_keys}


def test_정상온도는_원래재질을_유지한다(cmap, thresholds):
    """정상 구간에서는 blend 0 → 원래 색 그대로, 발광 없음."""
    s = cmap.sample(50.0, part_key="bearing_de", thresholds=thresholds["bearing_de"])
    assert s["pos"] == 0.0
    assert s["blend"] == 0.0
    assert s["intensity"] == 0.0
    assert s["diffuse"] == pytest.approx(cmap.base_color("bearing_de"))


def test_같은온도라도_부품에따라_색이_다르다(cmap, thresholds):
    """로터는 90 °C 까지 정상, 베어링은 70 °C 부터 주의 — 81 °C 에서 갈려야 한다."""
    rotor = cmap.sample(81.0, part_key="rotor", thresholds=thresholds["rotor"])
    bearing = cmap.sample(81.0, part_key="bearing_de", thresholds=thresholds["bearing_de"])
    assert rotor["pos"] == 0.0            # 로터: 아직 정상
    assert bearing["pos"] > 0.2           # 베어링: 이미 주의 구간
    assert bearing["blend"] > rotor["blend"]


def test_온도가_오르면_발광이_세진다(cmap, thresholds):
    th = thresholds["bearing_de"]
    vals = [cmap.sample(t, part_key="bearing_de", thresholds=th)["intensity"]
            for t in (60, 80, 95, 130)]
    assert vals == sorted(vals)
    assert vals[0] == 0.0 and vals[-1] > 5.0


def test_경고온도에서_빨강계열이_된다(cmap, thresholds):
    s = cmap.sample(100.0, part_key="bearing_de", thresholds=thresholds["bearing_de"])
    r, g, b = s["diffuse"]
    assert r > 0.6 and r > g * 2 and r > b * 2


def test_위험단계는_맥동한다(cmap, thresholds):
    """발광 강도가 시간에 따라 변해야 한다 (0.5~1 Hz)."""
    th = thresholds["bearing_de"]
    a = cmap.sample(130.0, part_key="bearing_de", stage="danger", time_s=0.0, thresholds=th)
    b = cmap.sample(130.0, part_key="bearing_de", stage="danger", time_s=0.45, thresholds=th)
    assert a["intensity"] != pytest.approx(b["intensity"])


def test_정상단계는_맥동하지_않는다(cmap, thresholds):
    th = thresholds["bearing_de"]
    a = cmap.sample(60.0, part_key="bearing_de", stage="normal", time_s=0.0, thresholds=th)
    b = cmap.sample(60.0, part_key="bearing_de", stage="normal", time_s=0.45, thresholds=th)
    assert a["intensity"] == b["intensity"] == 0.0


def test_정규화_위치가_단계경계와_일치한다(cmap, thresholds):
    th = thresholds["bearing_de"]
    assert cmap.position(th["normal"], th) == pytest.approx(0.0)
    assert cmap.position(th["caution"], th) == pytest.approx(0.5)
    assert cmap.position(th["warning"], th) == pytest.approx(0.8)
    assert cmap.position(th["warning"] + 100, th) == pytest.approx(1.0)


def test_모든부품에_기본재질이_정의되어있다(cmap):
    """prim_map 의 확인된 부품은 base_materials 에 색이 있어야 회색으로 떨어지지 않는다."""
    from engine.config_loader import load
    parts = load("prim_map")["parts"]
    for key, info in parts.items():
        if info.get("status") != "confirmed":
            continue
        assert key in cmap.base_materials, f"{key} 의 기본 재질 미정의"


def test_전류상태_색상(  ):
    ec = ElectricalColormap()
    over = ec.sample("over_danger")
    normal = ec.sample("normal")
    under = ec.sample("under_danger")
    assert over["diffuse"][0] > 0.8                      # 과전류 = 빨강
    assert normal["diffuse"][1] > 0.8                    # 정상 = 초록
    assert under["diffuse"][2] > 0.8                     # 저전류 = 파랑


def test_단락루프는_맥동한다():
    ec = ElectricalColormap()
    a = ec.sample("short_loop", time_s=0.0)["intensity"]
    b = ec.sample("short_loop", time_s=0.3)["intensity"]
    assert a != pytest.approx(b)


def test_색보간():
    assert blend((0, 0, 0), (1, 1, 1), 0.5) == pytest.approx((0.5, 0.5, 0.5))
    assert blend((0, 0, 0), (1, 1, 1), -1) == pytest.approx((0, 0, 0))    # 범위 클램프
