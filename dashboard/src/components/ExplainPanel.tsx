import { indexAt, type ModeData } from "../data";
import { usePlayback } from "../state/playback";
import type { ModeContent } from "../content/types";

// 지금 무엇이 보이는가 → 왜 그런가 → 무엇을 해야 하는가 (챕터당 3문장, src/content 에서 온다)
export function ExplainPanel({ data, content }: { data: ModeData; content: ModeContent }) {
  const { t, stepIndex } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  const i = indexAt(data.timeseries, t);
  const text = content.chapter(step.id, data, i);
  return (
    <div className="panel explain">
      <div className="panel-h">지금 일어나는 일</div>
      <div className="panel-b explain fade" key={step.id} style={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <div className="title">{step.label}</div>
        <div className="sub">{step.subtitle}</div>
        <dl className="q">
          <dt>무엇이 보이나</dt><dd>{text.see}</dd>
          <dt>왜 그런가</dt><dd>{text.why}</dd>
          <dt>현장에서는</dt><dd>{text.act}</dd>
        </dl>
        <div className="src">데이터 출처: {step.source} · 이 구간 열 시뮬레이션 배속 ×{step.time_scale}</div>
      </div>
    </div>
  );
}
