# -*- coding: utf-8 -*-
"""traceability.py — 근거 사슬 (V3): 화면·HUD 에 나오는 양마다 `표시량 → 엔진 함수 → 입력 파일(sha) → 해석 단계 → 출처 등급` 한 줄.
숫자는 analysis_reference.json(파일 sha 포함)에서, 문장은 여기(출처 등급·단계 설명)에서. 기계 결함은 Maxwell 근거 없음 — 상수 출처만.

  py -3.12 -X utf8 tools/verify/traceability.py → docs/verification/traceability.json + traceability.md
"""
from __future__ import annotations

import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
OUT_DIR = os.path.join(REPO, "docs", "verification")


def main():
    ref = json.load(open(os.path.join(VIZ, "data", "electrical", "analysis_reference.json"), encoding="utf-8"))
    inp = ref["inputs"]
    def f(key):
        return f"{inp[key]['path']} ({inp[key]['sha256'][:12]})"
    chain_mccm = "mccm.py: RMxprt v2m2 등가회로 상수(M400-50A_user60, 철손 데이터시트) → 다중결합 회로(Z₂ 카탈로그 앵커 7.136 Ω, 단락 루프 R_f + μR1) → 격자 160점 LUT; 2D 와전류 FEM(F1) 단락 루프 전류 ±5 % 정합"
    rows = [
        {"display": "I₂/I₁ (HUD I2/I1, 상태 보드 게이지, 대시보드 추세)", "engine": "engine/current_model.CurrentModel.waveform→analyze (phasors_from_waveform·symmetrical_components); LUT 결함 I₂ + 고유 비대칭 페이저 합",
         "inputs": [f("lut_dt"), f("electrical_yaml")], "analysis_chain": chain_mccm, "grade": "등가회로 LUT + 2D FEM 검증 (provisional, fem_verified false) + 고유 비대칭(참고 데이터셋)"},
        {"display": "I₂/I_n (HUD I2/In, 부하 무관 보조 지표)", "engine": "CurrentModel.analyze → i2_over_in = |I₂|/I_n (I_n = electrical.yaml rated_current_A 4.73)",
         "inputs": [f("lut_dt"), f("electrical_yaml"), f("m1_yaml")], "analysis_chain": chain_mccm + "; 시뮬은 I₁ 을 정격×부하로 고정하는 규약이라 LUT I₂/I_n(LUT I₁ 기준)과 분모가 다르다", "grade": "등가회로 LUT (표시 전용, 판정 없음)"},
        {"display": "상별 RMS Ia/Ib/Ic·전류/정격 비율·상태색", "engine": "CurrentModel._phasors (I₁ 피크 = √2·I_n·부하, I₂ = I₁·(r·e^{jθ}+h)) → waveform → analyze.rms_A/ratio/status",
         "inputs": [f("lut_dt"), f("m1_yaml"), f("electrical_yaml")], "analysis_chain": "LUT 의 I₂/I₁·위상(θ vs I₁) 만 쓰고 크기는 정격 규약 — LUT 자체 I_a/I_b/I_c(결함 시 I₁ 상승)와는 다름", "grade": "등가회로 LUT + 카탈로그 정격"},
        {"display": "단락 루프 전류 I_f (Coil_01_short 발광·입자, 상태 short_loop)", "engine": "CurrentModel.short_loop → LUT i_f_A (lut.query 3축 보간)",
         "inputs": [f("lut_dt")], "analysis_chain": chain_mccm + "; FEM 보정값 35.2/4.56 A 는 참고 열", "grade": "등가회로 MCCM (FEM ±5 % 정합)"},
        {"display": "단락 루프 총손실 P_loop_total (권선 노드 추가 손실, HUD basis 줄)", "engine": "CurrentModel.loop_loss_W → LUT p_loop_total_W → ThermalModel.step(extra_loss_W={winding})",
         "inputs": [f("lut_dt"), f("electrical_yaml")], "analysis_chain": "I_f²·(R_f + μ·R1_hot) + 단락 턴 동손 (MCCM)", "grade": "등가회로 MCCM"},
        {"display": "권선·로터·베어링·프레임 온도(색·HUD·게이지)", "engine": "engine/thermal_model.ThermalModel.step (RK4, 9노드 집중정수, losses: copper_i2r·iron_const·rotor_slip·bearing_friction)",
         "inputs": [f("thermal_yaml"), f("m1_yaml")], "analysis_chain": "22 kW 보정값을 손실비 P(1−η)/η·프레임 치수비로 스케일(engine/motor_library.thermal_cfg, thermal.yaml reference) — Maxwell 근거 아님", "grade": "열회로 모델(낙관 가능성, 실측 전 보정 불가)"},
        {"display": "판정 SAFE/WARN/DANGER·원인 신호·advisory", "engine": "engine/thresholds.Judge.update (worst-of, 히스테리시스 5 %, 지속 3 s, provisional 정책)",
         "inputs": [f("thresholds_yaml")], "analysis_chain": "I₂/I₁ 0.05/0.10(참고 데이터셋 provisional), 전류/정격 0.85~1.10/1.25·0.50, 온도 F종·그리스, 진동 ISO 10816-1 Class I", "grade": "임계값(표준·참고 데이터셋) — 해석값 아님"},
        {"display": "정격점(카탈로그 4.73 A·pf 0.79·η 0.895·1760 rpm) — 모터 모델 근거 표", "engine": "config/motors/M1.yaml (motor_library.motor_spec)",
         "inputs": [f("m1_yaml"), f("rmxprt"), f("eddy_summary"), f("f7")], "analysis_chain": "RMxprt v2m2 정합 4.670 A·0.791·89.58 % / 2D FEM lite 4.90 A·0.740 / IEC 60034-1 허용차", "grade": "카탈로그 (RMxprt 정합·FEM 참고)"},
        {"display": "기동 특성(잠김 전류·토크비) — 근거 표", "engine": "표시 전용 (엔진 미사용)", "inputs": [f("m1_yaml"), f("rmxprt"), f("f2")],
         "analysis_chain": "카탈로그 6.5×/2.1× ↔ RMxprt 8.24×/3.09× ↔ 2D FEM + F2 스큐 보정 7.43×/2.34×", "grade": "카탈로그 / RMxprt / 2D FEM 보정"},
        {"display": "등가회로 상수(R1·R2′·X1·X2′·Xm·Z₂) — 근거 표", "engine": "표시 전용", "inputs": [f("rmxprt"), f("temp_sweep"), f("magcurve"), f("eddy_summary"), f("inductance")],
         "analysis_chain": "RMxprt v2m2 (R1 20/95 °C 온도 스윕) ↔ 2D FEM X_total 95.6 Ω(자화 곡선 k=1) ↔ 역상 Z₂ 5.33(FEM)/5.97(보정) vs 앵커 7.136", "grade": "RMxprt 정합 / 2D FEM"},
        {"display": "기계 결함(DE 베어링·오정렬·팬·브레이크·과부하) 진동·kurtosis·고주파 지표", "engine": "engine/fault_injector (결함별 상수) + thermal.yaml faults(손실 배율·열저항)",
         "inputs": [f("thermal_yaml"), f("thresholds_yaml")], "analysis_chain": "Maxwell 근거 없음 — 진동 상수(시나리오), ISO 10816-1 Class I(표준), 베어링 지표 AI Hub 참고 데이터셋", "grade": "표준 / 참고 데이터셋 / 시나리오 상수 (해석값 아님)"},
    ]
    doc = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "generator": "motor_dt_viz/tools/verify/traceability.py", "reference_json": "motor_dt_viz/data/electrical/analysis_reference.json",
           "rows": rows, "limitations": ref["limitations"]}
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "traceability.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["# 근거 사슬 (traceability) — 화면값 → 엔진 → 입력 파일(sha) → 해석 단계 → 출처 등급", "", f"생성 {doc['generated']} · `{doc['generator']}` · 숫자 출처 `{doc['reference_json']}`", "",
         "| 표시량 | 엔진 함수 | 입력 파일 (sha256 앞 12자리) | 해석 단계 | 출처 등급 |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['display']} | `{r['engine']}` | {'<br>'.join(r['inputs'])} | {r['analysis_chain']} | **{r['grade']}** |")
    L += ["", "## 한계", ""] + [f"- {x}" for x in ref["limitations"]]
    open(os.path.join(OUT_DIR, "traceability.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    dash = os.path.join(REPO, "dashboard", "public", "data", "verification")       # V6 '근거 보기' 서랍용 사본
    os.makedirs(dash, exist_ok=True)
    json.dump(doc, open(os.path.join(dash, "traceability.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {OUT_DIR}/traceability.json·md ({len(rows)} 행)")


if __name__ == "__main__":
    main()
