import { useEffect, useMemo, useRef, useState } from "react";
import { indexAt } from "../data";
import { usePlayback } from "../state/playback";
import { glowPx, hex, sample } from "./colormap";
import type { MechData } from "./data";

// ② 위치 안내 (TASK 5.3) — 모터 측단면도를 SVG 로 직접 그린다 (외부 이미지 없음).
// 부품 색은 영상과 같은 컬러맵(colors.yaml → thresholds.json thermal.colormap)으로 실시간 계산,
// 위험 단계 맥동도 영상과 같은 0.8 Hz. 주목 부품 화살표·이름표, 열 경로 화살표(narration.yaml heat_path),
// 장면 시작 시 주목 부품 강조. 마우스를 올리면 이름·온도·등급·허용 한계·근거.
//
// 배치(viewBox 0 0 440 210): 왼쪽 NDE(팬·브레이크) — 오른쪽 DE(축 출력). 좌표는 그림 목적일 뿐 실제 치수가 아니다.
interface Shape { key: string; kind: "rect" | "circle"; x: number; y: number; w: number; h: number; rx?: number; label: string; lx: number; ly: number }
const SHAPES: Shape[] = [
  { key: "frame", kind: "rect", x: 100, y: 38, w: 236, h: 134, rx: 10, label: "하우징", lx: 218, ly: 196 },
  { key: "endshield_nde", kind: "rect", x: 78, y: 46, w: 24, h: 118, rx: 5, label: "NDE 엔드실드", lx: 96, ly: 30 },
  { key: "endshield_de", kind: "rect", x: 334, y: 46, w: 24, h: 118, rx: 5, label: "DE 엔드실드", lx: 346, ly: 30 },
  { key: "stator_core", kind: "rect", x: 128, y: 54, w: 180, h: 24, label: "고정자 코어", lx: 218, ly: 50 },
  { key: "stator_core", kind: "rect", x: 128, y: 132, w: 180, h: 24, label: "", lx: 0, ly: 0 },
  { key: "winding", kind: "rect", x: 108, y: 56, w: 20, h: 20, rx: 6, label: "권선", lx: 158, ly: 30 },
  { key: "winding", kind: "rect", x: 308, y: 56, w: 20, h: 20, rx: 6, label: "", lx: 0, ly: 0 },
  { key: "winding", kind: "rect", x: 108, y: 134, w: 20, h: 20, rx: 6, label: "", lx: 0, ly: 0 },
  { key: "winding", kind: "rect", x: 308, y: 134, w: 20, h: 20, rx: 6, label: "", lx: 0, ly: 0 },
  { key: "rotor", kind: "rect", x: 128, y: 84, w: 180, h: 42, rx: 4, label: "로터", lx: 218, ly: 108 },
  { key: "shaft", kind: "rect", x: 36, y: 99, w: 396, h: 12, rx: 3, label: "축", lx: 400, ly: 92 },
  { key: "bearing_nde", kind: "circle", x: 90, y: 105, w: 26, h: 26, label: "NDE 베어링", lx: 90, ly: 184 },
  { key: "bearing_de", kind: "circle", x: 346, y: 105, w: 26, h: 26, label: "DE 베어링", lx: 346, ly: 184 },
];
// 열 노드가 아닌 부품 — 결함 상태만 표시한다
const FAN = { x: 46, y: 62, w: 26, h: 86 };
const BRAKE = { x: 12, y: 74, w: 22, h: 62 };
const CENTER: Record<string, [number, number]> = {
  frame: [218, 165], endshield_nde: [90, 105], endshield_de: [346, 105], stator_core: [218, 66], winding: [118, 66],
  rotor: [218, 105], shaft: [260, 105], bearing_nde: [90, 105], bearing_de: [346, 105],
};

export function MotorSchematic({ data, focus }: { data: MechData; focus: string }) {
  const { t, stepIndex } = usePlayback();
  const th = data.thresholds, ts = data.timeseries;
  const cm = th.thermal.colormap;
  const i = indexAt(ts, t);
  const parts = useMemo(() => Object.fromEntries(th.thermal.parts.map((p) => [p.key, p])), [th]);
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const [hover, setHover] = useState<string | null>(null);

  // 장면 시작 강조: 장면이 바뀌면 주목 부품을 2 초간 깜빡인다 (영상의 해당 부위와 동시)
  const [pulseKey, setPulseKey] = useState<string | null>(null);
  const prevStep = useRef(stepIndex);
  useEffect(() => {
    if (prevStep.current !== stepIndex) { prevStep.current = stepIndex; setPulseKey(focus); const h = setTimeout(() => setPulseKey(null), 2200); return () => clearTimeout(h); }
  }, [stepIndex, focus]);

  const fill = (key: string) => {
    const p = parts[key]; if (!p) return { color: "#777", glow: 0, glowColor: "#000", pulsing: false };
    const s = sample(cm, ts.temperature_C[key][i], key, p, ts.stage[key][i], t);
    return { color: hex(s.diffuse), glow: glowPx(s.intensity), glowColor: hex(s.emissive), pulsing: s.pulsing };
  };
  const faults = step.faults;
  const fanDead = faults.includes("fan_failure"), brakeDrag = faults.includes("brake_drag");
  const heatPath = scene?.heat_path ?? [];
  const info = hover ? parts[hover] : null;

  return (
    <div className="panel schem">
      <div className="panel-h"><span className="h-title">위치 안내 <span className="dim">모터 측단면도 · 색은 영상과 같은 컬러맵</span></span>
        <span className="grow" /><span className="dim">NDE ← → DE</span></div>
      <div className="schem-body">
        <svg viewBox="0 0 440 210" className="schem-svg" onMouseLeave={() => setHover(null)}>
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#ffaa33" /></marker>
            <marker id="arrf" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#66ddff" /></marker>
          </defs>
          {/* 팬 · 브레이크 (열 노드 아님) */}
          <g className={"nonthermal" + (fanDead ? " dead" : "")} onMouseEnter={() => setHover("fan")}>
            <rect x={FAN.x} y={FAN.y} width={FAN.w} height={FAN.h} rx={4} fill="#5c6670" stroke="#8a94a0" />
            {[0, 1, 2, 3].map((k) => <line key={k} x1={FAN.x + 3} y1={FAN.y + 10 + k * 22} x2={FAN.x + FAN.w - 3} y2={FAN.y + 18 + k * 22} stroke="#aeb8c4" strokeWidth={2} />)}
            {fanDead && <g stroke="#ff2e0a" strokeWidth={3}><line x1={FAN.x} y1={FAN.y} x2={FAN.x + FAN.w} y2={FAN.y + FAN.h} /><line x1={FAN.x + FAN.w} y1={FAN.y} x2={FAN.x} y2={FAN.y + FAN.h} /></g>}
            <text x={FAN.x + FAN.w / 2} y={196} className="lbl">냉각팬{fanDead ? " 정지" : ""}</text>
          </g>
          <g className="nonthermal" onMouseEnter={() => setHover("brake")}>
            <rect x={BRAKE.x} y={BRAKE.y} width={BRAKE.w} height={BRAKE.h} rx={3} fill={brakeDrag ? "#f27a1f" : "#5c6670"} stroke="#8a94a0"
                  style={brakeDrag ? { filter: "drop-shadow(0 0 6px #f27a1f)" } : undefined} />
            <text x={BRAKE.x + BRAKE.w / 2} y={30} className="lbl">브레이크{brakeDrag ? " 끌림" : ""}</text>
          </g>
          {/* 열 노드 부품 */}
          {SHAPES.map((s, n) => {
            const f = fill(s.key);
            const isFocus = s.key === focus;
            const style: React.CSSProperties = { filter: f.glow > 0.5 ? `drop-shadow(0 0 ${f.glow.toFixed(1)}px ${f.glowColor})` : undefined };
            const cls = "part" + (f.pulsing ? " pulsing" : "") + (isFocus ? " focus" : "") + (pulseKey === s.key ? " intro" : "") + (hover === s.key ? " hover" : "");
            return s.kind === "circle"
              ? <circle key={n} cx={s.x} cy={s.y} r={s.w / 2} fill={f.color} className={cls} style={style} onMouseEnter={() => setHover(s.key)} />
              : <rect key={n} x={s.x} y={s.y} width={s.w} height={s.h} rx={s.rx ?? 2} fill={f.color} className={cls} style={style} onMouseEnter={() => setHover(s.key)} />;
          })}
          {SHAPES.filter((s) => s.label).map((s) => <text key={s.key + "l"} x={s.lx} y={s.ly} className={"lbl" + (s.key === focus ? " focus" : "")}>{s.label}</text>)}
          {/* 열 경로 화살표 (config 열회로 연결 관계 기반, 장면별 heat_path) */}
          {heatPath.slice(1).map((k, n) => {
            const a = CENTER[heatPath[n]], b = CENTER[k]; if (!a || !b) return null;
            return <line key={"hp" + n} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className="heatpath" markerEnd="url(#arr)" />;
          })}
          {brakeDrag && <line x1={BRAKE.x + BRAKE.w} y1={105} x2={CENTER.shaft[0] - 60} y2={105} className="heatpath" markerEnd="url(#arr)" />}
          {/* 주목 부품 화살표 + 이름표 */}
          {CENTER[focus] && (() => {
            const [cx, cy] = CENTER[focus]; const up = cy > 100; const ty = up ? cy - 44 : cy + 44;
            return <g className="focus-arrow"><line x1={cx} y1={ty + (up ? 6 : -6)} x2={cx} y2={cy + (up ? -16 : 16)} markerEnd="url(#arrf)" />
              <text x={cx} y={ty} className="focus-lbl">▶ {parts[focus]?.label} {ts.temperature_C[focus][i].toFixed(0)} °C</text></g>;
          })()}
        </svg>
        <div className="schem-info">
          {info ? (
            <>
              <b>{info.label}</b> · {ts.temperature_C[info.key][i].toFixed(1)} °C · <span style={{ color: th.thermal.stage_colors[ts.stage[info.key][i]] }}>{th.thermal.stage_labels[ts.stage[info.key][i]]}</span>
              <div className="dim">허용 {info.normal_max_C} / {info.caution_max_C} / {info.warning_max_C} °C{info.note ? ` · ${info.note}` : ""} · 손실 {Math.round(ts.loss_W[info.key][i])} W</div>
            </>
          ) : hover === "fan" ? <><b>냉각팬</b> · 열 노드 아님 · {fanDead ? "정지 — 방열 저항 증가" : "정상 회전"}</>
            : hover === "brake" ? <><b>브레이크</b> · 열 노드 아님 · {brakeDrag ? "끌림 — 마찰열이 축으로 유입" : "정상 해제"}</>
            : <span className="dim">부품에 마우스를 올리면 온도·등급·허용 한계가 나옵니다</span>}
        </div>
      </div>
    </div>
  );
}
