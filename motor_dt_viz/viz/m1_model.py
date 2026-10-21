# -*- coding: utf-8 -*-
"""m1_model.py — M1 전체 3D 모델(assets/motors/M1/M1.usd)을 장면에 올리고 상태 JSON 값을 색·회전으로만 보여준다 (P4 ⑤).

새 계산 없음: 온도·단계·단락 루프 손실·각속도는 demo_integrated 가 이미 계산한 값을 받는다.
  - 회전: /World/M1/Rotor xformOp:rotateX ← ω(rad/s) 적분 (상태 'rpm' 과 같은 소스)
  - 색: 열 노드 9개 → 부품 그룹 (assets/motors/M1/prim_map_M1.yaml). 색 램프는 기존 ThermalColormap(config/colors.yaml) 그대로
  - Coil_01_short 발광 = p_loop_total_W / p_loop(12턴) (0 → 꺼짐, 12턴 값 → 최대)
  - 정상 기본 재질: 코일은 상별 색(A/B/C), 나머지는 재질색
  - variantSet view: full | cutaway | windings_only | half_translucent | half_translucent_front (H2: 반투명 반은 /rtx/raytracing/fractionalCutoutOpacity 를 켜야 부분 불투명으로 그려진다)
기존 22 kW 모델(/World/Motor)·전류 경로(/World/CurrentPaths)는 숨기기만 한다(물리 조인트는 그대로 rpm 을 만든다).
"""
from __future__ import annotations

import math
import os

import yaml
from pxr import Gf, Sdf, UsdGeom, UsdShade

from engine.config_loader import load
from viz.colormap import ThermalColormap

M1_PRIM = "/World/M1"
MAT_SCOPE = "/World/M1_mats"


class M1Model:
    # 카메라 (m): 모델 x ±0.185, z 0~0.25
    CAM_WIDE = ([-0.55, -0.78, 0.42], [0.0, 0.0, 0.11])
    CAM_CLOSE = ([0.33, -0.42, 0.30], [0.06, 0.0, 0.12])      # 단락 루프(Coil_01, DE 쪽 엔드턴)
    CAM_SHAFT = ([0.58, -0.36, 0.20], [0.19, 0.0, 0.10])      # 축단
    CAM_FAULT = ([0.21, -0.11, 0.25], [0.085, 0.0, 0.165])    # fault_focus: 슬롯 1(+Z) Coil_01_short DE 쪽 엔드턴 근접 (절단면 θ −45~+45° 안, 적층 끝 x 67.5 + 돌출 28 mm)
    CAM_BEARING = ([0.30, -0.16, 0.26], [0.105, 0.0, 0.10])   # bearing_de: 절단면 위에서 DE 베어링(/M1/Bearings/DE, 축 중심 z≈0.10, 엔드실드 안쪽 x≈0.10) 근접 (파트 C S2 기계 장면)
    CAM_SIDE = ([0.02, -0.95, 0.13], [0.02, 0.0, 0.11])        # side: −Y 에서 본 측면 (half_translucent 의 위 반이 비치는 각도)
    FCO_KEY = "/rtx/raytracing/fractionalCutoutOpacity"       # Render Settings → Translucency → Fractional Cutout Opacity
    HALF_GLOW = 1.5                                           # half_translucent 에서 Coil_01_short 발광 표시 세기 배율 (값이 아니라 표시 세기)

    def __init__(self, stage, asset_dir: str, view: str = "full", hide=("/World/Motor", "/World/CurrentPaths"), shots_dir: str | None = None):
        self.stage = stage
        self.asset_dir = os.path.abspath(asset_dir)
        self.pm = yaml.safe_load(open(os.path.join(self.asset_dir, "prim_map_M1.yaml"), encoding="utf-8"))
        prim = stage.DefinePrim(M1_PRIM, "Xform")
        prim.GetReferences().AddReference(os.path.join(self.asset_dir, "M1.usd").replace("\\", "/"))
        self.prim = prim
        self.cmap = ThermalColormap(load("colors"))
        self.angle_deg = 0.0
        self.view = None
        self._fco_orig = None          # half_translucent 로 바꾸기 전의 fractionalCutoutOpacity 값 (다른 variant 로 돌아가면 복귀)
        self.set_view(view)
        for p in hide:
            pr = stage.GetPrimAtPath(p)
            if pr and pr.IsValid():
                UsdGeom.Imageable(pr).MakeInvisible()
        UsdGeom.Scope.Define(stage, MAT_SCOPE)
        self.groups: dict[str, dict] = {}
        for name, g in self.pm["groups"].items():
            mat = UsdShade.Material.Define(stage, f"{MAT_SCOPE}/{name}")
            sh = UsdShade.Shader.Define(stage, f"{MAT_SCOPE}/{name}/PreviewSurface"); sh.CreateIdAttr("UsdPreviewSurface")
            sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*g["base_color"]))
            sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0, 0, 0))
            sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(float(g.get("roughness", 0.5)))
            sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(float(g.get("metallic", 0.3)))
            mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
            n_bound = 0
            for rel in g["prims"]:
                pr = stage.GetPrimAtPath(M1_PRIM + rel)
                if pr and pr.IsValid():
                    UsdShade.MaterialBindingAPI.Apply(pr).Bind(mat, bindingStrength=UsdShade.Tokens.strongerThanDescendants); n_bound += 1
            self.groups[name] = {"shader": sh, "cfg": g, "bound": n_bound}
        self.rotor = stage.GetPrimAtPath(M1_PRIM + "/Rotor")
        self.rot_attr = self.rotor.GetAttribute("xformOp:rotateX")
        self.shots_dir = shots_dir
        self.shot_plan = []            # [(t_session, view, cam_name, file)]
        self._shot_i = 0
        print(f"[m1] M1.usd 참조 · 그룹 {len(self.groups)} · 바인딩 {sum(g['bound'] for g in self.groups.values())} prim · view {view}", flush=True)

    def hide_prims(self, paths) -> None:
        for p in paths:
            pr = self.stage.GetPrimAtPath(p)
            if pr and pr.IsValid():
                UsdGeom.Imageable(pr).MakeInvisible()

    # ------------------------------------------------------------- view / rotation
    def set_view(self, view: str) -> None:
        if view == self.view:
            return
        vs = self.prim.GetVariantSet("view")
        if vs and view in vs.GetVariantNames():
            vs.SetVariantSelection(view)
        self.view = view
        self._apply_render_settings(view)

    def _apply_render_settings(self, view: str) -> None:
        """half_translucent* 이면 부분 불투명도(fractionalCutoutOpacity)를 켜고, 다른 variant 로 가면 원래 값으로 되돌린다. carb 가 없으면(테스트) 건너뛴다."""
        try:
            import carb
            s = carb.settings.get_settings()
            if view.startswith("half_translucent"):
                if self._fco_orig is None:
                    self._fco_orig = bool(s.get(self.FCO_KEY) or False)
                if not s.get(self.FCO_KEY):
                    s.set(self.FCO_KEY, True)
                    print("[m1] render: fractionalCutoutOpacity on (half_translucent)", flush=True)
            elif self._fco_orig is not None and bool(s.get(self.FCO_KEY)) != self._fco_orig:
                s.set(self.FCO_KEY, self._fco_orig)
                print(f"[m1] render: fractionalCutoutOpacity restored to {self._fco_orig}", flush=True)
        except Exception as e:  # noqa: BLE001
            print("[m1] render setting skipped:", e, flush=True)

    def set_mount(self, mount: str) -> None:
        vs = self.prim.GetVariantSet("mount")
        if vs and mount in vs.GetVariantNames():
            vs.SetVariantSelection(mount)

    # ------------------------------------------------------------- M1 전용 시나리오·추가 케이스 (electrical.yaml 불변)
    @staticmethod
    def scenario_cfg(viz_root: str, mode: str):
        """config/scenarios_M1.yaml 의 <mode> 절 (없으면 None)."""
        p = os.path.join(viz_root, "config", "scenarios_M1.yaml")
        if not os.path.exists(p):
            return None
        d = yaml.safe_load(open(p, encoding="utf-8"))
        return d.get(mode)

    @staticmethod
    def register_extra_cases(cm, viz_root: str) -> list[str]:
        """scenarios_M1.yaml extra_cases: electrical.yaml 의 템플릿 케이스를 복사해 lut {turns, R_f_ohm}·load·label 만 바꿔 런타임 등록 (파일은 건드리지 않음)."""
        p = os.path.join(viz_root, "config", "scenarios_M1.yaml")
        if not os.path.exists(p):
            return []
        d = yaml.safe_load(open(p, encoding="utf-8")); added = []
        for key, spec in (d.get("extra_cases") or {}).items():
            if key in cm.cases:
                continue
            tpl = dict(cm.cases[spec["template"]])
            tpl["label"] = spec["label"]; tpl["lut"] = {"turns": spec["turns"], "R_f_ohm": spec["R_f_ohm"]}; tpl["load"] = float(spec.get("load", 1.0))
            tpl["target_i2i1"] = None
            if "short_loop" in tpl:
                tpl["short_loop"] = {**tpl["short_loop"], "turns": spec["turns"]}
            cm.cases[key] = tpl; cm._lut_cache.pop(key, None) if hasattr(cm, "_lut_cache") else None
            added.append(key)
        return added

    def step_rotation(self, w_rad_s: float, dt_s: float) -> float:
        self.angle_deg = (self.angle_deg + math.degrees(w_rad_s * dt_s)) % 360.0
        if self.rot_attr:
            self.rot_attr.Set(self.angle_deg)
        return self.angle_deg

    # ------------------------------------------------------------- 색
    def update(self, temperatures: dict, stages: dict, time_s: float, thresholds: dict, p_loop_W: float, p_loop_max_W: float, mode: str) -> None:
        k_loop = 0.0 if p_loop_max_W <= 0 else max(0.0, min(1.0, p_loop_W / p_loop_max_W))
        for name, g in self.groups.items():
            cfg = g["cfg"]; node = cfg["thermal"]; sh = g["shader"]
            base = tuple(cfg["base_color"])
            if node in temperatures and mode in ("mechanical", "integrated"):
                s = self.cmap.sample(temperatures[node], None, stages.get(node, "normal"), time_s, thresholds.get(node))
                b = s["blend"]
                diffuse = tuple(base[i] * (1 - b) + s["diffuse"][i] * b for i in range(3))
                em = [c * min(s["intensity"], 8.0) / 8.0 * 1.5 for c in s["emissive"]]
            else:
                diffuse = base; em = [0.0, 0.0, 0.0]
            if cfg.get("short_loop"):
                glow = 6.0 * (self.HALF_GLOW if (self.view or "").startswith("half_translucent") else 1.0)   # 반투명 껍질 너머로도 보이게 표시 세기만 올린다
                em = [em[i] + c * k_loop * glow for i, c in enumerate((1.0, 0.18, 0.05))]     # UsdPreviewSurface emissiveColor 는 강도 입력이 없어 색으로 세기를 준다
            sh.GetInput("diffuseColor").Set(Gf.Vec3f(*diffuse))
            sh.GetInput("emissiveColor").Set(Gf.Vec3f(*em))

    # ------------------------------------------------------------- 스크린샷 계획
    def plan_shots(self, plan: list[tuple]) -> None:
        self.shot_plan = sorted(plan, key=lambda p: p[0]); self._shot_i = 0

    def run_shots(self, t_session: float, set_camera_view, render) -> str | None:
        if not self.shots_dir or self._shot_i >= len(self.shot_plan):
            return None
        t, view, cam, fname = self.shot_plan[self._shot_i]
        if t_session < t:
            return None
        self._shot_i += 1
        self.set_view(view)
        eye, tgt = {"wide": self.CAM_WIDE, "close": self.CAM_CLOSE, "shaft": self.CAM_SHAFT, "fault_focus": self.CAM_FAULT, "bearing_de": self.CAM_BEARING, "side": self.CAM_SIDE}[cam]
        set_camera_view(eye=eye, target=tgt)
        for _ in range(8):
            render()
        os.makedirs(self.shots_dir, exist_ok=True)
        path = os.path.join(self.shots_dir, fname)
        try:
            from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport
            capture_viewport_to_file(get_active_viewport(), path)
            for _ in range(4):
                render()
            print(f"[m1] shot {fname} (t={t_session:.1f}s, view {view}, cam {cam})", flush=True)
        except Exception as e:  # noqa: BLE001
            print("[m1] shot failed:", e, flush=True)
        return path
