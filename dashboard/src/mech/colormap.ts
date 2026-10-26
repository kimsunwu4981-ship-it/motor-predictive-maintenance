// colormap.ts — motor_dt_viz/viz/colormap.py 의 ThermalColormap 을 그대로 옮긴 것.
// 영상 속 부품 색과 단면도 색이 같아야 하므로(TASK 5.3) 계산 규칙을 바꾸지 않는다.
//   1) 온도를 부품별 임계값(normal/caution/warning)으로 0~1 위치로 정규화
//   2) colors.yaml 의 stops 를 선형 보간
//   3) 원래 재질색과 열색을 blend 비율로 섞는다 (정상이면 원래 색 그대로)
//   4) 경고 단계부터 발광 강도가 0.8 Hz 로 맥동
import type { PartThreshold, Stage } from "../data";

export type RGB = [number, number, number];
export interface ThermalColormap {
  stops: { pos: number; color: RGB; blend: number; emissive: RGB; intensity: number }[];
  normalize: { normal_pos: number; caution_pos: number; warning_pos: number; danger_span_C: number };
  pulse: { enabled: boolean; start_stage: Stage; hz: number; depth: number };
  base_materials: Record<string, RGB>;
}
const STAGE_ORDER: Stage[] = ["normal", "caution", "warning", "danger"];

export function position(cm: ThermalColormap, tC: number, th: PartThreshold): number {
  const n = th.normal_max_C, c = th.caution_max_C, w = th.warning_max_C;
  const pc = cm.normalize.caution_pos, pw = cm.normalize.warning_pos, span = cm.normalize.danger_span_C;
  if (tC <= n) return 0;
  if (tC <= c) return pc * (tC - n) / Math.max(c - n, 1e-6);
  if (tC <= w) return pc + (pw - pc) * (tC - c) / Math.max(w - c, 1e-6);
  return Math.min(1, pw + (1 - pw) * (tC - w) / span);
}
function interp(cm: ThermalColormap, pos: number) {
  const st = cm.stops;
  if (pos <= st[0].pos) return st[0];
  if (pos >= st[st.length - 1].pos) return st[st.length - 1];
  for (let i = 1; i < st.length; i++) {
    if (pos <= st[i].pos) {
      const a = st[i - 1], b = st[i], f = (pos - a.pos) / Math.max(b.pos - a.pos, 1e-6);
      const mix = (x: number, y: number) => x + (y - x) * f;
      return { pos, color: [mix(a.color[0], b.color[0]), mix(a.color[1], b.color[1]), mix(a.color[2], b.color[2])] as RGB,
               blend: mix(a.blend, b.blend), emissive: [mix(a.emissive[0], b.emissive[0]), mix(a.emissive[1], b.emissive[1]), mix(a.emissive[2], b.emissive[2])] as RGB,
               intensity: mix(a.intensity, b.intensity) };
    }
  }
  return st[st.length - 1];
}
// colors.yaml 의 base_materials 는 3D 모델 prim 이름을 쓴다. 열 노드 키와 다른 것은 별칭으로 잇고,
// 3D 모델에 보이지 않아 영상 색이 없는 부품(권선·고정자 코어)은 구리·규소강 대체색을 쓴다.
const ALIAS: Record<string, string> = { frame: "housing_frame" };
const FALLBACK: Record<string, RGB> = { winding: [0.72, 0.42, 0.18], stator_core: [0.42, 0.45, 0.50] };
export function baseColor(cm: ThermalColormap, partKey: string): RGB {
  return cm.base_materials[partKey] ?? cm.base_materials[ALIAS[partKey] ?? ""] ?? FALLBACK[partKey] ?? [0.5, 0.5, 0.5];
}
export interface Sample { diffuse: RGB; emissive: RGB; intensity: number; pos: number; pulsing: boolean }
export function sample(cm: ThermalColormap, tC: number, partKey: string, th: PartThreshold, stage: Stage, timeS: number, baseOverride?: RGB): Sample {
  const pos = position(cm, tC, th);
  const s = interp(cm, pos);
  const base = baseOverride ?? baseColor(cm, partKey);     // baseOverride: 상태 보드 단순 보기 — 재질색 대신 중립 회색(색은 상태 셋만 의미)
  const b = s.blend;
  const diffuse: RGB = [0, 1, 2].map((i) => base[i] * (1 - b) + s.color[i] * b) as RGB;
  const pulsing = cm.pulse.enabled && STAGE_ORDER.indexOf(stage) >= STAGE_ORDER.indexOf(cm.pulse.start_stage);
  let intensity = s.intensity;
  if (pulsing) intensity *= 1 + cm.pulse.depth * Math.sin(2 * Math.PI * cm.pulse.hz * timeS);
  return { diffuse, emissive: s.emissive, intensity: Math.max(intensity, 0), pos, pulsing };
}
export function hex(rgb: RGB): string {
  return "#" + rgb.map((c) => Math.max(0, Math.min(255, Math.round(c * 255))).toString(16).padStart(2, "0")).join("");
}
// 발광은 화면(SVG)에서 drop-shadow 로 흉내 낸다. 강도 0~8 → 그림자 반경 0~14 px
export function glowPx(intensity: number): number {
  return Math.min(14, intensity * 1.75);
}
