# -*- coding: utf-8 -*-
"""build_parts_usd.py — 파트별 OBJ 12개 → 부품 단위 독립 prim USD 생성 (Blender headless).

Phase 0 에서 확인된 제약(현 USD 는 병합 메시 2개뿐 → 부품별 색상 불가)을 해소한다.
원본 USD/f3d 는 읽지도 쓰지도 않는다. 입력은 export/mesh/HM_*.obj 뿐이다 (Hard Rule 2).

실행:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background \
      --python motor_dt_viz/tools/build_parts_usd.py

출력: motor_dt_viz/assets/motor_parts.usd
계층:
  /World/Motor              (Xform, 나중에 ArticulationRoot)
    /Static/<부품>          (고정부 8개)
    /Rotating/<부품>        (회전부 3개)
"""
import os
import re
import sys

import bpy

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MESH_DIR = os.path.join(PROJECT, "export", "mesh")
OUT_USD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "motor_parts.usd"))

# prim_map.yaml 의 group 과 일치해야 한다 (Phase 0 확정)
ROTATING = {"HM_Shaft", "HM_Rotor_Core", "HM_Fan"}
EXCLUDE = {"HM_Mount_Interface"}          # 모터 부품이 아닌 마운팅 참조 지오메트리
OBJ_SCALE = 0.01                          # Fusion OBJ 단위 cm → m


def log(*a):
    print("[build_parts]", *a, flush=True)


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def import_part(path: str) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z", global_scale=OBJ_SCALE)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not new:
        raise RuntimeError(f"임포트 실패: {path}")
    if len(new) > 1:                      # 한 파일에 여러 오브젝트면 합친다
        bpy.ops.object.select_all(action="DESELECT")
        for o in new:
            o.select_set(True)
        bpy.context.view_layer.objects.active = new[0]
        bpy.ops.object.join()
        new = [bpy.context.view_layer.objects.active]
    return new[0]


def main():
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"

    col = bpy.data.collections.new("Export")
    scene.collection.children.link(col)

    root = bpy.data.objects.new("Motor", None)
    static_root = bpy.data.objects.new("Static", None)
    rot_root = bpy.data.objects.new("Rotating", None)
    for o in (root, static_root, rot_root):
        col.objects.link(o)
    static_root.parent = root
    rot_root.parent = root

    files = sorted(f for f in os.listdir(MESH_DIR) if f.lower().endswith(".obj"))
    made = {"Static": [], "Rotating": []}
    for fn in files:
        name = os.path.splitext(fn)[0]
        if name in EXCLUDE:
            log(f"제외: {name} (마운팅 참조 지오메트리)")
            continue
        obj = import_part(os.path.join(MESH_DIR, fn))
        obj.name = name
        obj.data.name = name + "_mesh"
        obj.data.materials.clear()        # 머티리얼은 Isaac 에서 prim 전용으로 새로 만든다
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)
        group = "Rotating" if name in ROTATING else "Static"
        obj.parent = rot_root if group == "Rotating" else static_root
        made[group].append(name)
        d = obj.dimensions
        log(f"{group:8s} {name:22s} dims=({d.x:.3f},{d.y:.3f},{d.z:.3f}) m  verts={len(obj.data.vertices)}")

    os.makedirs(os.path.dirname(OUT_USD), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in col.all_objects:
        o.select_set(True)

    kw = dict(filepath=OUT_USD, selected_objects_only=True, export_materials=False,
              export_uvmaps=False, export_normals=True, root_prim_path="/World",
              convert_orientation=False, export_lights=False, export_cameras=False)
    for _ in range(8):                    # Blender 버전별 미지원 인자 자동 제거
        try:
            bpy.ops.wm.usd_export(**kw)
            break
        except TypeError as e:
            m = re.search(r'keyword "(\w+)" unrecognized', str(e))
            if m and m.group(1) in kw:
                kw.pop(m.group(1))
            else:
                raise

    log(f"저장: {OUT_USD} ({os.path.getsize(OUT_USD)} bytes)")
    log(f"고정부 {len(made['Static'])}개: {', '.join(made['Static'])}")
    log(f"회전부 {len(made['Rotating'])}개: {', '.join(made['Rotating'])}")
    log("BUILD_OK")


if __name__ == "__main__":
    main()
