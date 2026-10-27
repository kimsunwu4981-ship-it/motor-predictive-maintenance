// elec/data.ts — 전기 실시간 해설 대시보드 전용 데이터 (export_electrical_extras.py 출력 + content YAML).
// 공통 ModeData(data.ts) 와 공통 LiveData(live/types.ts) 위에 얹는다. 기계 대시보드는 이 파일을 쓰지 않는다.
import type { ElecStatus, ModeData, Thresholds, Timeseries } from "../../data";
import { getJson, getYaml, getYamlOptional } from "../../live/load";
import type { GlossaryItem, LiveData, LiveEvent, LiveScene, QaItem, SceneValues, Templates } from "../../live/types";
import type { ElecSource } from "../../live/feed";

export type Phase = "A" | "B" | "C";
export const PHASES: Phase[] = ["A", "B", "C"];
export type Basis = "line" | "phase";     // 케이블 = 선전류, 권선 = 상전류 (Δ 면 √3 배, Y(M1)면 같음) — 정격값은 thresholds.json 에서

export interface ElecTimeseries extends Timeseries {
  ratio: Record<Phase, number[]>;          // 정격 대비 (선전류/정격 선전류 = 상전류/정격 상전류)
  phase_rms_A: Record<Phase, number[]>;
  phasor_deg: Record<Phase, number[]>;     // 기본파 페이저 각 (엔진 재계산, config 위상)
  case: string[];
  i2_over_in?: (number | null)[];          // 라이브(LUT 방식)에서만 — 부하 무관 보조 지표, 판정 없음
  recompute_check: { method: string; max_rms_diff_A: number; max_i2i1_diff: number; max_i2i1_diff_from_log_rms: number; pass: boolean };
}
export interface ElecEvent extends LiveEvent {
  phase?: string; phase_label?: string; from?: ElecStatus; to?: ElecStatus; from_ko?: string; to_ko?: string;
  rms_A?: number; pct?: number; threshold_A?: number; others?: string; is_focus?: boolean;
  mark?: string; level?: number; value?: number; prev?: number; x_normal?: number; up?: boolean; turns?: number;
}
export interface ElecScene extends LiveScene {
  focus_phases: Phase[]; focus_i2i1: boolean; matrix_label: string;
  circuit: { short_loop?: Phase; open_phase?: Phase; voltage_note?: string };
}
export interface MatrixPoint { scene: number; id: string; label: string; x_i2i1: number; y_ratio_max: number; y_ratio_mean: number; y_ratio_min: number }
export type ElecThresholds = Thresholds & {
  electrical: Thresholds["electrical"] & {
    slowmo_x: number; slowmo_label: string; phase_labels: Record<Phase, string>; phase_colors: Record<Phase, number[]>; status_rgb: Record<ElecStatus, number[]>;
    short_loop: { rgb: number[]; pulse_hz: number }; model_note: string; matrix: MatrixPoint[];
  };
};
export interface Waveforms {
  f0_Hz: number; samples: number; deg: number[];
  cases: Record<string, { A: number[]; B: number[]; C: number[]; deg: number[]; ratio: number[] }>;
}
export interface ElecData extends ModeData, LiveData<ElecScene> {
  mode: "electrical";
  thresholds: ElecThresholds;
  timeseries: ElecTimeseries;
  events: ElecEvent[];
  waveforms: Waveforms;
  content: { scenes: Record<string, ElecScene>; templates: Templates; qa: QaItem[]; glossary: GlossaryItem[] };
  source?: ElecSource | null;             // 전류 신호 근거 (라이브 state.electrical_source). 녹화 데이터는 undefined = legacy 해석식
}

export async function loadElecData(base: ModeData): Promise<ElecData> {
  const [events, values, waves, scenes, templates, qa, glossary] = await Promise.all([
    getJson<{ events: ElecEvent[] }>("data/electrical/events.json"),
    getJson<{ scenes: Record<string, SceneValues> }>("data/electrical/narration_values.json"),
    getJson<Waveforms>("data/electrical/waveforms.json"),
    getYaml<{ scenes: Record<string, ElecScene> }>("content/electrical/narration.yaml"),
    getYaml<Templates>("content/electrical/event_templates.yaml"),
    getYamlOptional<{ items: QaItem[] }>("content/electrical/qa.yaml", { items: [] }),
    getYamlOptional<{ items: GlossaryItem[] }>("content/electrical/glossary.yaml", { items: [] }),
  ]);
  const ts = base.timeseries as ElecTimeseries;
  if (!ts.ratio || !ts.phasor_deg) throw new Error("timeseries.json 에 전기 확장(ratio/phasor_deg)이 없다 — export --mode electrical 을 다시 실행");
  const th = base.thresholds as ElecThresholds;
  if (!th.electrical.matrix || !th.electrical.slowmo_x) throw new Error("thresholds.json 에 전기 확장(matrix/slowmo_x)이 없다 — export 를 다시 실행");
  const data: ElecData = {
    ...base, mode: "electrical", thresholds: th, timeseries: ts, events: events.events, values: values.scenes, waveforms: waves,
    content: { scenes: scenes.scenes, templates, qa: qa.items ?? [], glossary: glossary.items ?? [] },
    live: (t) => liveValues(data, t),
    timeNote: () => [{ label: "입자 흐름", value: `${th.electrical.slowmo_x}배 느리게` }, { label: "실제", value: `${th.motor.frequency_Hz} Hz` }],
  };
  return data;
}

export function idxAt(ts: Timeseries, t: number): number {
  const a = ts.t_real_s;
  let lo = 0, hi = a.length - 1;
  if (t <= a[0]) return 0;
  if (t >= a[hi]) return hi;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m] <= t) lo = m; else hi = m; }
  return lo;
}

// ---- 실시간 치환 변수 ----
// {a|b|c}_rms_now / _pct_now / _status_now / _phase_rms_now, i2i1_now, i2i1_x_normal_now — 재생 시각 t 의 로그 값.
// 테스트(test_electrical_extras.py LIVE_VARS)가 이 목록을 안다.
export function liveValues(data: ElecData, t: number): SceneValues {
  const ts = data.timeseries, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const normal = el.i2i1_marks.find((m) => m.case === "healthy")?.value ?? 0;
  const v: SceneValues = {
    i2i1_now: ts.i2_over_i1[i],
    i2i1_x_normal_now: normal > 0 ? Math.round((ts.i2_over_i1[i] / normal) * 10) / 10 : null,
  };
  for (const p of PHASES) {
    const lp = p.toLowerCase();
    v[`${lp}_rms_now`] = ts.current_rms_A[p][i];
    v[`${lp}_pct_now`] = Math.round(ts.ratio[p][i] * 100);
    v[`${lp}_status_now`] = el.status_labels[ts.current_status[p][i]];
    v[`${lp}_phase_rms_now`] = Math.round(ts.phase_rms_A[p][i] * 10) / 10;
  }
  return v;
}

export const ELEC_ORDER: ElecStatus[] = ["under_danger", "under_caution", "normal", "over_caution", "over_danger"];
export const ELEC_SEVERITY: Record<ElecStatus, number> = { normal: 0, over_caution: 1, under_caution: 1, over_danger: 2, under_danger: 2 };
// 기준(선/상)에 따른 암페어 값
export function ampere(data: ElecData, ratio: number, basis: Basis): number {
  const el = data.thresholds.electrical;
  return ratio * (basis === "line" ? el.rated_line_A : el.rated_phase_A);
}
