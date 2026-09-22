import { indexAt } from "../data";
import { usePlayback } from "../state/playback";
import type { MechData } from "./data";

// ② 위치 안내 (TASK 5.3). M2: 자리·주목 부품 표시만. M3 에서 SVG 단면도·실시간 색·열 경로 화살표를 그린다.
export function MotorSchematic({ data, focus }: { data: MechData; focus: string }) {
  const { t } = usePlayback();
  const th = data.thresholds, ts = data.timeseries;
  const i = indexAt(ts, t);
  const p = th.thermal.parts.find((q) => q.key === focus);
  const stage = p ? ts.stage[focus][i] : "normal";
  return (
    <div className="panel schem">
      <div className="panel-h">위치 안내 <span className="dim">모터 단면도 — M3 에서 SVG 로 구현</span></div>
      <div className="panel-b schem-body">
        <div className="schem-placeholder">
          <div className="dim">지금 달아오르는 부품</div>
          <div className="schem-focus" style={{ color: th.thermal.stage_colors[stage] }}>
            ▶ {p?.label ?? focus} · {p ? ts.temperature_C[focus][i].toFixed(1) : "-"} °C · {th.thermal.stage_labels[stage]}
          </div>
          {p && <div className="dim">허용 {p.normal_max_C} / {p.caution_max_C} / {p.warning_max_C} °C · {p.note}</div>}
        </div>
      </div>
    </div>
  );
}
