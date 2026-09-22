import { useEffect } from "react";
import { usePlayback } from "../state/playback";
import { fill, liveValues, type MechData } from "./data";

// Q 서랍 (TASK 7.1): 예상 질문과 답 (content/mechanical/qa.yaml — 해설 PDF 7장 중 기계 항목).
// 답 안의 {변수} 는 항목이 지정한 장면(scene)의 narration_values 로 채우고, 실시간 변수는 현재 재생 시각 값이다.
// 현재 장면과 관련된 질문이 위로 온다. Q 키 또는 Esc 로 닫는다.
export function QaDrawer({ data, open, onClose }: { data: MechData; open: boolean; onClose: () => void }) {
  const { t, stepIndex } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  useEffect(() => {
    if (!open) return;
    const on = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [open, onClose]);
  if (!open) return null;
  const live = liveValues(data, t);
  const items = data.content.qa.map((q, n) => ({ ...q, n, here: q.scene === step.id }))
    .sort((a, b) => Number(b.here) - Number(a.here) || a.n - b.n);
  return (
    <div className="qa-drawer" role="dialog" aria-label="예상 질문과 답">
      <div className="qa-h">
        <b>예상 질문과 답</b> <span className="dim">해설 PDF 7장 · 기계적 결함 · 숫자는 config/로그 값</span>
        <span className="grow" /><button onClick={onClose}>닫기 (Q)</button>
      </div>
      <div className="qa-b">
        {items.map((q) => {
          const v = { ...data.values[q.scene ?? step.id], ...live };
          const sceneStep = data.scenarios.steps.find((s) => s.id === q.scene);
          return (
            <div key={q.n} className={"qa-item" + (q.here ? " here" : "")}>
              <div className="qa-q">Q. {fill(q.q, v)} {q.here && <span className="tag">이 장면</span>}
                {sceneStep && !q.here && <span className="dim"> · 장면 {sceneStep.n} 기준</span>}</div>
              <div className="qa-a">{fill(q.a, v)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
