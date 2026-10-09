import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT, indexAt } from "../data";
import { usePlayback } from "../state/playback";
import type { MechData } from "./data";

// 진동 차트 (TASK 5.1): 진동 속도 RMS 와 ISO 20816-3 구간(Watch/Plan/Act — config 값) 배경.
// 장면 3 에서 "온도보다 진동이 먼저" 가 보여야 한다. 미래 숨김·커서·등급 변화 마커.
export function VibChart({ data }: { data: MechData }) {
  const { t, seek } = usePlayback();
  const ts = data.timeseries, sc = data.scenarios, th = data.thresholds;
  const iso = th.vibration_iso, c = th.thermal.stage_colors;
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const zoneEvents = useMemo(() => data.events.filter((e) => e.type === "vib_zone"), [data.events]);

  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    const maxV = Math.ceil(Math.max(iso.act_mms * 1.3, ...ts.vibration_mms) * 1.15);
    type Area = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    const band = (lo: number, hi: number, color: string, text: string): Area => [
      { yAxis: lo, itemStyle: { color, opacity: .13 }, label: { show: true, formatter: text, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: hi }] as Area;
    const bands: Area[] = [
      band(0, iso.watch_mms, c.normal, `정상 < ${iso.watch_mms}`),
      band(iso.watch_mms, iso.plan_mms, c.caution, `주시 ≥ ${iso.watch_mms} mm/s`),
      band(iso.plan_mms, iso.act_mms, c.warning, `정비 계획 ≥ ${iso.plan_mms}`),
      band(iso.act_mms, maxV, c.danger, `즉시 조치 ≥ ${iso.act_mms} mm/s`),
    ];
    return {
      animation: false, backgroundColor: "transparent",
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "-" : `${Number(v).toFixed(1)} mm/s`), axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
      grid: { left: 44, right: 14, top: 30, bottom: 26 },
      xAxis: { type: "value", min: sc.t_min ?? 0, max: sc.total_duration_s, axisLabel: { formatter: (v: number) => fmtT(v), color: fg }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false } },
      yAxis: { type: "value", name: "mm/s", min: 0, max: maxV, axisLabel: { color: fg }, splitLine: { lineStyle: { color: line } } },
      series: [
        { id: "vib", name: "진동 속도 RMS", type: "line", showSymbol: false, step: "end", lineStyle: { width: 2.5, color: "#ffd166" }, itemStyle: { color: "#ffd166" },
          areaStyle: { color: "rgba(255,209,102,.12)" }, data: [] as number[][], markArea: { silent: true, data: bands } },
        { id: "vmark", type: "scatter", z: 6, symbolSize: 10, itemStyle: { color: "#fff", borderColor: "#ffd166", borderWidth: 2 },
          label: { show: true, position: "right", fontSize: 11, color: fg, formatter: (o: unknown) => (o as { data?: { name?: string } }).data?.name ?? "" }, data: [] as { value: number[]; name: string }[] },
        { id: "cursor", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
      ],
    } as echarts.EChartsOption;
  }, [ts, sc, iso, c]);

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

  useEffect(() => {
    const ch = chart.current; if (!ch) return;
    const i = indexAt(ts, t) + 1;
    ch.setOption({ series: [
      { id: "vib", data: ts.t_real_s.slice(0, i).map((x, k) => [x, ts.vibration_mms[k]]) },
      { id: "vmark", data: zoneEvents.filter((e) => e.t <= t).map((e) => ({ value: [e.t, e.value_mms], name: `${e.to_ko} ${e.threshold_mms}` })) },
      { id: "cursor", markLine: { data: [{ xAxis: t }] } },
    ] }, { lazyUpdate: true });
  }, [t, ts, zoneEvents]);

  const i = indexAt(ts, t);
  return (
    <div className="panel charts">
      <div className="panel-h"><span className="h-title">진동 <span className="dim">ISO 20816-3</span></span>
        <span className="grow" />
        <span className="vib-now" style={{ color: ts.iso_zone[i] === "Normal" ? c.normal : ts.iso_zone[i] === "Watch" ? c.caution : ts.iso_zone[i] === "Plan" ? c.warning : c.danger }}>
          {ts.vibration_mms[i].toFixed(1)} mm/s · {th.vibration_iso.zone_labels[ts.iso_zone[i]] ?? ts.iso_zone[i]}
        </span>
      </div>
      <div ref={el} className="chart" />
    </div>
  );
}
