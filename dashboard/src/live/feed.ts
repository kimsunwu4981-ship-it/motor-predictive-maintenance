// live/feed.ts — Isaac Sim LiveBridge(app/live_bridge.py) 와의 WebSocket 연결 (TASK 실시간 §6 R2).
//
// 받는 것: state(10 Hz, 키 = demo CSV 컬럼, docs/live_r0_report.md §5) · heartbeat(1 Hz) · ack.
// 보내는 것: command {id, name, args} → ack 로 resolve. 허용 목록·범위는 Isaac 쪽 config/live.yaml 이 판단한다.
// 끊김: heartbeat_timeout_s 동안 아무 메시지도 없으면 status "lost" → 호출자(세션)가 녹화 모드로 폴백하고, reconnect_s 마다 다시 붙는다.
// 판정은 하지 않는다 — state.status(엔진 Judge 결과)를 그대로 쓴다 (§5.2).
import type { Stage } from "../data";
import { getYamlOptional } from "./load";

export type Level = "SAFE" | "WARN" | "DANGER";
export interface LiveCfg {
  default_url: string; heartbeat_timeout_s: number; reconnect_s: number; window_s: number; buffer_max_n: number;
  command_timeout_s: number; video_panel: "hint" | "snapshot" | "webrtc"; stream_port?: number;
  switch_why_hot?: string; switch_why_restart?: string; switch_compare?: string;
}
export const LIVE_CFG_DEFAULT: LiveCfg = {
  default_url: "ws://localhost:8765", heartbeat_timeout_s: 3, reconnect_s: 2, window_s: 300, buffer_max_n: 6000, command_timeout_s: 3, video_panel: "hint", stream_port: 8766,
};
let cfgPromise: Promise<LiveCfg> | null = null;
export function loadLiveCfg(): Promise<LiveCfg> {
  if (!cfgPromise) cfgPromise = getYamlOptional<Partial<LiveCfg>>("content/live.yaml", {}).then((c) => ({ ...LIVE_CFG_DEFAULT, ...c }));
  return cfgPromise;
}

export interface LiveScene { id: string; label: string; elapsed_s: number; duration_s: number; progress: number; total_elapsed_s: number; time_scale: number; playing: boolean }
export interface LiveStatus {
  status: Level; label: string; cause_signal: string; cause_component: string; value: number; threshold: string;
  levels: Record<string, Level>;                                        // kind → 가장 나쁜 등급 (+ bearing 종합)
  signals: { kind: string; component: string; level: Level; value: number }[];
}
export interface LiveState {
  type: "state"; schema: number; t_s: number; t_real_s: number; t_session_s: number; t_wall: number;
  motor_id: string; mode: "mechanical" | "electrical" | "integrated"; step: string; case: string; scene: LiveScene | null;
  faults: string[]; load: number; time_scale: number; slowmo: number; rpm: number;
  T: Record<string, number>; stage: Record<string, Stage>; loss_W?: Record<string, number>;
  Ia_rms: number; Ib_rms: number; Ic_rms: number; i2_over_i1: number; rated_line_A: number; current_status: string[];
  // TASK A D4/D5 (2026-10-17) 추가 — 없는 옛 스트림도 동작한다
  i2_over_in?: number | null;                 // I₂/I_n (electrical.yaml rated_current_A 기준, LUT 방식에서만) — 판정에 쓰지 않음
  p_loop_total_W?: number;                    // ITSC 단락 루프 총손실 (LUT) → 권선 추가 손실
  electrical_source?: ElecSource;             // 전류 신호 근거 배지
  i2i1_marks?: { case: string; label: string; value: number }[];   // 현재 방식의 게이지 눈금 (정상/4턴/12턴)
  vibration_mms: number; iso_zone: string; bearing_kurtosis: number; bearing_hf_ratio: number;
  status: LiveStatus;
  narration_key: { mode: string; scene: string | null; reveal: "why" | "visible" | "result" | null };
  perf: { fps: number | null; vram_mb?: number | null; ram_mb?: number | null; stream?: { clients: number; sent: number; encode_ms: number | null; capture_ms: number | null } | null };
  host: { ip: string; ws: string; clients: number };
  // 레이아웃 A (2026-10-27) 추가 — 케이스별 대칭 성분·2주기 파형 (app/live_signals.py, export case_signals 와 같은 식). 없는 옛 스트림도 동작한다
  sym_components_A?: { i1_A: number; i2_A: number; i0_A: number };
  waveform_last_2cycles?: { fs_Hz: number; f0_Hz: number; cycles: number; unit: string; t_ms: number[]; A: number[]; B: number[]; C: number[] };
}
export interface ElecSourceCase { key: string; label: string; method: "lut" | "legacy"; expected_i2i1: number | null; turns: number | null; R_f_ohm: number | null; load: number }
export interface ElecSource {
  method: "lut" | "legacy"; grade: string; status: string; fem_verified: boolean | string; lut_version: string | null; lut_sha256: string | null;   // string = 2D-eddy-lite 검증 범위 문구
  motor: string; base_turns_per_phase: number | null; inherent_i2i1: number; reason: string; rated_current_A: number | null;
  case?: string; case_method?: "lut" | "legacy"; expected_i2i1?: number | null; turns?: number; turn_frac?: number; R_f_ohm?: number; load_pct?: number;
  lut_i2_over_i1?: number; lut_i2_over_in?: number; lut_i2_angle_deg?: number; i_f_A?: number; p_loop_total_W?: number; clamped?: boolean;
  cases?: ElecSourceCase[];
}
export interface LiveAck { type: "ack"; id: string | null; name?: string; ok: boolean; applied?: Record<string, unknown>; reason?: string; t_wall: number }
export interface LiveHeartbeat { type: "heartbeat"; t_wall: number; clients: number; schema?: number }
export interface LiveHello {
  type: "hello"; schema: number; commands: Record<string, Record<string, unknown>>; motors: string[]; restart_eta_s: number; ws: string; t_wall: number;
  stream_ws?: string; stream?: { fps: number; size: number[]; quality: number; view: string };                 // 레이아웃 A: 뷰포트 스트림 주소·설정
  scenes?: { n: number; id: string; label: string; duration_s: number; electrical_case?: string; mode?: string }[];   // play_scenario {scene: n} 의 n 순서
}
export type FeedStatus = "off" | "connecting" | "live" | "lost";

export class LiveFeed {
  status: FeedStatus = "off";
  last: LiveState | null = null;
  hello: LiveHello | null = null;            // 접속 직후 Isaac 이 보내는 허용 명령·모터 목록 (config/live.yaml)
  lastMsgAt = 0;
  clients = 0;
  error = "";
  private ws: WebSocket | null = null;
  private timer: number | null = null;
  private reconnectAt = 0;
  private stopped = true;
  private pending = new Map<string, { resolve: (a: LiveAck) => void; timer: number }>();
  private onStateCbs = new Set<(s: LiveState) => void>();
  private onStatusCbs = new Set<(s: FeedStatus) => void>();
  private onAckCbs = new Set<(a: LiveAck) => void>();

  constructor(public url: string, public cfg: LiveCfg = LIVE_CFG_DEFAULT) {}

  onState(cb: (s: LiveState) => void) { this.onStateCbs.add(cb); return () => { this.onStateCbs.delete(cb); }; }
  onStatus(cb: (s: FeedStatus) => void) { this.onStatusCbs.add(cb); return () => { this.onStatusCbs.delete(cb); }; }
  onAck(cb: (a: LiveAck) => void) { this.onAckCbs.add(cb); return () => { this.onAckCbs.delete(cb); }; }

  start() {
    this.stopped = false;
    this.open();
    if (this.timer == null) this.timer = window.setInterval(() => this.tick(), 250);
  }
  stop() {
    this.stopped = true;
    if (this.timer != null) { clearInterval(this.timer); this.timer = null; }
    this.closeSocket();
    this.setStatus("off");
  }
  private setStatus(s: FeedStatus) {
    if (this.status === s) return;
    this.status = s;
    for (const cb of this.onStatusCbs) cb(s);
  }
  private open() {
    this.closeSocket();
    this.setStatus("connecting");
    try {
      const ws = new WebSocket(this.url);
      this.ws = ws;
      ws.onopen = () => { this.lastMsgAt = performance.now(); };
      ws.onmessage = (e) => this.onMessage(e);
      ws.onerror = () => { this.error = "연결 오류"; };
      ws.onclose = () => { if (this.ws === ws) { this.ws = null; if (!this.stopped) { this.setStatus("lost"); this.reconnectAt = performance.now() + this.cfg.reconnect_s * 1000; } } };
    } catch (e) {
      this.error = String(e);
      this.setStatus("lost");
      this.reconnectAt = performance.now() + this.cfg.reconnect_s * 1000;
    }
  }
  private closeSocket() {
    const ws = this.ws; this.ws = null;
    if (ws) { try { ws.onclose = null; ws.close(); } catch { /* */ } }
  }
  private tick() {
    const now = performance.now();
    if (this.status === "live" || this.status === "connecting") {
      if (this.ws && this.lastMsgAt && now - this.lastMsgAt > this.cfg.heartbeat_timeout_s * 1000) {   // 하트비트 끊김 (§1.3)
        this.closeSocket();
        this.setStatus("lost");
        this.reconnectAt = now + this.cfg.reconnect_s * 1000;
      } else if (this.status === "connecting" && !this.ws) {
        this.setStatus("lost"); this.reconnectAt = now + this.cfg.reconnect_s * 1000;
      }
    }
    if (this.status === "lost" && !this.stopped && now >= this.reconnectAt) this.open();
  }
  private onMessage(e: MessageEvent) {
    this.lastMsgAt = performance.now();
    let m: LiveState | LiveAck | LiveHeartbeat | LiveHello;
    try { m = JSON.parse(String(e.data)); } catch { return; }
    if (m.type === "hello") { this.hello = m; return; }
    if (m.type === "heartbeat") { this.clients = m.clients; this.setStatus("live"); return; }
    if (m.type === "state") {
      this.last = m; this.clients = m.host?.clients ?? this.clients; this.setStatus("live");
      for (const cb of this.onStateCbs) cb(m);
      return;
    }
    if (m.type === "ack") {
      const p = m.id ? this.pending.get(m.id) : undefined;
      if (p) { clearTimeout(p.timer); this.pending.delete(m.id!); p.resolve(m); }
      for (const cb of this.onAckCbs) cb(m);
    }
  }
  // 명령 → ack (허용 목록·범위는 Isaac 쪽이 판단). 연결이 없거나 시간 안에 ack 가 없으면 ok:false
  send(name: string, args: Record<string, unknown> = {}): Promise<LiveAck> {
    const id = (crypto as { randomUUID?: () => string }).randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const ws = this.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return Promise.resolve({ type: "ack", id, name, ok: false, reason: "라이브 연결 없음", t_wall: Date.now() / 1000 });
    return new Promise((resolve) => {
      const timer = window.setTimeout(() => { this.pending.delete(id); resolve({ type: "ack", id, name, ok: false, reason: `ack 없음 (${this.cfg.command_timeout_s} s)`, t_wall: Date.now() / 1000 }); }, this.cfg.command_timeout_s * 1000);
      this.pending.set(id, { resolve, timer });
      ws.send(JSON.stringify({ type: "command", id, name, args }));
    });
  }
}
