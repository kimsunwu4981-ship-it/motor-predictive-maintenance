# -*- coding: utf-8 -*-
"""stream_viewport.py — Isaac Sim 뷰포트를 JPEG 로 WebSocket 바이너리 프레임으로 송출한다 (TASK 레이아웃 A §A1, 2026-10-27).

  streamer = ViewportStreamer(port=8766).start()          # config/live.yaml server.stream_port, 127.0.0.1 바인딩(인증 없음 → 방화벽 열지 않음)
  streamer.tick(viewport_api, t_session)                  # 메인 루프 매 프레임: fps 간격마다 다음 프레임 캡처를 예약 (클라이언트가 없으면 아무 것도 안 함)
  streamer.stop()

경로: omni.kit.viewport.utility.capture_viewport_to_buffer(RGBA8 readback, 추가 렌더 없음) → 메인 스레드 콜백은 numpy 복사만(≈1 ms)
      → 인코더 스레드(cv2 리사이즈·JPEG, 품질 80) → asyncio 서버 스레드가 모든 클라이언트에 바이너리 방송. 한 칸 슬롯이라 느린 쪽은 오래된 프레임을 버린다(적체 없음).
프레임 = 32 B 헤더(<4sddIII: b"VGF1", 캡처 벽시계 time.time(), t_session_s, w, h, seq) + JPEG. 접속 직후 JSON hello 한 줄
  {"type":"hello","stream":"jpeg","fps":30,"size":[1280,720],"quality":80,"header_bytes":32}. 수신 쪽은 (수신 시각 − 헤더 벽시계)로 지연을 바로 잰다(같은 PC).
Isaac 비의존: push_frame() 으로 아무 numpy 프레임을 넣을 수 있어 테스트는 Isaac 없이 돈다 (tests/test_stream_viewport.py).
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import struct
import threading
import time

import numpy as np

MAGIC = b"VGF1"
HEADER = struct.Struct("<4sddIII")          # magic, t_wall, t_session, width, height, seq  → 32 B
assert HEADER.size == 32


def buffer_to_array(buffer, buffer_size: int, width: int, height: int) -> np.ndarray:
    """캡처 콜백의 버퍼(버퍼 프로토콜 객체 또는 PyCapsule 포인터) → (h, w, ch) uint8 **복사본**. 행 패딩이 있으면 잘라낸다."""
    try:
        data = np.frombuffer(memoryview(buffer), dtype=np.uint8, count=int(buffer_size))
    except TypeError:
        ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
        ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
        ptr = ctypes.pythonapi.PyCapsule_GetPointer(buffer, None)
        data = np.ctypeslib.as_array(ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint8 * int(buffer_size))).contents)
    h, w = int(height), int(width)
    stride = int(buffer_size) // h                   # 행 바이트 (패딩 포함)
    ch = 4 if stride >= 4 * w else (3 if stride >= 3 * w else 1)   # RGBA8 기본 — 패딩은 채널 수가 아니라 행 끝에 붙는다
    return data[: stride * h].reshape(h, stride)[:, : w * ch].reshape(h, w, ch).copy()


class ViewportStreamer:
    def __init__(self, port: int, host: str = "127.0.0.1", fps: float = 30.0, size=(1280, 720), quality: int = 80,
                 max_clients: int = 8, log=print):
        self.host, self.port = str(host), int(port)
        self.fps = float(fps)
        self.size = (int(size[0]), int(size[1])) if size else None
        self.quality = int(quality)
        self.max_clients = int(max_clients)
        self.log = log
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._out_q: asyncio.Queue | None = None
        self._thread: threading.Thread | None = None
        self._enc_thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._slot_lock = threading.Lock()
        self._slot_ev = threading.Event()
        self._slot: tuple | None = None            # (meta, array, fmt_name)
        self._inflight = 0                          # 예약했지만 콜백이 아직 안 온 캡처 수 (readback ≈ 1 프레임이라 2개까지 겹쳐 30 fps 를 채운다)
        self._inflight_max = 3
        self._inflight_since = 0.0
        self._last_sched = 0.0
        self._next_due = 0.0                        # 누적 예약 시각 — 렌더 프레임 격자(예: 21 ms)에 양자화되지 않도록 1·2 프레임 간격을 섞어 평균 fps 를 맞춘다
        self._seq = 0
        self.error: str | None = None
        self._capture_warned = False
        self.stats = {"scheduled": 0, "captured": 0, "encoded": 0, "sent": 0, "dropped": 0, "clients_max": 0,
                      "encode_ms": None, "capture_ms": None, "bytes_last": 0, "format": None, "src_size": None}

    # ------------------------------------------------------------------ 수명
    def start(self) -> "ViewportStreamer":
        self._thread = threading.Thread(target=self._run, name="viewport_stream", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10.0)
        if self.error:
            raise RuntimeError(f"ViewportStreamer 시작 실패: {self.error}")
        self._enc_thread = threading.Thread(target=self._encoder, name="viewport_stream_enc", daemon=True)
        self._enc_thread.start()
        self.log(f"[stream] viewport JPEG {self.url}  ({self.fps:g} fps, {self.size[0]}x{self.size[1]} q{self.quality}, bind {self.host} only)")
        return self

    def stop(self) -> None:
        self._stop.set()
        self._slot_ev.set()
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(lambda: None)
            except Exception:
                pass
        for t in (self._enc_thread, self._thread):
            if t is not None:
                t.join(timeout=5.0)

    @property
    def clients(self) -> int:
        return len(self._clients)

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    def hello(self) -> dict:
        return {"type": "hello", "stream": "jpeg", "fps": self.fps, "size": list(self.size) if self.size else None,
                "quality": self.quality, "header_bytes": HEADER.size, "t_wall": time.time()}

    # ------------------------------------------------------------------ 메인 루프 쪽 API
    def tick(self, viewport_api, t_session: float) -> None:
        """매 프레임 호출. 클라이언트가 있고 fps 간격이 지났고 앞 캡처가 끝났으면 다음 프레임 캡처를 예약한다(예약은 수 µs)."""
        if not self._clients or viewport_api is None:
            return
        now = time.perf_counter()
        if self._inflight >= self._inflight_max:
            if now - self._inflight_since > 2.0:             # 콜백이 오지 않으면(뷰포트 숨김 등) 2 s 뒤 다시 시도
                self._inflight = 0
            else:
                return
        period = 1.0 / max(self.fps, 1e-3)
        if now < self._next_due:
            return
        self._next_due = max(self._next_due + period, now - period)      # 밀린 만큼은 따라잡되 한 주기 넘게 빚지지 않는다
        self._last_sched = now
        meta = (time.time(), float(t_session), self._seq, now)
        self._seq += 1
        try:
            from omni.kit.viewport.utility import capture_viewport_to_buffer
            self._inflight += 1
            self._inflight_since = now
            capture_viewport_to_buffer(viewport_api, lambda *a, _m=meta: self._on_capture(_m, *a))
            self.stats["scheduled"] += 1
        except Exception as e:  # noqa: BLE001
            self._inflight = max(self._inflight - 1, 0)
            if not self._capture_warned:
                self._capture_warned = True
                self.log(f"[stream] capture schedule failed: {e}")

    def _on_capture(self, meta, buffer, buffer_size, width, height, byte_format) -> None:
        """캡처 콜백(메인 스레드): 복사만 하고 인코더에 넘긴다."""
        self._inflight = max(self._inflight - 1, 0)
        try:
            arr = buffer_to_array(buffer, buffer_size, width, height)
        except Exception as e:  # noqa: BLE001
            if not self._capture_warned:
                self._capture_warned = True
                self.log(f"[stream] capture buffer read failed: {e}")
            return
        self.stats["capture_ms"] = round((time.perf_counter() - meta[3]) * 1000, 1)
        self.push_frame(arr, t_wall=meta[0], t_session=meta[1], seq=meta[2], fmt_name=str(byte_format))

    def push_frame(self, arr: np.ndarray, t_wall: float | None = None, t_session: float = 0.0, seq: int | None = None, fmt_name: str = "") -> None:
        """(h, w, 3|4) uint8 프레임을 인코더에 넘긴다 (테스트·다른 소스용). 슬롯이 차 있으면 오래된 것을 버린다."""
        if seq is None:
            seq = self._seq
            self._seq += 1
        meta = (time.time() if t_wall is None else float(t_wall), float(t_session), int(seq))
        with self._slot_lock:
            if self._slot is not None:
                self.stats["dropped"] += 1
            self._slot = (meta, arr, fmt_name)
            self.stats["captured"] += 1
            self.stats["format"] = fmt_name or self.stats["format"]
            self.stats["src_size"] = [int(arr.shape[1]), int(arr.shape[0])]
        self._slot_ev.set()

    # ------------------------------------------------------------------ 인코더 스레드
    def encode(self, arr: np.ndarray, fmt_name: str = "") -> bytes:
        """(h, w, 3|4) uint8 → JPEG bytes. cv2 가 있으면 cv2(빠름, Isaac 파이썬), 없으면 PIL."""
        ch = arr.shape[2] if arr.ndim == 3 else 1
        bgr_order = "B8G8R8" in (fmt_name or "")
        try:
            import cv2
        except ImportError:
            cv2 = None
        if cv2 is not None:
            if ch == 4:
                img = arr[:, :, :3] if bgr_order else cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            elif ch == 3:
                img = arr if bgr_order else cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            else:
                img = arr
            if self.size and (img.shape[1], img.shape[0]) != self.size:
                img = cv2.resize(img, self.size, interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", np.ascontiguousarray(img), [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
            if not ok:
                raise RuntimeError("cv2.imencode failed")
            return buf.tobytes()
        import io
        from PIL import Image
        rgb = arr[:, :, :3]
        if bgr_order:
            rgb = rgb[:, :, ::-1]
        im = Image.fromarray(np.ascontiguousarray(rgb), "RGB") if ch >= 3 else Image.fromarray(arr.reshape(arr.shape[0], arr.shape[1]), "L")
        if self.size and im.size != self.size:
            im = im.resize(self.size, Image.BILINEAR)
        bio = io.BytesIO()
        im.save(bio, "JPEG", quality=self.quality)
        return bio.getvalue()

    def _encoder(self) -> None:
        while not self._stop.is_set():
            self._slot_ev.wait(timeout=0.5)
            self._slot_ev.clear()
            with self._slot_lock:
                item, self._slot = self._slot, None
            if item is None or not self._clients:
                continue
            meta, arr, fmt_name = item
            try:
                t0 = time.perf_counter()
                jpg = self.encode(arr, fmt_name)
                w, h = (self.size if self.size else (arr.shape[1], arr.shape[0]))
                frame = HEADER.pack(MAGIC, meta[0], meta[1], int(w), int(h), int(meta[2]) & 0xFFFFFFFF) + jpg
                ms = (time.perf_counter() - t0) * 1000
                self.stats["encode_ms"] = round(ms if self.stats["encode_ms"] is None else 0.9 * self.stats["encode_ms"] + 0.1 * ms, 1)
                self.stats["encoded"] += 1
                self.stats["bytes_last"] = len(frame)
                if self._loop is not None and self._out_q is not None:
                    self._loop.call_soon_threadsafe(self._out_q.put_nowait, frame)
            except Exception as e:  # noqa: BLE001
                if not self._capture_warned:
                    self._capture_warned = True
                    self.log(f"[stream] encode failed: {e}")

    # ------------------------------------------------------------------ 서버 스레드
    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            self._ready.set()

    async def _main(self) -> None:
        import websockets
        self._loop = asyncio.get_running_loop()
        self._out_q = asyncio.Queue()
        server = None
        try:
            server = await websockets.serve(self._handler, self.host, self.port, ping_interval=20, ping_timeout=20, max_size=1 << 16, compression=None)
        except OSError as e:
            self.error = f"bind {self.host}:{self.port}: {e}"
            self._ready.set()
            return
        self._ready.set()
        sender = asyncio.create_task(self._sender())
        try:
            while not self._stop.is_set():
                await asyncio.sleep(0.05)
        finally:
            sender.cancel()
            server.close()
            await server.wait_closed()

    async def _handler(self, ws) -> None:
        if len(self._clients) >= self.max_clients:
            await ws.close(code=1013, reason="too many clients")
            return
        self._clients.add(ws)
        self.stats["clients_max"] = max(self.stats["clients_max"], len(self._clients))
        peer = getattr(ws, "remote_address", None)
        self.log(f"[stream] client + {peer}  ({len(self._clients)})")
        try:
            await ws.send(json.dumps(self.hello()))
            async for _ in ws:                     # 받는 명령은 없다 (명령은 8765 LiveBridge 로) — 읽어서 버린다
                pass
        except Exception:
            pass
        finally:
            self._clients.discard(ws)
            self.log(f"[stream] client - {peer}  ({len(self._clients)})")

    async def _sender(self) -> None:
        while True:
            frame = await self._out_q.get()
            while not self._out_q.empty():           # 적체되면 최신 것만 보낸다
                frame = self._out_q.get_nowait()
                self.stats["dropped"] += 1
            for c in list(self._clients):
                try:
                    await c.send(frame)
                    self.stats["sent"] += 1
                except Exception:
                    self._clients.discard(c)


def parse_frame(data: bytes) -> tuple[dict, bytes]:
    """수신 쪽 보조: 바이너리 프레임 → (헤더 dict, JPEG bytes). 테스트·probe 가 쓴다."""
    magic, t_wall, t_session, w, h, seq = HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError("bad magic")
    return {"t_wall": t_wall, "t_session_s": t_session, "width": w, "height": h, "seq": seq}, data[HEADER.size:]
