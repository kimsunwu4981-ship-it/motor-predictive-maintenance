import type { ModeData } from "../data";

// 설명 문구는 여기(src/content)에만 둔다. 발표자가 코드 구조를 몰라도 고칠 수 있게 하기 위함이다.
// 숫자는 절대 직접 쓰지 않고 ModeData(JSON) 에서 꺼내 문장에 끼운다.
export interface ChapterText { see: string; why: string; act: string }
export interface FaultCardText {
  key: string; name: string; easy: string; cause: string; seen: string; criteria: string;
  ifIgnored: string; action: string; signals: string[]; stepId?: string;
}
export interface GlossaryEntry { term: string; body: string }
export interface ModeContent {
  chapter: (stepId: string, d: ModeData, i: number) => ChapterText;
  faultCards: (d: ModeData) => FaultCardText[];
  glossary: (d: ModeData) => GlossaryEntry[];
  partReason?: (partKey: string) => string;
}
