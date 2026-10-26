import type { Phase } from "../data";

// ② 3상 전류 파형 (단순 보기 §1b): 엔진이 합성한 최근 2주기(2 kHz) — export case_signals[case].waveform. 결함상 선 굵게, 정격 진폭(√2·I_n) 점선.
// 글자: 상 이름 세 글자 + "정격" 뿐. 축 눈금 없음(툴팁에 수치).
export interface Waveform { fs_Hz: number; f0_Hz: number; cycles: number; unit: string; t_ms: number[]; A: number[]; B: number[]; C: number[] }
const PH: Phase[] = ["A", "B", "C"];

export function WaveTile({ wf, ratedA, faultPhase, phaseLabels, rmsA }: {
  wf: Waveform; ratedA: number; faultPhase: Phase | null; phaseLabels: Record<Phase, string>; rmsA: Record<Phase, number>;
}) {
  const W = 400, H = 170, L = 26, R = 8, T = 10, B = 14;
  const peak = Math.SQRT2 * ratedA;
  const vmax = Math.max(peak * 1.25, ...PH.flatMap((p) => wf[p].map((v) => Math.abs(v))));
  const n = wf.t_ms.length;
  const x = (k: number) => L + ((W - L - R) * k) / Math.max(n - 1, 1);
  const y = (v: number) => T + ((H - T - B) * (1 - v / vmax)) / 2;
  const path = (a: number[]) => a.map((v, k) => `${k ? "L" : "M"}${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg className="wv-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="3상 전류 파형">
      <line className="wv-zero" x1={L} x2={W - R} y1={y(0)} y2={y(0)} />
      <line className="wv-rated" x1={L} x2={W - R} y1={y(peak)} y2={y(peak)}><title>{`정격 진폭 √2 × ${ratedA} A`}</title></line>
      <line className="wv-rated" x1={L} x2={W - R} y1={y(-peak)} y2={y(-peak)} />
      <text className="wv-lbl" x={W - R} y={y(peak) - 3} textAnchor="end">정격</text>
      {PH.map((p) => (
        <path key={p} className={"wv-line" + (faultPhase === p ? " fault" : "")} d={path(wf[p])}><title>{`${phaseLabels[p]}상 ${rmsA[p].toFixed(2)} A RMS`}</title></path>
      ))}
      {PH.map((p, k) => <text key={"l" + p} className={"wv-ph" + (faultPhase === p ? " fault" : "")} x={4} y={y(0) - 24 + k * 16}>{phaseLabels[p]}</text>)}
    </svg>
  );
}
