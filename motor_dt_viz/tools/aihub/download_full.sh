#!/bin/bash
# download_full.sh — AI Hub 238 전체 데이터 다운로드 (결정 C-1 ②, 2026-10-08). Git Bash 에서 실행.
#
#   AIHUB_API_KEY=<내 키> bash tools/aihub/download_full.sh [대상폴더]        # 기본: ..\aihub_full (프로젝트 저장소 밖, 외부 데이터 격리)
#   bash tools/aihub/download_full.sh --list                                 # 파일 트리만 (키 불필요)
#
# 파일 트리 (2026-10-08 aihubshell -mode l 238):
#   1.Training/current.zip 21 GB (44889) · 1.Training/vibration.zip 78 GB (44890)
#   2.Validation/current.zip 3 GB (44891) · 2.Validation/vibration.zip 10 GB (44815)
# 1차는 진동만(선별 기준 config/aihub_select.yaml signals) → 44890,44815 = 88 GB. 전류까지 받으려면 FILEKEYS 에 44889,44891 추가 (총 112 GB).
# API 키: AI Hub 로그인 → 마이페이지 → API 키 발급. 키는 저장소에 적지 않는다 (환경변수로만).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ "$1" = "--list" ]; then bash "$HERE/aihubshell" -mode l -datasetkey 238; exit 0; fi
DEST="${1:-/c/vigent_data/aihub_full}"
FILEKEYS="${AIHUB_FILEKEYS:-44890,44815}"
[ -n "$AIHUB_API_KEY" ] || { echo "AIHUB_API_KEY 환경변수가 필요하다 (AI Hub 마이페이지 → API 키)"; exit 1; }
mkdir -p "$DEST" && cd "$DEST"
echo "[download] 대상 $DEST, filekey $FILEKEYS, 시작 $(date +%H:%M:%S)"
bash "$HERE/aihubshell" -mode d -datasetkey 238 -filekey "$FILEKEYS" -aihubapikey "$AIHUB_API_KEY"
echo "[download] 끝 $(date +%H:%M:%S)"; ls -la "$DEST"
