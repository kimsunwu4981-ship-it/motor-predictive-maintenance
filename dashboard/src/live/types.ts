// live/types.ts — 실시간 해설 대시보드의 공통 타입·치환 함수 (기계·전기 공용).
// 모드별 데이터(src/mech/data.ts, src/elec/data.ts)는 이 LiveData 를 만족하도록 자기 값을 채운다.
// 공통 컴포넌트(live/*)는 LiveData 만 안다 — 부품·상(phase) 같은 모드 고유 개념은 여기 없다.
import type { Scenarios } from "../data";

export type Mode = "mechanical" | "electrical";
export type SceneValues = Record<string, number | string | null>;

// export 가 로그에서 만든 사건. 모드마다 필드가 다르므로 공통 필드만 고정하고 나머지는 열어 둔다.
export interface LiveEvent { id: number; type: string; t: number; scene: number; priority: number; tpl?: string; [k: string]: unknown }
export interface RevealTiming { why: number; visible: number; result: number }
export interface CauseChain { cause: string; mechanism: string; effect: string; action: string }
export interface LiveScene {
  title: string; fingerprint: string; reveal_timing: RevealTiming;
  why: string; visible: string; result: string; presenter_line: string; cause_chain: CauseChain;
  data_source_note?: string; [k: string]: unknown;
}
export type Templates = Record<string, Record<string, string>>;
export interface QaItem { q: string; a: string; scene?: string }
export interface LiveContent<S extends LiveScene = LiveScene> { scenes: Record<string, S>; templates: Templates; qa: QaItem[] }
export interface TimeNote { label: string; value: string }
export interface LiveData<S extends LiveScene = LiveScene> {
  mode: Mode;
  scenarios: Scenarios;
  events: LiveEvent[];
  values: Record<string, SceneValues>;          // 장면 종료 값 (narration_values.json)
  content: LiveContent<S>;
  live: (t: number) => SceneValues;             // 재생 시각의 실시간 변수 ({…}_now)
  timeNote: (t: number) => TimeNote[];          // 상단·발표자 화면의 시간 표기 (기계: 시뮬 경과·배속, 전기: 슬로모션)
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
export function fmtNum(x: number): string {
  if (Number.isInteger(x)) return String(x);
  const a = Math.abs(x);
  const d = a < 0.01 ? 4 : a < 1 ? 3 : 1;      // I₂/I₁ 같은 작은 값은 자리수를 살린다
  return String(Math.round(x * 10 ** d) / 10 ** d);
}
// fill 과 같지만 치환된 값을 구분해 돌려준다 (화면에서 수치를 굵게 보여주기 위해)
export function fillParts(text: string, v: SceneValues | undefined): { s: string; v: boolean }[] {
  const out: { s: string; v: boolean }[] = [];
  let last = 0;
  const re = /\{([a-zA-Z0-9_]+)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ s: text.slice(last, m.index), v: false });
    const x = v?.[m[1]];
    if (x === undefined || x === null) out.push({ s: m[0], v: false });
    else out.push({ s: typeof x === "number" ? fmtNum(x) : String(x), v: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ s: text.slice(last), v: false });
  return out;
}
