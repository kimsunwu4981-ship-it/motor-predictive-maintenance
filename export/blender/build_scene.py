# build_scene.py — Hoist motor render scene builder (Blender 5.x)
# 실행: blender --python build_scene.py  (GUI)  /  blender -b --python build_scene.py (headless)
import bpy, os, glob, math, mathutils

PROJ = r"c:\Users\sunwu\OneDrive\바탕 화면\프로젝트\디지털 트윈\크레인 퀀선 모터 모델링"
MESH = os.path.join(PROJ, "export", "mesh")
BLEND = os.path.join(PROJ, "export", "blender", "hoist_motor_render.blend")


def build():
    scene = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.length_unit = 'METERS'

    # ---------- 임포트 (Fusion OBJ = cm, +Z up) ----------
    col = bpy.data.collections.new("HoistMotor"); scene.collection.children.link(col)
    objs = {}
    for f in sorted(glob.glob(os.path.join(MESH, "*.obj"))):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=f, forward_axis='Y', up_axis='Z', global_scale=0.01)
        new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
        name = os.path.splitext(os.path.basename(f))[0]
        bpy.ops.object.select_all(action='DESELECT')
        for o in new: o.select_set(True)
        bpy.context.view_layer.objects.active = new[0]
        if len(new) > 1: bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active; o.name = name
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        o.data.materials.clear()
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
        for c in list(o.users_collection): c.objects.unlink(o)
        col.objects.link(o); objs[name] = o
    print("frame dims:", tuple(round(v, 3) for v in objs["HM_Frame"].dimensions))

    # ---------- 재질 ----------
    def mat(name, base, rough=0.5, metal=0.0, coat=0.0, bump=0.0, bump_scale=300, grime=0.0):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
        for n in list(nt.nodes): nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Base Color"].default_value = (*base, 1); b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        if "Coat Weight" in b.inputs: b.inputs["Coat Weight"].default_value = coat
        nt.links.new(b.outputs[0], out.inputs[0])
        if grime > 0:  # 얼룩: 노이즈로 색·러프니스 변조
            nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6; nz.inputs["Detail"].default_value = 8
            ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
            mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = grime
            mix.inputs[6].default_value = (*base, 1); mix.inputs[7].default_value = (0.45, 0.38, 0.28, 1)
            nt.links.new(nz.outputs["Fac"], ramp.inputs[0]); nt.links.new(ramp.outputs[0], mix.inputs[0])
            nt.links.new(mix.outputs[2], b.inputs["Base Color"])
        if bump > 0:
            tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = bump_scale; tex.inputs["Detail"].default_value = 6
            bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
            nt.links.new(tex.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
        return m

    paint = mat("MotorPaint_GrayBlue", (0.36, 0.44, 0.47), rough=0.5, coat=0.2, bump=0.06, grime=0.35)
    paint_dirty = mat("MotorPaint_Dirty", (0.33, 0.40, 0.42), rough=0.65, bump=0.12, grime=0.5)
    steel_dark = mat("Steel_Dark", (0.10, 0.09, 0.08), rough=0.4, metal=0.9, bump=0.1)
    steel_bright = mat("Steel_Machined", (0.55, 0.55, 0.55), rough=0.3, metal=1.0)
    alu = mat("Aluminium_Cast", (0.6, 0.6, 0.6), rough=0.5, metal=0.9)
    yellow = mat("Crane_Yellow", (0.85, 0.60, 0.05), rough=0.55, bump=0.08, grime=0.45)
    plate = mat("CheckerPlate_Rusty", (0.50, 0.36, 0.17), rough=0.85, bump=0.5, bump_scale=120, grime=0.6)
    green = mat("Floor_Green", (0.04, 0.42, 0.28), rough=0.5)
    black_rubber = mat("Rope_Black", (0.02, 0.02, 0.02), rough=0.35, metal=0.6, bump=0.8, bump_scale=60)
    assign = {"HM_Frame": paint, "HM_Endshield_DE": paint, "HM_Endshield_NDE": paint, "HM_Fan_Cover": paint_dirty,
              "HM_Terminal_Box": paint, "HM_Shaft": steel_dark, "HM_Rotor_Core": steel_dark,
              "HM_Bearing_DE": steel_bright, "HM_Bearing_NDE": steel_bright, "HM_Fan": alu,
              "HM_Eyebolt": steel_dark, "HM_Mount_Interface": yellow}
    for n, m in assign.items(): objs[n].data.materials.append(m)

    # 명판(사진의 흰 라벨) — 프레임 측면에 얇은 판
    label = mat("Nameplate", (0.85, 0.85, 0.82), rough=0.4, metal=0.3)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0.33, -0.201, 0.02), rotation=(math.radians(90), 0, 0))
    np_ = bpy.context.active_object; np_.name = "Nameplate"; np_.scale = (0.11, 0.07, 1); np_.data.materials.append(label)
    for c in list(np_.users_collection): c.objects.unlink(np_)
    col.objects.link(np_)

    # ---------- 환경 ----------
    env = bpy.data.collections.new("Environment"); scene.collection.children.link(env)

    def link(o):
        for c in list(o.users_collection): c.objects.unlink(o)
        env.objects.link(o); return o

    def box(name, size, loc, m, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        o = bpy.context.active_object; o.name = name; o.scale = size; o.data.materials.append(m); return link(o)

    def pipe(name, p0, p1, r=0.02, m=yellow):
        v = mathutils.Vector(p1) - mathutils.Vector(p0)
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=v.length, location=(mathutils.Vector(p0) + v / 2))
        o = bpy.context.active_object; o.name = name; o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
        o.data.materials.append(m); return link(o)

    def cyl(name, r, depth, loc, m, rot=(0, math.radians(90), 0)):
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot)
        o = bpy.context.active_object; o.name = name; o.data.materials.append(m); return link(o)

    box("Trolley_Plate", (2.8, 2.2, 0.03), (0.45, -0.2, -0.235), plate)
    box("Motor_Pedestal", (0.5, 0.5, 0.15), (0.425, 0.0, -0.31), yellow)
    box("Girder_Beam", (3.0, 0.35, 0.55), (0.45, 0.95, 0.02), yellow)
    box("Girder_Beam2", (0.35, 2.2, 0.55), (-1.1, 0.0, 0.02), yellow)
    box("Trolley_Frame_Side", (3.0, 0.12, 0.3), (0.45, -1.25, -0.1), yellow)
    for i, x in enumerate((-0.6, 0.2, 1.0, 1.8)): pipe(f"Rail_Post{i}", (x, -1.3, -0.25), (x, -1.3, 0.85))
    pipe("Rail_Top", (-0.6, -1.3, 0.85), (1.8, -1.3, 0.85)); pipe("Rail_Mid", (-0.6, -1.3, 0.3), (1.8, -1.3, 0.3))
    box("Floor_Green", (30, 30, 0.05), (0.45, 0, -6.0), green)
    box("Wall_Back", (30, 0.1, 12), (0.45, 6.0, 0.0), mat("Wall", (0.6, 0.62, 0.6), rough=0.9))
    # 와이어 드럼 + 로프(전경)
    cyl("Wire_Drum", 0.23, 0.9, (0.35, -0.95, -0.62), black_rubber)
    cyl("Drum_Flange_L", 0.30, 0.03, (-0.12, -0.95, -0.62), steel_dark); cyl("Drum_Flange_R", 0.30, 0.03, (0.82, -0.95, -0.62), steel_dark)
    # DE측: 커플링 허브 + 브레이크 드럼(사진의 검은 원통·디스크)
    cyl("Coupling_Hub", 0.075, 0.10, (-0.06, 0, 0), steel_dark)
    cyl("Brake_Drum", 0.11, 0.05, (-0.16, 0, 0), steel_dark)
    cyl("Brake_Shaft", 0.03, 0.35, (-0.36, 0, 0), steel_dark)
    box("Brake_Stand", (0.16, 0.30, 0.20), (-0.19, 0, -0.30), paint)
    # 리밋스위치 박스(NDE측, 사진)
    box("Limit_Switch", (0.15, 0.12, 0.10), (1.10, 0.05, -0.05), paint)

    # ---------- 조명 ----------
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); scene.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background"); bg.inputs[0].default_value = (0.55, 0.62, 0.6, 1); bg.inputs[1].default_value = 0.3

    def area(name, loc, size, energy, target=(0.45, 0, 0)):
        bpy.ops.object.light_add(type='AREA', location=loc); L = bpy.context.active_object; L.name = name
        L.data.energy = energy; L.data.size = size; L.data.color = (1.0, 0.98, 0.95)
        L.rotation_euler = (mathutils.Vector(target) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return link(L)

    area("Key_Ceiling", (0.2, -1.2, 3.0), 2.5, 300)
    area("Fill_Side", (2.0, -2.0, 1.0), 2.0, 70)
    area("Rim_Back", (0.5, 2.0, 1.5), 1.5, 90)

    # ---------- 카메라 (사진2 구도: 3/4 위, 전면 -Y·DE측에서) ----------
    cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Camera", cam_data); link(cam)
    cam.location = (-0.35, -1.05, 0.78)
    cam.rotation_euler = (mathutils.Vector((0.42, 0.0, 0.02)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = 35; cam_data.sensor_width = 36; scene.camera = cam

    # ---------- 렌더 설정 ----------
    scene.render.resolution_x = 1600; scene.render.resolution_y = 1200; scene.render.resolution_percentage = 100
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 64; scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.view_settings.view_transform = 'AgX'
    try: scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.join(PROJ, "export", "render", "hoist_motor_render.png")
    os.makedirs(os.path.dirname(scene.render.filepath), exist_ok=True)
    os.makedirs(os.path.dirname(BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("SCENE BUILT & SAVED:", BLEND)


if bpy.app.background:
    build()
else:
    def _later():
        try:
            build()
        except Exception as e:
            import traceback; traceback.print_exc()
        return None
    bpy.app.timers.register(_later, first_interval=2.5)
