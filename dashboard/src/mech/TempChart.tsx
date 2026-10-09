import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT, indexAt } from "../data";
import { usePlayback } from "../state/playback";
import type { MechData } from "./data";

// 부품별 온도 차트 (TASK 5.1)
//  · 주목 부품만 임계 구간 배경 띠 + 굵은 선. 다른 부품은 등급에 따라 선 색이 바뀐다(visualMap, 부품별 임계값).
//  · 영상 재생 위치까지만 선을 그린다(미래 숨김). 되감으면 선도 되돌아간다.
//  · 주목 부품이 주의·경고·위험 경계를 넘는 순간(events.json)에 점과 라벨을 찍는다.
//  · 장면 2 리드 타임: 조기 경보(주황 점선) ↔ 위험 도달(빨간 선), 재생 시간과 시뮬레이션 시간 함께 표기.
export const PALETTE: Record<string, string> = {
  bearing_de: "#ff5b3a", bearing_nde: "#ff9c7a", winding: "#ffc93c", rotor: "#62d2ff", shaft: "#b78bff",
  frame: "#8fe3a8", stator_core: "#e0c48a", endshield_de: "#c9a0ff", endshield_nde: "#a6d8ff",
};
export const TEMP_DEFAULT_ON = ["bearing_de", "bearing_nde", "winding", "rotor", "shaft", "frame"];

export function TempChart({ data, focus, shown, onToggle }: {
  data: MechData; focus: string; shown: Set<string>; onToggle: (k: string) => void;
}) {
  const { t, seek } = usePlayback();
  const th = data.thresholds, ts = data.timeseries, sc = data.scenarios;
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const lt = sc.lead_time;
  const c = th.thermal.stage_colors;
  const parts = useMemo(() => th.thermal.parts.filter((q) => shown.has(q.key) || q.key === focus), [th, shown, focus]);
  const markerEvents = useMemo(() => data.events.filter((e) => e.part === focus && (e.type === "stage_up" || e.type === "stage_down" || e.type === "recovered")), [data.events, focus]);

  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    const p = th.thermal.parts.find((q) => q.key === focus) ?? th.thermal.parts[0];
    const maxT = Math.ceil((Math.max(p.warning_max_C + 30, ...parts.map((q) => Math.max(...ts.temperature_C[q.key]))) + 5) / 10) * 10;
    type Area = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    type Line = NonNullable<echarts.MarkLineComponentOption["data"]>[number];
    const band = (lo: number, hi: number, color: string, text: string): Area => [
      { yAxis: lo, itemStyle: { color, opacity: .13 }, label: { show: true, formatter: text, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: hi }] as Area;
    const bands: Area[] = [
      band(0, p.normal_max_C, c.normal, `${p.label} 정상 ≤ ${p.normal_max_C} °C`),
      band(p.normal_max_C, p.caution_max_C, c.caution, `주의 ≤ ${p.caution_max_C}`),
      band(p.caution_max_C, p.warning_max_C, c.warning, `경고 ≤ ${p.warning_max_C}`),
      band(p.warning_max_C, maxT, c.danger, `위험 > ${p.warning_max_C} °C`),
    ];
    const chapters: Area[] = sc.steps.map((s, i) => [{ xAxis: s.t_start, itemStyle: { color: i % 2 ? "rgba(128,128,128,.07)" : "rgba(128,128,128,0)" }, label: { show: false } }, { xAxis: s.t_end }] as Area);
    const lead: Line[] = [];
    if (lt.alarm_t != null) lead.push({ xAxis: lt.alarm_t, lineStyle: { color: "#ffaa33", type: "dashed", width: 2 },
      label: { formatter: "▲ VIGENT 조기 경보 (주의 진입)", position: "end", align: "left", offset: [4, -2], color: "#ffaa33", fontWeight: "bold", fontSize: 12 } });
    if (lt.danger_t != null) lead.push({ xAxis: lt.danger_t, lineStyle: { color: c.danger, width: 2 },
      label: { formatter: `■ 위험 도달 — 리드 타임 화면 ${lt.lead_s} s = 시뮬레이션 약 ${((lt.lead_sim_s ?? 0) / 60).toFixed(1)} 분`, position: "end", align: "left", offset: [4, 14], color: c.danger, fontSize: 12 } });
    // 비주목 부품: 등급별 선 색 (부품마다 임계값이 달라 visualMap 을 부품마다 따로 둔다)
    const visualMap = parts.filter((q) => q.key !== focus).map((q, k) => ({
      type: "piecewise" as const, show: false, dimension: 1, seriesIndex: parts.findIndex((x) => x.key === q.key),
      pieces: [
        { lt: q.normal_max_C, color: "rgba(160,170,180,.55)" },
        { gte: q.normal_max_C, lt: q.caution_max_C, color: c.caution },
        { gte: q.caution_max_C, lt: q.warning_max_C, color: c.warning },
        { gte: q.warning_max_C, color: c.danger },
      ], id: "vm" + k,
    }));
    return {
      animation: false, backgroundColor: "transparent",
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "-" : `${Number(v).toFixed(1)} °C`), axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
      grid: { left: 52, right: 18, top: 40, bottom: 26 },
      xAxis: { type: "value", min: sc.t_min ?? 0, max: sc.total_duration_s, axisLabel: { formatter: (v: number) => fmtT(v), color: fg }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false } },
      yAxis: { type: "value", name: "°C", min: 0, max: maxT, axisLabel: { color: fg }, splitLine: { lineStyle: { color: line } } },
      visualMap,
      series: [
        ...parts.map((q) => ({
          id: q.key, name: q.label, type: "line" as const, showSymbol: false, z: q.key === focus ? 5 : 2,
          lineStyle: { width: q.key === focus ? 3.5 : 1.4, color: q.key === focus ? PALETTE[q.key] : undefined, opacity: q.key === focus ? 1 : 0.8 },
          itemStyle: { color: PALETTE[q.key] ?? "#999" },
          data: [] as number[][],
          ...(q.key === focus ? { markArea: { silent: true, data: [...bands, ...chapters] }, markLine: { silent: true, symbol: "none", data: lead } } : {}),
        })),
        { id: "markers", name: "임계 통과", type: "scatter", z: 6, symbolSize: 11, itemStyle: { color: "#fff", borderColor: PALETTE[focus] ?? "#fff", borderWidth: 2 },
          label: { show: true, position: "top", fontSize: 11, color: fg, formatter: (o: unknown) => (o as { data?: { name?: string } }).data?.name ?? "" }, data: [] as { value: number[]; name: string }[] },
        { id: "cursor", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
      ],
    } as echarts.EChartsOption;
  }, [th, ts, sc, lt, c, parts, focus]);

  useEffect(() => {
    if (!el.current) return;
    const ch = echarts.init(el.current, undefined, { renderer: "canvas" });
    chart.current = ch;
    ch.setOption(base, { notMerge: true });
    ch.getZr().on("click", (ev: { offsetX: number; offsetY: number }) => {
      const g = ch.convertFromPixel({ gridIndex: 0 }, [ev.offsetX, ev.offsetY]) as number[] | undefined;
      if (g && Number.isFinite(g[0])) seek(g[0]);
    });
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(el.current);
    return () => { ro.disconnect(); ch.dispose(); chart.current = null; };
  }, [base, seek]);

  // 재생 위치까지만 데이터를 넣는다 (미래 숨김). 20 Hz 갱신, 715 샘플 × 6 선이라 가볍다.
  useEffect(() => {
    const ch = chart.current; if (!ch) return;
    const i = indexAt(ts, t) + 1;
    const series: object[] = parts.map((q) => ({ id: q.key, data: ts.t_real_s.slice(0, i).map((x, k) => [x, ts.temperature_C[q.key][k]]) }));
    series.push({ id: "markers", data: markerEvents.filter((e) => e.t <= t).map((e) => ({
      value: [e.t, e.temp_C], name: `${e.type === "recovered" ? "정상 복귀" : e.to_ko} ${e.threshold_C} °C${e.note === "early_warning" ? " ▲경보" : ""}` })) });
    series.push({ id: "cursor", markLine: { data: [{ xAxis: t }] } });
    ch.setOption({ series }, { lazyUpdate: true });
  }, [t, ts, parts, markerEvents]);

  return (
    <div className="panel charts">
      <div className="panel-h"><span className="h-title">부품 온도 <span className="dim">★ 주목 부품만 임계 띠 · 나머지는 등급색 선</span></span>
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
