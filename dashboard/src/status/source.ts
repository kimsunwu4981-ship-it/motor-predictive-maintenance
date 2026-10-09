// status/source.ts — 상태 보드 데이터 소스 추상화 (TASK_다중모터 §8 P5 "실측 스트림 입력 — 데이터 소스 추상화만 미리").
//
// 보드는 StatusSource 인터페이스만 안다. 지금은 ReplaySource(엔진 배치 JSON) 하나가 실제로 동작하고,
// LiveSource 는 실측 스트림이 붙을 때 채울 자리다 — 같은 JSON 형태(index.json, <id>_<mode>.json)를 HTTP 로 주고
// 선택적으로 Server-Sent Events(`<url>/events`) 로 새 샘플을 밀어 넣는 계약만 정해 둔다. 판정은 어느 쪽이든 서버(엔진)가 한다.
//   #/status?live=http://host:port/fleet   → LiveSource (URL 아래 index.json 등을 읽는다)
import type { Mode } from "../data";
import { loadFleetIndex, loadSeries, type FleetIndex, type MotorSeries } from "./data";
import { getJson } from "../live/load";

export interface LiveSample {           // 스트림 한 샘플 (append 용). 시계열 JSON 의 한 행과 같은 의미
  motor: string; mode: Mode; t: number; status: string; cause_signal: string; cause_component: string; cause_value: number;
  temperature_C: Record<string, number>; current_rms_A: Record<string, number>; i2i1: number; vibration_mms: number; bearing_kurtosis: number; bearing_hf_ratio: number;
  bearing_site_hint?: string | null;                 // 결함 부위 추정 (포락선 BPFO/BPFI, 베어링 번호 아는 모터만) — 판정에 쓰지 않음
}
export interface StatusSource {
  kind: "replay" | "live";
  label: string;                                       // 상단 정직성 라벨 옆에 보여줄 출처
  loadIndex(): Promise<FleetIndex>;
  loadSeries(index: FleetIndex, id: string, mode: Mode): Promise<MotorSeries>;
  subscribe?(onSample: (s: LiveSample) => void): () => void;   // 라이브만. 해제 함수를 돌려준다
}

export class ReplaySource implements StatusSource {
  kind = "replay" as const;
  label = "엔진 배치 로그 재생 (logs/fleet)";
  loadIndex() { return loadFleetIndex(); }
  loadSeries(index: FleetIndex, id: string, mode: Mode) { return loadSeries(index, id, mode); }
}

export class LiveSource implements StatusSource {
  kind = "live" as const;
  label: string;
  constructor(private base: string) { this.label = `실측 스트림 ${base}`; }
  loadIndex() { return getJson<FleetIndex>(`${this.base}/index.json`); }
  loadSeries(index: FleetIndex, id: string, mode: Mode) {
    const m = index.motors.find((x) => x.id === id);
    if (!m) throw new Error(`모터 ${id} 가 index.json 에 없다`);
    return getJson<MotorSeries>(`${this.base}/${m.files[mode]}`);
  }
  subscribe(onSample: (s: LiveSample) => void) {
    if (typeof EventSource === "undefined") return () => undefined;
    const es = new EventSource(`${this.base}/events`);
    es.onmessage = (e) => { try { onSample(JSON.parse(e.data) as LiveSample); } catch { /* 형식이 다르면 무시 */ } };
    return () => es.close();
  }
}

export function pickSource(params: URLSearchParams): StatusSource {
  const live = params.get("live");
  // ws:// 는 라이브 세션(live/session.ts, WebSocket) 이 맡는다 — 여기서는 HTTP(+SSE) 계약의 실측 소스만 (R2 이후 둘 다 가능)
  return live && /^https?:/.test(live) ? new LiveSource(live.replace(/\/$/, "")) : new ReplaySource();
}

// 라이브 샘플을 시계열 끝에 붙인다 (불변 갱신). 메모리 상한은 호출자가 정한다.
export function appendSample(s: MotorSeries, x: LiveSample, ratedLineA: number, maxN = 20000): MotorSeries {
  const cut = <T,>(a: T[]) => (a.length >= maxN ? a.slice(a.length - maxN + 1) : a);
  const out: MotorSeries = {
    ...s, n: Math.min(s.n + 1, maxN),
    t: [...cut(s.t), x.t], step: [...cut(s.step), "live"], time_scale: [...cut(s.time_scale), 1],
    temperature_C: Object.fromEntries(Object.keys(s.temperature_C).map((k) => [k, [...cut(s.temperature_C[k]), x.temperature_C[k] ?? NaN]])),
    current_rms_A: { A: [...cut(s.current_rms_A.A), x.current_rms_A.A ?? NaN], B: [...cut(s.current_rms_A.B), x.current_rms_A.B ?? NaN], C: [...cut(s.current_rms_A.C), x.current_rms_A.C ?? NaN] },
    current_ratio: { A: [...cut(s.current_ratio.A), (x.current_rms_A.A ?? NaN) / ratedLineA], B: [...cut(s.current_ratio.B), (x.current_rms_A.B ?? NaN) / ratedLineA], C: [...cut(s.current_ratio.C), (x.current_rms_A.C ?? NaN) / ratedLineA] },
    i2i1: [...cut(s.i2i1), x.i2i1], vibration_mms: [...cut(s.vibration_mms), x.vibration_mms],
    bearing_kurtosis: [...cut(s.bearing_kurtosis), x.bearing_kurtosis], bearing_hf_ratio: [...cut(s.bearing_hf_ratio), x.bearing_hf_ratio],
    bearing_site_hint: [...cut(s.bearing_site_hint ?? s.t.map(() => null)), x.bearing_site_hint ?? null],
    status: [...cut(s.status), x.status as MotorSeries["status"][number]], cause_signal: [...cut(s.cause_signal), x.cause_signal],
    cause_component: [...cut(s.cause_component), x.cause_component], cause_value: [...cut(s.cause_value), x.cause_value],
    cause_threshold: [...cut(s.cause_threshold), ""],
    levels: Object.fromEntries(Object.keys(s.levels).map((k) => [k, [...cut(s.levels[k as keyof typeof s.levels] ?? []), "SAFE"]])) as MotorSeries["levels"],
  };
  return out;
}
