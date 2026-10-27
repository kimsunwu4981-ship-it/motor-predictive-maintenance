# -*- coding: utf-8 -*-
"""state_snapshot.py — 8765 state 한 건을 받아 JSON 으로 저장 (패널 Q1 3자 대조: 패널 표시 vs 대시보드 vs 엔진 state).
  py -3.12 -X utf8 tools/live/state_snapshot.py --out docs/isaac_panel_q1/measure/state_4turn.json [--cmd play_scenario --scene 2] [--wait 3]
--cmd 를 주면 그 명령을 먼저 보내고(ack 기록) --wait 초 뒤의 state 를 저장한다 (시나리오 복귀 검사).
"""
import argparse
import asyncio
import json
import os
import sys
import time

for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)
import websockets  # noqa: E402

KEYS = ["t_session_s", "case", "step", "control_source", "manual_fault", "load", "Ia_rms", "Ib_rms", "Ic_rms", "i2_over_i1", "i2_over_in", "p_loop_total_W", "persistence", "status", "sym_components_A"]


async def main(a):
    ws = await websockets.connect(a.state, ping_interval=None, max_size=1 << 22)
    ack = None
    if a.cmd:
        args = {"scene": a.scene} if a.cmd == "play_scenario" else {}
        await ws.send(json.dumps({"type": "command", "id": "snap-1", "name": a.cmd, "args": args}))
    end = time.time() + a.wait
    st = None
    while time.time() < max(end, time.time() + 0.1):
        m = json.loads(await asyncio.wait_for(ws.recv(), 5))
        if m.get("type") == "ack" and m.get("id") == "snap-1":
            ack = m
        elif m.get("type") == "state":
            st = m
            if time.time() >= end:
                break
    out = {"taken": time.strftime("%Y-%m-%d %H:%M:%S"), "ack": ack, "state": {k: st.get(k) for k in KEYS} if st else None}
    if st:
        es = st.get("electrical_source") or {}
        out["state"]["electrical_source"] = {k: es.get(k) for k in ("case", "turns", "R_f_ohm", "i_f_A", "p_loop_total_W", "lut_i2_over_i1", "clamped")}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[snapshot]", json.dumps({k: out["state"].get(k) for k in ("case", "control_source", "i2_over_i1", "Ia_rms")} if out["state"] else None, ensure_ascii=False), "ack", (ack or {}).get("ok"))
    await ws.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="ws://127.0.0.1:8765")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cmd", default="")
    ap.add_argument("--scene", type=int, default=1)
    ap.add_argument("--wait", type=float, default=0.5)
    asyncio.run(main(ap.parse_args()))
