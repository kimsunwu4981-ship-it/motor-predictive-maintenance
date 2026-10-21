# -*- coding: utf-8 -*-
"""test_m1_model.py — M1 전체 3D 모델 검증 (P4 ③). 실행: py -3.12 -X utf8 -m pytest tests/test_m1_model.py -q

| 검사 | 기준 |
| 내부 체적: 치+요크(Stator_Core), 바 합+엔드링(케이지) vs geometry_check_v2.json | ±2 % |
| 코일 합 vs geometry_check (코일 1개 체적 × 36) | ±2 % — 엔드턴 규칙이 geometry_check 일 때. 시트 l_end 규칙이면 시트 기대값(2·A·(L+l_end)) ±2 % 로 검사하고 geometry_check 대비 편차는 기록 |
| 슬롯 수 36, 바 수 28, 스큐 각 10.0°±0.1°, Coil_01_short 체적비 25 %±1 %p | — |
| 하우징 7개 치수(H·A·B·C·D·E·L) STEP 재판독 vs 카탈로그 | ±0.5 mm |
| 삼각형 수(내부+하우징) | ≤ 300k |
결과 표는 tools/cad/write_model_doc.py 가 docs/assets/M1_model.md 에 쓴다 (이 테스트의 계산 함수를 재사용).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "motors" / "M1"
INP = ASSET / "inputs"


@pytest.fixture(scope="module")
def ctx():
    ds = yaml.safe_load(open(INP / "datasheet_v4.yaml", encoding="utf-8"))
    gc = json.loads((INP / "geometry_check_v2.json").read_text(encoding="utf-8"))["designs"]["M1_3D_full"]
    im = json.loads((ASSET / "internals_parts.json").read_text(encoding="utf-8"))
    hm = json.loads((ASSET / "housing_parts.json").read_text(encoding="utf-8"))
    return {"ds": ds, "gc": gc, "im": im, "hm": hm}


def dsv(ds, sym, sec):
    for k, d in ds["design_sections"].items():
        if k.startswith(sec) and sym in d:
            return d[sym]["value"]
    raise KeyError(sym)


# ----------------------------------------------------------------------------- 체적
def volume_rows(c) -> list[dict]:
    im, gc, ds = c["im"], c["gc"], c["ds"]
    P = im["parts"]; S = im["sums"]
    rows = [{"item": "치+요크 Stator_Core [mm³]", "model": P["Stator_Core"]["volume_mm3"], "ref": gc["teeth_yoke"]["V_core"], "ref_src": "geometry_check teeth_yoke.V_core", "tol": 0.02}]
    cage = S["bars_mm3"] + S["rings_mm3"]
    rows.append({"item": "케이지 (바 28 + 엔드링 2) [mm³]", "model": cage, "ref": gc["cage"]["volume_after"], "ref_src": "geometry_check cage.volume_after", "tol": 0.02})
    L = dsv(ds, "L", "3."); l_end = dsv(ds, "l_end", "6."); A = im["coil_area_mm2"]; n = im["coil_count"]
    coil_sum = S["coils_mm3"]
    rows.append({"item": f"코일 합 (코일 {n}개) vs geometry_check [mm³]", "model": coil_sum, "ref": gc["coil_volume_mm3"] * n, "ref_src": "geometry_check coil_volume_mm3 × 36 (RMxprt 자동 엔드코일)", "tol": 0.02,
                 "gate": im["coil_end_path_rule"].startswith("geometry_check")})
    rows.append({"item": f"코일 합 vs 시트 규칙 2·A·(L+l_end)·{n} [mm³]", "model": coil_sum, "ref": 2 * A * (L + l_end) * n, "ref_src": f"coil area {A} × 2 × (L {L} + l_end {l_end:.2f}) × {n}", "tol": 0.02,
                 "gate": im["coil_end_path_rule"].startswith("시트")})
    for r in rows:
        r["dev_pct"] = (r["model"] / r["ref"] - 1) * 100
        r["pass"] = abs(r["dev_pct"]) <= r["tol"] * 100
    return rows


def test_core_volume(ctx):
    r = volume_rows(ctx)[0]
    assert r["pass"], r


def test_cage_volume(ctx):
    r = volume_rows(ctx)[1]
    assert r["pass"], r


def test_coil_volume_vs_geometry_check(ctx):
    """코일 합 vs Maxwell geometry_check ±2 % — 엔드턴 정본 = geometry_check (2026-10-21 결정). 시트 l_end 행은 참고."""
    r = volume_rows(ctx)[2]
    assert ctx["im"]["coil_end_path_rule"].startswith("geometry_check"), ctx["im"]["coil_end_path_rule"]
    assert r["pass"], r


# ----------------------------------------------------------------------------- 개수·스큐·분할비
def count_rows(c) -> list[dict]:
    im, ds = c["im"], c["ds"]; P = im["parts"]
    Q_s = int(ds["maxwell_model"]["stator"]["Q_s"]); Q_r = int(ds["maxwell_model"]["rotor"]["Q_r"])
    n_coil = sum(1 for k in P if k.startswith("Coil_") and k != "Coil_01_short"); n_bar = sum(1 for k in P if k.startswith("Bar_"))
    skew = skew_angle_from_glb()
    short = P["Coil_01_short"]["volume_mm3"] / im["sums"]["coil01_full_mm3"] * 100
    return [{"item": "슬롯(코일) 수", "model": n_coil, "ref": Q_s, "pass": n_coil == Q_s},
            {"item": "바 수", "model": n_bar, "ref": Q_r, "pass": n_bar == Q_r},
            {"item": "스큐 각 [°] (Bar_01 양 끝단 중심각 차, GLB 재판독)", "model": skew, "ref": dsv(ds, "θ_m", "8."), "pass": abs(skew - dsv(ds, "θ_m", "8.")) <= 0.1},
            {"item": "Coil_01_short 체적비 [%]", "model": short, "ref": 25.0, "pass": abs(short - 25.0) <= 1.0}]


def skew_angle_from_glb() -> float:
    import numpy as np
    import trimesh
    sc = trimesh.load(ASSET / "internals.glb")
    g = sc.geometry["Bar_01"]; v = np.asarray(g.vertices)
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    def ang(sel):
        c = v[sel].mean(axis=0); return math.degrees(math.atan2(c[1], c[2]))
    a0 = ang(np.abs(v[:, 0] - xmin) < 1e-3); a1 = ang(np.abs(v[:, 0] - xmax) < 1e-3)
    return abs((a1 - a0 + 180) % 360 - 180)


def test_counts_skew_split(ctx):
    rows = count_rows(ctx)
    bad = [r for r in rows if not r["pass"]]
    assert not bad, bad


# ----------------------------------------------------------------------------- 하우징 치수 (STEP 재판독)
def housing_rows(c) -> list[dict]:
    import cadquery as cq
    fo = c["ds"]["catalog_frame_100L"]["foot_mount_IM_B3"]
    hs = cq.importers.importStep(str(ASSET / "housing_100L.step"))
    ins = cq.importers.importStep(str(ASSET / "internals.step"))
    solids_h = hs.solids().vals(); solids_i = ins.solids().vals()
    def by_name_like(solids, pred):
        return [s for s in solids if pred(s)]
    # Foot: 얇은 판(두께 < 30) 중 가장 낮은 솔리드 (z_min = 0). (B35 플랜지 P 250 은 축 높이 100 보다 커서 발 바닥 아래 −25 까지 내려온다 → 두께로 거른다)
    foot = min([s for s in solids_h if (s.BoundingBox().zmax - s.BoundingBox().zmin) < 30], key=lambda s: s.BoundingBox().zmin)
    bb_f = foot.BoundingBox()
    # 발 구멍: 반지름 ≈ K/2 원통면 중심
    holes = []
    for f in foot.Faces():
        if f.geomType() == "CYLINDER":
            r = f._geomAdaptor().Cylinder().Radius()
            if abs(r - fo["K"] / 2) < 0.05:
                cen = f.Center(); holes.append((round(cen.x, 2), round(cen.y, 2)))
    xs = sorted({h[0] for h in holes}); ys = sorted({h[1] for h in holes})
    A_m = ys[-1] - ys[0] if len(ys) >= 2 else float("nan"); B_m = xs[-1] - xs[0] if len(xs) >= 2 else float("nan")
    # 축 어깨: B3 엔드쉴드(축 통과 구멍 반지름 D/2+3 원통면을 갖고 플랜지 P/2 원통면이 없는 솔리드)의 +X 바깥 평면
    def has_cyl(s, r):
        return any(f.geomType() == "CYLINDER" and abs(f._geomAdaptor().Cylinder().Radius() - r) < 0.05 for f in s.Faces())
    fl = c["ds"]["catalog_frame_100L"]["flange_FF215"]
    de = next(s for s in solids_h if has_cyl(s, fo["D"] / 2 + 3) and not has_cyl(s, fl["P"] / 2))
    planes_x = sorted({round(f.Center().x, 3) for f in de.Faces() if f.geomType() == "PLANE" and abs(f.normalAt().x) > 0.99}, reverse=True)
    shoulder = planes_x[0]
    C_m = shoulder - xs[-1]
    # 축: 내부 STEP 에서 x_max 가 가장 큰 솔리드, 축단 원통 반지름
    shaft = max(solids_i, key=lambda s: s.BoundingBox().xmax)
    bb_s = shaft.BoundingBox()
    r_end = [f._geomAdaptor().Cylinder().Radius() for f in shaft.Faces() if f.geomType() == "CYLINDER" and f.Center().x > shoulder + 1]
    D_m = 2 * min(r_end) if r_end else float("nan")
    E_m = bb_s.xmax - shoulder
    L_m = bb_s.xmax - min(s.BoundingBox().xmin for s in solids_h)
    # H: 축 중심 높이 = DE 엔드쉴드 축 통과 구멍(반지름 D/2+3) 원통의 축 z − 발 바닥 z
    bores = [f for f in de.Faces() if f.geomType() == "CYLINDER" and abs(f._geomAdaptor().Cylinder().Radius() - (fo["D"] / 2 + 3)) < 0.05]
    z_axis = bores[0]._geomAdaptor().Cylinder().Location().Z() if bores else float("nan")
    H_m = z_axis - bb_f.zmin
    rows = [("H (축 중심 높이)", H_m, fo["H"]), ("A (발 구멍 간격, 폭)", A_m, fo["A"]), ("B (발 구멍 간격, 축방향)", B_m, fo["B1"]), ("C (축 어깨~첫 구멍)", C_m, fo["C"]),
            ("D (축단 지름)", D_m, fo["D"]), ("E (축단 길이)", E_m, fo["E"]), ("L (전장: 축단~팬커버)", L_m, fo["L"])]
    return [{"item": n, "model": m, "ref": float(r), "pass": abs(m - float(r)) <= 0.5} for n, m, r in rows]


def test_housing_dims(ctx):
    rows = housing_rows(ctx)
    bad = [r for r in rows if not r["pass"]]
    assert not bad, bad


# ----------------------------------------------------------------------------- 삼각형
def test_triangle_budget(ctx):
    n = ctx["im"]["triangles_total"] + ctx["hm"]["triangles_total"]
    assert n <= 300_000, n
    assert ctx["im"]["triangles_total"] <= 200_000, ctx["im"]["triangles_total"]
