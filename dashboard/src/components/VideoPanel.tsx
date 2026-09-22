import type { ReactNode } from "react";
import { fmtT, type ModeData } from "../data";
import { usePlayback } from "../state/playback";

// 영상이 단일 시간 소스. 아래 챕터 타임라인을 누르면 그 시각으로 이동한다(양방향 동기화).
// overlay: 영상 위에 겹쳐 그릴 요소 (기계 대시보드의 자막 바). 전기 대시보드는 넘기지 않는다.
export function VideoPanel({ data, overlay }: { data: ModeData; overlay?: ReactNode }) {
  const { videoRef, t, playing, toggle, seek, stepIndex, duration } = usePlayback();
  const sc = data.scenarios;
  return (
    <div className="panel video-wrap">
      <div className="panel-h">
        애니메이션 <span className="dim">Isaac Sim 녹화 · 오프셋 {sc.video_offset_s.toFixed(3)} s</span>
        <span className="grow" />
        <span className="dim">{sc.steps[stepIndex].n}/{sc.steps.length} {sc.steps[stepIndex].label}</span>
      </div>
      <div className="video-box">
        <video ref={videoRef} src={`${sc.video}?v=${sc.video_offset_s}`} preload="auto" playsInline onClick={toggle} />   /* 재녹화(오프셋 변경)마다 주소가 바뀌어 캐시된 옛 영상이 나오지 않는다 */
        {overlay}
      </div>
      <div className="controls">
        <button className="primary" onClick={toggle}>{playing ? "❚❚ 정지" : "▶ 재생"}</button>
        <button onClick={() => seek(0)}>⏮ 처음</button>
        <span className="time">{fmtT(t)} / {fmtT(duration)}</span>
        <input type="range" min={0} max={duration} step={0.05} value={t} style={{ flex: 1 }}
               onChange={(e) => seek(Number(e.target.value))} aria-label="재생 위치" />
      </div>
      <div className="chapters">
        {sc.steps.map((s, i) => {
          const prog = i < stepIndex ? 1 : i > stepIndex ? 0 : (t - s.t_start) / (s.t_end - s.t_start);
          return (
            <div key={s.id} className={"chapter" + (i === stepIndex ? " active" : "") + (s.highlight ? " hl" : "")}
                 onClick={() => seek(s.t_start + 0.05)} title={s.subtitle}>
              <span className="n">{s.n}</span>{s.label.replace(/^\d+\.\s*/, "")}
              <div className="prog" style={{ width: `${Math.max(0, Math.min(prog, 1)) * 100}%` }} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
