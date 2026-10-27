import type { Mode, ModeData } from "../../data";
import { usePlayback } from "../../state/playback";
import type { ModeContent } from "../../content/types";

// 결함 도감 — 카드를 누르면 해당 결함이 나오는 영상 구간으로 이동한다.
export function FaultCards({ mode, data, content }: { mode: Mode; data: ModeData; content: ModeContent }) {
  const { seek, play } = usePlayback();
  const cards = content.faultCards(data);
  return (
    <div className="cards">
      {cards.map((c) => {
        const step = c.stepId ? data.scenarios.steps.find((s) => s.id === c.stepId) : undefined;
        return (
          <div key={c.key} className="card" onClick={() => { if (step) { seek(step.t_start + 0.05); play(); } }}
               title={step ? `클릭: 영상 ${step.n}번 장면으로 이동` : "이 결함은 현재 시나리오 영상에 없습니다"}>
            <h3>{c.name}</h3>
            <div className="easy">{c.easy}</div>
            <dl>
              <dt>원인</dt><dd>{c.cause}</dd>
              <dt>화면에서</dt><dd>{c.seen}</dd>
              <dt>판정 기준</dt><dd>{c.criteria}</dd>
              <dt>방치하면</dt><dd>{c.ifIgnored}</dd>
              <dt>현장 조치</dt><dd>{c.action}</dd>
            </dl>
            <div className="sig">{c.signals.map((s) => <span key={s}>VIGENT 감지: {s}</span>)}</div>
            {step && <div className="dim" style={{ marginTop: 6 }}>▶ 영상 {step.n}번 장면 {mode === "mechanical" ? "(온도)" : "(전류)"}</div>}
          </div>
        );
      })}
    </div>
  );
}
