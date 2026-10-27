import { useEffect, useMemo, useState } from "react";
import type { LiveSession } from "./session";
import type { LiveAck } from "./feed";

// 양방향 제어 패널 (TASK 실시간 §7 R3, L2). 라이브 모드에서만 활성. 허용 목록·범위는 Isaac 이 접속 직후 보내는 hello(config/live.yaml)에서,
// 현재 값은 state 에서 온다 — 버튼 상태는 "내가 눌렀다" 가 아니라 "Isaac 이 적용했다"(state) 로 확정되고, 거부되면 토스트에 이유.
// 모터 전환은 자동 재시작(select_motor → Isaac 재기동, 세션이 '모터 전환 중' 띠를 띄우고 재접속 대기).
const FAULT_LABEL: Record<string, string> = {
  bearing_de_fault: "DE 베어링 결함", bearing_nde_fault: "NDE 베어링 결함", misalignment: "축 정렬 불량", fan_failure: "냉각팬 고장", brake_drag: "브레이크 끌림", overload: "과부하",
  itsc_4turn: "턴간 단락 4턴", itsc_12turn: "턴간 단락 12턴", voltage_unbalance: "전압 불평형", single_phasing: "결상 (R상)", no_load: "무부하",
};
interface Toast { id: number; ok: boolean; text: string }

export function ControlPanel({ live, open, onClose }: { live: LiveSession; open: boolean; onClose: () => void }) {
  const st = live.last;
  const hello = live.hello;
  const cmds = hello?.commands ?? {};
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [load, setLoad] = useState<number | null>(null);
  const [ts, setTs] = useState<number | null>(null);
  const [sm, setSm] = useState<number | null>(null);
  useEffect(() => {
    if (!open) return;
    const on = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [open, onClose]);
  const toast = (ok: boolean, text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-4), { id, ok, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), ok ? 2500 : 6000);
  };
  const run = async (name: string, args: Record<string, unknown>, label: string) => {
    setBusy(label);
    let a: LiveAck;
    try { a = await live.send(name, args); } finally { setBusy(null); }
    if (a.ok) toast(true, `${label} ✓`); else toast(false, `${label} 거부 — ${a.reason ?? "이유 없음"}`);
    return a;
  };
  const mode = st?.mode ?? "mechanical";
  const inject = cmds.inject_fault as { thermal?: string[]; electrical?: string[] } | undefined;
  const thermal = inject?.thermal ?? [];
  const electrical = inject?.electrical ?? [];
  const playing = !!st?.scene?.playing;
  const faultsOn = new Set(st?.faults ?? []);
  const caseOn = st?.case ?? "healthy";
  const range = (k: string, key: string, d: [number, number]) => (cmds[k] as Record<string, [number, number]> | undefined)?.[key] ?? d;
  const loadR = range("set_load", "pct", [0, 150]), tsR = range("set_time_scale", "x", [1, 600]), smR = range("set_slowmo", "x", [1, 240]);
  const motors = hello?.motors ?? [];
  const modes = (cmds.set_mode as { modes?: string[] } | undefined)?.modes ?? ["mechanical", "electrical", "integrated"];
  const disabled = !live.active || (!!live.restarting && !live.restarting.arrived && !live.restarting.hot);
  const loadV = load ?? Math.round((st?.load ?? 1) * 100), tsV = ts ?? (st?.time_scale ?? 60), smV = sm ?? Math.round(1 / (st?.slowmo || 1 / 60));
  const scenes = useMemo(() => (cmds.play_scenario ? [1, 2, 3, 4, 5, 6, 7] : []), [cmds.play_scenario]);
  if (!open) return null;
  return (
    <div className="ctl-drawer" role="dialog" aria-label="제어 패널">
      <div className="ctl-h">
        <b>제어 패널</b> <span className="dim">{live.active ? `LIVE · ${st?.motor_id} · ${mode}` : "LIVE 연결이 있어야 조작할 수 있습니다"}</span>
        <span className="grow" />
        {busy && <span className="dim">{busy}…</span>}
        <button onClick={onClose} title="Esc">닫기</button>
      </div>
      {live.restarting && !live.restarting.hot && <div className="ctl-note">모터 전환 중 — {live.restarting.motor_id} 재기동 (약 {Math.round(live.restarting.eta_s)} s), 재접속 대기</div>}
      {live.active && !hello && <div className="ctl-note">Isaac 이 허용 명령 목록(hello)을 보내지 않았습니다 — R3 이전 코드로 떠 있는 인스턴스입니다. Isaac 을 다시 실행하면 결함·모터 버튼이 채워집니다.</div>}
      <div className="ctl-b">
        <section>
          <h4>결함 주입 <span className="dim">{playing ? "시나리오 재생 중에는 거부됩니다 — 먼저 정지" : "켜면 Isaac 모터가 즉시 반응"}</span></h4>
          {(mode === "mechanical" || mode === "integrated") && (
            <div className="ctl-grid">
              {thermal.map((f) => <button key={f} className={"ctl-fault" + (faultsOn.has(f) ? " on" : "")} disabled={disabled}
                onClick={() => run("inject_fault", { fault: f, on: !faultsOn.has(f) }, `${FAULT_LABEL[f] ?? f} ${faultsOn.has(f) ? "해제" : "주입"}`)}>{FAULT_LABEL[f] ?? f}</button>)}
            </div>
          )}
          {(mode === "electrical" || mode === "integrated") && (
            <div className="ctl-grid">
              {electrical.map((f) => <button key={f} className={"ctl-fault el" + (caseOn === f ? " on" : "")} disabled={disabled}
                onClick={() => run("inject_fault", { fault: f, on: caseOn !== f }, `${FAULT_LABEL[f] ?? f} ${caseOn === f ? "해제" : "주입"}`)}>{FAULT_LABEL[f] ?? f}</button>)}
            </div>
          )}
          <div className="dim small">현재: 열 결함 {st?.faults?.length ? st.faults.map((f) => FAULT_LABEL[f] ?? f).join(", ") : "없음"} · 전류 {caseOn === "healthy" ? "정상" : FAULT_LABEL[caseOn] ?? caseOn}</div>
        </section>
        <section>
          <h4>부하 · 배속</h4>
          <label>부하율 <b>{loadV} %</b><input type="range" min={loadR[0]} max={loadR[1]} step={5} value={loadV} disabled={disabled}
            onChange={(e) => setLoad(Number(e.target.value))} onMouseUp={() => { if (load != null) { run("set_load", { pct: load }, `부하 ${load} %`); setLoad(null); } }}
            onTouchEnd={() => { if (load != null) { run("set_load", { pct: load }, `부하 ${load} %`); setLoad(null); } }} /></label>
          <label>시간 배속 <b>×{tsV}</b><input type="range" min={tsR[0]} max={tsR[1]} step={1} value={tsV} disabled={disabled || mode === "electrical"}
            onChange={(e) => setTs(Number(e.target.value))} onMouseUp={() => { if (ts != null) { run("set_time_scale", { x: ts }, `배속 ×${ts}`); setTs(null); } }} /></label>
          <label>슬로모션 1/<b>{smV}</b><input type="range" min={smR[0]} max={smR[1]} step={1} value={smV} disabled={disabled || mode === "mechanical"}
            onChange={(e) => setSm(Number(e.target.value))} onMouseUp={() => { if (sm != null) { run("set_slowmo", { x: sm }, `슬로모션 1/${sm}`); setSm(null); } }} /></label>
        </section>
        <section>
          <h4>모드 · 시나리오</h4>
          <div className="ctl-row">
            {modes.map((m) => <button key={m} className={mode === m ? "on" : ""} disabled={disabled || mode === m} onClick={() => run("set_mode", { mode: m }, `모드 ${m}`)}>{m === "mechanical" ? "기계" : m === "electrical" ? "전기" : "통합"}</button>)}
          </div>
          <div className="ctl-row">
            {playing ? <button className="primary" disabled={disabled} onClick={() => run("stop_scenario", {}, "시나리오 정지")}>■ 시나리오 정지</button>
                     : <button className="primary" disabled={disabled} onClick={() => run("play_scenario", {}, "시나리오 재생")}>▶ 시나리오 자동 재생</button>}
            {scenes.map((n) => <button key={n} disabled={disabled} onClick={() => run("play_scenario", { scene: n }, `장면 ${n}`)} title={`장면 ${n} 부터`}>{n}</button>)}
            <button disabled={disabled} onClick={() => run("reset", {}, "리셋")}>↺ 리셋</button>
          </div>
        </section>
        <section>
          <h4>모터 선택 <span className="dim">{(hello?.commands?.select_motor as { switch_mode?: string } | undefined)?.switch_mode === "restart" ? `자동 재시작 — 약 ${Math.round(hello?.restart_eta_s ?? 45)} s 끊김 뒤 재접속` : "핫 스위치 — 재기동 없이 열회로·전류 모델·카메라만 교체 (안내 띠 몇 초)"}</span></h4>
          <div className="ctl-row">
            {motors.map((m) => <button key={m} className={st?.motor_id === m ? "on" : ""} disabled={disabled || st?.motor_id === m}
              onClick={() => run("select_motor", { motor_id: m }, `모터 ${m} 전환`)}>{m}</button>)}
          </div>
        </section>
        <section>
          <h4>최근 명령</h4>
          <div className="ctl-toasts">
            {toasts.length === 0 && <span className="dim">아직 없음</span>}
            {toasts.map((t) => <div key={t.id} className={"ctl-toast " + (t.ok ? "ok" : "bad")}>{t.text}</div>)}
          </div>
        </section>
      </div>
    </div>
  );
}
