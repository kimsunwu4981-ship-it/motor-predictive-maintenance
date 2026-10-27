# -*- coding: utf-8 -*-
"""ViewportStreamer (viz/stream_viewport.py) — Isaac 없이: 프레임 push → WebSocket 클라이언트가 hello + 32 B 헤더 + JPEG 를 받는다. 지연·드롭·버퍼 변환."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import time

import numpy as np
import pytest

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, VIZ)
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

websockets = pytest.importorskip("websockets")
from viz.stream_viewport import HEADER, MAGIC, ViewportStreamer, buffer_to_array, parse_frame  # noqa: E402


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def frame(w=320, h=180, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, 0] = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    img[:, :, 1] = rng.integers(0, 255, (h, w), dtype=np.uint8)
    img[:, :, 3] = 255
    return img


def test_buffer_to_array_strips_row_padding_and_copies():
    h, w, stride = 4, 6, 32                      # 6 px × 4 ch = 24 B, 행 패딩 8 B
    raw = bytearray(stride * h)
    for y in range(h):
        for x in range(w):
            raw[y * stride + x * 4: y * stride + x * 4 + 4] = bytes([x, y, 7, 255])
    arr = buffer_to_array(raw, len(raw), w, h)
    assert arr.shape == (h, w, 4)
    assert arr[2, 5].tolist() == [5, 2, 7, 255]
    raw[0] = 99
    assert arr[0, 0, 0] == 0                     # 복사본


def test_header_is_32_bytes_and_roundtrips():
    s = ViewportStreamer(port=free_port(), size=(160, 90), quality=70, log=lambda *a, **k: None)
    jpg = s.encode(frame(), "R8G8B8A8_UNORM")
    data = HEADER.pack(MAGIC, 1.5, 2.5, 160, 90, 7) + jpg
    hdr, body = parse_frame(data)
    assert hdr == {"t_wall": 1.5, "t_session_s": 2.5, "width": 160, "height": 90, "seq": 7}
    import io
    from PIL import Image
    assert Image.open(io.BytesIO(body)).size == (160, 90)        # 리사이즈 반영


def test_push_frames_to_client_with_latency_and_drop_of_stale():
    s = ViewportStreamer(port=free_port(), fps=30, size=(320, 180), log=lambda *a, **k: None).start()
    try:
        async def run():
            async with websockets.connect(s.url, ping_interval=None) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), 3))
                assert hello["type"] == "hello" and hello["stream"] == "jpeg" and hello["header_bytes"] == 32
                for _ in range(50):                            # 클라이언트 등록을 기다린다
                    if s.clients:
                        break
                    await asyncio.sleep(0.02)
                assert s.clients == 1
                got = []
                for k in range(5):
                    s.push_frame(frame(seed=k), t_session=10.0 + k, seq=k)
                    data = await asyncio.wait_for(ws.recv(), 3)
                    assert isinstance(data, (bytes, bytearray))
                    hdr, body = parse_frame(data)
                    got.append(hdr)
                    assert body[:2] == b"\xff\xd8"           # JPEG SOI
                    assert (time.time() - hdr["t_wall"]) < 1.0
                assert [g["seq"] for g in got] == [0, 1, 2, 3, 4]
                assert got[0]["width"] == 320 and got[0]["height"] == 180
                # 한꺼번에 밀어 넣으면 오래된 프레임은 버린다 (슬롯 1칸 또는 송신 큐 압축)
                for k in range(20):
                    s.push_frame(frame(seed=k), seq=100 + k)
                await asyncio.sleep(0.5)
                n = 0
                try:
                    while True:
                        await asyncio.wait_for(ws.recv(), 0.3); n += 1
                except asyncio.TimeoutError:
                    pass
                assert 1 <= n < 20
                assert s.stats["dropped"] >= 1
        asyncio.run(run())
        assert s.stats["sent"] >= 5 and s.stats["encode_ms"] is not None
    finally:
        s.stop()


def test_no_client_means_no_encode():
    s = ViewportStreamer(port=free_port(), log=lambda *a, **k: None).start()
    try:
        s.push_frame(frame())
        time.sleep(0.3)
        assert s.stats["encoded"] == 0 and s.stats["sent"] == 0
        assert s.hello()["size"] == [1280, 720]
    finally:
        s.stop()
