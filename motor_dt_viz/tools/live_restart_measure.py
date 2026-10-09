# -*- coding: utf-8 -*-
"""live_restart_measure.py — select_motor 자동 재시작 시간 실측 (R3).

  <python> tools/live_restart_measure.py ws://127.0.0.1:8765 M1 [--out docs/live_r3/restart_M5_to_M1.json]

측정: ① 현재 state 의 motor_id 확인 → ② select_motor 전송, ack 수신 시각 t0 → ③ 소켓이 끊기는 시각 → ④ 0.5 s 간격 재접속 시도,
새 인스턴스의 첫 state(motor_id == 목표) 수신 시각 t1. 보고: ack→끊김, 끊김→재접속, ack→첫 state(= 대시보드가 보는 '모터 전환 중' 길이).
"""
import asyncio, json, os, sys, time

sys.path.append(os.environ.get("VIGENT_PYMODS") or r"C:\Temp\pymods")
import websockets  # noqa: E402


async def first_state(url, timeout=10.0):
    async with websockets.connect(url, ping_interval=None, open_timeout=2) as ws:
        end = time.time() + timeout
        while time.time() < end:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if m.get("type") == "state":
                return m
    return None


async def main():
    url, target = sys.argv[1], sys.argv[2].upper()
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ""
    res = {"url": url, "target": target}
    async with websockets.connect(url, ping_interval=None) as ws:
        st = None
        while st is None:
            m = json.loads(await ws.recv())
            if m.get("type") == "state":
                st = m
        res["from"] = st["motor_id"]; res["fps_before"] = st["perf"].get("fps")
        print(f"[restart] 현재 {st['motor_id']} → {target} 요청", flush=True)
        await ws.send(json.dumps({"type": "command", "id": "rs1", "name": "select_motor", "args": {"motor_id": target}}))
        t_send = time.time()
        ack = None
        while ack is None:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if m.get("type") == "ack" and m.get("id") == "rs1":
                ack = m
        res["ack"] = ack; t_ack = time.time(); res["send_to_ack_s"] = round(t_ack - t_send, 3)
        print(f"[restart] ack {ack.get('ok')} {ack.get('applied') or ack.get('reason')}", flush=True)
        if not ack.get("ok"):
            json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1) if out else None
            return
        try:
            while True:
                await asyncio.wait_for(ws.recv(), timeout=60)
        except Exception:
            pass
        t_close = time.time(); res["ack_to_close_s"] = round(t_close - t_ack, 2)
        print(f"[restart] 연결 끊김 +{res['ack_to_close_s']} s", flush=True)
    # 재접속 대기
    t1 = None; attempts = 0; first_connect = None
    deadline = time.time() + 300
    while time.time() < deadline:
        attempts += 1
        try:
            m = await first_state(url, timeout=15)
            if first_connect is None:
                first_connect = time.time()
            if m and m.get("motor_id") == target:
                t1 = time.time(); res["first_state"] = {"motor_id": m["motor_id"], "mode": m["mode"], "step": m["step"], "fps": m["perf"].get("fps")}
                break
        except Exception:
            pass
        await asyncio.sleep(0.5)
    res["reconnect_attempts"] = attempts
    if first_connect:
        res["ack_to_reconnect_s"] = round(first_connect - t_ack, 1)
    if t1:
        res["ack_to_first_state_s"] = round(t1 - t_ack, 1)
        print(f"[restart] 새 모터 {target} 첫 state: ack 기준 +{res['ack_to_first_state_s']} s (재접속 +{res.get('ack_to_reconnect_s')} s, 시도 {attempts}회)", flush=True)
    else:
        print("[restart] 시간 안에 새 state 없음", flush=True)
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

asyncio.run(main())
