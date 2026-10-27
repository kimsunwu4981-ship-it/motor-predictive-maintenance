import { useMemo, type RefObject } from "react";
import { fmtT } from "../data";
import { fill } from "../live/types";
import type { LiveState } from "../live/feed";
import type { StreamStats } from "../live/stream";
import { TrendChart, type TrendSel } from "./TrendChart";
import { StatusStrip } from "./StatusStrip";
import { WaveTile } from "./tiles/WaveTile";
import { BarsTile, type Bar } from "./tiles/BarsTile";
import { Plain, motorLabel, fmtVal, nameOf, primaryOf } from "./plain";
import { specFor, plainOf, PHASES, type FleetIndex, type FleetScenario, type Level, type MotorInfo, type MotorSeries, type Phase, type PlainLabels, type StatusScene } from "./data";
import "./simple.css";
import "./layout_a.css";

// 레이아웃 A (2026-10-27): 실시간 전용·전기 전용 상태 보드.
//   [헤더 40] VIGENT · 전기 상태 보드 · 실시간   ● LIVE ws://…   시나리오 ▾
//   [상태 띠 72] ▲ 경고  전류 불균형 0.073  안전 <0.05 · 위험 ≥0.10 · 3초 지속  현대 HLP-2.2/4 · 2.2 kW 4극
//   [2×2] ① 아이작심 실시간(canvas, JPEG 스트림) ② 전류 파형(최근 2주기) / ③ 전류 성분 I₁·I₂·I₀ ④ 추세
//   [하단 44] 왜? … | 무엇을? … | 시뮬레이션 추정값 · 근거 보기 ›
// 데이터는 전부 Isaac state(10 Hz) → toMotorSeries(MotorSeries) 와 index.json(임계값·색·라벨). 판정은 Isaac 쪽 엔진 결과 그대로.
// 녹화·전문가·기계·발표 모드 없음. 색은 상태 셋(초록·주황·빨강) + ●▲■. 전환은 상태색 300 ms 페이드만.
export interface SceneOpt { n: number; id: string; label: string }
export interface StepA { n: number; id: string; label: string; electrical_case: string; t_start: number }
const MANUAL_OPT = -1;   // 시나리오 ▾ 의 "수동 조작" 표시용 값
export type ConnStatus = "off" | "connecting" | "live" | "lost";

export function LayoutA(p: {
  index: FleetIndex; motor: MotorInfo; labels: PlainLabels; s: MotorSeries | null; i: number; last: LiveState | null;
  step: StepA; sc: FleetScenario; scene?: StatusScene; sceneValues?: Record<string, number | string | null>;
  conn: ConnStatus; wsUrl: string; onUrl: (u: string) => void; isaacMode: string | null;
  scenes: SceneOpt[]; onScene: (n: number) => void; switching: { n: number; at: number } | null; lastSwitchMs: number | null;
  stream: StreamStats; canvasRef: RefObject<HTMLCanvasElement>;
  manualAction?: string;              // 수동 조작 때 "무엇을?" (가까운 장면의 조치 문구, LiveBoard 가 고른다)
  sTrend?: MotorSeries | null;        // 추세·상태 띠용 시계열 (0.5 s 간격으로 갱신 — ECharts 전체 재그리기를 10 Hz 로 하지 않도록). 없으면 s
  openDrawer: () => void;
}) {
  const { index, motor, labels, s, i, last, step, sc, scene, sceneValues, conn, stream } = p;
  const L = labels.notes; const A = labels.layout_a ?? {}; const T = labels.tiles ?? {};
  const prim = s ? primaryOf(index, motor, s, i, "electrical", labels) : null;
  const level: Level = prim?.level ?? "SAFE"; const col = prim ? index.colors[level] : "var(--fg3)";   // state 가 없으면 중립 회색 (안전으로 보이지 않게)
  const meta = index.thresholds.meta;
  const provisional = prim && ((prim.kind === "i2i1" && meta?.i2i1?.status === "provisional") || (prim.kind === "current_ratio" && meta?.current_ratio?.status === "provisional"));
  const note = (L.persistence ?? "{s}초 이상 지속될 때만 경보가 올라갑니다").replace("{s}", String(prim?.persistence ?? 3));
  const cc = scene?.cause_chain;
  const manual = last?.control_source === "manual" ? (last.manual_fault ?? null) : null;      // 패널 Q1: 수동 조작 중
  const mf = manual ? `${manual.phase_label ?? index.phase_labels[manual.phase as Phase] ?? manual.phase}상 ${manual.coil.replace("Coil_", "코일 ")}` : "";
  const why = manual
    ? (manual.turns > 0 ? `${mf} · ${manual.turns}턴 단락 (수동 주입, R_f ${manual.R_f_ohm} Ω)` : manual.unbalance > 0 ? "공급전압 불평형 (수동 주입, config 케이스)" : "결함 없음 (수동 · 정상)")
    : cc ? `${fill(cc.cause, sceneValues)} → ${fill(cc.mechanism, sceneValues)}` : scene?.why ? fill(String(scene.why), sceneValues) : step.label;
  const what = manual ? (p.manualAction ?? "") : cc ? fill(cc.action, sceneValues) : "";
  // ---- 전기 신호 (케이스별 파형·성분은 state 에서)
  const caseId = last?.case ?? step.electrical_case ?? "healthy";
  const csig = s?.case_signals?.[caseId];
  const rated = motor.spec.rated_line_current_a;
  const rms = s ? { A: s.current_rms_A.A[i], B: s.current_rms_A.B[i], C: s.current_rms_A.C[i] } : { A: 0, B: 0, C: 0 };
  const worst = PHASES.reduce((a, b) => (Math.abs(rms[b] / rated - 1) > Math.abs(rms[a] / rated - 1) ? b : a), "A" as Phase);
  const causePhase: Phase | null = s && s.cause_signal[i] === "current_ratio" && (PHASES as string[]).includes(s.cause_component[i]) ? (s.cause_component[i] as Phase) : null;
  const faultPhase: Phase | null = s && s.levels.current_ratio[i] !== "SAFE" ? (causePhase ?? worst) : (s && Math.abs(rms[worst] / rated - 1) > 0.05 ? worst : null);
  const fp = faultPhase ?? worst;
  const th = index.thresholds; const fg = "var(--fg)";
  const i1 = csig?.i1_A ?? 0, i2 = csig?.i2_A ?? 0, i0 = csig?.i0_A ?? 0;
  // §4.6: I₂ 막대는 위험 눈금(0.10·I₁)이 타일 높이의 70 % 에 오도록 — 그 이상은 꽉 채우고 ▲. I₁·I₀ 는 보조(회색·좁게, 정격 기준)
  const i2max = Math.max((th.i2i1.danger_from * i1) / rated / 0.7, 1e-6);
  const bars: Bar[] = [
    { key: "i1", label: "I₁", value: i1 / rated, max: 1.3, level: null, minor: true, tip: `정상분 I₁ ${i1.toFixed(2)} A (정격 ${rated} A 기준, 보조)` },
    { key: "i2", label: "I₂", value: Math.min(i2 / rated, i2max), max: i2max, level: s ? s.levels.i2i1[i] : null, over: i2 / rated > i2max, ticks: [{ at: th.i2i1.safe_below * i1 / rated, label: String(th.i2i1.safe_below) }, { at: th.i2i1.danger_from * i1 / rated, label: String(th.i2i1.danger_from) }], tip: `역상분 I₂ ${i2.toFixed(2)} A — I₂/I₁ ${s ? s.i2i1[i].toFixed(4) : "-"} (눈금 = 경고·위험 경계 × I₁, 위험 눈금 = 높이 70 %)` },
    { key: "i0", label: "I₀", value: i0 / rated, max: 1.3, level: null, minor: true, tip: `영상분 I₀ ${i0.toFixed(2)} A (보조)` },
  ];
  const trendSel: TrendSel = { kind: "i2i1" };
  const trendSpec = useMemo(() => specFor(index, motor, trendSel), [index, motor]);   // eslint-disable-line react-hooks/exhaustive-deps
  const trendName = nameOf(index, labels, "i2i1").plain;
  const injectT = caseId !== "healthy" ? step.t_start : null;
  const tNow = s ? s.t[i] : 0;
  const sT = p.sTrend ?? s;
  const es = last?.electrical_source;
  const shortOn = caseId.startsWith("itsc");
  // ---- 헤더 연결 뱃지
  const badge = conn === "live" ? { cls: "on", text: "LIVE" } : conn === "connecting" ? { cls: "wait", text: "연결 중…" } : conn === "lost" ? { cls: "lost", text: "끊김 · 재연결 중" } : { cls: "rec", text: "꺼짐" };
  const curN = p.scenes.find((x) => x.id === step.id)?.n ?? 0;
  const loadPct = last ? Math.round(last.load * 100) : null;
  const streamOk = stream.status === "live";
  return (
    <div className="la" style={{ ["--sv-col" as string]: col }}>
      {/* 헤더 */}
      <header className="la-head">
        <span className="brand">VIGENT</span>
        <span className="la-title">{A.title ?? "전기 상태 보드 · 실시간"}</span>
        <span className={"live-badge " + badge.cls} title={`Isaac state WebSocket ${p.wsUrl}${last?.perf?.fps ? ` · Isaac ${last.perf.fps} fps` : ""} — 클릭: 주소 바꾸기`}
              onClick={() => { const u = window.prompt("Isaac state WebSocket 주소", p.wsUrl); if (u && u.trim()) p.onUrl(u.trim()); }}>
          <i />{badge.text} <code>{p.wsUrl.replace(/^ws:\/\//, "")}</code></span>
        {p.isaacMode && p.isaacMode !== "electrical" && <span className="dim" title="Isaac 이 다른 모드로 실행 중 — 이 보드는 전기 신호만 보여준다">Isaac 모드 {p.isaacMode} · 전기 신호만</span>}
        <span className="grow" />
        <label className="la-scene">
          <span className="dim">{A.scenario ?? "시나리오"}</span>
          <select value={p.switching ? p.switching.n : (manual ? MANUAL_OPT : curN)} onChange={(e) => { const n = Number(e.target.value); if (n > 0) p.onScene(n); }} disabled={conn !== "live" || !p.scenes.length} title="선택하면 Isaac 에 play_scenario 명령을 보낸다 (그 장면 시작으로 점프). 패널로 조작 중이면 '수동 조작' 으로 표시되고, 장면을 고르면 시나리오로 돌아간다">
            {!p.scenes.length && <option value={0}>— Isaac 연결 대기 —</option>}
            {manual && <option value={MANUAL_OPT}>수동 조작 (아이작심 패널)</option>}
            {p.scenes.map((x) => <option key={x.n} value={x.n}>{/^\d+\./.test(x.label) ? x.label : `${x.n}. ${x.label}`}</option>)}
          </select>
          {p.switching && <span className="dim">전환 중…</span>}
          {!p.switching && p.lastSwitchMs !== null && <span className="dim" title="명령 전송 → 새 장면 첫 state 수신">전환 {p.lastSwitchMs} ms</span>}
        </label>
      </header>

      {/* 상태 띠 */}
      <section className="sv2-top la-top" aria-label="지금 상태">
        <span className="sv2-status" style={{ color: col }}>{prim ? `${index.icons[level]} ${index.labels_ko[level]}` : "—"}</span>
        {prim ? (
          <span className="sv2-cause" title={`${prim.name.term}${prim.name.tip ? " — " + prim.name.tip : ""}\n${prim.threshold}\n${prim.persistence > 0 ? note : ""}`}>
            <abbr title={`${prim.name.term}${prim.name.tip ? " — " + prim.name.tip : ""}`}>{prim.name.plain}</abbr> <b>{fmtVal(prim.kind, prim.value)}</b>
            {provisional && <span className="sv-tag" title={L.provisional_tip ?? "실측 기준선 확보 전까지 참고 기준"}>{L.provisional_tag ?? "임시"}</span>}
          </span>
        ) : <span className="sv2-cause dim">{conn === "live" ? "state 수신 대기…" : (A.state_waiting ?? "Isaac Sim 연결 대기")}</span>}
        {prim && <span className="la-thr" title={note}>{prim.threshold}{prim.persistence > 0 ? ` · ${prim.persistence}초 지속` : ""}</span>}
        <span className="sv2-motor" title={motor.name}>{motorLabel(motor, labels)}</span>
        {loadPct !== null && <span className="la-load" title="운전 부하 (Isaac state load — 패널에서 조작하지 않음)">부하 <b>{loadPct} %</b></span>}
        <span className="grow" />
        <span className="sv2-scene" title={last?.scene ? `장면 ${last.scene.elapsed_s}/${last.scene.duration_s} s` : ""}>{manual ? `수동 조작 · ${mf}${manual.turns > 0 ? ` · ${manual.turns}턴` : ""}` : <>{curN ? `장면 ${curN}/${p.scenes.length} ` : ""}{scene?.title ?? step.label}{last?.scene ? ` · ${fmtT(last.scene.elapsed_s)}` : ""}</>}</span>
        {conn === "lost" && s && <span className="la-lost" title={A.state_lost}>⟳ {A.state_lost ?? "끊김 — 마지막 값"}</span>}
      </section>

      {/* 2×2 */}
      <section className="sv2-tiles la-tiles" aria-label="그림">
        <div className="tile tile-isaac">
          <div className="tile-h"><span className="t">{T.isaac ?? A.isaac_tile ?? "아이작심 실시간"}</span>
            <span className="dim" title={`JPEG ${stream.size ? `${stream.size[0]}×${stream.size[1]}` : ""} · 지연 = 수신 시각 − 캡처 시각 (같은 PC)`}>{A.view_label ?? "반절 반투명"}{streamOk ? ` · ${stream.fps} fps · 지연 ${stream.latencyMs ?? "-"} ms` : ""}</span>
            <b className="big" style={{ color: shortOn ? index.colors[s ? s.levels.i2i1[i] : "SAFE"] : undefined }}>{shortOn && es?.turns ? `단락 ${es.turns}턴` : ""}</b></div>
          <div className="tile-b tile-canvas">
            <canvas ref={p.canvasRef} className={"la-canvas" + (streamOk ? "" : " stale")} width={1280} height={720} />
            {shortOn && streamOk && <span className="la-glow" style={{ color: index.colors[s ? s.levels.i2i1[i] : "WARN"] }} title={`Coil_01 단락 루프${es?.i_f_A ? ` · I_f ${es.i_f_A} A` : ""}${last?.p_loop_total_W ? ` · 손실 ${last.p_loop_total_W} W` : ""}`}>● {A.short_badge ?? "단락 코일 발광"}{es?.i_f_A ? ` · ${es.i_f_A.toFixed(1)} A` : ""}</span>}
            {!streamOk && <div className="la-overlay"><b>{stream.status === "connecting" ? (A.isaac_connecting ?? "아이작심 연결 중…") : (A.isaac_lost ?? "아이작심 연결 끊김 — 재연결 중")}</b><span className="dim">{stream.frames ? "마지막 프레임 유지" : "Isaac Sim 을 --live 로 실행하면 뷰포트가 여기에 나옵니다"}</span></div>}
          </div>
        </div>
        <div className="tile">
          <div className="tile-h"><span className="t">{T.wave ?? "전류 파형"}</span><span className="dim">최근 2주기</span>
            <b className="big" style={s ? { color: index.colors[s.levels.current_ratio[i]] } : undefined}>{s ? `${index.phase_labels[fp]} ${rms[fp].toFixed(2)} A (${(rms[fp] / rated).toFixed(2)}×)` : ""}</b>
            {loadPct !== null && <span className="la-load-s" title="운전 부하">부하 {loadPct} %</span>}</div>
          <div className="tile-b">{csig ? <WaveTile wf={csig.waveform} ratedA={rated} faultPhase={faultPhase} phaseLabels={index.phase_labels} rmsA={rms} /> : <div className="tile-na">{s ? "파형 없음 (Isaac 스트림이 구 버전)" : "—"}</div>}</div>
        </div>
        <div className="tile">
          <div className="tile-h"><span className="t">{T.comp ?? "전류 성분"}</span><span className="dim">정격 대비</span>
            <b className="big" style={s ? { color: index.colors[s.levels.i2i1[i]] } : undefined} title={plainOf(labels, "i2i1", "I₂/I₁").term}>{s ? s.i2i1[i].toFixed(3) : "—"}</b></div>
          <div className="tile-b">{csig ? <BarsTile bars={bars} colors={index.colors} fg={fg} /> : <div className="tile-na">—</div>}</div>
        </div>
        <div className="tile">
          <div className="tile-h"><span className="t">{T.trend ?? "추세"}</span><span className="dim">{trendName} · {(() => { const w = sc.total_duration_s - (sc.t_min ?? 0); return w < 90 ? `최근 ${Math.round(w)} 초` : `최근 ${Math.round(w / 60)} 분`; })()}</span></div>
          <div className="tile-b tile-trend">
            {sT && sT.t.length >= 2 ? <TrendChart index={index} motor={motor} series={sT} sel={trendSel} spec={trendSpec} t={tNow} onSeek={() => undefined} scenario={sc} plain yName={trendName} markT={injectT} relativeTo={sc.total_duration_s} /> : <div className="tile-na">—</div>}
            {sT && <div className="sv2-strip-row"><div className="st-strip" title="색: 판정 상태 · 숫자: 장면"><StatusStrip index={index} s={sT} total={sc.total_duration_s} from={sc.t_min ?? 0} />
              {sc.steps.map((st) => <span key={st.id + st.t_start} className={"st-ch" + (st.id === step.id && st.t_start === step.t_start ? " cur" : "")} style={{ left: `${((st.t_start - (sc.t_min ?? 0)) / Math.max(sc.total_duration_s - (sc.t_min ?? 0), 1e-6)) * 100}%`, width: `${((st.t_end - st.t_start) / Math.max(sc.total_duration_s - (sc.t_min ?? 0), 1e-6)) * 100}%` }} title={st.label}>{st.n || "·"}</span>)}
            </div></div>}
          </div>
        </div>
      </section>

      {/* 하단 띠 */}
      <section className="sv2-foot la-foot" aria-label="원인과 조치">
        <span className="k">{L.why ?? "왜?"}</span><span className="v" title={why}><Plain text={why} labels={labels} /></span>
        <span className="k">{L.what ?? "무엇을?"}</span><span className="v" title={what}>{what ? <Plain text={what} labels={labels} /> : "—"} {prim && <span style={{ color: col }}>({index.labels_ko[level]} 단계)</span>}</span>
        <button className="sv-chip sv-honesty" onClick={p.openDrawer} title={`${index.honesty.label} — ${index.honesty.lines.join(" · ")}`}>{L.honesty_chip ?? "시뮬레이션 추정값 · 근거 보기 ›"}</button>
      </section>
    </div>
  );
}
