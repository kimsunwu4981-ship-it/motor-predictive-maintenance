import { usePlayback } from "../state/playback";
import { fill } from "../live/types";
import type { ElecData } from "./data";

// 원인 패널 (E2 골격) — E4 에서 결함 판별 매트릭스가 붙는다. 숫자는 전부 로그 값이다.

export function CauseElec({ data }: { data: ElecData }) {
  const { stepIndex } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = data.values[step.id];
  const cc = scene?.cause_chain;
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
        <div className="dim" style={{ marginTop: 8 }}>결함 판별 매트릭스 (크기 × 균형) — E4</div>
      </div>
    </div>
  );
}
