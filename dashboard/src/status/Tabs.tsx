import type { FleetIndex, MotorInfo } from "./data";

// 임계값 기준표 · 모터 사양표 (레이아웃 A 근거 서랍의 탭, 2026-10-27 — 기존 StatusBoard 의 ThresholdTab/SpecTab 을 그대로 옮김. 숫자는 전부 index.json).

export function ThresholdTab({ index, easy }: { index: FleetIndex; easy?: Record<string, string> }) {
  const th = index.thresholds;
  const ez = (k: string) => <td className="easy">{easy?.[k] ?? ""}</td>;
  const t = th.temperature, r = th.current_ratio;
  const groups = new Map<string, string[]>();
  for (const m of index.motors) { const k = `${m.vibration.watch_mms}|${m.vibration.act_mms}|${m.vibration.standard}`; groups.set(k, [...(groups.get(k) ?? []), m.id]); }
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>세 단계 <b>안전 / 경고 / 위험</b>. 모터 전체 상태는 모든 신호 중 가장 나쁜 등급이고, 원인 신호를 항상 함께 표시합니다.
        등급 하향은 임계값의 {Math.round(th.hysteresis_fraction * 100)} % 안쪽으로 들어와야 바뀌고(히스테리시스), 전류·진동·I₂/I₁·베어링 지표(kurtosis·고주파 배율)는 {th.persistence_s.current_ratio} s 이상 지속돼야 상향됩니다(돌입전류 무시).</p>
      <table className="grid">
        <thead><tr><th>신호</th><th><span className="sw" style={{ background: index.colors.SAFE }} />{index.icons.SAFE} 안전</th><th><span className="sw" style={{ background: index.colors.WARN }} />{index.icons.WARN} 경고</th><th><span className="sw" style={{ background: index.colors.DANGER }} />{index.icons.DANGER} 위험</th><th>근거 · 적용</th><th>쉬운 설명</th></tr></thead>
        <tbody>
          <tr><td>베어링 온도</td><td>&lt; {t.bearing.safe_below} °C</td><td>{t.bearing.safe_below}~{t.bearing.danger_from}</td><td>≥ {t.bearing.danger_from}</td><td>{t.bearing.note ?? "그리스 수명"} · 모터 공통</td>{ez("temp_bearing")}</tr>
          <tr><td>권선 온도</td><td>&lt; {t.winding.safe_below}</td><td>{t.winding.safe_below}~{t.winding.danger_from}</td><td>≥ {t.winding.danger_from}</td><td>{t.winding.note ?? "F종 절연"} · 모터 공통</td>{ez("temp_winding")}</tr>
          <tr><td>로터 온도</td><td>&lt; {t.rotor.safe_below}</td><td>{t.rotor.safe_below}~{t.rotor.danger_from}</td><td>≥ {t.rotor.danger_from}</td><td>{t.rotor.note ?? ""} 모터 공통</td>{ez("temp_rotor")}</tr>
          <tr><td>축·하우징 온도</td><td>&lt; {t.default.safe_below}</td><td>{t.default.safe_below}~{t.default.danger_from}</td><td>≥ {t.default.danger_from}</td><td>{t.default.note ?? ""} 모터 공통</td>{ez("temp_default")}</tr>
          <tr><td>전류 비율 r = I / I정격</td><td>{r.safe_low} ≤ r ≤ {r.safe_high}</td><td>{r.safe_high} &lt; r ≤ {r.danger_over} 또는 {r.danger_under} ≤ r &lt; {r.safe_low}</td><td>r &gt; {r.danger_over} 또는 r &lt; {r.danger_under}</td><td>I정격은 모터별 ({index.motors.map((m) => `${m.id} ${m.spec.rated_line_current_a} A`).join(", ")}) · 저전류는 결상 의심</td>{ez("current_ratio")}</tr>
          <tr><td>I₂/I₁</td><td>&lt; {th.i2i1.safe_below}</td><td>{th.i2i1.safe_below}~{th.i2i1.danger_from}</td><td>≥ {th.i2i1.danger_from}</td><td>{index.honesty.itsc_note}</td>{ez("i2i1")}</tr>
          {[...groups.entries()].map(([k, ids]) => { const v = index.motors.find((m) => m.id === ids[0])!.vibration; return (
            <tr key={k}><td>진동 속도 RMS<div className="dim">{v.standard}</div></td><td>&lt; {v.watch_mms} mm/s</td><td>{v.watch_mms}~{v.act_mms}{v.plan_mms < v.act_mms ? ` (${v.plan_mms} 부터 "정비 계획")` : ""}</td><td>≥ {v.act_mms}</td><td>{ids.join(" · ")}{v.note ? ` — ${v.note}` : ""}</td>{ez("vibration")}</tr>); })}
          <tr><td>베어링 kurtosis (주 지표)</td><td>&lt; {th.bearing.kurtosis.safe_below}</td><td>{th.bearing.kurtosis.safe_below}~{th.bearing.kurtosis.danger_from}</td><td>≥ {th.bearing.kurtosis.danger_from}</td><td>가속도 첨도, 모터 공통. 정상 ≈3, 소손 시 수십. 시뮬레이션은 결함별 등가값</td>{ez("bearing_kurtosis")}</tr>
          <tr><td>베어링 고주파 RMS 배율 (보조 지표)</td><td>&lt; {th.bearing.hf_ratio.safe_below}배</td><td>{th.bearing.hf_ratio.safe_below}~{th.bearing.hf_ratio.danger_from}배</td><td>≥ {th.bearing.hf_ratio.danger_from}배</td><td>1 kHz 이상 대역 RMS ÷ 모터별 정상 기준선 ({index.motors.map((m) => `${m.id} ${m.bearing_hf_baseline?.rms_g ?? "-"} g`).join(" · ")}). 베어링 종합 = 둘 중 나쁜 쪽. 포락선 BPFO/BPFI 는 판정 제외(결함 부위 추정 표시만)</td>{ez("bearing_hf_ratio")}</tr>
        </tbody>
      </table>
    </div>
  );
}

export function SpecTab({ index }: { index: FleetIndex }) {
  const ms = index.motors;
  const row = (label: string, f: (m: MotorInfo) => React.ReactNode) => <tr><td><b>{label}</b></td>{ms.map((m) => <td key={m.id}>{f(m)}</td>)}</tr>;
  return (
    <div>
      <div className="st-honesty-lines">{index.honesty.lines.map((l) => <span key={l}>• {l}</span>)}<span className="dim">{index.honesty.itsc_note}</span></div>
      <table className="grid">
        <thead><tr><th>항목</th>{ms.map((m) => <th key={m.id}>{m.id}</th>)}</tr></thead>
        <tbody>
          {row("모델", (m) => `${m.name.split(" — ")[0]} · 해석 기준 모터`)}
          {row("정격 출력", (m) => `${m.spec.rated_power_kw} kW`)}
          {row("극수 / 동기속도", (m) => `${m.spec.poles}극 / ${m.spec.sync_rpm} rpm`)}
          {row("정격 회전수", (m) => `${m.spec.rated_rpm} rpm (슬립 ${(m.derived.slip * 100).toFixed(1)} %)`)}
          {row("전압 · 결선", (m) => <>{m.spec.voltage_v} V {m.spec.frequency_hz} Hz · {connLabel(m.spec.connection)}{srcIcon(m, "connection")}</>)}
          {row("정격 선전류 / 상전류", (m) => <>{m.spec.rated_line_current_a} A{srcIcon(m, "rated_line_current_a")} / {m.spec.rated_phase_current_a} A{srcIcon(m, "rated_phase_current_a")}</>)}
          {row("효율 / 역률", (m) => <>{m.spec.efficiency}{srcIcon(m, "efficiency")} / {m.spec.power_factor}{srcIcon(m, "power_factor")}</>)}
          {row("프레임 · 외형 스케일", (m) => `${m.spec.frame} · ×${m.spec.geometry_scale}`)}
          {row("베어링 DE / NDE", (m) => `${m.spec.bearing_de} / ${m.spec.bearing_nde}`)}
          {row("BPFO / BPFI (정격 rpm)", (m) => `${m.derived.bpfo_hz} / ${m.derived.bpfi_hz} Hz`)}
          {row("절연 / 듀티", (m) => `${m.spec.insulation_class}종 / ${m.spec.duty}`)}
          {row("진동 규격", (m) => `${m.vibration.standard.split(" (")[0]} (${m.vibration.watch_mms}/${m.vibration.act_mms})`)}
          {row("정상 수렴 권선 온도 (연속)", (m) => `${m.steady_C.winding} °C`)}
          {row("출처", (m) => <>{m.spec.source === "nameplate" ? "명판값" : "카탈로그 (catalog)"}<SourceIcons motor={m} /></>)}
        </tbody>
      </table>
    </div>
  );
}

// 키별 출처 아이콘 (config/motors/<id>.yaml 의 {value, source, …} 래퍼): ✓ catalog·nameplate·measured / 🔴 assumed·estimated(현장 확인) / · representative
const SRC_ICON: Record<string, string> = { catalog: "✓", nameplate: "✓✓", measured: "✓✓", standard: "✓", reference_dataset: "·", assumed: "🔴", estimated: "🔴", calculated: "🔴", verify_on_site: "🔴", representative: "·" };
const SRC_LABEL: Record<string, string> = { catalog: "카탈로그", nameplate: "명판", measured: "실측", standard: "규격", reference_dataset: "참고 데이터셋", assumed: "가정 (현장 확인 필요)", estimated: "추정 (실물 확인 시 교체)", calculated: "계산", verify_on_site: "현장 확인", representative: "대표값" };
const FIELD_KO: Record<string, string> = { rated_power_kw: "정격 출력", poles: "극수", rated_rpm: "정격 회전수", voltage_v: "전압", frequency_hz: "주파수", rated_line_current_a: "정격 선전류", rated_phase_current_a: "정격 상전류", efficiency: "효율", power_factor: "역률", frame: "프레임", connection: "결선", insulation_class: "절연", duty: "듀티", bearing_de: "DE 베어링", bearing_nde: "NDE 베어링" };
export function connLabel(c: string): string { return c === "delta" ? "Δ결선" : c === "star" ? "Y결선" : c; }
function srcIcon(m: MotorInfo, key: string): React.ReactNode {
  const fs = m.spec_source?.[key];
  if (!fs) return null;
  const tip = `${SRC_LABEL[fs.source] ?? fs.source}${fs.doc ? ` · ${fs.doc}` : ""}${fs.note ? ` · ${fs.note}` : ""}${fs.verify_on_site ? " · verify_on_site" : ""}`;
  const icon = fs.verify_on_site ? SRC_ICON.verify_on_site : (SRC_ICON[fs.source] ?? "?");
  return <span className={"st-src st-src-" + fs.source} title={tip}>{icon}</span>;
}
function SourceIcons({ motor }: { motor: MotorInfo }) {
  const fs = motor.spec_source ?? {};
  const keys = Object.keys(fs);
  if (!keys.length) return null;
  const groups: Record<string, string[]> = {};
  for (const k of keys) (groups[fs[k].source] ??= []).push(k);
  const name = (k: string) => FIELD_KO[k] ?? k;
  const NL = String.fromCharCode(10);
  return <span className="dim st-src-list" title={"키별 출처 — config/motors/<id>.yaml" + NL + Object.entries(groups).map(([src, ks]) => `${SRC_ICON[src] ?? "?"} ${SRC_LABEL[src] ?? src}: ${ks.map(name).join(", ")}`).join(NL)}>
    {Object.entries(groups).map(([src, ks]) => <span key={src} className={"st-src st-src-" + src}>{SRC_ICON[src] ?? "?"} {SRC_LABEL[src] ?? src} {(SRC_ICON[src] === "🔴") ? ks.map(name).join("·") : ks.length}</span>)}
  </span>;
}
