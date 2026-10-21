# -*- coding: utf-8 -*-
"""datasheet_to_yaml.py — M1 데이터시트 xlsx(+ 카탈로그 PDF 치수표, RMxprt 채택 스냅샷) → assets/motors/M1/inputs/datasheet_v4.yaml

입력(모두 assets/motors/M1/inputs/ 의 복사본, PROVENANCE.md 참조):
  Maxwell_M1_HLP2.2-4_전체데이터시트_v4.xlsx   「설계값(라이브)」·「카탈로그 직접값」·「권선 배치표」·「ITSC 케이스」·「해석 설정(3D)」
  현대_SSEN_카탈로그.pdf (Maxwell 저장소 docs/sources, 읽기만)  KS 형식 치수표 100L 행 (각 치수 기호 그대로)
  rmxprt_v2m2.json                               Maxwell 3D 모델이 실제로 쓴 슬롯·권선·스큐 치수 (RMxprt v2 오버라이드 반영)
규칙: 숫자를 손으로 적지 않는다 — 전부 파일에서 읽어 키 이름으로 넣는다. 재실행 멱등.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[2]
INP = ROOT / "assets" / "motors" / "M1" / "inputs"
XLSX = INP / "Maxwell_M1_HLP2.2-4_전체데이터시트_v4.xlsx"
RMX = INP / "rmxprt_v2m2.json"
import os
PDF = Path(os.environ.get("MAXWELL_ROOT", r"C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링")) / "docs" / "sources" / "현대_SSEN_카탈로그.pdf"   # D1: 카탈로그 PDF 는 저장소 밖(docs/sources, gitignore) — 없으면 datasheet_v4.yaml 을 재생성하지 말 것 (커밋본이 입력 정본)
OUT = INP / "datasheet_v4.yaml"

FOOT_COLS = ["frame", "H", "poles", "A", "AA", "AB", "HA", "B1", "B2", "B3", "BB", "C", "K", "N_holes", "HC", "HD", "L", "D", "E", "F", "GE", "key", "AD", "O", "PF"]
FLANGE_COLS = ["frame", "poles", "flange", "M", "N", "P", "n", "S", "LA", "T", "AC_table", "L", "D", "E", "F", "GE", "key", "AD", "O", "PF"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def num(x):
    if isinstance(x, (int, float)):
        return x
    try:
        return float(x) if "." in str(x) else int(x)
    except (TypeError, ValueError):
        return x


def read_xlsx():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    out = {}
    # 설계값(라이브): 절 → 기호 → {name, value, unit, grade, basis}
    sections = {}; cur = None
    for r in wb["설계값(라이브)"].iter_rows(min_row=4, values_only=True):
        if r[0] and r[1] is None and r[2] is None and re.match(r"^\d+\.", str(r[0])):
            cur = str(r[0]).strip(); sections[cur] = {}
            continue
        if cur and r[1]:
            sym = str(r[1]).strip()
            if sym == "-":
                sym = str(r[0]).strip()
            sections[cur][sym] = {"name": r[0], "value": num(r[2]), "unit": r[3], "grade": r[4], "basis": r[5]}
    out["design_sections"] = sections
    flat = {}
    for sec, d in sections.items():
        for sym, v in d.items():
            if sym not in flat:
                flat[sym] = {**v, "section": sec}
    out["design"] = flat
    out["catalog_direct"] = [{"item": r[0], "value": r[1], "unit": r[2], "note": r[3]} for r in wb["카탈로그 직접값"].iter_rows(min_row=3, values_only=True) if r[0]]
    out["winding_table"] = [{"slot": int(r[0]), "top": r[1], "bottom": r[2], "coil": int(r[3]), "phase": r[4], "winding": r[5], "fault": r[6]}
                            for r in wb["권선 배치표"].iter_rows(min_row=4, values_only=True) if isinstance(r[0], (int, float))]
    out["itsc_cases"] = [{"case": r[0], "turns": r[1], "ratio": r[2], "coil_basis": r[3], "R_f": r[4], "load": r[5], "equiv": r[6], "note": r[7]}
                         for r in wb["ITSC 케이스"].iter_rows(min_row=5, values_only=True) if r[0] and r[1] is not None]
    out["load_speed_table"] = [{"load": r[0], "slip": r[3], "rpm": r[5]} for r in wb["해석 설정(3D)"].iter_rows(min_row=3, values_only=True) if isinstance(r[0], (int, float))]
    return out


def read_catalog_pdf():
    if not PDF.exists():
        return {"available": False, "note": "카탈로그 PDF 없음(Maxwell 저장소 docs/sources)"}
    import pypdf
    r = pypdf.PdfReader(str(PDF))
    foot = flange = None; foot_page = flange_page = None
    for i, pg in enumerate(r.pages):
        t = (pg.extract_text() or "").replace("\n", " ")
        m = re.search(r"100L 100 2~8 ((?:[\d.x/\-]+ ){21}[\d.]+)", t)
        if m and foot is None:
            vals = ["100L", 100, "2~8"] + [num(v) for v in m.group(1).split()]
            foot = dict(zip(FOOT_COLS, vals)); foot_page = i + 1
        m = re.search(r"100L 2~8 FF215 ((?:[\d.x/\-]+ ){16}[\d.]+)", t)
        if m and flange is None:
            vals = ["100L", "2~8", "FF215"] + [num(v) for v in m.group(1).split()]
            flange = dict(zip(FLANGE_COLS, vals)); flange_page = i + 1
    return {"available": True, "sha256": sha(PDF), "foot_mount_IM_B3": foot, "foot_mount_page": foot_page, "flange_FF215": flange, "flange_page": flange_page,
            "AD_note": "발 장착(IM B3) 표의 AD 328 은 그림 B(90–200Fr) 끝면도에서 프레임 측면~단자함 끝까지의 전체 폭 치수로 그려져 있다(축 중심~단자함 상면이 아님). "
                       "플랜지(FF215) 표의 AD 175 는 플랜지 그림 기준으로 정의가 다르다. 두 값 모두 카탈로그 원문 그대로 보관하고, 하우징 모델은 HD 247(단자함 상면 높이)만 구속으로 쓴다.",
            "columns_foot": FOOT_COLS, "columns_flange": FLANGE_COLS}


def read_rmxprt():
    d = json.loads(RMX.read_text(encoding="utf-8"))
    i = d["inputs"]; res = d["results"]
    return {"tag": d["tag"], "design": d.get("design"), "sha256": sha(RMX),
            "stator": {"slot_type": i["slot_type_s"], "Hs0": i["Hs0_s"], "Hs1": i["Hs1_s"], "Hs2": i["Hs2_s"], "Bs0": i["Bs0_s"], "Bs1": i["Bs1_s"], "Bs2": i["Bs2_s"],
                       "Q_s": i["Q_s"], "N_c": i["N_c"], "conductors_per_slot": i["conductors_per_slot"], "coil_pitch": i["coil_pitch"], "parallel": i["parallel"],
                       "wire_d": i["wire_d"], "wire_wrap": i["wire_wrap"], "strands": i["strands"], "slot_area_gross": res["slot_area_gross"], "slot_area_net": res["slot_area_net"],
                       "N_ph": res["N_ph"], "half_turn_len": res["half_turn_len"], "steel": i["steel"]},
            "rotor": {"slot_type": i["rotor"]["type"], "Hs0": i["rotor"]["Hs0"], "Hs01": i["rotor"]["Hs01"], "Bs0": i["rotor"]["Bs0"], "Bs1": i["rotor"]["Bs1"], "Bs2": i["rotor"]["Bs2"], "Hs2": i["rotor"]["Hs2"],
                      "Q_r": i["Q_r"], "cast": i["rotor"]["cast"], "end_ring_w": i["rotor"]["end_ring_w"], "end_ring_h": i["rotor"]["end_ring_h"], "end_length": i["rotor"]["end_length"],
                      "skew_rotor_pitch": i["skew_rotor_pitch"], "bar_area": res.get("rotor_slot_area_calc")},
            "note": "Maxwell 3D(M1_3D_full)·2D 모델이 실제로 쓴 치수 = 데이터시트 §5·§7 기본값에 RMxprt v2 오버라이드(①~④·⑥: 로터 브리지 0.8, 고정자 개구 2.0, 쐐기 1.5, 로터 바 19.8/4.5/2.4, N_c 16)를 적용한 값. "
                    "geometry_check_v2.json 의 체적은 이 치수로 만든 모델의 측정값이므로 동일성 검증은 이 절을 기준으로 한다."}


def main():
    data = {"meta": {"generator": "tools/cad/datasheet_to_yaml.py", "xlsx": XLSX.name, "xlsx_sha256": sha(XLSX), "rmxprt_json": RMX.name,
                     "units": "mm, deg, W, A, V (시트 단위 열 참조)", "rule": "숫자 수기 입력 없음 — 전부 파일에서 읽음"}}
    data.update(read_xlsx())
    data["catalog_frame_100L"] = read_catalog_pdf()
    mx = read_rmxprt()
    data["maxwell_model"] = mx
    txt = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200)
    if not OUT.exists() or OUT.read_text(encoding="utf-8") != txt:
        OUT.write_text(txt, encoding="utf-8")
    print(f"{OUT} ({OUT.stat().st_size / 1024:.1f} KB) · design {len(data['design'])} 기호 · catalog_direct {len(data['catalog_direct'])} · winding {len(data['winding_table'])} · foot {data['catalog_frame_100L'].get('foot_mount_IM_B3')} · flange {data['catalog_frame_100L'].get('flange_FF215')}")


if __name__ == "__main__":
    sys.exit(main())
