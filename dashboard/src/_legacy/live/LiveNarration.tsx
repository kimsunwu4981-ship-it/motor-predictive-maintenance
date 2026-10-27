import { useEffect, useMemo, useRef } from "react";
import { fmtT } from "../../data";
import { usePlayback } from "../../state/playback";
import { fillParts, type LiveData } from "./types";
import { REVEAL_KEYS, REVEAL_LABEL, revealTimes, type HistoryItem } from "./captions";

// ① 실시간 해설 (TASK 5.2, 공용). 두 층: (1) 장면 해설 — 왜 / 무엇이 보이나 / 그래서 를 reveal_timing 에 따라 단계별로 공개,
// 수치는 {…}_now 실시간 변수(data.live)로 재생 시각의 로그 값을 보여준다. (2) 이력 목록 — 지나간 장면 전환·해설·사건을
// 시간순으로 쌓고, 누르면 그 시점으로 이동한다.
// level: 공개된 단계 수(0~3). 자동 해설 모드는 시간이, 발표자 모드는 N 키가 올린다.
// note: 장면 아래 작게 붙일 데이터 출처 표기 (전기의 data_source_note — 규칙 5).
export function LiveNarration({ data, level, history }: { data: LiveData; level: number; history: HistoryItem[] }) {
  const { t, stepIndex, seek } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = useMemo(() => ({ ...data.values[step.id], ...data.live(t) }), [data, step.id, t]);

  const nPast = useMemo(() => { let n = 0; while (n < history.length && history[n].t <= t + 1e-6) n++; return n; }, [history, t]);
  const past = useMemo(() => history.slice(0, nPast), [history, nPast]);
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { const el = listRef.current; if (el) el.scrollTop = el.scrollHeight; }, [nPast]);

  if (!scene) return <div className="panel narr"><div className="panel-h">실시간 해설</div><div className="panel-b muted">{step.id === "manual"
    ? <>수동 조작 구간입니다 — 장면 해설은 시나리오가 재생될 때 나옵니다 (→ 키 또는 play_scenario 명령). 지금은 결함 토글·게이지·사건 자막으로 보세요.</>
    : <>narration.yaml 에 {step.id} 장면이 없습니다</>}</div></div>;
  const rt = revealTimes(scene, step);
  const emphasize = level >= 3;
  return (
    <div className="panel narr">
      <div className="panel-h">실시간 해설 <span className="dim">장면 {step.n} · {scene.fingerprint}</span>
        <span className="grow" /><span className="dim">{level}/3 공개</span></div>
      <div className="panel-b">
        <div className="narr-title fade" key={step.id}>{scene.title}</div>
        <dl className={"q reveal" + (emphasize ? " emph" : "")}>
          {REVEAL_KEYS.map((k, n) => {
            const on = level > n;
            return (
              <div key={step.id + k} className={"rv" + (on ? " on" : "")} title={on ? undefined : `${fmtT(rt[k])} 에 공개`}>
                <dt>{REVEAL_LABEL[k]}</dt>
                <dd>{on ? fillParts(scene[k], v).map((p, m) => (p.v ? <b key={m} className="v">{p.s}</b> : <span key={m}>{p.s}</span>))
                        : <span className="dim">… {fmtT(rt[k])}</span>}</dd>
              </div>
            );
          })}
        </dl>
        {scene.data_source_note && <div className="src-note">출처: {fillParts(scene.data_source_note, v).map((p) => p.s).join("")}</div>}
        <div className="hist" ref={listRef}>
          {past.length === 0 && <div className="dim">지나간 사건이 여기에 쌓입니다</div>}
          {past.map((h) => (
            <div key={h.id} className={"hist-item k-" + h.kind + (h.primary ? "" : " sec")} onClick={() => seek(h.t)} title="누르면 이 시점으로 이동">
              <span className="t">{fmtT(h.t)}</span>
              <span className="k">{h.kind === "scene" ? "장면" : h.kind === "narr" ? "해설" : h.primary ? "사건" : "동시"}</span>
              <span className="x">{h.text}</span>
            </div>
          ))}
        </div>
        <div className="src">데이터 출처: {step.source} · 수치는 재생 시각의 로그 값</div>
      </div>
    </div>
  );
}
