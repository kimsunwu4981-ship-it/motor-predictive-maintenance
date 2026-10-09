import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Mode } from "../data";
import { fmtT } from "../data";
import { PlaybackContext, useClockPlayback } from "../state/playback";
import { fill } from "../live/types";
import { Gauge } from "../status/Gauge";
import { TrendChart, type TrendSel } from "../status/TrendChart";
import {
  causeLine, fmtSim, gaugeCurrent, gaugeLoHi, gaugeTemp, gaugeVib, idxAt, levelOf, loadStatusContent,
  simElapsed, stepAt, worse, KINDS, PHASES,
  type FleetIndex, type Kind, type Level, type MotorInfo, type MotorSeries, type StatusContent, bearingLevel } from "../status/data";
import { pickSource, appendSample, type StatusSource } from "../status/source";
import { useLiveSession } from "../live/session";
import { LiveToggle, LiveBanner } from "../live/LiveToggle";
import { ControlPanel } from "../live/ControlPanel";
import { liveSteps, pageMode, toMotorSeries, useLivePlayback } from "../live/livedata";
import type { Step } from "../data";
import { applyNameplates, loadNameplates, saveNameplates, parseField, yamlSnippet, NAMEPLATE_FIELDS, type Nameplates } from "../status/nameplate";
import "../status/status.css";

// VIGENT 모터 상태 보드 (TASK_다중모터 §7): 5종 모터 카드 → 선택 모터 상세(게이지 8) → 원인과 조치 → 재생 바·추세 → 기준표 탭.
// 숫자는 전부 public/data/fleet/*.json (export_status_data.py). 판정은 엔진이 로그에 써 둔 status/cause 를 그대로 쓴다.
//   #/status?m=M3&t=27.5   특정 모터·시각으로 열기 (스크린샷·확인용)
const TEMP_GAUGES = ["winding", "bearing_de", "rotor", "shaft"];

export function StatusBoard() {
  const source = useMemo(() => pickSource(new URLSearchParams(window.location.hash.split("?")[1] ?? "")), []);   // ?live=<url> → 실측 스트림
  const [index, setIndex] = useState<FleetIndex | null>(null);
  const [content, setContent] = useState<StatusContent | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    Promise.all([source.loadIndex(), loadStatusContent()]).then(([i, c]) => { setIndex(i); setContent(c); }).catch((e) => setErr(String(e)));
  }, [source]);
  if (err) return <div style={{ padding: 30 }}>데이터를 읽지 못했습니다.<br /><code>{err}</code><div className="dim">{source.kind === "live" ? "라이브 소스 URL 아래에 index.json 이 있어야 합니다." : "dashboard/tools/export_status_data.py 를 먼저 실행하세요."}</div></div>;
  if (!index || !content) return <div style={{ padding: 30 }} className="muted">불러오는 중…</div>;
  return <Board index0={index} content={content} source={source} />;
}

function Board({ index0, content, source }: { index0: FleetIndex; content: StatusContent; source: StatusSource }) {
  const params = useMemo(() => new URLSearchParams(window.location.hash.split("?")[1] ?? ""), []);
  // 명판값 입력 (P5): localStorage 의 입력값을 index 에 덮어쓴다. 출처 라벨이 바뀐다.
  const [nameplates, setNameplates] = useState<Nameplates>(() => loadNameplates());
  const index = useMemo(() => applyNameplates(index0, nameplates), [index0, nameplates]);
  const [npOpen, setNpOpen] = useState<boolean>(() => params.get("np") === "1");
  const ids = index.motors.map((m) => m.id);
  const [sel, setSel] = useState<string>(() => (ids.includes(params.get("m") ?? "") ? (params.get("m") as string) : ids[0]));
  // 모터별 모드·시각 (데모 위치에서 시작, 재생하면 그 모터의 시각만 움직인다)
  const [modes, setModes] = useState<Record<string, Mode>>(() => Object.fromEntries(index.motors.map((m) => [m.id, m.demo.mode])));
  const [pos, setPos] = useState<Record<string, number>>(() => {
    const p = Object.fromEntries(index.motors.map((m) => [m.id, m.demo.t_s]));
    const t0 = Number(params.get("t")); if (Number.isFinite(t0) && params.get("t") !== null) p[sel] = t0;
    return p;
  });
  const [series, setSeries] = useState<Record<string, MotorSeries>>({});
  useEffect(() => {   // 모든 모터의 (현재 모드) 시계열을 읽는다 — 카드 상태 계산용
    for (const m of index.motors) {
      const key = `${m.id}/${modes[m.id]}`;
      if (series[key]) continue;
      source.loadSeries(index, m.id, modes[m.id]).then((s) => setSeries((prev) => ({ ...prev, [key]: s })));
    }
  }, [index, modes, series, source]);
  // 라이브 소스: 스트림 샘플을 해당 모터 시계열 끝에 붙인다 (재생 모드에서는 아무 일도 없다)
  useEffect(() => {
    if (!source.subscribe) return;
    return source.subscribe((x) => {
      const m = index.motors.find((q) => q.id === x.motor); if (!m) return;
      setSeries((prev) => { const k = `${x.motor}/${x.mode}`; return prev[k] ? { ...prev, [k]: appendSample(prev[k], x, m.spec.rated_line_current_a) } : prev; });
    });
  }, [source, index]);

  // ---- 라이브 (TASK 실시간 §6): Isaac --live 스트림의 모터 하나가 LIVE, 나머지 카드는 배치 로그(흐리게). 끊기면 자동으로 전부 녹화.
  const live = useLiveSession();
  const liveMotor = live.active ? live.last!.motor_id : null;
  const liveMode: Mode | null = live.active ? pageMode(live.last!.mode) : null;
  const liveSeries = useMemo(() => (live.active && liveMotor ? toMotorSeries(live.buffer, index, series[`${liveMotor}/${liveMode}`] ?? null) : null),
    [live.active, live.version, live.buffer, index, liveMotor, liveMode]);   // eslint-disable-line react-hooks/exhaustive-deps
  const isLiveSel = !!liveSeries && sel === liveMotor;
  const motor = index.motors.find((m) => m.id === sel)!;
  const mode: Mode = isLiveSel && liveMode ? liveMode : modes[sel];
  const scRec = index.scenarios[mode];
  const liveStepList: Step[] = useMemo(() => (liveSeries ? liveSteps(live.buffer, index.scenarios[mode].steps.map((s) => ({ ...s, source: "", video_start: 0, video_end: 0, highlight: false, clip: null }))) : []),
    [liveSeries, live.buffer, index, mode]);
  const sc = useMemo(() => (isLiveSel ? { ...scRec, total_duration_s: live.buffer.tEnd, t_min: live.buffer.tMin, steps: liveStepList as unknown as typeof scRec.steps } : scRec), [isLiveSel, scRec, live.buffer, liveStepList, live.version]);  // eslint-disable-line react-hooks/exhaustive-deps
  const pbClock = useClockPlayback(scRec, pos[sel]);
  const pbLive = useLivePlayback(live.buffer, live.version, liveStepList, live.send);
  const pb = isLiveSel ? pbLive : pbClock;
  useEffect(() => { if (liveMotor && ids.includes(liveMotor)) setSel(liveMotor); }, [liveMotor]);   // 스트림이 붙으면 그 모터를 선택  eslint-disable-line react-hooks/exhaustive-deps
  const x0 = isLiveSel ? (sc.t_min ?? 0) : 0;                  // 재생 바·추세의 창 시작
  const span = Math.max(sc.total_duration_s - x0, 1e-6);
  // 선택이 바뀌면 그 모터의 저장 시각으로, 재생 중이면 선택 모터의 시각을 저장한다
  const selRef = useRef(sel);
  useEffect(() => { if (selRef.current !== sel) { selRef.current = sel; if (!(liveMotor && sel === liveMotor)) { pb.pause(); pb.seek(pos[sel] ?? 0); } } }, [sel]);   // 라이브 모터로 바뀔 때는 LIVE 따라가기 유지  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setPos((p) => (Math.abs((p[sel] ?? 0) - pb.t) < 1e-3 ? p : { ...p, [sel]: pb.t })); }, [pb.t, sel]);
  const toggleMode = useCallback(() => {
    const nm: Mode = mode === "mechanical" ? "electrical" : "mechanical";
    setModes((m) => ({ ...m, [sel]: nm })); pb.pause(); pb.seek(0); setPos((p) => ({ ...p, [sel]: 0 }));
  }, [mode, sel, pb]);

  const [present, setPresent] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => { try { return (localStorage.getItem("vigent-theme") as "dark" | "light") || "dark"; } catch { return "dark"; } });
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); try { localStorage.setItem("vigent-theme", theme); } catch { /* */ } }, [theme]);
  const [tab, setTab] = useState<"thr" | "spec" | "gloss">("thr");
  const [ctl, setCtl] = useState<boolean>(() => params.get("ctl") === "1");                                   // K: 제어 패널 (라이브)
  const [trend, setTrend] = useState<TrendSel | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName ?? "")) return;
      if (npOpen) { if (e.key === "Escape") setNpOpen(false); return; }
      if (e.key === " ") { e.preventDefault(); pb.toggle(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); pb.gotoStep(pb.stepIndex + 2); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); pb.gotoStep(pb.stepIndex); }
      else if (e.key === "f" || e.key === "F") setPresent((p) => !p);
      else if (e.key === "k" || e.key === "K") setCtl((c) => !c);
      else if ((e.key === "m" || e.key === "M") && !isLiveSel) toggleMode();
      else if (e.key === "Escape") setPresent(false);
      else if (e.key >= "1" && e.key <= "9") { const id = ids[Number(e.key) - 1]; if (id) setSel(id); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pb, ids, toggleMode, npOpen, isLiveSel]);
  const npCount = Object.keys(nameplates).length;

  const cur = isLiveSel ? liveSeries! : series[`${sel}/${mode}`];
  const i = cur ? idxAt(cur.t, pb.t) : 0;
  const step = isLiveSel ? (liveStepList[pb.stepIndex] ?? liveStepList[liveStepList.length - 1] ?? stepAt(sc, pb.t)) : stepAt(sc, pb.t);
  const scene = content.narration[mode][step.id];
  const cl = cur ? causeLine(index, cur, i) : null;
  // 추세 차트 기본 선택: 원인 신호 (없으면 DE 베어링 온도)
  const trendSel: TrendSel = trend ?? (cur && cur.status[i] !== "SAFE" ? { kind: cur.cause_signal[i] as Kind, component: cur.cause_component[i] } : { kind: "temperature", component: "bearing_de" });
  const trendSpec = useMemo(() => specFor(index, motor, trendSel), [index, motor, trendSel]);

  return (
    <PlaybackContext.Provider value={pb}>
      <div className={"dash st" + (present ? " present" : "")}>
        <div className="panel hud">
          <span className="brand">VIGENT</span>
          <span className="mode">디지털 트윈 · 모터 상태 보드</span>
          <span className="st-legend">{(["SAFE", "WARN", "DANGER"] as Level[]).map((l) => <span key={l}><i style={{ background: index.colors[l] }} />{index.icons[l]} {index.labels_ko[l]}</span>)}</span>
          <span className="grow" />
          {!present && <a className="btn" href="#/mechanical" title="기계적 결함 실시간 해설 대시보드 (M5 애니메이션)">기계 해설 ↗</a>}
          {!present && <a className="btn" href="#/electrical" title="전기적 결함 실시간 해설 대시보드 (M5 애니메이션)">전기 해설 ↗</a>}
          {!present && <button className="b-theme" onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))} title="테마">{theme === "dark" ? "☀" : "☾"}</button>}
          <LiveToggle live={live} />
          {live.enabled && <button className="b-ctl" onClick={() => setCtl((c) => !c)} title="K 키: 결함 주입·부하·배속·모터 전환 (라이브)">{ctl ? "☑ 제어 K" : "☐ 제어 K"}</button>}
          <button onClick={() => setPresent((p) => !p)} title="F 키">{present ? "발표 종료 Esc" : "발표 F"}</button>
          <span className="honesty st-honesty" title={`${index.honesty.itsc_note} · 데이터: ${source.label}`}>
            <b>{index.honesty.label}{liveSeries ? " · LIVE (Isaac Sim)" : source.kind === "live" ? " · 실측 스트림" : ""}</b>
            <span>{(npCount ? [`명판값 입력: ${Object.keys(nameplates).join(", ")} (나머지 대표 사양)`, ...index.honesty.lines.slice(1)] : index.honesty.lines).join(" · ")}</span>
          </span>
          <LiveBanner live={live} index={index} />
        </div>

        <div className="st-cards">
          {index.motors.map((m, n) => {
            const isLive = !!liveSeries && m.id === liveMotor;
            const s = isLive ? liveSeries! : series[`${m.id}/${modes[m.id]}`];
            const t = isLive ? (m.id === sel ? pb.t : live.buffer.tEnd) : (pos[m.id] ?? m.demo.t_s);
            const k = s ? idxAt(s.t, t) : 0;
            const lv: Level = s ? s.status[k] : "SAFE";
            const c = s ? causeLine(index, s, k) : null;
            const st = isLive ? (liveStepList[liveStepList.length - 1] ?? stepAt(index.scenarios[modes[m.id]], 0)) : stepAt(index.scenarios[modes[m.id]], t);
            return (
              <div key={m.id} className={"st-card" + (m.id === sel ? " sel" : "") + (liveSeries && !isLive ? " off" : "")} onClick={() => setSel(m.id)} style={{ borderColor: m.id === sel ? index.colors[lv] : undefined }}>
                <div className="st-card-h"><span className="kbd">{n + 1}</span><b>{m.id}</b> <span className="muted">{m.tags.hoist_ton ?? ""} · {m.spec.rated_power_kw} kW {m.spec.poles}극</span>{isLive && <span className="st-live">● LIVE</span>}</div>
                <div className="st-badge" style={{ background: index.colors[lv] }}>{index.icons[lv]} {index.labels_ko[lv]}</div>
                <div className="st-cause">{c ? c.head : "불러오는 중…"}</div>
                <div className="dim st-foot">{isLive ? `LIVE · ${st.label} · ${fmtT(t)}` : liveSeries ? `라이브 아님 · 배치 로그 · ${st.label}` : `${modes[m.id] === "mechanical" ? "기계" : "전기"} 시나리오 · ${st.label} · ${fmtT(t)}`}</div>
              </div>
            );
          })}
        </div>

        <div className="st-main">
          <div className="panel st-detail">
            <div className="panel-h">② 선택 모터 상세 <span className="muted">{motor.id} · {motor.name}</span><span className="grow" />
              <span className={"dim" + (motor.spec.source === "nameplate" ? " st-np-on" : "")}>{motor.spec.source === "nameplate" ? `명판값 (입력 ${nameplates[sel]?.entered_at ?? ""})` : "대표 사양 (명판 아님)"}</span>
              {!present && <button className="b-np" onClick={() => setNpOpen(true)} title="이 모터의 명판값을 입력하면 출처가 nameplate 로 바뀐다">명판값 입력</button>}</div>
            <div className="panel-b">
              <div className="st-spec">
                <span><i>용도</i>{motor.tags.hoist_ton ?? "-"} 호이스트{motor.tags.hoist_speed ? ` · 권상 ${motor.tags.hoist_speed}` : ""}</span>
                <span><i>정격</i>{motor.spec.rated_power_kw} kW · {motor.spec.poles}극 · {motor.spec.rated_rpm} rpm (동기 {motor.spec.sync_rpm})</span>
                <span><i>전원</i>{motor.spec.voltage_v} V {motor.spec.frequency_hz} Hz · {motor.spec.connection === "delta" ? "Δ결선" : motor.spec.connection}</span>
                <span><i>정격 전류</i>선 <b>{motor.spec.rated_line_current_a} A</b> · 상 {motor.spec.rated_phase_current_a} A</span>
                <span><i>프레임·베어링</i>{motor.spec.frame} · DE {motor.spec.bearing_de} / NDE {motor.spec.bearing_nde}</span>
                <span><i>진동 규격</i><b>{motor.vibration.standard.split(" (")[0]}</b> · 경고 {motor.vibration.watch_mms} / 위험 {motor.vibration.act_mms} mm/s</span>
              </div>
              {cur ? <Gauges index={index} motor={motor} s={cur} i={i} onPick={setTrend} picked={trendSel} /> : <div className="muted">시계열 불러오는 중…</div>}
            </div>
          </div>

          <div className="panel st-cause-p">
            <div className="panel-h">③ 원인과 조치 <span className="grow" /><span className="dim">판정: engine/thresholds.py (히스테리시스 {Math.round(index.thresholds.hysteresis_fraction * 100)} % · 지속 {index.thresholds.persistence_s.current_ratio} s)</span></div>
            <div className="panel-b">
              {cl && cur && (
                <div className="st-head" style={{ borderColor: index.colors[cl.level], background: `color-mix(in srgb, ${index.colors[cl.level]} 18%, var(--panel2))` }}>
                  <div className="st-head-l"><span className="st-badge" style={{ background: index.colors[cl.level] }}>{index.icons[cl.level]} {index.labels_ko[cl.level]}</span><b>{cl.head}</b></div>
                  <div className="dim">{cl.detail}</div>
                  <div className="st-sig">{KINDS.map((k) => <span key={k} style={{ borderColor: index.colors[cur.levels[k][i]] }}><i style={{ background: index.colors[cur.levels[k][i]] }} />{index.signals[k].label.split(" (")[0]}</span>)}</div>
                </div>
              )}
              <div className="st-scene"><span className="dim">{isLiveSel ? "LIVE · 장면" : "장면"} {step.n}{isLiveSel ? "" : `/${sc.steps.length}`}</span> <b>{scene?.title ?? step.label}</b> <span className="dim">— {fill(step.subtitle, cur?.scene_values[step.id])}</span></div>
              {scene?.cause_chain ? (
                <div className="chain fade" key={`${sel}-${step.id}`}>
                  {(["cause", "mechanism", "effect", "action"] as const).map((k, n) => (
                    <div key={k} className={"chain-card c" + n}>
                      <div className="chain-k">{["원인", "메커니즘", "결과", "조치"][n]}</div>
                      <div>{fill(scene.cause_chain![k], cur?.scene_values[step.id])}</div>
                    </div>
                  ))}
                </div>
              ) : <div className="muted">이 장면의 cause_chain 없음 (narration.yaml)</div>}
              <div className="st-nav">
                <a className="btn primary" href={`#/${mode}?t=${pb.t.toFixed(1)}`}>{mode === "mechanical" ? "기계" : "전기"} 해설 대시보드에서 이 장면 보기 ↗</a>
                <span className="dim">해설 영상·설명은 M5(22 kW, 현 애니메이션 기준) 로 만든 것이다{sel !== "M5" ? ` — ${sel} 의 수치는 이 보드에서 확인` : ""}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="panel st-bottom">
          <div className="st-bar">
            <button onClick={pb.toggle} title="Space">{isLiveSel ? (pb.playing ? "❚❚ 최근 기록 보기" : "▶ LIVE 복귀") : (pb.playing ? "⏸ 일시정지" : "▶ 재생")}</button>
            {!isLiveSel && <button onClick={toggleMode} title="M 키: 기계 ↔ 전기 시나리오">{mode === "mechanical" ? "기계 시나리오" : "전기 시나리오"} ⇄</button>}
            <span className="time">{isLiveSel ? (pb.playing ? `LIVE · 최근 ${Math.round(live.cfg.window_s / 60)} 분` : `${fmtT(pb.t)} (버퍼)`) : `${fmtT(pb.t)} / ${fmtT(sc.total_duration_s)}`}</span>
            {mode === "mechanical" && <span className="tc"><span className="tc-scale">배속 ×<b>{step.time_scale}</b></span><span className="tc-elapsed">시뮬 경과 <b>{fmtSim(simElapsed(sc, pb.t))}</b></span></span>}
            <div className="st-strip" onClick={(e) => { const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect(); pb.seek(x0 + ((e.clientX - r.left) / r.width) * span); }} title={isLiveSel ? "클릭: 버퍼 안 그 시점 보기 (최근 기록) · 색: 판정 상태" : "클릭: 이동 · 색: 판정 상태"}>
              {cur && <StatusStrip index={index} s={cur} total={sc.total_duration_s} from={x0} />}
              {sc.steps.map((s) => <span key={s.id + s.t_start} className={"st-ch" + (s.id === step.id && (!isLiveSel || s.t_start === step.t_start) ? " cur" : "")} style={{ left: `${((s.t_start - x0) / span) * 100}%`, width: `${((s.t_end - s.t_start) / span) * 100}%` }} title={s.label}>{s.n || "·"}</span>)}
              <i className="st-cur" style={{ left: `${((pb.t - x0) / span) * 100}%` }} />
            </div>
            <span className="chips">
              {KINDS.map((k) => <span key={k} className={"chip" + (trendSel.kind === k ? " on" : "")} onClick={() => setTrend({ kind: k, component: k === "temperature" ? (trendSel.kind === "temperature" ? trendSel.component : "bearing_de") : undefined })}>{index.signals[k].label.split(" (")[0]}</span>)}
              {trendSel.kind === "temperature" && TEMP_GAUGES.map((n) => <span key={n} className={"chip" + (trendSel.component === n ? " on" : "")} onClick={() => setTrend({ kind: "temperature", component: n })}>{index.node_labels[n]}</span>)}
            </span>
          </div>
          {cur && <TrendChart index={index} motor={motor} series={cur} sel={trendSel} spec={trendSpec} t={pb.t} onSeek={pb.seek} scenario={isLiveSel ? sc : undefined} />}
        </div>

        <ControlPanel live={live} open={ctl} onClose={() => setCtl(false)} />
        {npOpen && <NameplateForm motor={index0.motors.find((m) => m.id === sel)!} current={nameplates[sel]} onClose={() => setNpOpen(false)}
          onSave={(np) => { const n = { ...nameplates }; if (np) n[sel] = np; else delete n[sel]; setNameplates(n); saveNameplates(n); setNpOpen(false); }} />}
        {!present && (
          <div className="panel tabs">
            <div className="tabbar">
              <button className={tab === "thr" ? "on" : ""} onClick={() => setTab("thr")}>임계값 기준표</button>
              <button className={tab === "spec" ? "on" : ""} onClick={() => setTab("spec")}>모터 사양표</button>
              <button className={tab === "gloss" ? "on" : ""} onClick={() => setTab("gloss")}>용어 풀이</button>
              <span className="grow" /><span className="dim">키: 1~5 모터 · Space 재생 · ←→ 장면 · M 모드 · F 발표</span>
            </div>
            <div className="tabbody">
              {tab === "thr" && <ThresholdTab index={index} />}
              {tab === "spec" && <SpecTab index={index} nameplates={nameplates} />}
              {tab === "gloss" && <dl className="gloss">{content.glossary.map((g) => <div key={g.term}><dt>{g.term}</dt><dd>{g.text}</dd></div>)}</dl>}
            </div>
          </div>
        )}
      </div>
    </PlaybackContext.Provider>
  );
}

function specFor(index: FleetIndex, motor: MotorInfo, sel: TrendSel) {
  if (sel.kind === "temperature") return gaugeTemp(index, sel.component ?? "bearing_de");
  if (sel.kind === "current_ratio") return gaugeCurrent(index);
  if (sel.kind === "i2i1") return gaugeLoHi(index.thresholds.i2i1, 0.3, "");
  if (sel.kind === "vibration") return gaugeVib(motor.vibration);
  if (sel.kind === "bearing_kurtosis") return gaugeLoHi(index.thresholds.bearing.kurtosis, 8, "");
  return gaugeLoHi(index.thresholds.bearing.hf_ratio, 5, "배");
}

// 신호별 게이지 9개: 온도 4 · 전류 비율 · I₂/I₁ · 진동 · 베어링 kurtosis · 베어링 고주파 RMS 배율 (베어링 종합 = 둘 중 나쁜 쪽). 모터별 임계값(진동 규격·정격 전류)이 자동 반영된다.
function Gauges({ index, motor, s, i, onPick, picked }: { index: FleetIndex; motor: MotorInfo; s: MotorSeries; i: number; onPick: (t: TrendSel) => void; picked: TrendSel }) {
  const cur = gaugeCurrent(index);
  const rated = motor.spec.rated_line_current_a;                                       // 명판값을 넣으면 여기서 바로 바뀐다 (판정은 배치 재실행 후)
  const ratios = PHASES.map((p) => ({ key: index.phase_labels[p], value: s.current_rms_A[p][i] / rated, p }));
  const worstPhase = ratios.reduce((a, b) => (Math.abs(b.value - 1) > Math.abs(a.value - 1) ? b : a));
  const item = (key: string, sel: TrendSel, node: React.ReactNode) => (
    <div key={key} className={"g-wrap" + (picked.kind === sel.kind && (sel.kind !== "temperature" || picked.component === sel.component) ? " on" : "")} onClick={() => onPick(sel)}>{node}</div>
  );
  return (
    <div className="st-gauges">
      {TEMP_GAUGES.map((n) => item(n, { kind: "temperature", component: n },
        <Gauge index={index} title={`${index.node_labels[n] ?? n} 온도`} unit="°C" spec={gaugeTemp(index, n)} value={s.temperature_C[n][i]} />))}
      {item("cur", { kind: "current_ratio" },
        <Gauge index={index} title={`전류 / 정격 (${motor.spec.rated_line_current_a} A)`} unit="×" spec={cur} value={worstPhase.value}
          markers={ratios.map((r) => ({ key: r.key, value: r.value }))} judged={s.levels.current_ratio[i]}
          note={ratios.map((r) => `${r.key} ${s.current_rms_A[r.p][i].toFixed(1)} A`).join(" · ") + (motor.spec.source === "nameplate" ? " · 명판 정격 기준 (판정은 배치 재실행 전)" : "")} />)}
      {item("i2i1", { kind: "i2i1" },
        <Gauge index={index} title="I₂/I₁ 역상 전류비" unit="" spec={gaugeLoHi(index.thresholds.i2i1, 0.3, "")} value={s.i2i1[i]} judged={s.levels.i2i1[i]} />)}
      {item("vib", { kind: "vibration" },
        <Gauge index={index} title="진동 속도 RMS" unit="mm/s" spec={gaugeVib(motor.vibration)} value={s.vibration_mms[i]} judged={s.levels.vibration[i]} note={motor.vibration.standard.split(" (")[0] + (motor.vibration.plan_mms < motor.vibration.act_mms ? ` · ${motor.vibration.plan_mms} 부터 정비 계획` : "")} />)}
      {item("brg_k", { kind: "bearing_kurtosis" },
        <Gauge index={index} title={`베어링 kurtosis · 종합 ${index.icons[bearingLevel(s, i)]} ${index.labels_ko[bearingLevel(s, i)]}`} unit="" spec={gaugeLoHi(index.thresholds.bearing.kurtosis, 8, "")} value={s.bearing_kurtosis[i]} judged={s.levels.bearing_kurtosis[i]}
          note={"주 지표 · 모터 공통 경계 · 시뮬레이션: 결함별 등가값 (thermal.yaml)" + (s.bearing_site_hint?.[i] ? ` · 결함 부위 추정 ${s.bearing_site_hint[i]}` : "")} />)}
      {item("brg_h", { kind: "bearing_hf_ratio" },
        <Gauge index={index} title="베어링 고주파 RMS (정상 대비)" unit="배" spec={gaugeLoHi(index.thresholds.bearing.hf_ratio, 5, "배")} value={s.bearing_hf_ratio[i]} judged={s.levels.bearing_hf_ratio[i]}
          note={"보조 지표 · 기준선 " + (motor.bearing_hf_baseline?.rms_g != null ? `${motor.bearing_hf_baseline.rms_g} g (${motor.bearing_hf_baseline.source})` : "미설정") + " · 종합은 둘 중 나쁜 쪽"} />)}
    </div>
  );
}

// 재생 바 배경: 시각별 판정 상태 색 (구간 병합)
function StatusStrip({ index, s, total, from = 0 }: { index: FleetIndex; s: MotorSeries; total: number; from?: number }) {
  const segs = useMemo(() => {
    const out: { from: number; to: number; lv: Level }[] = [];
    for (let k = 0; k < s.t.length; k++) {
      const lv = s.status[k];
      const last = out[out.length - 1];
      if (last && last.lv === lv) last.to = s.t[k]; else out.push({ from: s.t[k], to: s.t[k], lv });
    }
    return out;
  }, [s]);
  return <>{segs.map((g, n) => <i key={n} className="st-seg" style={{ left: `${((g.from - from) / (total - from)) * 100}%`, width: `${Math.max(0.2, ((g.to - g.from) / (total - from)) * 100)}%`, background: index.colors[g.lv] }} />)}</>;
}

function ThresholdTab({ index }: { index: FleetIndex }) {
  const th = index.thresholds;
  const t = th.temperature, r = th.current_ratio;
  const groups = new Map<string, string[]>();
  for (const m of index.motors) { const k = `${m.vibration.watch_mms}|${m.vibration.act_mms}|${m.vibration.standard}`; groups.set(k, [...(groups.get(k) ?? []), m.id]); }
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>세 단계 <b>안전 / 경고 / 위험</b>. 모터 전체 상태는 모든 신호 중 가장 나쁜 등급이고, 원인 신호를 항상 함께 표시합니다.
        등급 하향은 임계값의 {Math.round(th.hysteresis_fraction * 100)} % 안쪽으로 들어와야 바뀌고(히스테리시스), 전류·진동·I₂/I₁·베어링 지표(kurtosis·고주파 배율)는 {th.persistence_s.current_ratio} s 이상 지속돼야 상향됩니다(돌입전류 무시).</p>
      <table className="grid">
        <thead><tr><th>신호</th><th><span className="sw" style={{ background: index.colors.SAFE }} />{index.icons.SAFE} 안전</th><th><span className="sw" style={{ background: index.colors.WARN }} />{index.icons.WARN} 경고</th><th><span className="sw" style={{ background: index.colors.DANGER }} />{index.icons.DANGER} 위험</th><th>근거 · 적용</th></tr></thead>
        <tbody>
          <tr><td>베어링 온도</td><td>&lt; {t.bearing.safe_below} °C</td><td>{t.bearing.safe_below}~{t.bearing.danger_from}</td><td>≥ {t.bearing.danger_from}</td><td>{t.bearing.note ?? "그리스 수명"} · 모터 공통</td></tr>
          <tr><td>권선 온도</td><td>&lt; {t.winding.safe_below}</td><td>{t.winding.safe_below}~{t.winding.danger_from}</td><td>≥ {t.winding.danger_from}</td><td>{t.winding.note ?? "F종 절연"} · 모터 공통</td></tr>
          <tr><td>로터 온도</td><td>&lt; {t.rotor.safe_below}</td><td>{t.rotor.safe_below}~{t.rotor.danger_from}</td><td>≥ {t.rotor.danger_from}</td><td>{t.rotor.note ?? ""} 모터 공통</td></tr>
          <tr><td>축·하우징 온도</td><td>&lt; {t.default.safe_below}</td><td>{t.default.safe_below}~{t.default.danger_from}</td><td>≥ {t.default.danger_from}</td><td>{t.default.note ?? ""} 모터 공통</td></tr>
          <tr><td>전류 비율 r = I / I정격</td><td>{r.safe_low} ≤ r ≤ {r.safe_high}</td><td>{r.safe_high} &lt; r ≤ {r.danger_over} 또는 {r.danger_under} ≤ r &lt; {r.safe_low}</td><td>r &gt; {r.danger_over} 또는 r &lt; {r.danger_under}</td><td>I정격은 모터별 ({index.motors.map((m) => `${m.id} ${m.spec.rated_line_current_a} A`).join(", ")}) · 저전류는 결상 의심</td></tr>
          <tr><td>I₂/I₁</td><td>&lt; {th.i2i1.safe_below}</td><td>{th.i2i1.safe_below}~{th.i2i1.danger_from}</td><td>≥ {th.i2i1.danger_from}</td><td>{index.honesty.itsc_note}</td></tr>
          {[...groups.entries()].map(([k, ids]) => { const v = index.motors.find((m) => m.id === ids[0])!.vibration; return (
            <tr key={k}><td>진동 속도 RMS<div className="dim">{v.standard}</div></td><td>&lt; {v.watch_mms} mm/s</td><td>{v.watch_mms}~{v.act_mms}{v.plan_mms < v.act_mms ? ` (${v.plan_mms} 부터 "정비 계획")` : ""}</td><td>≥ {v.act_mms}</td><td>{ids.join(" · ")}{v.note ? ` — ${v.note}` : ""}</td></tr>); })}
          <tr><td>베어링 kurtosis (주 지표)</td><td>&lt; {th.bearing.kurtosis.safe_below}</td><td>{th.bearing.kurtosis.safe_below}~{th.bearing.kurtosis.danger_from}</td><td>≥ {th.bearing.kurtosis.danger_from}</td><td>가속도 첨도, 모터 공통. 정상 ≈3, 소손 시 수십. 시뮬레이션은 결함별 등가값</td></tr>
          <tr><td>베어링 고주파 RMS 배율 (보조 지표)</td><td>&lt; {th.bearing.hf_ratio.safe_below}배</td><td>{th.bearing.hf_ratio.safe_below}~{th.bearing.hf_ratio.danger_from}배</td><td>≥ {th.bearing.hf_ratio.danger_from}배</td><td>1 kHz 이상 대역 RMS ÷ 모터별 정상 기준선 ({index.motors.map((m) => `${m.id} ${m.bearing_hf_baseline?.rms_g ?? "-"} g`).join(" · ")}). 베어링 종합 = 둘 중 나쁜 쪽. 포락선 BPFO/BPFI 는 판정 제외(결함 부위 추정 표시만)</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function SpecTab({ index, nameplates }: { index: FleetIndex; nameplates: Nameplates }) {
  const ms = index.motors;
  const row = (label: string, f: (m: MotorInfo) => React.ReactNode) => <tr><td><b>{label}</b></td>{ms.map((m) => <td key={m.id}>{f(m)}</td>)}</tr>;
  return (
    <div>
      <div className="st-honesty-lines">{index.honesty.lines.map((l) => <span key={l}>• {l}</span>)}<span className="dim">{index.honesty.itsc_note}</span></div>
      <table className="grid">
        <thead><tr><th>항목</th>{ms.map((m) => <th key={m.id}>{m.id}</th>)}</tr></thead>
        <tbody>
          {row("용도", (m) => `${m.tags.hoist_ton ?? "-"} 호이스트${m.tags.hoist_speed ? ` · ${m.tags.hoist_speed}` : ""}`)}
          {row("정격 출력", (m) => `${m.spec.rated_power_kw} kW`)}
          {row("극수 / 동기속도", (m) => `${m.spec.poles}극 / ${m.spec.sync_rpm} rpm`)}
          {row("정격 회전수", (m) => `${m.spec.rated_rpm} rpm (슬립 ${(m.derived.slip * 100).toFixed(1)} %)`)}
          {row("전압 · 결선", (m) => `${m.spec.voltage_v} V ${m.spec.frequency_hz} Hz · ${m.spec.connection === "delta" ? "Δ" : m.spec.connection}`)}
          {row("정격 선전류 / 상전류", (m) => `${m.spec.rated_line_current_a} A / ${m.spec.rated_phase_current_a} A`)}
          {row("효율 / 역률 (대표)", (m) => `${m.spec.efficiency} / ${m.spec.power_factor}`)}
          {row("프레임 · 외형 스케일", (m) => `${m.spec.frame} · ×${m.spec.geometry_scale}`)}
          {row("베어링 DE / NDE", (m) => `${m.spec.bearing_de} / ${m.spec.bearing_nde}`)}
          {row("BPFO / BPFI (정격 rpm)", (m) => `${m.derived.bpfo_hz} / ${m.derived.bpfi_hz} Hz`)}
          {row("절연 / 듀티", (m) => `${m.spec.insulation_class}종 / ${m.spec.duty}`)}
          {row("진동 규격", (m) => `${m.vibration.standard.split(" (")[0]} (${m.vibration.watch_mms}/${m.vibration.act_mms})`)}
          {row("정상 수렴 권선 온도 (연속)", (m) => `${m.steady_C.winding} °C`)}
          {row("출처", (m) => m.spec.source === "nameplate" ? `명판값 (입력 ${nameplates[m.id]?.entered_at ?? ""}, YAML 반영 전)` : "대표값 (representative)")}
        </tbody>
      </table>
    </div>
  );
}

// 명판값 입력 폼 (P5): 값을 넣고 저장하면 이 브라우저에 남고, YAML 조각을 복사해 config/motors/<id>.yaml 에 반영한다.
function NameplateForm({ motor, current, onClose, onSave }: { motor: MotorInfo; current?: Nameplates[string]; onClose: () => void; onSave: (np: Nameplates[string] | null) => void }) {
  const [vals, setVals] = useState<Record<string, string>>(() => Object.fromEntries(NAMEPLATE_FIELDS.map((f) => [f.key, current?.values[f.key] !== undefined ? String(current.values[f.key]) : ""])));
  const [note, setNote] = useState(current?.note ?? "");
  const [copied, setCopied] = useState(false);
  const values: Record<string, string | number> = {};
  for (const f of NAMEPLATE_FIELDS) { const v = parseField(f.key, vals[f.key] ?? ""); if (v !== undefined && v !== motor.spec[f.key]) values[f.key] = v; }
  const np: Nameplates[string] | null = Object.keys(values).length ? { values: values as Nameplates[string]["values"], entered_at: new Date().toISOString().slice(0, 10), note: note || undefined } : null;
  const snippet = np ? yamlSnippet(motor.id, np) : "";
  return (
    <div className="st-modal" onClick={onClose}>
      <div className="st-modal-b" onClick={(e) => e.stopPropagation()}>
        <div className="panel-h">명판값 입력 — {motor.id} {motor.name} <span className="grow" /><button onClick={onClose}>닫기 Esc</button></div>
        <div className="st-np-grid">
          {NAMEPLATE_FIELDS.map((f) => (
            <label key={f.key}><span>{f.label}{f.unit ? ` (${f.unit})` : ""}</span>
              <input value={vals[f.key]} placeholder={String(motor.spec[f.key])} onChange={(e) => setVals((v) => ({ ...v, [f.key]: e.target.value }))} inputMode={f.step !== undefined ? "decimal" : "text"} />
              <small className="dim">대표값 {String(motor.spec[f.key])}</small></label>
          ))}
          <label className="wide"><span>메모 (명판 사진·출처)</span><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="예: 2026-10 현장 명판 촬영" /></label>
        </div>
        <div className="st-np-foot">
          <div className="dim">저장하면 이 브라우저에서 사양 표시·정격 전류 기준 게이지가 즉시 바뀌고 출처가 <b>명판값</b>이 된다. 판정·수렴 온도까지 바꾸려면 아래 YAML 을
            <code> config/motors/{motor.id}.yaml</code> 에 반영하고 <code>run_fleet.py → export_status_data.py → npm run build</code> 를 다시 돌린다.</div>
          {snippet && <pre className="st-np-yaml">{snippet}</pre>}
          <div className="st-np-btns">
            <button className="btn primary" disabled={!np} onClick={() => onSave(np)}>저장</button>
            <button disabled={!snippet} onClick={() => { navigator.clipboard?.writeText(snippet).then(() => setCopied(true)).catch(() => undefined); }}>{copied ? "YAML 복사됨" : "YAML 복사"}</button>
            {current && <button onClick={() => onSave(null)}>대표 사양으로 되돌리기</button>}
          </div>
        </div>
      </div>
    </div>
  );
}

// 사용하지 않는 import 경고 방지용 (levelOf·worse 는 Gauge/data 내부에서 쓰인다)
void levelOf; void worse;
