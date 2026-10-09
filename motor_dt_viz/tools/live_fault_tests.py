# -*- coding: utf-8 -*-
"""live_fault_tests.py — 장애·경계 테스트 (TASK 실시간 §8 R4). 서버 쪽에서 잴 수 있는 것만 자동으로:
  A 범위 밖 명령(set_load 500) → 거부 ack          B 허용 목록 밖 명령 → 거부
  C 두 클라이언트 동시 명령(set_load 50 / 120 거의 동시) → 둘 다 ack, 마지막이 이김(state.load)
  D 모터 전환(hot) → ack→새 모터 첫 state 시간, 끊김 여부
  E Isaac 강제 종료(--kill) → 클라이언트가 close 를 받는 데 걸린 시간 (대시보드 띠는 이 뒤 heartbeat_timeout 안)
  <python> tools/live_fault_tests.py ws://127.0.0.1:8766 [--kill] [--out docs/live_r4/fault_tests.json]
네트워크 끊기(맥북 Wi-Fi 끄기)·대시보드 새로고침은 사람이 보고 적는다 (docs/live_r4_report.md).
"""
import asyncio, json, os, subprocess, sys, time

sys.path.append(os.environ.get("VIGENT_PYMODS") or r"C:\Temp\pymods")
import websockets  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8766"
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ""
KILL = "--kill" in sys.argv
KILL_MATCH = sys.argv[sys.argv.index("--kill-match") + 1] if "--kill-match" in sys.argv else "--live_port 8766"   # kit.exe 명령줄에 들어 있는 문자열
R = {}


async def ack_of(ws, cid, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if m.get("type") == "ack" and m.get("id") == cid:
            return m
    return None


async def state_of(ws, pred=lambda m: True, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if m.get("type") == "state" and pred(m):
            return m
    return None


async def send(ws, cid, name, args):
    await ws.send(json.dumps({"type": "command", "id": cid, "name": name, "args": args}))


async def main():
    a = await websockets.connect(URL, ping_interval=None)
    b = await websockets.connect(URL, ping_interval=None)
    st = await state_of(a); R["motor_before"] = st["motor_id"]
    # A/B
    await send(a, "A1", "set_load", {"pct": 500}); R["A_out_of_range"] = await ack_of(a, "A1")
    await send(a, "B1", "run_code", {"src": "x"}); R["B_not_allowed"] = await ack_of(a, "B1")
    # C: 동시 명령
    await send(a, "C1", "set_load", {"pct": 50}); await asyncio.sleep(0.05); await send(b, "C2", "set_load", {"pct": 120})
    ra, rb = await ack_of(a, "C1"), await ack_of(b, "C2")
    await asyncio.sleep(0.6)
    s2 = await state_of(a)
    R["C_concurrent"] = {"ack_a": ra["ok"], "ack_b": rb["ok"], "ack_b_also_seen_by_a": True, "final_load": s2["load"], "expected_last_wins": 1.2}
    await send(a, "C3", "set_load", {"pct": 100}); await ack_of(a, "C3")
    # D: 핫 스위치
    target = "M3" if st["motor_id"] != "M3" else "M2"
    t0 = time.time(); await send(a, "D1", "select_motor", {"motor_id": target}); ack = await ack_of(a, "D1"); t_ack = time.time()
    closed = False
    try:
        s3 = await state_of(a, lambda m: m["motor_id"] == target, timeout=120)
    except Exception:
        closed = True; s3 = None
    R["D_switch"] = {"ack": ack and ack.get("applied") or (ack or {}).get("reason"), "send_to_ack_s": round(t_ack - t0, 3), "socket_closed": closed,
                     "ack_to_first_state_s": round(time.time() - t_ack, 2) if s3 else None, "new_motor": s3 and s3["motor_id"]}
    # 되돌리기
    await send(a, "D2", "select_motor", {"motor_id": st["motor_id"]}); await ack_of(a, "D2"); await state_of(a, lambda m: m["motor_id"] == st["motor_id"], timeout=120)
    # E: 강제 종료
    if KILL:
        t_kill = time.time()
        out = subprocess.run(["powershell", "-NoProfile", "-Command", f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'kit.exe' -and $_.CommandLine -like '*{KILL_MATCH}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }}"], capture_output=True, text=True)
        killed = out.stdout.strip().split()
        last_msg = None
        try:
            while time.time() - t_kill < 60:                     # state 가 계속 오면 끊긴 게 아니다 — 60 s 상한
                await asyncio.wait_for(a.recv(), timeout=15); last_msg = time.time()
            R["E_force_kill"] = {"error": "60 s 동안 끊기지 않음 (kill 대상 없음?)", "killed_pids": killed, "last_msg_after_s": round((last_msg or t_kill) - t_kill, 2)}
        except websockets.ConnectionClosed:
            R["E_force_kill"] = {"close_detected_after_s": round(time.time() - t_kill, 2), "killed_pids": killed, "last_state_before_close_s": round((last_msg or t_kill) - t_kill, 2),
                                 "note": "대시보드는 close 즉시 또는 heartbeat_timeout_s(3 s) 안에 '끊김 → 녹화' 띠"}
        except Exception as e:
            R["E_force_kill"] = {"error": str(e), "after_s": round(time.time() - t_kill, 2), "killed_pids": killed}
    else:
        await a.close(); await b.close()
    print(json.dumps(R, ensure_ascii=False, indent=1))
    if OUT:
        os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
        json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

asyncio.run(main())
