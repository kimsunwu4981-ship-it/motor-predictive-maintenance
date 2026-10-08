# -*- coding: utf-8 -*-
"""선별 파이프라인(tools/aihub/run_pipeline.py) 검증 (TASK_AIHub_데이터선별 §8): 메타 스키마, 샘플 수 = sample_rate × duration,
모터 매핑 = config, 선별 결과가 config 기준만 포함, manifest 행 수 = 목록 예상, 특징값 범위, 분할 zip 가상 연결."""
from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

VIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIZ / "tools" / "aihub"))
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

import yaml  # noqa: E402

_EXT = Path(os.environ.get("VIGENT_AIHUB_DATA", r"C:\vigent_data\aihub"))
DATA = _EXT if _EXT.exists() else VIZ / "data" / "aihub"          # run_pipeline.py 와 같은 규칙 (OneDrive 밖)
SEL = yaml.safe_load(open(VIZ / "config" / "aihub_select.yaml", encoding="utf-8"))
need = pytest.mark.skipif(not (DATA / "L2" / "meta.parquet").exists(), reason="data/aihub/L2 없음 — run_pipeline.py 먼저")


def test_splitfile_reads_parts_like_one_zip(tmp_path):
    """작은 zip 을 3조각으로 쪼개 .zip.part1~3 으로 두고 병합 없이 목록·추출이 되는지."""
    import run_pipeline as rp
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(5):
            zf.writestr(f"vibration/2.2kW/M/정상/f{i}.csv", ("x,%d\n" % i) * 2000)
    raw = z.read_bytes(); n = len(raw) // 3
    for k, chunk in enumerate((raw[:n], raw[n:2 * n], raw[2 * n:]), 1):
        (tmp_path / f"a.zip.part{k}").write_bytes(chunk)
    z.unlink()
    with rp.open_zip(str(tmp_path / "a.zip.part1")) as zz:
        names = zz.namelist()
        assert len(names) == 5 and zz.read(names[3]) == ("x,3\n" * 2000).encode()


@need
def test_meta_schema_and_sampling_consistency():
    import pandas as pd
    from convert_parquet import META_COLS
    m = pd.read_parquet(DATA / "L2" / "meta.parquet")
    assert list(m.columns) == META_COLS and m["file_id"].is_unique
    assert ((m["sample_rate"] * m["duration_s"]).round() - m["n_samples"]).abs().le(0.01 * m["n_samples"]).all()
    assert (m["n_samples"] - m["n_samples_annot"]).abs().le(0.01 * m["n_samples_annot"]).all()


@need
def test_selection_follows_config():
    import pandas as pd
    m = pd.read_parquet(DATA / "L2" / "meta.parquet")
    assert set(m["signal"]) <= set(SEL["signals"])
    assert set(m["label"]) <= set(SEL["labels"]["include"]) and not (set(m["label"]) & set(SEL["labels"]["exclude"]))
    assert set(m["power_kw"]) <= set(float(x) for x in SEL["power_kw"])
    mm = {float(k): v for k, v in SEL["motor_map"].items()}
    assert all(mm[kw] == mid for kw, mid in zip(m["power_kw"], m["motor_id"]))
    # manifest 행 수 = 목록(list_report) 예상 선별 파일 수 = 메타 행 수
    rep = json.load(open(DATA / "list_report.json", encoding="utf-8"))
    man = sum(1 for _ in open(DATA / "L1" / "manifest.csv", encoding="utf-8")) - 1
    assert man == rep["selected_files"] == len(m)
    # 균형 샘플링: 조합당 상한 이하
    s = pd.read_parquet(DATA / "L2" / "sampled" / "meta.parquet")
    assert s.groupby(["motor_id", "label", "signal"]).size().le(SEL["sample_per_motor_label"]).all()
    assert set(s["file_id"]) <= set(m["file_id"])


@need
def test_feature_value_ranges():
    import pandas as pd
    f = pd.read_parquet(DATA / "L3" / "features.parquet")
    assert (f["rms"] >= 0).all() and (f["crest_factor"] >= 1).all() and (f["vel_rms_mm_s"] >= 0).all()
    assert f["bearing_known"].all() and f["env_bpfo_ratio"].notna().all()      # 선별본(2.2 kW 4대)은 전부 가이드라인 표에 베어링이 있다
    assert f["nan_count"].eq(0).all() and set(f["motor_id"]) <= set(SEL["motor_map"].values())
    assert (VIZ / "docs" / "aihub_feature_summary.md").exists() and (VIZ / "docs" / "aihub_selection.md").exists()
