import type { FleetIndex, GaugeSpec, Level } from "./data";
import { levelOf } from "./data";

// 신호 게이지 (TASK_다중모터 §7.2): 현재값을 안전/경고/위험 구간 띠 위에 마커로 보여준다.
// 구간 경계는 GaugeSpec(모터별 진동 규격·정격 전류 반영)에서만 온다. 색 + 아이콘 병기.
export interface Marker { key: string; value: number }
export function Gauge({ index, title, unit, spec, value, markers, note, judged, badge, titleTip }: {
  index: FleetIndex; title: string; unit: string; spec: GaugeSpec;
  badge?: { text: string; title: string };     // P1 참고 배지 (회색 테두리) — provisional 지표
  titleTip?: string;                            // 제목 툴팁 (예: 열회로 스케일 주의)
  value: number;                       // 대표값 (등급·숫자 표시)
  markers?: Marker[];                  // 여러 마커 (상별 전류). 없으면 value 하나
  note?: string;                       // 작은 보조 문구 (규격 이름 등)
  judged?: Level;                      // 판정 엔진의 등급(히스테리시스·지속 적용). 현재값 등급과 다르면 함께 보여준다
}) {
  const span = spec.max - spec.min;
  const pos = (x: number) => `${Math.max(0, Math.min(100, ((x - spec.min) / span) * 100))}%`;
  const lv = levelOf(spec, value);
  const col = index.colors[lv];
  const fmt = (x: number) => (Math.abs(x) < 1 ? x.toFixed(3) : Math.abs(x) < 10 ? x.toFixed(2) : x.toFixed(1));
  return (
    <div className="g-row" title={spec.threshold}>
      <div className="g-head">
        <span className="g-title" title={titleTip}>{title}</span>
        {badge && <span className="g-prov" title={badge.title}>{badge.text}</span>}
        <span className="g-val" style={{ color: col }}>{index.icons[lv]} {fmt(value)}{unit && <small> {unit}</small>}</span>
        <span className="g-lv" style={{ background: col }}>{index.labels_ko[lv]}</span>
        {judged && judged !== lv && <span className="g-judged" title="판정 엔진 등급 (히스테리시스·지속 시간 적용)">판정 {index.labels_ko[judged]}</span>}
      </div>
      {note && <div className="g-note">{note}</div>}
      <div className="g-bar">
        {spec.segments.map((s, n) => (
          <i key={n} className={"seg " + s.level} style={{ left: pos(s.from), width: `calc(${pos(s.to)} - ${pos(s.from)})`, background: index.colors[s.level] }}>
            {s.label && <em>{s.label}</em>}
          </i>
        ))}
        {spec.ticks?.map((tk) => <b key={tk.label} className="tick" style={{ left: pos(tk.at) }} title={`${tk.label} ${tk.at}`}><span>{tk.label}</span></b>)}
        {(markers ?? [{ key: "", value }]).map((m) => (
          <u key={m.key} className="mk" style={{ left: pos(m.value) }} title={`${m.key} ${fmt(m.value)}`}>{m.key && <span>{m.key}</span>}</u>
        ))}
      </div>
      <div className="g-foot">
        {spec.segments.filter((s) => s.level !== "DANGER" || s.from < spec.max).map((s, n) => (
          <span key={n} className="g-seg-l" style={{ left: pos(s.from) }}>{n === 0 ? "" : fmt(s.from)}</span>
        ))}
      </div>
    </div>
  );
}
