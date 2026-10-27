# -*- coding: utf-8 -*-
"""stream_probe.py — 뷰포트 스트림(ws://127.0.0.1:8766)과 state(ws://…:8765)에 동시에 붙어 N 초 동안 측정한다 (레이아웃 A §A1 실측).

  py -3.12 -X utf8 tools/live/stream_probe.py --seconds 60 --out logs/stream_probe.json [--save_jpg logs/stream_last.jpg]

측정: 프레임 수·fps, 프레임 지연(수신 벽시계 − 헤더 캡처 벽시계, 같은 PC), 프레임 간격, 바이트, 끊김(5 s 무응답) 횟수,
      state 쪽 perf.fps(Isaac 렌더 FPS)·perf.stream(encode_ms·capture_ms·clients) 최소/중앙/최대. 10분 안정성은 --seconds 600.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, VIZ)
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)
import websockets  # noqa: E402

from viz.stream_viewport import parse_frame  # noqa: E402


def q(xs, f):
    return round(f(xs), 1) if xs else None


async def connect_retry(url: str, deadline_s: float):
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            return await websockets.connect(url, ping_interval=None, max_size=1 << 24)
        except Exception:
            await asyncio.sleep(1.0)
    return None


async def probe_stream(url: str, seconds: float, res: dict, save_jpg: str) -> None:
    ws = await connect_retry(url, 300)
    if ws is None:
        res["stream_error"] = f"connect failed {url}"; return
    t0 = time.time(); last = None
    lat, gaps, sizes, sess = [], [], [], []
    n = 0; hello = None; lost = 0; last_jpg = None; n_per_sec = {}
    while time.time() - t0 < seconds:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            lost += 1; print(f"[probe] stream 5 s 무응답 ({lost})", flush=True); continue
        except Exception as e:
            res["stream_error"] = f"recv: {e}"; break
        now = time.time()
        if isinstance(msg, str):
            hello = json.loads(msg); continue
        hdr, jpg = parse_frame(msg)
        n += 1; sizes.append(len(msg)); lat.append((now - hdr["t_wall"]) * 1000); sess.append(hdr["t_session_s"])
        n_per_sec[int(now - t0)] = n_per_sec.get(int(now - t0), 0) + 1
        if last is not None:
            gaps.append((now - last) * 1000)
        last = now; last_jpg = jpg
    dur = time.time() - t0
    res["stream"] = {"url": url, "hello": hello, "seconds": round(dur, 1), "frames": n, "fps": round(n / max(dur, 1e-6), 2),
                     "fps_per_sec_min": min(n_per_sec.values()) if n_per_sec else None, "fps_per_sec_max": max(n_per_sec.values()) if n_per_sec else None,
                     "latency_ms_p50": q(lat, statistics.median), "latency_ms_p95": q(sorted(lat), lambda a: a[int(len(a) * 0.95) - 1]) if len(lat) > 20 else q(lat, max), "latency_ms_max": q(lat, max),
                     "gap_ms_p50": q(gaps, statistics.median), "gap_ms_max": q(gaps, max),
                     "bytes_p50": int(statistics.median(sizes)) if sizes else None, "kbps": round(sum(sizes) * 8 / max(dur, 1e-6) / 1000) if sizes else None,
                     "timeouts_5s": lost, "t_session_first": sess[0] if sess else None, "t_session_last": sess[-1] if sess else None}
    if save_jpg and last_jpg:
        os.makedirs(os.path.dirname(os.path.abspath(save_jpg)) or ".", exist_ok=True)
        open(save_jpg, "wb").write(last_jpg); res["stream"]["saved_jpg"] = save_jpg
    await ws.close()


async def probe_state(url: str, seconds: float, res: dict) -> None:
    ws = await connect_retry(url, 300)
    if ws is None:
        res["state_error"] = f"connect failed {url}"; return
    t0 = time.time(); fps, enc, cap, clients, lat, n = [], [], [], [], [], 0
    hello = None; cases = {}; has_wave = False; sym_last = None
    while time.time() - t0 < seconds:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            res["state_error"] = f"recv: {e}"; break
        m = json.loads(msg)
        if m.get("type") == "hello":
            hello = {k: m.get(k) for k in ("schema", "ws", "stream_ws", "motors")}
        elif m.get("type") == "state":
            n += 1; lat.append((time.time() - m["t_wall"]) * 1000) if "t_wall" in m else None
            p = m.get("perf") or {}
            if p.get("fps"):
                fps.append(p["fps"])
            st = p.get("stream") or {}
            if st.get("encode_ms") is not None:
                enc.append(st["encode_ms"])
            if st.get("capture_ms") is not None:
                cap.append(st["capture_ms"])
            if st.get("clients") is not None:
                clients.append(st["clients"])
            c = m.get("case"); cases[c] = cases.get(c, 0) + 1
            if m.get("waveform_last_2cycles"):
                has_wave = True; sym_last = m.get("sym_components_A")
    res["state"] = {"url": url, "hello": hello, "states": n, "rate_hz": round(n / max(time.time() - t0, 1e-6), 2),
                    "isaac_fps_min": q(fps, min), "isaac_fps_p50": q(fps, statistics.median), "isaac_fps_max": q(fps, max),
                    "encode_ms_p50": q(enc, statistics.median), "encode_ms_max": q(enc, max), "capture_ms_p50": q(cap, statistics.median), "capture_ms_max": q(cap, max),
                    "stream_clients_max": max(clients) if clients else None, "cases_seen": cases, "has_waveform_field": has_wave, "sym_components_last": sym_last}
    await ws.close()


async def main(a):
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": a.seconds}
    tasks = [probe_state(a.state, a.seconds, res)]
    if a.stream and a.stream != "none":                       # --stream none: state 만 (스트림 클라이언트 없는 기준 FPS 측정)
        tasks.append(probe_stream(a.stream, a.seconds, res, a.save_jpg))
    await asyncio.gather(*tasks)
    print("[probe] " + json.dumps(res, ensure_ascii=False), flush=True)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", default="ws://127.0.0.1:8766")
    ap.add_argument("--state", default="ws://127.0.0.1:8765")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--save_jpg", default="")
    asyncio.run(main(ap.parse_args()))
