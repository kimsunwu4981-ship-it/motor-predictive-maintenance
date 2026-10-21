# -*- coding: utf-8 -*-
"""build_internals_M1.py — M1(현대 HLP-2.2/4) 내부 모델: 고정자 코어·코일 36(+Coil_01_short)·로터 코어·바 28(스큐)·엔드링·축 (CadQuery).

입력: assets/motors/M1/inputs/datasheet_v4.yaml 만 (키 이름으로 읽음, 숫자 수기 입력 없음).
  - 코어 외경/내경/적층·공극·축경·슬롯 수·스큐 각·엔드링·엔드권선 길이: 설계값 §3·§4·§6·§7·§8
  - 슬롯 프로파일·코일당 턴수: `maxwell_model`(RMxprt v2 오버라이드 = Maxwell 3D 가 실제 쓴 치수) — geometry_check_v2.json 체적과의 동일성 기준
  - 코일 단면: geometry_check_v2.json 'coil solid section (CoilTerm area)' 측정값(= Maxwell 코일 단면)
좌표: 축 +X, 적층 중심 원점, mm. 객체 이름은 Maxwell 과 동일(Stator_Core, Coil_01…36, Coil_01_short, Rotor_Core, Bar_01…28, EndRing_DE/NDE, Shaft).
출력: assets/motors/M1/internals.step, internals.obj(그룹=부품), internals.glb, internals_cutaway.{obj,glb}, internals_parts.json(재질·체적·삼각형).

  py -3.12 -X utf8 tools/cad/build_internals_M1.py [--end-path sheet|geometry_check] [--end-segments N] [--quick]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m1_common import ASSET, HALF_SPLITS, INP, PartSet, load_ds, dsv, pol, rot_x, quarter_cutter, save_json, solid_volume, split_parts  # noqa: E402

# 시각 추정(visual_estimate) 배치 상수 — 카탈로그·시트에 없는 값. 어떤 체적·치수 검증에도 쓰지 않는다. 하우징 스크립트가 housing_params.yaml 에 같은 값을 기록한다.
LAYOUT = {
    "shoulder_x_mm": 125.0,        # DE 엔드쉴드 바깥면(축 어깨) 위치. 프레임+엔드쉴드 = ±125 → 팬커버 60 → 전장 L 370 = E 60 + 310 (카탈로그 L·E 와 정합)
    "bearing_x_mm": 108.0,         # 베어링 중심 ±108 (엔드쉴드 안쪽)
    "bearing_6206": {"id": 30.0, "od": 62.0, "w": 16.0},   # 6206 규격(표준)
    "shaft_nde_end_x_mm": -150.0,  # NDE 축 끝(팬 허브 자리)
    "shaft_nde_d_mm": 25.0,        # NDE 축경(팬 쪽, 추정)
    "coil_clearance_mm": 0.3,      # 슬롯 라이너 두께(코일 폭 = 슬롯 폭 − 2c)
    "end_exit_mm": 3.0,            # 코일이 적층 끝에서 축방향으로 곧게 나가는 길이
    "end_bulge_mm": 3.0,           # 엔드턴 반경 방향 바깥 부풀림
}


# ----------------------------------------------------------------------------- 프로파일
def stator_slot_wire(r_si, Hs0, Hs1, Hs2, Bs0, Bs1, Bs2, tab=0.5):
    """RMxprt 고정자 Slot Type 2: 개구(Bs0×Hs0) → 쐐기(Bs0→Bs1, Hs1) → 몸통(Bs1→Bs2, Hs2) → 반원 바닥(Bs2/2). +Z 방향, YZ 평면."""
    r1 = r_si + Hs0 + Hs1; r2 = r1 + Hs2
    return (cq.Workplane("YZ").polyline([(-Bs0 / 2, r_si - tab), (-Bs0 / 2, r_si + Hs0), (-Bs1 / 2, r1), (-Bs2 / 2, r2)])
            .threePointArc((0, r2 + Bs2 / 2), (Bs2 / 2, r2)).lineTo(Bs1 / 2, r1).lineTo(Bs0 / 2, r_si + Hs0).lineTo(Bs0 / 2, r_si - tab).close())


def rotor_slot_wire(r_ro, Hs0, Bs1, Bs2, Hs2):
    """RMxprt 로터 Slot Type 1 (닫힌 배형): 브리지 Hs0 아래 상부 원(Bs1) → 직선 테이퍼(Hs2) → 하부 원(Bs2). +Z 방향."""
    rc1 = r_ro - Hs0 - Bs1 / 2; rc2 = rc1 - Hs2
    return (cq.Workplane("YZ").moveTo(-Bs1 / 2, rc1).threePointArc((0, rc1 + Bs1 / 2), (Bs1 / 2, rc1))
            .lineTo(Bs2 / 2, rc2).threePointArc((0, rc2 - Bs2 / 2), (-Bs2 / 2, rc2)).close())


def slot_width(r, r1, r2, Bs1, Bs2):
    return Bs1 + (Bs2 - Bs1) * (r - r1) / (r2 - r1)


def coil_trapezoid(r_lo, area, r1, r2, Bs1, Bs2, c):
    """슬롯 테이퍼를 따르는 사다리꼴 코일 단면: 아래 반경 r_lo 에서 위로 높이 h (면적 = area 가 되게 이분법). 반환 (점 목록 (y,z), h, 중심 r)."""
    def area_of(h):
        w0 = slot_width(r_lo, r1, r2, Bs1, Bs2) - 2 * c; w1 = slot_width(r_lo + h, r1, r2, Bs1, Bs2) - 2 * c
        return (w0 + w1) / 2 * h
    lo, hi = 0.1, 30.0
    for _ in range(60):
        h = (lo + hi) / 2
        if area_of(h) < area:
            lo = h
        else:
            hi = h
    h = (lo + hi) / 2
    w0 = slot_width(r_lo, r1, r2, Bs1, Bs2) - 2 * c; w1 = slot_width(r_lo + h, r1, r2, Bs1, Bs2) - 2 * c
    pts = [(-w0 / 2, r_lo), (-w1 / 2, r_lo + h), (w1 / 2, r_lo + h), (w0 / 2, r_lo)]
    rc = r_lo + h * (w0 + 2 * w1) / (3 * (w0 + w1))
    return pts, h, rc


def offset_polygon(pts, t):
    """2D 다각형 안쪽 균일 오프셋(t>0 안쪽). 반환 새 점 목록 (CadQuery offset2D)."""
    w = cq.Workplane("YZ").polyline(pts).close().offset2D(-t, "intersection")
    verts = w.val().Vertices()
    return [(v.Y, v.Z) for v in verts]


def polygon_area(pts):
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2


def inner_offset_for_ratio(pts, ratio):
    """면적비 ratio(=0.75) 가 되는 안쪽 오프셋 t 를 이분법으로 찾는다 (Maxwell '전체 면 균일 오프셋' 과 같은 규칙)."""
    A0 = polygon_area(pts)
    lo, hi = 0.0, 3.0
    for _ in range(50):
        t = (lo + hi) / 2
        if polygon_area(offset_polygon(pts, t)) / A0 > ratio:
            lo = t
        else:
            hi = t
    return (lo + hi) / 2


# ----------------------------------------------------------------------------- 코일
def end_path_points(x_end, rA, thA, rB, thB, overhang, exit_mm, bulge, n):
    """적층 끝 x_end 에서 slot A(rA,thA) → 엔드턴 → slot B(rB,thB) 로 가는 3D 점 (스플라인용). 축방향 최대 돌출 = overhang."""
    P = [(x_end,) + pol(rA, thA), (x_end + exit_mm,) + pol(rA, thA)]
    for i in range(1, n):
        u = i / n
        th = thA + u * (thB - thA); r = rA + u * (rB - rA) + bulge * math.sin(math.pi * u)
        x = x_end + exit_mm + (overhang - exit_mm) * math.sin(math.pi * u)
        P.append((x,) + pol(r, th))
    P += [(x_end + exit_mm,) + pol(rB, thB), (x_end,) + pol(rB, thB)]
    return P


def path_length(P):
    return sum(math.dist(P[i], P[i + 1]) for i in range(len(P) - 1))


def solve_overhang(target_len, x_end, rA, thA, rB, thB, exit_mm, bulge, n):
    lo, hi = exit_mm + 1.0, 150.0
    for _ in range(60):
        m = (lo + hi) / 2
        if path_length(end_path_points(x_end, rA, thA, rB, thB, m, exit_mm, bulge, n)) < target_len:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def coil_solids(pts_top, pts_bot, th_pitch_deg, Lh, overhang, exit_mm, bulge, n_seg, scale_inner=None):
    """슬롯 θ=0(상층) ↔ θ=pitch(하층) 코일: 직선부 2 + 엔드턴 2 (각각 솔리드). 반환 솔리드 목록."""
    def prism(pts, th):
        s = cq.Workplane("YZ").polyline(pts).close().extrude(Lh, both=True)
        return rot_x(s, th)
    def centroid_r(pts):
        return sum(p[1] for p in pts) / len(pts)
    rA, rB = centroid_r(pts_top), centroid_r(pts_bot)
    solids = [prism(pts_top, 0.0).val(), prism(pts_bot, th_pitch_deg).val()]
    for sign in (+1, -1):
        P = end_path_points(Lh, rA, 0.0, rB, th_pitch_deg, overhang, exit_mm, bulge, n_seg)
        if sign < 0:
            P = [(-x, y, z) for x, y, z in P]
        path = cq.Workplane("XY").spline(P)
        prof = cq.Workplane("YZ", origin=(sign * Lh, 0, 0)).polyline(pts_top).close()
        sw = prof.sweep(path, isFrenet=True, transition="round")
        solids.append(sw.val())
    return solids


# ----------------------------------------------------------------------------- 본체
def build(end_path: str, n_seg: int, quick: bool, half_splits=tuple(HALF_SPLITS)) -> dict:
    ds = load_ds(); mx = ds["maxwell_model"]; st, ro = mx["stator"], mx["rotor"]
    gc = json.loads((INP / "geometry_check_v2.json").read_text(encoding="utf-8"))
    full = gc["designs"]["M1_3D_full"]
    coil_area = next(r[2] for r in full["dimension_table"] if r[0].startswith("coil solid section (CoilTerm area)"))   # Maxwell 코일 단면 (측정)
    D_so, D_si, L = dsv(ds, "D_so", "3."), dsv(ds, "D_si", "3."), dsv(ds, "L", "3.")
    D_ro, D_sh = dsv(ds, "D_ro", "3."), dsv(ds, "D_shaft", "3.")
    Q_s, Q_r = int(st["Q_s"]), int(ro["Q_r"])
    theta_skew = dsv(ds, "θ_m", "8.")                     # 10° 기계각 = 1 고정자 슬롯피치
    h_er, w_er, D_er = dsv(ds, "h_er", "7."), dsv(ds, "w_er", "7."), dsv(ds, "D_er", "7.")
    l_end = dsv(ds, "l_end", "6.")                         # 엔드권선 도체 길이 (편측)
    pitch = int(st["coil_pitch"]); N_c = int(st["N_c"])
    cat = ds["catalog_frame_100L"]["foot_mount_IM_B3"]
    D_ext, E_ext = cat["D"], cat["E"]; key_b, key_h, key_l = (float(x) for x in str(cat["key"]).lower().split("x"))
    r_si, r_so, r_ro, r_ri = D_si / 2, D_so / 2, D_ro / 2, D_sh / 2
    Lh = L / 2
    ps = PartSet("M1_internals")
    log = lambda *a: print("[internals]", *a, flush=True)  # noqa: E731

    # ---- 고정자 코어 (치+요크 단일 솔리드, 슬롯 36 컷)
    t = time.time()
    ann = cq.Workplane("YZ").circle(r_so).circle(r_si).extrude(Lh, both=True)
    slot = stator_slot_wire(r_si, st["Hs0"], st["Hs1"], st["Hs2"], st["Bs0"], st["Bs1"], st["Bs2"]).extrude(Lh + 1, both=True)
    slots = [rot_x(slot, 360.0 / Q_s * k).val() for k in range(Q_s)]
    core = ann.cut(cq.Compound.makeCompound(slots))
    ps.add("Stator_Core", core, "silicon_steel", "Stator", f"D_so {D_so}/D_si {D_si}/L {L}, 슬롯 {Q_s} (RMxprt type {st['slot_type']}: Hs0 {st['Hs0']} Hs1 {st['Hs1']} Hs2 {st['Hs2']} Bs0 {st['Bs0']} Bs1 {st['Bs1']} Bs2 {st['Bs2']})", tol=0.10, ang=0.30)
    log(f"Stator_Core {solid_volume(core):.0f} mm³ ({time.time() - t:.1f} s)")

    # ---- 코일 단면: 슬롯 몸통(r1~r2)을 상·하 두 층으로, 각 층 안에 면적 coil_area 사다리꼴
    r1 = r_si + st["Hs0"] + st["Hs1"]; r2 = r1 + st["Hs2"]; c = LAYOUT["coil_clearance_mm"]
    h_layer = (r2 + st["Bs2"] / 2 - r1) / 2
    pts_top, h_t, rc_t = coil_trapezoid(r1 + c, coil_area, r1, r2, st["Bs1"], st["Bs2"], c)
    pts_bot, h_b, rc_b = coil_trapezoid(r1 + h_layer + c, coil_area, r1, r2, st["Bs1"], st["Bs2"], c)
    # 상층 코일을 층 가운데로 (층 높이 − 코일 높이)/2 만큼 올림
    def shift(pts, d):
        return [(y, z + d) for y, z in pts]
    pts_top = shift(pts_top, (h_layer - h_t) / 2 - c); pts_bot = shift(pts_bot, (h_layer - h_b) / 2 - c)
    rc_t += (h_layer - h_t) / 2 - c; rc_b += (h_layer - h_b) / 2 - c
    th_pitch = 360.0 / Q_s * pitch
    # 엔드턴 경로 길이 규칙
    if end_path == "sheet":
        target = l_end; rule = f"시트 l_end {l_end:.2f} mm (설계값 §6 엔드권선 도체 길이, 편측)"
    else:
        target = full["coil_volume_mm3"] / coil_area / 2 - L; rule = f"geometry_check 코일 체적 {full['coil_volume_mm3']} / 단면 {coil_area} / 2 − L = {target:.2f} mm (정본, 2026-10-21 결정; 시트 l_end {l_end:.2f} mm 는 참고)"
    overhang = solve_overhang(target, Lh, rc_t, 0.0, rc_b, th_pitch, LAYOUT["end_exit_mm"], LAYOUT["end_bulge_mm"], n_seg)
    P_chk = end_path_points(Lh, rc_t, 0.0, rc_b, th_pitch, overhang, LAYOUT["end_exit_mm"], LAYOUT["end_bulge_mm"], n_seg)
    log(f"코일 단면 {coil_area} mm² · 상층 중심 r {rc_t:.2f} / 하층 r {rc_b:.2f} · 엔드턴 경로 {path_length(P_chk):.2f} mm (목표 {target:.2f}, 축 돌출 {overhang:.2f} mm, 규칙: {rule})")
    t_in = inner_offset_for_ratio(pts_top, 0.75)
    pts_top_in = offset_polygon(pts_top, t_in); pts_bot_in = offset_polygon(pts_bot, inner_offset_for_ratio(pts_bot, 0.75))
    log(f"Coil_01 분할 오프셋 t {t_in:.3f} mm → 안쪽 면적비 {polygon_area(pts_top_in) / polygon_area(pts_top):.4f}")

    winding = {w["coil"]: w for w in ds["winding_table"]}
    coils = range(1, 3) if quick else range(1, Q_s + 1)
    t = time.time()
    for k in coils:
        th = 360.0 / Q_s * (k - 1)
        sol = coil_solids(pts_top, pts_bot, th_pitch, Lh, overhang, LAYOUT["end_exit_mm"], LAYOUT["end_bulge_mm"], n_seg)
        comp = cq.Workplane("XY").add([rot_x(cq.Workplane("XY").add(s), th).val() for s in sol])
        phase = winding.get(k, {}).get("phase", "?")
        if k == 1:
            inner = coil_solids(pts_top_in, pts_bot_in, th_pitch, Lh, overhang, LAYOUT["end_exit_mm"], LAYOUT["end_bulge_mm"], n_seg)
            inner_c = cq.Workplane("XY").add([rot_x(cq.Workplane("XY").add(s), th).val() for s in inner])
            shell = [a.cut(b) for a, b in zip(comp.vals(), inner_c.vals())]
            ps.add("Coil_01", inner_c, "copper", "Stator", f"슬롯 {k} 상층 ↔ {k + pitch} 하층, 상 {phase}, 안쪽 75 % (healthy)", tol=0.3, ang=0.6)
            ps.add("Coil_01_short", cq.Workplane("XY").add(shell), "copper", "Stator", "Coil_01 바깥 균일 오프셋 셸 25 % (ITSC 단락 턴 표시용)", tol=0.3, ang=0.6)
        else:
            ps.add(f"Coil_{k:02d}", comp, "copper", "Stator", f"슬롯 {k} 상층 ↔ {(k - 1 + pitch) % Q_s + 1} 하층, 상 {phase}, 엔드턴 visual_estimate", tol=0.3, ang=0.6)
    log(f"코일 {len(coils)}개 ({time.time() - t:.1f} s), Coil_01 {solid_volume(ps.parts['Coil_01']['shape']):.0f} + short {solid_volume(ps.parts['Coil_01_short']['shape']):.0f} mm³")

    # ---- 로터: 바(스큐 트위스트) → 코어에서 빼기
    t = time.time()
    bar_w = rotor_slot_wire(r_ro, ro["Hs0"], ro["Bs1"], ro["Bs2"], ro["Hs2"])
    bar0 = bar_w.twistExtrude(L, theta_skew).translate((-Lh, 0, 0))
    bars = [rot_x(bar0, 360.0 / Q_r * k) for k in range(Q_r)]
    rot_ann = cq.Workplane("YZ").circle(r_ro).circle(r_ri).extrude(Lh, both=True)
    rotor = rot_ann.cut(cq.Compound.makeCompound([b.val() for b in bars]))
    ps.add("Rotor_Core", rotor, "silicon_steel", "Rotor", f"D_ro {D_ro}/D_shaft {D_sh}/L {L}, 닫힌 슬롯 {Q_r} (브리지 Hs0 {ro['Hs0']}), 스큐 {theta_skew}° (1 고정자 슬롯피치)", tol=0.2, ang=0.5)
    for k, b in enumerate(bars, 1):
        ps.add(f"Bar_{k:02d}", b, "aluminum", "Rotor", f"RMxprt type {ro['slot_type']} Bs1 {ro['Bs1']} Bs2 {ro['Bs2']} Hs2 {ro['Hs2']}, 트위스트 {theta_skew}°", tol=0.2, ang=0.6)
    log(f"Rotor_Core {solid_volume(rotor):.0f} mm³, 바 {Q_r}×{solid_volume(bar0):.2f} ({time.time() - t:.1f} s)")

    # ---- 엔드링: 평균 직경 D_er, 반경 높이 h_er, 축방향 폭 w_er, 적층 끝 바깥
    for name, x0 in (("EndRing_DE", Lh), ("EndRing_NDE", -Lh - w_er)):
        ring = cq.Workplane("YZ", origin=(x0, 0, 0)).circle(D_er / 2 + h_er / 2).circle(D_er / 2 - h_er / 2).extrude(w_er)
        ps.add(name, ring, "aluminum", "Rotor", f"D_er {D_er} h_er {h_er} w_er {w_er}", tol=0.05, ang=0.2)

    # ---- 축: 로터부 D_shaft → 베어링 자리(6206 내경) → DE 축단 D×E (카탈로그) + 키홈 8×7×45, NDE 짧은 축
    bx, bw, bid = LAYOUT["bearing_x_mm"], LAYOUT["bearing_6206"]["w"], LAYOUT["bearing_6206"]["id"]
    sh_x = LAYOUT["shoulder_x_mm"]
    x_rot_end = Lh + w_er + 2.0
    seg = [(-x_rot_end, x_rot_end, r_ri), (x_rot_end, sh_x, bid / 2), (sh_x, sh_x + E_ext, D_ext / 2), (LAYOUT["shaft_nde_end_x_mm"], -x_rot_end, LAYOUT["shaft_nde_d_mm"] / 2)]
    shaft = None
    for x0, x1, r in seg:
        s = cq.Workplane("YZ", origin=(x0, 0, 0)).circle(r).extrude(x1 - x0)
        shaft = s if shaft is None else shaft.union(s)
    keyway = cq.Workplane("XY").box(key_l, key_b, key_h * 2).translate((sh_x + E_ext - key_l / 2 - 3.0, 0, D_ext / 2))
    shaft = shaft.cut(keyway)
    ps.add("Shaft", shaft, "steel", "Rotor", f"로터부 Ø{D_sh}(시트), 베어링부 Ø{bid}(6206 내경, 표준), DE 축단 Ø{D_ext}×{E_ext} 키 {cat['key']}(카탈로그), NDE Ø{LAYOUT['shaft_nde_d_mm']} visual_estimate", tol=0.05, ang=0.2)

    # ---- 베어링 6206 (시각: 내경·외경·폭 표준값, 위치 LAYOUT) — USD /M1/Bearings
    for name, xc in (("Bearing_DE", bx), ("Bearing_NDE", -bx)):
        b = cq.Workplane("YZ", origin=(xc - bw / 2, 0, 0)).circle(LAYOUT["bearing_6206"]["od"] / 2).circle(bid / 2).extrude(bw)
        ps.add(name, b, "steel", "Bearings", f"6206 내경 {bid} 외경 {LAYOUT['bearing_6206']['od']} 폭 {bw} (규격), 위치 x {xc} visual_estimate", tol=0.1, ang=0.3)

    # ---- 내보내기
    out = ASSET
    ps.export_step(out / "internals.step"); ps.export_obj(out / "internals.obj"); ps.export_glb(out / "internals.glb")
    man = ps.manifest({"coil_area_mm2": coil_area, "coil_end_path_rule": rule, "coil_end_path_mm": path_length(P_chk), "coil_end_overhang_mm": overhang,
                       "coil_layer_center_r_mm": {"top": rc_t, "bottom": rc_b}, "coil01_short_offset_mm": t_in, "skew_deg": theta_skew, "layout_visual_estimate": LAYOUT,
                       "coil_count": len(coils), "quick": quick,
                       "sums": {"coils_mm3": sum(p["volume_mm3"] for n, p in ps.parts.items() if n.startswith("Coil_") and n != "Coil_01_short") + ps.parts["Coil_01_short"]["volume_mm3"],
                                "bars_mm3": sum(p["volume_mm3"] for n, p in ps.parts.items() if n.startswith("Bar_")),
                                "rings_mm3": sum(p["volume_mm3"] for n, p in ps.parts.items() if n.startswith("EndRing")),
                                "coil01_full_mm3": ps.parts["Coil_01"]["volume_mm3"] + ps.parts["Coil_01_short"]["volume_mm3"]}})
    save_json(out / "internals_parts.json", man)
    # ---- cutaway: 하우징·고정자(코어·코일) 1/4 절단, 로터는 그대로
    cutter = quarter_cutter()
    pc = PartSet("M1_internals_cutaway")
    for n, p in ps.parts.items():
        if p["group"] == "Stator":
            cut = p["shape"].cut(cutter)
            pc.add(n, cut, p["material"], p["group"], p["note"], tol=0.3 if n.startswith("Coil") else 0.10, ang=0.6 if n.startswith("Coil") else 0.30)
        else:
            pc.parts[n] = p
    pc.export_obj(out / "internals_cutaway.obj"); pc.export_glb(out / "internals_cutaway.glb")
    man["cutaway_triangles"] = pc.triangles()
    save_json(out / "internals_parts.json", man)
    # ---- 반 분할 (H1): 고정자 코어만 (권선·로터·축·베어링·엔드링은 나누지 않는다). 평면은 축(원점)을 지난다
    man["half_split"] = {}
    for split in half_splits:
        ph, tab = split_parts(ps, ["Stator_Core"], split, f"M1_internals_half_{split}", z_axis=0.0, tol=0.10, ang=0.30)
        ph.export_obj(out / f"internals_half_{split}.obj"); ph.export_glb(out / f"internals_half_{split}.glb")
        man["half_split"][split] = tab
        log(f"half {split}: Stator_Core 조각 {len(ph.parts)} · 삼각형 {tab['triangles']:,} · 체적 합 편차 {tab['parts']['Stator_Core']['dev_pct']:.4f} %")
    save_json(out / "internals_parts.json", man)
    log(f"삼각형 {ps.triangles():,} (cutaway {pc.triangles():,}) · 코일 합 {man['sums']['coils_mm3']:.0f} · 바 합 {man['sums']['bars_mm3']:.0f} · 링 {man['sums']['rings_mm3']:.0f} mm³ · {man['generated_s']} s")
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end-path", choices=["sheet", "geometry_check"], default="geometry_check",
                    help="엔드턴 경로 길이 규칙 (기본 geometry_check = Maxwell RMxprt 자동 엔드코일 체적에서 역산 106.9 mm — 2026-10-21 결정; sheet = 시트 l_end 121.5 mm 참고)")
    ap.add_argument("--end-segments", type=int, default=10, help="엔드턴 스플라인 분할 수")
    ap.add_argument("--quick", action="store_true", help="코일 2개만 (개발용)")
    ap.add_argument("--half-split", nargs="*", choices=list(HALF_SPLITS), default=list(HALF_SPLITS), help="고정자 코어 반 분할 평면 (기본: top front 둘 다)")
    a = ap.parse_args()
    build(a.end_path, a.end_segments, a.quick, tuple(a.half_split))


if __name__ == "__main__":
    main()
