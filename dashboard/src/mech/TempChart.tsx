import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT } from "../data";
import { usePlayback } from "../state/playback";
import type { MechData } from "./data";

// 부품별 온도 차트 (TASK 5.1). 주목 부품만 임계 구간 배경 띠를 깔고 굵게, 나머지는 흐리게.
// (다른 부품은 임계값이 달라 공통 띠를 깔면 틀린 그림이 된다.)
// M2: 레이아웃·주목 강조. M3 에서 미래 데이터 숨김·임계 통과 마커·등급별 선색을 더한다.
const PALETTE: Record<string, string> = {
  bearing_de: "#ff5b3a", bearing_nde: "#ff9c7a", winding: "#ffc93c", rotor: "#62d2ff", shaft: "#b78bff",
  frame: "#8fe3a8", stator_core: "#e0c48a", endshield_de: "#c9a0ff", endshield_nde: "#a6d8ff",
};
const DEFAULT_ON = ["bearing_de", "bearing_nde", "winding", "rotor", "shaft", "frame"];

export function TempChart({ data, focus, shown, onToggle }: {
  data: MechData; focus: string; shown: Set<string>; onToggle: (k: string) => void;
}) {
  const { t, seek } = usePlayback();
  const th = data.thresholds, ts = data.timeseries, sc = data.scenarios;
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const lt = sc.lead_time;

  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    const p = th.thermal.parts.find((q) => q.key === focus) ?? th.thermal.parts[0];
    const parts = th.thermal.parts.filter((q) => shown.has(q.key) || q.key === focus);
    const maxT = Math.ceil((Math.max(p.warning_max_C + 30, ...parts.map((q) => Math.max(...ts.temperature_C[q.key]))) + 5) / 10) * 10;
    type Area = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    type Line = NonNullable<echarts.MarkLineComponentOption["data"]>[number];
    const band = (lo: number, hi: number, color: string, text: string): Area => [
      { yAxis: lo, itemStyle: { color, opacity: .13 }, label: { show: true, formatter: text, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: hi }] as Area;
    const c = th.thermal.stage_colors;
    const bands: Area[] = [
      band(0, p.normal_max_C, c.normal, `${p.label} 정상 ≤ ${p.normal_max_C} °C`),
      band(p.normal_max_C, p.caution_max_C, c.caution, `주의 ≤ ${p.caution_max_C}`),
      band(p.caution_max_C, p.warning_max_C, c.warning, `경고 ≤ ${p.warning_max_C}`),
      band(p.warning_max_C, maxT, c.danger, `위험 > ${p.warning_max_C} °C`),
    ];
    const chapters: Area[] = sc.steps.map((s, i) => [{ xAxis: s.t_start, itemStyle: { color: i % 2 ? "rgba(128,128,128,.07)" : "rgba(128,128,128,0)" }, label: { show: false } }, { xAxis: s.t_end }] as Area);
    const lead: Line[] = [];
    if (lt.alarm_t != null) lead.push({ xAxis: lt.alarm_t, lineStyle: { color: "#ffaa33", type: "dashed", width: 2 },
      label: { formatter: "▲ VIGENT 조기 경보", position: "end", align: "left", offset: [4, -2], color: "#ffaa33", fontWeight: "bold", fontSize: 12 } });
    if (lt.danger_t != null) lead.push({ xAxis: lt.danger_t, lineStyle: { color: c.danger, width: 2 },
      label: { formatter: `■ 위험 도달 (리드 타임 화면 ${lt.lead_s} s = 시뮬 약 ${((lt.lead_sim_s ?? 0) / 60).toFixed(1)} 분)`, position: "end", align: "left", offset: [4, 14], color: c.danger, fontSize: 12 } });
    return {
      animation: false, backgroundColor: "transparent",
      tooltip: { trigger: "axis", valueFormatter: (v) => `${Number(v).toFixed(1)} °C`, axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
      grid: { left: 52, right: 18, top: 40, bottom: 26 },
      xAxis: { type: "value", min: 0, max: sc.total_duration_s, axisLabel: { formatter: (v: number) => fmtT(v), color: fg }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false } },
      yAxis: { type: "value", name: "°C", min: 0, max: maxT, axisLabel: { color: fg }, splitLine: { lineStyle: { color: line } } },
      series: [
        ...parts.map((q) => ({
          id: q.key, name: q.label, type: "line" as const, showSymbol: false, z: q.key === focus ? 5 : 2,
          lineStyle: { width: q.key === focus ? 3.5 : 1.2, color: PALETTE[q.key] ?? "#999", opacity: q.key === focus ? 1 : 0.45 },
          itemStyle: { color: PALETTE[q.key] ?? "#999" },
          data: ts.t_real_s.map((x, i) => [x, ts.temperature_C[q.key][i]]),
          ...(q.key === focus ? { markArea: { silent: true, data: [...bands, ...chapters] }, markLine: { silent: true, symbol: "none", data: lead } } : {}),
        })),
        { id: "cursor", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
      ],
    };
  }, [data, focus, shown]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current, undefined, { renderer: "canvas" });
    chart.current = c;
    c.setOption(base, { notMerge: true });
    c.getZr().on("click", (ev: { offsetX: number; offsetY: number }) => {
      const g = c.convertFromPixel({ gridIndex: 0 }, [ev.offsetX, ev.offsetY]) as number[] | undefined;
      if (g && Number.isFinite(g[0])) seek(g[0]);
    });
    const ro = new ResizeObserver(() => c.resize()); ro.observe(el.current);
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, [base, seek]);
  useEffect(() => { chart.current?.setOption({ series: [{ id: "cursor", markLine: { data: [{ xAxis: t }] } }] }, { lazyUpdate: true }); }, [t]);

  return (
    <div className="panel charts">
      <div className="panel-h"><span className="h-title">부품 온도 <span className="dim">주목 부품(★)의 임계 구간만 배경으로</span></span>
        <span className="chips">
          {th.thermal.parts.map((q) => (
            <span key={q.key} className={"chip" + (q.key === focus ? " on" : shown.has(q.key) ? " shown" : "")}
                  onClick={() => q.key !== focus && onToggle(q.key)} style={{ borderColor: q.key === focus ? PALETTE[q.key] : undefined }}>
              <span className="sw" style={{ background: PALETTE[q.key], width: 9, height: 9 }} />{q.label}{q.key === focus ? " ★" : ""}
            </span>))}
        </span>
      </div>
      <div ref={el} className="chart" />
    </div>
  );
}
export { DEFAULT_ON as TEMP_DEFAULT_ON };
