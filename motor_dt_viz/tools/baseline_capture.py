# -*- coding: utf-8 -*-
"""baseline_capture.py — 3상 전류 녹화에서 I₂/I₁ 기준선을 만든다 (P1-3). 시뮬레이션 값은 쓰지 않는다.

입력: AI Hub 238 형식 CSV 폴더(메타 9줄 + 시간,ch1,ch2,ch3 — 1 s 파일 하나가 창 하나) 또는 일반 CSV(열: t, ia, ib, ic [, va, vb, vc])
처리: 1 s 창마다 기본파 페이저(tools/aihub/extract_features.fundamental_phasors — 주파수 탐색 + 최소자승) → I₁·I₂·I₂/I₁·상 불평형 (+V₁·V₂·V₂/V₁)
       → 중앙값·p95·표준편차·변동계수. 2 kHz 샘플이라도 60 Hz 기본파 대칭 성분에는 충분하다(나이퀴스트 1 kHz ≫ 60 Hz; 1 s 창 분해능 1 Hz, 피크 보간).
품질 게이트: 창 < 500 또는 I₁ 변동계수 > 10 % 면 "부적합" (quality.pass False). 참고 등급(reference)은 부적합이어도 값을 기록하되 플래그를 남긴다.
출력: config/baselines/<motor>_<tag>.yaml + thresholds.yaml 반영용 diff 출력(자동 덮어쓰기 금지). --apply-reference 는 참고 등급일 때만
      current.negative_sequence.reference_baseline.value 에 p95 를 쓴다(baseline 은 실모터 실측 전까지 null 유지).

  py -3.12 -X utf8 tools/baseline_capture.py --motor M1 --tag AIHUB_LSF04_REFERENCE --grade reference --aihub-dir "<…>/current/2.2kW/L-SF-04/정상" --apply-reference
  py -3.12 -X utf8 tools/baseline_capture.py --motor M1 --tag SITE_2026xxxx --csv recording.csv --fs 2000
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools" / "aihub"))
from extract_features import fundamental_phasors  # noqa: E402

A = np.exp(2j * np.pi / 3)


def sym(ph):
    i1 = (ph[0] + A * ph[1] + A * A * ph[2]) / 3
    i2 = (ph[0] + A * A * ph[1] + A * ph[2]) / 3
    return abs(i1), abs(i2)


def window_features(chs, fs, f0=60.0, vchs=None):
    ph, f_est = fundamental_phasors(chs, fs, f0)
    i1, i2 = sym(ph)
    big, small = (i1, i2) if i1 >= i2 else (i2, i1)
    rms = [float(np.sqrt(np.mean((c - c.mean()) ** 2))) for c in chs]
    unb = max(abs(r - np.mean(rms)) for r in rms) / np.mean(rms) if np.mean(rms) > 0 else float("nan")
    out = {"I1_A": float(big / np.sqrt(2)), "I2_A": float(small / np.sqrt(2)), "i2_over_i1": float(small / big) if big > 0 else float("nan"),
           "unbalance": float(unb), "f0_hz": float(f_est), "seq": "abc" if i1 >= i2 else "acb", "rms_A": rms}
    if vchs is not None:
        vp, _ = fundamental_phasors(vchs, fs, f0); v1, v2 = sym(vp)
        out["V1_V"] = float(v1 / np.sqrt(2)); out["V2_V"] = float(v2 / np.sqrt(2)); out["v2_v1"] = float(v2 / v1) if v1 > 0 else float("nan")
    return out


def read_aihub(path: Path):
    """AI Hub CSV: 메타 9줄(Date, Filename, Data Label, Label No, Motor Spec, Period, Sample Rate, RMS, Data Length) 뒤 t,ch1,ch2,ch3, (끝 빈 필드)."""
    meta = {}; rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, line in enumerate(f):
            parts = [p for p in line.rstrip("\r\n").split(",")]
            if i < 9:
                meta[parts[0].strip()] = [p.strip() for p in parts[1:] if p.strip() != ""]
                continue
            try:
                rows.append([float(p) for p in parts[:4]])
            except ValueError:
                continue
    arr = np.asarray(rows, dtype=float)
    fs = float(meta.get("Sample Rate", ["2000"])[0])
    return meta, fs, [arr[:, 1], arr[:, 2], arr[:, 3]]


def read_generic(path: Path, fs: float):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f); cols = [c.lower() for c in rd.fieldnames]; data = {c: [] for c in cols}
        for r in rd:
            for c, v in zip(cols, r.values()):
                data[c].append(float(v))
    ia, ib, ic = (np.asarray(data[k]) for k in ("ia", "ib", "ic"))
    v = [np.asarray(data[k]) for k in ("va", "vb", "vc")] if all(k in data for k in ("va", "vb", "vc")) else None
    n = int(fs); wins = []
    for s in range(0, len(ia) - n + 1, n):
        wins.append(([ia[s:s + n], ib[s:s + n], ic[s:s + n]], [x[s:s + n] for x in v] if v else None))
    return wins


def stats(xs):
    xs = [x for x in xs if x == x]
    if not xs:
        return {"n": 0}
    xs_s = sorted(xs)
    return {"n": len(xs), "median": float(statistics.median(xs)), "p95": float(xs_s[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]),
            "mean": float(statistics.mean(xs)), "std": float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0, "min": float(xs_s[0]), "max": float(xs_s[-1])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--motor", default="M1"); ap.add_argument("--tag", required=True)
    ap.add_argument("--grade", choices=("baseline", "reference"), default="baseline", help="baseline = 실모터 실측(판정 기준 후보), reference = 참고 데이터셋")
    ap.add_argument("--aihub-dir", help="AI Hub 형식 CSV 폴더 (정상 라벨 폴더)")
    ap.add_argument("--csv", help="일반 CSV (t, ia, ib, ic[, va, vb, vc])"); ap.add_argument("--fs", type=float, default=2000.0)
    ap.add_argument("--f0", type=float, default=60.0)
    ap.add_argument("--min-windows", type=int, default=500); ap.add_argument("--max-cv", type=float, default=0.10)
    ap.add_argument("--apply-reference", action="store_true", help="grade=reference 일 때 thresholds.yaml reference_baseline.value 에 p95 를 기록")
    a = ap.parse_args()

    feats = []; meta_first = None; files = []
    if a.aihub_dir:
        files = sorted(glob.glob(os.path.join(a.aihub_dir, "*.csv")))
        for p in files:
            meta, fs, chs = read_aihub(Path(p))
            meta_first = meta_first or meta
            feats.append(window_features(chs, fs, a.f0))
        src = {"kind": "aihub_dir", "path": a.aihub_dir, "n_files": len(files), "meta_first": meta_first,
               "column_mapping": "메타 9줄 뒤 열 = 시간, ch1, ch2, ch3 — AI Hub 가이드라인 v2.4 §1.3.2 '전류 = 시간 + R·S·T 상전류' (config/aihub_format.yaml channels.current). 헤더에 열 이름 없음 → 상 순서는 문서 근거, 페이저 대칭분은 순서에 무관(큰 쪽을 정상분으로, seq 기록)"}
    elif a.csv:
        for chs, vchs in read_generic(Path(a.csv), a.fs):
            feats.append(window_features(chs, a.fs, a.f0, vchs))
        src = {"kind": "csv", "path": a.csv, "fs": a.fs}
    else:
        raise SystemExit("--aihub-dir 또는 --csv")
    n = len(feats)
    i1 = stats([f["I1_A"] for f in feats]); r = stats([f["i2_over_i1"] for f in feats]); unb = stats([f["unbalance"] for f in feats])
    f0s = stats([f["f0_hz"] for f in feats]); seqs = {s: sum(1 for f in feats if f["seq"] == s) for s in ("abc", "acb")}
    cv = i1["std"] / i1["mean"] if i1.get("mean") else float("nan")
    quality = {"n_windows": n, "min_windows": a.min_windows, "I1_cv": round(cv, 4), "max_cv": a.max_cv,
               "pass": bool(n >= a.min_windows and cv <= a.max_cv),
               "reasons": ([f"창 {n} < {a.min_windows}"] if n < a.min_windows else []) + ([f"I₁ 변동계수 {cv:.3f} > {a.max_cv}"] if cv > a.max_cv else [])}
    has_v = any("v2_v1" in f for f in feats)
    doc = {"motor": a.motor, "tag": a.tag, "grade": a.grade, "generated": time.strftime("%Y-%m-%d %H:%M"), "source": src,
           "window_s": 1.0, "fundamental_hz": f0s, "phase_sequence_counts": seqs,
           "I1_A": i1, "i2_over_i1": r, "unbalance": unb,
           "v2_v1": stats([f["v2_v1"] for f in feats]) if has_v else {"n": 0, "note": "전압 채널 없음 → 전압 불평형 보정 불가(compensation enabled 금지)"},
           "quality": quality,
           "note": ("참고 등급: 같은 용량대 다른 모터(공조기) 정상 데이터 — 실모터 기준선이 아니며 confirmed 조건이 되지 않는다. " if a.grade == "reference" else "실모터 실측 기준선 후보. ")
                   + "2 kHz 샘플은 60 Hz 기본파 대칭 성분 추출에 충분(나이퀴스트 1 kHz, 1 s 창 분해능 1 Hz + 피크 보간).",
           "thresholds_diff": {}}
    # thresholds.yaml 반영 제안 (자동 덮어쓰기 금지)
    thr_p = ROOT / "config" / "thresholds.yaml"; thr = yaml.safe_load(open(thr_p, encoding="utf-8"))
    ns = thr["current"]["negative_sequence"]
    if a.grade == "reference":
        doc["thresholds_diff"] = {"current.negative_sequence.reference_baseline.value": [ns["reference_baseline"].get("value"), round(r["p95"], 4)],
                                  "note": "참고 등급 — warn/danger·baseline 은 바꾸지 않는다"}
    else:
        doc["thresholds_diff"] = {"current.negative_sequence.baseline": [ns.get("baseline"), {"value": round(r["p95"], 4), "measured_at": doc["generated"], "n_windows": n, "p95": round(r["p95"], 4),
                                                                                              "median": round(r["median"], 4), "v2_v1_mean": round(doc["v2_v1"].get("mean", float("nan")), 4) if has_v else None}],
                                  "current.negative_sequence.mode": [ns.get("mode"), "baseline_multiple"],
                                  "resulting_warn_danger": [round(r["p95"] * float(ns["warn_multiple"]), 4), round(r["p95"] * float(ns["danger_multiple"]), 4)],
                                  "note": "품질 게이트 통과 시에만 사람이 yaml 에 옮긴다 (자동 반영 없음)"}
    out_dir = ROOT / "config" / "baselines"; out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{a.motor}_{a.tag}.yaml"
    out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
    print(f"{out}\n창 {n} · I₁ 중앙값 {i1.get('median', float('nan')):.3f} A (CV {cv:.3f}) · I₂/I₁ 중앙값 {r.get('median', float('nan')):.4f} / p95 {r.get('p95', float('nan')):.4f} / 최대 {r.get('max', float('nan')):.4f} · 불평형 중앙값 {unb.get('median', float('nan')):.4f} · 기본파 {f0s.get('median', float('nan')):.2f} Hz · seq {seqs}")
    print("품질:", "적합" if quality["pass"] else "부적합", quality["reasons"])
    print("thresholds.yaml 반영 제안:", json.dumps(doc["thresholds_diff"], ensure_ascii=False))
    if a.apply_reference:
        if a.grade != "reference":
            raise SystemExit("--apply-reference 는 grade=reference 전용 (실측 baseline 은 사람이 옮긴다)")
        txt = thr_p.read_text(encoding="utf-8")
        old = "      value: null               # P1-3 baseline_capture --apply-reference 가 채움 (p95)"
        new = f"      value: {round(r['p95'], 4)}             # P1-3 baseline_capture --apply-reference ({a.tag}, p95 of {n} windows, {doc['generated']}; 품질 {'적합' if quality['pass'] else '부적합: ' + '; '.join(quality['reasons'])})"
        if old in txt:
            thr_p.write_text(txt.replace(old, new), encoding="utf-8"); print("thresholds.yaml reference_baseline.value ←", round(r["p95"], 4))
        else:
            import re
            txt2, k = re.subn(r"(reference_baseline:\s*\n\s*value:) [^\n]*", lambda m: f"{m.group(1)} {round(r['p95'], 4)}             # P1-3 baseline_capture --apply-reference ({a.tag}, p95 of {n} windows, {doc['generated']})", txt, count=1)
            if k:
                thr_p.write_text(txt2, encoding="utf-8"); print("thresholds.yaml reference_baseline.value ←", round(r["p95"], 4))
            else:
                print("reference_baseline.value 줄을 찾지 못함 — 수동 반영")
    return 0


if __name__ == "__main__":
    sys.exit(main())
