import type { Cluster } from "./captions";
import { captionText, type Templates } from "./captions";
import type { LiveEvent } from "./types";

// CaptionBar (TASK 5.2, 공용): 영상 바로 아래 띠에 현재 자막 한 줄을 크게 띄운다. 영상만 보는 심사위원도 읽을 수 있게.
// 위 작은 줄 = 장면 전환(6 s 유지), 아래 큰 줄 = 최근 사건(8 s 유지, 다음 사건이 오면 즉시 교체).
// 영상 프레임 위에 겹치지 않는다 — 영상 안에도 Isaac Sim HUD 글자가 있어 겹치면 둘 다 안 읽힌다.
// 자막이 없어도 상자는 남겨 두어(고정 높이) 영상 크기가 들썩이지 않게 한다.

// 사건 종류 → 색 톤 (danger 빨강 / up 주황 / alarm 조기 경보 / vib·balance 노랑 / cold 파랑 / ok 초록)
function tone(e: LiveEvent): string {
  switch (e.type) {
    case "stage_up": return e.to === "danger" ? "danger" : e.note === "early_warning" ? "alarm" : "up";
    case "vib_zone": return "vib";
    case "recovered": return "ok";
    case "status": {
      const to = String(e.to);
      return to === "over_danger" ? "danger" : to === "over_caution" ? "up" : to === "normal" ? "ok" : "cold";
    }
    case "i2i1": return e.up ? "vib" : "ok";
    case "balance_only": return "alarm";
    case "short_loop_on": return "danger";
    default: return "";
  }
}
function icon(e: LiveEvent): string {
  switch (e.type) {
    case "stage_up": return "▲";
    case "stage_down": case "recovered": return "▼";
    case "vib_zone": return "〜";
    case "status": { const to = String(e.to); return to === "over_danger" ? "▲▲" : to === "over_caution" ? "▲" : to === "normal" ? "●" : to === "under_caution" ? "▼" : "▼▼"; }
    case "i2i1": case "balance_only": return "⚖";
    default: return "◈";
  }
}

export function CaptionBar({ scene, cap, tpl }: { scene: { text: string; age: number } | null; cap: { cluster: Cluster; age: number } | null; tpl: Templates }) {
  if (!scene && !cap) return <div className="capbar empty" />;
  const e = cap?.cluster.primary;
  return (
    <div className="capbar">
      {scene && <div className="cap-scene" key={"s" + scene.text}>{scene.text}</div>}
      {cap && e && (
        <div className={"cap-main " + tone(e)} key={"c" + e.id}>
          <span className="ic">{icon(e)}</span>
          {captionText(e, tpl)}
          {cap.cluster.others.length > 0 && <span className="more">+{cap.cluster.others.length} 동시 (목록)</span>}
        </div>
      )}
    </div>
  );
}
