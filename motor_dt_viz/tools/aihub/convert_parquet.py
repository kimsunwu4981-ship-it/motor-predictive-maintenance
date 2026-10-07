# -*- coding: utf-8 -*-
"""convert_parquet.py — AI Hub 238 CSV → Parquet 변환 + 메타 테이블 (TASK_AIHub_샘플 S1).

  python -I tools/aihub/convert_parquet.py --src "<샘플 폴더>" --out data/aihub/sample/L2 [--verify 10] [--limit N]

입력 형식은 config/aihub_format.yaml, 모터 매핑은 config/aihub_select.yaml 에서만 읽는다.
출력: <out>/waveforms/<signal>/<file_id>.parquet (t, ch1[, ch2, ch3]; float32, zstd), <out>/meta.parquet, <out>/convert_report.json
-I 로 실행되므로 PYTHONPATH 가 무시된다 → 보조 모듈 경로는 VIGENT_PYMODS 또는 C:\\Temp\\pymods 를 뒤에 덧붙인다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

VIZ = Path(__file__).resolve().parents[2]
CONFIG = VIZ / "config"
META_COLS = ["file_id", "source_path", "signal", "power_kw", "motor_id", "aihub_motor_name", "label", "label_no", "date",
             "sample_rate", "duration_s", "n_samples", "n_samples_annot", "n_channels", "rms_annot", "rated_rpm", "rated_power",
             "rated_current", "bearing", "sensor_id", "source_dat", "sha1", "nan_count", "clipping_ratio"]


def load_cfg():
    fmt = yaml.safe_load(open(CONFIG / "aihub_format.yaml", encoding="utf-8"))
    sel = yaml.safe_load(open(CONFIG / "aihub_select.yaml", encoding="utf-8"))
    return fmt, sel


def read_text(path: Path, fmt: dict) -> list[str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else fmt["encoding"], "utf-8-sig", "cp949"):
        try:
            return raw.decode(enc).splitlines(), hashlib.sha1(raw).hexdigest()  # type: ignore[return-value]
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없다: {path}")


def parse_file(path: Path, fmt: dict) -> tuple[dict, np.ndarray]:
    """헤더 9줄 → meta dict, 데이터 → (n, 1+ch) float64 배열 (0열 = t)."""
    lines, sha1 = read_text(path, fmt)
    d = fmt["delimiter"]
    h = int(fmt["header_lines"])
    meta_raw: dict[str, list[str]] = {}
    for l in lines[:h]:
        parts = [x.strip() for x in l.split(d)]
        meta_raw[parts[0]] = parts[1:]
    meta: dict = {"sha1": sha1}
    for k, col in fmt["meta_keys"].items():
        if k in meta_raw:
            meta[col] = meta_raw[k]
    spec = [x for x in meta.pop("motor_spec", []) if x != ""]
    for name, val in zip(fmt["motor_spec_fields"], spec):
        meta[name] = val
    meta["label"] = meta.get("label", [""])[0]
    meta["label_no"] = meta.get("label_no", [""])[0]
    meta["date"] = meta.get("date", [""])[0]
    meta["source_dat"] = meta.get("source_dat", [""])[0]
    meta["period"] = meta.get("period", [""])[0]
    meta["sample_rate"] = float(meta.get("sample_rate", ["nan"])[0])
    meta["rms_annot"] = [float(x) for x in meta.get("rms_annot", []) if x != ""]
    meta["n_samples_annot"] = int(float(meta.get("n_samples_annot", ["-1"])[0]))
    rows = [l for l in lines[h:] if l.strip()]
    data = np.array([[float(x) for x in l.split(d) if x != ""] for l in rows], dtype=np.float64)
    return meta, data


def file_fields(path: Path, src: Path, fmt: dict) -> dict:
    rel = path.relative_to(src).as_posix().split("/")
    signal, kw, motor, label = rel[0], rel[1], rel[2], rel[3]
    stem = path.stem
    sensor = stem.split("_")[0].split("-", 2)[2] if stem.count("-") >= 2 else ""
    return {"signal": signal, "power_kw": float(kw.lower().replace("kw", "")), "folder_motor": motor, "folder_label": label, "sensor_id": sensor}


def convert_one(path: Path, src: Path, out: Path, fmt: dict, sel: dict) -> dict:
    meta, data = parse_file(path, fmt)
    ff = file_fields(path, src, fmt)
    n, nch = data.shape[0], data.shape[1] - 1
    vals = data[:, 1:]
    top = float(fmt.get("clipping_top_fraction", 0.995)) if "clipping_top_fraction" in fmt else 0.995
    mx = np.abs(vals).max(axis=0)
    clip = float(np.mean(np.abs(vals) >= top * np.where(mx > 0, mx, 1.0))) if n else 0.0
    file_id = path.stem
    pdir = out / "waveforms" / ff["signal"]
    pdir.mkdir(parents=True, exist_ok=True)
    cols = {"t": pa.array(data[:, 0].astype(np.float32))}
    for k in range(nch):
        cols[f"ch{k + 1}"] = pa.array(vals[:, k].astype(np.float32))
    pq.write_table(pa.table(cols), pdir / f"{file_id}.parquet", compression=fmt["parquet"]["compression"])
    motor_map = {float(k): v for k, v in sel["motor_map"].items()}
    return {
        "file_id": file_id, "source_path": path.relative_to(src).as_posix(), "signal": ff["signal"], "power_kw": ff["power_kw"],
        "motor_id": motor_map.get(ff["power_kw"]), "aihub_motor_name": meta.get("aihub_motor_name", ff["folder_motor"]),
        "label": meta["label"] or ff["folder_label"], "label_no": meta["label_no"], "date": meta["date"],
        "sample_rate": meta["sample_rate"], "duration_s": float(data[-1, 0] - data[0, 0] + (data[1, 0] - data[0, 0])) if n > 1 else 0.0,
        "n_samples": n, "n_samples_annot": meta["n_samples_annot"], "n_channels": nch, "rms_annot": meta["rms_annot"],
        "rated_rpm": float(meta.get("rated_rpm", "nan")), "rated_power": float(meta.get("rated_power", "nan")),
        "rated_current": float(meta.get("rated_current", "nan")), "bearing": None if not fmt.get("bearing_in_annotation") else meta.get("bearing"),
        "sensor_id": ff["sensor_id"], "source_dat": meta["source_dat"], "sha1": meta["sha1"],
        "nan_count": int(np.isnan(vals).sum()), "clipping_ratio": clip,
        "_folder_label": ff["folder_label"], "_folder_motor": ff["folder_motor"],
    }


def verify(meta: pd.DataFrame, src: Path, out: Path, fmt: dict, n: int, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    res = []
    for _, r in meta.sample(n=min(n, len(meta)), random_state=rng.randint(0, 10**6)).iterrows():
        _, data = parse_file(src / r["source_path"], fmt)
        t = pq.read_table(out / "waveforms" / r["signal"] / f"{r['file_id']}.parquet").to_pandas()
        ok_len = len(t) == data.shape[0]
        ok_val = ok_len and all(np.allclose(t[f"ch{k + 1}"].to_numpy(), data[:, k + 1].astype(np.float32), rtol=1e-6, atol=1e-7) for k in range(data.shape[1] - 1))
        res.append({"file_id": r["file_id"], "len_ok": bool(ok_len), "values_ok": bool(ok_val),
                    "max_abs_err": float(max(np.abs(t[f"ch{k + 1}"].to_numpy() - data[:, k + 1]).max() for k in range(data.shape[1] - 1)))})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="AI Hub 샘플 루트 (vibration/, current/ 가 있는 폴더)")
    ap.add_argument("--out", default=str(VIZ / "data" / "aihub" / "sample" / "L2"))
    ap.add_argument("--verify", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="앞 N개만 (시험용)")
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    fmt, sel = load_cfg()
    files = sorted(p for p in src.rglob("*.csv"))
    if a.limit:
        files = files[: a.limit]
    t0 = time.time()
    rows, errors = [], []
    for i, p in enumerate(files):
        try:
            rows.append(convert_one(p, src, out, fmt, sel))
        except Exception as e:  # noqa: BLE001
            errors.append({"path": p.relative_to(src).as_posix(), "error": str(e)})
        if (i + 1) % 500 == 0:
            print(f"[convert] {i + 1}/{len(files)}  {time.time() - t0:.1f} s")
    dt = time.time() - t0
    meta = pd.DataFrame(rows)
    # 폴더 라벨·모터명과 헤더가 다른 파일 (검증 기록)
    mism = meta[(meta["label"] != meta["_folder_label"]) | (meta["aihub_motor_name"] != meta["_folder_motor"])]
    meta = meta.drop(columns=["_folder_label", "_folder_motor"])
    out.mkdir(parents=True, exist_ok=True)
    meta.to_parquet(out / "meta.parquet", index=False, compression="zstd")
    src_bytes = sum(p.stat().st_size for p in files)
    pq_bytes = sum(p.stat().st_size for p in (out / "waveforms").rglob("*.parquet")) + (out / "meta.parquet").stat().st_size
    ver = verify(meta, src, out, fmt, a.verify) if a.verify else []
    bad_len = meta[(meta["n_samples"] - meta["n_samples_annot"]).abs() > 0.01 * meta["n_samples_annot"]]
    bad_rate = meta[((meta["sample_rate"] * meta["duration_s"]).round() - meta["n_samples"]).abs() > 0.01 * meta["n_samples"]]
    report = {
        "src": str(src), "out": str(out), "files": len(files), "converted": len(meta), "errors": errors,
        "elapsed_s": round(dt, 1), "s_per_file": round(dt / max(len(files), 1), 4), "src_MB": round(src_bytes / 2**20, 1),
        "parquet_MB": round(pq_bytes / 2**20, 1), "size_ratio": round(pq_bytes / max(src_bytes, 1), 3),
        "verify": ver, "verify_pass": all(v["len_ok"] and v["values_ok"] for v in ver),
        "length_mismatch_files": bad_len["file_id"].tolist(), "rate_mismatch_files": bad_rate["file_id"].tolist(),
        "nan_files": meta[meta["nan_count"] > 0]["file_id"].tolist(),
        "clipping_suspect_files": meta[meta["clipping_ratio"] > 0.10]["file_id"].tolist(),   # 순수 사인파의 자연 비율 ≈ 6.4 % (|x| ≥ 0.995·A) → 10 % 넘으면 평탄 절단 의심
        "header_folder_mismatch": mism["file_id"].tolist(),
        "by_signal": meta.groupby("signal").size().to_dict(),
        "by_power_label_signal": {f"{k[0]}|{k[1]}|{k[2]}": int(v) for k, v in meta.groupby(["power_kw", "label", "signal"]).size().items()},
    }
    json.dump(report, open(out / "convert_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[convert] {len(meta)} 파일, {dt:.1f} s ({report['s_per_file'] * 1000:.1f} ms/파일), CSV {report['src_MB']} MB → Parquet {report['parquet_MB']} MB (×{report['size_ratio']})")
    print(f"[convert] 검증 {sum(v['values_ok'] for v in ver)}/{len(ver)} 통과, 길이 불일치 {len(bad_len)}, NaN {len(report['nan_files'])}, 클리핑 의심 {len(report['clipping_suspect_files'])}, 오류 {len(errors)}")
    if errors:
        print(errors[:3])


if __name__ == "__main__":
    main()
