import type { ReactNode } from "react";
import { fmtT, type ModeData } from "../data";
import { usePlayback } from "../state/playback";
import type { LiveSession } from "./session";

// 라이브 모드의 영상 패널 자리 (TASK 실시간 §6 "영상 영역" 옵션 1: 비움 + 안내, 듀얼 모니터용 기본).
// 옵션 2(스냅샷)·3(WebRTC)은 R5. 아래 챕터 줄은 스트림에서 관찰된 장면 전환(LiveBuffer → liveSteps)이고,
// 누르면 play_scenario 명령을 보낸다(←/→ 와 같음). 재생 바는 "최근 N 초" 창이다 — 되감기 대신 "최근 기록 보기"(일시정지)로 버퍼 안을 본다.
export function LiveVideoPanel({ data, live, overlay }: { data: ModeData; live: LiveSession; overlay?: ReactNode }) {
  const { t, playing, toggle, seek, stepIndex, duration } = usePlayback();
  const sc = data.scenarios;
  const tMin = sc.t_min ?? 0;
  const span = Math.max(duration - tMin, 1e-6);
  const st = live.last;
  return (
    <div className="panel video-wrap live-video">
      <div className="panel-h">
        라이브 <span className="dim">Isaac Sim 창을 보세요 · {live.url}</span>
        <span className="grow" />
        <span className="dim">{sc.steps[stepIndex]?.label ?? "-"}</span>
      </div>
      <div className="video-box live-hint">
        <div className="hint-main">
          <div className="hint-title">Isaac Sim 창을 보세요</div>
          <div className="hint-sub">이 화면의 게이지·차트·해설은 Isaac Sim 이 보내는 state(10 Hz)로 움직입니다. 영상 패널은 듀얼 모니터용으로 비워 두었습니다.</div>
          {st && (
            <div className="hint-grid">
              <span><i>모터</i>{st.motor_id}</span><span><i>모드</i>{st.mode}</span>
              <span><i>장면</i>{st.scene ? `${st.scene.label} · ${st.scene.elapsed_s.toFixed(0)} / ${st.scene.duration_s.toFixed(0)} s` : "수동 조작"}</span>
              <span><i>결함</i>{st.faults.length ? st.faults.join(", ") : (st.case !== "healthy" ? st.case : "없음")}</span>
              <span><i>부하 · 배속</i>{Math.round(st.load * 100)} % · ×{st.time_scale}</span>
              <span><i>FPS · VRAM</i>{st.perf?.fps ?? "-"} · {st.perf?.vram_mb ? `${(st.perf.vram_mb / 1024).toFixed(1)} GB` : "-"}</span>
            </div>
          )}
        </div>
        {overlay}
      </div>
      <div className="controls">
        <button className="primary" onClick={toggle} title={playing ? "일시정지: 버퍼 안을 돌려본다 (최근 기록 보기)" : "LIVE 로 복귀"}>{playing ? "❚❚ 최근 기록 보기" : "▶ LIVE 복귀"}</button>
        <span className="time">{playing ? "LIVE" : fmtT(t)} · 최근 {Math.round(live.cfg.window_s / 60)} 분</span>
        <input type="range" min={tMin} max={duration} step={0.1} value={t} style={{ flex: 1 }} disabled={playing}
               onChange={(e) => seek(Number(e.target.value))} aria-label="버퍼 위치" />
      </div>
      <div className="chapters">
        {sc.steps.map((s, i) => {
          const prog = i < stepIndex ? 1 : i > stepIndex ? 0 : (t - s.t_start) / Math.max(s.t_end - s.t_start, 1e-6);
          return (
            <div key={s.id + s.t_start} className={"chapter" + (i === stepIndex ? " active" : "")} style={{ flex: Math.max(s.t_end - s.t_start, 2) / span }}
                 onClick={() => { if (s.n > 0) live.send("play_scenario", { scene: s.n }); }} title={s.n > 0 ? `장면 ${s.n} 부터 다시 재생 (play_scenario)` : "수동 조작 구간"}>
              <span className="n">{s.n > 0 ? s.n : "·"}</span>{s.label.replace(/^\d+\.\s*/, "")}
              <div className="prog" style={{ width: `${Math.max(0, Math.min(prog, 1)) * 100}%` }} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
