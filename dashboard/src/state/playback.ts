// playback.ts — 영상의 currentTime 이 단일 시간 소스다 (dashboard/CLAUDE.md §5).
//
// 모든 패널은 t_real(시뮬레이션 로그 시각)로 대화한다.
//   t_real = video.currentTime - video_offset_s
// 차트 클릭·챕터 이동은 seek(t_real) 로 영상을 움직이고, 영상이 움직이면 t 가 갱신된다.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import type { Scenarios } from "../data";

export interface Playback {
  t: number;                    // 현재 t_real [s]
  playing: boolean;
  duration: number;             // 시나리오 길이 [s]
  videoRef: RefObject<HTMLVideoElement>;
  seek: (tReal: number) => void;
  toggle: () => void;
  play: () => void;
  pause: () => void;
  gotoStep: (n: number) => void;      // 1-based 챕터 번호
  stepIndex: number;                  // 현재 챕터 (0-based)
}

export const PlaybackContext = createContext<Playback | null>(null);
export function usePlayback(): Playback {
  const p = useContext(PlaybackContext);
  if (!p) throw new Error("PlaybackContext 밖에서 usePlayback 호출");
  return p;
}

const UPDATE_HZ = 20;   // 커서 갱신 주기. timeupdate 이벤트(약 4 Hz)만으로는 커서가 끊겨 보인다.

export function usePlaybackController(sc: Scenarios): Playback {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const pending = useRef<{ t: number; at: number } | null>(null);   // 진행 중인 seek 목표
  const off = sc.video_offset_s;
  const duration = sc.total_duration_s;

  // rAF 루프: 재생 중이면 영상 시각을 t_real 로 바꿔 상태에 반영 (20 Hz 스로틀)
  useEffect(() => {
    let raf = 0, last = 0;
    const tick = (now: number) => {
      const v = videoRef.current;
      if (v && now - last >= 1000 / UPDATE_HZ) {
        last = now;
        const pd = pending.current;
        if (pd && Math.abs(v.currentTime - (pd.t + off)) > 0.3 && now - pd.at < 3000) { raf = requestAnimationFrame(tick); return; }
        pending.current = null;
        const tr = Math.max(0, Math.min(v.currentTime - off, duration));
        setT((prev) => (Math.abs(prev - tr) > 1e-3 ? tr : prev));
        if (v.paused !== !playing) setPlaying(!v.paused);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [off, duration, playing]);

  // URL 의 ?t=초 로 시작 위치를 지정할 수 있다 (스크린샷·동기 검증·특정 장면 바로 열기)
  //   예) #/mechanical?t=40
  useEffect(() => {
  //   ?autoplay=1 을 더하면 로드 즉시 재생한다 (화면 녹화용; 자동재생 정책 때문에 음소거로 튼다 — 영상에 소리는 없다)
  //   &delay=5 를 더하면 그만큼 기다렸다 재생한다 (녹화 프로그램이 창을 잡을 시간)
    const q = window.location.hash.split("?")[1];
    const params = new URLSearchParams(q ?? "");
    const auto = params.get("autoplay") === "1";
    const delay = Math.max(0, Number(params.get("delay") ?? 0) || 0);
    const t0 = q ? Number(params.get("t") ?? (auto ? 0 : NaN)) : NaN;
    const v = videoRef.current;
    if (!v || !Number.isFinite(t0)) return;
    const tr = Math.max(0, Math.min(t0, duration));
    setT(tr);                                   // 차트·설명은 영상 로드와 무관하게 즉시 그 시각으로
    pending.current = { t: tr, at: performance.now() };
    const apply = () => {
      pending.current = { t: tr, at: performance.now() }; v.currentTime = tr + off;
      if (auto) { v.muted = true; setTimeout(() => v.play().then(() => setPlaying(true)).catch(() => undefined), delay * 1000); }
    };
    if (v.readyState >= 1) apply(); else v.addEventListener("loadedmetadata", apply, { once: true });
  }, [off, duration]);

  const seek = useCallback((tReal: number) => {
    const v = videoRef.current;
    const tr = Math.max(0, Math.min(tReal, duration));
    pending.current = { t: tr, at: performance.now() };
    if (v) v.currentTime = tr + off;
    setT(tr);
  }, [off, duration]);
  const play = useCallback(() => { videoRef.current?.play().catch(() => undefined); setPlaying(true); }, []);
  const pause = useCallback(() => { videoRef.current?.pause(); setPlaying(false); }, []);
  const toggle = useCallback(() => { const v = videoRef.current; if (!v) return; if (v.paused) play(); else pause(); }, [play, pause]);

  const stepIndex = useMemo(() => {
    const i = sc.steps.findIndex((s) => t < s.t_end);
    return i < 0 ? sc.steps.length - 1 : i;
  }, [sc.steps, t]);
  const gotoStep = useCallback((n: number) => {
    const s = sc.steps[Math.max(0, Math.min(n - 1, sc.steps.length - 1))];
    seek(s.t_start + 0.05);
  }, [sc.steps, seek]);

  return useMemo(() => ({ t, playing, duration, videoRef, seek, toggle, play, pause, gotoStep, stepIndex }),
    [t, playing, duration, seek, toggle, play, pause, gotoStep, stepIndex]);
}
