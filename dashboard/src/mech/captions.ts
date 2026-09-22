// captions.ts — 이벤트 자막 · 이력 목록 · 장면 해설 단계별 공개 (TASK 5.2).
//
// 사건의 시각·수치는 export 가 로그에서 만든 events.json 에서만 온다. 여기서는 문구 템플릿(event_templates.yaml)에
// 끼워 넣고, 같은 순간에 몰린 사건을 우선순위로 하나만 고르며, 장면 해설이 언제 공개되는지(reveal_timing)를 계산한다.
import type { Step } from "../data";
import { fmtNum, liveValues, fill, type MechData, type MechEvent, type SceneNarration } from "./data";

export const CLUSTER_S = 1.0;      // 이 시간 안에 몰린 사건은 "같은 순간" — 우선순위가 가장 높은 것만 자막
export const CAPTION_HOLD_S = 8;   // 자막 유지 시간 [s] (다음 사건이 오면 즉시 교체)
export const SCENE_HOLD_S = 6;     // 장면 전환 표시 유지 시간 [s]

export type Templates = Record<string, Record<string, string>>;

// 사건 한 건 → 자막 문구. 템플릿 선택 규칙: stage_up 은 early_warning / danger / default, vib_zone 은 up / down.
export function captionText(e: MechEvent, tpl: Templates): string {
  const g = tpl[e.type] ?? {};
  let key = "default";
  if (e.type === "stage_up") key = e.note === "early_warning" ? "early_warning" : e.to === "danger" ? "danger" : "default";
  else if (e.type === "vib_zone") key = e.up ? "up" : "down";
  const text = g[key] ?? g.default ?? `[${e.type} 템플릿 없음]`;
  return text.replace(/\{([a-zA-Z0-9_]+)\}/g, (m, k) => {
    const x = (e as unknown as Record<string, unknown>)[k];
    if (x === undefined || x === null) return m;
    return typeof x === "number" ? fmtNum(x) : String(x);
  });
}

// 같은 순간(CLUSTER_S 안)에 몰린 사건 묶음. primary 가 자막, others 는 목록에만 쌓인다. 장면 전환은 별도 줄이라 제외.
export interface Cluster { t: number; primary: MechEvent; others: MechEvent[] }
export function buildClusters(events: MechEvent[]): Cluster[] {
  const out: Cluster[] = [];
  for (const e of events) {
    if (e.type === "scene") continue;
    const last = out[out.length - 1];
    if (last && e.t - last.t <= CLUSTER_S) {
      if (e.priority < last.primary.priority) { last.others.push(last.primary); last.primary = e; } else last.others.push(e);
    } else out.push({ t: e.t, primary: e, others: [] });
  }
  return out;
}

// t 시각에 떠 있어야 할 자막 (없으면 null). 마지막 묶음이 HOLD 안이면 그것.
export function captionAt(clusters: Cluster[], t: number): { cluster: Cluster; age: number } | null {
  let lo = -1;
  for (let i = 0; i < clusters.length && clusters[i].t <= t; i++) lo = i;
  if (lo < 0) return null;
  const c = clusters[lo], age = t - c.t;
  return age <= CAPTION_HOLD_S ? { cluster: c, age } : null;
}
export function sceneCaptionAt(events: MechEvent[], t: number, tpl: Templates): { text: string; age: number } | null {
  let last: MechEvent | null = null;
  for (const e of events) { if (e.type === "scene" && e.t <= t) last = e; }
  if (!last) return null;
  const age = t - last.t;
  return age <= SCENE_HOLD_S ? { text: captionText(last, tpl), age } : null;
}

// ---- 장면 해설 단계별 공개 (narration.yaml reveal_timing = 장면 진행률 0~1) ----
export type RevealKey = "why" | "visible" | "result";
export const REVEAL_KEYS: RevealKey[] = ["why", "visible", "result"];
export const REVEAL_LABEL: Record<RevealKey, string> = { why: "왜 그런가", visible: "무엇이 보이나", result: "그래서" };

export function revealTimes(scene: SceneNarration, step: Step): Record<RevealKey, number> {
  const dur = step.t_end - step.t_start;
  const rt = scene.reveal_timing ?? { why: 0, visible: 0.4, result: 0.8 };
  return { why: step.t_start + dur * rt.why, visible: step.t_start + dur * rt.visible, result: step.t_start + dur * rt.result };
}
// 자동 해설 모드: t 까지 공개된 단계 수 (0~3)
export function autoLevel(scene: SceneNarration, step: Step, t: number): number {
  const rt = revealTimes(scene, step);
  return REVEAL_KEYS.filter((k) => t >= rt[k] - 1e-6).length;
}

// ---- 이력 목록: 사건 + 장면 전환 + 해설 공개, 시간순. 항목을 누르면 그 시점으로 이동 ----
export interface HistoryItem { t: number; kind: "scene" | "event" | "narr"; text: string; primary: boolean; scene: number; id: string; type?: string }
export function buildHistory(data: MechData, clusters: Cluster[]): HistoryItem[] {
  const items: HistoryItem[] = [];
  const tpl = data.content.templates;
  for (const e of data.events) if (e.type === "scene") items.push({ t: e.t, kind: "scene", text: captionText(e, tpl), primary: true, scene: e.scene, id: `e${e.id}`, type: e.type });
  for (const c of clusters) {
    items.push({ t: c.primary.t, kind: "event", text: captionText(c.primary, tpl), primary: true, scene: c.primary.scene, id: `e${c.primary.id}`, type: c.primary.type });
    for (const o of c.others) items.push({ t: o.t, kind: "event", text: captionText(o, tpl), primary: false, scene: o.scene, id: `e${o.id}`, type: o.type });
  }
  for (const step of data.scenarios.steps) {
    const scene = data.content.scenes[step.id]; if (!scene) continue;
    const rt = revealTimes(scene, step);
    for (const k of REVEAL_KEYS) {
      const v = { ...data.values[step.id], ...liveValues(data, rt[k]) };   // 공개 시점의 수치로 채운다
      items.push({ t: rt[k], kind: "narr", text: `${REVEAL_LABEL[k]} — ${fill(scene[k], v)}`, primary: true, scene: step.n, id: `n${step.id}_${k}` });   // 목록에서는 한 줄로 잘라 보여준다 (CSS ellipsis)
    }
  }
  // 같은 시각이면 장면 → 해설 → 사건 순
  const rank = { scene: 0, narr: 1, event: 2 };
  items.sort((a, b) => a.t - b.t || rank[a.kind] - rank[b.kind]);
  return items;
}
