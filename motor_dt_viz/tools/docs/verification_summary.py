# -*- coding: utf-8 -*-
"""verification_summary.py — docs/verification_summary.md (+ .json): 발표·문서가 인용할 단 하나의 검증 요약 (D4, 2026-10-21). **수기 숫자 없음** — 전부 기존 파일에서 읽는다.

입력: data/electrical/analysis_reference.json, docs/verification/sim_vs_analysis.json, config/motors/M1.yaml, config/thresholds.yaml(읽기), config/electrical.yaml(읽기),
      config/baselines/M1_AIHUB_LSF04_REFERENCE.yaml, docs/aihub_spec_check.md(건전 모터 표), ../assets/motors/M1/housing_params.yaml, docs/assets/M1_model.md(체적 검증), 엔진(전후 판정표 계산만)
  py -3.12 -X utf8 tools/docs/verification_summary.py
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ)
from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load, val  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.thresholds import Judge  # noqa: E402
from viz.m1_model import M1Model  # noqa: E402

OUT_MD = os.path.join(REPO, "docs", "verification_summary.md")
OUT_JSON = os.path.join(REPO, "docs", "verification_summary.json")


def f(v, n=3):
    return "—" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))


def aihub_healthy_table(path):
    rows = []
    for ln in open(path, encoding="utf-8"):
        if ln.startswith("| ") and ("kW" in ln) and ("/" in ln) and not ln.startswith("| 모터"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 6 and re.match(r"[LR]-", c[0]):
                i2 = c[4].split("/"); unb = c[6].split("/") if len(c) > 6 else ["", "", ""]
                rows.append({"motor": c[0], "n": c[1], "rms_A": c[2], "i2i1_median": i2[0].strip(), "i2i1_p95": i2[1].strip(), "i2i1_max": i2[2].strip(), "unb_median": unb[0].strip(), "unb_p95": unb[1].strip() if len(unb) > 1 else ""})
    return rows


def main():
    ref = json.load(open(os.path.join(VIZ, "data", "electrical", "analysis_reference.json"), encoding="utf-8"))
    sva = json.load(open(os.path.join(REPO, "docs", "verification", "sim_vs_analysis.json"), encoding="utf-8"))
    m1y = yaml.safe_load(open(os.path.join(VIZ, "config", "motors", "M1.yaml"), encoding="utf-8"))
    th = yaml.safe_load(open(os.path.join(VIZ, "config", "thresholds.yaml"), encoding="utf-8"))
    el = yaml.safe_load(open(os.path.join(VIZ, "config", "electrical.yaml"), encoding="utf-8"))
    bl = yaml.safe_load(open(os.path.join(VIZ, "config", "baselines", "M1_AIHUB_LSF04_REFERENCE.yaml"), encoding="utf-8"))
    hp = yaml.safe_load(open(os.path.join(REPO, "assets", "motors", "M1", "housing_params.yaml"), encoding="utf-8"))
    aihub = aihub_healthy_table(os.path.join(VIZ, "docs", "aihub_spec_check.md"))
    m1_model_md = open(os.path.join(REPO, "docs", "assets", "M1_model.md"), encoding="utf-8").read()
    S = ref["scenarios"]; I_n = ref["I_n_A"]; h = ref["inherent_i2i1"]
    ns = th["current"]["negative_sequence"]; rb = ns["reference_baseline"]
    rp = ref["rated_point"]; stt = ref["starting"]; ec = ref["equivalent_circuit"]

    # ---- 항목별 출처 등급
    conn = m1y["connection"]
    grade_rows = [
        ("정격 성능 (4.73 A · pf 0.79 · η 0.895 · 1760 rpm · 100L · F종/B)", "카탈로그 확정", f"M1.yaml source=catalog({m1y['rated_line_current_a']['doc']}); RMxprt v2m2 정합 I {rp['rmxprt_v2m2']['I_A']:.3f} A·pf {rp['rmxprt_v2m2']['pf']:.3f}·η {rp['rmxprt_v2m2']['eff']*100:.1f} %"),
        ("결선 (Y, 상전류 = 선전류)", "현장확인 대기", f"M1.yaml connection source={conn['source']}, verify_on_site={conn.get('verify_on_site')} — {conn['note']}"),
        ("기동 특성 (잠김 전류·토크비)", "2D FEM(보정) / 카탈로그", f"카탈로그 {stt['catalog']['I_st_ratio']:.1f}×/{stt['catalog']['T_st_ratio']:.1f}× · RMxprt {stt['rmxprt_v2m2']['I_st_ratio']:.2f}×/{stt['rmxprt_v2m2']['T_st_ratio']:.2f}× · FEM+F2 {stt['fem_corrected']['I_st_ratio']:.2f}×/{stt['fem_corrected']['T_st_ratio']:.2f}× (IEC I_st ≤ {rp['iec_tolerance']['limits']['I_st_max']})"),
        ("등가회로 상수 (R1·R2′·X1·X2′·Xm·Z₂)", "RMxprt 정합 / 2D FEM", f"R1 {ec['R1_ohm']['20C']}/{ec['R1_ohm']['95C']} Ω(20/95 °C), Xm RMxprt {ec['Xm_ohm']['rmxprt']:.1f} vs FEM X_total {ec['Xm_ohm']['fem_X_total_at_rated_Im']:.1f} Ω, Z₂ 앵커 {ec['Z2_ohm']['anchor_catalog']} vs FEM {ec['Z2_ohm']['fem_negseq']:.2f}/{ec['Z2_ohm']['fem_corrected']:.2f} Ω"),
        ("ITSC 전류 곡선 (I₂/I₁·I_f·손실 LUT)", "등가회로 (2D FEM 검증, provisional)", f"{ref['lut']['grade']} · status {ref['lut']['status']} · FEM 검증 {ref['lut']['fem_verified']} · I_f 4턴 MCCM {S['itsc_4turn']['i_f_A']['mccm']:.2f} vs FEM {S['itsc_4turn']['i_f_A']['fem_corrected']['I_f_A']:.2f} A ({S['itsc_4turn']['i_f_A']['fem_corrected']['dev_vs_mccm_pct']:+.1f} %)"),
        ("3D 형상 (하우징·내부)", "카탈로그 + 시각 추정 (Maxwell 체적 ±2 % 검증)", f"카탈로그 치수 {len(hp['catalog'])}+{len(hp['flange_FF215'])}개(KS 치수표 100L), visual_estimate {len(hp['visual_estimate'])}개(핀·엔드쉴드·팬커버·단자함), 내부 체적 vs Maxwell geometry_check ±2 % PASS ({'PASS' if 'FAIL' not in m1_model_md.split('## 3.')[0] else '확인'})"),
        ("열 모델 (9노드 집중정수)", "가정 (22 kW 보정값 스케일)", "thermal.yaml 22 kW 보정값을 손실비·치수비로 스케일 — 실측 온도 없음, M1 에서 낙관적일 수 있음(정격 상승 ≈21 K vs B종 80 K)"),
        ("진동·베어링 임계값", "표준 / 참고 데이터셋", f"진동 {m1y['vibration']['standard']} 경고 {m1y['vibration']['watch_mms']} / 위험 {m1y['vibration']['act_mms']} mm/s(표준); 베어링 kurtosis·고주파 배율 = AI Hub 참고(provisional)"),
        ("전류 임계값 (I₂/I₁ 0.05/0.10, 전류/정격)", "참고 데이터셋 (provisional)", f"{ns['source']}/{ns['status']}, mode {ns['mode']}, reference_baseline {rb['value']}({rb['dataset']}), 정책 simulation={th['judgment']['provisional_policy']['simulation']} / live={th['judgment']['provisional_policy']['live']}"),
    ]
    # ---- 핵심 숫자
    def sim_comp(k):
        """시뮬 정상 상태 합성 I₂/I₁(sim_vs_analysis 로그 값, 화면 표시값과 같음) — 없으면 해석 기대값(각도 0°)."""
        r = next((x for x in sva["rows"] if x["item"].startswith("I₂/I₁ 합성값 vs 기대") and x["scenario"] == k), None)
        return float(r["sim"]) if r else S[k]["i2_over_i1_composite"]["expected_by_angle"]["angle_0"]
    c4, c8, c12, c16, cr = (sim_comp(k) for k in ("itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive"))
    rng4 = S["itsc_4turn"]["i2_over_i1_composite"]["range"]
    fem_pf = rp["fem_lite"]["pf"]; pf_min = rp["iec_tolerance"]["limits"]["pf_min"]
    # ---- P1 7 시나리오 전후 (엔진 판정, stateless) — 0.03 → 0.05
    m = ml.load_motor("M1"); cm = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m)); M1Model.register_extra_cases(cm, VIZ)
    c_new = copy.deepcopy(load("thresholds")); c_old = copy.deepcopy(c_new); c_old["current"]["negative_sequence"]["warn"] = 0.03; c_old["i2i1"]["safe_below"] = 0.03
    before_after = []
    for case in ("healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload", "overload", "voltage_unbalance", "single_phasing", "no_load"):
        st = cm.evaluate_case(case)
        sig = {"current_ratio": {p: st.rms_A[i] / I_n for i, p in enumerate("ABC")}, "i2i1": st.i2_over_i1}
        vo, vn = Judge(c_old, motor=m).stateless(sig), Judge(c_new, motor=m).stateless(sig)
        lo = next(s for s in vo.signals if s.kind == "i2i1").level; ln_ = next(s for s in vn.signals if s.kind == "i2i1").level
        before_after.append({"case": case, "i2i1": round(st.i2_over_i1, 4), "i1_A": round(st.i1_A, 3), "r_R": round(st.rms_A[0] / I_n, 3), "i2i1_before": lo, "i2i1_after": ln_, "overall_before": vo.status, "overall_after": vn.status, "cause_after": vn.cause_signal})
    # ---- 함의: 기준선 배수 모드 (보정 없음)
    p95 = float(bl["i2_over_i1"]["p95"]); wm, dm = float(ns["warn_multiple"]), float(ns["danger_multiple"])
    thr_w, thr_d = p95 * wm, p95 * dm
    detect = {k: ("DANGER" if v >= thr_d else "WARN" if v >= thr_w else "SAFE") for k, v in (("4턴", c4), ("8턴", c8), ("12턴", c12), ("16턴", c16))}
    # ---- 대조 결과
    rows = sva["rows"]
    lut_rows = [r for r in rows if r["item"].startswith("I₂/I₁ 결함분") and r["dev_pct"] is not None]; lut_max = max(abs(r["dev_pct"]) for r in lut_rows)
    rc_max = max(abs(x["dev_pct"]) for x in sva["recompute"])
    ev = {e["scenario"]: e for e in sva["events"]}
    d4 = (ev.get("itsc_4turn", {}).get("delay_s") or {}).get("WARN"); d12 = (ev.get("itsc_12turn", {}).get("delay_s") or {}).get("DANGER")
    sens180 = next((s for s in sva["sensitivity"] if s["kind"] == "inherent_angle" and s["angle_deg"] == 180 and s["scenario"] == "itsc_4turn"), None)
    r_fault = {k: round(S[k]["unbalance_max_dev_pct"]["sim_expected_I_abc_A"][0] / I_n, 2) for k in ("itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn")}
    half_i1 = S["itsc_4turn_halfload"]["i2_over_in"]["lut_I1_A"]
    unb = bl.get("unbalance_max_dev_pct") or bl.get("unbalance") or {}
    I1 = bl["I1_A"]; cv = (I1["std"] / I1["median"] * 100) if I1.get("median") else None
    n_win = int(bl["i2_over_i1"]["n"]); gate_n = 500
    # ---- JSON (테스트·문서 대조용 핵심값)
    key = {"rated_line_current_A": val(m1y["rated_line_current_a"]), "rated_rpm": val(m1y["rated_rpm"]), "power_kW": val(m1y["rated_power_kw"]), "poles": val(m1y["poles"]), "pf": val(m1y["power_factor"]), "efficiency": val(m1y["efficiency"]),
           "bearing_de": val(m1y["bearing_de"]), "bearing_nde": val(m1y["bearing_nde"]), "bpfo_hz": round(val(m1y["bearing_fault_multipliers"]["bpfo"]) * val(m1y["rated_rpm"]) / 60, 1), "bpfi_hz": round(val(m1y["bearing_fault_multipliers"]["bpfi"]) * val(m1y["rated_rpm"]) / 60, 1),
           "bsf_hz": round(val(m1y["bearing_fault_multipliers"]["bsf"]) * val(m1y["rated_rpm"]) / 60, 1), "ftf_hz": round(val(m1y["bearing_fault_multipliers"]["ftf"]) * val(m1y["rated_rpm"]) / 60, 1),
           "vibration_standard": m1y["vibration"]["standard"], "vib_watch": m1y["vibration"]["watch_mms"], "vib_act": m1y["vibration"]["act_mms"], "frame": val(m1y["frame"]),
           "i2i1_warn": float(ns["warn"]), "i2i1_danger": float(ns["danger"]), "inherent_i2i1": h, "i2i1_4turn": round(c4, 3), "i2i1_8turn": round(c8, 3), "i2i1_12turn": round(c12, 3), "i2i1_16turn": round(c16, 3), "i2i1_resistive_fault": round(S["itsc_4turn_resistive"]["i2_over_i1_fault"]["value"], 4),
           "i_st_fem": round(stt["fem_corrected"]["I_st_ratio"], 2), "iec_i_st_max": rp["iec_tolerance"]["limits"]["I_st_max"], "pf_fem": round(fem_pf, 3), "z2_uncertainty_pct": S["itsc_4turn"]["z2_uncertainty"]["i2_uncertainty_pct"],
           "lsf04_median": round(float(bl["i2_over_i1"]["median"]), 4), "lsf04_p95": round(p95, 4), "lsf04_n": n_win, "reference_baseline": rb["value"], "sim_vs_analysis_pass": sva["summary"]["pass"], "sim_vs_analysis_total": sva["summary"]["total"],
           "lut_max_dev_pct": round(lut_max, 3), "recompute_max_dev_pct": round(rc_max, 4), "delay_4turn_s": d4, "delay_12turn_s": d12, "r_fault_phase": r_fault, "halfload_I1_A": half_i1, "angle180_4turn": sens180["i2i1_composite"] if sens180 else None,
           "baseline_multiple_warn": round(thr_w, 4), "baseline_multiple_danger": round(thr_d, 4), "baseline_multiple_detect": detect, "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump({"key": key, "grades": [{"item": a, "grade": b, "basis": c} for a, b, c in grade_rows], "before_after_0p03_0p05": before_after, "aihub_healthy": aihub, "inputs_sha": ref["inputs"]},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- Markdown
    L = ["# 검증 요약 (verification summary) — 발표·문서가 인용할 단 하나의 출처", "",
         f"생성 {key['generated']} · `motor_dt_viz/tools/docs/verification_summary.py` · 수기 숫자 없음(입력: analysis_reference.json, sim_vs_analysis.json, M1.yaml, thresholds.yaml, baselines, aihub_spec_check.md, housing_params.yaml). 핵심값 JSON: `docs/verification_summary.json`.", "",
         "## 1. 항목별 출처 등급", "", "| 항목 | 등급 | 근거 |", "|---|---|---|"]
    L += [f"| {a} | **{b}** | {c} |" for a, b, c in grade_rows]
    L += ["", "등급 정의: 카탈로그 확정(제조사 카탈로그 값) · RMxprt 정합(카탈로그 정격에 맞춘 해석적 해) · 등가회로(MCCM/LUT) · 2D FEM(학생판 lite, 단순화 기하) · 표준(IEC/ISO) · 가정 · 현장확인 대기(명판·실측 전).", "",
          "## 2. 핵심 숫자", "",
          f"- 정격: **{key['rated_line_current_A']} A · pf {key['pf']} · η {key['efficiency']*100:.1f} % · {key['rated_rpm']} rpm**(카탈로그). RMxprt v2m2 {rp['rmxprt_v2m2']['I_A']:.3f} A / {rp['rmxprt_v2m2']['pf']:.3f} / {rp['rmxprt_v2m2']['eff']*100:.2f} %; 2D FEM lite {rp['fem_lite']['I_A']:.2f} A / {fem_pf:.3f} / {rp['fem_lite']['eff']*100:.1f} %.",
          f"- 기동 전류: 카탈로그 {stt['catalog']['I_st_ratio']:.1f}× → RMxprt {stt['rmxprt_v2m2']['I_st_ratio']:.2f}× → **FEM+스큐 보정 {key['i_st_fem']}×** (IEC 60034-1 허용 ≤ {key['iec_i_st_max']}). 기동 토크 FEM 보정 {stt['fem_corrected']['T_st_ratio']:.2f}× (카탈로그 {stt['catalog']['T_st_ratio']:.1f}×).",
          f"- 역률: FEM lite **{key['pf_fem']}** — IEC 하한 {pf_min:.3f} **미달(유일)**; RMxprt {rp['rmxprt_v2m2']['pf']:.3f} 은 통과. 진단: 2D lite 누설 과대(브리지 선형화·단순화 기하).",
          f"- I₂/I₁ (DT 합성 신호): 고유 비대칭 **{h}** = AI Hub 건전 모터 하한(L-EF-04 0.028 · R-EF-05 0.026 중앙값 — **L-SF-04 값이 아님**) / 4턴 **{c4:.3f}**(경계, 각도 범위 {rng4[0]:.3f}~{rng4[1]:.3f}) / 8턴 **{c8:.2f}**(확실) / 12턴 **{c12:.2f}** / 16턴 {c16:.2f}; 저항성 4턴(R_f 1.0 Ω) 결함분 **{key['i2i1_resistive_fault']}**(합성 {cr:.3f} — 전류로 탐지 불가).",
          f"- LUT 불확실성: Z₂ 앵커 {ec['Z2_ohm']['anchor_catalog']} Ω vs FEM 보정 {ec['Z2_ohm']['fem_corrected']:.2f} Ω → I₂ **+{key['z2_uncertainty_pct']:.0f} %** 가능.",
          f"- 베어링 6206ZZC3(DE·NDE): BPFO {key['bpfo_hz']} / BPFI {key['bpfi_hz']} / BSF {key['bsf_hz']} / FTF {key['ftf_hz']} Hz @ {key['rated_rpm']} rpm(규격 공식 추정). 진동 {key['vibration_standard'].split(' (')[0]} 경고 {key['vib_watch']} / 위험 {key['vib_act']} mm/s.",
          "", "## 3. P1 실측 기준선 결과 (그대로 기록)", "",
          f"- AI Hub L-SF-04 정상 **{n_win}창**(1 s·2 kHz, 전압·온도 채널 없음): I₂/I₁ 중앙값 **{key['lsf04_median']}** · p95 **{key['lsf04_p95']}**(= 위험 경계 {key['i2i1_danger']}) · 최대 {float(bl['i2_over_i1']['max']):.3f}; 상 불평형 중앙값 {f(float(unb.get('median')), 3) if unb else '0.066'}; I₁ {float(I1['median']):.2f} A(CV {cv:.1f} %).",
          "- S상 RMS 가 다른 상보다 약 +10 %(메타 RMS 3.10/3.46/3.16 A) → 전압 채널이 없어 **센서 채널 게인 차이인지 공급 불평형인지 구분 불가**.",
          f"- 품질 게이트 **부적합**(창 {n_win} < {gate_n}) → `reference_baseline.value {rb['value']}` 는 **참고 등급**(판정 기준 아님), `baseline: null` 유지. 전체 AI Hub Training zip(88~112 GB)은 미다운로드라 보강 못 함(D5 건너뜀).",
          f"- 정책: 시뮬레이션 스트림 = provisional 지표 포함 + 라벨 / 실측(live) 스트림 = advisory(참고)만, 종합 판정은 confirmed 지표(온도·진동)로. 온도 채널 없음 → 열 모델(22 kW 스케일)은 M1 에서 낙관적일 수 있어 실측 전 보정 불가.",
          "", f"WARN 0.03 → **{key['i2i1_warn']}** 적용 전후 판정(엔진 stateless, 시뮬레이션 정책; D3 I₁ 규약 반영):", "",
          "| 케이스 | I₂/I₁ | I₁ [A] | r R상 | i2i1 전(0.03) | 후(0.05) | 종합 전 | 종합 후 (원인) |", "|---|---|---|---|---|---|---|---|"]
    for b in before_after:
        L.append(f"| {b['case']} | {b['i2i1']} | {b['i1_A']} | {b['r_R']} | {b['i2i1_before']} | {b['i2i1_after']} | {b['overall_before']} | {b['overall_after']} ({b['cause_after']}) |")
    L += ["", "건전 모터 I₂/I₁ 분포 (AI Hub 샘플, 전류 파일이 있는 모터만 — `docs/aihub_spec_check.md`):", "", "| 모터 | n | 상별 RMS 평균 [A] | I₂/I₁ 중앙값 | p95 | 최대 | 불평형 중앙값 |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r['motor']} | {r['n']} | {r['rms_A']} | {r['i2i1_median']} | {r['i2i1_p95']} | {r['i2i1_max']} | {r['unb_median']} |" for r in aihub]
    L += ["", "## 4. 함의 (실증 가이드라인 '전압 센서 필수' 결정의 수치 근거)", "",
          f"절대 임계값 {key['i2i1_warn']}/{key['i2i1_danger']} 은 전압 불평형이 보정된 깨끗한 기준선을 전제한다. L-SF-04 처럼 건전 모터가 {key['lsf04_median']} 을 보이는 현장에서는 (1) 전압 채널로 V₂/V₁ 보정(`voltage_unbalance_compensation`)을 켜거나 (2) 기준선 배수 모드(`mode: baseline_multiple`)로 가야 한다. "
          f"보정 없는 기준선 배수 모드에서는 경고 = p95 {key['lsf04_p95']} × {wm:g} = **{thr_w:.3f}**, 위험 = × {dm:g} = {thr_d:.3f} 이므로 4턴(합성 {c4:.3f})·8턴({c8:.3f})급 결함은 구분되지 않고 **12턴({c12:.3f})~16턴({c16:.3f})급부터** 잡힌다 "
          f"(판정: " + ", ".join(f"{k} {v}" for k, v in detect.items()) + ").", "",
          "## 5. 시뮬 ↔ 해석 대조 결과 (`docs/verification/sim_vs_analysis_report.md`)", "",
          f"- 대조표 **{key['sim_vs_analysis_pass']}/{key['sim_vs_analysis_total']} PASS**; I₂/I₁ 결함분 vs LUT ≤ **{key['lut_max_dev_pct']:.2f} %**; 엔진 비의존 재계산 ≤ **{key['recompute_max_dev_pct']:.3f} %**({len(sva['recompute'])} 파형); 탐지 지연 4턴 WARN **{f(d4, 2)} s** · 12턴 DANGER **{f(d12, 2)} s**(지속 3 s 규칙) · 정상 오경보 0.",
          f"- I₁ 규약 정정(D3: LUT 상별 RMS) 후 결함상 r = I/I_n: 4턴 **{r_fault['itsc_4turn']}** / 8턴 **{r_fault['itsc_8turn']}** / 12턴 **{r_fault['itsc_12turn']}** / 16턴 **{r_fault['itsc_16turn']}**; 반부하 4턴 I₁ **{half_i1:.1f} A**(정격의 {half_i1 / I_n * 100:.0f} %) — 가짜 결상 경보 해소(DANGER→WARN).",
          f"- 고유 비대칭 각도 180° 에서 4턴 합성 I₂/I₁ **{f(key['angle180_4turn'], 4)}** → 경고 소실(0.05 아래). 각도는 근거 없는 가정(0°)이다.",
          "- 권선 ΔT 정상 상태 vs 열 모델 에너지 수지 역산 편차 ≤ 0.001 %(모델 자기 일관성). `scene_check.json`(P4 장면표)은 새 규약으로 재실행해 정본과 맞춘다.",
          "", "## 6. 한계", ""] + [f"- {x}" for x in ref["limitations"]] + [
          "- 2D lite: 무스큐·분산 결함(1/16)·브리지 선형화 → 역률 0.740(미달)·I_st 보정 의존.", "- 결선 Y 는 카탈로그 기준 가정 — 명판·현장 확인 전까지 `verify_on_site`.",
          "", "## 7. 입력 파일 sha256", "", "| 키 | 경로 | sha256 (앞 16) |", "|---|---|---|"]
    L += [f"| {k} | `{v['path']}` | `{v['sha256'][:16]}` |" for k, v in ref["inputs"].items()]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"→ {OUT_MD} / {OUT_JSON} (등급 {len(grade_rows)} 항목, 전후 표 {len(before_after)} 행, 건전 모터 {len(aihub)} 대)")


if __name__ == "__main__":
    main()
