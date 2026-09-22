import { useEffect, useState } from "react";
import { Landing } from "./pages/Landing";
import { ModeDashboard } from "./pages/ModeDashboard";
import { MechanicalLive } from "./pages/MechanicalLive";
import { PresenterView } from "./pages/PresenterView";
import type { Mode } from "./data";

// 해시 라우팅: #/mechanical, #/electrical, #/mechanical/presenter(발표자 화면). 정적 서버·file:// 어디서든 동작한다.
// 한 화면에는 한 가지 결함 유형만 나온다 — 두 대시보드는 데이터·콘텐츠만 다르고 컴포넌트는 공유한다.
type Route = Mode | "presenter";
function readRoute(): Route | null {
  const h = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  if (h === "mechanical/presenter") return "presenter";
  return h === "mechanical" || h === "electrical" ? h : null;
}

export function App() {
  const [route, setRoute] = useState<Route | null>(readRoute());
  useEffect(() => {
    const on = () => setRoute(readRoute());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  if (!route) return <Landing />;
  // 기계는 실시간 해설 대시보드, 전기는 기존 대시보드. key 로 모드 전환 시 상태를 완전히 새로 만든다.
  if (route === "presenter") return <PresenterView key={route} />;
  if (route === "mechanical") return <MechanicalLive key={route} />;
  return <ModeDashboard key={route} mode={route} />;
}
