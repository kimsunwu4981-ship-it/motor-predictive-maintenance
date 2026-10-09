import React, { useEffect, useRef, useState } from "react";
import { indexAt, worstStage } from "../data";
import { usePlayback } from "../state/playback";
import { STAGE_ICON } from "../components/Legend";
import { fmtSim, type MechData } from "./data";

// 상단 바: 모드 · 장면 n/7 제목 · 상태 뱃지 · 시간 압축 · 정직성 라벨 (dashboard/CLAUDE.md 규칙 4·5, TASK 5.4)
export function HUDLive({ data, theme, onTheme, present, onPresent, autoMode, onAutoMode, captions, onCaptions, qa, onQa, onPresenter, extra, banner }: {
  data: MechData; theme: "dark" | "light"; onTheme: () => void; present: boolean; onPresent: () => void;
  autoMode: boolean; onAutoMode: () => void; captions: boolean; onCaptions: () => void; qa: boolean; onQa: () => void; onPresenter: () => void;
  extra?: React.ReactNode;            // 녹화/LIVE 토글 (항상 보인다 — 모드 표시 규칙 §1.6)
  banner?: React.ReactNode;           // 끊김 띠 (hud 패널 안, 줄바꿈) — 바깥 grid 행을 밀지 않는다
}) {
  const { t, stepIndex } = usePlayback();
  const th = data.thresholds, ts = data.timeseries;
  const i = indexAt(ts, t);
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const focus = scene?.focus_component;
  const hudKeys = th.thermal.parts.filter((p) => p.hud).map((p) => p.key);
  const s = worstStage(ts, i, hudKeys);
  const focusStage = focus ? ts.stage[focus][i] : s;
  const scale = ts.time_scale[i];

  // 장면이 바뀌어 배속이 달라지면 짧게 강조한다 (TASK 5.4)
  const [flash, setFlash] = useState(false);
  const prevScale = useRef(scale);
  useEffect(() => {
    if (prevScale.current !== scale) { prevScale.current = scale; setFlash(true); const h = setTimeout(() => setFlash(false), 1800); return () => clearTimeout(h); }
  }, [scale]);

  return (
    <div className="panel hud">
      <span className="brand">VIGENT</span>
      <span className="mode">기계적 결함 (온도)</span>
      <span className="scene-title">장면 {step.n}/{data.scenarios.steps.length} <b>{scene?.title ?? step.label}</b>
        {scene?.fingerprint && <span className="dim"> — {scene.fingerprint}</span>}</span>
      <span className="badge" style={{ background: th.thermal.stage_colors[focusStage] }}
            title={focus ? `주목 부품 ${th.thermal.parts.find((p) => p.key === focus)?.label} 의 현재 등급` : "현재 상태"}>
        <span className="ic">{STAGE_ICON[focusStage]}</span>{th.thermal.stage_labels[focusStage]}
      </span>
      <span className={"tc" + (flash ? " flash" : "")}
            title="실제 모터는 이렇게 빨리 뜨거워지지 않습니다. 발표 시간 안에 보여주기 위해 압축했습니다.">
        <span className="tc-scale">화면 1초 = 시뮬레이션 <b>{scale}</b>초</span>
        <span className="tc-elapsed">시뮬레이션 경과 <b>{fmtSim(ts.sim_elapsed_s[i])}</b></span>
      </span>
      <span className="grow" />
      {extra}
      {!present && <button onClick={onAutoMode} title="자동 해설: 해설 단계가 시간에 따라 저절로 공개 / 발표자 모드: N 키를 눌러야 다음 단계">{autoMode ? "자동 해설" : "발표자 모드 · N"}</button>}
      {!present && <button className="b-qa" onClick={onQa} title="Q 키: 예상 질문과 답 서랍">{qa ? "☑ 질문 Q" : "☐ 질문 Q"}</button>}
      {!present && <button className="b-pres" onClick={onPresenter} title="발표자 노트북용 화면을 새 창으로 연다 (멘트는 그 창에만)">발표자 ↗</button>}
      {!present && <button className="b-cap" onClick={onCaptions} title="C 키: 영상 아래 자막 켜기/끄기">{captions ? "☑ 자막 C" : "☐ 자막 C"}</button>}
      {!present && <button className="b-theme" onClick={onTheme} title="테마">{theme === "dark" ? "☀" : "☾"}</button>}
      <button onClick={onPresent} title="F 키">{present ? "발표 종료 Esc" : "발표 F"}</button>
      <span className="honesty">
        <b>{th.honesty.label}</b>
        <span>{th.honesty.rating_basis}</span>
        <span>{th.honesty.thermal_note}</span>
      </span>
      {banner}
    </div>
  );
}
