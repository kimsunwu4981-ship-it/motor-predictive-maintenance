import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { fmtT } from "../data";
import type { FleetIndex, FleetScenario, GaugeSpec, Kind, MotorInfo, MotorSeries, Phase } from "./data";
import { PHASES } from "./data";

// 신호별 추세 차트 (TASK_다중모터 §7.1 ④): 선택 신호를 임계 구간 배경 위에 그린다. 장면 경계 띠, 현재 시각 커서, 클릭으로 이동.
// 전체 시계열을 그리고 커서로 현재를 표시한다 (상태 보드는 해설용이 아니라 감시용이라 미래를 숨기지 않는다).
export interface TrendSel { kind: Kind; component?: string }

export function TrendChart({ index, motor, series, sel, spec, t, onSeek, scenario, plain = false, yName: yNameProp, markT = null, relativeTo = null }: {
  index: FleetIndex; motor: MotorInfo; series: MotorSeries; sel: TrendSel; spec: GaugeSpec; t: number; onSeek: (t: number) => void;
  scenario?: FleetScenario;            // 라이브: 흐르는 창 {t_min, total_duration_s=버퍼 끝, 관찰된 장면}
  plain?: boolean;                     // 단순 보기: 선은 전경색 하나(상별은 선 모양으로 구분), 임계 띠는 연하게, 축 라벨 최소
  yName?: string;                      // y축 이름 덮어쓰기 (단순 보기: 쉬운 말)
  markT?: number | null;               // 주입 시각 세로선 (단순 보기 ④)
  relativeTo?: number | null;          // 라이브(패널 Q1 §4.1): x 축 라벨을 "지금 기준 −m:ss" 로 — 제목 "최근 N 분" 과 같은 구간을 가리키게
}) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const sc = scenario ?? index.scenarios[series.mode];

  const base = useMemo<echarts.EChartsOption>(() => {
    const css = getComputedStyle(document.documentElement);
    const fg = css.getPropertyValue("--fg2").trim() || "#aab", line = css.getPropertyValue("--line").trim() || "#334";
    type Area = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    const lines: { name: string; data: number[]; color: string }[] = [];
    const sig = index.signals[sel.kind];
    let yName = yNameProp ?? (sig.label + (sig.unit ? ` (${sig.unit})` : ""));
    if (sel.kind === "temperature") {
      const node = sel.component ?? "bearing_de";
      lines.push({ name: index.node_labels[node] ?? node, data: series.temperature_C[node], color: "#ffc93c" });
      yName = yNameProp ?? `${index.node_labels[node] ?? node} 온도 (°C)`;
    } else if (sel.kind === "current_ratio") {
      const cols: Record<Phase, string> = { A: "#ff5b3a", B: "#62d2ff", C: "#8fe3a8" };
      for (const p of PHASES) lines.push({ name: `${index.phase_labels[p]}상`, data: series.current_ratio[p], color: cols[p] });
      yName = yNameProp ?? "전류 / 정격 (×)";
    } else if (sel.kind === "i2i1") lines.push({ name: "I₂/I₁", data: series.i2i1, color: "#b78bff" });
    else if (sel.kind === "vibration") lines.push({ name: "진동 RMS", data: series.vibration_mms, color: "#62d2ff" });
    else if (sel.kind === "bearing_kurtosis") lines.push({ name: "베어링 kurtosis", data: series.bearing_kurtosis, color: "#e0c48a" });
    else lines.push({ name: "베어링 고주파 RMS 배율", data: series.bearing_hf_ratio, color: "#f0a06a" });
    const fgMain = css.getPropertyValue("--fg").trim() || "#eee";
    const dashes: ("solid" | "dashed" | "dotted")[] = ["solid", "dashed", "dotted"];
    if (plain) lines.forEach((l) => { l.color = fgMain; });
    const vmax = Math.max(...lines.flatMap((l) => l.data));
    const yMax = Math.max(spec.max, vmax * 1.08);
    const bands: Area[] = spec.segments.map((s) => [
      { yAxis: s.from, itemStyle: { color: index.colors[s.level], opacity: plain ? .10 : .12 },
        label: { show: true, formatter: `${index.labels_ko[s.level]}${s.label ? " " + s.label : ""}`, position: "insideTopLeft", color: fg, fontSize: plain ? 12 : 11 } },
      { yAxis: Math.min(s.to, yMax) }] as Area);
    const chapters: Area[] = sc.steps.map((s, i) => [{ xAxis: s.t_start, itemStyle: { color: i % 2 ? "rgba(128,128,128,.08)" : "rgba(128,128,128,0)" },
      label: { show: true, formatter: s.n ? String(s.n) : (s.id === "manual" ? "수동" : ""), position: "insideTop", color: fg, fontSize: 10 } }, { xAxis: s.t_end }] as Area);   // §4.5: 번호 없는 수동 스텝은 "0" 대신 "수동"
    return {
      animation: false,
      grid: { left: 54, right: 16, top: 22, bottom: 24 },
      tooltip: { trigger: "axis", valueFormatter: (v) => (typeof v === "number" ? (Math.abs(v) < 1 ? v.toFixed(3) : v.toFixed(2)) : String(v)) },
      legend: { show: lines.length > 1, top: 0, right: 10, textStyle: { color: fg, fontSize: plain ? 12 : 11 } },
      xAxis: { type: "value", min: sc.t_min ?? 0, max: sc.total_duration_s, splitNumber: plain ? 3 : undefined, axisLabel: { color: fg, fontSize: plain ? 12 : undefined, formatter: (v: number) => (relativeTo !== null && relativeTo !== undefined ? (relativeTo - v < 0.5 ? "지금" : `-${fmtT(relativeTo - v)}`) : fmtT(v)) }, splitLine: { show: false }, axisLine: { lineStyle: { color: line } } },
      yAxis: { type: "value", min: Math.min(spec.min, 0), max: yMax, splitNumber: plain ? 2 : undefined, name: plain ? "" : yName, nameLocation: "end", nameGap: 4, nameTextStyle: { color: fg, align: "left", padding: [0, 0, 0, -44], fontSize: plain ? 12 : 11 }, axisLabel: { color: fg, fontSize: plain ? 12 : undefined, showMaxLabel: !plain }, splitLine: { show: !plain, lineStyle: { color: line, opacity: .5 } } },
      series: [
        ...lines.map((l, n) => ({
          name: l.name, type: "line" as const, showSymbol: false, lineStyle: { width: plain ? 2.5 : 2, color: l.color, type: plain ? dashes[n % 3] : "solid" }, itemStyle: { color: l.color },
          data: series.t.map((x, i) => [x, l.data[i]]),
          ...(n === 0 ? { markArea: { silent: true, data: [...bands, ...chapters] } } : {}),
        })),
        { name: "cursor", type: "line" as const, data: [], silent: true, tooltip: { show: false },
          markLine: { symbol: "none", animation: false, data: [{ xAxis: t }], lineStyle: { color: index.colors[series.status[0]] ?? "#fff", width: 2 }, label: { show: false } } },
        ...(markT !== null && markT !== undefined ? [{ name: "inject", type: "line" as const, data: [], silent: true, tooltip: { show: false },
          markLine: { symbol: "none", animation: false, data: [{ xAxis: markT }], lineStyle: { color: fg, width: 1, type: "dashed" as const }, label: { show: true, formatter: "주입", position: "insideEndTop" as const, rotate: 0, color: fg, fontSize: 11 } } }] : []),
      ],
    };
  }, [index, series, sel, spec, sc, plain, yNameProp, markT, relativeTo]);  // eslint-disable-line react-hooks/exhaustive-deps

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
