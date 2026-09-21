# -*- coding: utf-8 -*-
"""e6_run_batch.py — v2 시나리오 배치: (6 결함 × 3 심각도 + 정상) × {half, rated} × 시드 n. 런당 e_run.py 독립 프로세스.
사용: C:\ISSACS~1\python.bat e6_run_batch.py --dataset dataset_v02 [--repeats 2] [--dry]"""
import os, sys, json, subprocess, time, argparse, datetime, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", default=None); ap.add_argument("--repeats", type=int, default=2); ap.add_argument("--dry", action="store_true")
ap.add_argument("--python", default=r"C:\ISSACS~1\python.bat"); ap.add_argument("--faults", default="brb,ecc_static,ecc_dynamic,itsc,bpfo,bpfi"); args = ap.parse_args()
import yaml; sys.path.insert(0, os.path.dirname(__file__))
from fault_injector import SEV
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8")); SEED0 = int(CFG["meta"]["seed"])
MODES = args.faults.split(","); LOADS = ["half", "rated"]
name = args.dataset or ("dataset_v02_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")); outdir = os.path.join(ROOT, "output", name); os.makedirs(outdir, exist_ok=True)
runs = []
for r in range(args.repeats):
    for l in LOADS:
        runs.append({"fault": "none", "severity": "none", "load": l, "seed": SEED0 + 100 * r})
        for m in MODES:
            for s in SEV[m]: runs.append({"fault": m, "severity": s, "load": l, "seed": SEED0 + 100 * r + 7})
hold = float(CFG["e_run"]["hold_s"]); total = hold + float(CFG["e_run"]["settle_s"]) + float(CFG["e_run"]["stop_tail_s"])
print(f"runs={len(runs)} est_time={len(runs)*(15+total*1.4)/60:.0f} min est_size~{len(runs)*1.2:.0f} MB", flush=True)
manifest = {"dataset": name, "created": datetime.datetime.now().isoformat(), "isaac_sim": "4.5.0", "physics_hz": CFG["e_run"]["physics_hz"], "hold_s": hold, "total_s": total,
            "config_sha256_12": hashlib.sha256(open(os.path.join(ROOT, "config", "motor.yaml"), "rb").read()).hexdigest()[:12],
            "generation": {"speed_torque_channel": "physx_torque_control", "current_channel": "analytic", "fault_signature": "analytic_injection", "caveat": "주입 시그니처의 재생산 — FEM/실측 유도 데이터 아님"},
            "runs": []}
if args.dry: print(json.dumps(runs, ensure_ascii=False)); sys.exit(0)
t0 = time.time()
for i, r in enumerate(runs):
    cmd = f'"{args.python}" "{os.path.join(ROOT, "scripts", "e_run.py")}" --load {r["load"]} --seed {r["seed"]} --fault {r["fault"]} --severity {r["severity"]} --outdir "{outdir}"'
    ts = time.time(); rc = subprocess.call(cmd, shell=True, stdout=open(os.path.join(outdir, f"log_{i:03d}.txt"), "w"), stderr=subprocess.STDOUT)
    last = open(os.path.join(ROOT, "output", "e_run_last.txt"), encoding="utf-8").read().strip() if rc == 0 else None
    meta = json.load(open(last + ".json", encoding="utf-8")) if last and os.path.exists(last + ".json") else None
    entry = {"idx": i, **r, "rc": rc, "file": (os.path.basename(last) + ".npz") if last else None, "elapsed_s": round(time.time() - ts, 1), "verify": meta.get("verify") if meta else None}
    manifest["runs"].append(entry); json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[{i+1}/{len(runs)}] {r} rc={rc} {entry['elapsed_s']}s", flush=True)
manifest["total_elapsed_s"] = round(time.time() - t0, 1); json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("DONE", name, flush=True)
