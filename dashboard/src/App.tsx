import { useEffect, useState } from "react";
import { Landing } from "./pages/Landing";
import { ModeDashboard } from "./pages/ModeDashboard";
import { MechanicalLive } from "./pages/MechanicalLive";
import { ElectricalLive } from "./pages/ElectricalLive";
import { PresenterView } from "./pages/PresenterView";
import { StatusBoard } from "./pages/StatusBoard";

// 해시 라우팅 — 정적 서버·file:// 어디서든 동작한다.
//   #/mechanical            기계 실시간 해설 대시보드      #/mechanical/presenter  발표자 화면
//   #/electrical            전기 실시간 해설 대시보드      #/electrical/presenter  발표자 화면
//   #/status                모터 5종 상태 보드 (다중 모터, 판정 엔진)
//   #/electrical/classic    이전 전기 대시보드 (기준표·결함 도감·용어 풀이 탭) — 참고용으로 남긴다
// 한 화면에는 한 가지 결함 유형만 나온다.
type Route = "mechanical" | "electrical" | "mechanical/presenter" | "electrical/presenter" | "electrical/classic" | "status";
const ROUTES: Route[] = ["mechanical", "electrical", "mechanical/presenter", "electrical/presenter", "electrical/classic", "status"];
function readRoute(): Route | null {
  const h = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  return (ROUTES as string[]).includes(h) ? (h as Route) : null;
}

export function App() {
  const [route, setRoute] = useState<Route | null>(readRoute());
  useEffect(() => {
    const on = () => setRoute(readRoute());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  if (!route) return <Landing />;
  // key 로 모드 전환 시 상태를 완전히 새로 만든다.
  if (route === "status") return <StatusBoard key={route} />;
  if (route === "mechanical/presenter") return <PresenterView key={route} mode="mechanical" />;
  if (route === "electrical/presenter") return <PresenterView key={route} mode="electrical" />;
  if (route === "electrical/classic") return <ModeDashboard key={route} mode="electrical" />;
  if (route === "mechanical") return <MechanicalLive key={route} />;
  return <ElectricalLive key={route} />;
}
