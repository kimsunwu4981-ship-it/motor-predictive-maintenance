// live/session.ts — 라이브 세션 훅 (TASK 실시간 §6): 녹화/LIVE 토글 상태, 주소(마지막 값 기억), 피드, 수신 버퍼, 폴백.
//
//   const live = useLiveSession();
//   live.active          → LIVE 가 켜져 있고 연결이 살아 있다 (이때만 라이브 데이터를 쓴다; 끊기면 자동으로 녹화 데이터)
//   live.buffer / live.version → 최근 window_s 의 state 목록 (version 은 state 마다 1 증가 — useMemo 의존성)
//   live.send(name, args) → 명령 (R3 제어 패널)
// 세 화면(#/status, #/mechanical, #/electrical)이 같은 훅을 쓴다. 토글은 localStorage(vigent-live)로 공유된다.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LIVE_CFG_DEFAULT, LiveFeed, loadLiveCfg, type FeedStatus, type LiveAck, type LiveCfg, type LiveHello, type LiveState } from "./feed";

const KEY = "vigent-live";
interface Saved { enabled: boolean; url: string }
function loadSaved(): Saved {
  const q = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("live");
  let s: Saved = { enabled: false, url: "" };
  try { s = { ...s, ...(JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Saved>) }; } catch { /* */ }
  if (q && q.startsWith("ws")) s = { enabled: true, url: q };          // #/status?live=ws://host:8765 → 바로 LIVE
  return s;
}
function save(s: Saved) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* */ } }

export class LiveBuffer {
  states: LiveState[] = [];
  t: number[] = [];                       // t_session_s (단조 증가)
  constructor(public windowS: number, public maxN: number) {}
  push(s: LiveState) {
    if (this.t.length && s.t_session_s < this.t[this.t.length - 1] - 1e-6) { this.states = []; this.t = []; }   // Isaac 재시작 → 버퍼 비움
    this.states.push(s); this.t.push(s.t_session_s);
    const tMin = s.t_session_s - this.windowS;
    let cut = 0;
    while (cut < this.t.length - 1 && (this.t[cut] < tMin || this.t.length - cut > this.maxN)) cut++;
    if (cut) { this.states = this.states.slice(cut); this.t = this.t.slice(cut); }
  }
  get last(): LiveState | null { return this.states[this.states.length - 1] ?? null; }
  get tEnd(): number { return this.t[this.t.length - 1] ?? 0; }
  get tMin(): number { return Math.max(this.t[0] ?? 0, this.tEnd - this.windowS); }
  clear() { this.states = []; this.t = []; }
}

export interface LiveSession {
  cfg: LiveCfg;
  enabled: boolean; setEnabled: (on: boolean) => void;
  url: string; setUrl: (u: string) => void;
  status: FeedStatus;                    // off | connecting | live | lost
  active: boolean;                       // enabled && status === "live" && 버퍼에 샘플 2개 이상
  fallback: boolean;                     // enabled 인데 끊겨서 녹화 데이터를 보여주는 중 (노란 띠)
  buffer: LiveBuffer; version: number; last: LiveState | null; clients: number;
  send: (name: string, args?: Record<string, unknown>) => Promise<LiveAck>;
  lastAck: LiveAck | null;
  hello: LiveHello | null;               // 허용 명령·모터 목록 (제어 패널)
  restarting: { motor_id: string; from: string; eta_s: number; at: number; hot: boolean; switch_ms?: number; from_summary: string; arrived: boolean } | null;   // select_motor 뒤 전환 안내 (hot: 재기동 없음, 최소 eta_s 동안 안내 띠)
}

export function useLiveSession(): LiveSession {
  const [cfg, setCfg] = useState<LiveCfg>(LIVE_CFG_DEFAULT);
  const [saved, setSaved] = useState<Saved>(() => loadSaved());
  const [status, setStatus] = useState<FeedStatus>("off");
  const [version, setVersion] = useState(0);
  const [lastAck, setLastAck] = useState<LiveAck | null>(null);
  const [hello, setHello] = useState<LiveHello | null>(null);
  const [restarting, setRestarting] = useState<LiveSession["restarting"]>(null);
  const feedRef = useRef<LiveFeed | null>(null);
  const bufRef = useRef<LiveBuffer>(new LiveBuffer(LIVE_CFG_DEFAULT.window_s, LIVE_CFG_DEFAULT.buffer_max_n));
  useEffect(() => { loadLiveCfg().then((c) => { setCfg(c); bufRef.current.windowS = c.window_s; bufRef.current.maxN = c.buffer_max_n; }); }, []);
  const url = saved.url || cfg.default_url;

  useEffect(() => {
    if (!saved.enabled) { feedRef.current?.stop(); feedRef.current = null; setStatus("off"); bufRef.current.clear(); setVersion((v) => v + 1); return; }
    const feed = new LiveFeed(url, cfg);
    feedRef.current = feed;
    const offs = [
      feed.onStatus((s) => setStatus(s)),
      feed.onState((s) => {
        bufRef.current.push(s); setVersion((v) => v + 1);
        if (feed.hello) setHello(feed.hello);
        setRestarting((r) => {                                                          // 새 모터의 첫 state → 도착 표시; 띠는 최소 eta_s 유지(안내 시간)
          if (!r || s.motor_id !== r.motor_id) return r;
          if (r.arrived) return Date.now() - r.at >= r.eta_s * 1000 ? null : r;
          return { ...r, arrived: true };
        });
      }),
      feed.onAck((a) => {
        setLastAck(a);
        const ap2 = a.applied as { restart?: boolean; hot?: boolean; motor_id?: string; from?: string; eta_s?: number; switch_ms?: number } | undefined;
        if (a.ok && a.name === "select_motor" && ap2?.motor_id && (ap2.restart || ap2.hot)) {
          const last = bufRef.current.last;
          const sum = last ? `${last.status.label ?? last.status.status}${last.status.cause_signal !== "-" ? ` (${last.status.cause_signal} ${last.status.value})` : ""} · DE 베어링 ${last.T?.bearing_de ?? "-"} °C · 진동 ${last.vibration_mms} mm/s` : "-";
          bufRef.current.clear();
          setRestarting({ motor_id: ap2.motor_id, from: ap2.from ?? last?.motor_id ?? "-", eta_s: Number(ap2.eta_s ?? 45), at: Date.now(), hot: !!ap2.hot, switch_ms: ap2.switch_ms, from_summary: sum, arrived: false });
        }
      }),
    ];
    feed.start();
    return () => { offs.forEach((f) => f()); feed.stop(); if (feedRef.current === feed) feedRef.current = null; };
  }, [saved.enabled, url, cfg]);

  // 끊김이 길어지면 버퍼의 옛 샘플이 "현재"로 보이지 않도록 재접속 후 첫 state 가 올 때까지 active 를 내린다 (status 가 live 로 바뀌면 됨)
  const setEnabled = useCallback((on: boolean) => setSaved((s) => { const n = { ...s, enabled: on }; save(n); return n; }), []);
  const setUrl = useCallback((u: string) => setSaved((s) => { const n = { ...s, url: u.trim() }; save(n); return n; }), []);
  const send = useCallback((name: string, args: Record<string, unknown> = {}) => {
    const f = feedRef.current;
    return f ? f.send(name, args) : Promise.resolve<LiveAck>({ type: "ack", id: null, name, ok: false, reason: "LIVE 꺼짐", t_wall: Date.now() / 1000 });
  }, []);
  // 전환이 너무 오래 걸리면(2×eta 또는 timeout) 일반 끊김으로 되돌린다
  useEffect(() => {
    if (!restarting) return;
    // 도착했으면 최소 안내 시간(eta_s)만, 아직이면 재기동 한도(2×eta 또는 timeout) 뒤 일반 끊김으로
    const ms = restarting.arrived ? Math.max(0, restarting.eta_s * 1000 - (Date.now() - restarting.at)) : Math.max(restarting.eta_s * 2, 60) * 1000;
    const h = setTimeout(() => setRestarting(null), ms);
    return () => clearTimeout(h);
  }, [restarting]);
  const buf = bufRef.current;
  const active = saved.enabled && status === "live" && buf.states.length >= 2;
  const fallback = saved.enabled && !active;
  return useMemo(() => ({
    cfg, enabled: saved.enabled, setEnabled, url, setUrl, status, active, fallback,
    buffer: buf, version, last: buf.last, clients: feedRef.current?.clients ?? 0, send, lastAck, hello, restarting,
  }), [cfg, saved.enabled, setEnabled, url, setUrl, status, active, fallback, buf, version, send, lastAck, hello, restarting]);
}
