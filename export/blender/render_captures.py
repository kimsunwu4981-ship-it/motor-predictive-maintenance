# render_captures.py — 모터 모델 캡처 이미지 일괄 렌더 (Blender 5.x, hoist_motor_only.blend 기준)
#   "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b hoist_motor_only.blend --python render_captures.py -- <out_dir> [samples]
# 기존 카메라·3점 조명·스튜디오 바닥은 그대로 쓰고, 카메라만 뷰별로 옮겨 모터(HM_*)가 화면을 채우게 한다. 충돌용 메시는 숨긴다.
import bpy, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(os.path.dirname(bpy.data.filepath), "captures")
SAMPLES = int(argv[1]) if len(argv) > 1 else 64
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene

# 렌더 설정: Cycles GPU(OptiX) + 디노이즈, 1920×1080
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1920, 1080, 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
# GPU: 모든 백엔드를 열거(get_devices)하면 oneAPI 로더(ze_loader.dll)에서 죽는다(실측) → OptiX 만 지정해서 켠다. 실패하면 CPU.
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    devs = prefs.get_devices_for_type("OPTIX")
    n = 0
    for d in devs:
        d.use = True; n += 1
    scene.cycles.device = "GPU" if n else "CPU"
    print("[capture] cycles OPTIX devices", [d.name for d in devs], "->", scene.cycles.device, flush=True)
except Exception as e:
    scene.cycles.device = "CPU"
    print("[capture] GPU setup failed, CPU:", e, flush=True)

# 컬렉션 단위로 렌더에서 꺼진 것(하우징 등)을 전부 켠다 — 객체 플래그는 켜져 있어도 컬렉션이 꺼져 있으면 안 그려진다(실측)
def _enable(lc):
    lc.exclude = False
    lc.collection.hide_render = False
    for c in lc.children:
        _enable(c)
_enable(bpy.context.view_layer.layer_collection)
for c in bpy.data.collections:
    print("[capture] collection", c.name, "hide_render", c.hide_render, "objs", len(c.objects))
# 빈 재질 슬롯은 검게 렌더된다(단자함 윗부분 실측) → 같은 객체의 첫 재질로 채운다
for o in bpy.data.objects:
    if o.type != "MESH" or not o.name.startswith("HM_"):
        continue
    mats = [sl.material for sl in o.material_slots]
    first = next((m for m in mats if m is not None), None)
    if first and any(m is None for m in mats):
        for sl in o.material_slots:
            if sl.material is None:
                sl.material = first
        print("[capture] filled empty material slots on", o.name, "->", first.name)
    if o.name == "HM_Terminal_Box":
        print("[capture] terminal box slots", [sl.material.name if sl.material else None for sl in o.material_slots], "polys", len(o.data.polygons), "mat idx", sorted({p.material_index for p in o.data.polygons}))
# 충돌 메시 숨김, 모터 부품 bbox
for o in bpy.data.objects:
    if o.name.startswith("collision_") or o.name in ("visual_frame", "visual_rotor"):   # Isaac 용 병합 복제 메시 — HM_* 와 겹쳐 단자함이 검게 나왔다(실측). HM_* 만 그린다
        o.hide_render = True; o.hide_viewport = True
parts = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("HM_")]
mn, mx = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for o in parts:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
center = (mn + mx) / 2
size = max(mx - mn)
print("[capture] motor bbox", tuple(round(v, 3) for v in mn), tuple(round(v, 3) for v in mx), "size", round(size, 3))
# 축 방향 판단: 가장 긴 축이 샤프트 축
ext = mx - mn
axis = max(range(3), key=lambda i: ext[i])
de_sign = 1.0   # DE 샤프트 쪽 부호 (샤프트 객체 중심이 bbox 중심보다 어느 쪽인지)
shaft = bpy.data.objects.get("HM_Shaft")
if shaft:
    sc = sum((shaft.matrix_world @ Vector(c) for c in shaft.bound_box), Vector()) / 8
    de_sign = 1.0 if sc[axis] >= center[axis] else -1.0

# 월드 밝기: 위쪽이 검은 월드를 광택 페인트(단자함 윗면)가 그대로 비춰 검게 나왔다(실측) → 균일한 밝은 회색 환경광
w = scene.world
if w and w.use_nodes:
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs[0].default_value = (0.55, 0.57, 0.60, 1.0)
        bg.inputs[1].default_value = 1.0
cam = scene.camera or bpy.data.objects.get("Camera")
cam.data.lens = 50
cam.data.clip_end = 1000


def look(direction: Vector, dist_mult=2.2, lens=50, target=None):
    """direction: 카메라가 놓일 방향(모터 중심 기준, 정규화 전). 모터가 화면을 채우도록 거리 자동."""
    cam.data.lens = lens
    d = direction.normalized()
    tgt = target if target is not None else center
    dist = size * dist_mult * (lens / 50)
    cam.location = tgt + d * dist
    rot = (-d).to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()


def axis_vec(i, s=1.0):
    v = Vector((0, 0, 0)); v[i] = s; return v


a = axis_vec(axis, de_sign)          # DE(샤프트) 방향
side = axis_vec((axis + 1) % 3)      # 측면 방향 (수평)
if side.z != 0:                      # 측면이 수직이면 다른 축
    side = axis_vec((axis + 2) % 3)
up = Vector((0, 0, 1))
views = {
    "01_iso_DE_front": (a * 1.0 + side * 1.1 + up * 0.75, 2.0, 50),
    "02_iso_NDE_fan": (-a * 1.0 - side * 1.1 + up * 0.75, 2.0, 50),
    "03_side": (side * 1.0 + up * 0.18, 2.1, 60),
    "04_front_DE": (a * 1.0 + up * 0.12, 1.9, 60),
    "05_rear_NDE": (-a * 1.0 + up * 0.12, 1.9, 60),
    "06_top": (up * 1.0 + a * 0.05, 2.0, 50),
    "07_iso_low": (a * 0.9 - side * 1.0 + up * 0.35, 1.9, 45),
}
for name, (d, mult, lens) in views.items():
    look(d, mult, lens)
    scene.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("[capture] saved", scene.render.filepath, flush=True)

# 클로즈업: 단자함·DE 베어링 쪽
tb = bpy.data.objects.get("HM_Terminal_Box")
if tb:
    tc = sum((tb.matrix_world @ Vector(c) for c in tb.bound_box), Vector()) / 8
    look(a * 0.8 + side * 1.0 + up * 0.9, 0.9, 70, target=(tc + center) / 2)
    scene.render.filepath = os.path.join(OUT, "08_close_terminal_box.png")
    bpy.ops.render.render(write_still=True)
    print("[capture] saved", scene.render.filepath, flush=True)
print("[capture] DONE")
