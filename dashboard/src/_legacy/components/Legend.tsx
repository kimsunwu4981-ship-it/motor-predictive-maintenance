import type { ElecStatus, Mode, ModeData, Stage } from "../../data";

// 색각 이상 관람자를 위해 색 + 아이콘/텍스트를 항상 함께 쓴다.
export const STAGE_ICON: Record<Stage, string> = { normal: "●", caution: "◐", warning: "▲", danger: "■" };
export const ELEC_ICON: Record<ElecStatus, string> = {
  over_danger: "▲▲", over_caution: "▲", normal: "●", under_caution: "▼", under_danger: "▼▼",
};

export function Legend({ mode, data }: { mode: Mode; data: ModeData }) {
  const th = data.thresholds;
  if (mode === "mechanical") {
    const order: Stage[] = ["normal", "caution", "warning", "danger"];
    return (
      <div className="legend">
        {order.map((s) => (
          <span key={s}>
            <span className={"sw" + (s === "danger" ? " pulse" : "")}
                  style={{ background: s === "normal" ? th.thermal.base_material : th.thermal.stage_colors[s], color: th.thermal.stage_colors[s] }} />
            {STAGE_ICON[s]} {th.thermal.stage_labels[s]}{s === "normal" ? " (원래 재질)" : s === "danger" ? " (발광·맥동)" : ""}
          </span>
        ))}
      </div>
    );
  }
  const order: ElecStatus[] = ["over_danger", "over_caution", "normal", "under_caution", "under_danger"];
  return (
    <div className="legend">
      {order.map((s) => (
        <span key={s}><span className="sw" style={{ background: th.electrical.status_colors[s] }} />{ELEC_ICON[s]} {th.electrical.status_labels[s]}</span>
      ))}
      <span><span className="sw pulse" style={{ background: th.electrical.short_loop_color, color: th.electrical.short_loop_color }} />단락 루프</span>
    </div>
  );
}
