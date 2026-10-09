# -*- coding: utf-8 -*-
"""R0 프로토타입 클라이언트: ws://host:8765 에 붙어 N 초 동안 메시지 수·주기·지연(t_wall 대비)을 잰다. 연결될 때까지 재시도."""
import asyncio, json, os, statistics, sys, time

sys.path.append(r"C:\Temp\pymods")
import websockets  # noqa: E402

url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8765"
dur = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
out = sys.argv[3] if len(sys.argv) > 3 else ""


async def main():
    deadline = time.time() + 300
    ws = None
    while time.time() < deadline:
        try:
            ws = await websockets.connect(url, ping_interval=None)
            break
        except Exception:
            await asyncio.sleep(1.0)
    if ws is None:
        print("[ws_client] 접속 실패", url); return
    t_conn = time.time()
    print(f"[ws_client] 접속 {url}", flush=True)
    n_state = n_hb = 0
    gaps, lat, sizes = [], [], []
    last = None
    await ws.send(json.dumps({"type": "command", "id": "proto-1", "name": "noop", "args": {}}))
    ack = None
    while time.time() - t_conn < dur:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            print("[ws_client] 5 s 무응답", flush=True); break
        now = time.time()
        m = json.loads(msg)
        if m.get("type") == "state":
            n_state += 1; sizes.append(len(msg))
            lat.append((now - m["t_wall"]) * 1000)
            if last is not None:
                gaps.append((now - last) * 1000)
            last = now
        elif m.get("type") == "heartbeat":
            n_hb += 1
        elif m.get("type") == "ack":
            ack = m
    res = {"url": url, "seconds": round(time.time() - t_conn, 1), "state_msgs": n_state, "heartbeats": n_hb,
           "rate_hz": round(n_state / max(time.time() - t_conn, 1e-6), 2),
           "gap_ms_p50": round(statistics.median(gaps), 1) if gaps else None, "gap_ms_max": round(max(gaps), 1) if gaps else None,
           "latency_ms_p50": round(statistics.median(lat), 1) if lat else None, "latency_ms_max": round(max(lat), 1) if lat else None,
           "bytes_p50": int(statistics.median(sizes)) if sizes else None, "ack": ack}
    print("[ws_client] " + json.dumps(res, ensure_ascii=False), flush=True)
    if out:
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    await ws.close()

asyncio.run(main())
