import { useMemo } from "react";
import { usePlayback } from "../state/playback";
import { ELEC_ICON } from "../components/Legend";
import { ampere, idxAt, PHASES, type Basis, type ElecData, type Phase } from "./data";
import { CurrentTrend } from "./CurrentTrend";

// ③ 상별 전류 막대 (TASK 5.1 주 표시): A·B·C 세 막대가 정격 대비 %로 실시간으로 오르내린다.
// 배경 띠 = config 의 다섯 구간(저전류 위험/주의, 정상, 과전류 주의/위험), 막대 색 = 영상과 같은 상태색,
// 막대 위에 암페어 + ▲▲/▲/●/▼/▼▼ 기호 (색각 이상 대비). 기준(선/상전류)에 따라 암페어 눈금이 바뀐다.
export function CurrentBars({ data, basis, focus }: { data: ElecData; basis: Basis; focus: Phase[] }) {
  const { t } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical, eth = el.ratio_thresholds;
  const i = idxAt(ts, t);
  // 세로 축 최대: 로그 최대 비율 × 1.08 (최소 1.5) — 장면 3 의 201 % 까지 보이게
  const maxR = useMemo(() => Math.max(1.5, ...PHASES.map((p) => Math.max(...ts.ratio[p]))) * 1.08, [ts]);
  const y = (r: number) => `${Math.min(100, (r / maxR) * 100)}%`;
  const bands = [
    { from: 0, to: eth.under_danger, s: "under_danger" as const },
    { from: eth.under_danger, to: eth.under_caution, s: "under_caution" as const },
    { from: eth.under_caution, to: eth.over_caution, s: "normal" as const },
    { from: eth.over_caution, to: eth.over_danger, s: "over_caution" as const },
    { from: eth.over_danger, to: maxR, s: "over_danger" as const },
  ];
  const A = (r: number) => ampere(data, r, basis).toFixed(1);
  return (
    <div className="panel cbars">
      <div className="panel-h">상별 전류 <span className="dim">정격 대비 % · {basis === "line" ? `선전류(케이블, 정격 ${el.rated_line_A} A)` : `상전류(권선, 정격 ${el.rated_phase_A} A)`}</span>
        <span className="grow" /><span className="dim">I₂/I₁ {ts.i2_over_i1[i].toFixed(3)}</span></div>
      <div className="cbars-body">
        <div className="cbars-plot-wrap">
        <div className="cbars-plot">
          {bands.map((b) => (
            <div key={b.s} className="band" style={{ bottom: y(b.from), height: `calc(${y(b.to)} - ${y(b.from)})`, background: `rgba(${el.status_rgb[b.s].map((c) => Math.round(c * 255)).join(",")},0.16)` }}
                 title={`${el.status_labels[b.s]}: ${A(b.from)}~${b.to >= maxR ? "" : A(b.to)} A`}>
              <span className="band-l">{ELEC_ICON[b.s]} {el.status_labels[b.s].replace("(결상 의심)", "")} {b.s === "normal" ? `${A(b.from)}~${A(b.to)} A` : b.s.startsWith("over") ? `> ${A(b.from)} A` : `< ${A(b.to)} A`}</span>
            </div>
          ))}
          <div className="rated" style={{ bottom: y(1) }}><span>정격 100 % = {A(1)} A</span></div>
          {PHASES.map((p) => {
            const r = ts.ratio[p][i], s = ts.current_status[p][i];
            const isF = focus.includes(p);
            return (
              <div key={p} className={"bar-col" + (isF ? " focus" : focus.length ? " dim" : "")}>
                <div className="bar-val" style={{ bottom: y(r) }}>
                  <b style={{ color: el.status_colors[s] }}>{ELEC_ICON[s]} {A(r)} A</b>
                  <span>{Math.round(r * 100)} %</span>
                </div>
                <div className="bar" style={{ height: y(r), background: el.status_colors[s] }} />
                <div className="bar-name" style={{ borderColor: `rgb(${el.phase_colors[p].map((c) => Math.round(c * 255)).join(",")})` }}>{p}상</div>
              </div>
            );
          })}
        </div>
        </div>
        <CurrentTrend data={data} basis={basis} focus={focus} />
      </div>
    </div>
  );
}
