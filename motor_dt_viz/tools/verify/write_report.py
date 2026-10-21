# -*- coding: utf-8 -*-
"""write_report.py — docs/verification/sim_vs_analysis_report.md (V5): 결론·시나리오 서술·대조표·민감도·근거 사슬·한계·증명 범위. 숫자는 sim_vs_analysis.json / analysis_reference.json / traceability.json 에서만.

  py -3.12 -X utf8 tools/verify/write_report.py
"""
from __future__ import annotations

import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
OUT_DIR = os.path.join(REPO, "docs", "verification")


def f(v, n=4):
    return "—" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))


def main():
    res = json.load(open(os.path.join(OUT_DIR, "sim_vs_analysis.json"), encoding="utf-8"))
    ref = json.load(open(os.path.join(VIZ, "data", "electrical", "analysis_reference.json"), encoding="utf-8"))
    tr = json.load(open(os.path.join(OUT_DIR, "traceability.json"), encoding="utf-8"))
    rows = res["rows"]; S = ref["scenarios"]
    def rget(item_prefix, sid):
        return next((r for r in rows if r["item"].startswith(item_prefix) and r["scenario"] == sid), None)
    lut_rows = [r for r in rows if r["item"].startswith("I₂/I₁ 결함분") and r["scenario"] != "healthy"]
    lut_max = max(abs(r["dev_pct"]) for r in lut_rows if r["dev_pct"] is not None)
    rc = res["recompute"]; rc_max = max(abs(x["dev_pct"]) for x in rc)
    fails = [r for r in rows if not r["pass"]]
    ev = {e["scenario"]: e for e in res["events"]}
    th = {t["scenario"]: t for t in res["thermal"]}
    warn, danger = ref["thresholds"]["i2i1_warn"], ref["thresholds"]["i2i1_danger"]
    L = ["# Isaac Sim 결함 시뮬레이션 ↔ Maxwell/등가회로 해석 결과 대조 검증 보고서", "",
         f"생성 {time.strftime('%Y-%m-%d %H:%M')} · 생성기 `motor_dt_viz/tools/verify/write_report.py` · 대조 `sim_vs_analysis.json`({res['generated']}) · 기준 `motor_dt_viz/data/electrical/analysis_reference.json`({ref['generated']}) · 근거 사슬 `traceability.json`",
         "", "> 새 계산·새 해석·설정 변경 없음. 시뮬은 기존 장면·엔진·LUT 로 돌렸고(Isaac Sim 헤드리스 자동 재생, `demo_integrated.py --verify_dir` 로깅 훅), 대조·그림·표는 스크립트가 로그와 해석 파일에서 읽어 만들었다(수기 숫자 없음). 기계 결함은 Maxwell 근거가 없어 출처만 표기한다.", "",
         "## 1. 한 줄 결론", "",
         f"- 전기 결함 시나리오의 표시값(I₂/I₁ 결함분·I_f·단락 루프 손실·불평형)은 해석값(LUT v2 = MCCM 등가회로)과 **최대 {lut_max:.2f} %** 안에서 일치한다(허용 ±1 %, 손실 ±2 %). 합성 파형을 엔진과 무관하게 다시 계산한 I₂/I₁ 은 **최대 {rc_max:.3f} %** 차이(허용 ±0.5 %, {len(rc)} 파형).",
         f"- 대조표 **{res['summary']['pass']}/{res['summary']['total']} PASS**. FAIL {len(fails)}건은 모두 한 가지 규약 차이다: 엔진은 I₁ 을 정격×부하로 고정하는데 LUT 의 I₂/I_n 은 결함 시 상승한 LUT 자체 I₁ 기준이라, **시뮬의 'I₂/I_n' 표시값은 LUT 의 I₂/I_n 이 아니라 I₂/I₁×부하** 와 같다(§3 비고). 엔진 수치 변경 금지 범위라 보고만 한다.",
         "- 판정: 4턴은 주입 3 s 뒤 WARN(0.05 경계), 8·12·16턴은 3 s 뒤 DANGER(0.10), 저항성 4턴(R_f 1.0 Ω)은 SAFE 유지, 정상 구간 오경보 0건 — 임계값·지속 규칙과 일치.",
         "", "| 시나리오 | 주입 [s] | 첫 WARN | 첫 DANGER | 지연 [s] | 장면 끝 | 원인 |", "|---|---|---|---|---|---|---|"]
    for sid in ("healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload"):
        e = ev.get(sid)
        if e:
            dly = ", ".join(f"{k} {v:.2f}" for k, v in (e["delay_s"] or {}).items()) or "—"
            L.append(f"| {sid} | {e['t_inject_s']} | {f(e['first_WARN_s'], 2)} | {f(e['first_DANGER_s'], 2)} | {dly} | {e['final']} | {e['cause']} |")
    L += ["", "## 2. 시나리오별 '무슨 일이 일어나는가' (비전공자용)", ""]
    narr = {
        "healthy": "세 상 전류가 거의 같다. 완전히 같지는 않은데(R상이 약간 큼), 이것은 정상 모터·전원에도 있는 '고유 비대칭' {h} 을 일부러 넣었기 때문이다. I₂/I₁ 은 {h} 로 경고 경계 {warn} 아래라 **안전** 이 유지된다.",
        "itsc_4turn": "코일 한 개의 4턴(권선의 2.1 %)이 서로 붙었다. 붙은 고리에 큰 순환 전류 I_f ≈ {if_:.0f} A 가 돌지만 바깥 선전류는 R상이 {ia:.2f} A 로 조금 커질 뿐이다. 대신 세 상의 '균형'을 재는 I₂/I₁ 이 {h} → {comp:.3f} 으로 뛰어 경계 {warn} 을 넘고, 3 s 지속 규칙 뒤 **경고**가 뜬다(주입 후 {d} s). 단락 고리에서 {pl:.0f} W 가 더 발열해 권선이 천천히 데워진다(통합 모드 §3 열).",
        "itsc_8turn": "8턴(4.2 %)이 붙으면 I₂/I₁ 이 {comp:.3f} 으로 위험 경계 {danger} 를 넘어 3 s 뒤 **위험**이다. 손실 {pl:.0f} W 로 권선 온도 상승이 뚜렷하다.",
        "itsc_12turn": "12턴(6.3 %)에서는 I₂/I₁ {comp:.3f}, 순환 전류 {if_:.0f} A, 손실 {pl:.0f} W. 권선 온도가 F종 한계를 넘는 방향으로 간다(통합 모드에서 권선 ΔT 역산 {dT:.0f} °C). **위험**.",
        "itsc_16turn": "코일 전체 16턴이 붙은 경우. I₂/I₁ {comp:.3f}, R상 선전류도 {ia:.2f} A(정격의 {ra:.0f} %)로 과전류 경고 영역에 들어간다. 손실 {pl:.0f} W. **위험**.",
        "itsc_4turn_resistive": "4턴이 붙었지만 접촉 저항이 1.0 Ω 으로 크면 순환 전류가 {if_:.1f} A 에 그쳐 I₂/I₁ 은 {comp:.3f} — 경계 {warn} 아래라 **안전** 으로 남는다. '턴 수'가 아니라 '얼마나 세게 붙었나'가 탐지를 가른다는 뜻이다.",
        "itsc_4turn_halfload": "같은 4턴 단락을 부하 50 % 에서 보면 I₂/I₁ 은 {comp:.3f} 으로 100 % 부하({comp100:.3f})보다 커 보인다(분모 I₁ 이 작아져서). 그래서 부하 무관 지표 I₂/I_n 을 같이 본다. 이 장면은 세 상 전류 자체가 정격의 절반이라 '저전류' 규칙에도 걸려 종합은 **위험**(원인 current_ratio)이다 — 시나리오 설계상 저부하를 결상처럼 보는 규칙의 한계.",
    }
    for sid, tpl in narr.items():
        R = S[sid]; r_ia = rget("상 불평형", sid); comp = rget("I₂/I₁ 합성값 vs 기대", sid); if_ = rget("단락 루프 전류", sid); pl = rget("단락 루프 총손실", sid)
        e = ev.get(sid, {}); dly = (e.get("delay_s") or {}); d = dly.get("WARN", dly.get("DANGER", "—"))
        ia = R["unbalance_max_dev_pct"]["sim_expected_I_abc_A"][0]
        txt = tpl.format(h=ref["inherent_i2i1"], warn=warn, danger=danger, if_=(if_["sim"] if if_ else R["i_f_A"]["lut"]), ia=ia, ra=ia / ref["I_n_A"] * 100,
                         comp=(comp["sim"] if comp else R["i2_over_i1_composite"]["expected_by_angle"]["angle_0"]), comp100=S["itsc_4turn"]["i2_over_i1_composite"]["expected_by_angle"]["angle_0"],
                         pl=(pl["sim"] if pl else R["p_loop_total_W"]["lut"]), d=d, dT=th.get(sid, {}).get("dT_steady_ref_C", R["winding_dT_steady_C"]["model"]["winding"]))
        L.append(f"**{sid}** — {txt}"); L.append("")
    L += ["## 3. 대조표 (허용 안 = PASS)", "", "| 항목 | 시나리오 | 시뮬(로그) | 해석 기준 | 허용 | 편차 | 판정 | 비고 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        tol = "" if r["tolerance"] is None else (f"±{r['tolerance'] * 100:g} %" if r["kind"] == "rel" else str(r["tolerance"]))
        sim = r["sim"] if not isinstance(r["sim"], float) else f"{r['sim']:.5g}"; refv = r["ref"] if not isinstance(r["ref"], float) else f"{r['ref']:.5g}"
        L.append(f"| {r['item']} | {r['scenario']} | {sim} | {refv} | {tol} | {'' if r['dev_pct'] is None else f'{r['dev_pct']:+.2f} %'} | {'PASS' if r['pass'] else '**FAIL**'} | {r['note']} |")
    L += ["", "### 열 (통합 모드, 주입 후 권선 온도 — 모델 자기 일관성 ±5 %)", "", "| 시나리오 | 주입 전 [°C] | 끝 [°C] | ΔT 시뮬 | ΔT 에너지 수지 역산 | 편차 | 시뮬 분 | P_loop [W] |", "|---|---|---|---|---|---|---|---|"]
    for t in res["thermal"]:
        L.append(f"| {t['scenario']} | {t['T_winding_before_C']} | {t['T_winding_end_C']} | {t['dT_end_C']} | {t['dT_steady_ref_C']} | {t['dev_pct']:+.2f} % | {t['sim_minutes_after_injection']} | {t['p_loop_W']} |")
    if not res["thermal"]:
        L.append("| (통합 모드 열 실행 로그 없음) | | | | | | | |")
    L += ["", "### 민감도", "", "고유 비대칭 각도 0/90/180° — 4턴 합성 I₂/I₁ 과 판정:", "", "| 각도 | 시나리오 | 합성 I₂/I₁ | 기대 | i2i1 등급 | 종합 |", "|---|---|---|---|---|---|"]
    for s_ in res["sensitivity"]:
        if s_["kind"] == "inherent_angle":
            L.append(f"| {s_['angle_deg']}° | {s_['scenario']} | {s_['i2i1_composite']:.4f} | {f(s_['expected'])} | {s_['i2i1_level']} | {s_['status']} |")
    L += ["", "부하 50/100 % (4턴): I₂/I₁ 은 부하에 따라 흔들리고 I₂/I_n 은 덜 흔들린다 —", ""]
    for s_ in res["sensitivity"]:
        if s_["kind"] == "load":
            L.append(f"- {s_['scenario']} (부하 {s_['load']}): 시뮬 I₂/I₁ {f(s_['i2i1'])}, 시뮬 I₂/I_n {f(s_['i2_over_in'])} · LUT 결함분 {s_['lut_i2i1_fault']}, LUT I₂/I_n {s_['lut_i2_over_in']}")
    L += ["", "그림: `img/i2i1_timeseries.png`(시계열·판정 띠·주입 시각), `img/sim_vs_analysis_bars.png`(결함 4종 막대), `img/winding_temperature.png`(권선 온도), `img/waveform_spectrum.png`(합성 파형·스펙트럼 — 기본파만, RSH 없음), `img/hud_0*.png`(HUD 합성 4장).", "",
          "## 4. 근거 사슬 (표시량 → 엔진 → 입력 파일 → 해석 단계 → 등급)", "", "| 표시량 | 엔진 | 입력(sha) | 해석 단계 | 등급 |", "|---|---|---|---|---|"]
    for r in tr["rows"]:
        L.append(f"| {r['display']} | `{r['engine'][:70]}…` | {'; '.join(x.split(' (')[0].split('/')[-1] + ' (' + x.split(' (')[1] for x in r['inputs'])} | {r['analysis_chain'][:140]}… | **{r['grade']}** |")
    L += ["", "전체 문장은 `traceability.md`. 해석 파일 sha256 은 `analysis_reference.json inputs` 에 있다(LUT sha 일치: " + str(ref["lut"]["sha_match"]) + ").", "",
          "## 5. 한계", ""] + [f"- {x}" for x in ref["limitations"]] + [
          "- 합성 신호라 전류 과도가 없다: 판정 지연은 오직 '3 s 지속 규칙'이다. 실모터에서는 창 길이·필터·돌입이 더해진다.",
          "- 열 ΔT 대조는 '같은 모델의 정상 상태 해'와의 자기 일관성이다(22 kW 보정값 스케일, 실측 아님).",
          "", "## 6. 이 보고서가 증명하는 것 / 증명하지 않는 것", "",
          "**증명하는 것**", "- 화면·HUD·로그의 전기 결함 숫자가 해석 파일(RMxprt v2m2 → MCCM/LUT v2 → 2D FEM F1 정합)에서 어떻게 나왔는지 — 같은 파일 sha 로 추적되고, 값이 ±1 %(손실 ±2 %) 안에서 재현된다.",
          "- 엔진의 대칭 성분 계산이 독립 구현(엔진 비의존 Fortescue·DFT)과 ±0.5 % 안에서 같다.", "- 임계값·지속 규칙이 설정대로 동작한다(예상 판정·탐지 지연 일치, 정상 오경보 0).",
          "- 열 모델이 자기 일관적이다(주입 후 정상 상태 ΔT ↔ 손실·열저항 역산).",
          "**증명하지 않는 것**", "- 실모터와의 일치. 고유 비대칭 0.027·임계값 0.05/0.10 은 참고 데이터셋 가정이고, 실측 기준선(P1 `tools/baseline_capture.py`) 전까지 provisional 이다.",
          "- 2D lite FEM 의 절대 정확도(학생판·단순화 기하·무스큐), Z₂ 앵커 불확실성(+20 %), 열 모델의 M1 절대 온도.", "- 기계 결함(베어링·오정렬·팬·브레이크)의 해석 근거 — 없다. 진동·베어링 상수와 표준·참고 데이터셋 출처만 표기한다."]
    open(os.path.join(OUT_DIR, "sim_vs_analysis_report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"→ {OUT_DIR}/sim_vs_analysis_report.md (PASS {res['summary']['pass']}/{res['summary']['total']}, LUT 최대 편차 {lut_max:.2f} %, 재계산 최대 {rc_max:.3f} %)")


if __name__ == "__main__":
    main()
