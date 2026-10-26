import { useEffect, useState } from "react";
import { getJson } from "../../live/load";
import { glowPx, hex, sample, type ThermalColormap } from "../../mech/colormap";
import type { PartThreshold, Stage } from "../../data";
import type { FleetIndex, MotorSeries } from "../data";

// ① 모터 열·결함 지도 (단순 보기 §1b): 측단면 SVG — 부품 색 = 열 모델 노드 온도를 영상과 같은 컬러맵(thresholds.json thermal.colormap, colors.yaml)으로.
// 열 모델이 안 도는 모드(전기)는 회색 + "온도 미계산". 단락 코일(Coil_01)은 손실(P_loop)에 비례한 발광 점. 기계 모드 결함 베어링은 경고 이상이면 맥동.
// 좌표는 그림 목적(mech/MotorSchematic 과 같은 배치: 왼쪽 NDE, 오른쪽 DE) — 실제 치수가 아니다. 열화상 카메라가 아니라 열 모델 추정값이다(툴팁).
interface ThermalDoc { thermal: { parts: PartThreshold[]; colormap: ThermalColormap } }
let cache: Promise<ThermalDoc | null> | null = null;
export function useThermalDoc(): ThermalDoc | null {
  const [d, setD] = useState<ThermalDoc | null>(null);
  useEffect(() => { if (!cache) cache = getJson<ThermalDoc>("data/mechanical/thresholds.json").catch(() => null); cache.then(setD); }, []);
  return d;
}
interface Shape { key: string; kind: "rect" | "circle"; x: number; y: number; w: number; h: number; rx?: number }
const SHAPES: Shape[] = [
  { key: "frame", kind: "rect", x: 100, y: 38, w: 236, h: 134, rx: 10 },
  { key: "endshield_nde", kind: "rect", x: 78, y: 46, w: 24, h: 118, rx: 5 },
  { key: "endshield_de", kind: "rect", x: 334, y: 46, w: 24, h: 118, rx: 5 },
  { key: "stator_core", kind: "rect", x: 128, y: 54, w: 180, h: 24 },
  { key: "stator_core", kind: "rect", x: 128, y: 132, w: 180, h: 24 },
  { key: "winding", kind: "rect", x: 108, y: 56, w: 20, h: 20, rx: 6 },
  { key: "winding", kind: "rect", x: 308, y: 56, w: 20, h: 20, rx: 6 },
  { key: "winding", kind: "rect", x: 108, y: 134, w: 20, h: 20, rx: 6 },
  { key: "winding", kind: "rect", x: 308, y: 134, w: 20, h: 20, rx: 6 },
  { key: "rotor", kind: "rect", x: 128, y: 84, w: 180, h: 42, rx: 4 },
  { key: "shaft", kind: "rect", x: 36, y: 99, w: 396, h: 12, rx: 3 },
  { key: "bearing_nde", kind: "circle", x: 90, y: 105, w: 26, h: 26 },
  { key: "bearing_de", kind: "circle", x: 346, y: 105, w: 26, h: 26 },
];
const SLOT_N = 36;   // 고정자 슬롯 수 — 코어 띠 위에 코일 자리 표시 (그림)
const NEUTRAL: [number, number, number] = [0.42, 0.46, 0.52];   // 정상(램프 위치 0)일 때의 바탕색 — 재질색이 주황(구리)이라 경고색과 헷갈리지 않게

export function stageOf(tC: number, p: PartThreshold): Stage {
  return tC <= p.normal_max_C ? "normal" : tC <= p.caution_max_C ? "caution" : tC <= p.warning_max_C ? "warning" : "danger";
}

export function MotorMap({ index, s, i, thermalOn, t, pLoopW, pLoopMaxW, faultBearing, labelNoTemp }: {
  index: FleetIndex; s: MotorSeries; i: number; thermalOn: boolean; t: number;
  pLoopW: number; pLoopMaxW: number;        // 단락 루프 손실 (지금 / 시리즈 최대) → 발광 점 크기
  faultBearing: string | null;              // 기계 모드: 결함 베어링 키 (경고 이상이면 맥동)
  labelNoTemp: string;
}) {
  const doc = useThermalDoc();
  const parts = Object.fromEntries((doc?.thermal.parts ?? []).map((p) => [p.key, p]));
  const cm = doc?.thermal.colormap;
  const fill = (key: string) => {
    const p = parts[key];
    if (!cm || !p || !thermalOn) return { color: "#4a5058", glow: 0, glowColor: "#000", stage: "normal" as Stage, tC: s.temperature_C[key]?.[i] ?? NaN };
    const tC = s.temperature_C[key]?.[i] ?? NaN;
    const st = stageOf(tC, p);
    const sm = sample(cm, tC, key, p, st, t, NEUTRAL);        // 재질색(구리·강) 대신 중립 회색 — 색은 온도 램프만
    return { color: hex(sm.diffuse), glow: glowPx(sm.intensity), glowColor: hex(sm.emissive), stage: st, tC };
  };
  const glowR = pLoopW > 0 ? 4 + 10 * Math.min(1, pLoopW / Math.max(pLoopMaxW, 1e-6)) : 0;
  const danger = index.colors.DANGER;
  return (
    <svg className="mm-svg" viewBox="0 0 440 210" role="img" aria-label="모터 열·결함 지도">
      {SHAPES.map((sh, n) => {
        const f = fill(sh.key);
        const pulsing = faultBearing === sh.key && thermalOn && (f.stage === "warning" || f.stage === "danger");
        const tip = `${index.node_labels[sh.key] ?? sh.key}${thermalOn && Number.isFinite(f.tC) ? ` ${f.tC.toFixed(1)} °C (열 모델 추정)` : " — 온도 미계산"}`;
        const style = { fill: f.color, filter: f.glow > 0 ? `drop-shadow(0 0 ${f.glow}px ${f.glowColor})` : undefined };
        return sh.kind === "circle"
          ? <circle key={n} className={"mm-part" + (pulsing ? " pulsing" : "")} cx={sh.x} cy={sh.y} r={sh.w / 2} style={style}><title>{tip}</title></circle>
          : <rect key={n} className={"mm-part" + (pulsing ? " pulsing" : "")} x={sh.x} y={sh.y} width={sh.w} height={sh.h} rx={sh.rx ?? 0} style={style}><title>{tip}</title></rect>;
      })}
      {/* 고정자 슬롯 자리 (코어 띠 위·아래 36 코일 중 보이는 쪽) */}
      {Array.from({ length: SLOT_N / 2 }, (_, k) => <rect key={"s" + k} className="mm-slot" x={132 + k * 9.8} y={78} width={4} height={6} />)}
      {Array.from({ length: SLOT_N / 2 }, (_, k) => <rect key={"t" + k} className="mm-slot" x={132 + k * 9.8} y={126} width={4} height={6} />)}
      {/* 단락 코일 발광 점 (Coil_01, DE 쪽 상단 코일 엔드) */}
      {glowR > 0 && <circle className="mm-short" cx={318} cy={66} r={glowR} style={{ fill: danger, filter: `drop-shadow(0 0 ${Math.round(glowR * 1.2)}px ${danger})` }}><title>{`단락 코일 손실 ${pLoopW.toFixed(0)} W (LUT)`}</title></circle>}
      <text className="mm-lbl" x={90} y={190}>NDE</text><text className="mm-lbl" x={346} y={190}>DE</text>
      {!thermalOn && <text className="mm-note" x={218} y={200}>{labelNoTemp}</text>}
    </svg>
  );
}
