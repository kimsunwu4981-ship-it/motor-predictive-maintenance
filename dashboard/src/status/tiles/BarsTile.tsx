import type { Level } from "../data";

// ③ 막대 타일 (단순 보기 §1b): 전기 = 대칭 성분 I₁·I₂·I₀ (정격 대비), 기계 = 진동 RMS / 베어링 충격성·고주파. 막대 옆 작은 선 = 임계 눈금(최대 2개).
// 글자: 막대 이름(2~4자)과 눈금 값만. 색은 상태 셋만.
export interface Bar { key: string; label: string; value: number; max: number; level: Level | null; ticks?: { at: number; label: string }[]; tip?: string }

export function BarsTile({ bars, colors, fg }: { bars: Bar[]; colors: Record<Level, string>; fg: string }) {
  const W = 400, H = 170, T = 14, B = 22, gap = 22;
  const bw = Math.min(70, (W - gap * (bars.length + 1)) / bars.length);
  const y = (v: number, max: number) => T + (H - T - B) * (1 - Math.max(0, Math.min(1, v / max)));
  return (
    <svg className="br-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="막대">
      <line className="br-base" x1={gap / 2} x2={W - gap / 2} y1={H - B} y2={H - B} />
      {bars.map((b, k) => {
        const x0 = gap + k * (bw + gap) + (W - gap - bars.length * (bw + gap)) / 2;
        const top = Math.min(y(b.value, b.max), H - B - 2);          // 아주 작은 값도 2 px 는 보이게
        const col = b.level ? colors[b.level] : fg;
        return (
          <g key={b.key}>
            <rect className="br-bar" x={x0} y={top} width={bw} height={H - B - top} style={{ fill: col, opacity: b.level ? 0.85 : 0.5 }}><title>{b.tip ?? `${b.label} ${b.value}`}</title></rect>
            {(b.ticks ?? []).map((tk, n) => (n % 2 === 0 ? (          // 눈금이 가까우면 겹치므로 좌·우 교대로
              <g key={tk.label}>
                <line className="br-tick" x1={x0 - 14} x2={x0 - 3} y1={y(tk.at, b.max)} y2={y(tk.at, b.max)} />
                <text className="br-tick-l" x={x0 - 17} y={y(tk.at, b.max) + 3} textAnchor="end">{tk.label}</text>
              </g>
            ) : (
              <g key={tk.label}>
                <line className="br-tick" x1={x0 + bw + 3} x2={x0 + bw + 14} y1={y(tk.at, b.max)} y2={y(tk.at, b.max)} />
                <text className="br-tick-l" x={x0 + bw + 17} y={y(tk.at, b.max) + 3}>{tk.label}</text>
              </g>
            )))}
            <text className="br-lbl" x={x0 + bw / 2} y={H - B + 15} textAnchor="middle">{b.label}</text>
          </g>
        );
      })}
    </svg>
  );
}
