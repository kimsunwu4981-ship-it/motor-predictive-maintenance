// live/livedata.ts — 수신 버퍼(LiveBuffer) → 기존 화면이 먹는 데이터 모양으로 (TASK 실시간 §6 "RecordedSource 와 같은 형태").
//
//   상태 보드  : toMotorSeries(buffer, index)            → MotorSeries (status/cause/levels 는 state.status 그대로 — 판정 안 함)
//   기계 화면  : toMechData(base, buffer, index)          → MechData   (timeseries 성장 버퍼, scenarios = 관찰된 장면 전환, events = 등급 변화)
//   전기 화면  : toElecData(base, buffer, index)          → ElecData
//   재생기     : useLivePlayback(...)                      → Playback   (t = 버퍼 끝을 따라감, 일시정지 = 최근 기록 보기, ←/→ = play_scenario 명령)
// 시간축은 t_session_s(기동 후 누적, 리셋 없음). 차트는 scenarios.t_min ~ total_duration_s(=버퍼 끝) 창을 그린다.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ElecStatus, Scenarios, Stage, Step } from "../data";
import type { ElecData, ElecTimeseries, Phase } from "../elec/data";
import { liveValues as elecLiveValues } from "../elec/data";
import type { MechData, MechEvent, MechTimeseries } from "../mech/data";
import { fmtSim, liveValues as mechLiveValues } from "../mech/data";
import type { Playback } from "../state/playback";
import type { FleetIndex, Level, MotorSeries } from "../status/data";
import { fill, type LiveEvent, type Templates } from "./types";
import { captionText, type HistoryItem } from "./captions";
import type { LiveBuffer } from "./session";
import type { LiveState } from "./feed";

const UPDATE_HZ = 20;
const RANK: Record<Level, number> = { SAFE: 0, WARN: 1, DANGER: 2 };
const REVEAL_LEVEL: Record<string, number> = { why: 1, visible: 2, result: 3 };
export function revealLevel(s: LiveState | null): number { return s?.narration_key?.reveal ? REVEAL_LEVEL[s.narration_key.reveal] ?? 0 : 0; }
export function pageMode(m: LiveState["mode"]): "mechanical" | "electrical" { return m === "electrical" ? "electrical" : "mechanical"; }

// ---- 장면 단계: 스트림에서 관찰된 step 전환. 라벨은 정적 시나리오(같은 config)에서, 없으면 "수동 조작"
export function liveSteps(buf: LiveBuffer, staticSteps: Step[]): Step[] {
  const out: Step[] = [];
  const byId = new Map(staticSteps.map((s) => [s.id, s]));
  for (let k = 0; k < buf.states.length; k++) {
    const s = buf.states[k];
    const last = out[out.length - 1];
    if (last && last.id === s.step) { last.t_end = s.t_session_s; continue; }
    const st = byId.get(s.step);
    out.push({
      n: st?.n ?? 0, id: s.step, label: st?.label ?? (s.step === "manual" ? "수동 조작" : s.step), subtitle: st?.subtitle ?? "", source: st?.source ?? "Isaac Sim 라이브",
      t_start: s.t_session_s, t_end: s.t_session_s, video_start: 0, video_end: 0,
      electrical_case: s.case, faults: s.faults, load: s.load, time_scale: s.time_scale, highlight: st?.highlight ?? false, clip: null,
    });
  }
  if (out.length) out[out.length - 1].t_end = Math.max(out[out.length - 1].t_end, buf.tEnd + 1e-3);
  return out;
}
function liveScenarios(base: Scenarios, buf: LiveBuffer, staticSteps: Step[]): Scenarios {
  return { ...base, video: "", video_offset_s: 0, video_duration_s: null, total_duration_s: buf.tEnd, t_min: buf.tMin, steps: liveSteps(buf, staticSteps),
    lead_time: { basis: "라이브 — 리드 타임은 장면이 끝나야 계산", alarm_t: null, danger_t: null, lead_s: null, lead_sim_s: null } };
}

// ---- 상태 보드 시계열
export function toMotorSeries(buf: LiveBuffer, index: FleetIndex, template: MotorSeries | null): MotorSeries {
  const S = buf.states;
  const col = <T,>(f: (s: LiveState) => T) => S.map(f);
  const nodes = Object.keys(S[0]?.T ?? {});
  const kinds = Object.keys(index.signals);
  const first = S[0];
  const m = index.motors.find((x) => x.id === first?.motor_id);
  const rated = first?.rated_line_A || m?.spec.rated_line_current_a || 1;
  return {
    motor: first?.motor_id ?? "", mode: pageMode(first?.mode ?? "mechanical"), n: S.length,
    source: `Isaac Sim 라이브 ${first?.host?.ws ?? ""} · 판정 engine/thresholds.py (Isaac 쪽)`,
    t: buf.t.slice(), step: col((s) => s.step), time_scale: col((s) => s.time_scale),
    temperature_C: Object.fromEntries(nodes.map((k) => [k, col((s) => s.T[k])])),
    current_rms_A: { A: col((s) => s.Ia_rms), B: col((s) => s.Ib_rms), C: col((s) => s.Ic_rms) },
    current_ratio: { A: col((s) => s.Ia_rms / rated), B: col((s) => s.Ib_rms / rated), C: col((s) => s.Ic_rms / rated) },
    i2i1: col((s) => s.i2_over_i1), vibration_mms: col((s) => s.vibration_mms),
    bearing_kurtosis: col((s) => s.bearing_kurtosis), bearing_hf_ratio: col((s) => s.bearing_hf_ratio), bearing_site_hint: null,
    status: col((s) => s.status.status), cause_signal: col((s) => s.status.cause_signal), cause_component: col((s) => s.status.cause_component),
    cause_value: col((s) => s.status.value), cause_threshold: col((s) => s.status.threshold),
    levels: { ...Object.fromEntries(kinds.map((k) => [k, col((s) => s.status.levels[k] ?? "SAFE")])), bearing: col((s) => s.status.levels.bearing ?? "SAFE") } as MotorSeries["levels"],
    scene_values: template?.scene_values ?? {},
    // 레이아웃 A (2026-10-27): 라이브 state 의 케이스별 성분·파형 → case_signals, 근거 서랍 값(LUT 결함분·I₂/I_n·I_f·P_loop) — 전부 Isaac 쪽 엔진 값 그대로
    case_signals: Object.fromEntries(S.filter((s) => s.waveform_last_2cycles && s.sym_components_A).map((s) => [s.case, { ...s.sym_components_A!, waveform: s.waveform_last_2cycles! }])),
    i2i1_fault: col((s) => s.electrical_source?.lut_i2_over_i1 ?? null), i2_over_in: col((s) => s.i2_over_in ?? null),
    i_f_A: col((s) => s.electrical_source?.i_f_A ?? null), p_loop_total_W: col((s) => s.p_loop_total_W ?? null), winding_dT_C: null,
    extras_note: { i2i1_fault: "LUT 결함분 (Isaac electrical_source.lut_i2_over_i1)", i2_over_in: "I₂/I_n (Isaac state)", i_f_A: "단락 루프 전류 (Isaac electrical_source)", p_loop_total_W: "단락 루프 총손실 (Isaac state)", winding_dT_C: "라이브 전기 모드: 열 모델 미실행" },
  };
}

// ---- 사건 (등급 변화·장면 전환·해설 공개) — 자막·이력용. 수치는 state 에서만.
function tempClass(index: FleetIndex, node: string) { const c = index.thresholds.temperature.component_class[node] ?? "default"; return (index.thresholds.temperature as unknown as Record<string, { safe_below: number; danger_from: number }>)[c]; }
export function liveEvents(buf: LiveBuffer, index: FleetIndex | null, mode: "mechanical" | "electrical", focusNode?: string): LiveEvent[] {
  const S = buf.states;
  const ev: LiveEvent[] = [];
  let id = 0;
  const lab = (l: Level) => index?.labels_ko[l] ?? l;
  for (let k = 0; k < S.length; k++) {
    const s = S[k], p = S[k - 1];
    const t = s.t_session_s;
    const sceneN = s.scene ? Number(String(s.step).match(/\d+/)?.[0] ?? 0) : 0;
    if (!p || p.step !== s.step) {
      ev.push({ id: id++, type: "scene", t, scene: sceneN, priority: 0, label: s.scene?.label ?? (s.step === "manual" ? "수동 조작" : s.step), time_scale: s.time_scale, slowmo_x: Math.round(1 / (s.slowmo || 1)) });
    }
    if (p && p.narration_key?.reveal !== s.narration_key?.reveal && s.narration_key?.reveal) {
      ev.push({ id: id++, type: "reveal", t, scene: sceneN, priority: 9, reveal: s.narration_key.reveal });
    }
    if (!p) continue;
    const prev = new Map(p.status.signals.map((x) => [`${x.kind}/${x.component}`, x]));
    for (const x of s.status.signals) {
      const q = prev.get(`${x.kind}/${x.component}`);
      if (!q || q.level === x.level) continue;
      const up = RANK[x.level] > RANK[q.level];
      if (mode === "mechanical" && x.kind === "temperature") {
        const th = index ? tempClass(index, x.component) : null;
        const thr = th ? (x.level === "DANGER" || q.level === "DANGER" ? th.danger_from : th.safe_below) : null;
        ev.push({ id: id++, type: up ? "stage_up" : (x.level === "SAFE" ? "recovered" : "stage_down"), t, scene: sceneN, priority: x.component === focusNode ? 1 : 3,
          part: x.component, part_label: index?.node_labels[x.component] ?? x.component, from: q.level, to: x.level, from_ko: lab(q.level), to_ko: lab(x.level),
          threshold_C: thr, temp_C: x.value, is_focus: x.component === focusNode, note: up && x.level === "WARN" ? "early_warning" : "" });
      } else if (mode === "mechanical" && x.kind === "vibration") {
        const m = index?.motors.find((mm) => mm.id === s.motor_id);
        ev.push({ id: id++, type: "vib_zone", t, scene: sceneN, priority: 2, up, to_ko: lab(x.level), value_mms: x.value,
          threshold_mms: m ? (x.level === "DANGER" || q.level === "DANGER" ? m.vibration.act_mms : m.vibration.watch_mms) : null });
      } else if (mode === "electrical" && x.kind === "current_ratio") {
        const ph = x.component as Phase;
        const rms = ph === "A" ? s.Ia_rms : ph === "B" ? s.Ib_rms : s.Ic_rms;
        const st = s.current_status?.["ABC".indexOf(ph)] ?? "";
        ev.push({ id: id++, type: "status", tpl: x.level === "SAFE" ? "normal_return" : (st || "default"), t, scene: sceneN, priority: 1,
          phase: ph, phase_label: index?.phase_labels[ph] ?? ph, rms_A: Math.round(rms * 10) / 10, pct: Math.round(x.value * 100),
          threshold_A: Math.round((x.level === "DANGER" ? (x.value > 1 ? index?.thresholds.current_ratio.danger_over : index?.thresholds.current_ratio.danger_under) : (x.value > 1 ? index?.thresholds.current_ratio.safe_high : index?.thresholds.current_ratio.safe_low)) ?? 0 * s.rated_line_A * 10) / 10,
          from_ko: lab(q.level), to_ko: lab(x.level), others: "", others_rms_A: "", others_pct: "" });
      } else if (mode === "electrical" && x.kind === "i2i1") {
        ev.push({ id: id++, type: "i2i1", tpl: up ? "up" : "down", t, scene: sceneN, priority: 1, up, prev: q.value, value: x.value, level: x.level, mark_label: lab(x.level), x_normal: null });
      }
    }
  }
  return ev;
}
export function liveHistory(events: LiveEvent[], tpl: Templates, revealText: (e: LiveEvent) => string): HistoryItem[] {
  const items: HistoryItem[] = [];
  for (const e of events) {
    if (e.type === "reveal") items.push({ t: e.t, kind: "narr", text: revealText(e), primary: true, scene: e.scene, id: `r${e.id}` });
    else if (e.type === "scene") items.push({ t: e.t, kind: "scene", text: captionText(e, tpl), primary: true, scene: e.scene, id: `e${e.id}`, type: e.type });
    else items.push({ t: e.t, kind: "event", text: captionText(e, tpl), primary: true, scene: e.scene, id: `e${e.id}`, type: e.type });
  }
  return items;
}

// ---- 기계 화면 데이터
export function toMechData(base: MechData, buf: LiveBuffer, index: FleetIndex | null, focusNode?: string): MechData {
  const S = buf.states;
  const col = <T,>(f: (s: LiveState) => T) => S.map(f);
  const nodes = base.thresholds.thermal.parts.map((p) => p.key);
  let simAcc = 0;
  const sim: number[] = S.map((s, k) => { if (k) simAcc += Math.max(0, s.t_session_s - S[k - 1].t_session_s) * s.time_scale; if (s.step !== (S[k - 1]?.step ?? s.step)) simAcc = 0; return simAcc; });
  const ts: MechTimeseries = {
    mode: "mechanical", n: S.length, t_real_s: buf.t.slice(), step: col((s) => s.step),
    temperature_C: Object.fromEntries(nodes.map((k) => [k, col((s) => s.T[k] ?? NaN)])),
    stage: Object.fromEntries(nodes.map((k) => [k, col((s) => (s.stage[k] ?? "normal") as Stage)])),
    current_rms_A: { A: col((s) => s.Ia_rms), B: col((s) => s.Ib_rms), C: col((s) => s.Ic_rms) },
    current_status: { A: col((s) => (s.current_status?.[0] ?? "normal") as ElecStatus), B: col((s) => (s.current_status?.[1] ?? "normal") as ElecStatus), C: col((s) => (s.current_status?.[2] ?? "normal") as ElecStatus) },
    i2_over_i1: col((s) => s.i2_over_i1), vibration_mms: col((s) => s.vibration_mms), iso_zone: col((s) => s.iso_zone),
    loss_W: Object.fromEntries(nodes.map((k) => [k, col((s) => s.loss_W?.[k] ?? 0)])),   // 부품별 손실열 (state.loss_W, 없는 옛 스트림은 0)
    time_scale: col((s) => s.time_scale), sim_elapsed_s: sim, step_elapsed_s: col((s) => s.scene?.elapsed_s ?? 0), step_n: col((s) => s.scene ? Number(String(s.step).match(/\d+/)?.[0] ?? 0) : 0),
    replay_check: { method: "live (Isaac Sim 엔진 값 그대로)", max_err_inner_C: {}, max_err_edge_C: {}, pass: true },
  };
  const events = liveEvents(buf, index, "mechanical", focusNode) as MechEvent[];
  const data: MechData = {
    ...base, scenarios: liveScenarios(base.scenarios, buf, base.scenarios.steps), timeseries: ts, events,
    live: (t) => mechLiveValues(data, t),
    timeNote: (t) => { const i = idxOf(ts.t_real_s, t); return [{ label: "시뮬레이션 경과 (장면)", value: fmtSim(ts.sim_elapsed_s[i]) }, { label: "화면 1초 = 시뮬레이션", value: `${ts.time_scale[i]} 초` }]; },
  };
  return data;
}

// ---- 전기 화면 데이터
export function toElecData(base: ElecData, buf: LiveBuffer, index: FleetIndex | null): ElecData {
  const S = buf.states;
  const col = <T,>(f: (s: LiveState) => T) => S.map(f);
  const rated = (s: LiveState) => s.rated_line_A || base.thresholds.electrical.rated_line_A || 1;
  const ph = (s: LiveState, p: Phase) => (p === "A" ? s.Ia_rms : p === "B" ? s.Ib_rms : s.Ic_rms);
  const deg = (s: LiveState, p: Phase) => { const w = base.waveforms.cases[s.case]?.deg; const i = "ABC".indexOf(p); return Array.isArray(w) && w.length >= 3 ? w[i] : [0, -120, 120][i]; };
  const ts: ElecTimeseries = {
    mode: "electrical", n: S.length, t_real_s: buf.t.slice(), step: col((s) => s.step),
    temperature_C: {}, stage: {},
    current_rms_A: { A: col((s) => s.Ia_rms), B: col((s) => s.Ib_rms), C: col((s) => s.Ic_rms) },
    current_status: { A: col((s) => (s.current_status?.[0] ?? "normal") as ElecStatus), B: col((s) => (s.current_status?.[1] ?? "normal") as ElecStatus), C: col((s) => (s.current_status?.[2] ?? "normal") as ElecStatus) },
    i2_over_i1: col((s) => s.i2_over_i1), vibration_mms: col((s) => s.vibration_mms), iso_zone: col((s) => s.iso_zone),
    ratio: { A: col((s) => s.Ia_rms / rated(s)), B: col((s) => s.Ib_rms / rated(s)), C: col((s) => s.Ic_rms / rated(s)) },
    phase_rms_A: { A: col((s) => ph(s, "A") / Math.sqrt(3)), B: col((s) => ph(s, "B") / Math.sqrt(3)), C: col((s) => ph(s, "C") / Math.sqrt(3)) },   // Δ결선 상전류 = 선전류/√3
    phasor_deg: { A: col((s) => deg(s, "A")), B: col((s) => deg(s, "B")), C: col((s) => deg(s, "C")) },                          // 케이스별 config 위상 (엔진 재계산 아님)
    case: col((s) => s.case),
    i2_over_in: col((s) => (s.i2_over_in == null ? null : s.i2_over_in)),
    recompute_check: { method: "live (Isaac Sim 엔진 값 그대로)", max_rms_diff_A: 0, max_i2i1_diff: 0, max_i2i1_diff_from_log_rms: 0, pass: true },
  };
  // 근거 배지·눈금 (D5): 마지막 state 의 electrical_source / i2i1_marks. LUT 방식(M1)이면 눈금이 0.027/0.071/0.264 로 바뀐다 — 녹화 데이터(legacy 0.006/0.104/0.269)와 다른 것이 정상
  const last = S[S.length - 1];
  const thresholds = last?.i2i1_marks?.length ? { ...base.thresholds, electrical: { ...base.thresholds.electrical, i2i1_marks: last.i2i1_marks } } : base.thresholds;
  const data: ElecData = {
    ...base, thresholds, source: last?.electrical_source ?? null,
    scenarios: liveScenarios(base.scenarios, buf, base.scenarios.steps), timeseries: ts, events: liveEvents(buf, index, "electrical") as ElecData["events"],
    live: (t) => elecLiveValues(data, t),
    timeNote: () => [{ label: "입자 흐름", value: `${base.thresholds.electrical.slowmo_x}배 느리게` }, { label: "모드", value: "LIVE" }],
  };
  return data;
}

function idxOf(a: number[], t: number): number {
  let lo = 0, hi = a.length - 1;
  if (hi < 0) return 0;
  if (t <= a[0]) return 0;
  if (t >= a[hi]) return hi;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m] <= t) lo = m; else hi = m; }
  return lo;
}
export function fillLive(text: string, s: LiveState | null): string { return fill(text, s ? { rated_line_A: s.rated_line_A, a_rms_end: s.Ia_rms, a_pct_end: Math.round((s.Ia_rms / (s.rated_line_A || 1)) * 100) } : undefined); }

// ---- 라이브 재생기: playing = 버퍼 끝을 따라감(LIVE), 일시정지 = 최근 기록 보기(버퍼 안 seek). gotoStep → play_scenario 명령.
export function useLivePlayback(buf: LiveBuffer, version: number, steps: Step[], send: (name: string, args?: Record<string, unknown>) => unknown): Playback {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [follow, setFollow] = useState(true);
  const [frozen, setFrozen] = useState(0);
  const tEnd = buf.tEnd;
  const t = follow ? tEnd : Math.max(buf.tMin, Math.min(frozen, tEnd));
  const [, bump] = useState(0);
  useEffect(() => { if (!follow) return; const h = setInterval(() => bump((x) => x + 1), 1000 / UPDATE_HZ); return () => clearInterval(h); }, [follow]);
  void version;
  const seek = useCallback((x: number) => { setFollow(false); setFrozen(x); }, []);
  const play = useCallback(() => setFollow(true), []);
  const pause = useCallback(() => { setFrozen(buf.tEnd); setFollow(false); }, [buf]);
  const toggle = useCallback(() => setFollow((f) => { if (f) setFrozen(buf.tEnd); return !f; }), [buf]);
  const stepIndex = useMemo(() => { const i = steps.findIndex((s) => t < s.t_end); return i < 0 ? Math.max(steps.length - 1, 0) : i; }, [steps, t]);
  const gotoStep = useCallback((n: number) => { if (n >= 1) send("play_scenario", { scene: n }); }, [send]);
  return useMemo(() => ({ t, playing: follow, duration: tEnd, videoRef, seek, toggle, play, pause, gotoStep, stepIndex }),
    [t, follow, tEnd, seek, toggle, play, pause, gotoStep, stepIndex]);
}
