import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Step } from "../data";
import { useLiveSession } from "../live/session";
import { liveSteps, toMotorSeries } from "../live/livedata";
import { streamUrlFor, useViewportStream } from "../live/stream";
import type { LiveState } from "../live/feed";
import { EvidenceDrawer } from "../status/EvidenceDrawer";
import { LayoutA, type SceneOpt, type StepA } from "../status/LayoutA";
import { ThresholdTab, SpecTab } from "../status/Tabs";
import { loadFleetIndex, loadStatusContent, type FleetIndex, type FleetScenario, type StatusContent } from "../status/data";
import "../status/status.css";

// 실시간 전기 상태 보드 (레이아웃 A, 2026-10-27). 데이터 소스는 Isaac --live 의 state WebSocket 하나뿐 (녹화 재생 없음).
//   #/status            기본 ws://localhost:8765 (content/live.yaml default_url) — 상태 JSON 10 Hz
//   #/status?live=ws://host:8765   다른 PC 의 Isaac. 뷰포트 JPEG 스트림은 hello.stream_ws (없으면 같은 host 의 stream_port)
// index.json(임계값·색·라벨·모터 사양)과 narration.yaml(왜/무엇을)·labels_plain.yaml 은 정적 내용이다 — 숫자는 state 에서만.
export function LiveBoard() {
  const [index, setIndex] = useState<FleetIndex | null>(null);
  const [content, setContent] = useState<StatusContent | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { document.documentElement.setAttribute("data-theme", "dark"); }, []);     // 다크 단일
  useEffect(() => {
    Promise.all([loadFleetIndex(), loadStatusContent()]).then(([i, c]) => { setIndex(i); setContent(c); }).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div style={{ padding: 30 }}>데이터를 읽지 못했습니다.<br /><code>{err}</code><div className="dim">dashboard/tools/export_status_data.py 로 index.json 을 먼저 만드세요 (임계값·라벨의 단일 출처).</div></div>;
  if (!index || !content) return <div style={{ padding: 30 }} className="muted">불러오는 중…</div>;
  return <Board index={index} content={content} />;
}

// 라이브 state → 해설 변수 (narration.yaml 의 {변수}). 전부 state 값 — 숫자를 여기서 만들지 않는다
function liveSceneValues(s: LiveState, index: FleetIndex, statusKo: Record<string, string>): Record<string, number | string | null> {
  const r = s.rated_line_A || 1; const es = s.electrical_source;
  const ko = (k: string) => statusKo[k] ?? k;
  const pct = (a: number) => Math.round((a / r) * 100);
  const inherent = es?.inherent_i2i1 ?? null;
  const xn = inherent ? Math.round((s.i2_over_i1 / inherent) * 10) / 10 : null;
  const caseMap: Record<string, number | null> = {};
  for (const c of es?.cases ?? []) caseMap[c.key] = c.expected_i2i1;
  return {
    ph_a: index.phase_labels.A, ph_b: index.phase_labels.B, ph_c: index.phase_labels.C, rated_line_A: r,
    a_rms_now: s.Ia_rms, b_rms_now: s.Ib_rms, c_rms_now: s.Ic_rms, a_pct_now: pct(s.Ia_rms), b_pct_now: pct(s.Ib_rms), c_pct_now: pct(s.Ic_rms),
    a_status_now: ko(s.current_status?.[0] ?? ""), b_status_now: ko(s.current_status?.[1] ?? ""), c_status_now: ko(s.current_status?.[2] ?? ""),
    i2i1_now: s.i2_over_i1, i2i1_x_normal_now: xn, i2_over_in_now: s.i2_over_in ?? null,
    a_rms_end: s.Ia_rms, b_rms_end: s.Ib_rms, c_rms_end: s.Ic_rms, a_pct_end: pct(s.Ia_rms), b_pct_end: pct(s.Ib_rms), c_pct_end: pct(s.Ic_rms),
    a_status_end: ko(s.current_status?.[0] ?? ""), b_status_end: ko(s.current_status?.[1] ?? ""), c_status_end: ko(s.current_status?.[2] ?? ""),
    i2i1_end: s.i2_over_i1, i2i1_x_normal_end: xn, i2i1_start: null,
    bc_rms_end: s.Ib_rms, bc_pct_end: pct(s.Ib_rms), max_pct_end: Math.max(pct(s.Ia_rms), pct(s.Ib_rms), pct(s.Ic_rms)), min_pct_end: Math.min(pct(s.Ia_rms), pct(s.Ib_rms), pct(s.Ic_rms)),
    short_turns: es?.turns ?? null, r_f_ohm: es?.R_f_ohm ?? null, load_pct: Math.round(s.load * 100), i_f_A: es?.i_f_A ?? null, p_loop_W: s.p_loop_total_W ?? null,
    i2i1_normal: inherent, i2i1_4turn: caseMap.itsc_4turn ?? null, i2i1_12turn: caseMap.itsc_12turn ?? null,
  };
}

function Board({ index, content }: { index: FleetIndex; content: StatusContent }) {
  const live = useLiveSession();
  useEffect(() => { if (!live.enabled) live.setEnabled(true); }, [live.enabled]);   // eslint-disable-line react-hooks/exhaustive-deps  — 라이브 상시 (녹화 토글 없음)
  const last = live.buffer.last;
  const motor = useMemo(() => index.motors.find((m) => m.id === last?.motor_id) ?? index.motors[0], [index, last?.motor_id]);
  const staticSteps: Step[] = useMemo(() => {
    const base = index.scenarios.electrical.steps.map((s) => ({ ...s, source: "", video_start: 0, video_end: 0, highlight: false, clip: null }));
    const hs = live.hello?.scenes;
    if (!hs?.length) return base;
    const byId = new Map(base.map((s) => [s.id, s]));
    return hs.map((h) => ({ ...(byId.get(h.id) ?? { subtitle: "", electrical_case: h.electrical_case ?? h.id, faults: [], load: 1, time_scale: 1, t_start: 0, t_end: 0 }), n: h.n, id: h.id, label: h.label, source: "Isaac Sim", video_start: 0, video_end: 0, highlight: false, clip: null } as Step));
  }, [index, live.hello]);
  const series = useMemo(() => (live.buffer.states.length ? toMotorSeries(live.buffer, index, null) : null), [live.version, index]);   // eslint-disable-line react-hooks/exhaustive-deps
  const steps = useMemo(() => liveSteps(live.buffer, staticSteps), [live.version, staticSteps]);   // eslint-disable-line react-hooks/exhaustive-deps
  const trendTick = Math.floor(live.version / 5);                                                   // 추세 차트는 0.5 s(5 state)마다 — 프레임 디코딩과 경쟁하지 않게
  const trendSeries = useMemo(() => series, [trendTick]);                                            // eslint-disable-line react-hooks/exhaustive-deps
  const cur = steps[steps.length - 1];
  const step: StepA = cur ? { n: cur.n, id: cur.id, label: cur.label, electrical_case: cur.electrical_case, t_start: cur.t_start } : { n: 0, id: "healthy", label: "연결 대기", electrical_case: "healthy", t_start: 0 };
  const sc: FleetScenario = useMemo(() => ({ total_duration_s: Math.max(live.buffer.tEnd, live.buffer.tMin + 1), t_min: live.buffer.tMin, steps: steps as unknown as FleetScenario["steps"] }), [live.version, steps]);   // eslint-disable-line react-hooks/exhaustive-deps
  const i = series ? series.t.length - 1 : 0;
  const scene = content.narration.electrical[step.id];
  const sceneValues = useMemo(() => (last ? liveSceneValues(last, index, content.labels.elec_status ?? {}) : undefined), [last, index, content]);
  const scenes: SceneOpt[] = useMemo(() => (live.hello?.scenes?.length ? live.hello.scenes.map((h) => ({ n: h.n, id: h.id, label: h.label })) : index.scenarios.electrical.steps.map((s) => ({ n: s.n, id: s.id, label: s.label }))), [live.hello, index]);
  // 시나리오 전환: 명령 → 새 장면 첫 state 까지 시간 (A3 측정값으로 헤더에 표시)
  const [switching, setSwitching] = useState<{ n: number; at: number } | null>(null);
  const [lastSwitchMs, setLastSwitchMs] = useState<number | null>(null);
  const onScene = useCallback((n: number) => { setSwitching({ n, at: performance.now() }); live.send("play_scenario", { scene: n }).then((a) => { if (!a.ok) setSwitching(null); }); }, [live]);
  useEffect(() => {
    if (!switching) return;
    const target = scenes.find((x) => x.n === switching.n);
    if (target && last?.scene?.id === target.id && last.scene.elapsed_s < 2) { setLastSwitchMs(Math.round(performance.now() - switching.at)); setSwitching(null); }
    else if (performance.now() - switching.at > 10000) setSwitching(null);
  }, [switching, last, scenes]);
  // 뷰포트 스트림
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamUrl = live.enabled ? streamUrlFor(live.url, live.hello?.stream_ws, live.cfg.stream_port ?? 8766) : null;
  const stream = useViewportStream(streamUrl, canvasRef);
  const [drawer, setDrawer] = useState<null | string>(() => { const p = new URLSearchParams(window.location.hash.split("?")[1] ?? ""); return p.get("drawer") === "1" ? (p.get("tab") ?? "evidence") : null; });
  const conn = live.enabled ? live.status : "off";
  return (
    <>
      <LayoutA index={index} motor={motor} labels={content.labels} s={series} i={i} last={last} step={step} sc={sc} scene={scene} sceneValues={sceneValues}
        conn={conn} wsUrl={live.url} onUrl={(u) => live.setUrl(u)} isaacMode={last?.mode ?? null}
        scenes={scenes} onScene={onScene} switching={switching} lastSwitchMs={lastSwitchMs}
        stream={stream} canvasRef={canvasRef} sTrend={trendSeries} openDrawer={() => setDrawer("evidence")} />
      {drawer && <EvidenceDrawer index={index} s={series} i={i} stepId={step.id} electricalCase={step.electrical_case} mode="electrical" live={last} isLive={conn === "live"}
        sourceLabel={`Isaac Sim 라이브 ${live.url}`} labels={content.labels} onClose={() => setDrawer(null)} initialTab={drawer}
        tabs={[
          { key: "thr", label: "임계값", node: <ThresholdTab index={index} easy={content.labels.thresholds_easy} /> },
          { key: "spec", label: "사양", node: <SpecTab index={index} /> },
          { key: "gloss", label: "용어", node: <dl className="gloss">{content.glossary.map((g) => <div key={g.term}><dt>{g.term}</dt><dd>{g.text}</dd></div>)}</dl> },
        ]} />}
    </>
  );
}
