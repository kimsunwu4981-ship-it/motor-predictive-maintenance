# -*- coding: utf-8 -*-
"""LiveBridge (app/live_bridge.py) — Isaac Sim 없이 WebSocket 왕복·허용 목록·범위 검사·ack 를 확인한다."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import socket
import sys
import time

import pytest

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, VIZ)
sys.path.insert(0, os.path.join(VIZ, "app"))
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

websockets = pytest.importorskip("websockets")
from engine.config_loader import load
from engine import motor_library as ml  # noqa: E402
from live_bridge import LiveBridge, lan_ip  # noqa: E402


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def make_bridge(**over) -> LiveBridge:
    cfg = copy.deepcopy(load("live"))
    cfg["server"].update({"host": "127.0.0.1", "port": free_port(), "state_hz": 20, "heartbeat_hz": 5, "perf_period_s": 60})
    cfg["server"].update(over)
    return LiveBridge(cfg, log=lambda *a, **k: None).start()


async def recv_until(ws, pred, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(end - time.time(), 0.05)))
        if pred(m):
            return m
    raise AssertionError("expected message not received")


async def wait_commands(b: LiveBridge, timeout=2.0) -> list[dict]:
    """메인 루프 역할 — 클라이언트 이벤트 루프를 막지 않도록(송신 버퍼가 flush 되도록) asyncio.sleep 으로 기다린다."""
    end = time.time() + timeout
    while time.time() < end:
        c = b.poll_commands()
        if c:
            return c
        await asyncio.sleep(0.02)
    return []


def test_state_heartbeat_and_command_roundtrip():
    b = make_bridge()

    async def run():
        async with websockets.connect(f"ws://127.0.0.1:{b.port}") as ws:
            hello = await recv_until(ws, lambda m: m["type"] == "hello")          # 접속 직후: 허용 명령 목록·모터 목록 (config/live.yaml)
            assert set(hello["commands"]) == set(load("live")["commands"]) and hello["motors"] == ml.list_ids() == ["M1"] and hello["restart_eta_s"] > 0
            b.publish({"t_s": 1.0, "mode": "mechanical", "perf": {"fps": 60.0}})
            st = await recv_until(ws, lambda m: m["type"] == "state")
            assert st["schema"] == load("live")["schema"] and st["t_s"] == 1.0 and "t_wall" in st
            assert st["host"]["ws"].startswith("ws://") and st["host"]["clients"] == 1 and st["perf"]["fps"] == 60.0
            await recv_until(ws, lambda m: m["type"] == "heartbeat" and "clients" in m)
            # 같은 state 는 다시 보내지 않는다 (최신 것만) — 새로 publish 하면 온다
            b.publish({"t_s": 2.0})
            st2 = await recv_until(ws, lambda m: m["type"] == "state" and m["t_s"] == 2.0)
            assert st2["t_s"] == 2.0
            # 명령 → 메인 루프 큐 → ack 방송
            await ws.send(json.dumps({"type": "command", "id": "c1", "name": "set_load", "args": {"pct": 135}}))
            cmds = await wait_commands(b)
            assert cmds and cmds[0]["name"] == "set_load" and cmds[0]["args"]["pct"] == 135.0 and cmds[0]["id"] == "c1"
            b.ack(cmds[0], True, {"load": 1.35})
            ack = await recv_until(ws, lambda m: m["type"] == "ack" and m["id"] == "c1")
            assert ack["ok"] is True and ack["applied"] == {"load": 1.35}
    asyncio.run(run())
    assert b.stats["commands"] == 1 and b.stats["sent"] >= 2
    b.stop()


def test_rejections_follow_config():
    b = make_bridge()
    spec = load("live")["commands"]

    async def send(ws, cid, name, args):
        await ws.send(json.dumps({"type": "command", "id": cid, "name": name, "args": args}))
        return await recv_until(ws, lambda m: m["type"] == "ack" and m["id"] == cid)

    async def run():
        async with websockets.connect(f"ws://127.0.0.1:{b.port}") as ws:
            hi = spec["set_load"]["pct"][1]
            a = await send(ws, "r1", "set_load", {"pct": hi + 50})
            assert a["ok"] is False and "range" in a["reason"]
            a = await send(ws, "r2", "run_code", {"src": "print(1)"})          # 허용 목록 밖 → 거부, 큐에 안 들어감
            assert a["ok"] is False and "not allowed" in a["reason"]
            a = await send(ws, "r3", "select_motor", {"motor_id": "M9"})       # 라이브러리에 없는 모터 → 거부
            assert a["ok"] is False and "library" in a["reason"]
            a = await send(ws, "r4", "inject_fault", {"fault": "no_such_fault", "on": True})
            assert a["ok"] is False and "fault" in a["reason"]
            a = await send(ws, "r5", "set_mode", {"mode": "thermal"})
            assert a["ok"] is False
            await ws.send("not json")
            a = await recv_until(ws, lambda m: m["type"] == "ack" and m["ok"] is False)
            assert "JSON" in a["reason"]
            assert b.poll_commands() == []                                     # 거부된 것은 메인 루프에 가지 않는다
            # 별칭 정규화: bearing → bearing_de_fault, 통과한 명령만 큐로
            await ws.send(json.dumps({"type": "command", "id": "ok1", "name": "inject_fault", "args": {"fault": "bearing"}}))
            cmds = await wait_commands(b)
            assert cmds and cmds[0]["args"] == {"fault": "bearing_de_fault", "on": True}
            await ws.send(json.dumps({"type": "command", "id": "ok2", "name": "play_scenario", "args": {"scene": "2"}}))
            cmds = await wait_commands(b)
            assert cmds and cmds[0]["args"]["scene"] == 2
            # select_motor (R3 자동 재시작): 라이브러리 모터면 통과해 메인 루프로 (재기동은 메인 루프가), 소문자도 정규화
            await ws.send(json.dumps({"type": "command", "id": "ok3", "name": "select_motor", "args": {"motor_id": "m1"}}))
            cmds = await wait_commands(b)
            assert cmds and cmds[0]["name"] == "select_motor" and cmds[0]["args"]["motor_id"] == "M1"
    asyncio.run(run())
    assert b.stats["rejected"] == 6
    b.stop()


def test_two_clients_both_get_ack_and_state():
    b = make_bridge()

    async def run():
        async with websockets.connect(f"ws://127.0.0.1:{b.port}") as a, websockets.connect(f"ws://127.0.0.1:{b.port}") as c:
            b.publish({"t_s": 5.0})
            sa = await recv_until(a, lambda m: m["type"] == "state"); sc = await recv_until(c, lambda m: m["type"] == "state")
            assert sa["host"]["clients"] == 2 == sc["host"]["clients"]
            await a.send(json.dumps({"type": "command", "id": "x", "name": "reset", "args": {}}))
            cmds = await wait_commands(b)
            b.ack(cmds[0], True, {"reset": True})
            await recv_until(a, lambda m: m["type"] == "ack" and m["id"] == "x")
            await recv_until(c, lambda m: m["type"] == "ack" and m["id"] == "x")      # 다른 클라이언트도 ack 를 받는다
    asyncio.run(run())
    b.stop()


def test_lan_ip_and_urls():
    ip = lan_ip()
    assert ip.count(".") == 3
    b = make_bridge()
    assert b.url == f"ws://{b.ip}:{b.port}" and b.dashboard_url.startswith(f"http://{b.ip}:{load('live')['dashboard']['port']}/#/status?live=ws://")
    b.stop()


def test_restart_args_keep_mode_and_live_drop_autoplay():
    import importlib.util
    # demo_integrated 는 Isaac 없이 import 할 수 없으므로 함수 소스만 떼어 실행한다
    src = open(os.path.join(VIZ, "app", "demo_integrated.py"), encoding="utf-8").read()
    i = src.index("def restart_args("); j = src.index("\n\n\n", i)
    ns: dict = {}; exec(src[i:j], ns)
    out = ns["restart_args"](["--gui", "--autoplay", "--mode", "integrated", "--live", "--live_port", "8766", "--motor", "M5", "--max_s", "90", "--low"], "M1")
    assert out == ["--gui", "--mode", "integrated", "--live", "--live_port", "8766", "--low", "--motor", "M1"]
    assert importlib.util.find_spec("websockets") is not None
