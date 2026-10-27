// mech/data.ts — 기계 실시간 해설 대시보드 전용 데이터 (export_mechanical_extras.py 출력 + content YAML).
// 공통 ModeData(data.ts) 와 공통 LiveData(live/types.ts) 위에 얹는다. 전기 대시보드는 이 파일을 쓰지 않는다.
import type { ModeData, Stage, Timeseries } from "../../data";
import { getJson, getYaml } from "../../live/load";
import { fill, fillParts, fmtNum, type LiveData, type LiveEvent, type LiveScene, type QaItem, type SceneValues, type Templates } from "../../live/types";
export { fill, fillParts, fmtNum };
export type { SceneValues };

export interface MechTimeseries extends Timeseries {
  loss_W: Record<string, number[]>;
  time_scale: number[];
  sim_elapsed_s: number[];
  step_elapsed_s: number[];
  step_n: number[];
  replay_check: { method: string; max_err_inner_C: Record<string, number>; max_err_edge_C: Record<string, number>; pass: boolean };
}
export type EventType = "scene" | "stage_up" | "stage_down" | "recovered" | "vib_zone" | "xray_on" | "xray_off";
export interface MechEvent extends LiveEvent {
  type: EventType;
  part?: string; part_label?: string; from?: string; to?: string; from_ko?: string; to_ko?: string;
  threshold_C?: number | null; temp_C?: number; is_focus?: boolean; note?: string;
  threshold_mms?: number; value_mms?: number; up?: boolean;
  scene_id?: string; time_scale?: number; label?: string;
}
export interface SceneNarration extends LiveScene {
  focus_component: string; heat_path: string[];
}
export interface MechContent { scenes: Record<string, SceneNarration>; templates: Templates; qa: QaItem[] }
// 기계 export 확장이 들어간 thresholds — 진동 경계·컬러맵 원본은 필수
export type MechThresholds = ModeData["thresholds"] & {
  vibration_iso: { watch_mms: number; plan_mms: number; act_mms: number; zone_labels: Record<string, string>; basis: string };
  thermal: ModeData["thresholds"]["thermal"] & { colormap: import("./colormap").ThermalColormap; couplings: { a: string; b: string; R_K_per_W: number }[]; loss_rated_W: Record<string, number> };
};
export interface MechData extends ModeData, LiveData<SceneNarration> {
  mode: "mechanical";
  thresholds: MechThresholds;
  timeseries: MechTimeseries;
  events: MechEvent[];
  content: MechContent;
}

export async function loadMechData(base: ModeData): Promise<MechData> {
  const [events, values, scenes, templates, qa] = await Promise.all([
    getJson<{ events: MechEvent[] }>("data/mechanical/events.json"),
    getJson<{ scenes: Record<string, SceneValues> }>("data/mechanical/narration_values.json"),
    getYaml<{ scenes: Record<string, SceneNarration> }>("content/mechanical/narration.yaml"),
    getYaml<Templates>("content/mechanical/event_templates.yaml"),
    getYaml<{ items: QaItem[] }>("content/mechanical/qa.yaml"),
  ]);
  const ts = base.timeseries as MechTimeseries;
  if (!ts.loss_W) throw new Error("timeseries.json 에 loss_W 가 없다 — export 를 다시 실행");
  const th = base.thresholds as MechThresholds;
  if (!th.vibration_iso || !th.thermal.colormap) throw new Error("thresholds.json 에 기계 확장(vibration_iso/colormap)이 없다 — export 를 다시 실행");
  const data: MechData = {
    ...base, mode: "mechanical", thresholds: th, timeseries: ts, events: events.events, values: values.scenes,
    content: { scenes: scenes.scenes, templates, qa: qa.items },
    live: (t) => liveValues(data, t),
    timeNote: (t) => { const i = idx(ts, t); return [{ label: "시뮬레이션 경과", value: fmtSim(ts.sim_elapsed_s[i]) }, { label: "화면 1초 = 시뮬레이션", value: `${ts.time_scale[i]}초` }]; },
  };
  return data;
}

function idx(ts: Timeseries, t: number): number {
  const a = ts.t_real_s;
  let lo = 0, hi = a.length - 1;
  if (t <= a[0]) return 0;
  if (t >= a[hi]) return hi;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (a[m] <= t) lo = m; else hi = m; }
  return lo;
}

// ---- 실시간 치환 변수 (M4) ----
// 장면 문구의 {부품}_now / {부품}_stage_now / vib_now / iso_now_ko / sim_elapsed_now / time_scale_now 는
// export 가 아니라 화면이 재생 시각 t 의 로그 값으로 채운다. 값의 출처는 여전히 timeseries.json(로그)뿐이다.
// 장면 종료 값({부품}_end 등)은 narration_values.json 그대로 쓴다. 테스트(test_mechanical_extras.py)가 이 목록을 안다.
export const LIVE_VAR_SUFFIXES = ["_now", "_stage_now"] as const;
export const LIVE_VAR_NAMES = ["vib_now", "iso_now_ko", "sim_elapsed_now", "time_scale_now"] as const;
export function liveValues(data: MechData, t: number): SceneValues {
  const ts = data.timeseries, th = data.thresholds;
  const i = idx(ts, t);
  const v: SceneValues = {
    vib_now: ts.vibration_mms[i], iso_now_ko: th.vibration_iso.zone_labels[ts.iso_zone[i]] ?? ts.iso_zone[i],
    sim_elapsed_now: fmtSim(ts.sim_elapsed_s[i]), time_scale_now: ts.time_scale[i],
  };
  for (const p of th.thermal.parts) {
    v[`${p.key}_now`] = ts.temperature_C[p.key][i];
    v[`${p.key}_stage_now`] = th.thermal.stage_labels[ts.stage[p.key][i]];
  }
  return v;
}
export function fmtSim(sec: number): string {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return m >= 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m}분 ${s.toString().padStart(2, "0")}초`;
}
export const STAGE_ORDER: Stage[] = ["normal", "caution", "warning", "danger"];
