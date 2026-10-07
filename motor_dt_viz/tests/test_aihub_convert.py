# -*- coding: utf-8 -*-
"""AI Hub 샘플 변환(L2) 검증 (TASK_AIHub_샘플 S1): 메타 스키마, 샘플 수 = sample_rate × duration, 원본 ↔ Parquet 값 동일,
모터 매핑 = config, 라벨 번호 = config, 품질 목록 보고."""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import pytest

VIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIZ / "tools" / "aihub"))
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

import yaml  # noqa: E402

SAMPLE = Path(os.environ.get("AIHUB_SAMPLE", r"C:\Users\sunwu\OneDrive\바탕 화면\2020-02-125.기계시설물고장예지_sample"))
L2 = VIZ / "data" / "aihub" / "sample" / "L2"
pytestmark = pytest.mark.skipif(not (L2 / "meta.parquet").exists(), reason="L2 없음 — tools/aihub/convert_parquet.py 먼저")


@pytest.fixture(scope="module")
def meta():
    import pandas as pd
    return pd.read_parquet(L2 / "meta.parquet")


@pytest.fixture(scope="module")
def sel():
    return yaml.safe_load(open(VIZ / "config" / "aihub_select.yaml", encoding="utf-8"))


def test_meta_schema(meta):
    from convert_parquet import META_COLS
    assert list(meta.columns) == META_COLS
    assert meta["file_id"].is_unique and len(meta) > 0
    assert set(meta["signal"]) <= {"vibration", "current"}
    assert meta["n_channels"].where(meta["signal"] == "vibration").dropna().eq(1).all()
    assert meta["n_channels"].where(meta["signal"] == "current").dropna().eq(3).all()


def test_samples_equal_rate_times_duration(meta):
    expect = (meta["sample_rate"] * meta["duration_s"]).round()
    assert ((expect - meta["n_samples"]).abs() <= 0.01 * meta["n_samples"]).all()
    assert ((meta["n_samples"] - meta["n_samples_annot"]).abs() <= 0.01 * meta["n_samples_annot"]).all()
    assert set(meta[meta["signal"] == "vibration"]["sample_rate"]) == {4000.0} and set(meta[meta["signal"] == "current"]["sample_rate"]) == {2000.0}


def test_motor_map_and_labels_follow_config(meta, sel):
    mm = {float(k): v for k, v in sel["motor_map"].items()}
    for kw, g in meta.groupby("power_kw"):
        assert set(g["motor_id"].fillna("None")) == {mm.get(kw, "None")}
    for no, g in meta.groupby("label_no"):
        assert set(g["label"]) == {sel["label_no"][no]}


@pytest.mark.skipif(not SAMPLE.exists(), reason="샘플 원본 폴더 없음")
def test_parquet_matches_original_random_files(meta):
    import pyarrow.parquet as pq
    from convert_parquet import load_cfg, parse_file
    fmt, _ = load_cfg()
    rng = random.Random(1)
    for _, r in meta.sample(n=12, random_state=rng.randint(0, 9999)).iterrows():
        _, data = parse_file(SAMPLE / r["source_path"], fmt)
        t = pq.read_table(L2 / "waveforms" / r["signal"] / f"{r['file_id']}.parquet").to_pandas()
        assert len(t) == data.shape[0]
        for k in range(data.shape[1] - 1):
            assert np.allclose(t[f"ch{k + 1}"].to_numpy(), data[:, k + 1].astype(np.float32), rtol=1e-6, atol=1e-7)
        # 어노테이션 RMS 와 변환본 RMS 가 맞는다 (전류는 DC 포함)
        for k, ra in enumerate(r["rms_annot"]):
            assert np.sqrt(np.mean(t[f"ch{k + 1}"].to_numpy(np.float64) ** 2)) == pytest.approx(ra, rel=2e-3)


def test_quality_lists_reported():
    rep = json.load(open(L2 / "convert_report.json", encoding="utf-8"))
    for k in ("nan_files", "clipping_suspect_files", "length_mismatch_files", "rate_mismatch_files", "header_folder_mismatch", "verify"):
        assert k in rep
    assert rep["errors"] == [] and rep["verify_pass"] and len(rep["verify"]) >= 10
    assert rep["length_mismatch_files"] == [] and rep["rate_mismatch_files"] == []
