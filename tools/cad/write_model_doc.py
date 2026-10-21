# -*- coding: utf-8 -*-
"""write_model_doc.py — docs/assets/M1_model.md 생성: 출처 표(카탈로그·데이터시트·시각 추정), 체적·치수 검증 표(tests/test_m1_model.py 의 계산 재사용), 폴리곤 수, 반입 경로, 장면 사용법.

  py -3.12 -X utf8 tools/cad/write_model_doc.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import test_m1_model as T  # noqa: E402

ASSET = ROOT / "assets" / "motors" / "M1"
OUT = ROOT / "docs" / "assets" / "M1_model.md"


def scene_lines(asset: Path) -> list[str]:
    p = asset / "scene_check.json"
    if not p.exists():
        return ["(장면 실행 로그 없음)"]
    sc = json.loads(p.read_text(encoding="utf-8")); f = sc["fps"]
    L = [f"- 전기 시나리오 7 장면 HUD 값(장면 끝 Ia/Ib/Ic·I₂/I₁·판정) ↔ 대시보드 fleet 로그: **{sum(1 for d in sc['steps'] if d['match'])}/{sc['n_steps']} 일치** (`{sc['run_csv']}` vs `{sc['fleet_csv']}`)",
         "", "| 장면 | 케이스 | 장면 Ia/Ib/Ic [A] | fleet Ia/Ib/Ic | I₂/I₁ 장면/fleet | I₂/I_n | 판정 장면/fleet | 일치 |", "|---|---|---|---|---|---|---|---|"]
    for d in sc["steps"]:
        L.append(f"| {d['step']} | {d['case']} | {d['Ia_rms'][0]:.1f}/{d['Ib_rms'][0]:.1f}/{d['Ic_rms'][0]:.1f} | {d['Ia_rms'][1]:.1f}/{d['Ib_rms'][1]:.1f}/{d['Ic_rms'][1]:.1f} | {d['i2_over_i1'][0]:.4f}/{d['i2_over_i1'][1]:.4f} | {d['i2_over_in'][0] or '—'} | {d['status'][0]}/{d['status'][1]} | {'✓' if d['match'] else '✗'} |")
    for d in sc.get("extra_steps", []):
        L.append(f"| {d['step']} | {d['case']} | {d['Ia_rms'][0]:.1f} (A상) | 엔진 {d['Ia_rms'][1]:.1f} | {d['i2_over_i1'][0]:.4f}/{d['i2_over_i1'][1]:.4f} (엔진 설계값) | {d['i2_over_in'][0] or '—'} | {d['status'][0]} / fleet 없음 | {'✓' if d['match'] else '✗'} |")
    L += ["", f"- FPS (1600×900, RTX 실시간): 평균 {f['mean']} · 최소 {f['min']} · full {f['full_0_12s']} / cutaway {f['cutaway_12_66s']} / windings_only {f['windings_only_66_70s']} / full(후반) {f['full_70s_']} — 30 FPS 기준 {'충족' if (f['min'] or 0) >= 30 else '미달 구간 있음'}"]
    return L


def main():
    ds = yaml.safe_load(open(ASSET / "inputs" / "datasheet_v4.yaml", encoding="utf-8"))
    gc = json.loads((ASSET / "inputs" / "geometry_check_v2.json").read_text(encoding="utf-8"))["designs"]["M1_3D_full"]
    im = json.loads((ASSET / "internals_parts.json").read_text(encoding="utf-8")); hm = json.loads((ASSET / "housing_parts.json").read_text(encoding="utf-8"))
    hp = yaml.safe_load(open(ASSET / "housing_params.yaml", encoding="utf-8"))
    ub = json.loads((ASSET / "usd_build.json").read_text(encoding="utf-8")) if (ASSET / "usd_build.json").exists() else {}
    c = {"ds": ds, "gc": gc, "im": im, "hm": hm}
    vol = T.volume_rows(c); cnt = T.count_rows(c); hou = T.housing_rows(c)
    mx = ds["maxwell_model"]
    L = ["# M1 전체 3D 모델 (현대 HLP-2.2/4, 100L) — 출처·검증·사용법", "",
         f"생성 {time.strftime('%Y-%m-%d %H:%M')} · `tools/cad/write_model_doc.py`. 입력은 `assets/motors/M1/inputs/`(PROVENANCE.md)뿐, Maxwell 폴더 쓰기 0. **새 계산 없음** — 모델은 치수를 그리는 것이고 화면값은 상태 JSON 에서 온다.", "",
         "## 1. 무엇이 카탈로그·데이터시트이고 무엇이 시각 추정인가", "",
         "| 부품 | 치수 | 출처 | 값 |", "|---|---|---|---|",
         f"| Stator_Core | D_so/D_si/L, 슬롯 수 | 데이터시트 §3·§4 (표준·계산·설계선택) | {T.dsv(ds, 'D_so', '3.')}/{T.dsv(ds, 'D_si', '3.')}/{T.dsv(ds, 'L', '3.')} mm, {mx['stator']['Q_s']} |",
         f"| Stator_Core 슬롯 프로파일 | Hs0/Hs1/Hs2/Bs0/Bs1/Bs2 | Maxwell 채택 치수(rmxprt_v2m2 inputs = 시트 §5 + RMxprt v2 오버라이드) | {mx['stator']['Hs0']}/{mx['stator']['Hs1']}/{mx['stator']['Hs2']}/{mx['stator']['Bs0']}/{mx['stator']['Bs1']}/{mx['stator']['Bs2']} |",
         f"| Coil_01…36 | 단면적 | geometry_check 'coil solid section (CoilTerm area)' (Maxwell 코일 단면 측정) | {im['coil_area_mm2']} mm² |",
         f"| Coil_01…36 | 피치·층 | 시트 §4 (피치 8/9, 2층) + 권선 배치표 | 피치 {mx['stator']['coil_pitch']} 슬롯 |",
         f"| Coil 엔드턴 | 경로 길이·돌출 | **visual_estimate** — 길이는 {im['coil_end_path_rule']} 에 맞춤, 형상(호·부풀림)은 추정 | 경로 {im['coil_end_path_mm']:.1f} mm, 축 돌출 {im['coil_end_overhang_mm']:.1f} mm |",
         f"| Coil_01_short | 분할 | Maxwell 과 같은 균일 오프셋 셸(ITSC 분할비 0.25) | 오프셋 {im['coil01_short_offset_mm']:.3f} mm → 체적비 {cnt[3]['model']:.2f} % |",
         f"| Rotor_Core | D_ro/축경/L, 슬롯 수 | 데이터시트 §3·§4 | {T.dsv(ds, 'D_ro', '3.')}/{T.dsv(ds, 'D_shaft', '3.')}/{T.dsv(ds, 'L', '3.')} mm, {mx['rotor']['Q_r']} |",
         f"| Bar_01…28 | 프로파일·스큐 | Maxwell 채택 치수(Hs0 {mx['rotor']['Hs0']} Bs1 {mx['rotor']['Bs1']} Bs2 {mx['rotor']['Bs2']} Hs2 {mx['rotor']['Hs2']}), 스큐 시트 §8 | {im['skew_deg']}° 기계각 |",
         f"| EndRing_DE/NDE | D_er/h_er/w_er | 데이터시트 §7 (설계선택·계산) | {T.dsv(ds, 'D_er', '7.')}/{T.dsv(ds, 'h_er', '7.')}/{T.dsv(ds, 'w_er', '7.')} mm |",
         f"| Shaft | 로터부 Ø, 축단 D×E, 키 | 시트 §3 D_shaft, 카탈로그 D/E/키 | {T.dsv(ds, 'D_shaft', '3.')} / {hp['catalog']['D']['value']}×{hp['catalog']['E']['value']} / {hp['catalog']['key']['value']} |",
         f"| Shaft 베어링부·NDE | Ø | 6206 내경(표준) / NDE visual_estimate | {im['layout_visual_estimate']['bearing_6206']['id']} / {im['layout_visual_estimate']['shaft_nde_d_mm']} |",
         f"| Bearing_DE/NDE | 6206 내경·외경·폭 | 규격(표준), 위치 visual_estimate | 30/62/16, x ±{im['layout_visual_estimate']['bearing_x_mm']} |",
         "| 하우징 Foot | H·A·AB·HA·B·BB·C·K | 카탈로그 KS 형식 치수표 100L | " + ", ".join(f"{k} {hp['catalog'][k]['value']}" for k in ("H", "A", "AB", "HA", "B1", "BB", "C", "K")) + " |",
         "| 하우징 EndShield_DE 플랜지 | M·N·P·n·S·LA·T | 카탈로그 KS 플랜지 치수표 100L (B35 옵션으로 포함) | " + ", ".join(f"{k} {hp['flange_FF215'][k]['value']}" for k in ("M", "N", "P", "n", "S", "LA", "T")) + " |",
         f"| 하우징 전장·높이 | L·HC·HD·O·PF | 카탈로그 | L {hp['catalog']['L']['value']}, HC {hp['catalog']['HC']['value']}, HD {hp['catalog']['HD']['value']}, O {hp['catalog']['O']['value']}, PF {hp['catalog']['PF']['value']} |",
         f"| 하우징 AD | 끝면도 전체 폭(프레임 측면~단자함 끝) | 카탈로그 (치수선 정의 확인) | {hp['AD']['value']} (플랜지형 {hp['AD']['value_flange_table']}) — 모델 전체 폭 ≤ AD 구속 |",
         "| 하우징 나머지 | AC·핀·엔드쉴드 두께·팬 커버·단자함 크기·위치·아이볼트 링·배치(어깨 x 125, 베어링 x ±108) | **visual_estimate** (housing_params.yaml) | " + ", ".join(f"{k} {v['value']}" for k, v in list(hp["visual_estimate"].items())[:6]) + " … |",
         "", "## 2. 체적 검증 (geometry_check_v2.json = Maxwell M1_3D_full 측정값, ±2 %)", "",
         "| 항목 | 모델 | 기준 | 기준 출처 | 편차 | 판정 |", "|---|---|---|---|---|---|"]
    for r in vol:
        gate = r.get("gate", True)
        L.append(f"| {r['item']} | {r['model']:,.0f} | {r['ref']:,.0f} | {r['ref_src']} | {r['dev_pct']:+.2f} % | {'PASS' if r['pass'] else 'FAIL'}{'' if gate else ' (시트 추정 — 참고)'} |")
    L += ["", "| 검사 | 모델 | 기준 | 판정 |", "|---|---|---|---|"]
    for r in cnt:
        L.append(f"| {r['item']} | {r['model']:.3f} | {r['ref']} | {'PASS' if r['pass'] else 'FAIL'} |" if isinstance(r["model"], float) else f"| {r['item']} | {r['model']} | {r['ref']} | {'PASS' if r['pass'] else 'FAIL'} |")
    L += ["", "## 3. 하우징 치수 (STEP 재판독 vs 카탈로그, ±0.5 mm)", "", "| 치수 | STEP 재판독 | 카탈로그 | 판정 |", "|---|---|---|---|"]
    for r in hou:
        L.append(f"| {r['item']} | {r['model']:.2f} | {r['ref']:.1f} | {'PASS' if r['pass'] else 'FAIL'} |")
    L += ["", "## 4. 폴리곤 수·파일", "",
          f"- 내부 {im['triangles_total']:,} 삼각형 (cutaway {im['cutaway_triangles']:,}) · 하우징 {hm['triangles_total']:,} (cutaway {hm['cutaway_triangles']:,}) · 합 {im['triangles_total'] + hm['triangles_total']:,} ≤ 300k. 엔드턴 스플라인 분할 `--end-segments`(기본 10), 메시 허용오차는 스크립트 `tol/ang`.",
          "- `assets/motors/M1/`: internals.step(보관, 27 MB) · internals.obj/.glb · internals_cutaway.obj/.glb · internals_parts.json(재질·체적·삼각형) · housing_100L.step · housing.obj/.glb · housing_cutaway.* · housing_parts.json · housing_params.yaml",
          f"- USD: M1_internals.usd / M1_internals_cutaway.usd / M1_housing.usd / M1_housing_cutaway.usd (omni.kit.asset_converter) → M1.usd 조립 (prim {ub.get('prims', '—')}, 메시 {ub.get('mesh_counts', '—')})",
          "", "## 4b. view variant 4+1종 · 반절 반투명 (H1~H3, 2026-10-21)", "",
          "| variant | 하우징·고정자 코어 | 그 밖(권선·로터·축·베어링) | 메시 파일 | 용도 |", "|---|---|---|---|---|",
          "| `full` | 원형 | 원형 | housing.obj / internals.obj | 외형 |",
          "| `cutaway` | θ −45~+45° 1/4 절단 | 원형 | *_cutaway.obj | 슬롯 1·Coil_01 노출 |",
          "| `windings_only` | 숨김 | 코일만 | internals.obj | 권선 배치 |",
          "| `half_translucent` | 위 반(`_T`, Z > 축 중심) 반투명 / 아래 반(`_B`) 불투명 | 원형(불투명) | housing_half_top.obj / internals_half_top.obj | 외형 유지 + 내부 비침 (기본) |",
          "| `half_translucent_front` | 카메라 쪽 반(`_F`, Y < 0) 반투명 / 반대(`_R`) 불투명 | 원형(불투명) | *_half_front.obj | 측면 카메라용 |", "",
          "- 반 분할은 **자르지 않고 나눈다**: 조각 체적 합 = 원본 ±0.1 %(`tests/test_m1_model.py::test_half_split_volume_sums`). 대상은 Foot 을 뺀 하우징 전 부품 + Stator_Core. "
          + " · ".join(f"{s_}: 하우징 {hm['half_split'][s_]['triangles']:,} + 코어 {im['half_split'][s_]['triangles']:,} 삼각형, 체적 편차 최대 {max(abs(r['dev_pct']) for r in list(hm['half_split'][s_]['parts'].values()) + list(im['half_split'][s_]['parts'].values())):.4f} %" for s_ in hm.get("half_split", {})) + ". 빈 조각(top 분할의 아이볼트 `_B`)은 메시를 만들지 않는다.",
          f"- 재질: `/M1/Looks/translucent_housing`(주철 색, opacity {ub.get('translucent_materials', {}).get('translucent_housing', {}).get('opacity', 0.20)}) · `translucent_core`(규소강 색, opacity {ub.get('translucent_materials', {}).get('translucent_core', {}).get('opacity', 0.35)}) — **UsdPreviewSurface `opacity`**(+ `opacityThreshold` 0) 채택. 기존 파이프라인이 UsdPreviewSurface 라 같은 방식이 가장 단순하고, RTX 실시간에서 부분 불투명도 설정만 켜면 블렌딩 순서 문제(겹침·검은 테두리) 없이 그려졌다. OmniGlass `thin_walled` 는 대안으로만 둔다(MDL 의존·굴절 없음).",
          "- 렌더 설정 한 줄: `/rtx/raytracing/fractionalCutoutOpacity = true` — `viz/m1_model.M1Model.set_view()` 가 half_translucent* 선택 시 켜고 다른 variant 로 돌아가면 원래 값으로 복귀. Coil_01_short 발광은 반투명 껍질 너머로 보이도록 표시 세기 ×1.5(`HALF_GLOW`, 값 아님).",
          "- 반투명 조각은 variant 안에서만 정의되는 형제 prim(`/M1/Housing/Frame_T` 등)이라 런타임 온도 색(그룹 재질, 불투명 반에 바인딩)의 영향을 받지 않는다. 분할선(평면 가장자리)은 그대로 둔다.",
          "- 스크린샷 `docs/assets/screenshots/M1_half/`(정상 측면·등각, 4턴 fault_focus, DE 베어링), FPS 는 SESSION_LOG 해당 장.",
          "", "## 5. 결정 대기·한계", "",
          f"- **코일 엔드턴 길이(결정 2026-10-21)**: 정본 = `--end-path geometry_check`(Maxwell RMxprt 자동 엔드코일 체적에서 역산한 경로 {im['coil_end_path_mm']:.1f} mm, 축 돌출 {im['coil_end_overhang_mm']:.1f} mm). 시트 l_end {T.dsv(ds, 'l_end', '6.'):.2f} mm 는 **시트 추정(참고)** — 그 규칙이면 코일 1개 {2 * im['coil_area_mm2'] * (T.dsv(ds, 'L', '3.') + T.dsv(ds, 'l_end', '6.')):,.0f} mm³(+{(2 * im['coil_area_mm2'] * (T.dsv(ds, 'L', '3.') + T.dsv(ds, 'l_end', '6.')) / gc['coil_volume_mm3'] - 1) * 100:.1f} %).",
          f"- **AD 328(카탈로그)**: {hp['AD']['note']}",
          f"- 플랜지: USD variant `mount` = B3(기본, 플랜지 없음) / B35(FF215, 카탈로그 B35 옵션 치수; P 250 > 2H 200 이라 발 바닥 아래 25 mm — 실물과 같음). {hp.get('mount_variants', {})}",
          "- 온도 색: 열 모델은 전기 전용 모드에서 적분하지 않는다(`demo_integrated` 가 `dt_sim_s=0` 으로 호출) → 온도 색은 **기계·통합 모드에서만** 적용되고 전기 모드는 상별 기본색이다.",
          "- 엔드턴·핀·단자함·팬 커버·아이볼트는 시각 추정이며 어떤 계산에도 쓰지 않는다. 베어링은 6206 규격 치수를 그린 시각 모델이다.",
          "- 슬롯 안 코일 단면은 Maxwell 과 같은 21.15 mm² 사다리꼴(슬롯 라이너 0.3 mm 가정)로 층 중앙에 두었다(층 중심 r " + f"{im['coil_layer_center_r_mm']['top']:.1f}/{im['coil_layer_center_r_mm']['bottom']:.1f} mm).",
          "", "## 5b. 장면 확인 (assets/motors/M1/scene_check.json — tools/cad/check_m1_scene.py)", ""] + scene_lines(ASSET) + [
          "", "## 6. 반입 경로·장면 사용법", "",
          "1. `py -3.12 -X utf8 tools/cad/datasheet_to_yaml.py` → `py -3.12 -X utf8 tools/cad/build_internals_M1.py` → `py -3.12 -X utf8 tools/cad/build_housing_100L.py`",
          "2. `py -3.12 -X utf8 -m pytest tests/test_m1_model.py -q` (체적·치수·개수·삼각형)",
          "3. `C:\\ISSACS~1\\python.bat tools\\cad\\build_usd_M1.py` (저장소 루트에서, 상대 경로) → `assets/motors/M1/M1.usd`",
          "4. 장면: `cd motor_dt_viz ; C:\\ISSACS~1\\python.bat app\\demo_integrated.py --gui --autoplay --mode electrical --motor M1 --m1_model [--view cutaway|windings_only]` — 22 kW 물리 모델은 숨긴 채 rpm·온도·전류 상태만 M1 USD 에 매핑한다(`motor_dt_viz/config` 변경 없음, 매핑은 `assets/motors/M1/prim_map_M1.yaml`).",
          "5. USD 계층: /M1(스케일 0.001 = mm→m) /Housing(EndShield_DE = B3, EndShield_DE_B35) /Stator(Core, Coils/Coil_01…36, Coils/Coil_01_short) /Rotor(xformOp:rotateX 회전 대상: Core, Bars, EndRing_DE/NDE, Shaft) /Bearings(DE, NDE) /Looks. variantSet `view` = full | cutaway(θ −45~+45° 절단, 슬롯 1 노출) | windings_only | half_translucent | half_translucent_front, `mount` = B3 | B35.",
          "6. M1 전용 전기 시나리오 `motor_dt_viz/config/scenarios_M1.yaml`(기존 7 + 8턴·16턴·저항성 4턴 R_f 1.0·반부하 4턴 50 %): `--m1_model` 이면 자동 사용, 추가 케이스는 electrical.yaml 의 itsc_4turn 템플릿에 lut {turns, R_f_ohm}·load 만 바꿔 런타임 등록(electrical.yaml 불변). 카메라 프리셋 `fault_focus`(Coil_01_short 근접) — 스크린샷 03/04."]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{OUT} · 체적 {sum(r['pass'] for r in vol if r.get('gate', True))}/{sum(1 for r in vol if r.get('gate', True))} · 개수 {sum(r['pass'] for r in cnt)}/{len(cnt)} · 치수 {sum(r['pass'] for r in hou)}/{len(hou)}")


if __name__ == "__main__":
    main()
