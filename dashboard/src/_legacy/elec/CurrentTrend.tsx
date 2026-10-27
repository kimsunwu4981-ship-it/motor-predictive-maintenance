import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT } from "../../data";
import { usePlayback } from "../../state/playback";
import { ampere, idxAt, PHASES, type Basis, type ElecData, type Phase } from "./data";

// 상별 전류 추세 (TASK 5.1): 재생 위치까지만 그리고 되감으면 되돌아간다. 선 색은 상 식별색(config phases),
// 배경 띠는 config 의 다섯 구간(기준 전환 시 암페어가 바뀐다), 주목 상의 상태 변화 순간에 마커. 클릭하면 그 시각으로 이동.
export function CurrentTrend({ data, basis, focus }: { data: ElecData; basis: Basis; focus: Phase[] }) {
  const { t, seek } = usePlayback();
  const ts = data.timeseries, sc = data.scenarios, el = data.thresholds.electrical, eth = el.ratio_thresholds;
  const elRef = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const pc = (p: Phase) => `rgb(${el.phase_colors[p].map((c) => Math.round(c * 255)).join(",")})`;
  const marks = useMemo(() => data.events.filter((e) => e.type === "status" && (e.phase === "ABC" || focus.includes(e.phase as Phase))), [data.events, focus]);

  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    const maxR = Math.max(1.5, ...PHASES.map((p) => Math.max(...ts.ratio[p]))) * 1.08;
    const A = (r: number) => ampere(data, r, basis);
    type Area = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    const band = (lo: number, hi: number, s: keyof typeof el.status_colors): Area => [
      { yAxis: A(lo), itemStyle: { color: el.status_colors[s], opacity: .12 } }, { yAxis: A(hi) }] as Area;
    const bands: Area[] = [band(0, eth.under_danger, "under_danger"), band(eth.under_danger, eth.under_caution, "under_caution"),
      band(eth.under_caution, eth.over_caution, "normal"), band(eth.over_caution, eth.over_danger, "over_caution"), band(eth.over_danger, maxR, "over_danger")];
    return {
      animation: false, backgroundColor: "transparent",
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "-" : `${Number(v).toFixed(1)} A`), axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
      grid: { left: 44, right: 12, top: 8, bottom: 22 },
      xAxis: { type: "value", min: sc.t_min ?? 0, max: sc.total_duration_s, axisLabel: { formatter: (v: number) => fmtT(v), color: fg, fontSize: 10 }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false } },
      yAxis: { type: "value", min: 0, max: Math.ceil(A(maxR)), axisLabel: { color: fg, fontSize: 10 }, splitLine: { lineStyle: { color: line } } },
      series: [
        ...PHASES.map((p) => ({ id: p, name: `${el.phase_labels[p]}상`, type: "line" as const, showSymbol: false, step: "end" as const, lineStyle: { width: focus.includes(p) || !focus.length ? 2.5 : 1.2, color: pc(p) }, itemStyle: { color: pc(p) }, data: [] as number[][], markArea: p === "A" ? { silent: true, data: bands } : undefined })),
        { id: "rated", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ yAxis: A(1) }], lineStyle: { color: "#66ddff", type: "dashed", width: 1 }, label: { show: true, formatter: `정격 ${A(1).toFixed(1)} A`, color: "#66ddff", fontSize: 10, position: "insideEndTop" } } },
        { id: "lead", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [
            { xAxis: sc.lead_time.alarm_t ?? 0, lineStyle: { color: "#ffaa33", type: "dashed", width: 2 }, label: { show: true, formatter: `▲ I₂/I₁ 4턴 수준(${sc.lead_time.alarm_level_i2i1}) 도달 = ■ A상 위험 과전류 — 같은 순간, 리드 타임 ${sc.lead_time.lead_s} s (등가 표현 한계)`, color: "#ffaa33", fontSize: 10, fontWeight: "bold", position: "end", align: "left", offset: [4, -2] } },
            { xAxis: sc.lead_time.danger_t ?? 0, lineStyle: { color: "#ff2e0a", type: "solid", width: 1.5 }, label: { show: false } },
          ] } },
        { id: "mk", type: "scatter", z: 6, symbolSize: 9, itemStyle: { color: "#fff", borderColor: "#ffaa33", borderWidth: 2 }, label: { show: false }, data: [] as { value: number[] }[] },
        { id: "cursor", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
      ],
    } as echarts.EChartsOption;
  }, [ts, sc, el, eth, basis, focus, data]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!elRef.current) return;
    const ch = echarts.init(elRef.current, undefined, { renderer: "canvas" });
    chart.current = ch;
    ch.setOption(base, { notMerge: true });
    ch.getZr().on("click", (ev: { offsetX: number; offsetY: number }) => {
      const g = ch.convertFromPixel({ gridIndex: 0 }, [ev.offsetX, ev.offsetY]) as number[] | undefined;
      if (g && Number.isFinite(g[0])) seek(g[0]);
    });
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(elRef.current);
    return () => { ro.disconnect(); ch.dispose(); chart.current = null; };
  }, [base, seek]);

  useEffect(() => {
    const ch = chart.current; if (!ch) return;
    const i = idxAt(ts, t) + 1;
    const A = (r: number) => ampere(data, r, basis);
    ch.setOption({ series: [
      ...PHASES.map((p) => ({ id: p, data: ts.t_real_s.slice(0, i).map((x, k) => [x, A(ts.ratio[p][k])]) })),
      { id: "mk", data: marks.filter((e) => e.t <= t).map((e) => ({ value: [e.t, A(Number(e.rms_A) / el.rated_line_A)] })) },
      { id: "cursor", markLine: { data: [{ xAxis: t }] } },
    ] }, { lazyUpdate: true });
  }, [t, ts, basis, marks, data, el]);

  return <div ref={elRef} className="chart trend" />;
}
