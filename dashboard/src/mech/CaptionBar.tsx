import type { Cluster } from "./captions";
import { captionText, type Templates } from "./captions";

// CaptionBar (TASK 5.2): 영상 하단에 현재 자막 한 줄을 크게 띄운다. 영상만 보는 심사위원도 읽을 수 있게.
// 위 작은 줄 = 장면 전환(6 s 유지), 아래 큰 줄 = 최근 사건(8 s 유지, 다음 사건이 오면 즉시 교체).
// 영상 프레임 위에 겹치지 않고 바로 아래 줄에 둔다 — 영상 안에도 Isaac Sim HUD 글자가 있어 겹치면 둘 다 안 읽힌다.
// 자막이 없어도 상자는 남겨 두어(고정 높이) 영상 크기가 들썩이지 않게 한다.
export function CaptionBar({ scene, cap, tpl }: { scene: { text: string; age: number } | null; cap: { cluster: Cluster; age: number } | null; tpl: Templates }) {
  if (!scene && !cap) return <div className="capbar empty" />;
  const e = cap?.cluster.primary;
  const cls = e ? (e.type === "stage_up" ? (e.to === "danger" ? " danger" : e.note === "early_warning" ? " alarm" : " up") : e.type === "vib_zone" ? " vib" : e.type === "recovered" ? " ok" : "") : "";
  return (
    <div className="capbar">
      {scene && <div className="cap-scene" key={"s" + scene.text}>{scene.text}</div>}
      {cap && e && (
        <div className={"cap-main" + cls} key={"c" + e.id}>
          <span className="ic">{e.type === "stage_up" ? "▲" : e.type === "stage_down" || e.type === "recovered" ? "▼" : e.type === "vib_zone" ? "〜" : "◈"}</span>
          {captionText(e, tpl)}
          {cap.cluster.others.length > 0 && <span className="more">+{cap.cluster.others.length} 동시 (목록)</span>}
        </div>
      )}
    </div>
  );
}
