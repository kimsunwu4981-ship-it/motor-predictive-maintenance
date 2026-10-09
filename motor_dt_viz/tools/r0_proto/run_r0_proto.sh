#!/bin/bash
# R0 프로토타입 실행: 기준(서버 없음) → 서버+클라이언트 → --low 프리셋+서버+클라이언트. 각 90 s. 성능 샘플 5 s 간격.
SP="/c/Users/sunwu/AppData/Local/Temp/claude/c--Users-sunwu-OneDrive--------------------------------/f79df350-ae0e-4415-bafd-be11ff9707ff/scratchpad"
VIZ="/c/Users/sunwu/OneDrive/바탕 화면/프로젝트/디지털 트윈/크레인 퀀선 모터 모델링/motor_dt_viz"
PY="/c/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe"
DEMO_W=$(cygpath -d "$VIZ/app/demo_integrated.py")
SRV_W=$(cygpath -d "$SP/ws_proto_server.py")
cd "$VIZ"
echo "pre-existing kit.exe:"; tasklist | grep -i "kit.exe" || echo "(none)"

sample() {  # $1 = out csv, 5 s 간격, kit.exe RAM 합계(MB)·GPU
  local out="$1"; echo "t,gpu_used_mib,gpu_util,kit_ram_mb" > "$out"
  while true; do
    g=$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits | tr -d ' ')
    r=$(tasklist /FI "IMAGENAME eq kit.exe" /FO CSV /NH 2>/dev/null | awk -F'","' '{gsub(/[",K ]/,"",$5); s+=$5} END {printf "%d", s/1024}')
    echo "$(date +%H:%M:%S),$g,$r" >> "$out"; sleep 5
  done
}

run_case() {  # $1 = name, $2 = server flag ("--no_server" or ""), $3 = extra demo args
  local name="$1" flag="$2" extra="$3"
  rm -rf "logs/$name"; mkdir -p "logs/$name"
  sample "logs/$name/perf_samples.csv" & local SPID=$!
  echo "=== $name  (server: ${flag:-yes}) $(date +%H:%M:%S)"
  if [ -z "$flag" ]; then
    ( "$PY" -X utf8 "$SP/ws_client.py" ws://127.0.0.1:8765 60 "$VIZ/logs/$name/ws_client.json" > "logs/$name/ws_client.log" 2>&1 ) &
    local CPID=$!
  fi
  "$PY" -X utf8 -c "import json,sys; json.dump({'demo': sys.argv[1], 'no_server': sys.argv[2]=='--no_server', 'demo_args': ['--gui','--autoplay','--mode','mechanical','--max_s','90','--log_subdir',sys.argv[3]] + [a for a in sys.argv[4].split() if a]}, open(sys.argv[5],'w',encoding='utf-8'), ensure_ascii=False)" "$(cygpath -w "$VIZ/app/demo_integrated.py")" "$flag" "$name" "$extra" "$SP/proto_$name.json"
  cmd //c "C:\ISSACS~1\python.bat $(cygpath -w "$SP/ws_proto_server.py") $(cygpath -w "$SP/proto_$name.json")" > "logs/$name/run.log" 2>&1
  [ -n "$CPID" ] && wait $CPID
  kill $SPID 2>/dev/null
  grep -h "\[ws_proto\]\|\[demo\] DONE\|Error\|Traceback" "logs/$name/run.log" | tail -5
  cat "logs/$name/demo_integrated.json" 2>/dev/null | tr -d '\n' | cut -c1-300; echo
  [ -f "logs/$name/ws_client.json" ] && cat "logs/$name/ws_client.json" | tr -d '\n' | cut -c1-400; echo
  tail -n +2 "logs/$name/perf_samples.csv" | awk -F, 'NR>3 {if($2>g)g=$2; if($4>r)r=$4; u+=$3; n++} END {printf "perf: gpu_used_max %d MiB, gpu_util_avg %.0f %%, kit_ram_max %d MB (%d samples)\n", g, u/n, r, n}'
}

run_case r0_proto_base "--no_server" ""
run_case r0_proto_ws "" ""
run_case r0_proto_low_ws "" "--low"
echo "ALL DONE $(date +%H:%M:%S)"
