import { useEffect, useMemo, useState } from "react";
import { fmtT, indexAt, loadModeData, type ModeData } from "../data";
import { fill, fmtSim, liveValues, loadMechData, type MechData } from "../mech/data";
import { buildClusters, captionText, REVEAL_KEYS, REVEAL_LABEL, revealTimes } from "../mech/captions";
import { openChannel, type Cmd, type MainState, type Msg } from "../mech/broadcast";
import "../mech/presenter.css";

// 발표자 전용 화면 (TASK 7.2): #/mechanical/presenter — 발표자 노트북용.
// 메인(심사위원) 화면과 같은 브라우저에서 열면 BroadcastChannel 로 재생 상태를 받아 같은 시각을 보여준다.
// 여기에만 나오는 것: 멘트(presenter_line). 메인 화면에는 절대 나오지 않는다.
// 키(Space, ←/→, 1~7, N)는 메인 화면으로 보낸다. 메인이 없으면 주소의 ?t= 로 혼자 연습할 수 있다.
export function PresenterView() {
  const [data, setData] = useState<MechData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    loadModeData("mechanical").then((base: ModeData) => loadMechData(base)).then(setData).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div style={{ padding: 30 }}>데이터를 읽지 못했습니다.<br /><code>{err}</code></div>;
  if (!data) return <div style={{ padding: 30 }} className="muted">불러오는 중…</div>;
  return <Inner data={data} />;
}

const STALE_MS = 3000;

function Inner({ data }: { data: MechData }) {
  const chan = useMemo(() => openChannel(), []);
  const [st, setSt] = useState<MainState | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!chan) return;
    const on = (e: MessageEvent<Msg>) => { if (e.data?.kind === "state") setSt(e.data); };
    chan.addEventListener("message", on);
    chan.postMessage({ kind: "hello" });
    const h = setInterval(() => setNow(Date.now()), 500);
    return () => { chan.removeEventListener("message", on); clearInterval(h); chan.close(); };
  }, [chan]);
  const send = (cmd: Cmd["cmd"], extra: Partial<Cmd> = {}) => chan?.postMessage({ kind: "cmd", cmd, ...extra } as Cmd);

  // 메인 화면이 없으면 ?t= (연습용)
  const connected = !!st && now - st.at < STALE_MS;
  const t0 = useMemo(() => { const q = window.location.hash.split("?")[1]; const v = q ? Number(new URLSearchParams(q).get("t")) : NaN; return Number.isFinite(v) ? v : 0; }, []);
  const t = st ? st.t : t0;
  const sc = data.scenarios, ts = data.timeseries;
  const stepIndex = st ? st.stepIndex : Math.max(0, sc.steps.findIndex((s) => t < s.t_end));
  const step = sc.steps[stepIndex], next = sc.steps[stepIndex + 1];
  const scene = data.content.scenes[step.id], nextScene = next ? data.content.scenes[next.id] : null;
  const i = indexAt(ts, t);
  const v = { ...data.values[step.id], ...liveValues(data, t) };
  const level = st ? st.level : 3;
  const rt = scene ? revealTimes(scene, step) : null;

  // 다음 사건 예고 (events.json)
  const clusters = useMemo(() => buildClusters(data.events), [data.events]);
  const nextEv = clusters.find((c) => c.t > t + 0.05);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === " ") { e.preventDefault(); send("toggle"); }
      else if (e.key === "ArrowRight") { e.preventDefault(); send("nextStep"); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); send("prevStep"); }
      else if (e.key === "n" || e.key === "N") send("nextLevel");
      else if (e.key >= "1" && e.key <= "9") send("goto", { n: Number(e.key) });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="presenter">
      <div className="pr-top">
        <span className="brand">VIGENT 발표자 화면</span>
        <span className={"conn" + (connected ? " on" : "")}>{connected ? "메인 화면 연결됨" : "메인 화면 연결 없음 — 같은 브라우저에서 #/mechanical 을 열어 두세요"}</span>
        <span className="grow" />
        <span className="clock">{st?.playing ? "▶" : "❚❚"} <b>{fmtT(t)}</b> / {fmtT(sc.total_duration_s)}</span>
        <span className="sim">시뮬레이션 경과 <b>{fmtSim(ts.sim_elapsed_s[i])}</b> · 화면 1초 = <b>{ts.time_scale[i]}</b>초</span>
      </div>
      <div className="pr-main">
        <div className="pr-now">
          <div className="pr-scene">장면 {step.n}/{sc.steps.length} <b>{scene?.title ?? step.label}</b> <span className="dim">— {scene?.fingerprint}</span>
            <span className="grow" /><span className="dim">장면 남은 시간 {fmtT(Math.max(0, step.t_end - t))}</span></div>
          <div className="pr-line-k">멘트 (이 화면에만 나옵니다)</div>
          <div className="pr-line">{scene ? fill(scene.presenter_line, v) : "—"}</div>
          <div className="pr-sub-k">심사위원 화면에 지금 보이는 해설 <span className="dim">{level}/3 공개{st && !st.autoMode ? " · 발표자 모드 — N 으로 다음 단계" : " · 자동"}</span></div>
          <dl className="pr-reveal">
            {REVEAL_KEYS.map((k, n) => (
              <div key={k} className={"rv" + (level > n ? " on" : "")}>
                <dt>{REVEAL_LABEL[k]}{rt && level <= n && <span className="dim"> {fmtT(rt[k])}</span>}</dt>
                <dd>{scene ? fill(scene[k], v) : ""}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="pr-side">
          <div className="pr-card">
            <div className="pr-k">다음 사건 {nextEv && <span className="dim">{fmtT(nextEv.t)} · {Math.max(0, nextEv.t - t).toFixed(0)}초 후</span>}</div>
            <div className="pr-ev">{nextEv ? captionText(nextEv.primary, data.content.templates) : "없음 (시나리오 끝)"}</div>
          </div>
          <div className="pr-card">
            <div className="pr-k">다음 장면 {next && <span className="dim">{fmtT(next.t_start)} · {Math.max(0, next.t_start - t).toFixed(0)}초 후</span>}</div>
            {next ? (
              <>
                <div className="pr-next-t">장면 {next.n} <b>{nextScene?.title ?? next.label}</b> <span className="dim">— {nextScene?.fingerprint}</span></div>
                <div className="pr-next-l">{nextScene ? fill(nextScene.presenter_line, { ...data.values[next.id], ...liveValues(data, next.t_start) }) : ""}</div>
                <div className="dim">화면 1초 = 시뮬레이션 {next.time_scale}초</div>
              </>
            ) : <div className="dim">마지막 장면입니다</div>}
          </div>
          <div className="pr-card">
            <div className="pr-k">리드 타임 (장면 2)</div>
            <div>주의 진입 {fmtT(sc.lead_time.alarm_t ?? 0)} → 위험 {fmtT(sc.lead_time.danger_t ?? 0)} : 화면 <b>{sc.lead_time.lead_s}</b> s = 시뮬레이션 약 <b>{Math.round(((sc.lead_time.lead_sim_s ?? 0) / 60) * 10) / 10}</b> 분</div>
          </div>
          <div className="pr-card keys">
            <div className="pr-k">조작 (메인 화면으로 전달)</div>
            <div><kbd>Space</kbd> 재생/정지 · <kbd>←</kbd><kbd>→</kbd> 장면 · <kbd>1</kbd>~<kbd>7</kbd> 바로 이동 · <kbd>N</kbd> 다음 해설 단계(발표자 모드)</div>
            <div className="pr-btns">
              <button onClick={() => send("toggle")}>{st?.playing ? "❚❚ 정지" : "▶ 재생"}</button>
              <button onClick={() => send("prevStep")}>← 이전 장면</button>
              <button onClick={() => send("nextStep")}>다음 장면 →</button>
              <button onClick={() => send("nextLevel")}>N 다음 단계</button>
            </div>
          </div>
        </div>
      </div>
      <div className="pr-bottom">
        {sc.steps.map((s) => (
          <div key={s.id} className={"pr-ch" + (s.n === step.n ? " cur" : "")} onClick={() => send("goto", { n: s.n })}>
            <b>{s.n}</b> {(data.content.scenes[s.id]?.title ?? s.label).replace(/^\d+\.\s*/, "")} <span className="dim">{fmtT(s.t_start)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
