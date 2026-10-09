# -*- coding: utf-8 -*-
"""live_demo_drive.py — 라이브 데모 5단계(docs/live_demo_script.md)를 같은 타이밍으로 자동 전송 (리허설·녹화용).

  <python> tools/live_demo_drive.py ws://127.0.0.1:8765 [--motor2 M1] [--fast]

단계: 1 정상 15 s → 2 inject bearing_de_fault 45 s → 3 inject itsc_4turn 30 s → 4 reset 30 s → 5 select_motor M1(재접속 대기) + bearing_de_fault 45 s.
통합 모드(--mode integrated)에서 돌려야 2·3 이 둘 다 적용된다. 각 ack 와 전환 시간을 stdout 과 --out JSON 에 남긴다.
"""
import asyncio, json, os, sys, time

sys.path.append(os.environ.get("VIGENT_PYMODS") or r"C:\Temp\pymods")
import websockets  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8765"
MOTOR2 = sys.argv[sys.argv.index("--motor2") + 1] if "--motor2" in sys.argv else "M1"
FAST = "--fast" in sys.argv
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ""
W = (lambda s: s / 6) if FAST else (lambda s: s)
LOG = []


def log(msg):
    print(f"[demo {time.strftime('%H:%M:%S')}] {msg}", flush=True); LOG.append({"t": time.time(), "msg": msg})


async def connect():
    for _ in range(300):
        try:
            return await websockets.connect(URL, ping_interval=None, open_timeout=2)
        except Exception:
            await asyncio.sleep(0.5)
    raise RuntimeError("접속 실패")


async def cmd(ws, name, args, cid):
    await ws.send(json.dumps({"type": "command", "id": cid, "name": name, "args": args}))
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if m.get("type") == "ack" and m.get("id") == cid:
            log(f"{name} {args} → {'ok' if m['ok'] else 'rejected'} {m.get('applied') or m.get('reason')}")
            return m


async def wait_state(ws, seconds, want=None):
    end = time.time() + seconds
    last = None
    while time.time() < end:
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        except asyncio.TimeoutError:
            continue
        if m.get("type") == "state":
            last = m
            if want and want(m):
                return m
    return last


async def main():
    ws = await connect()
    st = await wait_state(ws, 5)
    log(f"접속 {URL} · 모터 {st and st['motor_id']} · 모드 {st and st['mode']}")
    if st and st["scene"] and st["scene"]["playing"]:
        await cmd(ws, "stop_scenario", {}, "d0")
    log("1) 정상 운전"); await wait_state(ws, W(15))
    log("2) DE 베어링 결함 주입"); await cmd(ws, "inject_fault", {"fault": "bearing_de_fault", "on": True}, "d2")
    s = await wait_state(ws, W(45)); log(f"   → 상태 {s['status']['status']} 원인 {s['status']['cause_signal']} {s['status']['value']} / DE 베어링 {s['T'].get('bearing_de')} °C 진동 {s['vibration_mms']}")
    log("3) 턴간 단락 4턴"); await cmd(ws, "inject_fault", {"fault": "itsc_4turn", "on": True}, "d3")
    s = await wait_state(ws, W(30)); log(f"   → 상태 {s['status']['status']} R상 {s['Ia_rms']} A I2/I1 {s['i2_over_i1']}")
    log("4) 리셋"); await cmd(ws, "reset", {}, "d4")
    s = await wait_state(ws, W(30)); log(f"   → 상태 {s['status']['status']} DE 베어링 {s['T'].get('bearing_de')} °C")
    log(f"5) 모터 {MOTOR2} 로 전환 (자동 재시작)"); a = await cmd(ws, "select_motor", {"motor_id": MOTOR2}, "d5")
    t_ack = time.time()
    try:
        await ws.close()
    except Exception:
        pass
    ws2 = None
    for _ in range(600):
        try:
            ws2 = await websockets.connect(URL, ping_interval=None, open_timeout=2)
            m = await wait_state(ws2, 15, want=lambda x: x["motor_id"] == MOTOR2)
            if m:
                break
            await ws2.close(); ws2 = None
        except Exception:
            ws2 = None
        await asyncio.sleep(0.5)
    if not ws2:
        log("전환 실패 — 새 모터 state 없음"); return
    log(f"   → {MOTOR2} 첫 state +{time.time() - t_ack:.1f} s (ack 기준)")
    await asyncio.sleep(W(5))
    log(f"   DE 베어링 결함 주입 ({MOTOR2})"); await cmd(ws2, "inject_fault", {"fault": "bearing_de_fault", "on": True}, "d6")
    s = await wait_state(ws2, W(45)); log(f"   → 상태 {s['status']['status']} DE 베어링 {s['T'].get('bearing_de')} °C (M5 와 비교)")
    await cmd(ws2, "reset", {}, "d7")
    log("끝")
    if OUT:
        json.dump(LOG, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

asyncio.run(main())
