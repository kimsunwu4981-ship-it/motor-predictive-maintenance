# -*- coding: utf-8 -*-
"""build_housing_100L.py — IEC 100L 프레임 하우징(현대 SSEN HLP-2.2/4, IM B3 + FF215 플랜지 옵션) 시각 모델 (CadQuery).

구속 치수(카탈로그, datasheet_v4.yaml `catalog_frame_100L` — 숫자 수기 입력 없음): H A AA AB HA B(B1) BB C K HC HD L, 축단 D E F GE·키, 플랜지 M N P n S LA T, 단자함 O PF.
카탈로그에 없는 값(프레임 외경 AC, 핀, 엔드쉴드 두께, 팬 커버, 단자함 크기·위치, 아이볼트)은 visual_estimate — 어떤 계산에도 쓰지 않는다.
AD: 카탈로그 발 장착 표 328 / 플랜지 표 175 (정의가 다름) → verify. 단자함은 HD(상면 높이)만 맞춘다.
좌표: 축 +X, 발 바닥 Z 0, 축 중심 Z H(=100), 적층 중심 X 0 (내부 모델과 같은 X). 단위 mm.
출력: assets/motors/M1/housing_100L.step, housing.obj/.glb, housing_cutaway.obj/.glb, housing_parts.json, housing_params.yaml

  py -3.12 -X utf8 tools/cad/build_housing_100L.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import cadquery as cq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m1_common import ASSET, PartSet, load_ds, quarter_cutter, save_json  # noqa: E402
from build_internals_M1 import LAYOUT  # noqa: E402

VIS = {   # visual_estimate — 카탈로그·시트에 없음
    "AC_frame_od_mm": 196.0,          # 핀 끝 외경(≈ AB). 100L 주철 프레임 통상값
    "frame_body_od_mm": 172.0,        # 핀 뿌리 원통 외경
    "frame_len_mm": 200.0,            # 프레임 원통 길이 (±100), 엔드쉴드 25 씩 → ±125 = 축 어깨
    "fin_count": 28, "fin_h_mm": 12.0, "fin_t_mm": 3.0, "fin_len_mm": 180.0,
    "endshield_t_mm": 25.0, "endshield_od_mm": 180.0, "bearing_boss_od_mm": 85.0, "bearing_boss_len_mm": 30.0,
    "fancover_od_mm": 190.0, "fancover_t_mm": 1.5, "fancover_len_mm": 60.0, "fancover_slots": 24,
    "tbox_w_mm": 96.0, "tbox_l_mm": 96.0, "tbox_center_x_mm": -25.0, "tbox_base_h_mm": 14.0,
    "eyebolt_ring_od_mm": 40.0, "eyebolt_ring_d_mm": 8.0, "eyebolt_x_mm": 55.0,
    "foot_pad_len_mm": 150.0,
}


def build():
    ds = load_ds(); cat = ds["catalog_frame_100L"]; fo = cat["foot_mount_IM_B3"]; fl = cat["flange_FF215"]
    H, A, AA, AB, HA, B, BB, C, K = (float(fo[k]) for k in ("H", "A", "AA", "AB", "HA", "B1", "BB", "C", "K"))
    HC, HD, L_total, D, E, F, GE = (float(fo[k]) for k in ("HC", "HD", "L", "D", "E", "F", "GE"))
    O_tbox, PF = float(fo["O"]), fo["PF"]
    M, N, P, n_fl, S, LA, T = (float(fl[k]) for k in ("M", "N", "P", "n", "S", "LA", "T"))
    key = str(fo["key"])
    sh_x = LAYOUT["shoulder_x_mm"]; bx = LAYOUT["bearing_x_mm"]; brg = LAYOUT["bearing_6206"]
    Z = H                                              # 축 중심 높이
    ps = PartSet("M1_housing_100L")
    log = lambda *a: print("[housing]", *a, flush=True)  # noqa: E731
    yz = lambda x0: cq.Workplane("YZ", origin=(x0, 0, Z))  # noqa: E731

    # ---- Frame: 원통 + 핀 + 발 받침 패드
    fl_len = VIS["frame_len_mm"]
    D_so = float(ds["design"]["D_so"]["value"])
    frame = yz(-fl_len / 2).circle(VIS["frame_body_od_mm"] / 2).circle(D_so / 2 + 0.5).extrude(fl_len)   # 보어 = 고정자 외경 D_so(시트) + 0.5 — 코어가 프레임 안에 묻히지 않게
    fins = None
    for i in range(VIS["fin_count"]):
        ang = 360.0 / VIS["fin_count"] * i
        if 150 < ang < 210:                                 # 바닥(발 자리)엔 핀 없음
            continue
        fin = (cq.Workplane("XY").box(VIS["fin_len_mm"], VIS["fin_t_mm"], VIS["fin_h_mm"] + 2)
               .translate((0, 0, VIS["frame_body_od_mm"] / 2 + VIS["fin_h_mm"] / 2 - 1)).rotate((0, 0, 0), (1, 0, 0), ang).translate((0, 0, Z)))
        fins = fin if fins is None else fins.union(fin)
    pad = cq.Workplane("XY").box(VIS["foot_pad_len_mm"], A + 20, 40).translate((C_x := sh_x - C - B / 2, 0, HA + 20 - 2))   # 발 위~프레임 바닥
    frame = frame.union(fins).union(pad)
    ps.add("Frame", frame, "cast_iron", "Housing", f"원통 Ø{VIS['frame_body_od_mm']}+핀 {VIS['fin_count']}개(끝 Ø{VIS['AC_frame_od_mm']}) visual_estimate", tol=0.2, ang=0.5)

    # ---- Foot: 판 BB×AB×HA, 구멍 ØK ×4 (A 간격, B 간격), 첫 구멍은 축 어깨에서 C
    foot = cq.Workplane("XY").box(BB, AB, HA, centered=(True, True, False)).translate((C_x, 0, 0))
    x_holes = [sh_x - C, sh_x - C - B]
    for xh in x_holes:
        for yh in (-A / 2, A / 2):
            foot = foot.cut(cq.Workplane("XY").circle(K / 2).extrude(HA + 2).translate((xh, yh, -1)))
    ps.add("Foot", foot, "cast_iron", "Housing", f"BB {BB}×AB {AB}×HA {HA}, 구멍 ØK {K} @A {A}/B {B}, C {C} (카탈로그)", tol=0.2, ang=0.5)

    # ---- EndShield_DE: 베어링 보스 + FF215 플랜지 (B35 옵션 치수: P/N/M/n/S/LA/T) — 어깨면 x = sh_x
    es_t = VIS["endshield_t_mm"]
    de = yz(fl_len / 2).circle(VIS["endshield_od_mm"] / 2).extrude(sh_x - fl_len / 2 - LA)        # 몸통
    flange = yz(sh_x - LA).circle(P / 2).extrude(LA)                                                # 플랜지 판 두께 LA, 바깥면 = 어깨
    spigot = yz(sh_x).circle(N / 2).extrude(T)                                                      # 스피곳 N × T
    for i in range(int(n_fl)):
        a = math.radians(45 + 360 / n_fl * i)
        flange = flange.cut(yz(sh_x - LA - 1).center(M / 2 * math.sin(a), M / 2 * math.cos(a)).circle(S / 2).extrude(LA + 2))
    boss = yz(fl_len / 2 - 5).circle(VIS["bearing_boss_od_mm"] / 2).extrude(VIS["bearing_boss_len_mm"])
    de = de.union(flange).union(spigot).union(boss).cut(yz(fl_len / 2 - 10).circle(D / 2 + 3).extrude(60))   # 축 통과 구멍
    ps.add("EndShield_DE", de, "cast_iron", "Housing", f"FF215 플랜지 P {P}/N {N}/M {M}/n {int(n_fl)}×ØS {S}/LA {LA}/T {T} (카탈로그 B35 옵션), 두께·보스 visual_estimate", tol=0.2, ang=0.5)

    # ---- EndShield_NDE
    nde = yz(-sh_x).circle(VIS["endshield_od_mm"] / 2).extrude(es_t).union(yz(-fl_len / 2 - VIS["bearing_boss_len_mm"] + 5).circle(VIS["bearing_boss_od_mm"] / 2).extrude(VIS["bearing_boss_len_mm"]))
    nde = nde.cut(yz(-sh_x - 1).circle(LAYOUT["shaft_nde_d_mm"] / 2 + 2).extrude(60))
    ps.add("EndShield_NDE", nde, "cast_iron", "Housing", "visual_estimate", tol=0.2, ang=0.5)

    # ---- FanCover: 얇은 원통 + 뒷판(슬롯 그릴), 끝면 x = sh_x − L_total + E  (전장 L 카탈로그)
    x_back = sh_x + E - L_total
    fc_len = -sh_x - x_back
    cover = yz(x_back).circle(VIS["fancover_od_mm"] / 2).extrude(fc_len).cut(yz(x_back + VIS["fancover_t_mm"]).circle(VIS["fancover_od_mm"] / 2 - VIS["fancover_t_mm"]).extrude(fc_len))
    for i in range(VIS["fancover_slots"]):
        a = 360.0 / VIS["fancover_slots"] * i
        slot = cq.Workplane("XY").box(VIS["fancover_t_mm"] + 2, 4, 40).translate((x_back + VIS["fancover_t_mm"] / 2, 0, 55)).rotate((0, 0, 0), (1, 0, 0), a).translate((0, 0, Z))
        cover = cover.cut(slot)
    ps.add("FanCover", cover, "steel", "Housing", f"Ø{VIS['fancover_od_mm']}×{fc_len:.0f} visual_estimate, 뒷면 x {x_back:.0f} (L {L_total} = E {E} + 어깨~뒷면)", tol=0.25, ang=0.5)

    # ---- TerminalBox: 상면 z = HD (카탈로그), 크기·위치 visual_estimate, PF 커넥터 구멍 ØO
    z_top = HD; z_base = Z + VIS["frame_body_od_mm"] / 2 - 4
    tb = cq.Workplane("XY").box(VIS["tbox_l_mm"], VIS["tbox_w_mm"], z_top - z_base, centered=(True, True, False)).translate((VIS["tbox_center_x_mm"], 0, z_base))
    hole = cq.Workplane("XZ", origin=(VIS["tbox_center_x_mm"], 0, (z_top + z_base) / 2)).circle(O_tbox / 2).extrude(VIS["tbox_w_mm"], both=True)   # 커넥터 구멍(양측 관통, 시각)
    tb = tb.cut(hole)
    ps.add("TerminalBox", tb, "cast_iron", "Housing", f"상면 HD {HD}(카탈로그), 크기 {VIS['tbox_l_mm']}×{VIS['tbox_w_mm']} 위치 x {VIS['tbox_center_x_mm']} visual_estimate, 커넥터 ØO {O_tbox} PF {PF}, AD verify", tol=0.2, ang=0.5)

    # ---- Eyebolt: 상단 z = HC (카탈로그), 링 치수 visual_estimate
    rd = VIS["eyebolt_ring_d_mm"]; R = (VIS["eyebolt_ring_od_mm"] - rd) / 2
    ring = cq.Workplane("XZ").center(0, 0).circle(rd / 2).revolve(360, (-R, 0, 0), (-R, 1, 0))
    ring = cq.Workplane("XY").add(ring.val()).translate((VIS["eyebolt_x_mm"] + R, 0, HC - VIS["eyebolt_ring_od_mm"] / 2))
    shank = cq.Workplane("XY").circle(rd / 2 + 1).extrude(30).translate((VIS["eyebolt_x_mm"], 0, Z + VIS["frame_body_od_mm"] / 2 - 10))
    eye = cq.Workplane("XY").add(ring.val()).union(shank)
    ps.add("Eyebolt", eye, "steel", "Housing", f"상단 z = HC {HC}(카탈로그), 링 Ø{VIS['eyebolt_ring_od_mm']} visual_estimate", tol=0.2, ang=0.5)

    # ---- 내보내기
    out = ASSET
    ps.export_step(out / "housing_100L.step"); ps.export_obj(out / "housing.obj"); ps.export_glb(out / "housing.glb")
    man = ps.manifest({"axis_height_H_mm": Z, "shoulder_x_mm": sh_x, "shaft_end_x_mm": sh_x + E, "fancover_back_x_mm": x_back, "foot_holes_x_mm": x_holes, "foot_holes_y_mm": [-A / 2, A / 2]})
    save_json(out / "housing_parts.json", man)
    cutter = quarter_cutter().translate((0, 0, Z))
    pc = PartSet("M1_housing_cutaway")
    for n_, p in ps.parts.items():
        pc.add(n_, p["shape"].cut(cutter), p["material"], p["group"], p["note"], tol=0.2, ang=0.5)
    pc.export_obj(out / "housing_cutaway.obj"); pc.export_glb(out / "housing_cutaway.glb")
    man["cutaway_triangles"] = pc.triangles(); save_json(out / "housing_parts.json", man)

    # ---- housing_params.yaml: 항목마다 source
    params = {"meta": {"generator": "tools/cad/build_housing_100L.py", "frame": "IEC 100L (현대 SSEN HLP-2.2/4, IM B3 + FF215 B35 옵션 플랜지)", "coords": "축 +X, 발 바닥 Z 0, 축 중심 Z H, 적층 중심 X 0, mm"},
              "catalog": {k: {"value": fo[k], "source": "catalog", "where": f"카탈로그 KS 형식 치수표 100L 행 (PDF {cat['foot_mount_page']}쪽)"} for k in ("H", "A", "AA", "AB", "HA", "B1", "BB", "C", "K", "HC", "HD", "L", "D", "E", "F", "GE", "key", "O", "PF")},
              "flange_FF215": {k: {"value": fl[k], "source": "catalog", "where": f"카탈로그 KS 플랜지 치수표 100L 행 (PDF {cat['flange_page']}쪽)"} for k in ("M", "N", "P", "n", "S", "LA", "T")},
              "AD": {"value_foot_table": fo["AD"], "value_flange_table": fl["AD"], "source": "verify", "note": cat["AD_note"]},
              "visual_estimate": {k: {"value": v, "source": "visual_estimate"} for k, v in VIS.items()},
              "layout": {k: {"value": v, "source": "visual_estimate" if k != "bearing_6206" else "standard"} for k, v in LAYOUT.items()},
              "unused_catalog": {"AA": "발 측면 폭 — 시각 모델에서 직접 쓰지 않음(발 판은 AB 폭)", "F_GE_key": "키홈은 내부 모델 Shaft 에 적용"}}
    (out / "housing_params.yaml").write_text(yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
    log(f"삼각형 {ps.triangles():,} (cutaway {pc.triangles():,}) · 축단 x {sh_x + E} · 팬커버 뒷면 x {x_back} → L {sh_x + E - x_back} · 발 구멍 x {x_holes} · {man['generated_s']} s")
    return man


if __name__ == "__main__":
    build()
