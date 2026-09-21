# -*- coding: utf-8 -*-
"""s6_run_batch.py — 결함 시나리오 배치 (headless 순차 실행, 실행당 독립 파일 + manifest.json)
사용: C:\ISSACS~1\python.bat s6_run_batch.py [--dataset NAME] [--repeats 1] [--dry]
각 실행은 s4_run_baseline.py 를 별도 프로세스로 호출한다(SimulationApp 은 프로세스당 1회).
"""
import os, sys, json, subprocess, time, argparse, datetime, itertools, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", default=None); ap.add_argument("--repeats", type=int, default=1)
ap.add_argument("--dry", action="store_true"); ap.add_argument("--total_s", type=float, default=8.0); ap.add_argument("--python", default=r"C:\ISSACS~1\python.bat")
args = ap.parse_args()
import yaml
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
sys.path.insert(0, os.path.dirname(__file__))
from s5_fault_injector import SEV
MODES = list(SEV.keys()); LOADS = ["noload", "rated"]; SEED0 = int(CFG["meta"]["seed"])
name = args.dataset or ("dataset_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
outdir = os.path.join(ROOT, "output", name); os.makedirs(outdir, exist_ok=True)
runs = [{"fault": "none", "severity": "none", "load": l, "seed": SEED0 + r} for l in LOADS for r in range(args.repeats)]
for m, l, r in itertools.product(MODES, LOADS, range(args.repeats)):
    for s in SEV[m]: runs.append({"fault": m, "severity": s, "load": l, "seed": SEED0 + 1000 * r + 7})
est_s = len(runs) * (20 + args.total_s * 2.6); est_mb = len(runs) * 2560 * args.total_s * 8 * 8 / 1e6 * 0.6
print(f"runs={len(runs)} est_time={est_s/60:.1f} min est_size~{est_mb:.0f} MB (npz 압축 전 기준의 60%)")
manifest = {"dataset": name, "created": datetime.datetime.now().isoformat(), "generation": "analytic_injection", "isaac_sim": "4.5.0",
            "physics_hz": CFG["physics"]["physics_hz"]["value"], "duration_s": args.total_s, "config_sha256_12": hashlib.sha256(open(os.path.join(ROOT, "config", "motor.yaml"), "rb").read()).hexdigest()[:12],
            "note": "결함 데이터는 해석식 토크 리플 주입의 재생산이며 FEM 유도 데이터가 아님. 진폭비는 미확인(추정: 상대 스윕값).", "runs": []}
if args.dry: print(json.dumps(runs, ensure_ascii=False)); sys.exit(0)
t0 = time.time()
for i, r in enumerate(runs):
    cmd = f'"{args.python}" "{os.path.join(ROOT, "scripts", "s4_run_baseline.py")}" --load {r["load"]} --seed {r["seed"]} --fault {r["fault"]} --severity {r["severity"]} --outdir "{outdir}" --total_s {args.total_s}'
    ts = time.time(); rc = subprocess.call(cmd, shell=True, stdout=open(os.path.join(outdir, f"log_{i:03d}.txt"), "w"), stderr=subprocess.STDOUT)
    last = open(os.path.join(ROOT, "output", "s4_last.txt"), encoding="utf-8").read().strip() if rc == 0 else None
    meta = json.load(open(os.path.join(outdir, last + ".json"), encoding="utf-8")) if last and os.path.exists(os.path.join(outdir, last + ".json")) else None
    entry = {"idx": i, **r, "rc": rc, "file": (last + ".npz") if last else None, "elapsed_s": round(time.time() - ts, 1),
             "verify": meta.get("verify") if meta else None, "fault_params": meta.get("fault_params") if meta else None}
    manifest["runs"].append(entry)
    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[{i+1}/{len(runs)}] {r} rc={rc} {entry['elapsed_s']}s", flush=True)
manifest["total_elapsed_s"] = round(time.time() - t0, 1)
json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("DONE", name)
