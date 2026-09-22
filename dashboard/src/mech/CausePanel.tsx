import { usePlayback } from "../state/playback";
import { fill, type MechData } from "./data";

// ④ 원인 패널 (TASK 5.5). M2: 인과 흐름 카드만. M4 에서 손실 기여 막대·결함 지문 미니맵을 더한다.
export function CausePanel({ data }: { data: MechData }) {
  const { stepIndex } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = data.values[step.id];
  const cc = scene?.cause_chain;
  return (
    <div className="panel cause">
      <div className="panel-h">원인 → 메커니즘 → 결과 → 조치</div>
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
        <div className="dim" style={{ marginTop: 8 }}>손실 기여 막대·결함 지문 미니맵 — M4</div>
      </div>
    </div>
  );
}
