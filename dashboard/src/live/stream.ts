// live/stream.ts — Isaac 뷰포트 JPEG 스트림 수신 (레이아웃 A §A1, 2026-10-27). 송출은 motor_dt_viz/viz/stream_viewport.py.
//
//   const st = useViewportStream(url, canvasRef);     // url 없으면 off
//   st.status: off | connecting | live | lost          st.fps / st.latencyMs(수신 벽시계 − 캡처 벽시계, 같은 PC) / st.frames / st.size
// 프레임 = 32 B 헤더(<4sddIII: "VGF1", t_wall, t_session_s, w, h, seq) + JPEG. createImageBitmap 으로 비동기 디코딩해 <canvas> 에 그린다.
// 끊김: lost_after_s 동안 프레임이 없으면 lost → reconnect_s 마다 재접속. 명령은 보내지 않는다 (명령은 8765 LiveBridge).
import { useEffect, useRef, useState, type RefObject } from "react";

export type StreamStatus = "off" | "connecting" | "live" | "lost";
export interface StreamStats { status: StreamStatus; fps: number; latencyMs: number | null; frames: number; size: [number, number] | null; bytes: number; hello: Record<string, unknown> | null; tSession: number | null }
const HEADER_BYTES = 32;
const LOST_AFTER_S = 3, RECONNECT_S = 2;

export function useViewportStream(url: string | null, canvas: RefObject<HTMLCanvasElement>): StreamStats {
  const [stats, setStats] = useState<StreamStats>({ status: url ? "connecting" : "off", fps: 0, latencyMs: null, frames: 0, size: null, bytes: 0, hello: null, tSession: null });
  const ref = useRef({ frames: 0, lastAt: 0, win: [] as number[], lat: [] as number[], bytes: 0, size: null as [number, number] | null, hello: null as Record<string, unknown> | null, tSession: null as number | null, busy: false, pending: null as ArrayBuffer | null });
  useEffect(() => {
    if (!url) { setStats((s) => ({ ...s, status: "off" })); return; }
    let ws: WebSocket | null = null, stopped = false, reconnectAt = 0;
    const r = ref.current;
    r.frames = 0; r.win = []; r.lat = []; r.bytes = 0;
    let status: StreamStatus = "connecting";
    const setStatus = (s: StreamStatus) => { status = s; };

    const draw = async (buf: ArrayBuffer) => {
      // 디코딩 중 새 프레임이 오면 마지막 것만 남긴다 (적체 없음)
      if (r.busy) { r.pending = buf; return; }
      r.busy = true;
      try {
        const dv = new DataView(buf);
        if (dv.getUint8(0) !== 0x56 || dv.getUint8(1) !== 0x47) return;                 // "VG"
        const tWall = dv.getFloat64(4, true), tSession = dv.getFloat64(12, true);
        const w = dv.getUint32(20, true), h = dv.getUint32(24, true);
        const bmp = await createImageBitmap(new Blob([buf.slice(HEADER_BYTES)], { type: "image/jpeg" }));
        const c = canvas.current;
        if (c) {
          if (c.width !== bmp.width || c.height !== bmp.height) { c.width = bmp.width; c.height = bmp.height; }
          c.getContext("2d")?.drawImage(bmp, 0, 0);
        }
        bmp.close();
        const now = performance.now();
        r.frames += 1; r.bytes = buf.byteLength; r.size = [w, h]; r.tSession = tSession; r.lastAt = now;
        r.win.push(now); while (r.win.length && now - r.win[0] > 2000) r.win.shift();
        r.lat.push(Date.now() / 1000 - tWall); if (r.lat.length > 30) r.lat.shift();
        if (status !== "live") setStatus("live");
      } finally {
        r.busy = false;
        const p = r.pending; r.pending = null;
        if (p) void draw(p);
      }
    };
    const open = () => {
      try {
        ws = new WebSocket(url);
        ws.binaryType = "arraybuffer";
        setStatus("connecting");
        ws.onmessage = (e) => {
          if (typeof e.data === "string") { try { r.hello = JSON.parse(e.data); } catch { /* */ } return; }
          void draw(e.data as ArrayBuffer);
        };
        ws.onclose = () => { if (!stopped) { setStatus("lost"); reconnectAt = performance.now() + RECONNECT_S * 1000; } };
        ws.onerror = () => { /* onclose 가 따라온다 */ };
      } catch { setStatus("lost"); reconnectAt = performance.now() + RECONNECT_S * 1000; }
    };
    open();
    const timer = window.setInterval(() => {
      const now = performance.now();
      if (status === "live" && now - r.lastAt > LOST_AFTER_S * 1000) { setStatus("lost"); try { ws?.close(); } catch { /* */ } ws = null; reconnectAt = now + RECONNECT_S * 1000; }
      if (status === "lost" && !ws && now >= reconnectAt) open();
      const fps = r.win.length >= 2 ? (r.win.length - 1) / ((r.win[r.win.length - 1] - r.win[0]) / 1000) : (r.win.length ? 1 : 0);
      const lat = r.lat.length ? r.lat.slice().sort((a, b) => a - b)[Math.floor(r.lat.length / 2)] * 1000 : null;
      setStats({ status, fps: Math.round(fps * 10) / 10, latencyMs: lat === null ? null : Math.round(lat), frames: r.frames, size: r.size, bytes: r.bytes, hello: r.hello, tSession: r.tSession });
    }, 500);
    return () => { stopped = true; clearInterval(timer); try { ws?.close(); } catch { /* */ } ws = null; };
  }, [url, canvas]);
  return stats;
}

// 스트림 주소: LiveBridge hello 의 stream_ws (Isaac 이 알려줌) → 없으면 state 주소의 포트만 stream_port 로 바꾼다
export function streamUrlFor(stateUrl: string, helloStreamWs: string | null | undefined, streamPort: number): string {
  if (helloStreamWs) {
    try {                                                    // 송출은 127.0.0.1 에 묶여 있으므로 대시보드가 다른 PC 면 host 를 state 주소의 host 로
      const h = new URL(helloStreamWs), s = new URL(stateUrl);
      if (h.hostname === "127.0.0.1" && s.hostname !== "127.0.0.1" && s.hostname !== "localhost") h.hostname = s.hostname;
      return h.toString().replace(/\/$/, "");
    } catch { return helloStreamWs; }
  }
  try { const u = new URL(stateUrl); u.port = String(streamPort); return u.toString().replace(/\/$/, ""); } catch { return `ws://127.0.0.1:${streamPort}`; }
}
