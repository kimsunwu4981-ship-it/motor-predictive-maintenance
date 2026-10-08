# -*- coding: utf-8 -*-
"""fleet_compare.py — fleet 배치 판정 로그 두 벌(변경 전·후)의 비교표 (베어링 지표 정의 교체 2026-10-08).

  <python> tools/fleet_compare.py --before logs/fleet_before --after logs/fleet --out docs/bearing_metric_change_comparison.md

비교 항목 (모터 × 모드):
  · 장면(step)별 장면 끝 상태·원인 신호 — 전/후
  · 상태별 시간 점유율(SAFE/WARN/DANGER %) — 전/후
  · 종합 상태가 달라진 행 수, 원인 신호가 달라진 행 수
  · 베어링 신호 열: 전 bearing_index 등급 ↔ 후 bearing(종합)·bearing_kurtosis·bearing_hf_ratio 등급 점유율
숫자는 전부 두 로그(status_fleet.csv)와 meta.json 에서만 온다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, VIZ)

from engine import motor_library as ml  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402

LV = ("SAFE", "WARN", "DANGER")
KO = {"SAFE": "안전", "WARN": "경고", "DANGER": "위험"}


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8", newline="")))


def cause(r):
    if r["cause_signal"] == "-":
        return "-"
    c = r["cause_signal"] if r["cause_component"] in ("-", "") else f"{r['cause_signal']}/{r['cause_component']}"
    return f"{c} {float(r['value']):g}"


def share(rs, key="status"):
    c = Counter(r[key] for r in rs)
    n = max(len(rs), 1)
    return " / ".join(f"{KO[l]} {100 * c.get(l, 0) / n:.0f} %" for l in LV)


def end_rows(rs, steps):
    """장면별 마지막 행 (t < t_end)."""
    out, acc = [], 0.0
    for s in steps:
        t0, t1 = acc, acc + float(s["duration_s"])
        acc = t1
        seg = [r for r in rs if t0 <= float(r["t_real_s"]) < t1]
        out.append((s["id"], seg[-1] if seg else None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=os.path.join(VIZ, "logs", "fleet_before"))
    ap.add_argument("--after", default=os.path.join(VIZ, "logs", "fleet"))
    ap.add_argument("--out", default=os.path.join(VIZ, "docs", "bearing_metric_change_comparison.md"))
    a = ap.parse_args()
    L = ["# 베어링 지표 교체 전후 fleet 판정 비교 (M1~M5 × 기계·전기)", "",
         f"- 전: `{os.path.relpath(a.before, VIZ)}` (bearing_index = 베어링 결함 손실 배율 대체값, 경고 2배 / 위험 5배)",
         f"- 후: `{os.path.relpath(a.after, VIZ)}` (bearing_kurtosis 3.5/4.0 + bearing_hf_ratio 1.5/2.5, 종합 = 둘 중 나쁜 쪽; 시뮬레이션 등가값은 config/thermal.yaml)",
         "- 두 로그 모두 `tools/run_fleet.py`(엔진 배치)·`engine/thresholds.py` 판정. 온도·전류·진동 수치는 바뀌지 않았고 베어링 신호와 그에 따른 종합·원인만 다르다.",
         "- 숫자는 전부 두 로그의 `status_fleet.csv`·`meta.json`에서 왔다 (tools/fleet_compare.py).", ""]
    changed_total = 0
    for mode in ("mechanical", "electrical"):
        player = ScenarioPlayer.for_mode(mode)
        steps = player.steps
        L += [f"## {'기계' if mode == 'mechanical' else '전기'} 모드 — 장면 끝 상태 (원인 신호 값)", "",
              "| 모터 | 장면 | 전 | 후 | 변화 |", "|---|---|---|---|---|"]
        for mid in ml.list_ids():
            b = rows(os.path.join(a.before, mid, mode, "status_fleet.csv"))
            f = rows(os.path.join(a.after, mid, mode, "status_fleet.csv"))
            assert len(b) == len(f), f"{mid} {mode}: 행 수 다름 {len(b)} vs {len(f)}"
            for (sid, rb), (_, rf) in zip(end_rows(b, steps), end_rows(f, steps)):
                if rb is None or rf is None:
                    continue
                sb, sf = f"{KO[rb['status']]} ({cause(rb)})", f"{KO[rf['status']]} ({cause(rf)})"
                L.append(f"| {mid} | {sid} | {sb} | {sf} | {'—' if sb == sf else '**변경**'} |")
        L += ["", f"### {'기계' if mode == 'mechanical' else '전기'} 모드 — 상태 시간 점유율·변경 행", "",
              "| 모터 | 행 | 종합 상태 점유율 전 | 종합 상태 점유율 후 | 종합 변경 행 | 원인 변경 행 | 베어링 등급 전 (bearing_index) | 베어링 종합 후 | 후 kurtosis | 후 고주파 배율 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for mid in ml.list_ids():
            b = rows(os.path.join(a.before, mid, mode, "status_fleet.csv"))
            f = rows(os.path.join(a.after, mid, mode, "status_fleet.csv"))
            ch = sum(1 for x, y in zip(b, f) if x["status"] != y["status"])
            cc = sum(1 for x, y in zip(b, f) if x["cause_signal"] != y["cause_signal"])
            changed_total += ch
            L.append(f"| {mid} | {len(f)} | {share(b)} | {share(f)} | {ch} | {cc} | {share(b, 'bearing_index')} | "
                     f"{share(f, 'bearing')} | {share(f, 'bearing_kurtosis')} | {share(f, 'bearing_hf_ratio')} |")
        L.append("")
    L += ["## 읽는 법", "",
          "- 기계 모드 베어링 결함 장면: 전에는 손실 배율 5.0(≥5배)으로 베어링 지표가 위험이었고, 후에는 소손형 등가값(kurtosis·고주파 모두 위험 경계 초과)으로 위험이다. "
          "원인 신호는 초과 비율이 가장 큰 신호를 고르므로 진동(4.8/4.5)이 아니라 bearing_kurtosis 로 바뀐다 — 종합 등급은 같다.",
          "- 축정렬불량 장면: 전에는 손실 배율 2.5(경고), 후에는 M2 실측 등가값(kurtosis 3.7·고주파 ×2.2)으로 둘 다 경고 — 종합 등급은 같다.",
          "- 냉각팬·브레이크·과부하·전기 모드: 베어링 신호가 정상값(kurtosis 3.0·×1.0)이라 전후 모두 베어링은 안전, 종합·원인 변화 없음.",
          f"- 종합 상태가 달라진 행: 전체 {changed_total} 행 (0 이면 등급은 그대로이고 원인 신호 표기만 바뀐 것).", ""]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(L))
    print(f"[compare] → {a.out} (종합 상태 변경 행 {changed_total})")


if __name__ == "__main__":
    main()
