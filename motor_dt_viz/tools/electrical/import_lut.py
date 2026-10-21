# -*- coding: utf-8 -*-
"""import_lut.py — Maxwell 경로 B 의 MCCM LUT 를 data/electrical/M1_mccm_lut_v<N>.json 으로 가져온다 (멱등).
같은 sha256 이면 새 버전을 만들지 않는다. data/electrical/LUT_INDEX.md 에 한 줄 추가.
실행: py -3.12 tools/electrical/import_lut.py [--src <mccm_lut.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MAXWELL_ROOT = os.environ.get("MAXWELL_ROOT", r"C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링")   # D1(2026-10-21): 환경변수로 Maxwell 저장소 위치 지정 (docs/REPRODUCE.md)
DEFAULT_SRC = os.path.join(MAXWELL_ROOT, "maxwell", "results", "mccm_lut.json")
OUT_DIR = os.path.join(ROOT, "data", "electrical")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    if not os.path.exists(src):
        print(f"[import_lut] 원본 없음: {src}"); return 2
    lut = json.load(open(src, encoding="utf-8"))
    rows = lut["rows"]
    if not any(int(r.get("turns", -1)) == 0 for r in rows):
        print("[import_lut] 0 % (정상) 행이 없다 — mccm.py 를 다시 돌려 만들 것. 임의로 채우지 않음."); return 3
    if "I2_angle_deg_vs_I1" not in lut["columns"]:
        print("[import_lut] I₂ 위상 열이 없다 — tools/maxwell/mccm.py 에 추가 후 재실행 필요."); return 4
    digest = sha256(src)
    os.makedirs(OUT_DIR, exist_ok=True)
    existing = sorted(f for f in os.listdir(OUT_DIR) if re.match(r"M1_mccm_lut_v\d+\.json$", f))
    for f in existing:
        try:
            if json.load(open(os.path.join(OUT_DIR, f), encoding="utf-8")).get("provenance", {}).get("source_sha256") == digest:
                print(f"[import_lut] 같은 sha256 → 기존 {f} 유지"); return 0
        except Exception:
            pass
    n = 1 + max([int(re.search(r"_v(\d+)", f).group(1)) for f in existing] or [0])
    mccm_py = os.path.join(os.path.dirname(os.path.dirname(src)), "..", "tools", "maxwell", "mccm.py")
    mccm_py = os.path.abspath(mccm_py)
    res_dir = os.path.dirname(src)
    mccm_res = json.load(open(os.path.join(res_dir, "mccm_results.json"), encoding="utf-8")) if os.path.exists(os.path.join(res_dir, "mccm_results.json")) else {}
    cal = mccm_res.get("calibration", {})
    params = lut.get("params", {})
    prov = {
        "source_path": src, "source_sha256": digest, "source_mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(src))),
        "imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mccm_py": {"path": mccm_py, "sha256": sha256(mccm_py) if os.path.exists(mccm_py) else None, "git_hash": "n/a (권상모터_3D모델링 은 git 저장소가 아님)"},
        "rmxprt_tag": params.get("source_tag", "v2"), "rmxprt_source": params.get("source"), "material": params.get("material", "M19_29G (×1.45 보정)"),
        "iron_loss_factor": params.get("iron_loss_factor", 1.45),
        "rfe_calibration": "physical" if cal.get("method") == "physical" else ("fitted_383" if cal else "unknown"),
        "calibration": {k: cal.get(k) for k in ("method", "Rfe", "R2p_hot", "R2p_scale", "I", "pf", "P_in_W")},
        "negative_sequence_impedance_ohm": params.get("Z_sc", 7.136), "base_turns_per_phase": lut.get("N_ph", 192), "rated_current_A": lut.get("I_n", 4.73),
        "axes": lut["axes"], "axis_definition": {"turn_ratio_pct": "n_short / base_turns_per_phase × 100 (상 A, 코일 1개 내)", "R_f": "단락 접촉 저항 [Ω]", "load": "부하 비율 (속도는 「해석 설정(3D)」 Kloss 표)"},
        "grade": "등가회로(RMxprt v2+MCCM)", "fem_verified": False, "status": "provisional",
        "limitations": ["단일 주파수 등가회로 — 포화·시간 고조파·RSH 없음", "단락 턴 누설을 μ·X1 로 근사", "역상 임피던스 = 카탈로그 Z_sc 7.136 Ω 고정 (FEM 미검증)",
                        "학생판 AEDT 로 FEM 불가 — 정규 라이선스에서 재검증", "C0 물리 정합: 입력 전력 정합, 전류 +2.4 %·pf −0.019"],
    }
    out = {"provenance": prov, "N_ph": lut.get("N_ph"), "I_n": lut.get("I_n"), "params": params, "axes": lut["axes"], "columns": lut["columns"], "rows": rows}
    name = f"M1_mccm_lut_v{n}.json"
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    idx = os.path.join(OUT_DIR, "LUT_INDEX.md")
    if not os.path.exists(idx):
        with open(idx, "w", encoding="utf-8") as f:
            f.write("# LUT 버전 색인 (import_lut.py 가 기록)\n\n| 버전 | 가져온 날짜 | 원본 sha256 (앞 12) | R_fe 보정 | 점 수 | 비고 |\n|---|---|---|---|---|---|\n")
    with open(idx, "a", encoding="utf-8") as f:
        f.write(f"| {name} | {prov['imported_at']} | {digest[:12]} | {prov['rfe_calibration']} | {len(rows)} | grade {prov['grade']}, RMxprt {prov['rmxprt_tag']}, 재질 {prov['material']}, provisional, FEM 미검증 |\n")
    print(f"[import_lut] {name} 생성 ({len(rows)} rows, sha {digest[:12]}, R_fe {prov['rfe_calibration']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
