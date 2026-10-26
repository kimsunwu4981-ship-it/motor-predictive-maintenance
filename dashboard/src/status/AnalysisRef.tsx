import { useEffect, useMemo, useState } from "react";
import { getJson } from "../live/load";
import type { LiveState } from "../live/feed";
import type { FleetIndex, MotorSeries } from "./data";
import type { Mode } from "../data";

// V6 (2026-10-21): "해석 근거 비교" 패널 — 지금 보이는 숫자 | Maxwell/해석 기준값 | 차이 % | 출처 배지.
// 숫자는 전부 data/electrical/analysis_reference.json(tools/verify/build_analysis_reference.py — 해석 파일에서만, sha 포함) 과 재생 중인 시계열/라이브 state 에서 온다.
// 허용은 tools/verify/sim_vs_analysis.py V2 표와 같다(I₂/I₁ ±1 %, I_f ±1 %, 손실 ±2 %, ΔT ±5 %). 기계 시나리오는 "Maxwell 근거 없음".

type Src = { file?: string; sha256?: string; grade?: string; grade_key?: string; note?: string };
export interface AnalysisReference {
  generated: string; motor: string; I_n_A: number; inherent_i2i1: number;
  thresholds: { i2i1_warn: number; i2i1_danger: number; persistence_s: number };
  lut: { dt_file: string; dt_sha256: string; sha_match: boolean; grade: string; status: string; fem_verified: boolean | string };
  grades: Record<string, string>;
  inputs: Record<string, { path: string; sha256: string }>;
  scenarios: Record<string, {
    turns: number; R_f_ohm: number | null; load: number; mccm_case: string | null;
    i2_over_i1_fault: { value: number; angle_deg_vs_i1: number } & Src;
    i2_over_i1_composite: { inherent: number; range: number[]; expected_by_angle: Record<string, number> };
    i2_over_in: { lut: number; sim_expected: number; note: string } & Src;
    unbalance_max_dev_pct: { lut: number; sim_expected: number; sim_expected_I_abc_A: number[] } & Src;
    i_f_A: { mccm: number | null; lut: number; fem_corrected?: { I_f_A: number; dev_vs_mccm_pct: number } | null } & Src;
    p_loop_total_W: { lut: number; mccm: number | null; formula: string } & Src;
    winding_dT_steady_C: { model: Record<string, number>; tolerance_pct: number; grade: string; note: string };
    expected_judgment: { i2i1_level: string; current_ratio_levels: string[]; overall_expected: string; detection_delay_expected_s: number | null };
    z2_uncertainty: { i2_uncertainty_pct: number; sentence: string };
  }>;
  rated_point: Record<string, Record<string, unknown>>;
  starting: Record<string, Record<string, unknown>>;
  equivalent_circuit: Record<string, Record<string, unknown>>;
  limitations: string[]; mechanical_note: string;
}
interface TraceDoc { rows: { display: string; engine: string; inputs: string[]; analysis_chain: string; grade: string }[]; limitations: string[] }

let refCache: Promise<AnalysisReference | null> | null = null;
let traceCache: Promise<TraceDoc | null> | null = null;
function loadRef() { if (!refCache) refCache = getJson<AnalysisReference>("data/electrical/analysis_reference.json").catch(() => null); return refCache; }
function loadTrace() { if (!traceCache) traceCache = getJson<TraceDoc>("data/verification/traceability.json").catch(() => null); return traceCache; }

const GRADE_CLS: Record<string, string> = { catalog: "g-cat", rmxprt: "g-rmx", mccm: "g-eq", lut: "g-eq", fem2d: "g-fem", standard: "g-std", assumed: "g-asm", model: "g-mod", dataset: "g-ds" };
const GRADE_SHORT: Record<string, string> = { catalog: "카탈로그", rmxprt: "RMxprt", mccm: "등가회로", lut: "등가회로 LUT", fem2d: "2D FEM", standard: "표준", assumed: "가정", model: "열 모델", dataset: "참고 데이터셋" };

interface Row { item: string; shown: number | string | null; ref: number | string | null; tol: number | null; unit: string; src: Src | { grade_key: string; note?: string }; reason?: string; kind?: "rel" | "match" }
// 단순 보기 근거 서랍(2026-10-26): export_status_data.py 가 붙인 케이스별 엔진 값 — 라이브가 아닐 때 '지금 표시값' 을 채운다 (값 계산은 엔진 그대로)
export interface Extras { i2i1_fault: number | null; i2_over_in: number | null; i_f_A: number | null; p_loop_total_W: number | null; winding_dT_C: number | null; note: Record<string, string> }

function fmt(v: number | string | null | undefined, n = 4): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(n);
  return String(v);
}
function devPct(a: number | string | null, b: number | string | null): number | null {
  if (typeof a !== "number" || typeof b !== "number" || b === 0) return null;
  return (a / b - 1) * 100;
}

export function AnalysisRef({ s, i, stepId, electricalCase, mode, live, isLive, extras, hideEmpty = false, defaultOpen = false, title = "④ 해석 근거 비교", traceTitle, limitsTitle }: {
  index: FleetIndex; s: MotorSeries | null; i: number; stepId: string; electricalCase: string; mode: Mode; live: LiveState | null; isLive: boolean;
  extras?: Extras;               // export 추가 필드 (케이스별 엔진 값) — 없으면 기존처럼 라이브 state 에서만
  hideEmpty?: boolean;           // 표시값이 없는(—) 행은 접어 둔다 ("표시 안 함 n행 ▾")
  defaultOpen?: boolean;         // 근거 사슬·한계를 펼친 채 시작 (서랍)
  title?: string; traceTitle?: string; limitsTitle?: string;
}) {
  const [ref, setRef] = useState<AnalysisReference | null>(null);
  const [trace, setTrace] = useState<TraceDoc | null>(null);
  const [open, setOpen] = useState(defaultOpen);
  const [basis, setBasis] = useState(false);
  const [showEmpty, setShowEmpty] = useState(false);
  useEffect(() => { loadRef().then(setRef); }, []);
  useEffect(() => { if (open && !trace) loadTrace().then(setTrace); }, [open, trace]);

  const rows: Row[] = useMemo(() => {
    if (!ref || mode !== "electrical" || !s) return [];
    const R = ref.scenarios[electricalCase];
    if (!R) return [];
    const shownI2 = s.i2i1[i];
    const exp0 = R.i2_over_i1_composite.expected_by_angle.angle_0;
    const [lo, hi] = R.i2_over_i1_composite.range;
    const tStart = s.t[i] - (s.t.find((_, k) => s.step[k] === stepId) ?? s.t[i]);
    const transient = tStart < ref.thresholds.persistence_s;
    const liveSrc = live?.electrical_source as (Record<string, unknown> | undefined);
    const liveIf = liveSrc && typeof liveSrc.i_f_A === "number" ? (liveSrc.i_f_A as number) : null;
    const ex = !isLive ? extras : undefined;                                                           // 재생 모드: export 가 붙인 케이스별 엔진 값
    const exNote = (k: string) => (ex?.note?.[k] ? ` · ${ex.note[k]}` : "");
    const dTshown = mode === "electrical" && !isLive ? (ex?.winding_dT_C ?? null) : (s.temperature_C.winding ? s.temperature_C.winding[i] - 25 : null);   // 전기 모드 녹화는 열 적분 없음 → export 값(없으면 회색)
    const out: Row[] = [
      { item: "I₂/I₁ (합성 = 결함분 + 고유 비대칭)", shown: shownI2, ref: exp0, tol: 0.01, unit: "", src: R.i2_over_i1_fault,
        reason: shownI2 < lo || shownI2 > hi ? `고유 비대칭 각도에 따른 범위 ${lo.toFixed(4)}~${hi.toFixed(4)} 밖` : transient ? "과도 구간 — 판정 지속 3 s 전" : undefined },
      { item: "I₂/I₁ 결함분 (LUT r, 고유 비대칭 제외)", shown: ex?.i2i1_fault ?? null, ref: R.i2_over_i1_fault.value, tol: 0.01, unit: "", src: R.i2_over_i1_fault,
        reason: ex?.i2i1_fault != null ? `엔진 LUT 조회값${exNote("i2i1_fault")}` : "표시값은 합성값뿐 — 결함분은 로그의 I₂ 위상으로 분리(검증 보고서)" },
      { item: "I₂/I_n (부하 무관 보조)", shown: isLive && live?.i2_over_in != null ? live.i2_over_in : (ex?.i2_over_in ?? null), ref: R.i2_over_in.sim_expected, tol: 0.01, unit: "", src: R.i2_over_in,
        reason: `LUT 자체 I₂/I_n ${R.i2_over_in.lut.toFixed(4)} (LUT I₁ 기준) — 시뮬은 I₁ 을 정격×부하로 고정 (규약 차이)${exNote("i2_over_in")}` },
      { item: "단락 루프 전류 I_f", shown: liveIf ?? ex?.i_f_A ?? null, ref: R.i_f_A.mccm ?? R.i_f_A.lut, tol: 0.01, unit: "A", src: R.i_f_A,
        reason: R.i_f_A.fem_corrected ? `2D FEM(F1 보정) ${R.i_f_A.fem_corrected.I_f_A.toFixed(2)} A (MCCM 대비 ${R.i_f_A.fem_corrected.dev_vs_mccm_pct.toFixed(1)} %)${exNote("i_f_A")}` : (isLive ? undefined : `단락 케이스에서만${exNote("i_f_A")}`) },
      { item: "단락 루프 총손실 P_loop", shown: isLive && live?.p_loop_total_W != null ? live.p_loop_total_W : (ex?.p_loop_total_W ?? null), ref: R.p_loop_total_W.lut, tol: 0.02, unit: "W", src: R.p_loop_total_W,
        reason: isLive ? undefined : `권선 노드 추가 손실${exNote("p_loop_total_W")}` },
      { item: "권선 ΔT 정상 상태 (열 모델 역산)", shown: dTshown, ref: R.winding_dT_steady_C.model.winding, tol: 0.05, unit: "°C", src: { grade_key: "model", note: R.winding_dT_steady_C.note },
        reason: mode === "electrical" && !isLive ? `전기 모드는 열 적분 없음(온도 상수) — 통합 모드 검증 로그 참조${exNote("winding_dT_C")}` : "주입 후 정상 상태 도달 전이면 작다" },
      { item: "판정 (예상 vs 현재)", shown: s.status[i], ref: R.expected_judgment.overall_expected, tol: null, unit: "", src: { grade_key: "dataset", note: "thresholds.yaml 0.05/0.10, 지속 3 s, 시뮬레이션 정책(provisional 포함)" }, kind: "match",
        reason: transient ? "주입 후 3 s 지속 전" : undefined },
    ];
    return out;
  }, [ref, mode, s, i, stepId, electricalCase, live, isLive, extras]);

  if (!ref) return <div className="st-aref muted">해석 근거 비교: analysis_reference.json 없음 (tools/verify/build_analysis_reference.py)</div>;
  if (mode !== "electrical") {
    return <div className="st-aref"><div className="st-aref-h">{title}</div><div className="st-aref-none">{ref.mechanical_note}</div></div>;
  }
  const visibleRows = hideEmpty && !showEmpty ? rows.filter((r) => r.shown !== null) : rows;
  const hiddenRows = hideEmpty && !showEmpty ? rows.filter((r) => r.shown === null) : [];
  const R = ref.scenarios[electricalCase];
  const exportCsv = () => {
    const lines = ["item,scenario,sim,ref,tolerance,dev_pct,pass,unit,note,source"];
    for (const r of rows) {
      const d = r.kind === "match" ? null : devPct(r.shown, r.ref);
      const ok = r.kind === "match" ? r.shown === r.ref : (d !== null && r.tol !== null && Math.abs(d) <= r.tol * 100);
      lines.push([r.item, electricalCase, fmt(r.shown), fmt(r.ref), r.tol ?? "", d === null ? "" : d.toFixed(3), r.shown === null ? "" : ok, r.unit, (r.reason ?? "").replace(/,/g, ";"), GRADE_SHORT[(r.src as Src).grade_key ?? ""] ?? ""].map((x) => `"${String(x)}"`).join(","));
    }
    const ts = new Date(); const pad = (n: number) => String(n).padStart(2, "0");
    const name = `export_${ts.getFullYear()}${pad(ts.getMonth() + 1)}${pad(ts.getDate())}_${pad(ts.getHours())}${pad(ts.getMinutes())}${pad(ts.getSeconds())}.csv`;
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); URL.revokeObjectURL(a.href);
  };
  return (
    <div className="st-aref">
      <div className="st-aref-h">{title} <span className="dim">{electricalCase}{R ? ` · ${R.turns}턴 · R_f ${R.R_f_ohm ?? "—"} Ω · 부하 ${R.load}` : " · LUT 밖(legacy 해석식) — 해석 기준 없음"}</span>
        <span className="grow" />
        <button onClick={() => setBasis(!basis)} title="정격점·기동·등가회로 상수 — 카탈로그 / RMxprt / 2D FEM / IEC 허용차">{basis ? "▾" : "▸"} 모터 모델 근거</button>
        {!defaultOpen && <button onClick={() => setOpen(!open)} title="표시량 → 엔진 → 파일(sha) → 해석 단계 → 등급 + 한계">{open ? "▾" : "▸"} 근거 보기</button>}
        <button onClick={exportCsv} disabled={!R} title="현재 시각의 비교표를 CSV 로 (V2 형식, export_<시각>.csv — 브라우저 다운로드; Isaac 쪽 logs/verify/export_*.csv 는 sim_vs_analysis.py 가 만든다)">비교 내보내기</button>
      </div>
      {R && (
        <table className="st-aref-t">
          <thead><tr><th>항목</th><th>지금 표시값</th><th>해석 기준값</th><th>차이</th><th>출처</th></tr></thead>
          <tbody>
            {visibleRows.map((r) => {
              const d = r.kind === "match" ? null : devPct(r.shown, r.ref);
              const ok = r.shown === null ? null : r.kind === "match" ? r.shown === r.ref : (d !== null && r.tol !== null && Math.abs(d) <= r.tol * 100);
              const gk = (r.src as Src).grade_key ?? "";
              const tip = [`${ref.grades[gk] ?? gk}`, (r.src as Src).file ? `${(r.src as Src).file} (sha ${(r.src as Src).sha256})` : "", (r.src as Src).note ?? "", r.reason ?? "", r.tol !== null ? `허용 ±${(r.tol * 100).toFixed(0)} %` : ""].filter(Boolean).join("\n");
              return (
                <tr key={r.item} className={ok === null ? "na" : ok ? "ok" : "ng"} title={tip}>
                  <td>{r.item}</td>
                  <td className="num">{fmt(r.shown)}{r.shown !== null && r.unit ? ` ${r.unit}` : ""}</td>
                  <td className="num">{fmt(r.ref)}{r.unit ? ` ${r.unit}` : ""}</td>
                  <td className="num">{d === null ? (r.kind === "match" && r.shown !== null ? (ok ? "일치" : "불일치") : "—") : <b>{d >= 0 ? "+" : ""}{d.toFixed(2)} %</b>}{r.reason && ok === false ? <span className="why" title={r.reason}> ⓘ</span> : null}</td>
                  <td><span className={"g " + (GRADE_CLS[gk] ?? "")}>{GRADE_SHORT[gk] ?? gk}</span></td>
                </tr>
              );
            })}
            {hiddenRows.length > 0 && (
              <tr className="more" onClick={() => setShowEmpty(true)} title={hiddenRows.map((r) => `${r.item}: ${r.reason ?? "표시값 없음"}`).join("\n")}>
                <td colSpan={5}>표시 안 함 {hiddenRows.length}행 ▾ <span className="dim">(이 모드에서 시뮬값이 없는 항목 — 사유는 툴팁)</span></td>
              </tr>
            )}
            {hideEmpty && showEmpty && rows.some((r) => r.shown === null) && (
              <tr className="more" onClick={() => setShowEmpty(false)}><td colSpan={5}>표시값 없는 행 접기 ▴</td></tr>
            )}
          </tbody>
        </table>
      )}
      {R && <div className="dim st-aref-note">초록 = 허용 안 · 주황 = 밖(ⓘ 사유) · 회색 = 표시값 없음. LUT sha {ref.lut.sha_match ? "일치" : "불일치"} · {ref.lut.grade} · {ref.lut.status} · Z₂ 불확실성 +{R.z2_uncertainty.i2_uncertainty_pct.toFixed(0)} %</div>}
      {basis && (
        <div className="st-aref-basis">
          <div className="sub-h">모터 모델 근거 — 정격점·기동·등가회로 (값·출처는 analysis_reference.json)</div>
          <table className="st-aref-t small"><thead><tr><th>항목</th><th>카탈로그</th><th>RMxprt v2m2</th><th>2D FEM lite</th><th>IEC 허용차</th></tr></thead>
            <tbody>
              {(ref.rated_point.iec_tolerance.table as { item: string; catalog: unknown; rmxprt_v2m2: unknown; fem_lite: unknown; iec_tolerance: string }[]).map((r) => (
                <tr key={r.item}><td>{r.item}</td><td className="num">{fmt(r.catalog as number)}</td><td className="num">{fmt(r.rmxprt_v2m2 as number)}</td><td className="num">{fmt(r.fem_lite as number)}</td><td>{r.iec_tolerance}</td></tr>))}
            </tbody></table>
          <table className="st-aref-t small"><thead><tr><th>등가회로</th><th>RMxprt</th><th>2D FEM / 보정</th><th>비고</th></tr></thead>
            <tbody>
              <tr><td>R1 [Ω] 20 / 95 °C</td><td className="num">{fmt(ref.equivalent_circuit.R1_ohm["20C"] as number)} / {fmt(ref.equivalent_circuit.R1_ohm["95C"] as number)}</td><td>—</td><td>온도 스윕</td></tr>
              <tr><td>R2′ [Ω]</td><td className="num">{fmt(ref.equivalent_circuit.R2p_ohm.rmxprt_95C as number)}</td><td className="num">{fmt(ref.equivalent_circuit.R2p_ohm.mccm_hot_calibrated as number)} (MCCM 보정)</td><td>기계출력 맞춤</td></tr>
              <tr><td>X1 / X2′ [Ω]</td><td className="num">{fmt(ref.equivalent_circuit.X1_ohm.rmxprt as number)} / {fmt(ref.equivalent_circuit.X2p_ohm.rmxprt as number)}</td><td>—</td><td></td></tr>
              <tr><td>Xm [Ω]</td><td className="num">{fmt(ref.equivalent_circuit.Xm_ohm.rmxprt as number)}</td><td className="num">{fmt(ref.equivalent_circuit.Xm_ohm.fem_X_total_at_rated_Im as number)} (X_total, 자화곡선 k=1)</td><td></td></tr>
              <tr><td>Z₂ [Ω]</td><td className="num">{fmt(ref.equivalent_circuit.Z2_ohm.anchor_catalog as number)} (앵커)</td><td className="num">{fmt(ref.equivalent_circuit.Z2_ohm.fem_negseq as number)} / {fmt(ref.equivalent_circuit.Z2_ohm.fem_corrected as number)}</td><td>LUT I₂ 불확실성 +20 %</td></tr>
              <tr><td>기동 I_st / T_st [×]</td><td className="num">{fmt(ref.starting.catalog.I_st_ratio as number, 2)} / {fmt(ref.starting.catalog.T_st_ratio as number, 2)}</td><td className="num">{fmt(ref.starting.rmxprt_v2m2.I_st_ratio as number, 2)} / {fmt(ref.starting.rmxprt_v2m2.T_st_ratio as number, 2)} → FEM+F2 {fmt(ref.starting.fem_corrected.I_st_ratio as number, 2)} / {fmt(ref.starting.fem_corrected.T_st_ratio as number, 2)}</td><td>스큐 보정</td></tr>
            </tbody></table>
        </div>
      )}
      {open && (
        <div className="st-aref-trace">
          <div className="sub-h">{traceTitle ?? "근거 사슬 — 표시량 → 엔진 → 파일(sha) → 해석 단계 → 등급"} <span className="dim">(docs/verification/traceability.json)</span></div>
          {trace ? (
            <table className="st-aref-t small"><thead><tr><th>표시량</th><th>엔진</th><th>입력(sha)</th><th>해석 단계</th><th>등급</th></tr></thead>
              <tbody>{trace.rows.map((r) => <tr key={r.display}><td>{r.display}</td><td><code>{r.engine}</code></td><td>{r.inputs.join(" · ")}</td><td>{r.analysis_chain}</td><td><b>{r.grade}</b></td></tr>)}</tbody></table>
          ) : <div className="muted">traceability.json 없음 — tools/verify/traceability.py</div>}
          <div className="sub-h">{limitsTitle ?? "한계"}</div>
          <ul>{(trace?.limitations ?? ref.limitations).map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
