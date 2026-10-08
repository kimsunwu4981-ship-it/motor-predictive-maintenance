# -*- coding: utf-8 -*-
"""run_pipeline.py — AI Hub 238 선별·변환·특징 파이프라인 D0~D3 (TASK_AIHub_데이터선별). 샘플 zip 과 전체 분할 zip 모두 같은 코드.

  python -I tools/aihub/run_pipeline.py list     --zip "<a.zip | a.zip.part1>"            # D0: 목록 → data/aihub/filelist.txt, select_patterns.txt
  python -I tools/aihub/run_pipeline.py extract  --zip ... [--units 2.2kW/정상 ...]       # D1+D2: 단위별 추출(L1) → Parquet(L2/full) → 검증 → L1 삭제
  python -I tools/aihub/run_pipeline.py sample                                           # D2: 균형 샘플링 → L2/sampled
  python -I tools/aihub/run_pipeline.py features                                         # D3: L3/features.parquet + docs/aihub_feature_summary.md + 그림
  python -I tools/aihub/run_pipeline.py all --zip ...

규칙: 병합 zip 을 만들지 않는다 — 분할 파일(*.zip.part1, part2 …)은 SplitFile 로 이어 붙인 것처럼 읽는다. 원본은 수정·삭제하지 않는다.
선별 기준은 config/aihub_select.yaml 에서만 읽는다. 버린 것은 docs/aihub_selection.md 에 기록한다 (D0 단계에서 자동 생성).
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

import convert_parquet as cp  # noqa: E402

VIZ = Path(__file__).resolve().parents[2]
# 전체 데이터 산출물은 OneDrive 동기화 밖에 둔다 (실측: 저장소(바탕 화면=OneDrive) 안에 5만 파일을 쓰니 OneDrive 가 CPU 2.3 GB 메모리로 동기화해 7 ms→38 ms/파일).
#   우선순위: 환경변수 VIGENT_AIHUB_DATA → C:igent_dataihub (있으면) → 저장소 data/aihub
_EXT = Path(os.environ.get("VIGENT_AIHUB_DATA", r"C:\vigent_data\aihub"))
DATA = _EXT if _EXT.exists() else VIZ / "data" / "aihub"
DOCS = VIZ / "docs"
SEL = yaml.safe_load(open(VIZ / "config" / "aihub_select.yaml", encoding="utf-8"))
FMT = yaml.safe_load(open(VIZ / "config" / "aihub_format.yaml", encoding="utf-8"))


# ------------------------------------------------------------------ 분할 zip 가상 연결
class SplitFile(io.RawIOBase):
    """a.zip.part1, a.zip.part2 … 를 하나의 읽기 전용 파일처럼 보여준다 (병합 디스크 0). 단일 zip 이면 그 파일 하나."""

    def __init__(self, first: str):
        m = re.match(r"^(.*\.zip)\.part(\d+)$", first)
        if m:
            base = m.group(1)
            parts = sorted(glob.glob(glob.escape(base) + ".part*"), key=lambda p: int(re.search(r"part(\d+)$", p).group(1)))
        else:
            parts = [first]
        self.parts = parts
        self.sizes = [os.path.getsize(p) for p in parts]
        self.offsets = np.cumsum([0] + self.sizes)
        self.total = int(self.offsets[-1])
        self.pos = 0
        self.handles = [open(p, "rb") for p in parts]

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=io.SEEK_SET):
        if whence == io.SEEK_SET: self.pos = off
        elif whence == io.SEEK_CUR: self.pos += off
        else: self.pos = self.total + off
        self.pos = max(0, min(self.pos, self.total))
        return self.pos

    def readinto(self, b):
        n = len(b); out = 0
        mv = memoryview(b)
        while out < n and self.pos < self.total:
            i = int(np.searchsorted(self.offsets, self.pos, side="right") - 1)
            h = self.handles[i]; h.seek(self.pos - int(self.offsets[i]))
            chunk = h.read(min(n - out, int(self.offsets[i + 1]) - self.pos))
            if not chunk: break
            mv[out:out + len(chunk)] = chunk; out += len(chunk); self.pos += len(chunk)
        return out

    def close(self):
        for h in self.handles: h.close()
        super().close()


class _Member:
    def __init__(self, name, offset, csize, usize, method):
        self.filename, self.offset, self.compress_size, self.file_size, self.method = name, offset, csize, usize, method
    def is_dir(self): return self.filename.endswith("/")


class ScanZip:
    """잘린 zip(중앙 디렉터리 없음) 읽기 — 로컬 헤더를 순차 스캔해 색인을 만들고, 완전한 항목만 돌려준다 (data descriptor 없는 zip 한정).
    색인은 <zip>.scanindex.json 에 캐시한다. 실측: 66.8 GiB 87만 항목 스캔 83 s. zipfile.ZipFile 과 같은 infolist()/open() 만 제공."""
    def __init__(self, path: str):
        self.path = path; self.size = os.path.getsize(path)
        idx = path + ".scanindex.json"
        if os.path.exists(idx) and os.path.getmtime(idx) >= os.path.getmtime(path):
            d = json.load(open(idx, encoding="utf-8"))
        else:
            d = self._scan(); json.dump(d, open(idx, "w", encoding="utf-8"), ensure_ascii=False)
        self.members = [_Member(*m) for m in d["members"]]; self.partial = d.get("partial"); self.truncated = d.get("truncated", True)

    def _scan(self) -> dict:
        import struct
        members = []; pos = 0; partial = None
        with open(self.path, "rb") as f:
            while pos + 30 <= self.size:
                f.seek(pos); h = f.read(30)
                if h[:4] != b"PK": break
                _, _, flag, method, _, _, _, csize, usize, nlen, elen = struct.unpack("<IHHHHHIIIHH", h)
                rawname = f.read(nlen); f.seek(elen, 1)
                # 로컬 헤더 이름 인코딩: utf-8 플래그(bit 11)면 utf-8, 아니면 cp949(실측: AI Hub zip 로컬 헤더는 cp949, 중앙 디렉터리는 utf-8)
                try:
                    name = rawname.decode("utf-8" if flag & 0x800 else "cp949")
                except UnicodeDecodeError:
                    name = rawname.decode("utf-8", "replace")
                if flag & 8: raise RuntimeError("data descriptor 가 있는 zip 은 순차 스캔으로 읽을 수 없다")
                data_off = pos + 30 + nlen + elen; end = data_off + csize
                if end > self.size: partial = name; break
                members.append((name, data_off, csize, usize, method)); pos = end
        return {"members": members, "partial": partial, "truncated": pos < self.size}

    def infolist(self): return self.members
    def namelist(self): return [m.filename for m in self.members]
    def open(self, name):
        import zlib
        m = next(x for x in self.members if x.filename == name)
        with open(self.path, "rb") as f:
            f.seek(m.offset); raw = f.read(m.compress_size)
        data = raw if m.method == 0 else zlib.decompress(raw, -15)
        if len(data) != m.file_size: raise ValueError(f"{name}: 크기 불일치 {len(data)} ≠ {m.file_size}")
        return io.BytesIO(data)
    def read(self, name): return self.open(name).read()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def open_zip(path: str):
    """정상 zip 은 zipfile(분할 파일은 SplitFile 로 이어 붙임), 중앙 디렉터리가 없는 잘린 zip 은 ScanZip."""
    try:
        return zipfile.ZipFile(io.BufferedReader(SplitFile(path), 8 * 2**20))
    except zipfile.BadZipFile:
        print(f"[zip] 중앙 디렉터리 없음 → 순차 스캔으로 연다 (잘린 파일): {os.path.basename(path)}")
        return ScanZip(path)


# ------------------------------------------------------------------ D0 목록·패턴
def entry_fields(name: str):
    """zip 항목 경로에서 (signal, kw, motor, label). 루트 폴더가 있으면 건너뛴다."""
    parts = name.split("/")
    for i in range(len(parts) - 4):
        if parts[i] in FMT["signals"].values() and parts[i + 1].lower().endswith("kw"):
            return parts[i], float(parts[i + 1].lower().replace("kw", "")), parts[i + 2], parts[i + 3]
    return None


def cmd_list(zpath: str):
    DATA.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open_zip(zpath) as z:
        infos = [(i.filename, i.file_size, i.compress_size) for i in z.infolist() if not i.is_dir()]
    (DATA / "filelist.txt").write_text("\n".join(f"{n}\t{s}\t{c}" for n, s, c in infos) + "\n", encoding="utf-8")
    rows = []
    for n, s, c in infos:
        f = entry_fields(n)
        if f: rows.append({"name": n, "size": s, "signal": f[0], "power_kw": f[1], "motor": f[2], "label": f[3]})
    df = pd.DataFrame(rows)
    keep = df[df["power_kw"].isin(SEL["power_kw"]) & df["label"].isin(SEL["labels"]["include"]) & df["signal"].isin(SEL["signals"])]
    pats = sorted({f"{r.signal}/{fmt_kw(r.power_kw)}/*/{r.label}/*.csv" for r in keep.itertuples()})
    (DATA / "select_patterns.txt").write_text("\n".join(pats) + "\n", encoding="utf-8")
    g_all = df.groupby(["signal", "power_kw", "label"]).agg(files=("size", "size"), MB=("size", lambda s: round(s.sum() / 2**20, 1))).reset_index()
    g_all["selected"] = g_all.apply(lambda r: r.power_kw in SEL["power_kw"] and r.label in SEL["labels"]["include"] and r.signal in SEL["signals"], axis=1)
    rep = {"zip": zpath, "entries": len(infos), "csv_rows": len(df), "selected_files": int(len(keep)), "selected_MB": round(keep["size"].sum() / 2**20, 1),
           "truncated": bool(getattr(z, "truncated", False)), "partial_entry": getattr(z, "partial", None),
           "total_MB": round(df["size"].sum() / 2**20, 1), "patterns": pats, "elapsed_s": round(time.time() - t0, 1)}
    json.dump(rep, open(DATA / "list_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_selection_doc(g_all, rep)
    print(f"[list] 항목 {len(infos)}, CSV {len(df)}, 선별 {len(keep)} 파일 {rep['selected_MB']} MB / 전체 {rep['total_MB']} MB ({rep['selected_MB']/max(rep['total_MB'],1e-9)*100:.0f} %), 패턴 {len(pats)}개, {rep['elapsed_s']} s")
    return rep


def fmt_kw(kw: float) -> str:
    return (f"{kw:g}" + "kW")


def write_selection_doc(g: pd.DataFrame, rep: dict):
    L = ["# AI Hub 238 선별 기록 (docs/aihub_selection.md) — D0 자동 생성 + 수기 보충", "",
         f"- 원본: `{rep['zip']}` (항목 {rep['entries']}, CSV {rep['csv_rows']}, {rep['total_MB']} MB). 버전 1.0 (2021-06-18), 출처 AI Hub 「기계시설물 고장 예지 센서」(dataSetSn=238) — 발표·문서에 출처를 표기한다.",
         f"- 선별 기준 `config/aihub_select.yaml`: 용량 {SEL['power_kw']} kW, 라벨 {SEL['labels']['include']}, 신호 {SEL['signals']}. 선별 {rep['selected_files']} 파일 {rep['selected_MB']} MB ({rep['selected_MB']/max(rep['total_MB'],1e-9)*100:.0f} %).",
         "", "## 받은 것 / 버린 것", "", "| 신호 | 용량 | 라벨 | 파일 | MB | 선별 | 이유 |", "|---|---|---|---|---|---|---|"]
    for r in g.itertuples():
        why = "선별" if r.selected else ("용량이 M1~M5 에 없음" if r.power_kw not in SEL["power_kw"] else ("라벨 제외 — " + ("권상 모터에 벨트 없음" if r.label == "벨트느슨함" else "불평형은 2차 과제") if r.label in SEL["labels"]["exclude"] else "신호 제외 — 전류는 2차(3상 확인됨)"))
        L.append(f"| {r.signal} | {r.power_kw:g} | {r.label} | {r.files} | {r.MB} | {'✔' if r.selected else '✘'} | {why} |")
    L += ["", "## 범위를 넓힐 때", "", "- 전류(3상, I₂/I₁ 가능)와 회전체불평형은 `aihub_select.yaml` 의 `signals`·`labels.include` 에 추가하고 `run_pipeline.py list → extract` 를 다시 돌리면 된다.",
          "- 55 kW 등 M1~M5 밖 용량은 `motor_map` 에 없어 motor_id=None 으로만 변환된다 (임계값 보정 대상 아님).", "",
          "## 디스크 흐름", "", "분할 원본(보존) → [가상 연결] → 목록 → 패턴 → 단위(용량·라벨)별 추출 L1 → Parquet L2/full → 검증 → L1 단위 삭제 → 균형 샘플링 L2/sampled → 특징 L3. 병합 zip 은 만들지 않는다."]
    (DOCS / "aihub_selection.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ D1+D2 단위별 추출·변환·삭제
def units_from_patterns() -> list[tuple[str, float, str]]:
    pats = (DATA / "select_patterns.txt").read_text(encoding="utf-8").split()
    out = []
    for p in pats:
        sig, kw, _, label, _ = p.split("/")
        out.append((sig, float(kw.lower().replace("kw", "")), label))
    return out


def cmd_extract(zpath: str, only: list[str] | None, keep_l1: bool):
    l1, l2 = DATA / "L1", DATA / "L2" / "full"
    l1.mkdir(parents=True, exist_ok=True); l2.mkdir(parents=True, exist_ok=True)
    man_p = DATA / "L1" / "manifest.csv"
    man_rows = []
    meta_rows = []
    motor_map = {float(k): v for k, v in SEL["motor_map"].items()}
    summary = []
    with open_zip(zpath) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
        for sig, kw, label in units_from_patterns():
            unit = f"{sig}/{fmt_kw(kw)}/{label}"
            if only and unit not in only and f"{fmt_kw(kw)}/{label}" not in only:
                continue
            members = [n for n in names if (f := entry_fields(n)) and f[0] == sig and f[1] == kw and f[3] == label]
            expected = len(members)
            udir = l1 / sig / fmt_kw(kw) / label
            t0 = time.time()
            for n in members:                                  # 추출 (경로는 signal 이후 부분만 유지)
                parts = n.split("/"); rel = Path(parts[-3], parts[-1])   # <motor>/<file>.csv (경로 …/<kW>/<motor>/<label>/<file>)
                dst = udir / rel; dst.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
            got = sorted(udir.rglob("*.csv"))
            assert len(got) == expected, f"{unit}: 추출 {len(got)} ≠ 목록 {expected}"
            # 변환 (convert_parquet.convert_one 재사용: src 루트는 L1, 경로 구조 <signal>/<kW>/<label>/<motor>/<file> 이므로 필드를 직접 준다)
            for p in got:
                meta, data = cp.parse_file(p, FMT)
                row = _convert_row(p, data, meta, sig, kw, label, motor_map, l2)
                meta_rows.append(row)
                man_rows.append({"path": f"{unit}/{p.parent.name}/{p.name}", "size": p.stat().st_size, "power_kw": kw, "label": label,
                                 "motor_id": row["motor_id"], "sha1": row["sha1"]})
            # 검증: 무작위 20개 원본 ↔ Parquet
            import pyarrow.parquet as pq
            rng = np.random.default_rng(SEL["random_seed"])
            for p in rng.choice(got, size=min(20, len(got)), replace=False):
                _, data = cp.parse_file(p, FMT)
                t = pq.read_table(l2 / "waveforms" / sig / f"{p.stem}.parquet").to_pandas()
                assert len(t) == len(data) and all(np.allclose(t[f"ch{k+1}"].to_numpy(), data[:, k+1].astype(np.float32), rtol=1e-6, atol=1e-7) for k in range(data.shape[1] - 1)), p
            l1_mb = sum(p.stat().st_size for p in got) / 2**20
            if not keep_l1:
                shutil.rmtree(udir)
            summary.append({"unit": unit, "files": expected, "L1_MB": round(l1_mb, 1), "s": round(time.time() - t0, 1)})
            print(f"[extract] {unit}: {expected} 파일 {l1_mb:.1f} MB → Parquet, 검증 20 통과, {time.time() - t0:.1f} s{'' if keep_l1 else ', L1 삭제'}")
    with open(man_p, "a" if man_p.exists() else "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "size", "power_kw", "label", "motor_id", "sha1"])
        if fh.tell() == 0: w.writeheader()
        w.writerows(man_rows)
    meta = pd.DataFrame(meta_rows)
    mp = DATA / "L2" / "meta.parquet"
    if mp.exists():
        old = pd.read_parquet(mp); meta = pd.concat([old[~old["file_id"].isin(meta["file_id"])], meta], ignore_index=True)
    meta.to_parquet(mp, index=False, compression="zstd")
    pq_mb = sum(p.stat().st_size for p in l2.rglob("*.parquet")) / 2**20
    json.dump({"units": summary, "manifest_rows": sum(1 for _ in open(man_p, encoding="utf-8")) - 1, "L2_full_MB": round(pq_mb, 1)},
              open(DATA / "extract_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[extract] manifest {len(man_rows)} 행 추가, L2/full {pq_mb:.1f} MB")


def _convert_row(p: Path, data: np.ndarray, meta: dict, sig: str, kw: float, label: str, motor_map: dict, l2: Path) -> dict:
    import pyarrow as pa, pyarrow.parquet as pq
    n, nch = data.shape[0], data.shape[1] - 1
    vals = data[:, 1:]
    mx = np.abs(vals).max(axis=0)
    cols = {"t": pa.array(data[:, 0].astype(np.float32))}
    for k in range(nch): cols[f"ch{k+1}"] = pa.array(vals[:, k].astype(np.float32))
    (l2 / "waveforms" / sig).mkdir(parents=True, exist_ok=True)      # extract_features 가 읽는 <L2>/waveforms/<signal>/ 구조 그대로
    pq.write_table(pa.table(cols), l2 / "waveforms" / sig / f"{p.stem}.parquet", compression=FMT["parquet"]["compression"])
    stem = p.stem
    return {"file_id": stem, "source_path": f"{sig}/{fmt_kw(kw)}/{p.parent.name}/{label}/{p.name}", "signal": sig, "power_kw": kw,
            "motor_id": motor_map.get(kw), "aihub_motor_name": meta.get("aihub_motor_name", p.parent.name), "label": meta["label"] or label,
            "label_no": meta["label_no"], "date": meta["date"], "sample_rate": meta["sample_rate"],
            "duration_s": float(data[-1, 0] - data[0, 0] + (data[1, 0] - data[0, 0])), "n_samples": n, "n_samples_annot": meta["n_samples_annot"],
            "n_channels": nch, "rms_annot": meta["rms_annot"], "rated_rpm": float(meta.get("rated_rpm", "nan")), "rated_power": float(meta.get("rated_power", "nan")),
            "rated_current": float(meta.get("rated_current", "nan")), "bearing": None, "sensor_id": stem.split("_")[0].split("-", 2)[2] if stem.count("-") >= 2 else "",
            "source_dat": meta["source_dat"], "sha1": meta["sha1"], "nan_count": int(np.isnan(vals).sum()),
            "clipping_ratio": float(np.mean(np.abs(vals) >= 0.995 * np.where(mx > 0, mx, 1.0)))}


# ------------------------------------------------------------------ D2 균형 샘플링
def cmd_sample():
    meta = pd.read_parquet(DATA / "L2" / "meta.parquet")
    cap, seed = int(SEL["sample_per_motor_label"]), int(SEL["random_seed"])
    dst = DATA / "L2" / "sampled"
    if dst.exists(): shutil.rmtree(dst)
    picked = []
    for (mid, lab, sig), g in meta.groupby(["motor_id", "label", "signal"], dropna=False):
        take = g.sample(n=min(cap, len(g)), random_state=seed) if len(g) > cap else g
        picked.append(take)
        print(f"[sample] {mid} · {lab} · {sig}: {len(g)} → {len(take)}")
    s = pd.concat(picked)
    for r in s.itertuples():
        (dst / "waveforms" / r.signal).mkdir(parents=True, exist_ok=True)
        shutil.copy2(DATA / "L2" / "full" / "waveforms" / r.signal / f"{r.file_id}.parquet", dst / "waveforms" / r.signal / f"{r.file_id}.parquet")
    s.to_parquet(dst / "meta.parquet", index=False, compression="zstd")
    print(f"[sample] {len(s)} 파일 → {dst}")


# ------------------------------------------------------------------ D3 특징·요약
def cmd_features():
    import extract_features as ef
    meta = pd.read_parquet(DATA / "L2" / "meta.parquet")
    l2 = DATA / "L2" / "full"                                     # <L2>/waveforms/<signal>/ 구조 (extract_features 와 동일)
    t0 = time.time(); rows = []
    for _, r in meta.iterrows():
        rows.extend(ef.features_for_file(r, l2))
    feat = pd.DataFrame(rows); dt = time.time() - t0
    l3 = DATA / "L3"; l3.mkdir(exist_ok=True)
    feat.to_parquet(l3 / "features.parquet", index=False, compression="zstd")
    print(f"[features] {len(feat)} 행, {dt:.1f} s ({dt/max(len(meta),1)*1000:.1f} ms/파일)")
    write_feature_summary(feat, meta, dt)


def write_feature_summary(feat: pd.DataFrame, meta: pd.DataFrame, dt: float):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
    fv = feat[feat["signal"] == "vibration"].copy()
    plots = DOCS / "aihub_plots"; plots.mkdir(exist_ok=True)
    L = ["# AI Hub 238 선별본 특징 요약 (D3) — docs/aihub_feature_summary.md", "",
         "**다음 작업(임계값 보정)의 입력이다.** 단, 이번 실행은 *경량 샘플 zip* 을 원본으로 썼으므로 수치는 참고용이고 전체 데이터가 오면 같은 명령으로 다시 만든다.",
         "진동 단위 g 는 가이드라인 v2.4 로 확정. 포락선 BPFO/BPFI 배율은 가이드라인 표의 모터별 베어링 호칭(`config/aihub_bearings.yaml`) + 카탈로그 기하(추정)로 계산 — 참고값.", "",
         f"- 특징 {len(feat)} 행 / {len(meta)} 파일, {dt:.1f} s. 결측률(선별 신호에 해당하는 열만): " + (", ".join(f"{k} {v:.0%}" for k, v in feat.isna().mean().items() if 0 < v < 1) or "없음") + ". 전부 NaN 인 열: " + ", ".join(k for k, v in feat.isna().mean().items() if v == 1) + " (베어링 번호 없음 / 전류 전용).", "",
         "## 1. 용량·라벨별 속도 RMS (mm/s)", "", "| 모터 ID | 용량 | 모터 | 라벨 | 파일 | 평균 | 중앙값 | 95 % | 최대 | crest 중앙값 | kurtosis 중앙값 | 포락선 BPFO 배율 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (mid, kw, m, lab), g in fv.groupby(["motor_id", "power_kw", "aihub_motor_name", "label"], dropna=False):
        v = g["vel_rms_mm_s"]
        eb = g["env_bpfo_ratio"]
        L.append(f"| {mid} | {kw:g} | {m} | {lab} | {len(g)} | {v.mean():.3f} | {v.median():.3f} | {v.quantile(.95):.3f} | {v.max():.3f} | {g['crest_factor'].median():.1f} | {g['kurtosis'].median():.1f} | " + (f"BPFO {eb.median():.1f} (95 % {eb.quantile(.95):.1f}) / BPFI {g['env_bpfi_ratio'].median():.1f} · {g['bearing_de'].iloc[0]}" if eb.notna().any() else "베어링 미상") + " |")
    L += ["", "## 2. 정상 속도 RMS 의 ISO 등급 위치 (용량별)", "", "| 모터 ID | 용량 | 정상 파일 | 중앙값 | 95 % | 적용 규격 | 경고 하한 | 중앙값/경고 | 95 %/경고 |", "|---|---|---|---|---|---|---|---|---|"]
    for (mid, kw), g in fv[fv["label_no"] == "00"].groupby(["motor_id", "power_kw"], dropna=False):
        std, lim = "ISO 20816-3 Group 2 강성 지지 (5종 통일)", 1.4
        v = g["vel_rms_mm_s"]
        L.append(f"| {mid} | {kw:g} | {len(g)} | {v.median():.3f} | {v.quantile(.95):.3f} | {std} | {lim} | {v.median()/lim:.0%} | {v.quantile(.95)/lim:.0%} |")
    L += ["", "## 3. 정상 vs 베어링 불량 — 포락선 배율과 보조 지표", "",
          "`env_bpfo_ratio` = 포락선 스펙트럼의 BPFO 피크 ÷ 주변 ±25 Hz 바닥(중앙값). 베어링 호칭은 가이드라인 표, 기하는 카탈로그 추정. 같은 모터의 정상 대비 고주파 대역 RMS·kurtosis·속도 RMS 도 함께 본다 (박스플롯 `docs/aihub_plots/`).", ""]
    brg = fv[fv["label_no"] == "01"]
    if len(brg):
        for m in brg["aihub_motor_name"].unique():
            nor = fv[(fv["aihub_motor_name"] == m) & (fv["label_no"] == "00")]; b = brg[brg["aihub_motor_name"] == m]
            for col in ("env_bpfo_ratio", "env_bpfi_ratio", "vel_rms_mm_s", "band_hi", "kurtosis", "rms"):
                L.append(f"- {m} `{col}`: 정상 중앙값 {nor[col].median():.4g} (n={len(nor)}) vs 베어링불량 {b[col].median():.4g} (n={len(b)}) → 비 {b[col].median()/max(nor[col].median(),1e-12):.2f}")
    # 그림: 라벨별 박스 (vel_rms, band_hi)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fv["grp"] = fv["motor_id"].astype(str) + " " + fv["aihub_motor_name"] + "\n" + fv["label"]
    order = sorted(fv["grp"].unique())
    for ax, col, ttl in zip(axes, ("vel_rms_mm_s", "env_bpfo_ratio"), ("속도 RMS mm/s (g)", "포락선 BPFO 배율 (피크/바닥, 가이드라인 베어링)")):
        ax.boxplot([fv[fv["grp"] == g][col].dropna() for g in order], tick_labels=order, showfliers=True); ax.set_title(ttl); ax.tick_params(axis="x", labelsize=7)
    fig.suptitle("선별본 라벨별 분포 — 경량 샘플 기반, 참고용 (베어링 호칭은 가이드라인 표, 기하는 카탈로그 추정)")
    fig.tight_layout(); p = plots / "label_box_vel_bpfo.png"; fig.savefig(p, dpi=110); plt.close(fig)
    L += ["", f"그림: `{p.relative_to(VIZ).as_posix()}`"]
    (DOCS / "aihub_feature_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[features] 요약 → {DOCS / 'aihub_feature_summary.md'}, 그림 {p.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "extract", "sample", "features", "all"])
    ap.add_argument("--zip", help="zip 또는 첫 분할 파일(*.zip.part1)")
    ap.add_argument("--units", nargs="*", help="예: 2.2kW/정상")
    ap.add_argument("--keep-l1", action="store_true")
    a = ap.parse_args()
    if a.cmd in ("list", "all"): cmd_list(a.zip)
    if a.cmd in ("extract", "all"): cmd_extract(a.zip, a.units, a.keep_l1)
    if a.cmd in ("sample", "all"): cmd_sample()
    if a.cmd in ("features", "all"): cmd_features()


if __name__ == "__main__":
    main()
