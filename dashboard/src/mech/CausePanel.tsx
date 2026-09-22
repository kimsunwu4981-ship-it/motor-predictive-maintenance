import { useMemo } from "react";
import { indexAt } from "../data";
import { usePlayback } from "../state/playback";
import { fill, type MechData } from "./data";
import { MiniMotor } from "./MotorSchematic";

// ④ 원인 패널 (TASK 5.5): 인과 흐름 카드 + 부품별 손실열 막대(실시간, 정상 대비 배율) + 결함 지문 미니맵(7장면).
// 손실열은 timeseries.json loss_W(엔진 재실행, 결함·부하만의 함수), 정격 손실은 thresholds.json loss_rated_W — 전부 config/로그.
export function CausePanel({ data, focus }: { data: MechData; focus: string }) {
  const { t, stepIndex, gotoStep } = usePlayback();
  const ts = data.timeseries, th = data.thresholds;
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = data.values[step.id];
  const cc = scene?.cause_chain;
  const i = indexAt(ts, t);
  const rated = th.thermal.loss_rated_W;
  // 손실이 생길 수 있는 부품만 (정격 손실 0 이고 시나리오 내내 0 인 부품은 뺀다)
  const lossParts = useMemo(() => th.thermal.parts.filter((p) => (rated[p.key] ?? 0) > 0 || Math.max(...ts.loss_W[p.key]) > 0), [th, ts, rated]);
  const maxW = useMemo(() => Math.max(...lossParts.map((p) => Math.max(...ts.loss_W[p.key]))), [lossParts, ts]);
  // 지문 미니맵: 장면 종료 시점(−0.3 s, narration_values 와 같은 규칙)의 부품 색
  const endIdx = useMemo(() => data.scenarios.steps.map((s) => indexAt(ts, s.t_end - 0.3)), [data.scenarios.steps, ts]);

  return (
    <div className="panel cause">
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
        <div className="cause-grid">
          <div className="loss">
            <div className="sub-h">손실열 <span className="dim">W · 정격 대비 배율</span></div>
            {lossParts.map((p) => {
              const W = ts.loss_W[p.key][i], r = rated[p.key] ?? 0;
              const ratio = r > 0 ? W / r : null;
              const col = th.thermal.stage_colors[ts.stage[p.key][i]];
              return (
                <div key={p.key} className={"loss-row" + (p.key === focus ? " focus" : "")}>
                  <span className="n">{p.label}</span>
                  <span className="loss-bar"><i style={{ width: `${maxW > 0 ? (W / maxW) * 100 : 0}%`, background: col }} /></span>
                  <span className="w">{Math.round(W)} W{ratio !== null ? <b className={ratio > 1.05 ? "hot" : ""}> ×{ratio.toFixed(1)}</b> : W > 0 ? <b className="hot"> 정상 0</b> : null}</span>
                </div>
              );
            })}
          </div>
          <div className="fmap-wrap">
            <div className="sub-h">결함 지문 비교 <span className="dim">장면 끝 색</span></div>
            <div className="fmap">
              {data.scenarios.steps.map((s, n) => (
                <div key={s.id} className={"fm" + (n === stepIndex ? " cur" : "")} onClick={() => gotoStep(s.n)}
                     title={`${s.label} — ${data.content.scenes[s.id]?.fingerprint ?? ""}`}>
                  <MiniMotor data={data} i={endIdx[n]} />
                  <div className="fm-l"><b>{s.n}</b> {(data.content.scenes[s.id]?.title ?? s.label).replace(/\s*\(.*\)$/, "")}</div>
                </div>
              ))}
            </div>
            <div className="fm-note dim">장면 4(전체 고르게) 와 5(축 먼저)처럼 패턴이 다르면 원인을 가릴 수 있다</div>
          </div>
        </div>
      </div>
    </div>
  );
}
