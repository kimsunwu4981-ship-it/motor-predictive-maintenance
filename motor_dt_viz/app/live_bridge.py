# -*- coding: utf-8 -*-
"""live_bridge.py — Isaac Sim 쪽 LiveBridge (TASK 실시간 §4 R1). Isaac Sim 비의존 (표준 threading + asyncio + websockets).

  bridge = LiveBridge().start()                 # config/live.yaml: 0.0.0.0:8765, state 10 Hz, heartbeat 1 Hz
  bridge.publish(state_dict)                    # 메인 루프: 매 프레임 (최신 것만 보관 — 백프레셔)
  for cmd in bridge.poll_commands():            # 메인 루프: 매 프레임 큐를 비우며 적용
      ok, info = apply(cmd); bridge.ack(cmd, ok, info)
  bridge.stop()

메인 루프와는 큐·락으로만 통신한다 (렌더 루프를 막지 않는다 — R0 프로토타입: FPS −3.4 %).
명령 검증(허용 목록·인자 범위)은 브리지 스레드에서 하고, 거부면 바로 ack(ok=false) 를 보낸다. 통과한 명령만 메인 루프 큐로 간다.
ack 는 보낸 클라이언트뿐 아니라 모든 클라이언트에 방송한다 (여러 화면이 같은 상태를 보도록 — 마지막 명령이 이긴다).
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.config_loader import load  # noqa: E402
from engine import motor_library as ml  # noqa: E402


def lan_ip() -> str:
    """이 PC 의 LAN IPv4 (기본 경로 인터페이스). UDP connect 는 패킷을 보내지 않는다. 실패하면 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def _vram_used_mb() -> float | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return float(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


class LiveBridge:
    def __init__(self, cfg: dict | None = None, port: int | None = None, log=print):
        self.cfg = cfg or load("live")
        s = self.cfg["server"]
        self.host = str(s.get("host", "0.0.0.0"))
        self.port = int(port or s["port"])
        self.state_hz = float(s.get("state_hz", 10))
        self.heartbeat_hz = float(s.get("heartbeat_hz", 1))
        self.perf_period_s = float(s.get("perf_period_s", 5))
        self.max_clients = int(s.get("max_clients", 8))
        self.commands = dict(self.cfg.get("commands") or {})
        self.schema = int(self.cfg.get("schema", 1))
        self.log = log
        self.ip = lan_ip()
        self._latest: dict | None = None
        self._latest_seq = 0
        self._sent_seq = -1
        self._lock = threading.Lock()
        self._cmd_q: queue.Queue = queue.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._out_q: asyncio.Queue | None = None
        self._thread: threading.Thread | None = None
        self._clients: set = set()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self.error: str | None = None
        self.perf: dict = {"vram_mb": None, "ram_mb": None}
        self.stats = {"sent": 0, "commands": 0, "rejected": 0, "heartbeats": 0}

    # ------------------------------------------------------------------ 수명
    def start(self) -> "LiveBridge":
        self._thread = threading.Thread(target=self._run, name="live_bridge", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10.0)
        if self.error:
            raise RuntimeError(f"LiveBridge 시작 실패: {self.error}")
        threading.Thread(target=self._perf_loop, name="live_perf", daemon=True).start()
        self.log(f"[live] WebSocket {self.url}  (bind {self.host}:{self.port}, state {self.state_hz:g} Hz, heartbeat {self.heartbeat_hz:g} Hz)")
        self.log(f"[live] dashboard  {self.dashboard_url}")
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(lambda: None)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    @property
    def clients(self) -> int:
        return len(self._clients)

    @property
    def url(self) -> str:
        return f"ws://{self.ip}:{self.port}"

    @property
    def dashboard_url(self) -> str:
        d = self.cfg.get("dashboard") or {}
        route = str(d.get("route", "#/status?live=ws://{ip}:{port}")).format(ip=self.ip, port=self.port)
        return f"http://{self.ip}:{int(d.get('port', 4173))}/{route}"

    # ------------------------------------------------------------------ 메인 루프 쪽 API
    def publish(self, state: dict) -> None:
        with self._lock:
            self._latest = state
            self._latest_seq += 1

    def poll_commands(self) -> list[dict]:
        out = []
        while True:
            try:
                out.append(self._cmd_q.get_nowait())
            except queue.Empty:
                return out

    def ack(self, cmd: dict, ok: bool, info=None) -> None:
        msg = {"type": "ack", "id": cmd.get("id"), "name": cmd.get("name"), "ok": bool(ok), "t_wall": time.time()}
        if ok:
            msg["applied"] = info if info is not None else {}
        else:
            msg["reason"] = str(info) if info is not None else "rejected"
            self.stats["rejected"] += 1
        self._send_threadsafe(msg)

    # ------------------------------------------------------------------ 명령 검증 (브리지 스레드)
    def validate(self, msg: dict) -> tuple[bool, str, dict]:
        """허용 목록·인자 범위 검사. (ok, reason, 정규화된 명령). 숫자는 config/live.yaml 에서만."""
        if msg.get("type") != "command":
            return False, "type must be 'command'", msg
        name = str(msg.get("name", ""))
        spec = self.commands.get(name)
        if spec is None:
            return False, f"command not allowed: {name}", msg
        args = dict(msg.get("args") or {})
        cmd = {"type": "command", "id": msg.get("id"), "name": name, "args": args}
        if spec.get("runtime") is False:
            return False, str(spec.get("reason", "not available at runtime")), cmd
        if name == "select_motor":                                   # runtime: restart — 모터 목록만 검사, 재기동은 메인 루프가
            mid = str(args.get("motor_id", "")).upper()
            if mid not in ml.list_ids():
                return False, f"motor_id not in library: {args.get('motor_id')} (allowed {', '.join(ml.list_ids())})", cmd
            args["motor_id"] = mid
            return True, "", cmd
        if name == "inject_fault":
            f = str(args.get("fault", ""))
            f = (spec.get("aliases") or {}).get(f, f)
            allowed = set(spec.get("thermal") or []) | set(spec.get("electrical") or [])
            if f not in allowed:
                return False, f"fault not allowed: {args.get('fault')}", cmd
            args["fault"] = f
            args["on"] = bool(args.get("on", True))
        elif name in ("set_load", "set_time_scale", "set_slowmo"):
            key = "pct" if name == "set_load" else "x"
            lo, hi = (float(x) for x in spec[key])
            try:
                v = float(args.get(key))
            except (TypeError, ValueError):
                return False, f"{key} missing or not a number", cmd
            if not (lo <= v <= hi):
                return False, f"{key} out of range {lo:g}~{hi:g}: {v:g}", cmd
            args[key] = v
        elif name == "set_mode":
            if args.get("mode") not in (spec.get("modes") or []):
                return False, f"mode not allowed: {args.get('mode')}", cmd
        elif name == "play_scenario":
            sc = args.get("scene")
            if sc is not None:
                try:
                    sc = int(sc)
                except (TypeError, ValueError):
                    return False, "scene must be an integer", cmd
                if sc < int(spec.get("scene_min", 1)):
                    return False, f"scene out of range: {sc}", cmd
                args["scene"] = sc
        return True, "", cmd

    # ------------------------------------------------------------------ 브리지 스레드
    def _send_threadsafe(self, msg: dict) -> None:
        if self._loop is None or self._out_q is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._out_q.put_nowait, msg)
        except RuntimeError:
            pass

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as e:                       # 시작 실패(포트 점유 등)
            self.error = f"{type(e).__name__}: {e}"
            self._ready.set()

    def hello(self) -> dict:
        """접속 직후 보내는 허용 명령 목록·모터 목록 (대시보드 제어 패널의 단일 출처 = config/live.yaml)."""
        return {"type": "hello", "schema": self.schema, "commands": self.commands, "motors": ml.list_ids(),
                "restart_eta_s": float((self.commands.get("select_motor") or {}).get("restart_eta_s", 45)), "ws": self.url, "t_wall": time.time()}

    async def _main(self) -> None:
        import websockets
        self._loop = asyncio.get_running_loop()
        self._out_q = asyncio.Queue()
        # 재기동 직후에는 이전 인스턴스가 아직 포트를 쥐고 있을 수 있다 → bind_retry_s 동안 1 s 간격으로 다시 시도
        deadline = time.time() + float((self.cfg.get("server") or {}).get("bind_retry_s", 0))
        while True:
            try:
                server = await websockets.serve(self._handler, self.host, self.port, ping_interval=20, ping_timeout=20, max_size=1 << 20)
                break
            except OSError as e:
                if time.time() >= deadline:
                    raise
                self.log(f"[live] port {self.port} busy ({e.errno}) - retrying")
                await asyncio.sleep(1.0)
        async with server:
            self._ready.set()
            tasks = [asyncio.create_task(self._broadcaster()), asyncio.create_task(self._heartbeat()), asyncio.create_task(self._sender())]
            try:
                while not self._stop.is_set():
                    await asyncio.sleep(0.05)
            finally:
                for t in tasks:
                    t.cancel()
                for c in list(self._clients):
                    try:
                        await c.close()
                    except Exception:
                        pass

    async def _handler(self, ws) -> None:
        if len(self._clients) >= self.max_clients:
            await ws.close(code=1013, reason="too many clients")
            return
        self._clients.add(ws)
        peer = getattr(ws, "remote_address", None)
        self.log(f"[live] client + {peer}  ({len(self._clients)})")
        await self._safe_send(ws, self.hello())
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    self.stats["rejected"] += 1
                    await self._safe_send(ws, {"type": "ack", "id": None, "ok": False, "reason": "invalid JSON"})
                    continue
                ok, reason, cmd = self.validate(msg if isinstance(msg, dict) else {})
                if not ok:
                    self.stats["rejected"] += 1
                    self.log(f"[live] 거부 {cmd.get('name')} {cmd.get('args')}: {reason}")
                    await self._safe_send(ws, {"type": "ack", "id": cmd.get("id"), "name": cmd.get("name"), "ok": False, "reason": reason, "t_wall": time.time()})
                    continue
                self.stats["commands"] += 1
                cmd["t_recv"] = time.time()
                self._cmd_q.put(cmd)                 # 메인 루프가 적용하고 ack()
        except Exception:
            pass
        finally:
            self._clients.discard(ws)
            self.log(f"[live] client - {peer}  ({len(self._clients)})")

    async def _safe_send(self, ws, msg: dict) -> None:
        try:
            await ws.send(json.dumps(msg, ensure_ascii=False))
        except Exception:
            self._clients.discard(ws)

    async def _broadcast(self, msg: dict) -> None:
        if not self._clients:
            return
        data = json.dumps(msg, ensure_ascii=False)
        for c in list(self._clients):
            try:
                await c.send(data)
            except Exception:
                self._clients.discard(c)

    async def _broadcaster(self) -> None:
        period = 1.0 / max(self.state_hz, 0.1)
        while True:
            await asyncio.sleep(period)
            with self._lock:
                st, seq = self._latest, self._latest_seq
            if st is None or seq == self._sent_seq or not self._clients:
                continue
            self._sent_seq = seq
            msg = dict(st)
            msg["type"] = "state"
            msg["schema"] = self.schema
            msg["t_wall"] = time.time()
            msg["host"] = {"ip": self.ip, "ws": self.url, "clients": len(self._clients)}
            perf = dict(msg.get("perf") or {})
            perf.update({k: v for k, v in self.perf.items() if v is not None})
            msg["perf"] = perf
            await self._broadcast(msg)
            self.stats["sent"] += 1

    async def _heartbeat(self) -> None:
        period = 1.0 / max(self.heartbeat_hz, 0.1)
        while True:
            await asyncio.sleep(period)
            await self._broadcast({"type": "heartbeat", "t_wall": time.time(), "clients": len(self._clients), "schema": self.schema})
            self.stats["heartbeats"] += 1

    async def _sender(self) -> None:
        while True:
            msg = await self._out_q.get()
            await self._broadcast(msg)

    def _perf_loop(self) -> None:
        try:
            import psutil
            proc = psutil.Process()
        except Exception:
            proc = None
        while not self._stop.is_set():
            if proc is not None:
                try:
                    self.perf["ram_mb"] = round(proc.memory_info().rss / 1048576)
                except Exception:
                    pass
            self.perf["vram_mb"] = _vram_used_mb()
            self._stop.wait(self.perf_period_s)
