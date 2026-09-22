import { useEffect, useRef, useState } from "react";
import { usePlayback } from "../state/playback";
import { idxAt, PHASES, type ElecData, type Phase } from "./data";

// ② 회로 안내 (TASK 5.3): 3상 회로도를 SVG 로 직접 그린다 — 공급 전원 → 케이블 A·B·C → 단자함 → Δ결선 권선 → 모터.
// 각 상의 선이 영상과 같은 상태색으로 칠해지고 입자가 흐른다. 입자는 교류이므로 앞뒤로 진동한다:
//   위치 = 진폭(∝ 정격 대비 전류) × sin(2π·f_slow·t + 위상),  f_slow = 60 Hz / 슬로모션 60 = 1 Hz (영상과 같은 속도).
// 케이블 구간은 선전류, 권선 삼각형 안은 상전류 — Δ결선의 두 값이 어디에 해당하는지 보이게 한다.
// 장면별: 단락 루프(A상 권선, 시각적 표시), 끊어진 상(A상 케이블 스위치), 전압 불평형(전원 쪽 정성 표기).
// 장면 시작 시 주목 상을 2 초 강조 (영상의 해당 부위와 동시).

// 좌표 (viewBox 0 0 460 250): 전원(왼쪽) — 케이블 — 단자함(x≈250) — Δ권선(삼각형) — 모터 외곽(오른쪽)
const Y: Record<Phase, number> = { A: 60, B: 110, C: 160 };
const SRC_X = 40, TB_X = 236, TB_W = 26;
const TRI = { A: [318, 52] as const, B: [372, 142] as const, C: [264, 142] as const };   // 삼각형 꼭짓점 = 단자 A, B, C
// 권선 변: AB(A→B 사이 코일), BC, CA. Δ결선에서 상전류는 변에 흐른다. 케이블 상 → 꼭짓점 이름 대응.
const SIDES: { key: Phase; from: Phase; to: Phase }[] = [{ key: "A", from: "A", to: "B" }, { key: "B", from: "B", to: "C" }, { key: "C", from: "C", to: "A" }];

export function CircuitSchematic({ data, focus }: { data: ElecData; focus: Phase[] }) {
  const { t, stepIndex, playing } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const circ = scene?.circuit ?? {};
  const [hover, setHover] = useState<Phase | null>(null);

  // 장면 시작 강조
  const [pulse, setPulse] = useState(false);
  const prev = useRef(stepIndex);
  useEffect(() => { if (prev.current !== stepIndex) { prev.current = stepIndex; setPulse(true); const h = setTimeout(() => setPulse(false), 2200); return () => clearTimeout(h); } }, [stepIndex]);

  // 입자 애니메이션: rAF 로 stroke-dashoffset 을 흔든다 (재생 중에만; 정지하면 입자도 멈춘다)
  const refs = useRef<Record<string, SVGPathElement | null>>({});
  const ratioRef = useRef<Record<Phase, number>>({ A: 0, B: 0, C: 0 });
  const degRef = useRef<Record<Phase, number>>({ A: 0, B: 0, C: 0 });
  ratioRef.current = { A: ts.ratio.A[i], B: ts.ratio.B[i], C: ts.ratio.C[i] };
  degRef.current = { A: ts.phasor_deg.A[i], B: ts.phasor_deg.B[i], C: ts.phasor_deg.C[i] };
  const playingRef = useRef(playing); playingRef.current = playing;
  const fSlow = data.thresholds.motor.frequency_Hz / el.slowmo_x;
  useEffect(() => {
    let raf = 0; const t0 = performance.now(); let paused = 0, pauseAt = 0;
    const tick = (now: number) => {
      if (!playingRef.current) { if (!pauseAt) pauseAt = now; raf = requestAnimationFrame(tick); return; }
      if (pauseAt) { paused += now - pauseAt; pauseAt = 0; }
      const tt = (now - t0 - paused) / 1000;
      for (const p of PHASES) {
        const amp = 26 * ratioRef.current[p];
        const off = amp * Math.sin(2 * Math.PI * fSlow * tt + (degRef.current[p] * Math.PI) / 180);
        const cable = refs.current["c" + p], wind = refs.current["w" + p];
        if (cable) cable.style.strokeDashoffset = `${off}`;
        if (wind) wind.style.strokeDashoffset = `${-off}`;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [fSlow]);

  const col = (p: Phase) => el.status_colors[ts.current_status[p][i]];
  const isF = (p: Phase) => !focus.length || focus.includes(p);
  const cablePath = (p: Phase) => circ.open_phase === p
    ? `M${SRC_X},${Y[p]} H${TB_X - 70}`   // 끊어진 상: 스위치 앞까지만 (뒤쪽은 회색 선)
    : `M${SRC_X},${Y[p]} H${TB_X}`;
  const sidePath = (s: typeof SIDES[number]) => { const a = TRI[s.from], b = TRI[s.to]; return `M${a[0]},${a[1]} L${b[0]},${b[1]}`; };
  const info = hover ? { p: hover, line: ts.current_rms_A[hover][i], ph: ts.phase_rms_A[hover][i], st: el.status_labels[ts.current_status[hover][i]], pct: Math.round(ts.ratio[hover][i] * 100) } : null;

  return (
    <div className="panel circuit">
      <div className="panel-h">회로 안내 <span className="dim">전원 → 케이블 → Δ권선 · 색은 영상과 같은 상태색</span>
        <span className="grow" /><span className="dim">주목 {focus.length ? focus.map((p) => el.phase_labels[p]).join("·") + "상" : "균형 지표"}</span></div>
      <div className="circ-body">
        <svg viewBox="0 0 460 250" className="circ-svg" onMouseLeave={() => setHover(null)}>
          {/* 전원 */}
          <g className="src">
            <rect x={6} y={40} width={30} height={140} rx={6} />
            <text x={21} y={30} className="lbl">전원 3상</text>
            {PHASES.map((p) => <text key={p} x={21} y={Y[p] + 4} className="lbl phase" fill={`rgb(${el.phase_colors[p].map((c) => Math.round(c * 255)).join(",")})`}>{el.phase_labels[p]}</text>)}
            {circ.voltage_note && <text x={21} y={196} className="lbl note">{circ.voltage_note.split(" (")[0]}</text>}
            {circ.voltage_note && <text x={21} y={208} className="lbl note dim">(원인 · 모델 입력 아님)</text>}
          </g>
          {/* 케이블 (선전류) */}
          {PHASES.map((p) => (
            <g key={p} className={"cable" + (isF(p) ? " focus" : " dim") + (pulse && isF(p) ? " intro" : "")} onMouseEnter={() => setHover(p)}>
              <path d={`M${SRC_X},${Y[p]} H${TB_X}`} className="wire-base" />
              <path d={cablePath(p)} className="wire" stroke={col(p)} />
              <path d={cablePath(p)} className="dots" stroke={col(p)} ref={(e) => { refs.current["c" + p] = e; }} />
              {circ.open_phase === p && (
                <g className="open"><line x1={TB_X - 70} y1={Y[p]} x2={TB_X - 40} y2={Y[p] - 16} /><circle cx={TB_X - 70} cy={Y[p]} r={3} /><circle cx={TB_X - 36} cy={Y[p]} r={3} />
                  <text x={TB_X - 54} y={Y[p] + 18} className="lbl warn">끊김</text></g>
              )}
              <text x={140} y={Y[p] - 7} className="lbl cur" fill={col(p)}>{el.phase_labels[p]}상 {ts.current_rms_A[p][i].toFixed(1)} A</text>
            </g>
          ))}
          {/* 단자함 */}
          <rect x={TB_X} y={44} width={TB_W} height={132} rx={4} className="tbox" />
          <text x={TB_X + TB_W / 2} y={190} className="lbl">단자함</text>
          {PHASES.map((p) => <line key={"t" + p} x1={TB_X + TB_W} y1={Y[p]} x2={TRI[p][0]} y2={TRI[p][1]} className="tie" stroke={col(p)} />)}
          {/* 모터 외곽 + Δ권선 (상전류) */}
          <rect x={248} y={30} width={150} height={130} rx={14} className="motor" />
          <text x={323} y={176} className="lbl">모터 · Δ결선 권선</text>
          {SIDES.map((s) => (
            <g key={s.key} className={"wind" + (isF(s.key) ? " focus" : " dim") + (pulse && isF(s.key) ? " intro" : "")} onMouseEnter={() => setHover(s.key)}>
              <path d={sidePath(s)} className="wire-base" />
              <path d={sidePath(s)} className="wire coil" stroke={col(s.key)} />
              <path d={sidePath(s)} className="dots" stroke={col(s.key)} ref={(e) => { refs.current["w" + s.key] = e; }} />
            </g>
          ))}
          {PHASES.map((p) => <g key={"v" + p}><circle cx={TRI[p][0]} cy={TRI[p][1]} r={4} className="node" /><text x={TRI[p][0] + (p === "C" ? -10 : p === "B" ? 10 : 0)} y={TRI[p][1] + (p === "A" ? -9 : 14)} className="lbl">{el.phase_labels[p]}</text></g>)}
          <text x={318} y={128} className="lbl small mid">권선 {ts.phase_rms_A.A[i].toFixed(1)} / {ts.phase_rms_A.B[i].toFixed(1)} / {ts.phase_rms_A.C[i].toFixed(1)} A</text>
          {/* 단락 루프 (시각적 표시) */}
          {circ.short_loop && (() => { const s = SIDES.find((x) => x.key === circ.short_loop)!; const a = TRI[s.from], b = TRI[s.to]; const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
            return <g className="short"><ellipse cx={mx} cy={my} rx={16} ry={9} style={{ animationDuration: `${1 / el.short_loop.pulse_hz}s` }} /><text x={mx + 30} y={my - 16} className="lbl warn" textAnchor="middle">단락 루프 · 시각적 표시</text></g>; })()}
          {/* 범례 */}
          <text x={40} y={236} className="lbl small">케이블 = 선전류(정격 {el.rated_line_A} A) · 권선 = 상전류(정격 {el.rated_phase_A} A) · 입자는 {el.slowmo_x}배 느린 교류</text>
        </svg>
        <div className="circ-info">
          {info ? <><b>{el.phase_labels[info.p]}상</b> · 케이블 {info.line.toFixed(1)} A → 권선 {info.ph.toFixed(1)} A · 정격의 {info.pct} % · <span style={{ color: col(info.p) }}>{info.st}</span></>
            : <span className="dim">{el.model_note}</span>}
        </div>
      </div>
    </div>
  );
}
