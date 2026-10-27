// live/livedata.ts — 수신 버퍼(LiveBuffer) → 상태 보드 데이터 (레이아웃 A/패널 Q1, 전기 전용 2026-10-27).
//   liveSteps(buf, staticSteps) → 관찰된 장면 전환 Step[]   ·   toMotorSeries(buf, index) → MotorSeries (판정은 state.status 그대로)
// 기계·전기 해설 화면용 변환(toMechData/toElecData/liveEvents/useLivePlayback)은 src/_legacy/live/livedata_full.ts.
import type { Step } from "../data";
import type { FleetIndex, Level, MotorSeries } from "../status/data";
import type { LiveBuffer } from "./session";
import type { LiveState } from "./feed";

const RANK: Record<Level, number> = { SAFE: 0, WARN: 1, DANGER: 2 };
void RANK;
// state.mode 는 payload 필드로 유지한다(값은 electrical 고정) — 보드는 전기 시계열만 만든다
export function pageMode(m: LiveState["mode"]): "mechanical" | "electrical" { return m === "electrical" ? "electrical" : "mechanical"; }

export function liveSteps(buf: LiveBuffer, staticSteps: Step[]): Step[] {
  const out: Step[] = [];
  const byId = new Map(staticSteps.map((s) => [s.id, s]));
  for (let k = 0; k < buf.states.length; k++) {
    const s = buf.states[k];
    const last = out[out.length - 1];
    if (last && last.id === s.step) { last.t_end = s.t_session_s; continue; }
    const st = byId.get(s.step);
    out.push({
      n: st?.n ?? 0, id: s.step, label: st?.label ?? (s.step === "manual" ? "수동 조작 (패널)" : s.step), subtitle: st?.subtitle ?? "", source: st?.source ?? "Isaac Sim 라이브",
      t_start: s.t_session_s, t_end: s.t_session_s, video_start: 0, video_end: 0,
      electrical_case: s.case, faults: s.faults, load: s.load, time_scale: s.time_scale, highlight: st?.highlight ?? false, clip: null,
    });
  }
  if (out.length) out[out.length - 1].t_end = Math.max(out[out.length - 1].t_end, buf.tEnd + 1e-3);
  return out;
}

// ---- 상태 보드 시계열
export function toMotorSeries(buf: LiveBuffer, index: FleetIndex, template: MotorSeries | null): MotorSeries {
  const S = buf.states;
  const col = <T,>(f: (s: LiveState) => T) => S.map(f);
  const nodes = Object.keys(S[0]?.T ?? {});
  const kinds = Object.keys(index.signals);
  const first = S[0];
  const m = index.motors.find((x) => x.id === first?.motor_id);
  const rated = first?.rated_line_A || m?.spec.rated_line_current_a || 1;
  return {
    motor: first?.motor_id ?? "", mode: pageMode(first?.mode ?? "mechanical"), n: S.length,
    source: `Isaac Sim 라이브 ${first?.host?.ws ?? ""} · 판정 engine/thresholds.py (Isaac 쪽)`,
    t: buf.t.slice(), step: col((s) => s.step), time_scale: col((s) => s.time_scale),
    temperature_C: Object.fromEntries(nodes.map((k) => [k, col((s) => s.T[k])])),
    current_rms_A: { A: col((s) => s.Ia_rms), B: col((s) => s.Ib_rms), C: col((s) => s.Ic_rms) },
    current_ratio: { A: col((s) => s.Ia_rms / rated), B: col((s) => s.Ib_rms / rated), C: col((s) => s.Ic_rms / rated) },
    i2i1: col((s) => s.i2_over_i1), vibration_mms: col((s) => s.vibration_mms),
    bearing_kurtosis: col((s) => s.bearing_kurtosis), bearing_hf_ratio: col((s) => s.bearing_hf_ratio), bearing_site_hint: null,
    status: col((s) => s.status.status), cause_signal: col((s) => s.status.cause_signal), cause_component: col((s) => s.status.cause_component),
    cause_value: col((s) => s.status.value), cause_threshold: col((s) => s.status.threshold),
    levels: { ...Object.fromEntries(kinds.map((k) => [k, col((s) => s.status.levels[k] ?? "SAFE")])), bearing: col((s) => s.status.levels.bearing ?? "SAFE") } as MotorSeries["levels"],
    scene_values: template?.scene_values ?? {},
    // 레이아웃 A (2026-10-27): 라이브 state 의 케이스별 성분·파형 → case_signals, 근거 서랍 값(LUT 결함분·I₂/I_n·I_f·P_loop) — 전부 Isaac 쪽 엔진 값 그대로
    case_signals: Object.fromEntries(S.filter((s) => s.waveform_last_2cycles && s.sym_components_A).map((s) => [s.case, { ...s.sym_components_A!, waveform: s.waveform_last_2cycles! }])),
    i2i1_fault: col((s) => s.electrical_source?.lut_i2_over_i1 ?? null), i2_over_in: col((s) => s.i2_over_in ?? null),
    i_f_A: col((s) => s.electrical_source?.i_f_A ?? null), p_loop_total_W: col((s) => s.p_loop_total_W ?? null), winding_dT_C: null,
    extras_note: { i2i1_fault: "LUT 결함분 (Isaac electrical_source.lut_i2_over_i1)", i2_over_in: "I₂/I_n (Isaac state)", i_f_A: "단락 루프 전류 (Isaac electrical_source)", p_loop_total_W: "단락 루프 총손실 (Isaac state)", winding_dT_C: "라이브 전기 모드: 열 모델 미실행" },
  };
}

