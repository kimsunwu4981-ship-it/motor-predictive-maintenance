import type { Mode, ModeData } from "../../data";
import { ELEC_ICON, STAGE_ICON } from "./Legend";
import { CONTENT } from "../../content";

// 색상 기준표 — 모든 숫자는 thresholds.json 에서 온다.
export function ThresholdTable({ mode, data }: { mode: Mode; data: ModeData }) {
  const th = data.thresholds;
  if (mode === "mechanical") {
    const why = CONTENT.mechanical.partReason ?? (() => "");
    const c = th.thermal.stage_colors;
    return (
      <div>
        <p className="muted" style={{ marginTop: 0 }}>
          부품마다 허용 온도가 다르므로 <b>같은 온도라도 색이 다를 수 있습니다</b>. 값은 "이 온도까지"를 뜻합니다.
          위험 단계에서는 빨강이 {th.thermal.pulse_hz} Hz 로 깜빡이며 발광합니다.
        </p>
        <table className="grid">
          <thead><tr>
            <th>부품</th>
            <th><span className="sw" style={{ background: th.thermal.base_material }} />{STAGE_ICON.normal} 정상 (원래 재질)</th>
            <th><span className="sw" style={{ background: c.caution }} />{STAGE_ICON.caution} 주의</th>
            <th><span className="sw" style={{ background: c.warning }} />{STAGE_ICON.warning} 경고</th>
            <th><span className="sw pulse" style={{ background: c.danger, color: c.danger }} />{STAGE_ICON.danger} 위험 (발광·맥동)</th>
            <th>이 부품이 뜨거워지는 이유</th>
          </tr></thead>
          <tbody>
            {th.thermal.parts.map((p) => (
              <tr key={p.key}>
                <td><b>{p.label}</b>{p.note && <div className="dim">{p.note}</div>}</td>
                <td>~ {p.normal_max_C} °C</td>
                <td>{p.normal_max_C} ~ {p.caution_max_C} °C</td>
                <td>{p.caution_max_C} ~ {p.warning_max_C} °C</td>
                <td>{p.warning_max_C} °C 초과</td>
                <td>{why(p.key)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="dim">예: 구동측 베어링은 {th.thermal.parts.find((p) => p.key === "bearing_de")?.caution_max_C} °C 를 넘으면 붉게 변하고, {th.thermal.parts.find((p) => p.key === "bearing_de")?.warning_max_C} °C 이상에서 깜빡이며 발광합니다.</p>
      </div>
    );
  }
  const e = th.electrical;
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        정격 대비 비율(r)로 판정하고 실제 암페어로 환산했습니다. 이 모터는 <b>{th.motor.connection === "delta" ? "Δ(델타)" : th.motor.connection === "star" ? "Y(스타)" : th.motor.connection}결선</b>이라
        케이블에는 선전류(정격 {e.rated_line_A} A), 권선 안에는 상전류(정격 {e.rated_phase_A} A)가 흐르므로 두 기준을 나눠 봅니다.
      </p>
      <table className="grid">
        <thead><tr><th>상태</th><th>색</th><th>기준 (정격 대비)</th><th>케이블 선전류</th><th>권선 상전류</th></tr></thead>
        <tbody>
          {e.rows.map((r) => (
            <tr key={r.status}>
              <td><b>{ELEC_ICON[r.status]} {r.label}</b></td>
              <td><span className="sw" style={{ background: r.color }} /></td>
              <td>{r.ratio_text}</td>
              <td>{r.status === "normal" && r.line_range_A ? `${r.line_range_A[0]} ~ ${r.line_range_A[1]} A` : `${r.line_A} A`}</td>
              <td>{r.status === "normal" && r.phase_range_A ? `${r.phase_range_A[0]} ~ ${r.phase_range_A[1]} A` : `${r.phase_A} A`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3 style={{ marginTop: 14 }}>I₂/I₁ (역상분 비율) 눈금</h3>
      <p className="muted">세 줄의 전류가 서로 얼마나 균형이 깨졌는지를 나타내는 숫자입니다. 권선 단락은 전류 크기보다 이 숫자에서 먼저 드러납니다.</p>
      <div className="gauge">
        {e.i2i1_marks.map((m) => (
          <span key={m.case} className="chip">{m.label} ≈ <b>{m.value}</b></span>
        ))}
      </div>
    </div>
  );
}
