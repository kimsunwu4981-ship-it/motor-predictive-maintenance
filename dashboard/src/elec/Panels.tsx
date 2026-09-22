import { usePlayback } from "../state/playback";
import { fill } from "../live/types";
import { idxAt, PHASES, type Basis, type ElecData, type Phase } from "./data";

// E2 골격용 패널 — E3(게이지·페이저·회로도)·E4(판별 매트릭스)에서 본 구현으로 바뀐다. 숫자는 전부 로그 값이다.

export function I2I1Panel({ data }: { data: ElecData }) {
  const { t } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const v = ts.i2_over_i1[i];
  const normal = el.i2i1_marks.find((m) => m.case === "healthy")?.value ?? 0;
  return (
    <div className="panel i2i1">
      <div className="panel-h">균형 지표 I₂/I₁ <span className="dim">역상분 비율</span></div>
      <div className="panel-b">
        <div className="big">{v.toFixed(3)}</div>
        <div className="dim">정상 {normal} 의 {normal > 0 ? (v / normal).toFixed(1) : "-"}배</div>
        <div className="marks">{el.i2i1_marks.map((m) => <span key={m.case} className={v >= m.value && m.case !== "healthy" ? "hit" : ""}>{m.label} {m.value}</span>)}</div>
        <div className="dim" style={{ marginTop: 8 }}>게이지·추세 — E3</div>
      </div>
    </div>
  );
}

export function PhasorPanel({ data, basis }: { data: ElecData; basis: Basis }) {
  const { t } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const rated = basis === "line" ? el.rated_line_A : el.rated_phase_A;
  return (
    <div className="panel phasor">
      <div className="panel-h">페이저도 <span className="dim">길이 = 크기, 각도 = 위상</span></div>
      <div className="panel-b">
        {PHASES.map((p) => <div key={p}>{p}상 {(ts.ratio[p][i] * rated).toFixed(1)} A ∠ {ts.phasor_deg[p][i].toFixed(0)}°</div>)}
        <div className="dim" style={{ marginTop: 8 }}>세 화살표의 길이와 간격이 같으면 균형, 일그러질수록 I₂/I₁ 이 커집니다. (그림 — E3)</div>
      </div>
    </div>
  );
}

export function CircuitSchematic({ data, focus }: { data: ElecData; focus: Phase[] }) {
  const { t, stepIndex } = usePlayback();
  const ts = data.timeseries, el = data.thresholds.electrical;
  const i = idxAt(ts, t);
  const scene = data.content.scenes[data.scenarios.steps[stepIndex].id];
  return (
    <div className="panel circuit">
      <div className="panel-h">회로 안내 <span className="dim">전원 → 케이블 → Δ권선 · 색은 영상과 같은 상태색</span>
        <span className="grow" /><span className="dim">주목 {focus.length ? focus.join("·") + "상" : "I₂/I₁"}</span></div>
      <div className="panel-b">
        {PHASES.map((p) => (
          <div key={p} style={{ color: el.status_colors[ts.current_status[p][i]] }}>
            {p}상 케이블 {ts.current_rms_A[p][i].toFixed(1)} A → 권선 {ts.phase_rms_A[p][i].toFixed(1)} A · {el.status_labels[ts.current_status[p][i]]}
          </div>
        ))}
        {scene?.circuit?.short_loop && <div className="dim">단락 루프 표시: {scene.circuit.short_loop}상 권선 (시각적 표시)</div>}
        {scene?.circuit?.open_phase && <div className="dim">끊어진 상: {scene.circuit.open_phase}</div>}
        {scene?.circuit?.voltage_note && <div className="dim">{scene.circuit.voltage_note}</div>}
        <div className="dim" style={{ marginTop: 8 }}>회로도 SVG · 입자 — E3</div>
      </div>
    </div>
  );
}

export function CauseElec({ data }: { data: ElecData }) {
  const { stepIndex } = usePlayback();
  const step = data.scenarios.steps[stepIndex];
  const scene = data.content.scenes[step.id];
  const v = data.values[step.id];
  const cc = scene?.cause_chain;
  return (
    <div className="panel cause">
      <div className="panel-h">원인 → 메커니즘 → 결과 → 조치 <span className="grow" /><span className="dim">지문: {scene?.fingerprint}</span></div>
      <div className="panel-b">
        {cc ? (
          <div className="chain fade" key={step.id}>
            {(["cause", "mechanism", "effect", "action"] as const).map((k, n) => (
              <div key={k} className={"chain-card c" + n}>
                <div className="chain-k">{["원인", "메커니즘", "결과", "조치"][n]}</div>
                <div>{fill(cc[k], v)}</div>
              </div>
            ))}
          </div>
        ) : <div className="muted">narration.yaml 의 cause_chain 없음</div>}
        <div className="dim" style={{ marginTop: 8 }}>결함 판별 매트릭스 (크기 × 균형) — E4</div>
      </div>
    </div>
  );
}
