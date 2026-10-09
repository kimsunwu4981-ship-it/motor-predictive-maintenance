import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadModeData, type ModeData } from "../data";
import { PlaybackContext, usePlaybackController } from "../state/playback";
import { VideoPanel } from "../components/VideoPanel";
import { loadElecData, type Basis, type ElecData, type Phase } from "../elec/data";
import { HUDElec } from "../elec/HUDElec";
import { CurrentBars } from "../elec/CurrentBars";
import { CauseElec } from "../elec/Panels";
import { I2I1Panel } from "../elec/I2I1Panel";
import { PhasorPanel } from "../elec/PhasorPanel";
import { CircuitSchematic } from "../elec/CircuitSchematic";
import { LiveNarration } from "../live/LiveNarration";
import { CaptionBar } from "../live/CaptionBar";
import { QaDrawer } from "../live/QaDrawer";
import { autoLevel, buildClusters, buildHistory, captionAt, sceneCaptionAt } from "../live/captions";
import { openChannel, type MainState, type Msg } from "../live/broadcast";
import { useLiveSession } from "../live/session";
import { LiveToggle, LiveBanner } from "../live/LiveToggle";
import { ControlPanel } from "../live/ControlPanel";
import { LiveVideoPanel } from "../live/LiveVideoPanel";
import { liveHistory, revealLevel, toElecData, useLivePlayback } from "../live/livedata";
import { REVEAL_LABEL } from "../live/captions";
import { loadFleetIndex, type FleetIndex } from "../status/data";
import "../mech/schematic.css";   /* 공통 레이아웃(.dash.live)·자막·해설·Q 서랍 규칙 */
import "../elec/elec.css";

// 전기적 결함 실시간 해설 대시보드 (TASK_전기실시간해설). 기계 대시보드(MechanicalLive)와 같은 골격, 공통 부분은 live/ 에서.
// 이전 전기 대시보드(ModeDashboard: 기준표·결함 도감·용어 풀이 탭)는 #/electrical/classic 에 그대로 남긴다.
export function ElectricalLive() {
  const [data, setData] = useState<ElecData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    loadModeData("electrical").then((base: ModeData) => loadElecData(base)).then(setData).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div style={{ padding: 30 }}>데이터를 읽지 못했습니다.<br /><code>{err}</code></div>;
  if (!data) return <div style={{ padding: 30 }} className="muted">불러오는 중…</div>;
  return <Inner data={data} />;
}

function Inner({ data: data0 }: { data: ElecData }) {
  const live = useLiveSession();
  const [fleet, setFleet] = useState<FleetIndex | null>(null);
  useEffect(() => { if (live.enabled && !fleet) loadFleetIndex().then(setFleet).catch(() => undefined); }, [live.enabled, fleet]);
  const liveData = useMemo(() => (live.active ? toElecData(data0, live.buffer, fleet) : null), [live.active, live.version, live.buffer, data0, fleet]);  // eslint-disable-line react-hooks/exhaustive-deps
  const data = liveData ?? data0;
  const pbRec = usePlaybackController(data0.scenarios);
  const pbLive = useLivePlayback(live.buffer, live.version, data.scenarios.steps, live.send);
  const pb = liveData ? pbLive : pbRec;
  const [present, setPresent] = useState(false);
  const [autoMode, setAutoMode] = useState(true);
  const [captions, setCaptions] = useState(true);
  const [ctl, setCtl] = useState(() => new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("ctl") === "1");                // K 키: 제어 패널 (라이브)
  const [qa, setQa] = useState(() => new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("qa") === "1");
  const [basis, setBasis] = useState<Basis>("line");       // 선전류(케이블) / 상전류(권선) — TASK 5.1 토글
  const [phasorBig, setPhasorBig] = useState(false);       // P 키: 페이저도 확대 보기 (TASK 7)
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try { return (localStorage.getItem("vigent-theme") as "dark" | "light") || "dark"; } catch { return "dark"; }
  });
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); try { localStorage.setItem("vigent-theme", theme); } catch { /* */ } }, [theme]);

  const step = data.scenarios.steps[pb.stepIndex];
  const scene = data.content.scenes[step.id];
  const focus: Phase[] = scene?.focus_phases ?? [];        // 장면별 "지금 주목할 것" (config)

  // 해설 단계 공개: 자동 해설 모드는 reveal_timing, 발표자 모드는 N 키
  const [manual, setManual] = useState<{ scene: string; level: number }>({ scene: step.id, level: 0 });
  const manualLevel = manual.scene === step.id ? manual.level : 0;
  const level = liveData && autoMode ? revealLevel(live.last) : autoMode ? (scene ? autoLevel(scene, step, pb.t) : 3) : manualLevel;
  const nextLevel = useCallback(() => { if (!autoMode) setManual({ scene: step.id, level: Math.min(3, manualLevel + 1) }); }, [autoMode, step.id, manualLevel]);

  const clusters = useMemo(() => buildClusters(data.events.filter((e) => e.type !== "reveal")), [data.events]);
  const history = useMemo(() => (liveData ? liveHistory(data.events, data.content.templates, (e) => `${REVEAL_LABEL[e.reveal as keyof typeof REVEAL_LABEL] ?? e.reveal} 공개`) : buildHistory(data, clusters)), [data, clusters, liveData]);
  const cap = useMemo(() => captionAt(clusters, pb.t), [clusters, pb.t]);
  const sceneCap = useMemo(() => sceneCaptionAt(data.events, pb.t, data.content.templates), [data.events, data.content.templates, pb.t]);

  // 발표자 화면과 상태 공유 (live/broadcast)
  const chan = useMemo(() => openChannel("electrical"), []);
  const stateRef = useRef<MainState | null>(null);
  stateRef.current = { kind: "state", t: pb.t, playing: pb.playing, stepIndex: pb.stepIndex, level, autoMode, captions, at: Date.now() };
  const lastPost = useRef(0);
  useEffect(() => {
    if (!chan) return;
    const now = performance.now();
    if (pb.playing && now - lastPost.current < 200) return;
    lastPost.current = now;
    chan.postMessage(stateRef.current);
  }, [chan, pb.t, pb.playing, pb.stepIndex, level, autoMode, captions]);
  useEffect(() => {
    if (!chan) return;
    const on = (e: MessageEvent<Msg>) => {
      const m = e.data;
      if (m?.kind === "hello") chan.postMessage({ ...stateRef.current, at: Date.now() });
      else if (m?.kind === "cmd") {
        if (m.cmd === "toggle") pb.toggle();
        else if (m.cmd === "goto" && m.n) pb.gotoStep(m.n);
        else if (m.cmd === "seek" && typeof m.t === "number") pb.seek(m.t);
        else if (m.cmd === "nextStep") pb.gotoStep(pb.stepIndex + 2);
        else if (m.cmd === "prevStep") pb.gotoStep(pb.stepIndex);
        else if (m.cmd === "nextLevel") nextLevel();
      }
    };
    chan.addEventListener("message", on);
    return () => chan.removeEventListener("message", on);
  }, [chan, pb, nextLevel]);
  useEffect(() => {
    if (!chan) return;
    const h = setInterval(() => { if (stateRef.current) chan.postMessage({ ...stateRef.current, at: Date.now() }); }, 1000);
    return () => clearInterval(h);
  }, [chan]);
  useEffect(() => () => chan?.close(), [chan]);
  const openPresenter = () => window.open(window.location.href.split("#")[0] + "#/electrical/presenter", "vigent-presenter-electrical");

  const togglePresent = () => setPresent((p) => {
    const next = !p;
    try { if (next && !document.fullscreenElement) document.documentElement.requestFullscreen?.(); else if (!next && document.fullscreenElement) document.exitFullscreen?.(); } catch { /* */ }
    return next;
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === " ") { e.preventDefault(); pb.toggle(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); pb.gotoStep(pb.stepIndex + 2); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); pb.gotoStep(pb.stepIndex); }
      else if (e.key === "f" || e.key === "F") togglePresent();
      else if (e.key === "c" || e.key === "C") setCaptions((c) => !c);
      else if (e.key === "q" || e.key === "Q") setQa((q) => !q);
      else if (e.key === "n" || e.key === "N") nextLevel();
      else if (e.key === "k" || e.key === "K") setCtl((c) => !c);
      else if (e.key === "l" || e.key === "L") setBasis((b) => (b === "line" ? "phase" : "line"));
      else if (e.key === "p" || e.key === "P") setPhasorBig((b) => !b);
      else if (e.key === "Escape" && phasorBig) setPhasorBig(false);
      else if (e.key === "Escape" && present) setPresent(false);
      else if (e.key >= "1" && e.key <= "9") pb.gotoStep(Number(e.key));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  useEffect(() => {
    const on = () => { if (!document.fullscreenElement) setPresent(false); };
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  return (
    <PlaybackContext.Provider value={pb}>
      <div className={"dash live elec" + (present ? " present" : "")}>
        <HUDElec data={data} theme={theme} onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
                 present={present} onPresent={togglePresent} autoMode={autoMode} onAutoMode={() => setAutoMode((a) => !a)}
                 captions={captions} onCaptions={() => setCaptions((c) => !c)} qa={qa} onQa={() => setQa((q) => !q)} onPresenter={openPresenter}
                 basis={basis} onBasis={() => setBasis((b) => (b === "line" ? "phase" : "line"))} extra={<><LiveToggle live={live} compact />{live.enabled && <button className="b-ctl" onClick={() => setCtl((c) => !c)} title="K 키: 제어 패널">{ctl ? "☑ 제어 K" : "☐ 제어 K"}</button>}</>} banner={<LiveBanner live={live} index={fleet} />} />
        <div className="live-main">
          {liveData ? <LiveVideoPanel data={data} live={live} overlay={captions ? <CaptionBar scene={sceneCap} cap={cap} tpl={data.content.templates} /> : null} />
                    : <VideoPanel data={data} overlay={captions ? <CaptionBar scene={sceneCap} cap={cap} tpl={data.content.templates} /> : null} />}
          <div className="live-side">
            <LiveNarration data={data} level={level} history={history} />
            <CircuitSchematic data={data} focus={focus} />
          </div>
        </div>
        <div className="live-bottom">
          <CurrentBars data={data} basis={basis} focus={focus} />
          <I2I1Panel data={data} focus={!!scene?.focus_i2i1} />
          <PhasorPanel data={data} basis={basis} focus={focus} big={phasorBig} onToggleBig={() => setPhasorBig((b) => !b)} />
          <CauseElec data={data} />
        </div>
        <QaDrawer data={data} open={qa} onClose={() => setQa(false)} />
        <ControlPanel live={live} open={ctl} onClose={() => setCtl(false)} />
      </div>
    </PlaybackContext.Provider>
  );
}
