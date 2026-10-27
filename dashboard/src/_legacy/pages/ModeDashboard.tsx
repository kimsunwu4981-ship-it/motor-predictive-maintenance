import { useEffect, useState } from "react";
import { loadModeData, type Mode, type ModeData } from "../../data";
import { PlaybackContext, usePlaybackController } from "../../state/playback";
import { HUDBar } from "../../components/HUDBar";
import { VideoPanel } from "../../components/VideoPanel";
import { ExplainPanel } from "../../components/ExplainPanel";
import { SyncedCharts } from "../../components/SyncedCharts";
import { ThresholdTable } from "../../components/ThresholdTable";
import { FaultCards } from "../../components/FaultCards";
import { Glossary } from "../../components/Glossary";
import { CONTENT } from "../../content";

type Tab = "table" | "faults" | "glossary";

export function ModeDashboard({ mode }: { mode: Mode }) {
  const [data, setData] = useState<ModeData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    loadModeData(mode).then(setData).catch((e) => setErr(String(e)));
  }, [mode]);
  if (err) return <div style={{ padding: 30 }}>데이터를 읽지 못했습니다.<br /><code>{err}</code></div>;
  if (!data) return <div style={{ padding: 30 }} className="muted">불러오는 중…</div>;
  return <Inner mode={mode} data={data} />;
}

function Inner({ mode, data }: { mode: Mode; data: ModeData }) {
  const pb = usePlaybackController(data.scenarios);
  // ?tab=table|faults|glossary 로 하단 탭을 지정해 열 수 있다 (스크린샷·발표 준비용)
  const [tab, setTab] = useState<Tab>(() => {
    const q = window.location.hash.split("?")[1];
    const v = q ? new URLSearchParams(q).get("tab") : null;
    return v === "faults" || v === "glossary" ? v : "table";
  });
  const [present, setPresent] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try { return (localStorage.getItem("vigent-theme") as "dark" | "light") || "dark"; } catch { return "dark"; }
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("vigent-theme", theme); } catch { /* 저장 불가 환경 */ }
  }, [theme]);

  // 발표 모드: 전체화면 + 글자 확대 + 하단 탭 숨김. 마우스 없이 진행할 수 있어야 한다.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === " ") { e.preventDefault(); pb.toggle(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); pb.gotoStep(pb.stepIndex + 2); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); pb.gotoStep(pb.stepIndex); }
      else if (e.key === "f" || e.key === "F") { togglePresent(); }
      else if (e.key === "Escape" && present) { setPresent(false); }
      else if (e.key >= "1" && e.key <= "9") { pb.gotoStep(Number(e.key)); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  const togglePresent = () => {
    setPresent((p) => {
      const next = !p;
      try {
        if (next && !document.fullscreenElement) document.documentElement.requestFullscreen?.();
        else if (!next && document.fullscreenElement) document.exitFullscreen?.();
      } catch { /* 전체화면 불가 환경 */ }
      return next;
    });
  };
  useEffect(() => {
    const on = () => { if (!document.fullscreenElement) setPresent(false); };
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const content = CONTENT[mode];
  return (
    <PlaybackContext.Provider value={pb}>
      <div className={"dash" + (present ? " present" : "")}>
        <HUDBar mode={mode} data={data} theme={theme} onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
                present={present} onPresent={togglePresent} />
        <div className="row-main">
          <VideoPanel data={data} />
          <ExplainPanel data={data} content={content} />
        </div>
        <SyncedCharts mode={mode} data={data} />
        <div className="panel tabs">
          <div className="tabbar">
            <button className={tab === "table" ? "on" : ""} onClick={() => setTab("table")}>색상 기준표</button>
            <button className={tab === "faults" ? "on" : ""} onClick={() => setTab("faults")}>결함 도감</button>
            <button className={tab === "glossary" ? "on" : ""} onClick={() => setTab("glossary")}>용어 풀이</button>
            <span className="grow" />
            <span className="dim" style={{ alignSelf: "center" }}>
              <span className="kbd">F</span> 발표 모드 · <span className="kbd">Space</span> 재생/정지 · <span className="kbd">←</span><span className="kbd">→</span> 챕터
            </span>
          </div>
          <div className="tabbody">
            {tab === "table" && <ThresholdTable mode={mode} data={data} />}
            {tab === "faults" && <FaultCards mode={mode} data={data} content={content} />}
            {tab === "glossary" && <Glossary data={data} content={content} />}
          </div>
        </div>
      </div>
    </PlaybackContext.Provider>
  );
}
