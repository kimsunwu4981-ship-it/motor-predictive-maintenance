// status/nameplate.ts — 명판값 입력 (TASK_다중모터 §8 P5). 사용자가 모터 명판값을 넣으면 그 모터의 출처가 nameplate 로 바뀌고 라벨이 바뀐다.
//
// 저장은 이 브라우저의 localStorage 에만 한다 (발표장 PC 의 편의 기능). 정본은 config/motors/<id>.yaml 이므로, 폼이 YAML 조각을 만들어 주고
// 그것을 파일에 붙여 넣은 뒤 배치(run_fleet → export_status_data)를 다시 돌려야 판정·수렴 온도까지 바뀐다. 보드에서 즉시 바뀌는 것은
// 사양 표시·정격 전류 기준 게이지(전류 비율)뿐이고, 판정 상태는 "배치 재실행 전" 표시를 붙인다.
import type { FleetIndex, MotorInfo, MotorSpec } from "./data";

export const NAMEPLATE_FIELDS: { key: keyof MotorSpec; label: string; unit: string; step?: number }[] = [
  { key: "rated_power_kw", label: "정격 출력", unit: "kW", step: 0.1 },
  { key: "rated_rpm", label: "정격 회전수", unit: "rpm", step: 1 },
  { key: "voltage_v", label: "정격 전압", unit: "V", step: 1 },
  { key: "rated_line_current_a", label: "정격 선전류", unit: "A", step: 0.1 },
  { key: "rated_phase_current_a", label: "정격 상전류", unit: "A", step: 0.1 },
  { key: "efficiency", label: "효율", unit: "", step: 0.001 },
  { key: "power_factor", label: "역률", unit: "", step: 0.001 },
  { key: "frame", label: "프레임", unit: "" },
  { key: "bearing_de", label: "베어링 DE", unit: "" },
  { key: "bearing_nde", label: "베어링 NDE", unit: "" },
];
export interface Nameplate { values: Partial<MotorSpec>; entered_at: string; note?: string }
export type Nameplates = Record<string, Nameplate>;
const KEY = "vigent-nameplate";

export function loadNameplates(): Nameplates {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Nameplates; } catch { return {}; }
}
export function saveNameplates(n: Nameplates) {
  try { localStorage.setItem(KEY, JSON.stringify(n)); } catch { /* 저장 불가 환경 */ }
}

// index 에 명판값을 덮어쓴 사본. spec.source 가 nameplate 로 바뀐다.
export function applyNameplates(index: FleetIndex, n: Nameplates): FleetIndex {
  if (!Object.keys(n).length) return index;
  return {
    ...index,
    motors: index.motors.map((m): MotorInfo => {
      const np = n[m.id];
      if (!np) return m;
      const spec: MotorSpec = { ...m.spec, ...np.values, source: "nameplate" };
      return { ...m, spec };
    }),
  };
}

// config/motors/<id>.yaml 에 붙여 넣을 조각 (바뀐 키만)
export function yamlSnippet(id: string, np: Nameplate): string {
  const lines = [`# ${id} 명판값 (${np.entered_at}) — config/motors/${id}.yaml 의 해당 키를 아래 값으로 바꾸고 source: nameplate 로`, "source: nameplate"];
  for (const [k, v] of Object.entries(np.values)) lines.push(`${k}: ${typeof v === "string" ? JSON.stringify(v) : v}`);
  return lines.join("\n");
}

export function parseField(key: keyof MotorSpec, raw: string): string | number | undefined {
  const s = raw.trim();
  if (!s) return undefined;
  const f = NAMEPLATE_FIELDS.find((x) => x.key === key);
  if (f?.step !== undefined) { const v = Number(s); return Number.isFinite(v) && v > 0 ? v : undefined; }
  return s;
}
