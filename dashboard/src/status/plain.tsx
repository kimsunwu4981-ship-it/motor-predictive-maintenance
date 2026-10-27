import { useMemo } from "react";
import type { Mode } from "../data";
import { plainOf, tempBand, type FleetIndex, type Kind, type Level, type MotorInfo, type MotorSeries, type Phase, type PlainLabel, type PlainLabels } from "./data";

// 쉬운 말 보조 (단순 보기 §1b → 레이아웃 A 공용, 2026-10-27): 본문 용어 치환(<abbr> 원문), 모터 라벨, 임계값 문장, 주 신호(원인) 고르기.

export function Plain({ text, labels }: { text: string; labels: PlainLabels }) {
  const parts = useMemo(() => {
    let out: (string | { to: string; tip: string })[] = [text];
    for (const r of labels.replace) {
      const next: typeof out = [];
      for (const p of out) {
        if (typeof p !== "string" || !p.includes(r.from)) { next.push(p); continue; }
        const segs = p.split(r.from);
        segs.forEach((sg, n) => { if (sg) next.push(sg); if (n < segs.length - 1) next.push({ to: r.to, tip: r.tip ?? r.from }); });
      }
      out = next;
    }
    return out;
  }, [text, labels]);
  return <>{parts.map((p, n) => (typeof p === "string" ? <span key={n}>{p}</span> : <abbr key={n} title={p.tip}>{p.to}</abbr>))}</>;
}
export function motorLabel(motor: MotorInfo, labels: PlainLabels): string {
  return `${motor.name.split(" — ")[0]} · ${motor.spec.rated_power_kw} kW ${motor.spec.poles}극 · ${labels.notes.motor_suffix ?? "해석 기준 모터"}`;
}
export function fmtVal(kind: string, v: number): string {
  if (kind === "i2i1") return v.toFixed(3);
  if (kind === "current_ratio") return `${v.toFixed(2)}×`;
  if (kind === "temperature") return `${v.toFixed(1)} °C`;
  if (kind === "vibration") return `${v.toFixed(1)} mm/s`;
  if (kind === "bearing_hf_ratio") return `${v.toFixed(2)}배`;
  return v.toFixed(1);
}
export function thresholdText(index: FleetIndex, motor: MotorInfo, kind: Kind, comp?: string): string {
  const th = index.thresholds;
  if (kind === "i2i1") return `안전 <${th.i2i1.safe_below} · 위험 ≥${th.i2i1.danger_from}`;
  if (kind === "current_ratio") { const r = th.current_ratio; return `안전 ${r.safe_low}~${r.safe_high}× · 위험 >${r.danger_over}× 또는 <${r.danger_under}×`; }
  if (kind === "temperature") { const b = tempBand(index, comp ?? "bearing_de"); return `안전 <${b.safe_below} °C · 위험 ≥${b.danger_from} °C`; }
  if (kind === "vibration") return `안전 <${motor.vibration.watch_mms} · 위험 ≥${motor.vibration.act_mms} mm/s`;
  if (kind === "bearing_kurtosis") return `안전 <${th.bearing.kurtosis.safe_below} · 위험 ≥${th.bearing.kurtosis.danger_from}`;
  return `안전 <${th.bearing.hf_ratio.safe_below}배 · 위험 ≥${th.bearing.hf_ratio.danger_from}배`;
}
export function nameOf(index: FleetIndex, labels: PlainLabels, kind: Kind, comp?: string): PlainLabel {
  const base = plainOf(labels, kind, index.signals[kind]?.label ?? kind);
  if (kind === "temperature" && comp) return { ...base, plain: `${index.node_labels[comp] ?? comp} ${base.plain}` };
  if (kind === "current_ratio" && comp && index.phase_labels[comp as Phase]) return { ...base, plain: `${index.phase_labels[comp as Phase]}상 ${base.plain}` };
  return base;
}
export interface Primary { kind: Kind; comp?: string; value: number; level: Level; name: PlainLabel; threshold: string; persistence: number }
export function primaryOf(index: FleetIndex, motor: MotorInfo, s: MotorSeries, i: number, mode: Mode, labels: PlainLabels): Primary {
  const lv = s.status[i]; const ck = s.cause_signal[i] as Kind | "-";
  if (lv !== "SAFE" && ck !== "-") {
    const comp = s.cause_component[i] || undefined;
    return { kind: ck, comp, value: s.cause_value[i], level: lv, name: nameOf(index, labels, ck, comp),
      threshold: (s.cause_threshold[i] || thresholdText(index, motor, ck, comp)).replace(/^\[|\]$/g, "").replace(/ \/ /g, " · "), persistence: index.thresholds.persistence_s[ck] ?? 0 };
  }
  const kind: Kind = mode === "electrical" ? "i2i1" : "temperature"; const comp = mode === "electrical" ? undefined : "bearing_de";
  const value = kind === "i2i1" ? s.i2i1[i] : s.temperature_C.bearing_de[i];
  return { kind, comp, value, level: "SAFE", name: nameOf(index, labels, kind, comp), threshold: thresholdText(index, motor, kind, comp), persistence: index.thresholds.persistence_s[kind] ?? 0 };
}
