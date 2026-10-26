import { useEffect } from "react";
import type { Mode } from "../data";
import type { LiveState } from "../live/feed";
import { AnalysisRef, type Extras } from "./AnalysisRef";
import type { FleetIndex, MotorSeries, PlainLabels } from "./data";

// export_status_data.py 가 붙인 케이스별 엔진 값(2026-10-26) → AnalysisRef 의 '지금 표시값'. 구 export(필드 없음)면 전부 null
export function extrasAt(s: MotorSeries | null, i: number): Extras | undefined {
  if (!s) return undefined;
  return { i2i1_fault: s.i2i1_fault?.[i] ?? null, i2_over_in: s.i2_over_in?.[i] ?? null, i_f_A: s.i_f_A?.[i] ?? null, p_loop_total_W: s.p_loop_total_W?.[i] ?? null,
    winding_dT_C: s.winding_dT_C?.[i] ?? null, note: s.extras_note ?? {} };
}
// 근거 서랍 (단순 보기 3층 "근거", 2026-10-26): ① 정직성 전문 ② 해석 근거 비교(시뮬값 있는 행만 기본) ③ 근거 사슬 ④ 한계 — 전부 AnalysisRef·index.honesty 의 기존 데이터.
// 출처 등급 색은 이 서랍 안에서만 쓴다.
export function EvidenceDrawer({ index, s, i, stepId, electricalCase, mode, live, isLive, sourceLabel, labels, onClose }: {
  index: FleetIndex; s: MotorSeries | null; i: number; stepId: string; electricalCase: string; mode: Mode; live: LiveState | null; isLive: boolean; sourceLabel: string; labels: PlainLabels; onClose: () => void;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    window.addEventListener("keydown", k, true);
    return () => window.removeEventListener("keydown", k, true);
  }, [onClose]);
  const extras = extrasAt(s, i);
  return (
    <div className="sv-drawer-bg" onClick={onClose}>
      <aside className="sv-drawer" onClick={(e) => e.stopPropagation()} aria-label="근거">
        <header><span>근거</span><span className="dim">{labels.notes.honesty_chip?.replace(" · 근거 보기 ›", "") ?? "시뮬레이션 추정값"}</span><span className="grow" /><button onClick={onClose}>닫기 Esc</button></header>
        <div className="body">
          <section>
            <h4>① 이 화면의 숫자는</h4>
            <b>{index.honesty.label}{isLive ? " · LIVE (Isaac Sim)" : ""}</b>
            <ul>{index.honesty.lines.map((l) => <li key={l}>{l}</li>)}</ul>
            <div className="dim">{index.honesty.itsc_note} · 데이터: {sourceLabel}</div>
          </section>
          <section>
            <AnalysisRef index={index} s={s} i={i} stepId={stepId} electricalCase={electricalCase} mode={mode} live={live} isLive={isLive}
              extras={extras} hideEmpty defaultOpen title="② 해석 근거 비교" traceTitle="③ 근거 사슬 — 표시량 → 엔진 → 파일(sha) → 해석 단계 → 등급" limitsTitle="④ 한계" />
          </section>
        </div>
      </aside>
    </div>
  );
}
