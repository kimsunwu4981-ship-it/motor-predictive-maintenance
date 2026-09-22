import { usePlayback } from "../state/playback";
import { ampere, idxAt, PHASES, type Basis, type ElecData, type Phase } from "./data";

// 페이저도 (TASK 5.1): 세 상 전류를 화살표 3개로. 길이 = 크기(정격 대비), 각도 = 기본파 위상(엔진 재계산, config 위상).
// 정상이면 균형 잡힌 별 모양, 단락·결상·불평형에서 일그러진다 — "균형"을 처음 보는 사람에게 가장 직관적으로 설명하는 도구.
// 점선 원 = 정격(100 %), 옅은 방사선 = 균형일 때의 120° 기준 방향. 화살표 색 = 영상과 같은 상태색.
export function PhasorPanel({ data, basis, focus, big, onToggleBig }: { data: ElecData; basis: Basis; focus: Phase[]; big?: boolean; onToggleBig?: () => void }) {
  const { t } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const S = 240, c = S / 2, rMax = c - 26;
  const scale = Math.max(1.6, ...PHASES.map((p) => Math.max(...ts.ratio[p]))) * 1.05;   // 로그 최대 비율(장면 3 의 2.01)까지 들어가게
  const rr = (ratio: number) => (ratio / scale) * rMax;
  const xy = (ratio: number, deg: number) => [c + rr(ratio) * Math.cos((deg * Math.PI) / 180), c - rr(ratio) * Math.sin((deg * Math.PI) / 180)];
  const refDeg = { A: ts.phasor_deg.A[0], B: ts.phasor_deg.B[0], C: ts.phasor_deg.C[0] };   // 로그 첫 행(정상) 방향을 기준선으로
  const gaps = PHASES.map((p, k) => { const q = PHASES[(k + 1) % 3]; return ((ts.phasor_deg[p][i] - ts.phasor_deg[q][i]) % 360 + 360) % 360; });
  const lens = PHASES.map((p) => ts.ratio[p][i]);
  const spread = Math.max(...lens) - Math.min(...lens);
  const angErr = Math.max(...gaps.map((g) => Math.abs(g - 120)));
  return (
    <div className={"panel phasor" + (big ? " big" : "")}>
      <div className="panel-h">페이저도 <span className="dim">길이 = 크기 · 각도 = 위상</span><span className="grow" />
        {onToggleBig && <button className="ph-big-btn" onClick={onToggleBig} title="P 키">{big ? "닫기 (P)" : "크게 (P)"}</button>}</div>
      <div className="panel-b">
        <svg viewBox={`0 0 ${S} ${S}`} className="ph-svg">
          <defs>{PHASES.map((p) => <marker key={p} id={`ph-${p}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill={el.status_colors[ts.current_status[p][i]]} /></marker>)}</defs>
          <circle cx={c} cy={c} r={rr(1)} className="ph-rated" />
          <text x={c + rr(1) + 3} y={c - 4} className="ph-lbl">정격 {ampere(data, 1, basis).toFixed(1)} A</text>
          {[el.ratio_thresholds.over_danger, el.ratio_thresholds.under_danger].map((r) => <circle key={r} cx={c} cy={c} r={rr(r)} className="ph-thr" />)}
          {PHASES.map((p) => { const [x, y] = xy(scale, refDeg[p]); return <line key={"r" + p} x1={c} y1={c} x2={x} y2={y} className="ph-ref" />; })}
          {PHASES.map((p) => {
            const r = ts.ratio[p][i], d = ts.phasor_deg[p][i], s = ts.current_status[p][i];
            const [x, y] = xy(r, d); const [lx, ly] = xy(Math.max(r, 0.35) + 0.22, d);
            const isF = !focus.length || focus.includes(p);
            return (
              <g key={p} className={"ph-arrow" + (isF ? " focus" : " dim")}>
                <line x1={c} y1={c} x2={x} y2={y} stroke={el.status_colors[s]} strokeWidth={isF ? 4 : 2.5} markerEnd={`url(#ph-${p})`} />
                <text x={lx} y={ly} className="ph-name" fill={el.status_colors[s]} textAnchor="middle" dominantBaseline="middle">{el.phase_labels[p]} {ampere(data, r, basis).toFixed(1)} A</text>
              </g>
            );
          })}
        </svg>
        <div className="ph-note">
          세 화살표의 길이와 간격이 같으면 균형, 일그러질수록 I₂/I₁ 이 커집니다.
          <div className="dim">길이 차 {Math.round(spread * 100)} %p · 간격 오차 최대 {angErr.toFixed(0)}° · {basis === "line" ? "선전류" : "상전류"} 기준</div>
        </div>
      </div>
    </div>
  );
}
