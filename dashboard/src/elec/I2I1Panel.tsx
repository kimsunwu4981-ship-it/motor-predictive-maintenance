import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT } from "../data";
import { usePlayback } from "../state/playback";
import { idxAt, type ElecData } from "./data";

// I₂/I₁ 게이지 + 추세 (TASK 5.1): 눈금은 config 의 케이스 목표값(정상 0.006 / 4턴 0.104 / 12턴 0.269), 범위는 로그 최대값 기준.
// 추세는 재생 위치까지만, 눈금 통과·"균형만 무너짐" 사건에 마커. 균형 지표는 크기(색)로는 안 보이는 결함을 잡는 숫자다.
export function I2I1Panel({ data, focus }: { data: ElecData; focus: boolean }) {
  const { t, seek } = usePlayback();
  const ts = data.timeseries, sc = data.scenarios, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const v = ts.i2_over_i1[i];
  const marks = el.i2i1_marks;
  const normal = marks.find((m) => m.case === "healthy")?.value ?? 0;
  const maxV = useMemo(() => Math.ceil(Math.max(...ts.i2_over_i1, marks[marks.length - 1]?.value ?? 0) * 1.1 * 20) / 20, [ts, marks]);
  const events = useMemo(() => data.events.filter((e) => e.type === "i2i1" || e.type === "balance_only"), [data.events]);

  // ---- 게이지 (SVG 반원, 선형 눈금) ----
  const R = 80, cx = 100, cy = 92;
  const ang = (x: number) => Math.PI - (Math.min(x, maxV) / maxV) * Math.PI;   // 0 → 왼쪽(180°), max → 오른쪽(0°)
  const pt = (x: number, r: number) => [cx + r * Math.cos(ang(x)), cy - r * Math.sin(ang(x))];
  const arc = (from: number, to: number, r: number) => { const [x1, y1] = pt(from, r), [x2, y2] = pt(to, r); return `M${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 ${to - from > maxV / 2 ? 1 : 0} 1 ${x2.toFixed(1)},${y2.toFixed(1)}`; };
  const [nx, ny] = pt(v, R - 6);
  const hit = marks.filter((m) => m.case !== "healthy" && v >= m.value - 1e-9).pop();

  // ---- 추세 (ECharts) ----
  const elRef = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    return {
      animation: false, backgroundColor: "transparent",
      tooltip: { trigger: "axis", valueFormatter: (x) => (x == null ? "-" : Number(x).toFixed(3)), axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
      grid: { left: 40, right: 10, top: 6, bottom: 20 },
      xAxis: { type: "value", min: sc.t_min ?? 0, max: sc.total_duration_s, axisLabel: { formatter: (x: number) => fmtT(x), color: fg, fontSize: 10 }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false } },
      yAxis: { type: "value", min: 0, max: maxV, axisLabel: { color: fg, fontSize: 10 }, splitLine: { lineStyle: { color: line } } },
      series: [
        { id: "v", name: "I₂/I₁", type: "line", showSymbol: false, step: "end", lineStyle: { width: 2.5, color: "#ffd166" }, itemStyle: { color: "#ffd166" }, areaStyle: { color: "rgba(255,209,102,.12)" }, data: [] as number[][],
          markLine: { symbol: "none", animation: false, silent: true, data: marks.filter((m) => m.case !== "healthy").map((m) => ({ yAxis: m.value, label: { formatter: `${m.label.replace("턴간 단락 ", "")} ${m.value}`, fontSize: 9, color: fg, position: "insideEndTop" }, lineStyle: { color: "#ffaa33", type: "dashed", width: 1 } })) } },
        { id: "mk", type: "scatter", z: 6, symbolSize: 9, itemStyle: { color: "#fff", borderColor: "#ffd166", borderWidth: 2 }, data: [] as { value: number[] }[] },
        { id: "cursor", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
      ],
    } as echarts.EChartsOption;
  }, [sc, maxV, marks]);
  useEffect(() => {
    if (!elRef.current) return;
    const ch = echarts.init(elRef.current, undefined, { renderer: "canvas" });
    chart.current = ch; ch.setOption(base, { notMerge: true });
    ch.getZr().on("click", (ev: { offsetX: number; offsetY: number }) => { const g = ch.convertFromPixel({ gridIndex: 0 }, [ev.offsetX, ev.offsetY]) as number[] | undefined; if (g && Number.isFinite(g[0])) seek(g[0]); });
    const ro = new ResizeObserver(() => ch.resize()); ro.observe(elRef.current);
    return () => { ro.disconnect(); ch.dispose(); chart.current = null; };
  }, [base, seek]);
  useEffect(() => {
    const ch = chart.current; if (!ch) return;
    const n = idxAt(ts, t) + 1;
    ch.setOption({ series: [
      { id: "v", data: ts.t_real_s.slice(0, n).map((x, k) => [x, ts.i2_over_i1[k]]) },
      { id: "mk", data: events.filter((e) => e.t <= t).map((e) => ({ value: [e.t, Number(e.value)] })) },
      { id: "cursor", markLine: { data: [{ xAxis: t }] } },
    ] }, { lazyUpdate: true });
  }, [t, ts, events]);

  return (
    <div className={"panel i2i1" + (focus ? " focus" : "")}>
      <div className="panel-h">균형 지표 I₂/I₁ <span className="dim">역상분 비율 · 세 줄이 얼마나 어긋났나</span></div>
      <div className="panel-b">
        <div className="gauge-row">
          <svg viewBox="0 0 200 104" className="gauge">
            <path d={arc(0, maxV, R)} className="g-arc" />
            {marks.map((m) => { const [x1, y1] = pt(m.value, R - 10), [x2, y2] = pt(m.value, R + 6); const [lx, ly] = pt(m.value, R + 16);
              return <g key={m.case} className={"g-mark" + (m.case === "healthy" ? " n" : "")}><line x1={x1} y1={y1} x2={x2} y2={y2} /><text x={lx} y={ly} textAnchor={m.value < maxV / 2 ? "start" : "end"}>{m.case === "healthy" ? "정상" : m.label.includes("4") ? "4턴" : "12턴"} {m.value}</text></g>; })}
            <line x1={cx} y1={cy} x2={nx} y2={ny} className={"g-needle" + (hit ? " hot" : "")} />
            <circle cx={cx} cy={cy} r={4} className="g-pin" />
          </svg>
          <div className="g-legend">
            <div className={"g-big" + (hit ? " hot" : "")}>{v.toFixed(3)}</div>
            <div className="g-x">{normal > 0 ? `정상(${normal})의 ${(v / normal).toFixed(1)}배` : ""}</div>
            {marks.filter((m) => m.case !== "healthy").map((m) => <div key={m.case} className={v >= m.value - 1e-9 ? "hit" : ""}>{m.label.replace("턴간 단락 ", "")} <b>{m.value}</b></div>)}
            <div className="dim">{hit ? `${hit.label.replace("턴간 단락 ", "")} 수준 이상` : "단락 눈금 아래"}</div>
          </div>
        </div>
        <div ref={elRef} className="chart i2i1-trend" />
      </div>
    </div>
  );
}
