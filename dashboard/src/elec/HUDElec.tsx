import React, { useEffect, useRef, useState } from "react";
import { usePlayback } from "../state/playback";
import { ELEC_ICON } from "../components/Legend";
import { ELEC_SEVERITY, idxAt, PHASES, type Basis, type ElecData } from "./data";

// 상단 바 (전기): 모드 · 장면 n/7 제목·지문 · 상태 뱃지(주목 상 기준) · 슬로모션 표시(TASK 5.4) · 선/상전류 토글 · 정직성 라벨
export function HUDElec({ data, theme, onTheme, present, onPresent, autoMode, onAutoMode, captions, onCaptions, qa, onQa, onPresenter, basis, onBasis, extra, banner }: {
  data: ElecData; theme: "dark" | "light"; onTheme: () => void; present: boolean; onPresent: () => void;
  autoMode: boolean; onAutoMode: () => void; captions: boolean; onCaptions: () => void; qa: boolean; onQa: () => void; onPresenter: () => void;
  basis: Basis; onBasis: () => void;
  extra?: React.ReactNode;            // 녹화/LIVE 토글
  banner?: React.ReactNode;           // 끊김 띠
}) {
  const { t, stepIndex } = usePlayback();
  const th = data.thresholds, el = th.electrical, ts = data.timeseries;
  const i = idxAt(ts, t);
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  // 뱃지: 주목 상 중 가장 심한 상태 (주목 상이 없으면 세 상). 장면 5 처럼 I₂/I₁ 만 주목하면 "색은 정상" 을 그대로 보여준다.
  const keys = scene?.focus_phases?.length ? scene.focus_phases : PHASES;
  const worst = keys.reduce((w, p) => (ELEC_SEVERITY[ts.current_status[p][i]] > ELEC_SEVERITY[w] ? ts.current_status[p][i] : w), ts.current_status[keys[0]][i]);
  const badgeTitle = `주목 상(${keys.map((p) => el.phase_labels[p]).join("·")})의 현재 상태 — 정격 대비 전류로 판정`;

  // 장면이 바뀌면 슬로모션 표시를 짧게 강조 (기계의 배속 강조와 같은 자리)
  const [flash, setFlash] = useState(false);
  const prev = useRef(stepIndex);
  useEffect(() => {
    if (prev.current !== stepIndex) { prev.current = stepIndex; setFlash(true); const h = setTimeout(() => setFlash(false), 1800); return () => clearTimeout(h); }
  }, [stepIndex]);

  return (
    <div className="panel hud">
      <span className="brand">VIGENT</span>
      <span className="mode">전기적 결함 (전류)</span>
      <span className="scene-title">장면 {step.n}/{data.scenarios.steps.length} <b>{scene?.title ?? step.label}</b>
        {scene?.fingerprint && <span className="dim fp"> — {scene.fingerprint}</span>}</span>
      <span className="badge" style={{ background: el.status_colors[worst] }} title={badgeTitle}>
        <span className="ic">{ELEC_ICON[worst]}</span>{el.status_labels[worst]}
      </span>
      <span className={"tc" + (flash ? " flash" : "")}
            title="실제 전류는 1초에 60번 방향이 바뀌어 눈으로 볼 수 없습니다. 흐름을 보이게 하려고 느리게 그렸습니다.">
        <span className="tc-scale">입자 흐름 <b>{el.slowmo_x}</b>배 느리게 표시</span>
        <span className="tc-elapsed">실제 <b>{th.motor.frequency_Hz}</b> Hz 교류</span>
      </span>
      <button className={"b-basis" + (basis === "phase" ? " on" : "")} onClick={onBasis}
              title={`왜 두 가지인가: Δ(델타)결선이라 케이블의 선전류(정격 ${el.rated_line_A} A)와 권선 안의 상전류(정격 ${el.rated_phase_A} A)가 √3 배 다릅니다. 기본은 케이블(선전류), 권선 오버레이를 설명할 때 상전류로 바꿉니다. (L 키)`}>
        {basis === "line" ? "선전류 ⇄" : "상전류 ⇄"}
      </button>
      <span className="grow" />
      {extra}
      {!present && <button onClick={onAutoMode} title="자동 해설: 해설 단계가 시간에 따라 저절로 공개 / 발표자 모드: N 키를 눌러야 다음 단계">{autoMode ? "자동 해설" : "발표자 모드 · N"}</button>}
      {!present && <button className="b-qa" onClick={onQa} title="Q 키: 예상 질문과 답 서랍">{qa ? "☑ 질문 Q" : "☐ 질문 Q"}</button>}
      {!present && <button className="b-pres" onClick={onPresenter} title="발표자 노트북용 화면을 새 창으로 연다 (멘트는 그 창에만)">발표자 ↗</button>}
      {!present && <button className="b-cap" onClick={onCaptions} title="C 키: 영상 아래 자막 켜기/끄기">{captions ? "☑ 자막 C" : "☐ 자막 C"}</button>}
      {!present && <button className="b-theme" onClick={onTheme} title="테마">{theme === "dark" ? "☀" : "☾"}</button>}
      <button onClick={onPresent} title="F 키">{present ? "발표 종료 Esc" : "발표 F"}</button>
      {data.source && (
        <span className={"basis-badge " + data.source.method}
              title={data.source.method === "lut"
                ? `전류 신호 근거: ${data.source.grade} · ${data.source.status} · FEM 검증 ${data.source.fem_verified ? "됨" : "안 됨"} · ${data.source.lut_version} (sha ${data.source.lut_sha256}) · 상당 턴수 ${data.source.base_turns_per_phase} · 고유 비대칭 I₂/I₁ ${data.source.inherent_i2i1} · I_n ${data.source.rated_current_A} A`
                : `전류 신호 근거: ${data.source.grade} — ${data.source.reason}`}>
          {data.source.method === "lut" ? <>근거 <b>등가회로 LUT</b> · {data.source.status} · FEM 미검증</> : <>근거 <b>해석식 역산</b> (legacy)</>}
        </span>
      )}
      <span className="honesty">
        <b>{th.honesty.label}</b>
        <span>{th.honesty.rating_basis}</span>
        <span>{th.honesty.current_note}</span>
      </span>
      {banner}
    </div>
  );
}
