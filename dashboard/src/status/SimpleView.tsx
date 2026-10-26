import { useMemo } from "react";
import type { Mode } from "../data";
import { fmtT } from "../data";
import type { Playback } from "../state/playback";
import { fill } from "../live/types";
import { TrendChart, type TrendSel } from "./TrendChart";
import { StatusStrip } from "./StatusStrip";
import { bearingLevel, plainOf, tempBand, PHASES,
  type FleetIndex, type FleetScenario, type GaugeSpec, type Kind, type Level, type MotorInfo, type MotorSeries, type Phase, type PlainLabel, type PlainLabels, type StatusScene } from "./data";
import "./simple.css";

// 상태 보드 단순 보기 (2026-10-26, 3단 정보 구조의 1층 "한눈에"):
//   첫 화면은 세 질문의 답만 — 지금 상태(영웅) / 왜(원인) / 무엇을(조치) + 이 모드에서 계산되는 신호 칩 + 흐름(재생·추세).
//   표·게이지 없음. I₂/I₁ 숫자는 영웅 1곳(+추세 차트). 전문 용어는 쉬운 말(labels_plain.yaml)로 쓰고 원문은 툴팁에.
//   데이터·판정은 전문가 보기와 완전히 같다 (export JSON·엔진 판정 그대로) — 화면 구성만 다르다.
const TEMP_NODES = ["winding", "bearing_de", "bearing_nde", "rotor", "shaft"];
export interface SceneChip { id: string; label: string; mode: Mode; t_s: number; expect?: string }
export interface StepLike { n: number; id: string; label: string; subtitle: string }

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
// 임계 구간 한 줄 (숫자는 index.thresholds / 모터 진동 규격에서만)
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
  // 안전: 모드의 대표 신호 하나 (전기 = 전류 불균형, 기계 = DE 베어링 온도)
  const kind: Kind = mode === "electrical" ? "i2i1" : "temperature"; const comp = mode === "electrical" ? undefined : "bearing_de";
  const value = kind === "i2i1" ? s.i2i1[i] : s.temperature_C.bearing_de[i];
  return { kind, comp, value, level: "SAFE", name: nameOf(index, labels, kind, comp), threshold: thresholdText(index, motor, kind, comp), persistence: index.thresholds.persistence_s[kind] ?? 0 };
}

interface Chip { key: string; name: PlainLabel; value: string; level: Level | null; sel: TrendSel; extraTip?: string }
function chipsOf(index: FleetIndex, motor: MotorInfo, s: MotorSeries, i: number, mode: Mode, labels: PlainLabels): { chips: Chip[]; noTemp: boolean } {
  const chips: Chip[] = []; const thermal = thermalActive(s);
  const tempChip = (): Chip => {
    let best = "bearing_de", bestF = -Infinity;
    for (const n of TEMP_NODES) { const b = tempBand(index, n); const f = (s.temperature_C[n][i] - b.safe_below) / Math.max(b.danger_from - b.safe_below, 1e-6); if (f > bestF) { bestF = f; best = n; } }
    return { key: "temp", name: nameOf(index, labels, "temperature", best), value: fmtVal("temperature", s.temperature_C[best][i]), level: s.levels.temperature[i], sel: { kind: "temperature", component: best }, extraTip: thresholdText(index, motor, "temperature", best) };
  };
  if (mode === "electrical") {
    chips.push({ key: "i2i1", name: nameOf(index, labels, "i2i1"), value: fmtVal("i2i1", s.i2i1[i]), level: s.levels.i2i1[i], sel: { kind: "i2i1" }, extraTip: thresholdText(index, motor, "i2i1") });
    const rated = motor.spec.rated_line_current_a;
    const rs = PHASES.map((p) => ({ p, r: s.current_rms_A[p][i] / rated }));
    const worst = rs.reduce((a, b) => (Math.abs(b.r - 1) > Math.abs(a.r - 1) ? b : a));
    chips.push({ key: "cur", name: nameOf(index, labels, "current_ratio", worst.p), value: fmtVal("current_ratio", worst.r), level: s.levels.current_ratio[i], sel: { kind: "current_ratio" },
      extraTip: `${rs.map((x) => `${index.phase_labels[x.p]} ${s.current_rms_A[x.p][i].toFixed(2)} A (${x.r.toFixed(2)}×)`).join(" · ")} · 정격 ${rated} A · ${thresholdText(index, motor, "current_ratio")}` });
    const mean = rs.reduce((a, b) => a + b.r, 0) / rs.length; const dev = mean > 0 ? Math.max(...rs.map((x) => Math.abs(x.r - mean))) / mean : 0;
    chips.push({ key: "unb", name: plainOf(labels, "phase_unbalance", "상 불평형"), value: dev.toFixed(3), level: null, sel: { kind: "current_ratio" } });
    if (thermal) chips.push(tempChip());
  } else {
    chips.push(tempChip());
    chips.push({ key: "vib", name: nameOf(index, labels, "vibration"), value: fmtVal("vibration", s.vibration_mms[i]), level: s.levels.vibration[i], sel: { kind: "vibration" }, extraTip: thresholdText(index, motor, "vibration") });
    const bl = bearingLevel(s, i);
    const short = (k: string, fb: string) => plainOf(labels, k, fb).plain.replace(/^베어링\s*/, "");
    chips.push({ key: "brg", name: plainOf(labels, "bearing", "베어링"), value: `${short("bearing_kurtosis", "충격성")} ${s.bearing_kurtosis[i].toFixed(1)} · ${short("bearing_hf_ratio", "고주파")} ${s.bearing_hf_ratio[i].toFixed(2)}배`,
      level: bl, sel: { kind: "bearing_kurtosis" }, extraTip: `${thresholdText(index, motor, "bearing_kurtosis")} · ${thresholdText(index, motor, "bearing_hf_ratio")}` });
  }
  return { chips, noTemp: mode === "electrical" && !thermal };
}

export function SimpleView(p: {
  index: FleetIndex; motor: MotorInfo; s: MotorSeries | null; i: number; mode: Mode; step: StepLike; sc: FleetScenario; scene?: StatusScene;
  labels: PlainLabels; pb: Playback; present: boolean; isLive: boolean; x0: number; span: number;
  trendSel: TrendSel; setTrend: (t: TrendSel) => void; trendSpec: GaugeSpec; sceneMap: SceneChip[]; onScene: (sm: SceneChip) => void;
  toggleMode: () => void; openDrawer: () => void; openTab: (t: "thr" | "spec" | "gloss") => void; setView: (v: "simple" | "expert") => void;
}) {
  const { index, motor, s, i, mode, step, sc, scene, labels, pb, present, isLive, x0, span } = p;
  const prim = s ? primaryOf(index, motor, s, i, mode, labels) : null;
  const level: Level = prim?.level ?? "SAFE"; const col = index.colors[level];
  const { chips, noTemp } = s ? chipsOf(index, motor, s, i, mode, labels) : { chips: [], noTemp: false };
  const meta = index.thresholds.meta; const provisional = prim && ((prim.kind === "i2i1" && meta?.i2i1?.status === "provisional") || (prim.kind === "current_ratio" && meta?.current_ratio?.status === "provisional") || (prim.kind.startsWith("bearing") && meta?.bearing?.status === "provisional"));
  const sv = s?.scene_values[step.id]; const cc = scene?.cause_chain;
  const why1 = cc ? fill(cc.cause, sv) : fill(String(scene?.why ?? step.subtitle), sv);
  const why2 = cc ? fill(cc.mechanism, sv) : "";
  const what1 = cc ? fill(cc.action, sv) : "";
  const what2 = cc ? fill(cc.effect, sv) : "";
  const note = (labels.notes.persistence ?? "{s}초 이상 지속될 때만 경보가 올라갑니다").replace("{s}", String(prim?.persistence ?? 3));
  const selOn = (c: Chip) => p.trendSel.kind === c.sel.kind && (c.sel.kind !== "temperature" || p.trendSel.component === c.sel.component);
  return (
    <div className={"sv" + (present ? " present" : "")} style={{ ["--sv-col" as string]: col }}>
      <div className="sv-top">
        <section className="sv-hero" aria-label="지금 상태">
          <div className="sv-status" style={{ color: col }}><span className="ic">{index.icons[level]}</span>{index.labels_ko[level]}</div>
          {prim && (
            <>
              <div className="sv-cause"><abbr title={`${prim.name.term}${prim.name.tip ? " — " + prim.name.tip : ""}`}>{prim.name.plain}</abbr> <b>{fmtVal(prim.kind, prim.value)}</b>
                {provisional && <span className="sv-tag" title={labels.notes.provisional_tip ?? "실측 기준선 확보 전까지 참고 기준"}>{labels.notes.provisional_tag ?? "임시"}</span>}</div>
              <div className="sv-thr">{prim.threshold}</div>
              <div className="sv-note">{prim.persistence > 0 ? `(${note})` : "(온도는 즉시 반영)"}</div>
            </>
          )}
          {!s && <div className="sv-cause">불러오는 중…</div>}
          <div className="sv-motor"><span>{motorLabel(motor, labels)}</span><span>{isLive ? "LIVE · " : ""}장면 {step.n}{isLive ? "" : `/${sc.steps.length}`} {scene?.title ?? step.label}</span></div>
        </section>
        <div className="sv-ww">
          <section className="sv-q" aria-label="원인"><div className="k">{labels.notes.why ?? "왜?"}</div><div className="l1"><Plain text={why1} labels={labels} /></div>{why2 && <div className="l2"><Plain text={why2} labels={labels} /></div>}</section>
          <section className="sv-q" aria-label="조치"><div className="k">{labels.notes.what ?? "무엇을?"}</div>
            <div className="l1">{what1 ? <Plain text={what1} labels={labels} /> : "—"} <span className="lv" style={{ color: col }}>({index.labels_ko[level]} 단계)</span></div>
            {what2 && <div className="l2"><Plain text={what2} labels={labels} /></div>}</section>
        </div>
      </div>

      {!present && (
        <section className="sv-sig" aria-label="신호">
          <span className="t">{labels.notes.signals_title ?? "신호 (이 모드에서 계산되는 것만)"}</span>
          {chips.map((c) => (
            <button key={c.key} className={"sv-chip" + (c.level === null ? " neutral" : "") + (selOn(c) ? " on" : "")} style={c.level ? { borderColor: index.colors[c.level] } : undefined}
              title={`${c.name.term}${c.name.tip ? " — " + c.name.tip : ""}${c.extraTip ? "\n" + c.extraTip : ""}${c.level === null ? "\n표시용 보조값 (판정 아님)" : ""}`} onClick={() => p.setTrend(c.sel)}>
              {c.level && <span className="ic" style={{ color: index.colors[c.level] }}>{index.icons[c.level]}</span>}<span>{c.name.plain}</span>
              {prim && c.sel.kind === prim.kind && (c.sel.kind !== "temperature" || c.sel.component === prim.comp) ? <span className="dim" title={c.value}>↖ 위</span> : <b>{c.value}</b>}</button>
          ))}
          {noTemp && <span className="sv-chip na" title={plainOf(labels, "temperature", "온도").tip}>{labels.notes.no_temperature_in_mode ?? "온도: 이 모드에서는 계산하지 않음"}</span>}
        </section>
      )}

      <section className="sv-flow" aria-label="흐름">
        <div className="sv-bar">
          <span className="t dim">{labels.notes.flow_title ?? "흐름"}</span>
          <button onClick={pb.toggle} title="Space">{isLive ? (pb.playing ? "❚❚ 최근 기록 보기" : "▶ LIVE 복귀") : (pb.playing ? "⏸ 일시정지" : "▶ 재생")}</button>
          {!isLive && <button onClick={p.toggleMode} title="M 키: 기계 ↔ 전기 시나리오">{mode === "mechanical" ? "기계" : "전기"} 시나리오 ⇄</button>}
          <span className="sv-time">{fmtT(pb.t)} / {fmtT(sc.total_duration_s)}</span>
          <div className="st-strip" onClick={(e) => { const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect(); pb.seek(x0 + ((e.clientX - r.left) / r.width) * span); }} title="클릭: 이동 · 색: 판정 상태">
            {s && <StatusStrip index={index} s={s} total={sc.total_duration_s} from={x0} />}
            {sc.steps.map((st) => <span key={st.id + st.t_start} className={"st-ch" + (st.id === step.id ? " cur" : "")} style={{ left: `${((st.t_start - x0) / span) * 100}%`, width: `${((st.t_end - st.t_start) / span) * 100}%` }} title={st.label}>{st.n || "·"}</span>)}
            <i className="st-cur" style={{ left: `${((pb.t - x0) / span) * 100}%` }} />
          </div>
          {!isLive && p.sceneMap.length > 0 && (
            <span className="chips st-scenes" title="장면 바로 가기">
              {p.sceneMap.map((sm) => <span key={sm.id} className={"chip sc" + (mode === sm.mode && Math.abs(pb.t - sm.t_s) < 1.5 ? " on" : "")} onClick={() => p.onScene(sm)}>
                {sm.expect && <i style={{ background: index.colors[sm.expect as Level] }} />}{sm.label}</span>)}
            </span>
          )}
        </div>
        {s && <TrendChart index={index} motor={motor} series={s} sel={p.trendSel} spec={p.trendSpec} t={pb.t} onSeek={pb.seek} scenario={isLive ? sc : undefined} plain
          yName={p.trendSel.kind === "temperature" ? `${index.node_labels[p.trendSel.component ?? "bearing_de"] ?? ""} ${plainOf(labels, "temperature", "온도").plain} (°C)`
            : `${nameOf(index, labels, p.trendSel.kind).plain}${index.signals[p.trendSel.kind]?.unit ? ` (${index.signals[p.trendSel.kind].unit})` : ""}`} />}
      </section>

      {!present && (
        <div className="sv-foot">
          <button className="sv-chip sv-honesty" onClick={p.openDrawer} title={`${index.honesty.label} — ${index.honesty.lines.join(" · ")}`}>{labels.notes.honesty_chip ?? "시뮬레이션 추정값 · 근거 보기 ›"}</button>
          <span className="grow" />
          <button className="sv-chip" onClick={() => p.openTab("thr")}>임계값</button>
          <button className="sv-chip" onClick={() => p.openTab("spec")}>사양</button>
          <button className="sv-chip" onClick={() => p.openTab("gloss")}>용어</button>
          <button className="sv-chip" onClick={() => p.setView("expert")} title="기존 상태 보드 (게이지·표 전부)">전문가 보기</button>
        </div>
      )}
    </div>
  );
}
