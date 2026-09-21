# -*- coding: utf-8 -*-
"""material_driver.py — 부품별 전용 머티리얼 생성·갱신 (USD/Isaac Sim 의존).

Hard Rule 2: 원본 USD 를 수정하지 않는다 → 머티리얼은 런타임 스테이지에만 만들고,
             필요 시 layers/viz_override.usda 로 따로 저장한다.
Hard Rule 3: 공유 머티리얼을 바꾸지 않는다 → prim 마다 전용 머티리얼을 새로 만들어 바인딩한다.
Hard Rule 5: 갱신을 10~20 Hz 로 스로틀링한다.

머티리얼 백엔드:
  · OmniPBR (MDL) — diffuse_color_constant / emissive_color / emissive_intensity (CLAUDE.md 권장)
  · UsdPreviewSurface — diffuseColor / emissiveColor (폴백, MDL 사용 불가 환경)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pxr import Gf, Sdf, UsdShade

from engine.config_loader import load
from viz.colormap import ThermalColormap

MATERIAL_SCOPE = "/World/VizMaterials"     # 우리가 만든 머티리얼만 모아두는 곳


class MaterialDriver:
    """부품 prim 에 전용 머티리얼을 붙이고 온도에 따라 색·발광을 갱신한다."""

    def __init__(self, stage, prim_map: dict | None = None, colors: dict | None = None,
                 prefer_omnipbr: bool = True, update_hz: float = 15.0):
        self.stage = stage
        self.prim_map = prim_map or load("prim_map")
        self.cmap = ThermalColormap(colors)
        self.prefer_omnipbr = prefer_omnipbr
        self.update_interval = 1.0 / float(update_hz)
        self._last_update = -1e9
        self.backend = "none"
        self.materials: dict[str, dict] = {}      # part_key → {"path", "shader", "backend"}
        self._skipped: list[str] = []
        UsdShade.Material.Define(self.stage, MATERIAL_SCOPE) if False else None
        from pxr import UsdGeom
        UsdGeom.Scope.Define(self.stage, MATERIAL_SCOPE)

    # ------------------------------------------------------------- 생성
    def setup(self, part_keys: list[str] | None = None) -> dict:
        """대상 부품에 전용 머티리얼을 생성·바인딩한다. 반환: 생성 요약."""
        parts = self.prim_map["parts"]
        keys = part_keys or [k for k, v in parts.items() if v.get("status") == "confirmed"]
        for key in keys:
            info = parts.get(key)
            if not info or info.get("status") != "confirmed":
                self._skipped.append(key)
                continue
            mesh_path = info.get("mesh_path") or info.get("target_path")
            prim = self.stage.GetPrimAtPath(mesh_path)
            if not prim or not prim.IsValid():
                self._skipped.append(key)
                continue
            mat = self._create_material(key)
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat["material"])
            self.materials[key] = mat
        return {"backend": self.backend, "bound": list(self.materials), "skipped": self._skipped}

    def _create_material(self, key: str) -> dict:
        """OmniPBR 우선, 실패 시 UsdPreviewSurface."""
        base = self.cmap.base_material(key)
        path = f"{MATERIAL_SCOPE}/mat_{key}"
        if self.prefer_omnipbr:
            try:
                mat = self._create_omnipbr(path, base)
                self.backend = "OmniPBR"
                return mat
            except Exception as e:                 # MDL 미가용 환경 → 폴백
                if self.backend != "UsdPreviewSurface":
                    print(f"[material_driver] OmniPBR 실패 → UsdPreviewSurface 폴백: {e}", flush=True)
        mat = self._create_preview(path, base)
        self.backend = "UsdPreviewSurface"
        return mat

    def _create_omnipbr(self, path: str, base: dict) -> dict:
        import omni.kit.commands
        from omni.kit.material.library import get_mdl_list  # noqa: F401  (가용성 확인용)

        ok, _ = omni.kit.commands.execute(
            "CreateMdlMaterialPrimCommand", mtl_url="OmniPBR.mdl", mtl_name="OmniPBR", mtl_path=path
        )
        prim = self.stage.GetPrimAtPath(path)
        if not ok or not prim or not prim.IsValid():
            raise RuntimeError("CreateMdlMaterialPrimCommand 실패")
        shader = UsdShade.Shader(self.stage.GetPrimAtPath(path + "/Shader"))
        if not shader:
            raise RuntimeError("OmniPBR Shader prim 없음")
        shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*base["color"]))
        shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(float(base["roughness"]))
        shader.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(float(base["metallic"]))
        shader.CreateInput("enable_emission", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("emissive_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0, 0, 0))
        shader.CreateInput("emissive_intensity", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("enable_opacity", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("opacity_constant", Sdf.ValueTypeNames.Float).Set(1.0)
        return {"path": path, "material": UsdShade.Material(prim), "shader": shader, "backend": "OmniPBR"}

    def _create_preview(self, path: str, base: dict) -> dict:
        mat = UsdShade.Material.Define(self.stage, path)
        shader = UsdShade.Shader.Define(self.stage, path + "/PreviewSurface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*base["color"]))
        shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0, 0, 0))
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(float(base["roughness"]))
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(float(base["metallic"]))
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0)
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        return {"path": path, "material": mat, "shader": shader, "backend": "UsdPreviewSurface"}

    # ------------------------------------------------------------- 투명도
    def set_opacity(self, part_keys: list[str], opacity: float) -> list[str]:
        """하우징 투명도 토글 (CLAUDE.md §6.2) — 내부 베어링·로터가 보이게 한다.

        베어링은 엔드실드 안에 있어 불투명하면 발열 색이 보이지 않는다.
        """
        changed = []
        for key in part_keys:
            mat = self.materials.get(key)
            if not mat:
                continue
            sh = mat["shader"]
            if mat["backend"] == "OmniPBR":
                sh.GetInput("enable_opacity").Set(opacity < 0.999)
                sh.GetInput("opacity_constant").Set(float(opacity))
            else:
                sh.GetInput("opacity").Set(float(opacity))
                # UsdPreviewSurface 반투명은 렌더러에 알파 모드를 알려야 한다
                prim = self.stage.GetPrimAtPath(
                    (self.prim_map["parts"].get(key) or {}).get("mesh_path", ""))
                if prim and prim.IsValid():
                    from pxr import UsdGeom
                    UsdGeom.Gprim(prim).CreateDisplayOpacityPrimvar("constant").Set([float(opacity)])
            changed.append(key)
        return changed

    HOUSING_KEYS = ["housing_frame", "endshield_de", "endshield_nde", "fan_cover", "terminal_box"]

    def housing_transparent(self, on: bool = True, opacity: float = 0.22) -> list[str]:
        """하우징 계열을 한 번에 반투명/불투명 전환."""
        return self.set_opacity(self.HOUSING_KEYS, opacity if on else 1.0)

    # ------------------------------------------------------------- 갱신
    def update(self, temperatures: dict[str, float], stages: dict[str, str],
               time_s: float, thresholds: dict[str, dict] | None = None,
               force: bool = False) -> bool:
        """열 노드 온도로 머티리얼을 갱신한다 (스로틀링). 갱신했으면 True.

        temperatures/stages 의 키는 열 노드 키(prim_map parts 키와 동일한 것만 반영된다).
        thresholds: 부품별 {normal, caution, warning} — 색을 부품 허용 온도 기준으로 정규화한다.
        """
        if not force and (time_s - self._last_update) < self.update_interval:
            return False
        self._last_update = time_s
        thresholds = thresholds or {}
        for key, mat in self.materials.items():
            if key not in temperatures:
                continue
            s = self.cmap.sample(temperatures[key], part_key=key,
                                 stage=stages.get(key, "normal"), time_s=time_s,
                                 thresholds=thresholds.get(key))
            self._apply(mat, s)
        return True

    def _apply(self, mat: dict, s: dict) -> None:
        shader = mat["shader"]
        if mat["backend"] == "OmniPBR":
            shader.GetInput("diffuse_color_constant").Set(Gf.Vec3f(*s["diffuse"]))
            emit = s["intensity"] > 1e-3
            shader.GetInput("enable_emission").Set(bool(emit))
            shader.GetInput("emissive_color").Set(Gf.Vec3f(*s["emissive"]))
            shader.GetInput("emissive_intensity").Set(float(s["intensity"]))
        else:
            shader.GetInput("diffuseColor").Set(Gf.Vec3f(*s["diffuse"]))
            # UsdPreviewSurface 는 강도 입력이 없어 색에 강도를 곱해 표현한다
            k = min(s["intensity"] / 5.0, 2.0)
            shader.GetInput("emissiveColor").Set(Gf.Vec3f(*[c * k for c in s["emissive"]]))

    def reset_to_base(self) -> None:
        """모든 부품을 원래 재질(발광 0)로 되돌린다."""
        for key, mat in self.materials.items():
            base = self.cmap.base_material(key)
            self._apply(mat, {"diffuse": tuple(base["color"]), "emissive": (0, 0, 0), "intensity": 0.0})

    def save_override_layer(self, path: str) -> str:
        """생성한 머티리얼을 별도 레이어로 저장한다 (원본 USD 무수정 보장)."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        layer = Sdf.Layer.CreateNew(path) if not os.path.exists(path) else Sdf.Layer.FindOrOpen(path)
        self.stage.GetRootLayer().Export(path)
        return path
