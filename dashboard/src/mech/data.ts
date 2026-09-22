// mech/data.ts — 기계 실시간 해설 대시보드 전용 데이터 (export_mechanical_extras.py 출력 + content YAML).
// 공통 ModeData(data.ts) 위에 얹는다. 전기 대시보드는 이 파일을 쓰지 않는다.
import yaml from "js-yaml";
import type { ModeData, Stage, Timeseries } from "../data";

export interface MechTimeseries extends Timeseries {
  loss_W: Record<string, number[]>;
  time_scale: number[];
  sim_elapsed_s: number[];
  step_elapsed_s: number[];
  step_n: number[];
  replay_check: { method: string; max_err_inner_C: Record<string, number>; max_err_edge_C: Record<string, number>; pass: boolean };
}
export type EventType = "scene" | "stage_up" | "stage_down" | "recovered" | "vib_zone" | "xray_on" | "xray_off";
export interface MechEvent {
  id: number; type: EventType; t: number; scene: number; priority: number;
  part?: string; part_label?: string; from?: string; to?: string; from_ko?: string; to_ko?: string;
  threshold_C?: number | null; temp_C?: number; is_focus?: boolean; note?: string;
  threshold_mms?: number; value_mms?: number; up?: boolean;
  scene_id?: string; time_scale?: number; label?: string;
}
export type SceneValues = Record<string, number | string | null>;

export interface SceneNarration {
  title: string; fingerprint: string; focus_component: string; heat_path: string[];
  reveal_timing: { why: number; visible: number; result: number };
  why: string; visible: string; result: string; presenter_line: string;
  cause_chain: { cause: string; mechanism: string; effect: string; action: string };
}
export interface MechContent {
  scenes: Record<string, SceneNarration>;
  templates: Record<string, Record<string, string>>;
  qa: { q: string; a: string; scene?: string }[];
}
export interface MechData extends ModeData {
  timeseries: MechTimeseries;
  events: MechEvent[];
  values: Record<string, SceneValues>;
  content: MechContent;
}

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} (${r.status}) — export_dashboard_data.py --mode mechanical 을 먼저 실행`);
  return r.json();
}
// 문구 파일은 빌드에 넣지 않고 런타임에 읽는다 → 발표자가 YAML 을 고치고 새로고침만 하면 반영된다
async function getYaml<T>(path: string): Promise<T> {
  const r = await fetch(path + "?v=" + Date.now());
  if (!r.ok) throw new Error(`${path} (${r.status})`);
  return yaml.load(await r.text()) as T;
}

export async function loadMechData(base: ModeData): Promise<MechData> {
  const [events, values, scenes, templates, qa] = await Promise.all([
    getJson<{ events: MechEvent[] }>("data/mechanical/events.json"),
    getJson<{ scenes: Record<string, SceneValues> }>("data/mechanical/narration_values.json"),
    getYaml<{ scenes: Record<string, SceneNarration> }>("content/mechanical/narration.yaml"),
    getYaml<Record<string, Record<string, string>>>("content/mechanical/event_templates.yaml"),
    getYaml<{ items: MechContent["qa"] }>("content/mechanical/qa.yaml"),
  ]);
  const ts = base.timeseries as MechTimeseries;
  if (!ts.loss_W) throw new Error("timeseries.json 에 loss_W 가 없다 — export 를 다시 실행");
  return { ...base, timeseries: ts, events: events.events, values: values.scenes,
           content: { scenes: scenes.scenes, templates, qa: qa.items } };
}

// {변수} 치환. 값이 없으면 변수명을 그대로 남겨 눈에 띄게 한다 (테스트가 미정의 변수를 잡는다).
export function fill(text: string, v: SceneValues | undefined): string {
  if (!v) return text;
  return text.replace(/\{([a-zA-Z0-9_]+)\}/g, (m, k) => {
    const x = v[k];
    if (x === undefined || x === null) return m;
    return typeof x === "number" ? fmtNum(x) : String(x);
  });
}
function fmtNum(x: number): string {
  return Number.isInteger(x) ? String(x) : String(Math.round(x * 10) / 10);
}
export function fmtSim(sec: number): string {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return m >= 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m}분 ${s.toString().padStart(2, "0")}초`;
}
export const STAGE_ORDER: Stage[] = ["normal", "caution", "warning", "danger"];
