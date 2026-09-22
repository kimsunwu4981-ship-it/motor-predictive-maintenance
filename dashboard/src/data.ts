// data.ts — export_dashboard_data.py 가 만든 JSON 의 타입과 로더.
// 대시보드의 모든 숫자는 여기서 읽은 값만 쓴다 (dashboard/CLAUDE.md 규칙 1).

export type Mode = "mechanical" | "electrical";
export type Stage = "normal" | "caution" | "warning" | "danger";
export type ElecStatus = "over_danger" | "over_caution" | "normal" | "under_caution" | "under_danger";

export interface PartThreshold {
  key: string; label: string; hud: boolean;
  normal_max_C: number; caution_max_C: number; warning_max_C: number; note: string;
}
export interface ElecRow {
  status: ElecStatus; label: string; ratio_text: string; ratio: number | null;
  line_A: number | null; phase_A: number | null;
  line_range_A: [number, number] | null; phase_range_A: [number, number] | null; color: string;
}
export interface Thresholds {
  mode: Mode;
  motor: {
    power_kW: number; poles: number; voltage_LL_V: number; frequency_Hz: number; rated_rpm: number;
    connection: string; rated_line_A: number; rated_phase_A: number; drawing: string; target: string;
    current_source: string;
  };
  honesty: { label: string; rating_basis: string; current_note: string; thermal_note: string };
  thermal: {
    parts: PartThreshold[]; stage_colors: Record<Stage, string>; stage_labels: Record<Stage, string>;
    base_material: string; pulse_hz: number; pulse_from_stage: Stage;
  };
  electrical: {
    rated_line_A: number; rated_phase_A: number;
    ratio_thresholds: { over_danger: number; over_caution: number; under_caution: number; under_danger: number };
    rows: ElecRow[]; status_colors: Record<ElecStatus, string>; status_labels: Record<ElecStatus, string>;
    short_loop_color: string; i2i1_marks: { case: string; label: string; value: number }[]; slowmo_factor: number;
  };
}

export interface Step {
  n: number; id: string; label: string; subtitle: string; source: string;
  t_start: number; t_end: number; video_start: number; video_end: number;
  electrical_case: string; faults: string[]; load: number; time_scale: number; highlight: boolean;
  clip: string | null;
}
export interface LeadTime {
  basis: string; alarm_t: number | null; danger_t: number | null; lead_s: number | null; lead_sim_s: number | null;
  alarm_part?: string | null; danger_part?: string | null; alarm_level_i2i1?: number | null;
}
export interface Scenarios {
  mode: Mode; video: string; video_offset_s: number; video_duration_s: number | null;
  total_duration_s: number; steps: Step[]; lead_time: LeadTime;
}

export interface Timeseries {
  mode: Mode; n: number; t_real_s: number[]; step: string[];
  temperature_C: Record<string, number[]>; stage: Record<string, Stage[]>;
  current_rms_A: { A: number[]; B: number[]; C: number[] };
  current_status: { A: ElecStatus[]; B: ElecStatus[]; C: ElecStatus[] };
  i2_over_i1: number[]; vibration_mms: number[]; iso_zone: string[];
}

export interface FaultItem {
  key: string; label: string; target?: string | null;
  loss_multiplier?: number | null; load_multiplier?: number | null; r_amb_multiplier?: number | null;
  extra_loss_W?: number | null; vibration_mms?: number | null;
  phase_scale?: number[]; load?: number; target_i2i1?: number | null; rms_A?: number[]; ratio?: number[];
  status?: ElecStatus[]; i2_over_i1?: number;
}
export interface Faults { mode: Mode; items: FaultItem[] }

export interface ModeData { thresholds: Thresholds; scenarios: Scenarios; timeseries: Timeseries; faults: Faults }

export async function loadModeData(mode: Mode): Promise<ModeData> {
  const base = `data/${mode}/`;
  const get = async <T,>(n: string): Promise<T> => {
    const r = await fetch(base + n + ".json");
    if (!r.ok) throw new Error(`${base}${n}.json 을 읽지 못했다 (${r.status}) — export_dashboard_data.py 를 먼저 실행`);
    return r.json();
  };
  const [thresholds, scenarios, timeseries, faults] = await Promise.all([
    get<Thresholds>("thresholds"), get<Scenarios>("scenarios"), get<Timeseries>("timeseries"), get<Faults>("faults"),
  ]);
  return { thresholds, scenarios, timeseries, faults };
}

// ---- 조회 도우미 (재생 시각 t_real 기준) ----
export function indexAt(ts: Timeseries, t: number): number {
  const a = ts.t_real_s;
  let lo = 0, hi = a.length - 1;
  if (t <= a[0]) return 0;
  if (t >= a[hi]) return hi;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m] <= t) lo = m; else hi = m; }
  return lo;
}
export function stepAt(sc: Scenarios, t: number): Step {
  return sc.steps.find((s) => t < s.t_end) ?? sc.steps[sc.steps.length - 1];
}
export const STAGE_ORDER: Stage[] = ["normal", "caution", "warning", "danger"];
export function worstStage(ts: Timeseries, i: number, keys?: string[]): Stage {
  let w: Stage = "normal";
  for (const k of keys ?? Object.keys(ts.stage)) {
    const s = ts.stage[k][i];
    if (STAGE_ORDER.indexOf(s) > STAGE_ORDER.indexOf(w)) w = s;
  }
  return w;
}
const ELEC_SEVERITY: Record<ElecStatus, number> = { normal: 0, over_caution: 1, under_caution: 1, over_danger: 2, under_danger: 2 };
export function worstElec(ts: Timeseries, i: number): ElecStatus {
  let w: ElecStatus = "normal";
  for (const p of ["A", "B", "C"] as const) {
    const s = ts.current_status[p][i];
    if (ELEC_SEVERITY[s] > ELEC_SEVERITY[w]) w = s;
  }
  return w;
}
export function fmtT(t: number): string {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
