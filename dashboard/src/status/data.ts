// status/data.ts — 상태 보드(#/status) 데이터 타입·로더·판정 보조 (TASK_다중모터 §7).
// 숫자는 전부 export_status_data.py 가 만든 public/data/fleet/*.json 에서 온다. 판정(status·cause)은 엔진(thresholds.py)이 로그에
// 이미 써 둔 값을 그대로 쓰고, 여기서는 게이지 색칠용 "현재값만의 등급"만 계산한다 (히스테리시스·지속 시간 없음).
import type { Mode } from "../data";
import { getJson, getYaml, getYamlOptional } from "../live/load";
import type { CauseChain } from "../live/types";

export type Level = "SAFE" | "WARN" | "DANGER";
export const LEVELS: Level[] = ["SAFE", "WARN", "DANGER"];
export type Kind = "temperature" | "current_ratio" | "i2i1" | "vibration" | "bearing_kurtosis" | "bearing_hf_ratio";
export const KINDS: Kind[] = ["temperature", "current_ratio", "i2i1", "vibration", "bearing_kurtosis", "bearing_hf_ratio"];
// 베어링 종합 등급 = kurtosis·고주파 배율 중 나쁜 쪽 (엔진이 status CSV 의 bearing 열에 써 둔 값; 여기서는 표시만)
export const BEARING_KINDS: Kind[] = ["bearing_kurtosis", "bearing_hf_ratio"];
export type Phase = "A" | "B" | "C";
export const PHASES: Phase[] = ["A", "B", "C"];

export interface FleetStep {
  n: number; id: string; label: string; subtitle: string; t_start: number; t_end: number;
  time_scale: number; load: number; faults: string[]; electrical_case: string;
}
export interface FleetScenario { total_duration_s: number; steps: FleetStep[]; t_min?: number }   // t_min: 라이브 창 시작
export interface VibSpec { standard: string; watch_mms: number; plan_mms: number; act_mms: number; note?: string }
export interface MotorSpec {
  rated_power_kw: number; poles: number; sync_rpm: number; rated_rpm: number; voltage_v: number; frequency_hz: number;
  connection: string; efficiency: number; power_factor: number; rated_line_current_a: number; rated_phase_current_a: number;
  frame: string; insulation_class: string; duty: string; bearing_de: string; bearing_nde: string; geometry_scale: number; source: string;
}
export interface FieldSource { source: string; doc?: string; note?: string; verify_on_site?: boolean }
export interface MetricMeta { source?: string; status?: string }
// 참고 배지 문구: provisional 지표 — 시뮬레이션(합성 신호)에서는 "임시 기준" 라벨로 종합에 포함, 실측 스트림에서는 판정 제외(advisory)
export function provisionalBadge(m?: MetricMeta, stream = "simulation"): { text: string; title: string } | undefined {
  if (!m || m.status !== "provisional") return undefined;
  const live = stream === "live";
  return { text: live ? "참고" : "참고 · 임시 기준",
           title: `실측 기준선 미확보 (출처 ${m.source ?? "?"}, 상태 provisional) — 실측 모드에서는 판정에 반영되지 않음(advisory). ${live ? "지금은 실측 스트림: 참고 표시만" : "시뮬레이션 시나리오: 임시 기준으로 종합 판정에 포함"}` };
}
export interface MotorInfo {
  id: string; name: string; tags: Record<string, string>; spec: MotorSpec;
  spec_source?: Record<string, FieldSource>;   // 키별 출처 — YAML {value, source, …} 래퍼로 적힌 키만 (M1 2026-10-19 카탈로그)
  derived: { slip: number; rotor_freq_hz: number; torque_nm: number; bpfo_hz: number; bpfi_hz: number; loss_w: number };
  bearing_hf_baseline?: { rms_g?: number; band_hz?: number[]; source?: string; note?: string };
  vibration: VibSpec; steady_C: Record<string, number>; thermal_scaled_from: unknown;
  demo: { mode: Mode; t_s: number; expect?: string; why?: string };
  files: Record<Mode, string>;
}
export interface TempBand { safe_below: number; danger_from: number; note?: string }
export interface FleetIndex {
  generated: string; source: string;
  honesty: { label: string; lines: string[]; itsc_note: string };
  levels: Level[]; labels_ko: Record<Level, string>; icons: Record<Level, string>; colors: Record<Level, string>;
  signals: Record<Kind, { label: string; unit: string }>;
  bearing_combined?: { label: string; unit: string };
  node_labels: Record<string, string>; phase_labels: Record<Phase, string>;
  thresholds: {
    temperature: { bearing: TempBand; winding: TempBand; rotor: TempBand; default: TempBand; component_class: Record<string, string> };
    current_ratio: { safe_low: number; safe_high: number; danger_over: number; danger_under: number };
    i2i1: TempBand;
    bearing: { kurtosis: TempBand; hf_ratio: TempBand; combine: string; envelope_hint: boolean; envelope_hint_min_ratio?: number };
    hysteresis_fraction: number; persistence_s: Record<string, number>; vibration_split_kw: number;
    meta?: {                                   // P1: 지표별 출처·상태 (참고 배지). 없으면 배지 없음
      current_ratio?: MetricMeta; i2i1?: MetricMeta & { mode?: string; warn?: number; danger?: number; warn_multiple?: number; danger_multiple?: number; baseline?: unknown; reference_baseline?: { value?: number | null; dataset?: string } };
      temperature?: MetricMeta; vibration?: MetricMeta; bearing?: MetricMeta;
      policy?: Record<string, string>; stream?: string; thermal_scaling_note?: string;
    };
  };
  scenarios: Record<Mode, FleetScenario>;
  scene_map?: { id: string; label: string; mode: Mode; t_s: number; expect?: string }[];   // 단일 모터(M1) 첫 화면 빠른 이동 칩 (config/status_demo.yaml)
  demo_note: string;
  motors: MotorInfo[];
}
export type SceneValues = Record<string, number | string | null>;
export interface MotorSeries {
  motor: string; mode: Mode; n: number; source: string;
  t: number[]; step: string[]; time_scale: number[];
  temperature_C: Record<string, number[]>;
  current_rms_A: Record<Phase, number[]>; current_ratio: Record<Phase, number[]>;
  i2i1: number[]; vibration_mms: number[]; bearing_kurtosis: number[]; bearing_hf_ratio: number[];
  bearing_site_hint?: (string | null)[] | null;          // 결함 부위 추정(포락선 BPFO/BPFI) — 실측 전용, 시뮬레이션은 null
  status: Level[]; cause_signal: string[]; cause_component: string[]; cause_value: number[]; cause_threshold: string[];
  levels: Record<Kind, Level[]> & { bearing?: Level[] };
  scene_values: Record<string, SceneValues>;
  // 단순 보기 근거 서랍용 (export_status_data.py 필드 추가, 2026-10-26) — 케이스별 엔진 값. 없으면(구 export) undefined, 값이 없으면 null
  i2i1_fault?: (number | null)[]; i2_over_in?: (number | null)[]; i_f_A?: (number | null)[]; p_loop_total_W?: (number | null)[];
  winding_dT_C?: number[] | null; extras_note?: Record<string, string>;
  case_signals?: Record<string, CaseSignals>;    // 케이스별 대칭 성분·최근 2주기 파형 (단순 보기 ②③ 타일, 2026-10-26 §1b)
}
export interface CaseSignals { i1_A: number; i2_A: number; i0_A: number; waveform: { fs_Hz: number; f0_Hz: number; cycles: number; unit: string; t_ms: number[]; A: number[]; B: number[]; C: number[] } }
// 쉬운 말 사전 (public/content/status/labels_plain.yaml) — 전문 용어 ↔ 쉬운 말 ↔ 툴팁
export interface PlainLabel { plain: string; term: string; tip: string }
export interface PlainLabels {
  signals: Record<string, PlainLabel>;
  replace: { from: string; to: string; tip?: string }[];
  notes: Record<string, string>;
  thresholds_easy: Record<string, string>;
  tiles?: Record<string, string>;                 // 타일 제목 (map/wave/comp/trend/vib/bearing)
}
export const EMPTY_LABELS: PlainLabels = { signals: {}, replace: [], notes: {}, thresholds_easy: {}, tiles: {} };
export function plainOf(labels: PlainLabels, kind: string, fallback: string): PlainLabel {
  return labels.signals[kind] ?? { plain: fallback, term: fallback, tip: "" };
}
export interface StatusScene { title: string; fingerprint?: string; cause_chain?: CauseChain; data_source_note?: string; [k: string]: unknown }
export interface StatusContent {
  narration: Record<Mode, Record<string, StatusScene>>;
  glossary: { term: string; text: string }[];
  labels: PlainLabels;
}

export async function loadFleetIndex(): Promise<FleetIndex> {
  return getJson<FleetIndex>("data/fleet/index.json");
}
const cache = new Map<string, Promise<MotorSeries>>();
export function loadSeries(index: FleetIndex, id: string, mode: Mode): Promise<MotorSeries> {
  const m = index.motors.find((x) => x.id === id);
  if (!m) throw new Error(`모터 ${id} 가 index.json 에 없다`);
  const key = `${id}/${mode}`;
  let p = cache.get(key);
  if (!p) { p = getJson<MotorSeries>("data/fleet/" + m.files[mode]); cache.set(key, p); }
  return p;
}
export async function loadStatusContent(): Promise<StatusContent> {
  const [mech, elec, gl, lb] = await Promise.all([
    getYaml<{ scenes: Record<string, StatusScene> }>("content/mechanical/narration.yaml"),
    getYaml<{ scenes: Record<string, StatusScene> }>("content/electrical/narration.yaml"),
    getYamlOptional<{ items: { term: string; text: string }[] }>("content/status/glossary.yaml", { items: [] }),
    getYamlOptional<Partial<PlainLabels>>("content/status/labels_plain.yaml", EMPTY_LABELS),
  ]);
  return { narration: { mechanical: mech.scenes, electrical: elec.scenes }, glossary: gl.items ?? [], labels: { ...EMPTY_LABELS, ...lb } };
}

// 정렬된 시각 배열에서 t 이하의 마지막 인덱스
export function idxAt(a: number[], t: number): number {
  let lo = 0, hi = a.length - 1;
  if (t <= a[0]) return 0;
  if (t >= a[hi]) return hi;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m] <= t) lo = m; else hi = m; }
  return lo;
}
export function stepAt(sc: FleetScenario, t: number): FleetStep {
  const i = sc.steps.findIndex((s) => t < s.t_end);
  return sc.steps[i < 0 ? sc.steps.length - 1 : i];
}
// 시뮬레이션 경과(기계: 장면 배속 누적). 전기는 배속 1.
export function simElapsed(sc: FleetScenario, t: number): number {
  let acc = 0;
  for (const s of sc.steps) {
    if (t <= s.t_start) break;
    acc += (Math.min(t, s.t_end) - s.t_start) * (s.time_scale || 1);
  }
  return acc;
}
export function fmtSim(sec: number): string {
  if (sec < 90) return `${Math.round(sec)} 초`;
  if (sec < 5400) return `${(sec / 60).toFixed(1)} 분`;
  return `${(sec / 3600).toFixed(2)} 시간`;
}

// ---- 게이지 구간 (현재값만의 등급). 경계 숫자는 index.thresholds / 모터 진동 규격에서만 온다.
export interface Segment { from: number; to: number; level: Level; label?: string }
export interface GaugeSpec { min: number; max: number; segments: Segment[]; threshold: string; ticks?: { at: number; label: string }[] }

export function tempBand(index: FleetIndex, node: string): TempBand {
  const cls = index.thresholds.temperature.component_class[node] ?? "default";
  return (index.thresholds.temperature as unknown as Record<string, TempBand>)[cls] ?? index.thresholds.temperature.default;
}
export function gaugeTemp(index: FleetIndex, node: string, ambient = 20): GaugeSpec {
  const b = tempBand(index, node);
  const max = Math.ceil((b.danger_from * 1.35) / 10) * 10;
  return { min: ambient, max, threshold: `안전 <${b.safe_below} / 경고 ${b.safe_below}~${b.danger_from} / 위험 ≥${b.danger_from} °C`,
    segments: [{ from: ambient, to: b.safe_below, level: "SAFE" }, { from: b.safe_below, to: b.danger_from, level: "WARN" }, { from: b.danger_from, to: max, level: "DANGER" }] };
}
export function gaugeCurrent(index: FleetIndex): GaugeSpec {
  const r = index.thresholds.current_ratio;
  const max = 1.6;
  return { min: 0, max, threshold: `안전 ${r.safe_low}~${r.safe_high} / 경고 ${r.safe_high}~${r.danger_over} 또는 ${r.danger_under}~${r.safe_low} / 위험 >${r.danger_over} 또는 <${r.danger_under}`,
    segments: [{ from: 0, to: r.danger_under, level: "DANGER", label: "저전류" }, { from: r.danger_under, to: r.safe_low, level: "WARN" },
      { from: r.safe_low, to: r.safe_high, level: "SAFE" }, { from: r.safe_high, to: r.danger_over, level: "WARN" }, { from: r.danger_over, to: max, level: "DANGER", label: "과전류" }],
    ticks: [{ at: 1.0, label: "정격" }] };
}
export function gaugeLoHi(b: TempBand, max: number, unit: string): GaugeSpec {
  return { min: 0, max, threshold: `안전 <${b.safe_below} / 경고 ${b.safe_below}~${b.danger_from} / 위험 ≥${b.danger_from}${unit ? " " + unit : ""}`,
    segments: [{ from: 0, to: b.safe_below, level: "SAFE" }, { from: b.safe_below, to: b.danger_from, level: "WARN" }, { from: b.danger_from, to: max, level: "DANGER" }] };
}
export function gaugeVib(v: VibSpec): GaugeSpec {
  const max = Math.max(7, Math.ceil(v.act_mms * 1.5));
  const spec = gaugeLoHi({ safe_below: v.watch_mms, danger_from: v.act_mms }, max, "mm/s");
  spec.threshold += ` (${v.standard.split(" (")[0]})`;
  if (v.plan_mms < v.act_mms) spec.ticks = [{ at: v.plan_mms, label: "정비 계획" }];
  return spec;
}
export function levelOf(spec: GaugeSpec, x: number): Level {
  for (const s of spec.segments) if (x >= s.from && x < s.to) return s.level;
  return x >= spec.segments[spec.segments.length - 1].from ? spec.segments[spec.segments.length - 1].level : spec.segments[0].level;
}
// 추세 차트 구간 사양 (신호 종류별). 상태 보드 전문가·단순 보기가 같이 쓴다.
export function specFor(index: FleetIndex, motor: MotorInfo, sel: { kind: Kind; component?: string }): GaugeSpec {
  if (sel.kind === "temperature") return gaugeTemp(index, sel.component ?? "bearing_de");
  if (sel.kind === "current_ratio") return gaugeCurrent(index);
  if (sel.kind === "i2i1") return gaugeLoHi(index.thresholds.i2i1, 0.3, "");
  if (sel.kind === "vibration") return gaugeVib(motor.vibration);
  if (sel.kind === "bearing_kurtosis") return gaugeLoHi(index.thresholds.bearing.kurtosis, 8, "");
  return gaugeLoHi(index.thresholds.bearing.hf_ratio, 5, "배");
}
export const RANK: Record<Level, number> = { SAFE: 0, WARN: 1, DANGER: 2 };
export function worse(a: Level, b: Level): Level { return RANK[a] >= RANK[b] ? a : b; }
// 베어링 종합 등급 (둘 중 나쁜 쪽). 엔진이 써 둔 levels.bearing 이 있으면 그것, 없으면 두 지표 등급에서 합성.
export function bearingLevel(s: MotorSeries, i: number): Level {
  return s.levels.bearing?.[i] ?? worse(s.levels.bearing_kurtosis[i], s.levels.bearing_hf_ratio[i]);
}

// 원인 한 줄: "DE 베어링 온도 91.2 °C — 경고 (안전 <70 / …)"
export function causeLine(index: FleetIndex, s: MotorSeries, i: number): { head: string; detail: string; level: Level } {
  const level = s.status[i];
  const kind = s.cause_signal[i] as Kind | "-";
  if (level === "SAFE" || kind === "-") return { head: "모든 신호가 안전 범위", detail: "원인 신호 없음", level: "SAFE" };
  const comp = s.cause_component[i];
  const sig = index.signals[kind];
  const compLabel = kind === "temperature" ? (index.node_labels[comp] ?? comp) + " "
    : kind === "current_ratio" ? (index.phase_labels[comp as Phase] ?? comp) + "상 " : "";
  const v = s.cause_value[i];
  const val = kind === "current_ratio" ? `${v.toFixed(2)}× (${Math.round(v * 100)} %)` : kind === "i2i1" ? v.toFixed(3)
    : kind === "bearing_kurtosis" ? v.toFixed(1) : `${v.toFixed(1)}${sig.unit ? " " + sig.unit : ""}`;
  return { head: `${compLabel}${sig.label} ${val} — ${index.labels_ko[level]}`, detail: s.cause_threshold[i], level };
}
