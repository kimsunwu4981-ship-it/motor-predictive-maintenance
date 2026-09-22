import { usePlayback } from "../state/playback";
import { fill, type MechData } from "./data";

// ① 실시간 해설 (TASK 5.2). M2: 장면 해설의 기본 표시. M4 에서 단계별 공개·이벤트 자막·이력 목록을 더한다.
export function LiveNarration({ data }: { data: MechData }) {
  const { stepIndex } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = data.values[step.id];
  if (!scene) return <div className="panel narr"><div className="panel-h">실시간 해설</div><div className="panel-b muted">narration.yaml 에 {step.id} 장면이 없습니다</div></div>;
  return (
    <div className="panel narr">
      <div className="panel-h">실시간 해설 <span className="dim">장면 {step.n} · {scene.fingerprint}</span></div>
      <div className="panel-b fade" key={step.id}>
        <div className="narr-title">{scene.title}</div>
        <dl className="q">
          <dt>왜 그런가</dt><dd>{fill(scene.why, v)}</dd>
          <dt>무엇이 보이나</dt><dd>{fill(scene.visible, v)}</dd>
          <dt>그래서</dt><dd>{fill(scene.result, v)}</dd>
        </dl>
        <div className="src">데이터 출처: {step.source}</div>
      </div>
    </div>
  );
}
