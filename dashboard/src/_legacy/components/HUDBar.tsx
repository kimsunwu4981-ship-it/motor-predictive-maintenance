import { indexAt, worstElec, worstStage, type Mode, type ModeData } from "../../data";
import { usePlayback } from "../../state/playback";
import { STAGE_ICON, ELEC_ICON } from "./Legend";

// 상단 바: 프로젝트명 · 모드 · 현재 상태 뱃지 · 정직성 라벨. 다른 모드로 가는 작은 링크만 둔다.
export function HUDBar({ mode, data, theme, onTheme, present, onPresent }: {
  mode: Mode; data: ModeData; theme: "dark" | "light"; onTheme: () => void; present: boolean; onPresent: () => void;
}) {
  const { t } = usePlayback();
  const th = data.thresholds;
  const i = indexAt(data.timeseries, t);
  let badge: { text: string; color: string; icon: string };
  if (mode === "mechanical") {
    const hudKeys = th.thermal.parts.filter((p) => p.hud).map((p) => p.key);
    const s = worstStage(data.timeseries, i, hudKeys);
    badge = { text: th.thermal.stage_labels[s], color: th.thermal.stage_colors[s], icon: STAGE_ICON[s] };
  } else {
    const s = worstElec(data.timeseries, i);
    badge = { text: th.electrical.status_labels[s], color: th.electrical.status_colors[s], icon: ELEC_ICON[s] };
  }
  const other = mode === "mechanical" ? { href: "#/electrical", label: "전기적 결함 →" } : { href: "#/mechanical", label: "← 기계적 결함" };
  return (
    <div className="panel hud">
      <span className="brand">VIGENT</span>
      <span className="muted subtitle">크레인 권상 모터 디지털 트윈</span>
      <span className="mode">{mode === "mechanical" ? "기계적 결함 (온도)" : "전기적 결함 (전류)"}</span>
      <span className="badge" style={{ background: badge.color }} title="현재 재생 시각의 상태 등급">
        <span className="ic">{badge.icon}</span>{badge.text}
      </span>
      <span className="grow" />
      {!present && <a href={other.href} className="dim">{other.label}</a>}
      {!present && <button onClick={onTheme} title="테마">{theme === "dark" ? "☀ 라이트" : "☾ 다크"}</button>}
      <button onClick={onPresent} title="F 키">{present ? "발표 모드 종료 (Esc)" : "발표 모드 (F)"}</button>
      <span className="honesty">
        <b>{th.honesty.label}</b>
        <span>{th.honesty.rating_basis}</span>
        <span>{mode === "mechanical" ? th.honesty.thermal_note : th.honesty.current_note}</span>
      </span>
    </div>
  );
}
