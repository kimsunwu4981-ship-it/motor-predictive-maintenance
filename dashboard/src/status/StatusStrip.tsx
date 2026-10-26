import { useMemo } from "react";
import type { FleetIndex, Level, MotorSeries } from "./data";

// 재생 바 배경: 시각별 판정 상태 색 (구간 병합). 상태 보드 전문가 보기와 단순 보기가 같이 쓴다.
export function StatusStrip({ index, s, total, from = 0 }: { index: FleetIndex; s: MotorSeries; total: number; from?: number }) {
  const segs = useMemo(() => {
    const out: { from: number; to: number; lv: Level }[] = [];
    for (let k = 0; k < s.t.length; k++) {
      const lv = s.status[k];
      const last = out[out.length - 1];
      if (last && last.lv === lv) last.to = s.t[k]; else out.push({ from: s.t[k], to: s.t[k], lv });
    }
    return out;
  }, [s]);
  return <>{segs.map((g, n) => <i key={n} className="st-seg" style={{ left: `${((g.from - from) / (total - from)) * 100}%`, width: `${Math.max(0.2, ((g.to - g.from) / (total - from)) * 100)}%`, background: index.colors[g.lv] }} />)}</>;
}
