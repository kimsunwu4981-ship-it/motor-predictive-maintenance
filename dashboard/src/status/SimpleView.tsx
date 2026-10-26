import { useMemo } from "react";
import type { Mode } from "../data";
import { fmtT } from "../data";
import type { Playback } from "../state/playback";
import { fill } from "../live/types";
import { TrendChart, type TrendSel } from "./TrendChart";
import { StatusStrip } from "./StatusStrip";
import { MotorMap } from "./tiles/MotorMap";
import { WaveTile } from "./tiles/WaveTile";
import { BarsTile, type Bar } from "./tiles/BarsTile";
import { bearingLevel, plainOf, specFor, tempBand, PHASES,
  type FleetIndex, type FleetScenario, type Kind, type Level, type MotorInfo, type MotorSeries, type Phase, type PlainLabel, type PlainLabels, type StatusScene } from "./data";
import "./simple.css";

// 상태 보드 단순 보기 (2026-10-26, TASK §1b "비주얼 우선"): 상태 띠(72 px) + 그림 타일 2×2(① 모터 열·결함 지도 ② 3상 전류 파형 ③ 전류 성분 ④ 추세) + 하단 띠(왜 / 무엇을 / 근거 ›).
//   각 타일 = 제목 한 단어 + 그림 + 큰 숫자 하나. 축 눈금·범례·단위는 최소(툴팁). I₂/I₁ 숫자는 상태 띠와 ③ 타일 두 곳뿐.
//   기계 모드: ② 진동 막대 ③ 베어링 충격성·고주파 막대 (진동 파형·스펙트럼 신호가 없으므로). 전기 모드: ① 은 회색 + "온도 미계산".
//   데이터·판정은 전문가 보기와 완전히 같다 (export JSON·엔진 판정 그대로) — 화면 구성만 다르다. 전문 용어는 쉬운 말(labels_plain.yaml), 원문은 툴팁.
const TEMP_NODES = ["winding", "bearing_de", "bearing_nde", "rotor", "shaft"];
export interface SceneChip { id: string; label: string; mode: Mode; t_s: number; expect?: string }
export interface StepLike { n: number; id: string; label: string; subtitle: string; electrical_case?: string; faults?: string[]; t_start?: number }

// 본문 문장의 전문 용어 → 쉬운 말 (툴팁에 원문). labels.replace 순서대로 치환.
export function Plain({ text, labels }: { text: string; labels: PlainLabels }) {
  const parts = useMemo(() => {
    let out: (string | { to: string; tip: string })[] = [text];
    for (const r of labels.replace) {
      const next: typeof out = [];
      for (const p of out) {
        if (typeof p !== "string" || !p.includes(r.from)) { next.push(p); continue; }
        const segs = p.split(r.from);
        segs.forEach((sg, n) => { if (sg) next.push(sg); if (n < segs.length - 1) next.push({ to: r.to, tip: r.tip ?? r.from }); });
      }
      out = next;
    }
    return out;
  }, [text, labels]);
  return <>{parts.map((p, n) => (typeof p === "string" ? <span key={n}>{p}</span> : <abbr key={n} title={p.tip}>{p.to}</abbr>))}</>;
}
export function motorLabel(motor: MotorInfo, labels: PlainLabels): string {
  return `${motor.name.split(" — ")[0]} · ${motor.spec.rated_power_kw} kW ${motor.spec.poles}극 · ${labels.notes.motor_suffix ?? "해석 기준 모터"}`;
}
export function thermalActive(s: MotorSeries): boolean {
  return TEMP_NODES.some((n) => { const a = s.temperature_C[n]; if (!a || !a.length) return false; let lo = a[0], hi = a[0]; for (const v of a) { if (v < lo) lo = v; if (v > hi) hi = v; } return hi - lo > 1e-6; });
}
function fmtVal(kind: string, v: number): string {
  if (kind === "i2i1") return v.toFixed(3);
  if (kind === "current_ratio") return `${v.toFixed(2)}×`;
  if (kind === "temperature") return `${v.toFixed(1)} °C`;
  if (kind === "vibration") return `${v.toFixed(1)} mm/s`;
  if (kind === "bearing_hf_ratio") return `${v.toFixed(2)}배`;
  return v.toFixed(1);
}
export function thresholdText(index: FleetIndex, motor: MotorInfo, kind: Kind, comp?: string): string {
  const th = index.thresholds;
  if (kind === "i2i1") return `안전 <${th.i2i1.safe_below} · 위험 ≥${th.i2i1.danger_from}`;
  if (kind === "current_ratio") { const r = th.current_ratio; return `안전 ${r.safe_low}~${r.safe_high}× · 위험 >${r.danger_over}× 또는 <${r.danger_under}×`; }
  if (kind === "temperature") { const b = tempBand(index, comp ?? "bearing_de"); return `안전 <${b.safe_below} °C · 위험 ≥${b.danger_from} °C`; }
  if (kind === "vibration") return `안전 <${motor.vibration.watch_mms} · 위험 ≥${motor.vibration.act_mms} mm/s`;
  if (kind === "bearing_kurtosis") return `안전 <${th.bearing.kurtosis.safe_below} · 위험 ≥${th.bearing.kurtosis.danger_from}`;
  return `안전 <${th.bearing.hf_ratio.safe_below}배 · 위험 ≥${th.bearing.hf_ratio.danger_from}배`;
}
function nameOf(index: FleetIndex, labels: PlainLabels, kind: Kind, comp?: string): PlainLabel {
  const base = plainOf(labels, kind, index.signals[kind]?.label ?? kind);
  if (kind === "temperature" && comp) return { ...base, plain: `${index.node_labels[comp] ?? comp} ${base.plain}` };
  if (kind === "current_ratio" && comp && index.phase_labels[comp as Phase]) return { ...base, plain: `${index.phase_labels[comp as Phase]}상 ${base.plain}` };
  return base;
}
interface Primary { kind: Kind; comp?: string; value: number; level: Level; name: PlainLabel; threshold: string; persistence: number }
function primaryOf(index: FleetIndex, motor: MotorInfo, s: MotorSeries, i: number, mode: Mode, labels: PlainLabels): Primary {
  const lv = s.status[i]; const ck = s.cause_signal[i] as Kind | "-";
  if (lv !== "SAFE" && ck !== "-") {
    const comp = s.cause_component[i] || undefined;
    return { kind: ck, comp, value: s.cause_value[i], level: lv, name: nameOf(index, labels, ck, comp),
      threshold: (s.cause_threshold[i] || thresholdText(index, motor, ck, comp)).replace(/^\[|\]$/g, "").replace(/ \/ /g, " · "), persistence: index.thresholds.persistence_s[ck] ?? 0 };
  }
  const kind: Kind = mode === "electrical" ? "i2i1" : "temperature"; const comp = mode === "electrical" ? undefined : "bearing_de";
  const value = kind === "i2i1" ? s.i2i1[i] : s.temperature_C.bearing_de[i];
  return { kind, comp, value, level: "SAFE", name: nameOf(index, labels, kind, comp), threshold: thresholdText(index, motor, kind, comp), persistence: index.thresholds.persistence_s[kind] ?? 0 };
}

export function SimpleView(p: {
  index: FleetIndex; motor: MotorInfo; s: MotorSeries | null; i: number; mode: Mode; step: StepLike; sc: FleetScenario; scene?: StatusScene;
  labels: PlainLabels; pb: Playback; present: boolean; isLive: boolean; x0: number; span: number;
  sceneMap: SceneChip[]; onScene: (sm: SceneChip) => void;
  toggleMode: () => void; openDrawer: () => void; openTab: (t: "thr" | "spec" | "gloss") => void; setView: (v: "simple" | "expert") => void;
}) {
  const { index, motor, s, i, mode, step, sc, scene, labels, pb, present, isLive, x0, span } = p;
  const L = labels.notes; const T = labels.tiles ?? {};
  const prim = s ? primaryOf(index, motor, s, i, mode, labels) : null;
  const level: Level = prim?.level ?? "SAFE"; const col = index.colors[level];
  const thermalOn = !!s && thermalActive(s);
  const meta = index.thresholds.meta;
  const provisional = prim && ((prim.kind === "i2i1" && meta?.i2i1?.status === "provisional") || (prim.kind === "current_ratio" && meta?.current_ratio?.status === "provisional") || (prim.kind.startsWith("bearing") && meta?.bearing?.status === "provisional"));
  const sv = s?.scene_values[step.id]; const cc = scene?.cause_chain;
  const why = cc ? `${fill(cc.cause, sv)} → ${fill(cc.mechanism, sv)}` : fill(String(scene?.why ?? step.subtitle), sv);
  const what = cc ? fill(cc.action, sv) : "";
  const note = (L.persistence ?? "{s}초 이상 지속될 때만 경보가 올라갑니다").replace("{s}", String(prim?.persistence ?? 3));
  // ---- 전기: 케이스 신호 (파형·대칭 성분)
  const caseId = step.electrical_case ?? sc.steps.find((st) => st.id === step.id)?.electrical_case ?? "healthy";
  const csig = s?.case_signals?.[caseId];
  const rated = motor.spec.rated_line_current_a;
  const rms = s ? { A: s.current_rms_A.A[i], B: s.current_rms_A.B[i], C: s.current_rms_A.C[i] } : { A: 0, B: 0, C: 0 };
  const worst = PHASES.reduce((a, b) => (Math.abs(rms[b] / rated - 1) > Math.abs(rms[a] / rated - 1) ? b : a), "A" as Phase);
  const causePhase: Phase | null = s && s.cause_signal[i] === "current_ratio" && (PHASES as string[]).includes(s.cause_component[i]) ? (s.cause_component[i] as Phase) : null;   // 원인이 전류 비율일 때만 상 이름 (I₂/I₁ 원인이면 "-")
  const faultPhase: Phase | null = s && s.levels.current_ratio[i] !== "SAFE" ? (causePhase ?? worst) : (s && Math.abs(rms[worst] / rated - 1) > 0.05 ? worst : null);
  const pLoop = s?.p_loop_total_W?.[i] ?? 0;
  const pLoopMax = useMemo(() => Math.max(1, ...((s?.p_loop_total_W ?? []).filter((v): v is number => typeof v === "number"))), [s]);
  // ---- ① 큰 숫자: 가장 뜨거운 노드
  const hottest = useMemo(() => {
    if (!s || !thermalOn) return null;
    let best = "bearing_de", bestF = -Infinity;
    for (const n of TEMP_NODES) { const b = tempBand(index, n); const f = (s.temperature_C[n][i] - b.safe_below) / Math.max(b.danger_from - b.safe_below, 1e-6); if (f > bestF) { bestF = f; best = n; } }
    return { node: best, tC: s.temperature_C[best][i] };
  }, [s, i, thermalOn, index]);
  const faultBearing = mode === "mechanical" && s ? (s.temperature_C.bearing_nde[i] > s.temperature_C.bearing_de[i] ? "bearing_nde" : "bearing_de") : null;
  // ---- ④ 추세: 모드 대표 신호 (전기 = 전류 불균형, 기계 = 원인 신호 또는 DE 베어링 온도) + 주입 시각
  const trendSel: TrendSel = mode === "electrical" ? { kind: "i2i1" } : (prim && prim.level !== "SAFE" ? { kind: prim.kind, component: prim.comp } : { kind: "temperature", component: "bearing_de" });
  const trendSpec = useMemo(() => specFor(index, motor, trendSel), [index, motor, trendSel.kind, trendSel.component]);   // eslint-disable-line react-hooks/exhaustive-deps
  const injectT = (step.faults?.length || (step.electrical_case && step.electrical_case !== "healthy")) ? (step.t_start ?? null) : null;
  const trendName = trendSel.kind === "temperature" ? `${index.node_labels[trendSel.component ?? "bearing_de"] ?? ""} ${plainOf(labels, "temperature", "온도").plain}` : nameOf(index, labels, trendSel.kind).plain;
  // ---- 타일 ②③ 내용 (모드별)
  const th = index.thresholds; const fg = "var(--fg)";
  let tile2: React.ReactNode, big2 = "", title2 = "", tile3: React.ReactNode, big3 = "", title3 = "", big3col: string | undefined;
  if (mode === "electrical") {
    title2 = T.wave ?? "전류 파형"; title3 = T.comp ?? "전류 성분";
    const fp = faultPhase ?? worst;
    big2 = `${index.phase_labels[fp]} ${rms[fp].toFixed(1)} A (${(rms[fp] / rated).toFixed(2)}×)`;
    tile2 = csig ? <WaveTile wf={csig.waveform} ratedA={rated} faultPhase={faultPhase} phaseLabels={index.phase_labels} rmsA={rms} /> : <div className="tile-na">파형 없음 (export 재실행)</div>;
    const i1 = csig?.i1_A ?? 0, i2 = csig?.i2_A ?? 0, i0 = csig?.i0_A ?? 0;
    const bars: Bar[] = [
      { key: "i1", label: "I₁", value: i1 / rated, max: 1.3, level: null, tip: `정상분 I₁ ${i1.toFixed(2)} A (정격 ${rated} A)` },
      { key: "i2", label: "I₂", value: i2 / rated, max: 1.3, level: s ? s.levels.i2i1[i] : null, ticks: [{ at: th.i2i1.safe_below * i1 / rated, label: String(th.i2i1.safe_below) }, { at: th.i2i1.danger_from * i1 / rated, label: String(th.i2i1.danger_from) }], tip: `역상분 I₂ ${i2.toFixed(2)} A — I₂/I₁ ${s ? s.i2i1[i].toFixed(4) : "-"} (눈금 = 경고·위험 경계 × I₁)` },
      { key: "i0", label: "I₀", value: i0 / rated, max: 1.3, level: null, tip: `영상분 I₀ ${i0.toFixed(2)} A` },
    ];
    tile3 = <BarsTile bars={bars} colors={index.colors} fg={fg} />;
    big3 = s ? s.i2i1[i].toFixed(3) : "—"; big3col = s ? index.colors[s.levels.i2i1[i]] : undefined;
  } else {
    title2 = T.vib ?? "진동"; title3 = T.bearing ?? "베어링";
    const vib = s?.vibration_mms[i] ?? 0; const v = motor.vibration;
    tile2 = <BarsTile bars={[{ key: "vib", label: plainOf(labels, "vibration", "진동").plain, value: vib, max: Math.max(7, v.act_mms * 1.5), level: s ? s.levels.vibration[i] : null, ticks: [{ at: v.watch_mms, label: String(v.watch_mms) }, { at: v.act_mms, label: String(v.act_mms) }], tip: `${v.standard} — ${thresholdText(index, motor, "vibration")}` }]} colors={index.colors} fg={fg} />;
    big2 = `${vib.toFixed(1)} mm/s`;
    const k = s?.bearing_kurtosis[i] ?? 0, hf = s?.bearing_hf_ratio[i] ?? 0;
    const short = (key: string, fb: string) => plainOf(labels, key, fb).plain.replace(/^베어링\s*/, "");
    tile3 = <BarsTile bars={[
      { key: "k", label: short("bearing_kurtosis", "충격성"), value: k, max: 8, level: s ? s.levels.bearing_kurtosis[i] : null, ticks: [{ at: th.bearing.kurtosis.safe_below, label: String(th.bearing.kurtosis.safe_below) }, { at: th.bearing.kurtosis.danger_from, label: String(th.bearing.kurtosis.danger_from) }], tip: `${plainOf(labels, "bearing_kurtosis", "kurtosis").term} ${k.toFixed(1)}` },
      { key: "hf", label: short("bearing_hf_ratio", "고주파"), value: hf, max: 5, level: s ? s.levels.bearing_hf_ratio[i] : null, ticks: [{ at: th.bearing.hf_ratio.safe_below, label: String(th.bearing.hf_ratio.safe_below) }, { at: th.bearing.hf_ratio.danger_from, label: String(th.bearing.hf_ratio.danger_from) }], tip: `${plainOf(labels, "bearing_hf_ratio", "고주파 배율").term} ${hf.toFixed(2)}배` },
    ]} colors={index.colors} fg={fg} />;
    big3 = `${short("bearing_kurtosis", "충격성")} ${k.toFixed(1)}`; big3col = s ? index.colors[bearingLevel(s, i)] : undefined;
  }
  return (
    <div className={"sv2" + (present ? " present" : "")} style={{ ["--sv-col" as string]: col }}>
      {/* 상태 띠 */}
      <section className="sv2-top" aria-label="지금 상태">
        <span className="sv2-status" style={{ color: col }}>{index.icons[level]} {index.labels_ko[level]}</span>
        {prim && (
          <span className="sv2-cause" title={`${prim.name.term}${prim.name.tip ? " — " + prim.name.tip : ""}\n${prim.threshold}\n${prim.persistence > 0 ? note : "온도는 즉시 반영"}`}>
            <abbr title={`${prim.name.term}${prim.name.tip ? " — " + prim.name.tip : ""}`}>{prim.name.plain}</abbr> <b>{fmtVal(prim.kind, prim.value)}</b>
            {provisional && <span className="sv-tag" title={L.provisional_tip ?? "실측 기준선 확보 전까지 참고 기준"}>{L.provisional_tag ?? "임시"}</span>}
          </span>
        )}
        <span className="sv2-motor" title={motor.name}>{motorLabel(motor, labels)}</span>
        <span className="grow" />
        <span className="sv2-scene">{isLive ? "LIVE · " : ""}장면 {step.n}{isLive ? "" : `/${sc.steps.length}`} {scene?.title ?? step.label}</span>
        <button onClick={pb.toggle} title="Space">{isLive ? (pb.playing ? "❚❚" : "▶ LIVE") : (pb.playing ? "⏸" : "▶")}</button>
        <span className="sv2-time">{fmtT(pb.t)} / {fmtT(sc.total_duration_s)}</span>
        {!isLive && !present && <button onClick={p.toggleMode} title="M 키: 기계 ↔ 전기 시나리오">{mode === "mechanical" ? "기계" : "전기"} ⇄</button>}
      </section>

      {/* 그림 타일 2×2 */}
      <section className="sv2-tiles" aria-label="그림">
        <div className="tile">
          <div className="tile-h"><span className="t">{T.map ?? "열·결함 지도"}</span><span className="dim" title="열 모델 추정값 (열화상 카메라 아님)">{thermalOn ? "열 모델" : ""}</span>
            <b className="big">{hottest ? `${index.node_labels[hottest.node] ?? hottest.node} ${hottest.tC.toFixed(1)} °C` : ""}</b></div>
          <div className="tile-b">{s && <MotorMap index={index} s={s} i={i} thermalOn={thermalOn} t={pb.t} pLoopW={pLoop} pLoopMaxW={pLoopMax} faultBearing={faultBearing} labelNoTemp={L.no_temperature_in_mode ?? "온도: 이 모드에서는 계산하지 않음"} />}</div>
        </div>
        <div className="tile">
          <div className="tile-h"><span className="t">{title2}</span><span className="dim">{mode === "electrical" ? "최근 2주기" : ""}</span><b className="big" style={mode === "electrical" && s ? { color: index.colors[s.levels.current_ratio[i]] } : undefined}>{big2}</b></div>
          <div className="tile-b">{tile2}</div>
        </div>
        <div className="tile">
          <div className="tile-h"><span className="t">{title3}</span><span className="dim">{mode === "electrical" ? "정격 대비" : ""}</span><b className="big" style={big3col ? { color: big3col } : undefined}>{big3}</b></div>
          <div className="tile-b">{tile3}</div>
        </div>
        <div className="tile">
          <div className="tile-h"><span className="t">{T.trend ?? "추세"}</span><span className="dim">{trendName}</span></div>
          <div className="tile-b tile-trend">
            {s && <TrendChart index={index} motor={motor} series={s} sel={trendSel} spec={trendSpec} t={pb.t} onSeek={pb.seek} scenario={isLive ? sc : undefined} plain yName={trendName} markT={injectT} />}
            <div className="sv2-strip-row">
              <div className="st-strip" onClick={(e) => { const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect(); pb.seek(x0 + ((e.clientX - r.left) / r.width) * span); }} title="클릭: 이동 · 색: 판정 상태">
                {s && <StatusStrip index={index} s={s} total={sc.total_duration_s} from={x0} />}
                {sc.steps.map((st) => <span key={st.id + st.t_start} className={"st-ch" + (st.id === step.id ? " cur" : "")} style={{ left: `${((st.t_start - x0) / span) * 100}%`, width: `${((st.t_end - st.t_start) / span) * 100}%` }} title={st.label}>{st.n || "·"}</span>)}
                <i className="st-cur" style={{ left: `${((pb.t - x0) / span) * 100}%` }} />
              </div>
              {!isLive && p.sceneMap.length > 0 && !present && (
                <span className="chips st-scenes" title="장면 바로 가기 (숫자 키 1~5)">
                  {p.sceneMap.map((sm) => <span key={sm.id} className={"chip sc" + (mode === sm.mode && Math.abs(pb.t - sm.t_s) < 1.5 ? " on" : "")} onClick={() => p.onScene(sm)}>
                    {sm.expect && <i style={{ background: index.colors[sm.expect as Level] }} />}{sm.label}</span>)}
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 하단 띠: 왜 / 무엇을 / 근거 */}
      <section className="sv2-foot" aria-label="원인과 조치">
        <span className="k">{L.why ?? "왜"}</span><span className="v" title={why}><Plain text={why} labels={labels} /></span>
        <span className="k">{L.what ?? "무엇을"}</span><span className="v" title={what}>{what ? <Plain text={what} labels={labels} /> : "—"} <span style={{ color: col }}>({index.labels_ko[level]} 단계)</span></span>
        <button className="sv-chip sv-honesty" onClick={p.openDrawer} title={`${index.honesty.label} — ${index.honesty.lines.join(" · ")}`}>{L.honesty_chip ?? "시뮬레이션 추정값 · 근거 보기 ›"}</button>
        {!present && (<>
          <button className="sv-chip" onClick={() => p.openTab("thr")}>임계값</button>
          <button className="sv-chip" onClick={() => p.openTab("spec")}>사양</button>
          <button className="sv-chip" onClick={() => p.openTab("gloss")}>용어</button>
          <button className="sv-chip" onClick={() => p.setView("expert")} title="기존 상태 보드 (게이지·표 전부)">전문가 보기</button>
        </>)}
      </section>
    </div>
  );
}
