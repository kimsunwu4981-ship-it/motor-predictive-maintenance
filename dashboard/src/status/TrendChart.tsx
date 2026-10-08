import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT } from "../data";
import type { FleetIndex, GaugeSpec, Kind, MotorInfo, MotorSeries, Phase } from "./data";
import { PHASES } from "./data";

// 신호별 추세 차트 (TASK_다중모터 §7.1 ④): 선택 신호를 임계 구간 배경 위에 그린다. 장면 경계 띠, 현재 시각 커서, 클릭으로 이동.
// 전체 시계열을 그리고 커서로 현재를 표시한다 (상태 보드는 해설용이 아니라 감시용이라 미래를 숨기지 않는다).
export interface TrendSel { kind: Kind; component?: string }

export function TrendChart({ index, motor, series, sel, spec, t, onSeek }: {
  index: FleetIndex; motor: MotorInfo; series: MotorSeries; sel: TrendSel; spec: GaugeSpec; t: number; onSeek: (t: number) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const sc = index.scenarios[series.mode];

  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    type Area = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    const lines: { name: string; data: number[]; color: string }[] = [];
    const sig = index.signals[sel.kind];
    let yName = sig.label + (sig.unit ? ` (${sig.unit})` : "");
    if (sel.kind === "temperature") {
      const node = sel.component ?? "bearing_de";
      lines.push({ name: index.node_labels[node] ?? node, data: series.temperature_C[node], color: "#ffc93c" });
      yName = `${index.node_labels[node] ?? node} 온도 (°C)`;
    } else if (sel.kind === "current_ratio") {
      const cols: Record<Phase, string> = { A: "#ff5b3a", B: "#62d2ff", C: "#8fe3a8" };
      for (const p of PHASES) lines.push({ name: `${index.phase_labels[p]}상`, data: series.current_ratio[p], color: cols[p] });
      yName = "전류 / 정격 (×)";
    } else if (sel.kind === "i2i1") lines.push({ name: "I₂/I₁", data: series.i2i1, color: "#b78bff" });
    else if (sel.kind === "vibration") lines.push({ name: "진동 RMS", data: series.vibration_mms, color: "#62d2ff" });
    else if (sel.kind === "bearing_kurtosis") lines.push({ name: "베어링 kurtosis", data: series.bearing_kurtosis, color: "#e0c48a" });
    else lines.push({ name: "베어링 고주파 RMS 배율", data: series.bearing_hf_ratio, color: "#f0a06a" });
    const vmax = Math.max(...lines.flatMap((l) => l.data));
    const yMax = Math.max(spec.max, vmax * 1.08);
    const bands: Area[] = spec.segments.map((s) => [
      { yAxis: s.from, itemStyle: { color: index.colors[s.level], opacity: .12 },
        label: { show: true, formatter: `${index.labels_ko[s.level]}${s.label ? " " + s.label : ""}`, position: "insideTopLeft", color: fg, fontSize: 11 } },
      { yAxis: Math.min(s.to, yMax) }] as Area);
    const chapters: Area[] = sc.steps.map((s, i) => [{ xAxis: s.t_start, itemStyle: { color: i % 2 ? "rgba(128,128,128,.08)" : "rgba(128,128,128,0)" },
      label: { show: true, formatter: String(s.n), position: "insideTop", color: fg, fontSize: 10 } }, { xAxis: s.t_end }] as Area);
    return {
      animation: false,
      grid: { left: 54, right: 16, top: 22, bottom: 24 },
      tooltip: { trigger: "axis", valueFormatter: (v) => (typeof v === "number" ? (Math.abs(v) < 1 ? v.toFixed(3) : v.toFixed(2)) : String(v)) },
      legend: { show: lines.length > 1, top: 0, right: 10, textStyle: { color: fg, fontSize: 11 } },
      xAxis: { type: "value", min: 0, max: sc.total_duration_s, axisLabel: { color: fg, formatter: (v: number) => fmtT(v) }, splitLine: { show: false }, axisLine: { lineStyle: { color: line } } },
      yAxis: { type: "value", min: Math.min(spec.min, 0), max: yMax, name: yName, nameLocation: "end", nameGap: 4, nameTextStyle: { color: fg, align: "left", padding: [0, 0, 0, -44], fontSize: 11 }, axisLabel: { color: fg }, splitLine: { lineStyle: { color: line, opacity: .5 } } },
      series: [
        ...lines.map((l, n) => ({
          name: l.name, type: "line" as const, showSymbol: false, lineStyle: { width: 2, color: l.color }, itemStyle: { color: l.color },
          data: series.t.map((x, i) => [x, l.data[i]]),
          ...(n === 0 ? { markArea: { silent: true, data: [...bands, ...chapters] } } : {}),
        })),
        { name: "cursor", type: "line" as const, data: [], silent: true, tooltip: { show: false },
          markLine: { symbol: "none", animation: false, data: [{ xAxis: t }], lineStyle: { color: index.colors[series.status[0]] ?? "#fff", width: 2 }, label: { show: false } } },
      ],
    };
  }, [index, series, sel, spec, sc]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current);
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    c.getZr().on("click", (ev: { offsetX: number; offsetY: number }) => {
      const p = c.convertFromPixel({ seriesIndex: 0 }, [ev.offsetX, ev.offsetY]);
      if (p && Number.isFinite(p[0])) onSeek(p[0]);
    });
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, [onSeek]);
  useEffect(() => { chart.current?.setOption(base, true); }, [base]);
  useEffect(() => {
    const i = Math.max(0, Math.min(series.t.length - 1, series.t.findIndex((x) => x > t) < 0 ? series.t.length - 1 : series.t.findIndex((x) => x > t) - 1));
    chart.current?.setOption({ series: [{ name: "cursor", markLine: { data: [{ xAxis: t }], lineStyle: { color: index.colors[series.status[i]] } } }] });
  }, [t, series, index]);

  return <div ref={el} className="st-chart" title={`${motor.id} ${series.mode} — 클릭하면 그 시각으로 이동`} />;
}
