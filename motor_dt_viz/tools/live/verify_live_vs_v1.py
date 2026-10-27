# -*- coding: utf-8 -*-
"""verify_live_vs_v1.py — 레이아웃 A §A3: 라이브 상태 보드가 받는 state(8765) 의 숫자가 V1 검증 로그(logs/verify/electrical_a0/state.csv, 장면 끝 행)와 일치하는지.

  py -3.12 -X utf8 tools/live/verify_live_vs_v1.py --out docs/dashboard_layout_a/v1_compare

7 시나리오(정상·4·8·12·16턴·저항성·반부하)를 대시보드와 같은 명령(play_scenario {scene:n}, n 은 hello.scenes)으로 차례로 띄우고,
장면 경과 ≥ settle 초(지속 규칙 3 s 뒤 정상 상태)의 state 를 V1 행과 비교한다: Ia/Ib/Ic·I₂/I₁·I₂/I_n·I_f·P_loop 상대 ±0.1 %, 판정 상태·원인 신호 동일.
덤으로 장면 전환 지연(명령 전송 → 새 장면 첫 state)을 잰다. 대시보드는 이 state 값을 그대로(반올림만) 보여준다.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)
import websockets  # noqa: E402

SCENES = ["healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload"]
FIELDS = [("Ia_rms", "Ia_rms"), ("Ib_rms", "Ib_rms"), ("Ic_rms", "Ic_rms"), ("i2_over_i1", "i2_over_i1"), ("i2_over_in", "i2_over_in"), ("i_f_A", "i_f_A"), ("p_loop_total_W", "p_loop_total_W")]


def v1_rows(path: str) -> dict:
    last = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        last[r["step"]] = r
    return last


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


async def run(a):
    v1 = v1_rows(a.v1)
    ws = await websockets.connect(a.state, ping_interval=None, max_size=1 << 22)
    hello = None; scenes = None
    while hello is None:
        m = json.loads(await ws.recv())
        if m.get("type") == "hello":
            hello = m; scenes = {s["id"]: s["n"] for s in (m.get("scenes") or [])}
    assert scenes, "hello.scenes 없음 — Isaac 을 새 코드로 실행했는지 확인"
    results = []
    for sid in SCENES:
        n = scenes[sid]
        t_cmd = time.time()
        await ws.send(json.dumps({"type": "command", "id": f"v1-{sid}", "name": "play_scenario", "args": {"scene": n}}))
        t_first = None; st = None
        deadline = time.time() + a.settle + 20
        while time.time() < deadline:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if m.get("type") != "state":
                continue
            sc = m.get("scene") or {}
            if sc.get("id") == sid and sc.get("elapsed_s", 0) < 5:
                if t_first is None:
                    t_first = time.time()
            if sc.get("id") == sid and t_first is not None and sc.get("elapsed_s", 0) >= a.settle:
                st = m; break
        row = {"scene": sid, "n": n, "switch_ms": None if t_first is None else round((t_first - t_cmd) * 1000), "ok": st is not None, "fields": [], "status_live": None, "status_v1": None}
        ref = v1.get(sid)
        if st is not None and ref is not None:
            es = st.get("electrical_source") or {}
            live_vals = {"Ia_rms": st["Ia_rms"], "Ib_rms": st["Ib_rms"], "Ic_rms": st["Ic_rms"], "i2_over_i1": st["i2_over_i1"], "i2_over_in": st.get("i2_over_in"),
                         "i_f_A": es.get("i_f_A"), "p_loop_total_W": st.get("p_loop_total_W")}
            for lk, vk in FIELDS:
                lv, rv = fnum(live_vals.get(lk)), fnum(ref.get(vk))
                if lv is None or rv is None or (lk == "i_f_A" and (rv == 0 or lv == 0)):
                    row["fields"].append({"field": lk, "live": lv, "v1": rv, "dev_pct": None, "pass": None}); continue
                dev = (lv / rv - 1) * 100 if rv else (0.0 if lv == 0 else None)
                # 라이브 state 는 반올림(전류 1자리·I₂/I₁ 4자리) — 허용은 ±0.1 % + 반올림 반 단위
                half = {"Ia_rms": 0.05, "Ib_rms": 0.05, "Ic_rms": 0.05, "i2_over_i1": 5e-5, "i2_over_in": 5e-5, "i_f_A": 0.05, "p_loop_total_W": 0.05}[lk]
                ok = dev is not None and (abs(dev) <= a.tol_pct or abs(lv - rv) <= half)
                row["fields"].append({"field": lk, "live": lv, "v1": rv, "dev_pct": None if dev is None else round(dev, 3), "pass": bool(ok)})
            row["status_live"] = [st["status"]["status"], st["status"]["cause_signal"]]
            row["status_v1"] = [ref["status"], ref["cause_signal"]]
            row["status_pass"] = row["status_live"] == row["status_v1"]
            row["sym_components_A"] = st.get("sym_components_A")
            row["dashboard_shows"] = {"i2i1": f"{st['i2_over_i1']:.3f}", "R": f"{st['Ia_rms']:.1f} A ({st['Ia_rms'] / (st['rated_line_A'] or 1):.2f}×)"}
        results.append(row)
        print(f"[v1] {sid}: switch {row['switch_ms']} ms  status {row.get('status_live')} vs {row.get('status_v1')}  " + " ".join(f"{f['field']}={f['dev_pct']}%" for f in row["fields"] if f["dev_pct"] is not None), flush=True)
    await ws.close()
    all_pass = all(r["ok"] and r.get("status_pass") and all(f["pass"] is not False for f in r["fields"]) for r in results)
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "state_ws": a.state, "v1_csv": a.v1, "tol_pct": a.tol_pct, "settle_s": a.settle, "all_pass": all_pass, "results": results,
           "note": "V1 = logs/verify/electrical_a0 (--inherent_angle_deg 0, --verify_dir). 라이브 state 전류는 1자리·I₂/I₁ 4자리 반올림이라 반올림 반 단위도 허용"}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump(out, open(a.out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        lines = ["| 장면 | 전환 ms | 판정 라이브 / V1 | Ia (dev %) | Ib | Ic | I₂/I₁ (dev %) | I₂/I_n | I_f | P_loop | 결과 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in results:
            f = {x["field"]: x for x in r["fields"]}
            cell = lambda k: ("—" if f.get(k, {}).get("dev_pct") is None else f"{f[k]['live']} ({f[k]['dev_pct']:+.3f})") if f.get(k) else "—"
            ok = r["ok"] and r.get("status_pass") and all(x["pass"] is not False for x in r["fields"])
            lines.append(f"| {r['scene']} | {r['switch_ms']} | {'/'.join(r['status_live'] or ['?'])} / {'/'.join(r['status_v1'] or ['?'])} | {cell('Ia_rms')} | {cell('Ib_rms')} | {cell('Ic_rms')} | {cell('i2_over_i1')} | {cell('i2_over_in')} | {cell('i_f_A')} | {cell('p_loop_total_W')} | {'PASS' if ok else 'FAIL'} |")
        open(a.out + ".md", "w", encoding="utf-8").write("\n".join(lines) + f"\n\n전체: {'PASS' if all_pass else 'FAIL'} · 허용 ±{a.tol_pct} % (반올림 반 단위 허용) · {out['generated']}\n")
    print("[v1] all_pass =", all_pass, flush=True)
    return 0 if all_pass else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="ws://127.0.0.1:8765")
    ap.add_argument("--v1", default=os.path.join(VIZ, "logs", "verify", "electrical_a0", "state.csv"))
    ap.add_argument("--settle", type=float, default=10.0, help="장면 경과 몇 초 뒤 state 를 비교할지 (지속 3 s + 여유)")
    ap.add_argument("--tol_pct", type=float, default=0.1)
    ap.add_argument("--out", default="")
    sys.exit(asyncio.run(run(ap.parse_args())))
