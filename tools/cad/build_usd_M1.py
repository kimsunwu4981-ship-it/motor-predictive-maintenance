# -*- coding: utf-8 -*-
"""build_usd_M1.py — M1 OBJ(내부·하우징·cutaway) → USD 반입(omni.kit.asset_converter) → 조립 M1.usd (계층·재질·variantSet view).

Isaac Sim 4.5 파이썬으로 실행 (경로에 공백·한글이 있으니 .bat 에는 상대 경로만):
  cd <저장소 루트> ; C:\\ISSACS~1\\python.bat tools\\cad\\build_usd_M1.py

출력(assets/motors/M1/):
  M1_internals.usd, M1_internals_cutaway.usd, M1_housing.usd, M1_housing_cutaway.usd   (변환기 출력, 메시 prim 이름 = OBJ 그룹 = 부품 이름)
  M1.usd — /M1 (Xform, mm→m 스케일 0.001)
    /M1/Housing/{Frame, EndShield_DE, EndShield_NDE, Foot, TerminalBox, FanCover, Eyebolt}
    /M1/Stator/Core, /M1/Stator/Coils/Coil_01…Coil_36, /M1/Stator/Coils/Coil_01_short
    /M1/Rotor (회전 대상 Xform: xformOp:rotateX) /Core, /Bars/Bar_01…28, /EndRing_DE, /EndRing_NDE, /Shaft
    /M1/Bearings/{DE, NDE}
    /M1/Looks/{copper, aluminum, silicon_steel, cast_iron, steel, phase_A/B/C, coil_short}
  variantSet "view": full | cutaway(하우징·고정자 1/4 절단 메시로 교체) | windings_only(코어 숨김)
배치: 적층 중심 = 프레임 길이 중심(x 0), 축 중심 z 100 mm (하우징 좌표: 발 바닥 z 0). 새 계산 없음.
"""
import asyncio
import json
import os
import sys

from isaacsim import SimulationApp

app = SimulationApp({"headless": True})
import omni.kit.app  # noqa: E402
import omni.kit.asset_converter as conv  # noqa: E402
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Kind  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSET = os.path.join(ROOT, "assets", "motors", "M1")
mgr = omni.kit.app.get_app().get_extension_manager(); mgr.set_extension_enabled_immediate("omni.kit.asset_converter", True)

MAT_COLOR = {"copper": (0.72, 0.45, 0.20), "aluminum": (0.80, 0.81, 0.83), "silicon_steel": (0.30, 0.31, 0.34), "cast_iron": (0.36, 0.40, 0.44), "steel": (0.58, 0.59, 0.61),
             "phase_A": (0.85, 0.25, 0.20), "phase_B": (0.95, 0.75, 0.15), "phase_C": (0.20, 0.45, 0.90), "coil_short": (1.00, 0.10, 0.05)}
MAT_ROUGH = {"copper": 0.35, "aluminum": 0.4, "silicon_steel": 0.6, "cast_iron": 0.7, "steel": 0.35, "phase_A": 0.4, "phase_B": 0.4, "phase_C": 0.4, "coil_short": 0.4}


def log(*a):
    print("[usd]", *a, flush=True)


async def convert(src, dst):
    ctx = conv.AssetConverterContext(); ctx.ignore_materials = True; ctx.merge_all_meshes = False; ctx.use_meter_as_world_unit = False
    task = conv.get_instance().create_converter_task(src, dst, None, ctx)
    ok = await task.wait_until_finished()
    return ok, str(task.get_status()), task.get_error_message()


def mesh_map(usd_path):
    """변환된 USD 의 메시 prim 경로를 이름으로 색인 (OBJ 'o' 그룹 이름)."""
    st = Usd.Stage.Open(usd_path); out = {}
    for p in st.Traverse():
        if p.IsA(UsdGeom.Mesh):
            name = p.GetName()
            out.setdefault(name, str(p.GetPath()))
    return st.GetDefaultPrim().GetPath().pathString if st.GetDefaultPrim() else None, out


def main():
    man_i = json.load(open(os.path.join(ASSET, "internals_parts.json"), encoding="utf-8"))
    man_h = json.load(open(os.path.join(ASSET, "housing_parts.json"), encoding="utf-8"))
    ds = __import__("yaml").safe_load(open(os.path.join(ASSET, "inputs", "datasheet_v4.yaml"), encoding="utf-8"))
    H_mm = float(man_h["axis_height_H_mm"])
    phase_of = {w["coil"]: w["phase"] for w in ds["winding_table"]}
    files = {"int_full": ("internals.obj", "M1_internals.usd"), "int_cut": ("internals_cutaway.obj", "M1_internals_cutaway.usd"),
             "hou_full": ("housing.obj", "M1_housing.usd"), "hou_cut": ("housing_cutaway.obj", "M1_housing_cutaway.usd")}
    maps = {}
    loop = asyncio.get_event_loop()
    for key, (src, dst) in files.items():
        r = loop.run_until_complete(convert(os.path.join(ASSET, src), os.path.join(ASSET, dst)))
        root, mm = mesh_map(os.path.join(ASSET, dst))
        maps[key] = (dst, root, mm)
        log(f"{src} → {dst}: {r[1]} 메시 {len(mm)} (root {root})")
        if not mm:
            raise SystemExit(f"변환 실패: {src} {r}")

    # ---------------- 조립 스테이지
    out = os.path.join(ASSET, "M1.usd")
    stage = Usd.Stage.CreateNew(out)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z); UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/M1"); stage.SetDefaultPrim(root.GetPrim())
    Usd.ModelAPI(root.GetPrim()).SetKind(Kind.Tokens.component)
    root.AddScaleOp().Set(Gf.Vec3d(0.001, 0.001, 0.001))                       # mm → m
    root.GetPrim().SetCustomDataByKey("units_source", "mm (tools/cad/build_internals_M1.py, build_housing_100L.py)")
    looks = UsdGeom.Scope.Define(stage, "/M1/Looks")
    mats = {}
    for name, col in MAT_COLOR.items():
        m = UsdShade.Material.Define(stage, f"/M1/Looks/{name}")
        sh = UsdShade.Shader.Define(stage, f"/M1/Looks/{name}/Shader"); sh.CreateIdAttr("UsdPreviewSurface")
        sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*col))
        sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(MAT_ROUGH[name])
        sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.9 if name in ("copper", "aluminum", "steel") else 0.3)
        sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0, 0, 0))
        m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
        mats[name] = m

    def place(prim_path, key, part_name, material, z_offset_mm=0.0):
        """Xform prim + 변환 USD 의 메시를 참조(variant 밖 = full)."""
        # 타입 없는 def — 참조된 Mesh 의 typeName 이 그대로 와야 렌더된다 (Xform.Define 으로 만들면 로컬 typeName 이 이겨 메시가 안 보인다, 실측)
        prim = stage.DefinePrim(prim_path)
        dst, _, mm = maps[key]
        prim.GetReferences().AddReference(f"./{dst}", mm[part_name])
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(mats[material])
        prim.SetCustomDataByKey("material", material)
        return prim

    def ref_variant(prim, key, part_name):
        dst, _, mm = maps[key]
        if part_name not in mm:                      # 절단으로 형상이 전부 사라진 부품(예: 절단 사분면 안의 아이볼트) → 이 variant 에서는 숨김
            UsdGeom.Imageable(prim).MakeInvisible(); return
        prim.GetReferences().ClearReferences()
        prim.GetReferences().AddReference(f"./{dst}", mm[part_name])

    # 하우징 (좌표 그대로: 발 바닥 z 0, 축 z H)
    hou_parts = list(man_h["parts"].keys())
    hou_prims = {n: place(f"/M1/Housing/{n}", "hou_full", n, man_h["parts"][n]["material"]) for n in hou_parts}
    # 고정자·로터·베어링 (내부 좌표 축 z 0 → z H)
    UsdGeom.Xform.Define(stage, "/M1/Stator").AddTranslateOp().Set(Gf.Vec3d(0, 0, H_mm))
    rotor = UsdGeom.Xform.Define(stage, "/M1/Rotor"); rotor.AddTranslateOp().Set(Gf.Vec3d(0, 0, H_mm)); rotor.AddRotateXOp().Set(0.0)   # 회전 대상
    UsdGeom.Xform.Define(stage, "/M1/Bearings").AddTranslateOp().Set(Gf.Vec3d(0, 0, H_mm))
    stator_prims = {"Stator_Core": place("/M1/Stator/Core", "int_full", "Stator_Core", "silicon_steel")}
    for n, p in man_i["parts"].items():
        if n.startswith("Coil_"):
            if n == "Coil_01_short":
                stator_prims[n] = place("/M1/Stator/Coils/Coil_01_short", "int_full", n, "coil_short")
            else:
                k = int(n.split("_")[1]); ph = phase_of.get(k, "A")
                stator_prims[n] = place(f"/M1/Stator/Coils/{n}", "int_full", n, f"phase_{ph}")
    place("/M1/Rotor/Core", "int_full", "Rotor_Core", "silicon_steel")
    for n in man_i["parts"]:
        if n.startswith("Bar_"):
            place(f"/M1/Rotor/Bars/{n}", "int_full", n, "aluminum")
    place("/M1/Rotor/EndRing_DE", "int_full", "EndRing_DE", "aluminum"); place("/M1/Rotor/EndRing_NDE", "int_full", "EndRing_NDE", "aluminum")
    place("/M1/Rotor/Shaft", "int_full", "Shaft", "steel")
    place("/M1/Bearings/DE", "int_full", "Bearing_DE", "steel"); place("/M1/Bearings/NDE", "int_full", "Bearing_NDE", "steel")

    # ---------------- variantSet view
    vs = root.GetPrim().GetVariantSets().AddVariantSet("view")
    for v in ("full", "cutaway", "windings_only"):
        vs.AddVariant(v)
    vs.SetVariantSelection("cutaway")
    with vs.GetVariantEditContext():
        for n, pr in hou_prims.items():
            ref_variant(pr, "hou_cut", n)
        for n, pr in stator_prims.items():
            ref_variant(pr, "int_cut", n)
    vs.SetVariantSelection("windings_only")
    with vs.GetVariantEditContext():
        UsdGeom.Imageable(stator_prims["Stator_Core"]).MakeInvisible()
        for n in ("Frame", "EndShield_DE", "EndShield_DE_B35", "EndShield_NDE", "FanCover", "TerminalBox", "Eyebolt"):
            if n in hou_prims:
                UsdGeom.Imageable(hou_prims[n]).MakeInvisible()
        UsdGeom.Imageable(stage.GetPrimAtPath("/M1/Rotor/Core")).MakeInvisible()
    vs.SetVariantSelection("full")
    root.GetPrim().SetCustomDataByKey("view_variants", "full | cutaway | windings_only")
    # mount: B3(기본, 플랜지 없음) / B35(FF215 플랜지)
    if "EndShield_DE_B35" in hou_prims:
        vm = root.GetPrim().GetVariantSets().AddVariantSet("mount")
        for v in ("B3", "B35"):
            vm.AddVariant(v)
        vm.SetVariantSelection("B3")
        with vm.GetVariantEditContext():
            UsdGeom.Imageable(hou_prims["EndShield_DE_B35"]).MakeInvisible()
        vm.SetVariantSelection("B35")
        with vm.GetVariantEditContext():
            UsdGeom.Imageable(hou_prims["EndShield_DE"]).MakeInvisible()
        vm.SetVariantSelection("B3")
        root.GetPrim().SetCustomDataByKey("mount_variants", "B3 (기본) | B35")
    root.GetPrim().SetCustomDataByKey("rotor_xform", "/M1/Rotor xformOp:rotateX [deg] — 런타임이 rpm 을 적분해 설정")
    stage.GetRootLayer().Save()
    n_prims = sum(1 for _ in stage.Traverse())
    log(f"M1.usd prims {n_prims} · 하우징 {len(hou_prims)} · 고정자 {len(stator_prims)} · 로터 {1 + sum(1 for n in man_i['parts'] if n.startswith('Bar_')) + 3}")
    json.dump({"files": {k: v[0] for k, v in maps.items()}, "mesh_counts": {k: len(v[2]) for k, v in maps.items()}, "prims": n_prims, "H_mm": H_mm},
              open(os.path.join(ASSET, "usd_build.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


try:
    main()
finally:
    app.close()
