import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts";
import { fmtT, type Mode, type ModeData } from "../../data";
import { usePlayback } from "../../state/playback";
import { Legend } from "./Legend";

// 영상 시각과 동기화된 차트. 세로 커서 = 현재 t_real, 클릭하면 영상이 그 시각으로 이동한다.
// 기계: 부품별 온도 + 선택 부품의 임계 구간 배경색 + 리드 타임 표시
// 전기: 상별 전류 RMS(임계 구간 배경색) + I2/I1 (케이스별 눈금)
export function SyncedCharts({ mode, data }: { mode: Mode; data: ModeData }) {
  const { t, seek } = usePlayback();
  const th = data.thresholds, ts = data.timeseries, sc = data.scenarios;
  const hudParts = th.thermal.parts.filter((p) => p.hud);
  const [part, setPart] = useState(hudParts[0]?.key ?? "bearing_de");
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const css = () => getComputedStyle(document.documentElement);
  const lt = sc.lead_time;

  // 기본 옵션 (데이터가 바뀔 때만)
  const base = useMemo<echarts.EChartsOption>(() => {
    const fg = css().getPropertyValue("--fg2").trim() || "#aab";
    const line = css().getPropertyValue("--line").trim() || "#334";
    const xAxis = (gridIndex: number): echarts.XAXisComponentOption => ({
      type: "value", min: 0, max: sc.total_duration_s, gridIndex,
      axisLabel: { formatter: (v: number) => fmtT(v), color: fg }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false },
    });
    type LineItem = NonNullable<echarts.MarkLineComponentOption["data"]>[number];
    const leadMarks = (): LineItem[] => {
      const d: LineItem[] = [];
      if (lt.alarm_t != null) d.push({ xAxis: lt.alarm_t, name: "VIGENT 조기 경보", lineStyle: { color: "#ffaa33", type: "dashed", width: 2 },
        label: { formatter: "▲ VIGENT 조기 경보 가능 시점", position: "end", align: "left", offset: [4, -2], color: "#ffaa33", fontWeight: "bold", fontSize: 12 } });
      if (lt.danger_t != null) d.push({ xAxis: lt.danger_t, name: "위험 도달", lineStyle: { color: th.thermal.stage_colors.danger, type: "solid", width: 2 },
        label: { formatter: "■ 위험 도달", position: "end", align: "left", offset: [4, 14], color: th.thermal.stage_colors.danger, fontSize: 12 } });
      return d;
    };
    // markArea 의 data 는 [시작, 끝] 2요소 튜플이어야 한다 — 배열로 추론되면 타입 오류
    type AreaItem = NonNullable<echarts.MarkAreaComponentOption["data"]>[number];
    const chapterAreas: AreaItem[] = sc.steps.map((s, i) => [{ xAxis: s.t_start, itemStyle: { color: i % 2 ? "rgba(128,128,128,.06)" : "rgba(128,128,128,0)" }, label: { show: false } }, { xAxis: s.t_end }] as AreaItem);

    if (mode === "mechanical") {
      const p = th.thermal.parts.find((q) => q.key === part) ?? hudParts[0];
      const maxT = Math.max(p.warning_max_C + 40, ...hudParts.map((q) => Math.max(...ts.temperature_C[q.key])) ) + 5;
      const bands: echarts.MarkAreaComponentOption["data"] = [
        [{ yAxis: 0, itemStyle: { color: th.thermal.stage_colors.normal, opacity: .07 }, label: { show: true, formatter: `${p.label} 정상 ≤ ${p.normal_max_C} °C`, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: p.normal_max_C }],
        [{ yAxis: p.normal_max_C, itemStyle: { color: th.thermal.stage_colors.caution, opacity: .12 }, label: { show: true, formatter: `주의 ≤ ${p.caution_max_C}`, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: p.caution_max_C }],
        [{ yAxis: p.caution_max_C, itemStyle: { color: th.thermal.stage_colors.warning, opacity: .14 }, label: { show: true, formatter: `경고 ≤ ${p.warning_max_C}`, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: p.warning_max_C }],
        [{ yAxis: p.warning_max_C, itemStyle: { color: th.thermal.stage_colors.danger, opacity: .16 }, label: { show: true, formatter: `위험 > ${p.warning_max_C} °C`, position: "insideTopLeft", color: fg, fontSize: 11 } }, { yAxis: maxT }],
      ];
      const palette = ["#ff5b3a", "#ffc93c", "#62d2ff", "#b78bff"];
      return {
        animation: false, backgroundColor: "transparent",
        tooltip: { trigger: "axis", valueFormatter: (v) => `${Number(v).toFixed(1)} °C`, axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
        legend: { top: 0, textStyle: { color: fg } },
        grid: { left: 56, right: 24, top: 46, bottom: 30 },
        xAxis: xAxis(0),
        yAxis: { type: "value", name: "°C", min: 0, max: Math.ceil(maxT / 10) * 10, axisLabel: { color: fg }, splitLine: { lineStyle: { color: line } } },
        series: [
          ...hudParts.map((q, k) => ({
            id: q.key, name: q.label, type: "line" as const, showSymbol: false, smooth: false,
            lineStyle: { width: q.key === part ? 3 : 1.6, color: palette[k % palette.length] }, itemStyle: { color: palette[k % palette.length] },
            data: ts.t_real_s.map((x, i) => [x, ts.temperature_C[q.key][i]]),
            ...(q.key === part ? { markArea: { silent: true, data: [...bands, ...chapterAreas] }, markLine: { silent: true, symbol: "none", data: leadMarks() } } : {}),
          })),
          { id: "cursor", type: "line", data: [], silent: true, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
        ],
      };
    }
    // ---- electrical ----
    const e = th.electrical, r = e.ratio_thresholds, I = e.rated_line_A;
    const maxA = Math.max(I * r.over_danger * 1.3, ...(["A", "B", "C"] as const).map((p) => Math.max(...ts.current_rms_A[p]))) + 5;
    const ab = (lo: number, hi: number, color: string, text: string): AreaItem => [
      { yAxis: lo, itemStyle: { color, opacity: .12 }, label: { show: false, formatter: text } }, { yAxis: hi }] as AreaItem;
    const bandsA = [
      ab(I * r.over_danger, maxA, e.status_colors.over_danger, `위험 과전류 > ${(I * r.over_danger).toFixed(1)} A (×${r.over_danger})`),
      ab(I * r.over_caution, I * r.over_danger, e.status_colors.over_caution, `주의 과전류 > ${(I * r.over_caution).toFixed(1)} A`),
      ab(I * r.under_caution, I * r.over_caution, e.status_colors.normal, `정상 ${(I * r.under_caution).toFixed(1)}–${(I * r.over_caution).toFixed(1)} A`),
      ab(I * r.under_danger, I * r.under_caution, e.status_colors.under_caution, `주의 저전류 < ${(I * r.under_caution).toFixed(1)} A`),
      ab(0, I * r.under_danger, e.status_colors.under_danger, `위험 저전류 < ${(I * r.under_danger).toFixed(1)} A`),
    ];
    const phaseColor = { A: "#ffd54a", B: "#4fd8ff", C: "#d68cff" };
    // 임계선 라벨은 오른쪽 끝, 좁은 구간끼리 겹치지 않게 위·아래로 번갈아 둔다
    const thrLine = (y: number, text: string, color: string, pos: "insideEndTop" | "insideEndBottom") => ({
      yAxis: y, lineStyle: { color, type: "dashed" as const, width: 1 }, label: { formatter: text, position: pos, color, fontSize: 11 } });
    const thrLines = [
      thrLine(I * r.over_danger, `위험 과전류 ${(I * r.over_danger).toFixed(1)} A (×${r.over_danger})`, e.status_colors.over_danger, "insideEndTop"),
      thrLine(I * r.over_caution, `주의 과전류 ${(I * r.over_caution).toFixed(1)} A (×${r.over_caution})`, e.status_colors.over_caution, "insideEndBottom"),
      thrLine(I * r.under_caution, `주의 저전류 ${(I * r.under_caution).toFixed(1)} A (×${r.under_caution})`, e.status_colors.under_caution, "insideEndBottom"),
      thrLine(I * r.under_danger, `위험 저전류 ${(I * r.under_danger).toFixed(1)} A (×${r.under_danger})`, e.status_colors.under_danger, "insideEndBottom"),
    ];
    const i2marks = e.i2i1_marks.map((m) => ({ yAxis: m.value, lineStyle: { color: "#ffaa33", type: "dotted" as const }, label: { formatter: `${m.label} ${m.value}`, position: "insideEndTop" as const, color: "#ffaa33", fontSize: 11 } }));
    const maxI2 = Math.max(0.35, ...ts.i2_over_i1) * 1.15;
    return {
      animation: false, backgroundColor: "transparent",
      tooltip: { trigger: "axis", axisPointer: { label: { formatter: (o) => fmtT(Number(o.value)) } } },
      legend: { top: 0, textStyle: { color: fg } },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      grid: [{ left: 56, right: 24, top: 44, height: "44%" }, { left: 56, right: 24, top: "66%", bottom: 28 }],
      xAxis: [xAxis(0), xAxis(1)],
      yAxis: [
        { type: "value", name: "A (선전류)", gridIndex: 0, min: 0, max: Math.ceil(maxA / 10) * 10, axisLabel: { color: fg }, splitLine: { lineStyle: { color: line } } },
        { type: "value", name: "I₂/I₁", gridIndex: 1, min: 0, max: Number(maxI2.toFixed(2)), axisLabel: { color: fg }, splitLine: { lineStyle: { color: line } } },
      ],
      series: [
        ...(["A", "B", "C"] as const).map((p, k) => ({
          id: "ph" + p, name: `${th.electrical.phase_labels?.[p] ?? p}상 RMS`, type: "line" as const, showSymbol: false, xAxisIndex: 0, yAxisIndex: 0,
          lineStyle: { width: 2, color: phaseColor[p] }, itemStyle: { color: phaseColor[p] },
          data: ts.t_real_s.map((x, i) => [x, ts.current_rms_A[p][i]]),
          ...(k === 0 ? { markArea: { silent: true, data: [...bandsA, ...chapterAreas] }, markLine: { silent: true, symbol: "none", data: [...leadMarks(), ...thrLines] } } : {}),
        })),
        { id: "i2i1", name: "I₂/I₁ (역상분 비율)", type: "line", showSymbol: false, xAxisIndex: 1, yAxisIndex: 1, lineStyle: { width: 2.5, color: "#66ddff" }, itemStyle: { color: "#66ddff" },
          areaStyle: { color: "rgba(102,221,255,.12)" }, data: ts.t_real_s.map((x, i) => [x, ts.i2_over_i1[i]]),
          markLine: { silent: true, symbol: "none", data: i2marks } },
        { id: "cursor", type: "line", data: [], silent: true, xAxisIndex: 0, yAxisIndex: 0, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
        { id: "cursor2", type: "line", data: [], silent: true, xAxisIndex: 1, yAxisIndex: 1, markLine: { symbol: "none", animation: false, data: [{ xAxis: 0 }], lineStyle: { color: "#66ddff", width: 2 }, label: { show: false } } },
      ],
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, data, part]);

  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current, undefined, { renderer: "canvas" });
    chart.current = c;
    c.setOption(base, { notMerge: true });
    // 클릭 → 영상 이동 (양방향 동기화)
    c.getZr().on("click", (ev: { offsetX: number; offsetY: number }) => {
      const g = c.convertFromPixel({ gridIndex: 0 }, [ev.offsetX, ev.offsetY]) as number[] | undefined;
      let x = g?.[0];
      if (mode === "electrical" && (x == null || Number.isNaN(x))) {
        const g2 = c.convertFromPixel({ gridIndex: 1 }, [ev.offsetX, ev.offsetY]) as number[] | undefined;
        x = g2?.[0];
      }
      if (x != null && Number.isFinite(x)) seek(x);
    });
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, [base, mode, seek]);

  // 커서만 갱신 (20 Hz)
  useEffect(() => {
    const c = chart.current; if (!c) return;
    const series = mode === "mechanical"
      ? [{ id: "cursor", markLine: { data: [{ xAxis: t }] } }]
      : [{ id: "cursor", markLine: { data: [{ xAxis: t }] } }, { id: "cursor2", markLine: { data: [{ xAxis: t }] } }];
    c.setOption({ series }, { lazyUpdate: true });
  }, [t, mode]);

  const leadText = lt.lead_s == null ? "리드 타임 계산 불가"
    : lt.lead_s <= 0.05
      ? `조기 경보 = 위험 도달 (동시 — 해석식 모델의 한계)`
      : `리드 타임 ${lt.lead_s.toFixed(1)} s (재생 시간) = 시뮬레이션 약 ${lt.lead_sim_s != null ? (lt.lead_sim_s / 60).toFixed(1) : "?"} 분`;

  return (
    <div className="panel charts">
      <div className="panel-h">
        {mode === "mechanical" ? "부품 온도 (임계 구간 배경색)" : "상별 전류 RMS · I₂/I₁"}
        {mode === "mechanical" && (
          <span className="chips">
            <span className="dim">기준 부품:</span>
            {hudParts.map((p) => <span key={p.key} className={"chip" + (p.key === part ? " on" : "")} onClick={() => setPart(p.key)}>{p.label}</span>)}
          </span>
        )}
        <span className="lead" title={lt.basis}>⏱ <b>{leadText}</b></span>
      </div>
      <div ref={el} className="chart" />
      <div style={{ padding: "0 14px 8px" }}><Legend mode={mode} data={data} /></div>
    </div>
  );
}
