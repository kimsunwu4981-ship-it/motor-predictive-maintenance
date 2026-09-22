// live/broadcast.ts — 메인(심사위원) 화면 ↔ 발표자 화면 재생 상태 공유 (TASK 7.2, 공용).
// BroadcastChannel 은 같은 브라우저의 창끼리 오프라인으로 통신한다. 메인이 상태를 보내고, 발표자 화면은 명령을 보낸다.
// 채널 이름은 모드별 — 기계 메인과 전기 발표자 화면이 섞이지 않는다.
// 멘트(presenter_line)는 발표자 화면이 자기 데이터로 그리므로 메인 화면으로는 절대 가지 않는다.
import type { Mode } from "./types";

export interface MainState {
  kind: "state"; t: number; playing: boolean; stepIndex: number; level: number; autoMode: boolean; captions: boolean; at: number;
}
export type CmdName = "toggle" | "goto" | "seek" | "nextLevel" | "nextStep" | "prevStep";
export interface Cmd { kind: "cmd"; cmd: CmdName; n?: number; t?: number }
export interface Hello { kind: "hello" }
export type Msg = MainState | Cmd | Hello;

export function openChannel(mode: Mode): BroadcastChannel | null {
  try { return new BroadcastChannel(`vigent-${mode}`); } catch { return null; }
}
