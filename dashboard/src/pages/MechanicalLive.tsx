import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadModeData, type ModeData } from "../data";
import { PlaybackContext, usePlaybackController } from "../state/playback";
import { VideoPanel } from "../components/VideoPanel";
import { loadMechData, type MechData } from "../mech/data";
import { HUDLive } from "../mech/HUDLive";
import { TempChart, TEMP_DEFAULT_ON } from "../mech/TempChart";
import { LiveNarration } from "../live/LiveNarration";
import { MotorSchematic } from "../mech/MotorSchematic";
import { CausePanel } from "../mech/CausePanel";
import { VibChart } from "../mech/VibChart";
import { CaptionBar } from "../live/CaptionBar";
import { QaDrawer } from "../live/QaDrawer";
import { autoLevel, buildClusters, buildHistory, captionAt, sceneCaptionAt } from "../live/captions";
import { openChannel, type MainState, type Msg } from "../live/broadcast";
import "../mech/schematic.css";

// 기계적 결함 실시간 해설 대시보드 (TASK_기계실시간해설). 전기 대시보드(ModeDashboard)는 그대로 둔다.
// 재생 스토어·VideoPanel·테마·발표 모드·키보드는 기존 것을 재사용한다.
export function MechanicalLive() {
  const [data, setData] = useState<MechData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    loadModeData("mechanical").then((base: ModeData) => loadMechData(base)).then(setData).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div style={{ padding: 30 }}>데이터를 읽지 못했습니다.<br /><code>{err}</code></div>;
  if (!data) return <div style={{ padding: 30 }} className="muted">불러오는 중…</div>;
  return <Inner data={data} />;
}

function Inner({ data }: { data: MechData }) {
  const pb = usePlaybackController(data.scenarios);
  const [present, setPresent] = useState(false);
  const [autoMode, setAutoMode] = useState(true);       // 자동 해설 / 발표자 모드 (TASK 7.1)
  const [captions, setCaptions] = useState(true);       // C 키: 자막 켜기/끄기
  const [qa, setQa] = useState(() => new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("qa") === "1");   // Q 키: 예상 질문 서랍 (?qa=1 로 열린 채 시작)
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try { return (localStorage.getItem("vigent-theme") as "dark" | "light") || "dark"; } catch { return "dark"; }
  });
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); try { localStorage.setItem("vigent-theme", theme); } catch { /* */ } }, [theme]);

  // 주목 부품: 장면 config(narration.yaml focus_component). 사용자가 칩을 눌러 잠시 다른 부품을 볼 수도 있지만
  // 장면이 바뀌면 다시 config 값으로 돌아온다.
  const step = data.scenarios.steps[pb.stepIndex];
  const scene = data.content.scenes[step.id];
  const cfgFocus = scene?.focus_component ?? "bearing_de";
  const [override, setOverride] = useState<{ scene: string; key: string } | null>(null);
  const focus = override && override.scene === step.id ? override.key : cfgFocus;
  const [shown, setShown] = useState<Set<string>>(() => new Set(TEMP_DEFAULT_ON));
  const toggle = (k: string) => setShown((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const setFocus = (k: string) => setOverride({ scene: step.id, key: k });
  const chartToggle = useMemo(() => (k: string) => (shown.has(k) ? setFocus(k) : toggle(k)), [shown, step.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  // 해설 단계 공개 (TASK 5.2 / 7.1): 자동 해설 모드는 reveal_timing, 발표자 모드는 N 키. 장면이 바뀌면 수동 단계는 0 으로.
  const [manual, setManual] = useState<{ scene: string; level: number }>({ scene: step.id, level: 0 });
  const manualLevel = manual.scene === step.id ? manual.level : 0;
  const level = autoMode ? (scene ? autoLevel(scene, step, pb.t) : 3) : manualLevel;
  const nextLevel = useCallback(() => { if (!autoMode) setManual({ scene: step.id, level: Math.min(3, manualLevel + 1) }); }, [autoMode, step.id, manualLevel]);

  // 이벤트 자막 · 이력 (events.json + event_templates.yaml)
  const clusters = useMemo(() => buildClusters(data.events), [data.events]);
  const history = useMemo(() => buildHistory(data, clusters), [data, clusters]);
  const cap = useMemo(() => captionAt(clusters, pb.t), [clusters, pb.t]);
  const sceneCap = useMemo(() => sceneCaptionAt(data.events, pb.t, data.content.templates), [data.events, data.content.templates, pb.t]);

  // 발표자 화면과 상태 공유 (TASK 7.2): 상태는 5 Hz 로 보내고, 발표자 화면의 명령을 받는다. 멘트는 여기서 보내지 않는다.
  const chan = useMemo(() => openChannel("mechanical"), []);
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
  // 정지 중에도 발표자 화면이 "연결됨" 을 알 수 있게 1 초마다 심장박동
  useEffect(() => {
    if (!chan) return;
    const h = setInterval(() => { if (stateRef.current) chan.postMessage({ ...stateRef.current, at: Date.now() }); }, 1000);
    return () => clearInterval(h);
  }, [chan]);
  useEffect(() => () => chan?.close(), [chan]);
  const openPresenter = () => window.open(window.location.href.split("#")[0] + "#/mechanical/presenter", "vigent-presenter");

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
      <div className={"dash live" + (present ? " present" : "")}>
        <HUDLive data={data} theme={theme} onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
                 present={present} onPresent={togglePresent} autoMode={autoMode} onAutoMode={() => setAutoMode((a) => !a)}
                 captions={captions} onCaptions={() => setCaptions((c) => !c)} qa={qa} onQa={() => setQa((q) => !q)} onPresenter={openPresenter} />
        <div className="live-main">
          <VideoPanel data={data} overlay={captions ? <CaptionBar scene={sceneCap} cap={cap} tpl={data.content.templates} /> : null} />
          <div className="live-side">
            <LiveNarration data={data} level={level} history={history} />
            <MotorSchematic data={data} focus={focus} />
          </div>
        </div>
        <div className="live-bottom">
          <TempChart data={data} focus={focus} shown={shown} onToggle={chartToggle} />
          <VibChart data={data} />
          <CausePanel data={data} focus={focus} />
        </div>
        <QaDrawer data={data} open={qa} onClose={() => setQa(false)} />
      </div>
    </PlaybackContext.Provider>
  );
}
