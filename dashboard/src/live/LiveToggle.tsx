import { useEffect, useState } from "react";
import type { LiveSession } from "./session";

// 상단 녹화 / LIVE 스위치 (TASK 실시간 §6). LIVE 를 누르면 주소 입력(마지막 값 기억) → 연결되면 초록 LIVE 뱃지,
// 끊기면 자동으로 녹화 데이터로 돌아가고 LiveBanner 가 노란 띠를 띄운다. 모드 표시는 항상 보인다(§1.6).
export function LiveToggle({ live, compact }: { live: LiveSession; compact?: boolean }) {
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState(live.url);
  const badge = !live.enabled ? { cls: "rec", text: "녹화" }
    : live.restarting ? { cls: "wait", text: `전환 중 → ${live.restarting.motor_id}` }
    : live.status === "live" ? { cls: "on", text: `LIVE${live.last ? ` · ${live.last.motor_id}` : ""}${live.clients ? ` · ${live.clients}명` : ""}` }
    : live.status === "connecting" ? { cls: "wait", text: "연결 중…" }
    : { cls: "lost", text: "끊김 → 녹화" };
  const apply = () => { live.setUrl(draft); live.setEnabled(true); setEdit(false); };
  return (
    <span className={"live-toggle" + (compact ? " compact" : "")} title={live.enabled ? `WebSocket ${live.url}` : "녹화 재생 (영상 + 로그)"}>
      <span className="seg">
        <button className={!live.enabled ? "on" : ""} onClick={() => live.setEnabled(false)} title="녹화 모드: 영상·엔진 배치 로그 재생 (발표 백업)">녹화</button>
        <button className={live.enabled ? "on" : ""} onClick={() => { if (live.enabled) setEdit((e) => !e); else { setDraft(live.url); setEdit(true); } }} title="LIVE 모드: Isaac Sim --live 스트림">LIVE</button>
      </span>
      <span className={"live-badge " + badge.cls}><i />{badge.text}</span>
      {edit && (
        <span className="live-url">
          <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") apply(); if (e.key === "Escape") setEdit(false); }}
                 placeholder="ws://데스크탑IP:8765" spellCheck={false} autoFocus />
          <button className="primary" onClick={apply}>연결</button>
          <button onClick={() => setEdit(false)}>취소</button>
        </span>
      )}
    </span>
  );
}

// 끊김 띠 (§1.3): LIVE 를 켰는데 스트림이 없을 때만 보인다. 발표 중 멈추지 않도록 화면은 녹화 데이터로 계속 간다.
export function LiveBanner({ live }: { live: LiveSession }) {
  const [, tick] = useState(0);
  useEffect(() => { if (!live.restarting) return; const h = setInterval(() => tick((x) => x + 1), 1000); return () => clearInterval(h); }, [live.restarting]);
  if (live.restarting) {                                   // select_motor 자동 재시작 (R3): 끊김이 아니라 전환 중
    const el = Math.round((Date.now() - live.restarting.at) / 1000);
    return (
      <div className="live-banner restart">
        ⟳ <b>모터 전환 중 ({live.restarting.motor_id}, 약 {Math.round(live.restarting.eta_s)}초)</b> — Isaac Sim 재기동, 재접속 대기 · 경과 {el}초
        <span className="grow" /><span className="dim">그동안 녹화 데이터를 보여줍니다</span>
      </div>
    );
  }
  if (!live.fallback) return null;
  const why = live.status === "connecting" ? "연결 중" : live.status === "lost" ? `재연결 시도 중 (${live.cfg.reconnect_s} s 간격)` : "스트림 대기";
  return (
    <div className="live-banner">
      ⚠ 라이브 연결 끊김 — <b>녹화 재생 중</b> · {why} · {live.url}
      <span className="grow" />
      <span className="dim">Isaac Sim 을 <code>--live</code> 로 실행했는지, 방화벽 8765 가 열렸는지 확인</span>
    </div>
  );
}
