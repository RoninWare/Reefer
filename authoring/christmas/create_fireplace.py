"""Build the brick fireplace, render its sprite and bake the looping flames.

    blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_fireplace.py

Writes fireplace.blend (editable), fireplace.png, fire_frames.png and fireplace.json, which
records where the chimney mouth and the flame sheet sit in the sprite, and where each of its
lights is: the coloured bulbs strung along the mantel's garland and the small white and yellow
ones in the wreath, as [x, y, colour, group, size] for the app to lay a twinkling glow over.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig
from rig import Blocks, Graph, TAU

OUT = rig.HERE / "fireplace.blend"
rig.guard(OUT)
scene = rig.reset(samples=192)
rng = random.Random(1225)
built = []          # everything that turns with the fireplace
TURN = -24.0        # degrees: the hearth faces the moray's cave to its left

# ---- measurements (1 unit = 100 tank pixels) ------------------------------------------
M = 0.012                      # mortar joint
BL, BD = 0.24, 0.115           # brick length and depth
HEARTH = 0.13
BODY_W, BODY_D, BODY_H = 2.40, 0.78, 1.52
COURSE = BODY_H / 17
FRONT = -BODY_D / 2
OPEN_W, SPRING, RING = 1.20, HEARTH + 0.52, 0.20
MANTEL_Z, MANTEL_H = HEARTH + BODY_H, 0.18
BREAST_Z = MANTEL_Z + MANTEL_H
BREAST_W, STACK_W, STACK_D, STEPS = 2.20, 0.95, 0.72, 9
STACK_Z = BREAST_Z + STEPS * COURSE
STACK_COURSES = 15
CAP_Z = STACK_Z + STACK_COURSES * COURSE


def keep(obj):
    built.append(obj)
    return obj


# ---- materials -------------------------------------------------------------------------
def brick_material():
    mat = rig.material("Fired brick", (0.45, 0.15, 0.09), 0.86)
    g = Graph(mat)
    tone = g.attribute("tone").outputs["Fac"]
    soot = g.attribute("soot").outputs["Fac"]
    moss = g.attribute("moss").outputs["Fac"]
    base = g.ramp(tone, [(0.0, (0.19, 0.058, 0.044)), (0.35, (0.36, 0.105, 0.068)), (0.72, (0.47, 0.155, 0.095)),
                         (0.93, (0.54, 0.23, 0.14)), (1.0, (0.52, 0.34, 0.23))]).outputs["Color"]
    grain = g.noise(g.coords(), scale=42, detail=5, roughness=0.7).outputs["Fac"]
    blotch = g.noise(g.coords(), scale=7, detail=2).outputs["Fac"]
    color = g.mix(g.math("MULTIPLY", grain, 0.55), base, (0.16, 0.06, 0.05), "MULTIPLY")
    color = g.mix(g.math("MULTIPLY", soot, 0.85, clamp=True), color, (0.022, 0.020, 0.019))
    # Tank life creeps up from the sand: a thin grey-green film on the lowest courses.
    film = g.math("MULTIPLY", moss, g.math("SMOOTHSTEP", 0.42, 0.62, blotch), clamp=True)
    color = g.mix(g.math("MULTIPLY", film, 0.55), color, (0.20, 0.30, 0.20))
    g.to("Base Color", color)
    g.bump(grain, strength=0.55, distance=0.012)
    return mat


def stone_material(name, color=(0.60, 0.58, 0.52), scale=30):
    mat = rig.material(name, color, 0.9)
    g = Graph(mat)
    grain = g.noise(g.coords(), scale=scale, detail=6, roughness=0.65).outputs["Fac"]
    blotch = g.noise(g.coords(), scale=4, detail=3).outputs["Fac"]
    dark = tuple(c * 0.55 for c in color)
    g.to("Base Color", g.mix(g.math("MULTIPLY", blotch, grain), dark, color))
    g.bump(grain, strength=0.4, distance=0.01)
    return mat


def timber_material():
    mat = rig.material("Oak beam", (0.24, 0.12, 0.05), 0.62)
    g = Graph(mat)
    mapping = g.node("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.4, 22, 22)
    g.set(mapping.inputs["Vector"], g.coords())
    rings = g.noise(mapping.outputs[0], scale=3.0, detail=4, roughness=0.6, distortion=0.6).outputs["Fac"]
    g.to("Base Color", g.ramp(rings, [(0.25, (0.085, 0.040, 0.018)), (0.55, (0.24, 0.115, 0.048)),
                                      (0.8, (0.36, 0.20, 0.09))]).outputs["Color"])
    g.bump(rings, strength=0.6, distance=0.012)
    return mat


def bark_material():
    mat = rig.material("Charred log", (0.12, 0.07, 0.04), 0.9)
    g = Graph(mat)
    grain = g.noise(g.coords(), scale=26, detail=5, roughness=0.7).outputs["Fac"]
    cracks = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    cracks.inputs["Scale"].default_value = 22
    glow = g.math("SUBTRACT", 1.0, g.math("SMOOTHSTEP", 0.0, 0.012, cracks.outputs["Distance"]))
    low = g.node("ShaderNodeSeparateXYZ")
    g.set(low.inputs[0], g.node("ShaderNodeNewGeometry").outputs["Normal"])
    under = g.math("SMOOTHSTEP", 0.35, -0.5, low.outputs["Z"])
    g.to("Base Color", g.ramp(grain, [(0.3, (0.018, 0.014, 0.012)), (0.75, (0.105, 0.062, 0.038))]).outputs["Color"])
    g.to("Emission Color", (1.0, 0.33, 0.04))
    g.to("Emission Strength", g.math("MULTIPLY", g.math("MULTIPLY", glow, under), 9.0))
    g.bump(grain, strength=0.45, distance=0.012)
    return mat


def felt(name, color):
    return rig.material(name, color, 0.95, Sheen_Weight=0.7, Sheen_Roughness=0.6)


BRICK, MORTAR = brick_material(), stone_material("Mortar", (0.60, 0.585, 0.54), 60)
LIME, SOOT = stone_material("Limestone"), stone_material("Sooted firebrick", (0.020, 0.017, 0.016), 50)
TIMBER, BARK = timber_material(), bark_material()
IRON = rig.material("Wrought iron", (0.02, 0.02, 0.023), 0.42, Metallic=1.0)
TERRACOTTA = stone_material("Terracotta pot", (0.60, 0.25, 0.13), 45)
NEEDLES = rig.needle_material()
RED, GREEN, WHITE = felt("Red felt", (0.55, 0.012, 0.022)), felt("Green felt", (0.02, 0.26, 0.09)), felt("Fleece", (0.9, 0.9, 0.87))
SATIN = rig.material("Red satin", (0.62, 0.01, 0.02), 0.32, Coat_Weight=0.4)
GOLD = rig.material("Gold bauble", (1.0, 0.62, 0.16), 0.22, Metallic=1.0)
RUBY = rig.material("Red bauble", (0.6, 0.01, 0.02), 0.12, Metallic=0.6, Coat_Weight=1.0)


# ---- masonry ---------------------------------------------------------------------------
bricks = Blocks("tone", "soot", "moss")
stone = Blocks("tone")


def clip_opening(xa, xb, zc):
    """Pieces of a front-wall brick left standing beside the firebox opening and its arch."""
    if zc < SPRING:
        half = OPEN_W / 2
    else:
        reach = OPEN_W / 2 + RING + M
        if zc - SPRING >= reach:
            return [(xa, xb)]
        half = math.sqrt(reach ** 2 - (zc - SPRING) ** 2)
    parts = []
    if xa < -half:
        parts.append((xa, min(xb, -half)))
    if xb > half:
        parts.append((max(xa, half), xb))
    return [(a, b) for a, b in parts if b - a > 0.035]


def lay(course_z, w, d, k, clip=None, soot_at=None, height=COURSE):
    """One course round a w x d footprint, bonded at the corners (the back wall is never seen)."""
    zc = course_z + height / 2
    even = k % 2 == 0
    moss = max(0.0, 1 - course_z / 0.75)
    rows = [("x", w if even else w - 2 * BD, -(d / 2 - BD / 2))]
    rows += [("y", d - 2 * BD if even else d, s * (w / 2 - BD / 2)) for s in (-1, 1)]
    for axis, span, fixed in rows:
        count = max(1, round(span / (BL + M)))
        unit = span / count
        for i in range(count):
            a, b = -span / 2 + i * unit + M / 2, -span / 2 + (i + 1) * unit - M / 2
            for a2, b2 in (clip(a, b, zc) if clip and axis == "x" else [(a, b)]):
                mid, length = (a2 + b2) / 2, b2 - a2
                proud = rng.uniform(-0.004, 0.006)
                if axis == "x":
                    center, size = (mid, fixed - proud, zc), (length, BD, height - M)
                else:
                    center, size = (fixed + math.copysign(proud, fixed), mid, zc), (BD, length, height - M)
                soot = soot_at(center) if soot_at else 0.0
                bricks.box(center, size, Matrix.Rotation(math.radians(rng.uniform(-0.5, 0.5)), 3, "Z"),
                           tone=rng.random(), soot=soot + rng.uniform(0, 0.12), moss=moss)


def core(name, w, d, z, h, inset=M):
    obj = rig.add_mesh(scene, name, rig.box_verts((0, 0, z + h / 2), (w - 2 * inset, d - 2 * inset, h)),
                       rig.BOX_FACES, [MORTAR])
    return keep(obj)


def body_soot(center):
    """Smoke stains the bricks just above the arch."""
    x, _, z = center
    rise = z - (SPRING + OPEN_W / 2)
    if rise < 0 or abs(x) > 0.75:
        return 0.0
    return max(0.0, 0.75 - rise * 1.9) * max(0.0, 1 - abs(x) / 0.75)


for k in range(17):
    lay(HEARTH + k * COURSE, BODY_W, BODY_D, k, clip_opening, body_soot)
body_core = core("Body mortar", BODY_W, BODY_D, HEARTH, BODY_H)

# Arch: wedge bricks round the semicircle, a limestone keystone at the crown.
ARCH_N = 15
for i in range(ARCH_N):
    key = i == ARCH_N // 2
    r0, r1 = OPEN_W / 2, OPEN_W / 2 + RING + (0.07 if key else 0)
    gap = M / (r0 + RING / 2) / 2
    a0, a1 = math.pi * i / ARCH_N + gap, math.pi * (i + 1) / ARCH_N - gap
    yf = FRONT - (0.04 if key else 0.018)
    corners = [(r * math.cos(a), y, SPRING + r * math.sin(a))
               for r in (r0, r1) for y in (yf, FRONT + 0.14) for a in (a1, a0)]
    if key:
        stone.hexa(corners, tone=0.5)
    else:
        bricks.hexa(corners, tone=rng.uniform(0.15, 0.7), soot=0.18 + 0.5 * math.sin(math.pi * (i + 0.5) / ARCH_N), moss=0)

# Stepped shoulders narrowing to the stack, then the stack and its corbelled cap.
for k in range(STEPS):
    w = BREAST_W - (BREAST_W - STACK_W) * k / STEPS
    lay(BREAST_Z + k * COURSE, w, STACK_D, k)
    core(f"Shoulder mortar {k}", w, STACK_D, BREAST_Z + k * COURSE, COURSE)
for k in range(STACK_COURSES):
    top = k / (STACK_COURSES - 1)
    lay(STACK_Z + k * COURSE, STACK_W, STACK_D, k + STEPS, soot_at=lambda c, top=top: 0.45 * top ** 3)
core("Stack mortar", STACK_W, STACK_D, STACK_Z, STACK_COURSES * COURSE)
for k in range(2):
    grow = 0.09 * (k + 1)
    lay(CAP_Z + k * COURSE, STACK_W + grow, STACK_D + grow, k, soot_at=lambda c: 0.3)
    core(f"Cap mortar {k}", STACK_W + grow, STACK_D + grow, CAP_Z + k * COURSE, COURSE)
SLAB_Z = CAP_Z + 2 * COURSE
stone.box((0, 0, SLAB_Z + 0.045), (STACK_W + 0.30, STACK_D + 0.30, 0.09), tone=0.4)

# Hearth of three flagstones, running under the firebox.
x = -1.39
for width in (0.98, 0.84, 0.94):
    stone.box((x + width / 2, -0.085, HEARTH / 2 + rng.uniform(-0.004, 0.004)), (width - 0.014, 1.07, HEARTH), tone=rng.random())
    x += width
# Corbels carrying the mantel beam.
for sx in (-1.06, 1.06):
    stone.box((sx, FRONT - 0.07, MANTEL_Z - 0.07), (0.17, 0.14, 0.14), tone=0.6)
    stone.box((sx, FRONT - 0.045, MANTEL_Z - 0.19), (0.13, 0.09, 0.10), tone=0.6)

keep(bricks.build(scene, "Bricks", [BRICK], bevel=0.007))
keep(stone.build(scene, "Stonework", [LIME], bevel=0.012))

# Cut the firebox out of the mortar core and line it with sooted firebrick.
FIREBOX_DEPTH = 0.56
profile = [(-OPEN_W / 2, HEARTH - 0.02)] + [
    (OPEN_W / 2 * math.cos(a), SPRING + OPEN_W / 2 * math.sin(a))
    for a in [math.pi - math.pi * i / 24 for i in range(25)]] + [(OPEN_W / 2, HEARTH - 0.02)]


def prism(name, outline, y0, y1, mats, front=False):
    n = len(outline)
    verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
    faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)] + [tuple(range(n, 2 * n))]
    if front:
        faces.append(tuple(reversed(range(n))))
    return rig.add_mesh(scene, name, verts, faces, mats)


cutter = keep(prism("Firebox cutter", profile, FRONT - 0.2, FRONT + FIREBOX_DEPTH, [], front=True))
cutter.hide_render = True
rig.modifier(body_core, "BOOLEAN", object=cutter, operation="DIFFERENCE", solver="EXACT")
inner = [(x * 0.997, z if z < HEARTH else SPRING + (z - SPRING) * 0.997) for x, z in profile]
keep(prism("Firebox lining", inner, FRONT + 0.01, FRONT + FIREBOX_DEPTH - 0.004, [SOOT]))

# Mantel: a heavy oak beam.
beam = keep(rig.add_mesh(scene, "Mantel beam", rig.box_verts((0, -0.10, MANTEL_Z + MANTEL_H / 2), (2.84, 1.0, MANTEL_H)),
                         rig.BOX_FACES, [TIMBER]))
rig.modifier(beam, "BEVEL", width=0.022, segments=3)

# Chimney pot: a tapered terracotta tube with a rolled rim, open at the top.
POT_Z, POT_H = SLAB_Z + 0.09, 0.44
lathe = [(0.185, 0.0), (0.19, 0.03), (0.165, 0.06), (0.150, 0.20), (0.135, 0.34), (0.155, 0.37), (0.16, 0.41),
         (0.14, POT_H), (0.105, POT_H), (0.10, 0.30), (0.10, 0.05)]
sides = 40
verts = [(r * math.cos(TAU * i / sides), r * math.sin(TAU * i / sides), POT_Z + z) for r, z in lathe for i in range(sides)]
faces = [(j * sides + i, j * sides + (i + 1) % sides, (j + 1) * sides + (i + 1) % sides, (j + 1) * sides + i)
         for j in range(len(lathe) - 1) for i in range(sides)]
faces.append(tuple(range((len(lathe) - 1) * sides, len(lathe) * sides)))
pot = keep(rig.add_mesh(scene, "Chimney pot", verts, faces, [TERRACOTTA, SOOT], smooth=True, sharp_angle=50))
for poly in pot.data.polygons:
    if poly.index >= (len(lathe) - 4) * sides:
        poly.material_index = 1
MOUTH = Vector((0, 0, POT_Z + POT_H))


# ---- the fire --------------------------------------------------------------------------
def tube(name, a, b, radius, mats, sides=16, wobble=0.0):
    a, b = Vector(a), Vector(b)
    path = [a.lerp(b, i / 6) + Vector((0, 0, wobble * math.sin(i * 1.7))) for i in range(7)]
    verts, faces, _ = rig.sweep(path, [(radius * (1 + 0.06 * math.sin(i * 2.1)),) * 2 for i in range(7)], sides)
    return keep(rig.add_mesh(scene, name, verts, faces, mats, smooth=True, sharp_angle=60))


FIRE_Y = FRONT + 0.27
for sx in (-0.34, 0.34):       # andirons with ball finials, grate bars between them
    tube("Andiron", (sx, FRONT + 0.06, HEARTH), (sx, FRONT + 0.06, HEARTH + 0.34), 0.018, [IRON])
    tube("Andiron foot", (sx, FRONT + 0.06, HEARTH + 0.075), (sx, FRONT + 0.50, HEARTH + 0.075), 0.014, [IRON])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.034, location=(sx, FRONT + 0.06, HEARTH + 0.36), segments=20, ring_count=10)
    ball = keep(bpy.context.object)
    ball.data.materials.append(IRON)
    bpy.ops.object.shade_smooth()
for dy in (0.16, 0.30, 0.44):
    tube("Grate bar", (-0.40, FRONT + dy, HEARTH + 0.09), (0.40, FRONT + dy, HEARTH + 0.09), 0.011, [IRON])
logs = [((-0.38, FIRE_Y - 0.08, HEARTH + 0.17), (0.40, FIRE_Y - 0.05, HEARTH + 0.18), 0.072),
        ((-0.40, FIRE_Y + 0.12, HEARTH + 0.17), (0.36, FIRE_Y + 0.14, HEARTH + 0.175), 0.068),
        ((-0.33, FIRE_Y + 0.07, HEARTH + 0.30), (0.34, FIRE_Y - 0.04, HEARTH + 0.295), 0.060)]
for a, b, r in logs:
    tube("Log", a, b, r, [BARK], sides=20, wobble=0.006)
ember = rig.material("Embers", (0.05, 0.01, 0.0), 0.9)
g = Graph(ember)
heat = g.noise(g.coords(), scale=38, detail=2).outputs["Fac"]
g.to("Emission Color", g.ramp(heat, [(0.3, (0.6, 0.03, 0.0)), (0.6, (1.0, 0.30, 0.02)), (0.8, (1.0, 0.75, 0.25))]).outputs["Color"])
g.to("Emission Strength", 6.0)
for _ in range(34):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.012, 0.028),
                                          location=(rng.uniform(-0.36, 0.36), FIRE_Y + rng.uniform(-0.16, 0.2), HEARTH + rng.uniform(0.005, 0.03)))
    lump = keep(bpy.context.object)
    lump.scale = (rng.uniform(0.8, 1.5), rng.uniform(0.8, 1.4), 0.6)
    lump.data.materials.append(ember)
glow = bpy.data.lights.new("Firelight", "POINT")
glow.energy, glow.color, glow.shadow_soft_size = 11, (1.0, 0.40, 0.09), 0.16
firelight = bpy.data.objects.new("Firelight", glow)
scene.collection.objects.link(firelight)
firelight.location = (0, FIRE_Y - 0.05, HEARTH + 0.48)
keep(firelight)


# ---- decorations -----------------------------------------------------------------------
def stocking(x, cloth, trim, toe=1, seed=0):
    r = random.Random(seed)
    top = MANTEL_Z - 0.03
    y = FRONT - 0.11
    lean = r.uniform(-0.03, 0.03)
    path = rig.smooth_path([(x + lean, y, top), (x + lean * 0.5, y, top - 0.17), (x, y, top - 0.31),
                            (x + toe * 0.02, y, top - 0.39), (x + toe * 0.09, y, top - 0.44), (x + toe * 0.19, y, top - 0.445)], 7)
    n = len(path)
    radii = []
    for i in range(n):
        u = i / (n - 1)
        wide = 0.074 + 0.012 * math.sin(u * 3.0) + (0.016 if 0.55 < u < 0.8 else 0)
        end = min(1.0, (1 - u) / 0.07) ** 0.5 if u > 0.93 else 1.0
        radii.append((wide * end, 0.048 * end))
    verts, faces, _ = rig.sweep(path, radii, 20)
    sock = keep(rig.add_mesh(scene, "Stocking", verts, faces, [cloth], smooth=True))
    rig.modifier(sock, "SUBSURF", levels=1, render_levels=1)
    cuff_path = [Vector((x + lean, y, top + 0.012 - 0.10 * i / 5)) for i in range(6)]
    verts, faces, _ = rig.sweep(cuff_path, [(0.094, 0.066)] * 6, 20)
    cuff = keep(rig.add_mesh(scene, "Stocking cuff", verts, faces, [trim], smooth=True))
    rig.modifier(cuff, "SUBSURF", levels=2, render_levels=2)
    fluff = bpy.data.textures.new("Fleece", "CLOUDS")
    fluff.noise_scale = 0.018
    rig.modifier(cuff, "DISPLACE", texture=fluff, strength=0.022)
    tube("Stocking loop", (x + lean, y + 0.03, top), (x + lean, y + 0.05, MANTEL_Z + 0.01), 0.008, [trim])


stocking(-0.97, RED, WHITE, toe=-1, seed=1)
stocking(-0.68, GREEN, WHITE, toe=1, seed=2)
stocking(0.90, RED, WHITE, toe=1, seed=3)


def bow(center, size=1.0):
    for part in rig.bow(scene, center, SATIN, size):
        keep(part)


def bauble(location, mat, radius=0.036):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location, segments=20, ring_count=10)
    ball = keep(bpy.context.object)
    ball.data.materials.append(mat)
    bpy.ops.object.shade_smooth()


# Garland swagged along the front of the beam, with tails at both ends.
GY = -0.10 - 0.5 - 0.05
swag = [(-1.43, GY, MANTEL_Z - 0.42), (-1.42, GY, MANTEL_Z + 0.02), (-1.36, GY, MANTEL_Z + 0.12)]
for i in range(1, 4):
    x0, x1 = -1.36 + (i - 1) * 2.72 / 3, -1.36 + i * 2.72 / 3
    swag += [((x0 + x1) / 2, GY - 0.02, MANTEL_Z - 0.035), (x1, GY, MANTEL_Z + 0.12)]
swag += [(1.42, GY, MANTEL_Z + 0.02), (1.43, GY, MANTEL_Z - 0.42)]
garland_path = rig.smooth_path(swag, 10)
keep(rig.evergreen(scene, "Garland", garland_path, 0.085, NEEDLES, seed=4, per_unit=2600, length=(0.07, 0.12)))
for i, point in enumerate(garland_path[6:-6:7]):
    bauble(point + Vector((rng.uniform(-0.02, 0.02), -0.09, rng.uniform(-0.06, -0.01))), GOLD if i % 2 else RUBY, 0.042)
bow((-1.36, GY - 0.07, MANTEL_Z + 0.10), 1.15)
bow((1.36, GY - 0.07, MANTEL_Z + 0.10), 1.15)

# Lights. Each is a small lit bulb in the picture, and its place is written out so that the app
# can lay a glow over it. A glow's colour is a cell of glows.png: red, green, blue, amber,
# pink, (firelight,) warm white.
BULB_COLORS = {0: (1.0, 0.10, 0.06), 1: (0.08, 1.0, 0.22), 2: (0.12, 0.38, 1.0), 3: (1.0, 0.62, 0.08), 4: (1.0, 0.16, 0.55), 6: (1.0, 0.88, 0.66)}
BULBS = {index: rig.material(f"Bulb {index}", color, 0.3, Emission_Color=color, Emission_Strength=5.0) for index, color in BULB_COLORS.items()}
LIGHTS = []         # (where, colour, size of its glow)
light_rng = random.Random(77)      # its own, so the rest of the fireplace is built as before


def light(location, color, radius, glow):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location, segments=14, ring_count=8)
    bulb = keep(bpy.context.object)
    bulb.scale = (1.0, 1.0, 1.3)
    bulb.data.materials.append(BULBS[color])
    bpy.ops.object.shade_smooth()
    LIGHTS.append((Vector(location), color, glow))


# A string of coloured bulbs along the garland, between its baubles.
for i, point in enumerate(garland_path[2:-2:7]):
    light(point + Vector((light_rng.uniform(-0.02, 0.02), -0.10, light_rng.uniform(0.0, 0.05))), i % 5, 0.027, 0.46)

# Wreath on the stack.
WREATH_Z, WREATH_R, WREATH_Y = STACK_Z + 0.62, 0.235, -STACK_D / 2 - 0.075
ring = [Vector((WREATH_R * math.cos(TAU * i / 48), WREATH_Y, WREATH_Z + WREATH_R * math.sin(TAU * i / 48))) for i in range(49)]
keep(rig.evergreen(scene, "Wreath", ring, 0.085, NEEDLES, seed=9, per_unit=2600, length=(0.06, 0.10)))
for i in range(9):
    a = TAU * (i + 0.3) / 9
    if abs(a - 1.5 * math.pi) > 0.5:
        bauble((WREATH_R * math.cos(a), WREATH_Y - 0.07, WREATH_Z + WREATH_R * math.sin(a)), RUBY if i % 3 else GOLD, 0.028)
bow((0, WREATH_Y - 0.08, WREATH_Z - WREATH_R), 1.0)
# Fairy lights in the wreath: small ones, warm white and yellow by turns, clear of the bow.
for i in range(12):
    a = TAU * (i + 0.5) / 12
    if abs(a - 1.5 * math.pi) > 0.4:
        r = WREATH_R + light_rng.uniform(-0.04, 0.04)
        light((r * math.cos(a), WREATH_Y - 0.085, WREATH_Z + r * math.sin(a)), 6 if i % 2 else 3, 0.014, 0.2)

sand = keep(rig.sand_drift(scene, -1.39, 1.37, -0.62, 0.45))

# ---- turn the whole fireplace, light and frame it --------------------------------------
pivot = bpy.data.objects.new("Fireplace", None)
scene.collection.objects.link(pivot)
for obj in built:
    obj.parent = pivot
pivot.rotation_euler.z = math.radians(TURN)
turn = Matrix.Rotation(math.radians(TURN), 4, "Z")

rig.tank_light(scene)
cam = rig.camera(scene, elevation=9)
catcher = rig.ground(scene)
visible = [o for o in built if o.type == "MESH" and not o.hide_render and o is not sand]
w, h = rig.frame(scene, cam, visible, pad=(10, 6, 26, 14))


# ---- flames: camera-facing cards whose shader scrolls and loops --------------------------
def flame_material(name, seed, phase):
    """Two copies of a rising noise field half a loop apart, cross-faded so frame N meets frame 0."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    g = Graph(mat)
    g.tree.nodes.remove(g.shader)
    uv = g.node("ShaderNodeSeparateXYZ")
    g.set(uv.inputs[0], g.node("ShaderNodeUVMap").outputs["UV"])
    u, v = uv.outputs["X"], uv.outputs["Y"]

    def field(offset):
        rise = g.math("SUBTRACT", g.math("MULTIPLY", v, 1.5), offset)
        where = g.node("ShaderNodeCombineXYZ")
        g.set(where.inputs["X"], g.math("MULTIPLY", u, 2.4))
        g.set(where.inputs["Y"], rise)
        where.inputs["Z"].default_value = seed
        warp = g.math("SUBTRACT", g.noise(where.outputs[0], scale=1.6, detail=2).outputs["Fac"], 0.5)
        uu = g.math("ADD", u, g.math("MULTIPLY", g.math("MULTIPLY", warp, 0.55), v))
        fine = g.node("ShaderNodeCombineXYZ")
        g.set(fine.inputs["X"], g.math("MULTIPLY", uu, 5.0))
        g.set(fine.inputs["Y"], g.math("MULTIPLY", rise, 2.6))
        fine.inputs["Z"].default_value = seed + 11
        lick = g.math("SUBTRACT", g.noise(fine.outputs[0], scale=1.0, detail=3, roughness=0.6).outputs["Fac"], 0.5)
        reach = g.math("MULTIPLY", 0.47, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", v, 0.82)))
        shape = g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", uu, 0.5)), reach), clamp=True)
        heat = g.math("ADD", g.math("MULTIPLY", shape, 1.05), g.math("MULTIPLY", lick, 1.9))
        return g.math("SUBTRACT", heat, g.math("MULTIPLY", v, 1.18))

    t = g.node("ShaderNodeValue", label="loop")
    t.name = "loop"
    travel = 3.2
    wrapped = g.math("FRACT", g.math("ADD", t.outputs[0], phase))
    a = field(g.math("MULTIPLY", wrapped, travel))
    b = field(g.math("MULTIPLY", g.math("SUBTRACT", wrapped, 1.0), travel))
    heat = g.math("ADD", g.math("MULTIPLY", a, g.math("SUBTRACT", 1.0, wrapped)), g.math("MULTIPLY", b, wrapped))
    foot = g.math("SMOOTHSTEP", 0.0, 0.10, v)
    heat = g.math("MULTIPLY", heat, foot, clamp=True)
    color = g.ramp(heat, [(0.16, (0.70, 0.04, 0.0, 0.0)), (0.30, (0.95, 0.13, 0.01, 0.66)), (0.48, (1.0, 0.36, 0.02, 0.93)),
                          (0.68, (1.0, 0.66, 0.10, 1.0)), (0.86, (1.0, 0.88, 0.36, 1.0)), (1.0, (1.0, 0.97, 0.72, 1.0))])
    emit = g.node("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.25
    g.set(emit.inputs["Color"], color.outputs["Color"])
    clear = g.node("ShaderNodeBsdfTransparent")
    blend = g.node("ShaderNodeMixShader")
    g.set(blend.inputs[0], color.outputs["Alpha"])
    g.set(blend.inputs[1], clear.outputs[0])
    g.set(blend.inputs[2], emit.outputs[0])
    g.set(g.output.inputs["Surface"], blend.outputs[0])
    return mat


fire_base = turn @ Vector((0, FIRE_Y, HEARTH + 0.20))
right = (cam.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
up = (cam.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
toward = (cam.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
flames = []
for i, (dx, wide, tall, depth) in enumerate([(0.0, 0.98, 0.94, -0.06), (-0.22, 0.56, 0.68, -0.03), (0.21, 0.60, 0.74, 0.0), (0.02, 0.46, 0.54, 0.025)]):
    origin = fire_base + right * dx + toward * depth
    corners = [origin - right * wide / 2, origin + right * wide / 2, origin + right * wide / 2 + up * tall, origin - right * wide / 2 + up * tall]
    card = rig.add_mesh(scene, f"Flame {i}", [tuple(c) for c in corners], [(0, 1, 2, 3)],
                        [flame_material(f"Flame {i}", seed=3.7 * i + 1.3, phase=i * 0.27)])
    layer = card.data.uv_layers.new(name="UVMap")
    for loop, co in zip(layer.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    card.visible_shadow = False
    card.visible_diffuse = False
    card.visible_glossy = False
    flames.append(card)

bpy.ops.wm.save_as_mainfile(filepath=str(OUT))

# Still picture: masonry, decorations and embers, lit by the fire but without the flames.
for card in flames:
    card.hide_render = True
rig.render(scene, rig.HERE / "fireplace.png")

# Flame sheet: only the cards, with everything in front of them cut out of the picture.
FRAMES, COLS = 16, 4
for obj in scene.objects:
    if obj.type == "MESH" and obj not in flames:
        obj.is_holdout = True
catcher.hide_render = True
for card in flames:
    card.hide_render = False
points = [rig.project(scene, cam, card.matrix_world @ v.co) for card in flames for v in card.data.vertices]
box = (math.floor(min(p[0] for p in points)), math.floor(min(p[1] for p in points)),
       math.ceil(max(p[0] for p in points)), math.ceil(max(p[1] for p in points)))
rig.crop_to(scene, box)
scene.cycles.samples = 48
scene.cycles.use_denoising = False
paths = []
for f in range(FRAMES):
    for card in flames:
        card.data.materials[0].node_tree.nodes["loop"].outputs[0].default_value = f / FRAMES
    paths.append(rig.HERE / f"_flame_{f:02d}.png")
    rig.render(scene, paths[-1])
fw, fh = rig.pack_grid(paths, rig.HERE / "fire_frames.png", COLS)

mouth = rig.project(scene, cam, turn @ MOUTH)
hearth = rig.project(scene, cam, turn @ Vector((0, FIRE_Y, HEARTH + 0.35)))
foot = rig.project(scene, cam, (0, 0, 0))
bulbs = []
for k, (where, color, glow) in enumerate(LIGHTS):
    x, y = rig.project(scene, cam, turn @ where)[:2]
    bulbs.append([round(x, 1), round(y, 1), color, k % 8, glow])
(rig.HERE / "fireplace.json").write_text(json.dumps({
    "size": [w, h], "foot": foot, "chimney": mouth, "hearth": hearth,
    "fire": {"x": box[0], "y": box[1], "w": fw, "h": fh, "frames": FRAMES, "cols": COLS},
    "bulbs": bulbs,
}) + "\n")
print("FIREPLACE", w, h, "flame frame", fw, fh, "mouth", mouth)
