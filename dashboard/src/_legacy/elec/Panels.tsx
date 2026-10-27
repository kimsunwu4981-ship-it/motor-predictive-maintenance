import { useMemo } from "react";
import { usePlayback } from "../../state/playback";
import { fill } from "../../live/types";
import { idxAt, PHASES, type ElecData } from "./data";

// ④ 원인 패널 + 결함 판별 매트릭스 (TASK 5.5). 숫자는 전부 로그·config 값이다.
//
// 매트릭스: 가로 = 균형(I₂/I₁), 세로 = 크기(세 상 중 가장 큰 정격 대비 비율). 7장면의 장면 종료 좌표(export matrix)를 점으로 찍고
// 현재 장면 점을 강조하며, 재생 시각의 실시간 점(◉)이 판 위를 움직인다. 가로축은 √ 눈금 — 0.006(정상)과 0.479(결상)를 한 판에 담기 위해.
// 세로 띠 = config 전류 구간(저전류 위험/주의·정상·과전류 주의/위험). "크기와 균형을 함께 보면 구분된다"가 이 판의 메시지다.
export function CauseElec({ data }: { data: ElecData }) {
  const { t, stepIndex, gotoStep } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical, eth = el.ratio_thresholds;
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = data.values[step.id];
  const cc = scene?.cause_chain;
  const i = idxAt(ts, t);
  const pts = el.matrix;
  const xMax = useMemo(() => Math.max(0.5, ...pts.map((p) => p.x_i2i1)) * 1.05, [pts]);
  const yMax = useMemo(() => Math.max(1.6, ...pts.map((p) => p.y_ratio_max)) * 1.08, [pts]);
  const W = 420, H = 190, L = 40, R = 10, T = 12, B = 30;
  const X = (x: number) => L + Math.sqrt(Math.max(0, x) / xMax) * (W - L - R);
  const Yc = (y: number) => T + (1 - Math.min(y, yMax) / yMax) * (H - T - B);
  const liveX = ts.i2_over_i1[i], liveY = Math.max(...PHASES.map((p) => ts.ratio[p][i]));
  const bands = [
    { lo: 0, hi: eth.under_danger, s: "under_danger" as const }, { lo: eth.under_danger, hi: eth.under_caution, s: "under_caution" as const },
    { lo: eth.under_caution, hi: eth.over_caution, s: "normal" as const }, { lo: eth.over_caution, hi: eth.over_danger, s: "over_caution" as const },
    { lo: eth.over_danger, hi: yMax, s: "over_danger" as const },
  ];
  const rgba = (s: keyof typeof el.status_rgb, a: number) => `rgba(${el.status_rgb[s].map((c) => Math.round(c * 255)).join(",")},${a})`;
  const xTicks = el.i2i1_marks.map((m) => m.value).concat([0.5]).filter((x) => x <= xMax);
  return (
    <div className="panel cause elec-cause">
      <div className="panel-h">원인 → 메커니즘 → 결과 → 조치 <span className="grow" /><span className="dim">지문: {scene?.fingerprint}</span></div>
      <div className="panel-b">
        {cc ? (
          <div className="chain fade" key={step.id}>
            {(["cause", "mechanism", "effect", "action"] as const).map((k, n) => (
              <div key={k} className={"chain-card c" + n}>
                <div className="chain-k">{["원인", "메커니즘", "결과", "조치"][n]}</div>
                <div>{fill(cc[k], v)}</div>
              </div>
            ))}
          </div>
        ) : <div className="muted">narration.yaml 의 cause_chain 없음</div>}
        <div className="sub-h" style={{ marginTop: 6 }}>결함 판별 매트릭스 <span className="dim">세로 = 크기(가장 큰 상, 정격 대비) · 가로 = 균형(I₂/I₁, √ 눈금) · 점 = 장면 끝 값, ◉ = 지금</span></div>
        <svg viewBox={`0 0 ${W} ${H}`} className="matrix">
          {bands.map((b) => <rect key={b.s} x={L} y={Yc(b.hi)} width={W - L - R} height={Yc(b.lo) - Yc(b.hi)} fill={rgba(b.s, 0.13)} />)}
          {bands.map((b) => <text key={"l" + b.s} x={L + 3} y={Yc(b.hi) + 9} className="m-band">{el.status_labels[b.s].replace("(결상 의심)", "")}</text>)}
          <line x1={L} y1={Yc(1)} x2={W - R} y2={Yc(1)} className="m-rated" />
          {xTicks.map((x) => <g key={x}><line x1={X(x)} y1={T} x2={X(x)} y2={H - B} className="m-grid" /><text x={X(x)} y={H - B + 11} className="m-tick" textAnchor="middle">{x}</text></g>)}
          <text x={W - R} y={H - 3} className="m-axis" textAnchor="end">균형 I₂/I₁ →</text>
          <text x={4} y={T + 8} className="m-axis">크기 ↑</text>
          {[0.5, 1, 1.5, 2].filter((y) => y <= yMax).map((y) => <text key={y} x={L - 3} y={Yc(y) + 3} className="m-tick" textAnchor="end">{Math.round(y * 100)}%</text>)}
          {/* 장면 점 + 영역 이름 */}
          {pts.map((p, n) => {
            const cur = n === stepIndex;
            const dx = p.label === "정상" ? 8 : p.label === "무부하" ? 8 : p.label.startsWith("단락") ? 8 : p.label === "과부하" ? 8 : p.label === "결상" ? -8 : 8;
            return (
              <g key={p.id} className={"m-pt" + (cur ? " cur" : "")} onClick={() => gotoStep(p.scene)}>
                <circle cx={X(p.x_i2i1)} cy={Yc(p.y_ratio_max)} r={cur ? 7 : 4.5} />
                <text x={X(p.x_i2i1) + dx} y={Yc(p.y_ratio_max) + (p.label === "정상" ? -6 : 4)} textAnchor={dx < 0 ? "end" : "start"}>{p.scene} {p.label}</text>
              </g>
            );
          })}
          <g className="m-live"><circle cx={X(liveX)} cy={Yc(liveY)} r={9} /><circle cx={X(liveX)} cy={Yc(liveY)} r={3} /></g>
        </svg>
        <div className="m-rules">
          <span>세 줄 같이 <b className="r">빨강</b> = 과부하</span><span>한 줄 <b className="r">빨강</b> = 단락</span><span>한 줄 <b className="b">파랑</b>·두 줄 <b className="r">빨강</b> = 결상</span>
          <span><b className="g">초록</b>인데 숫자 상승 = 전압 불평형</span><span>세 줄 같이 <b className="b">파랑</b> = 무부하</span>
        </div>
      </div>
    </div>
  );
}
