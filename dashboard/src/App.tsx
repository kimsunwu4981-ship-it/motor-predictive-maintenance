import { LiveBoard } from "./pages/LiveBoard";

// 2026-10-27 레이아웃 A: 대시보드는 실시간 전기 상태 보드 하나다 (#/status). 녹화 재생·해설(#/mechanical, #/electrical)·발표자 화면·전문가 보기는
// src/_legacy/ 로 옮겨 빌드에서 뺐다 (삭제 아님 — tsconfig exclude, 라우트 없음). 어떤 해시로 열어도 같은 보드가 뜬다.
export function App() {
  if (!window.location.hash.startsWith("#/status")) window.location.replace("#/status" + (window.location.hash.includes("?") ? "?" + window.location.hash.split("?")[1] : ""));
  return <LiveBoard />;
}
