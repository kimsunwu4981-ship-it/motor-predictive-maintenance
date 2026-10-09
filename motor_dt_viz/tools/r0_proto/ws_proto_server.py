# -*- coding: utf-8 -*-
"""R0 프로토타입: Isaac Sim 프로세스 안에서 websockets 서버를 별도 스레드(asyncio 루프)로 띄우고 10 Hz 로 상태를 보낸 뒤
기존 demo_integrated.py 를 그대로 실행한다 (메인 루프는 수정하지 않음). FPS 저하·접속 가능 여부만 본다.
  C:\ISSACS~1\python.bat ws_proto_server.py <config.json>  (한글 경로가 cmd 인자에서 깨져 JSON 으로 넘긴다)
보내는 내용: demo 가 LOG_PERIOD 마다 쓰는 logs/<subdir>/status.json 을 읽어 그대로 실어 보낸다 (실제 수치, 10 Hz).
"""
import asyncio, json, os, runpy, sys, threading, time

cfg = json.load(open(sys.argv[1], encoding="utf-8"))      # ASCII 경로의 JSON: {"demo": ..., "no_server": bool, "demo_args": [...]}
demo = cfg["demo"]
no_server = bool(cfg.get("no_server"))
demo_args = list(cfg["demo_args"])
status_path = None
for i, a in enumerate(demo_args):
    if a == "--log_subdir":
        status_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(demo))), "logs", demo_args[i + 1], "status.json")

STATS = {"clients": 0, "sent": 0, "loop_lag_ms": []}


def serve():
    import websockets

    clients = set()

    async def handler(ws):
        clients.add(ws); STATS["clients"] = len(clients)
        try:
            async for msg in ws:                       # 명령 수신 자리 (프로토타입은 echo ack)
                try:
                    m = json.loads(msg)
                except Exception:
                    continue
                await ws.send(json.dumps({"type": "ack", "id": m.get("id"), "ok": False, "reason": "prototype: no commands"}))
        finally:
            clients.discard(ws); STATS["clients"] = len(clients)

    async def broadcaster():
        n = 0
        last_hb = 0.0
        while True:
            t0 = time.perf_counter()
            await asyncio.sleep(0.1)
            lag = (time.perf_counter() - t0 - 0.1) * 1000
            STATS["loop_lag_ms"].append(lag)
            payload = {"type": "state", "n": n, "t_wall": time.time()}
            if status_path and os.path.exists(status_path):
                try:
                    payload["status"] = json.load(open(status_path, encoding="utf-8"))
                except Exception:
                    pass
            if time.time() - last_hb >= 1.0:
                last_hb = time.time()
                hb = json.dumps({"type": "heartbeat", "t_wall": last_hb, "clients": len(clients)})
                for c in list(clients):
                    try:
                        await c.send(hb)
                    except Exception:
                        pass
            data = json.dumps(payload)
            for c in list(clients):
                try:
                    await c.send(data); STATS["sent"] += 1
                except Exception:
                    pass
            n += 1

    async def main():
        async with websockets.serve(handler, "0.0.0.0", 8765, ping_interval=None):
            print("[ws_proto] WebSocket 서버 ws://0.0.0.0:8765 (스레드)", flush=True)
            await broadcaster()

    asyncio.run(main())


if not no_server:
    threading.Thread(target=serve, daemon=True, name="ws_proto").start()
    time.sleep(0.5)

t_start = time.time()
sys.argv = [demo] + demo_args
try:
    runpy.run_path(demo, run_name="__main__")
finally:
    lag = STATS["loop_lag_ms"]
    out = {"server": not no_server, "clients_last": STATS["clients"], "sent": STATS["sent"],
           "broadcast_loop_lag_ms_p50": sorted(lag)[len(lag) // 2] if lag else None,
           "broadcast_loop_lag_ms_max": max(lag) if lag else None, "wall_s": round(time.time() - t_start, 1)}
    print("[ws_proto] " + json.dumps(out), flush=True)
    if status_path:
        with open(os.path.join(os.path.dirname(status_path), "ws_proto.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
