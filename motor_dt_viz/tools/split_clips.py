# -*- coding: utf-8 -*-
"""split_clips.py — 모드별 전체 시나리오 영상을 장면(단계)별 클립으로 자른다.

재녹화하지 않는다. 시나리오 yaml 의 duration_s 와 녹화 메타(video_offset_s)로
각 단계의 영상 구간을 계산해 ffmpeg 로 잘라낸다. 발표 중 특정 결함만 보여줄 때 쓴다.

  영상시각 = t_real + video_offset_s      (D0 에서 실측 오차 0.07 s 이내)

사용:
  python tools/split_clips.py --mode mechanical --video ../dashboard/public/media/mechanical/mechanical_full.mp4
  python tools/split_clips.py --mode electrical --video ../dashboard/public/media/electrical/electrical_full.mp4

출력: <video 폴더>/clips/NN_<기계|전기>_<장면>.mp4  (NN 은 02 부터 — 01 은 전체 시나리오)
      같은 폴더에 clips_index.json (구간·파일명·자막) 을 남겨 대시보드와 바탕화면 정리에 쓴다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from engine.scenario_player import ScenarioPlayer  # noqa: E402

MODE_KO = {"mechanical": "기계", "electrical": "전기", "integrated": "통합"}
# 기동 직후 프레임(알림 팝업 등)을 피하려고 각 단계 앞머리를 조금 자른다
HEAD_TRIM_S = 0.5
# 단계 사이 화면 전환이 걸리므로 끝을 조금 남긴다
TAIL_TRIM_S = 0.3


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # winget 설치 경로 (PATH 에 안 잡힌 경우)
    base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(base):
        for d in os.listdir(base):
            if d.lower().startswith("gyan.ffmpeg"):
                for sub in os.listdir(os.path.join(base, d)):
                    cand = os.path.join(base, d, sub, "bin", "ffmpeg.exe")
                    if os.path.exists(cand):
                        return cand
    raise FileNotFoundError("ffmpeg 를 찾지 못했다 — PATH 에 추가하거나 winget install Gyan.FFmpeg")


def clip_name(label: str) -> str:
    """'6. 과부하 운전 (열 관점)' → '과부하_운전_열_관점' (파일명에 안전한 한글·영숫자만)."""
    s = re.sub(r"^\s*\d+\.\s*", "", label)
    s = re.sub(r"[^\w가-힣]+", "_", s, flags=re.UNICODE).strip("_")
    return re.sub(r"_+", "_", s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=("mechanical", "electrical", "integrated"))
    ap.add_argument("--video", required=True, help="전체 시나리오 mp4 (상대 경로는 motor_dt_viz 기준)")
    ap.add_argument("--meta", help="recording_*.json (생략하면 logs/<mode>/ 에서 찾는다)")
    ap.add_argument("--out", help="클립 출력 폴더 (기본: <video 폴더>/clips)")
    ap.add_argument("--dry_run", action="store_true", help="구간만 출력하고 자르지 않는다")
    args = ap.parse_args()

    video = os.path.abspath(os.path.join(ROOT, args.video)) if not os.path.isabs(args.video) else args.video
    if not os.path.exists(video):
        print("영상 없음:", video)
        return 1

    # 녹화 메타 (video_offset_s)
    meta_path = args.meta
    if not meta_path:
        stem = os.path.splitext(os.path.basename(video))[0]
        for d in (os.path.join(ROOT, "logs", args.mode), os.path.join(ROOT, "logs")):
            cand = os.path.join(d, f"recording_{stem}.json")
            if os.path.exists(cand):
                meta_path = cand
                break
    if not meta_path or not os.path.exists(meta_path):
        print("녹화 메타(recording_*.json) 를 찾지 못했다. --meta 로 지정하라.")
        return 1
    meta = json.load(open(meta_path, encoding="utf-8"))
    offset = float(meta["video_offset_s"])

    player = ScenarioPlayer.for_mode(args.mode)
    out_dir = args.out or os.path.join(os.path.dirname(video), "clips")
    os.makedirs(out_dir, exist_ok=True)
    ffmpeg = None if args.dry_run else find_ffmpeg()
    ko = MODE_KO[args.mode]

    index = {"mode": args.mode, "video": os.path.basename(video), "video_offset_s": offset,
             "meta": os.path.basename(meta_path), "clips": []}
    t0 = 0.0
    print(f"{'#':<3}{'장면':<22}{'t_real':>14}{'영상구간':>16}  파일")
    for i, step in enumerate(player.steps, start=2):      # 01 은 전체 시나리오
        d = float(step["duration_s"])
        t1 = t0 + d
        v_start = t0 + offset + HEAD_TRIM_S
        v_end = t1 + offset - TAIL_TRIM_S
        name = f"{i:02d}_{ko}_{clip_name(step['label'])}.mp4"
        path = os.path.join(out_dir, name)
        print(f"{i:<3}{step['id']:<22}{t0:6.1f}~{t1:6.1f}s{v_start:8.2f}~{v_end:6.2f}s  {name}")
        if not args.dry_run:
            # 프레임 정확도를 위해 재인코딩한다 (-c copy 는 키프레임 단위라 최대 수 초 어긋난다)
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{v_start:.3f}", "-to", f"{v_end:.3f}",
                   "-i", video, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", path]
            subprocess.run(cmd, check=True)
        index["clips"].append({
            "n": i, "step_id": step["id"], "file": name, "label": step["label"],
            "subtitle": step.get("subtitle", ""), "source": step.get("source", ""),
            "t_real_start": round(t0, 3), "t_real_end": round(t1, 3),
            "video_start": round(v_start, 3), "video_end": round(v_end, 3),
        })
        t0 = t1

    with open(os.path.join(out_dir, "clips_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\n{len(index['clips'])} 개 클립 → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
