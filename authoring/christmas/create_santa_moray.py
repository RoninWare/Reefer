"""Model the green moray in his Santa hat and bake his animation into a sprite sheet.

    blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_santa_moray.py

The eel is rebuilt from scratch for every frame from a pose (how far along the cave track his
head is, body sway, jaw gape, hat and sack angles), so no rig is needed. He is modelled in
tank pixels straight on, so each frame lands at a known place in front of the cave.

Two clips are baked: "pop" (he shoots out of the cave, overshoots, and his hat and sack catch
up) and "idle" (a seamless loop: swaying, looking about, breathing). Writes santa_moray.blend
(the first idle pose, editable), santa_moray.png (the sheet) and santa_moray.json.

Options after "--":  --overwrite   regenerate santa_moray.blend
                     --still NAME  render one pose (pop:<seconds> or idle:<phase>) to _still.png
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig
from rig import Graph, TAU

args = rig.script_args()
STILL = args[args.index("--still") + 1] if "--still" in args else None
OUT = rig.HERE / "santa_moray.blend"
if not STILL:
    rig.guard(OUT)
scene = rig.reset(samples=160)

# The picture every frame is cut from, in tank pixels. Nothing right of VIEW_X1 is ever seen:
# the cave's shade is opaque there.
VIEW_X0, VIEW_Y0, VIEW_X1, VIEW_Y1 = 1900, 640, 2312, 910
# The cave track, deep end first: tank x, tank y, depth toward the back of the tank (units).
TRACK = [(2600, 848, 0.34), (2470, 848, 0.30), (2350, 847, 0.20), (2262, 845, 0.08), (2196, 836, -0.04),
         (2142, 806, -0.15), (2098, 768, -0.23), (2046, 742, -0.29), (1984, 736, -0.33), (1920, 746, -0.36), (1850, 760, -0.38)]
TIP_IN, TIP_OUT = 2262.0, 1978.0      # tank x of the snout when hidden and when fully out
HEAD = 0.72                           # head length, units (1 unit = 100 px)
HINGE = 0.54


def tank(x, y, depth=0.0):
    return Vector((x / rig.PX, depth, -y / rig.PX))


track = rig.smooth_path([tank(*k) for k in TRACK], 24)
track_s = [0.0]
for p, q in zip(track, track[1:]):
    track_s.append(track_s[-1] + (q - p).length)


def on_track(s):
    s = min(max(s, 0.0), track_s[-1] - 1e-6)
    i = int(np.searchsorted(track_s, s, side="right")) - 1
    u = (s - track_s[i]) / (track_s[i + 1] - track_s[i])
    return track[i].lerp(track[i + 1], u)


def track_at_x(x):
    """Arc position where the track crosses tank x."""
    for i in range(len(track) - 1):
        if track[i + 1].x * rig.PX <= x:
            a, b = track[i].x * rig.PX, track[i + 1].x * rig.PX
            return track_s[i] + (track_s[i + 1] - track_s[i]) * (a - x) / (a - b)
    return track_s[-1]


S_IN, S_OUT = track_at_x(TIP_IN), track_at_x(TIP_OUT)


def curve(points):
    """Piecewise-linear lookup through (s, value) pairs."""
    xs, ys = zip(*points)
    return lambda s: float(np.interp(s, xs, ys))


TOP = curve([(0, 0.060), (0.04, 0.105), (0.12, 0.150), (0.26, 0.185), (0.42, 0.215), (0.60, 0.268), (0.80, 0.285), (1.1, 0.272), (9, 0.265)])
BELLY = curve([(0, 0.25), (0.7, 0.262), (1.0, 0.275), (9, 0.265)])
WIDTH = curve([(0, 0.060), (0.05, 0.100), (0.16, 0.130), (0.36, 0.165), (0.6, 0.190), (1.0, 0.180), (9, 0.17)])
JAW = curve([(0.03, 0.055), (0.09, 0.090), (0.22, 0.120), (0.38, 0.155), (0.54, 0.200), (0.70, 0.235)])
FIN = curve([(0, 0), (0.85, 0), (1.25, 0.055), (2.2, 0.075), (9, 0.075)])
MOUTH_LINE = 0.022


def smoothstep(a, b, x):
    u = min(max((x - a) / (b - a), 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---- materials -------------------------------------------------------------------------
def skin_material():
    mat = rig.material("Green moray skin", (0.25, 0.36, 0.06), 0.30, Coat_Weight=0.55, Coat_Roughness=0.15)
    g = Graph(mat)
    rest = g.attribute("rest").outputs["Vector"]
    belly = g.attribute("belly").outputs["Fac"]
    mouth = g.attribute("mouth").outputs["Fac"]
    flank = g.ramp(belly, [(0.0, (0.070, 0.115, 0.018)), (0.28, (0.150, 0.225, 0.030)), (0.60, (0.270, 0.340, 0.050)),
                           (0.84, (0.470, 0.480, 0.130)), (1.0, (0.620, 0.580, 0.250))]).outputs["Color"]
    blotch = g.noise(rest, scale=15, detail=4, roughness=0.62, distortion=0.4).outputs["Fac"]
    freckle = g.noise(rest, scale=46, detail=2).outputs["Fac"]
    color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.58, 0.38, blotch), 0.55), flank, (0.060, 0.105, 0.020), "MIX")
    color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.60, 0.74, freckle), 0.35), color, (0.60, 0.62, 0.24))
    color = g.mix(mouth, color, (0.74, 0.42, 0.40))
    g.to("Base Color", color)
    g.to("Subsurface Weight", 0.12)
    g.to("Subsurface Radius", (0.05, 0.08, 0.02))
    g.to("Subsurface Scale", 0.4)
    g.bump(g.noise(rest, scale=60, detail=3).outputs["Fac"], strength=0.10, distance=0.01)
    return mat


def fleece_material():
    mat = rig.material("Fleece", (0.93, 0.93, 0.90), 0.95, Sheen_Weight=0.8, Sheen_Roughness=0.5)
    g = Graph(mat)
    g.bump(g.noise(g.coords(), scale=70, detail=4, roughness=0.8).outputs["Fac"], strength=0.9, distance=0.03)
    return mat


def cane_material():
    mat = rig.material("Candy cane", (0.9, 0.9, 0.9), 0.22, Coat_Weight=0.6)
    g = Graph(mat)
    sep = g.node("ShaderNodeSeparateXYZ")
    g.set(sep.inputs[0], g.attribute("rest").outputs["Vector"])
    stripe = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", sep.outputs["X"], 7.0), sep.outputs["Y"]))
    g.to("Base Color", g.mix(g.math("SMOOTHSTEP", 0.42, 0.50, stripe), (0.93, 0.92, 0.90), (0.70, 0.01, 0.03)))
    return mat


SKIN = skin_material()
FLEECE = fleece_material()
FELT = rig.material("Hat felt", (0.62, 0.012, 0.025), 0.92, Sheen_Weight=0.8, Sheen_Roughness=0.55)
VELVET = rig.material("Sack velvet", (0.46, 0.016, 0.028), 0.88, Sheen_Weight=1.0, Sheen_Roughness=0.4)
_g = Graph(VELVET)
_fold = _g.noise(_g.coords(), scale=9, detail=3, roughness=0.6, distortion=1.2).outputs["Fac"]
_g.to("Base Color", _g.mix(_g.math("SMOOTHSTEP", 0.35, 0.65, _fold), (0.30, 0.008, 0.018), (0.56, 0.022, 0.035)))
_g.bump(_fold, strength=0.5, distance=0.05)
CORD = rig.material("Gold cord", (1.0, 0.63, 0.16), 0.30, Metallic=1.0)
EYE = rig.material("Eye", (0.92, 0.88, 0.62), 0.08, Coat_Weight=1.0)
PUPIL = rig.material("Pupil", (0.004, 0.004, 0.006), 0.05, Coat_Weight=1.0)
TOOTH = rig.material("Tooth", (0.95, 0.94, 0.88), 0.25)
CANE = cane_material()
GIFT = rig.material("Gift foil", (0.10, 0.45, 0.85), 0.25, Metallic=0.8)
FLUFF = bpy.data.textures.new("Fleece tufts", "CLOUDS")
FLUFF.noise_scale = 0.02


# ---- the eel ---------------------------------------------------------------------------
REST = dict(out=1.0, phase=0.0, sway=1.0, yaw=0.20, gape=0.0, hat_tilt=12.0, hat_bend=118.0, sack_tilt=20.0, sack_lift=0.0)


def build(pose):
    made = []

    def add(name, verts, faces, mats, smooth=True, **kw):
        obj = rig.add_mesh(scene, name, verts, faces, mats, smooth=smooth, **kw)
        made.append(obj)
        return obj

    # Centre line from the snout back into the cave.
    s_tip = S_IN + (S_OUT - S_IN) * pose["out"]
    step = 0.03
    n = int(min(s_tip, 4.2) / step)
    centre = []
    for i in range(n + 1):
        s = i * step
        p = on_track(s_tip - s).copy()
        reach = smoothstep(0.0, 1.0, pose["out"])
        # Idle sway: a slow wave running back from the head, fading out toward the cave.
        fade = max(0.0, 1 - s / 2.6) ** 1.3 * reach * pose["sway"]
        p.z += 0.070 * fade * math.sin(TAU * pose["phase"] - 2.1 * s)
        # The head swings toward the glass, so he looks out at the room.
        p.y -= pose["yaw"] * reach * max(0.0, 1.0 - s) ** 2
        centre.append(p)
    frames = []
    for i in range(n + 1):
        t = (centre[min(i + 1, n)] - centre[max(i - 1, 0)]).normalized()      # toward the tail
        side = t.cross(Vector((0, 0, 1))).normalized()                        # toward the glass
        frames.append((t, side, side.cross(t).normalized()))

    def at(s):
        """Centre, tail-ward, glass-ward and up vectors at s units behind the snout."""
        f = min(max(s / step, 0.0), n - 1e-6)
        i = int(f)
        u = f - i
        c = centre[i].lerp(centre[i + 1], u)
        return (c,) + tuple(frames[i][k].lerp(frames[i + 1][k], u).normalized() for k in range(3))

    SIDES = 28
    verts, faces, rest, belly, mouth = [], [], [], [], []
    for i in range(n + 1):
        s = i * step
        c, t, side, up = centre[i], *frames[i]
        open_jaw = 1 - smoothstep(HINGE - 0.08, HINGE + 0.14, s)
        top, low, wide, fin = TOP(s), MOUTH_LINE * open_jaw + BELLY(s) * (1 - open_jaw), WIDTH(s), FIN(s)
        if i == 0:
            top, low, wide = 0.030, 0.012, 0.030
        for k in range(SIDES):
            a = TAU * k / SIDES
            ca, sa = math.cos(a), math.sin(a)
            y = top * sa + fin * max(0.0, sa) ** 9 if sa >= 0 else low * sa
            x = wide * ca * (1 - 0.35 * max(0.0, sa) ** 9 * (fin > 0))
            verts.append(tuple(c + side * x + up * y))
            rest.append((s, 0.5 * ca, 0.5 * sa))
            belly.append(0.5 - 0.5 * sa * (0.75 if sa < 0 else 1.0) + 0.12 * (1 - smoothstep(0.0, 0.5, s)))
            mouth.append(open_jaw * smoothstep(-0.25, -0.6, sa) * (s < HINGE + 0.04))
            if i:
                j = (k + 1) % SIDES
                faces.append(((i - 1) * SIDES + k, (i - 1) * SIDES + j, i * SIDES + j, i * SIDES + k))
    faces.append(tuple(reversed(range(SIDES))))
    body = add("Moray body", verts, faces, [SKIN])
    attr = body.data.attributes.new("rest", "FLOAT_VECTOR", "POINT")
    attr.data.foreach_set("vector", [c for v in rest for c in v])
    rig.point_attribute(body, "belly", belly)
    rig.point_attribute(body, "mouth", mouth)
    rig.modifier(body, "SUBSURF", levels=1, render_levels=1)

    # Lower jaw, swinging down about the hinge.
    hc, ht, hside, hup = at(HINGE + 0.03)
    pivot = hc - hup * 0.035
    swing = Matrix.Rotation(math.radians(pose["gape"]), 3, hside)
    verts, faces, rest, belly, mouth = [], [], [], [], []
    rings = 0
    s = 0.035
    while s <= 0.70:
        c, t, side, up = at(s)
        deep, wide = JAW(s), WIDTH(s) * 0.93
        mid = c - up * (MOUTH_LINE + deep / 2)
        if rings == 0:
            deep, wide = 0.030, 0.030
        for k in range(SIDES):
            a = TAU * k / SIDES
            ca, sa = math.cos(a), math.sin(a)
            p = mid + side * (wide * ca) + up * (deep / 2 * (sa * 0.45 if sa > 0 else sa))
            verts.append(tuple(pivot + swing @ (p - pivot)))
            rest.append((s, 0.5 * ca, 0.5 * sa - 1.0))
            belly.append(0.74 + 0.22 * (0.5 - 0.5 * sa))
            mouth.append(smoothstep(0.15, 0.6, sa) * (s < HINGE))
            if rings:
                j = (k + 1) % SIDES
                faces.append(((rings - 1) * SIDES + k, (rings - 1) * SIDES + j, rings * SIDES + j, rings * SIDES + k))
        rings += 1
        s += step
    faces.append(tuple(reversed(range(SIDES))))
    jaw = add("Moray jaw", verts, faces, [SKIN])
    attr = jaw.data.attributes.new("rest", "FLOAT_VECTOR", "POINT")
    attr.data.foreach_set("vector", [c for v in rest for c in v])
    rig.point_attribute(jaw, "belly", belly)
    rig.point_attribute(jaw, "mouth", mouth)
    rig.modifier(jaw, "SUBSURF", levels=1, render_levels=1)

    def ball(name, centre_point, radius, mat, squash=None):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=centre_point, segments=24, ring_count=12)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        if squash:
            obj.scale = squash
        made.append(obj)
        return obj

    # Eyes: pale, bright and a little large for an eel, each with a dark pupil looking forward.
    for sign in (1, -1):
        c, t, side, up = at(0.21)
        eye = c + side * (sign * WIDTH(0.21) * 0.80) + up * (TOP(0.21) * 0.52)
        ball("Eye", eye, 0.052, EYE)
        ball("Pupil", eye + side * (sign * 0.030) - t * 0.014 + up * 0.004, 0.031, PUPIL)
    # Nostril tubes at the snout.
    for sign in (1, -1):
        c, t, side, up = at(0.03)
        base = c + side * (sign * 0.045) + up * 0.075
        v, f, _ = rig.sweep([base, base - t * 0.035 + up * 0.03], [(0.012, 0.012), (0.008, 0.008)], 8)
        obj = add("Nostril", v, f, [SKIN])
        attr = obj.data.attributes.new("rest", "FLOAT_VECTOR", "POINT")
        rig.point_attribute(obj, "belly", [0.45] * len(v))
    # A few needle teeth along each jaw.
    for s in (0.07, 0.13, 0.19, 0.26, 0.33):
        for sign in (1, -1):
            c, t, side, up = at(s)
            root = c + side * (sign * WIDTH(s) * 0.72) - up * (MOUTH_LINE - 0.004)
            v, f, _ = rig.sweep([root, root - up * 0.034 + t * 0.008], [(0.008, 0.008), (0.001, 0.001)], 6)
            add("Tooth", v, f, [TOOTH])
            low_root = pivot + swing @ (c + side * (sign * WIDTH(s) * 0.66) - up * (MOUTH_LINE + 0.006) + t * 0.03 - pivot)
            v, f, _ = rig.sweep([low_root, low_root + swing @ (up * 0.03 + t * 0.006)], [(0.007, 0.007), (0.001, 0.001)], 6)
            add("Tooth", v, f, [TOOTH])

    # Santa hat on the nape: fleece band, a felt cone that flops back, a pompom at the tip.
    hs = 0.66
    c, t, side, up = at(hs)
    tilt = math.radians(pose["hat_tilt"])
    axis = (up * math.cos(tilt) + t * math.sin(tilt)).normalized()
    seat = c + up * (TOP(hs) - 0.075) + t * 0.02
    fore = (t - axis * t.dot(axis)).normalized()
    band = [seat + fore * (0.19 * math.cos(a)) + side * (0.185 * math.sin(a)) for a in [TAU * i / 28 for i in range(29)]]
    v, f, _ = rig.sweep(band, [(0.056, 0.056)] * len(band), 12, cap=False)
    brim = add("Hat band", v, f, [FLEECE])
    rig.modifier(brim, "SUBSURF", levels=1, render_levels=1)
    rig.modifier(brim, "DISPLACE", texture=FLUFF, strength=0.022)
    spine, radii = [seat.copy()], [(0.172, 0.168)]
    length, parts = 0.66, 16
    for i in range(1, parts + 1):
        q = i / parts
        ang = tilt + math.radians(pose["hat_bend"]) * q ** 1.25
        heading = (up * math.cos(ang) + t * math.sin(ang) + side * (0.22 * q)).normalized()
        spine.append(spine[-1] + heading * (length / parts))
        radii.append(((0.172 * (1 - q) ** 0.9 + 0.022),) * 2)
    v, f, _ = rig.sweep(spine, radii, 20)
    cone = add("Hat", v, f, [FELT])
    rig.modifier(cone, "SUBSURF", levels=1, render_levels=1)
    pom = ball("Pompom", spine[-1], 0.074, FLEECE)
    rig.modifier(pom, "SUBSURF", levels=1, render_levels=1)
    rig.modifier(pom, "DISPLACE", texture=FLUFF, strength=0.03)

    # The sack, riding the near shoulder: a lumpy velvet bag, fleece cuff, gold cord.
    ss = 1.50
    c, t, side, up = at(ss)
    lean = math.radians(pose["sack_tilt"])
    axis = (up * math.cos(lean) + t * math.sin(lean) + side * 0.30).normalized()
    foot = c + up * (TOP(ss) * 0.12 + pose["sack_lift"]) + side * 0.17
    e1 = (t - axis * t.dot(axis)).normalized()
    e2 = axis.cross(e1).normalized()
    profile = [(0.0, 0.10), (0.04, 0.23), (0.12, 0.305), (0.24, 0.31), (0.37, 0.25), (0.47, 0.17), (0.545, 0.115),
               (0.60, 0.135), (0.66, 0.175), (0.70, 0.185)]
    SACK_SIDES = 28
    verts, faces = [], []
    dense = [(h, r) for (h0, r0), (h1, r1) in zip(profile, profile[1:]) for h, r in
             [(h0 + (h1 - h0) * u / 3, r0 + (r1 - r0) * u / 3) for u in range(3)]] + [profile[-1]]
    for j, (h, r) in enumerate(dense):
        for k in range(SACK_SIDES):
            a = TAU * k / SACK_SIDES
            lump = 1 + (0.085 * math.sin(3 * a + 7 * h + 0.6) + 0.06 * math.sin(5 * a - 11 * h + 2.0)) * smoothstep(0.5, 0.3, h)
            pleat = 1 + 0.07 * math.sin(9 * a) * smoothstep(0.38, 0.56, h)
            verts.append(tuple(foot + axis * h + (e1 * math.cos(a) + e2 * math.sin(a)) * (r * lump * pleat)))
            if j:
                k2 = (k + 1) % SACK_SIDES
                faces.append(((j - 1) * SACK_SIDES + k, (j - 1) * SACK_SIDES + k2, j * SACK_SIDES + k2, j * SACK_SIDES + k))
    faces.append(tuple(reversed(range(SACK_SIDES))))
    faces.append(tuple(range((len(dense) - 1) * SACK_SIDES, len(dense) * SACK_SIDES)))
    sack = add("Sack", verts, faces, [VELVET])
    rig.modifier(sack, "SUBSURF", levels=1, render_levels=1)
    for name, h, r, tube, mat, fluffy in (("Sack cuff", 0.705, 0.19, 0.046, FLEECE, True), ("Sack cord", 0.545, 0.125, 0.017, CORD, False)):
        loop = [foot + axis * h + (e1 * math.cos(a) + e2 * math.sin(a)) * r for a in [TAU * i / 28 for i in range(29)]]
        v, f, _ = rig.sweep(loop, [(tube, tube)] * len(loop), 10, cap=False)
        ring = add(name, v, f, [mat])
        if fluffy:
            rig.modifier(ring, "SUBSURF", levels=1, render_levels=1)
            rig.modifier(ring, "DISPLACE", texture=FLUFF, strength=0.02)
    # Out of the top: a candy cane and the corner of a present.
    stem = foot + axis * 0.56 + e1 * 0.045 + e2 * 0.03
    lean_out = (axis + e1 * 0.22).normalized()
    hook = [stem + lean_out * (0.34 * i / 6) for i in range(7)]
    for i in range(1, 8):
        a = math.pi * i / 7
        hook.append(hook[6] + lean_out * (0.06 * math.sin(a)) + e1 * (0.06 * (1 - math.cos(a))))
    hook = rig.smooth_path(hook, 3)
    v, f, uv = rig.sweep(hook, [(0.027, 0.027)] * len(hook), 10)
    cane = add("Candy cane", v, f, [CANE])
    attr = cane.data.attributes.new("rest", "FLOAT_VECTOR", "POINT")
    attr.data.foreach_set("vector", [c2 for a, b in uv for c2 in (a, b, 0.0)])
    spin = Matrix.Rotation(0.5, 3, axis) @ Matrix.Rotation(0.35, 3, e2)
    parcel = add("Parcel", [tuple(foot + axis * 0.73 - e1 * 0.07 - e2 * 0.02 + spin @ Vector(p)) for p in rig.box_verts((0, 0, 0), (0.15, 0.15, 0.15))],
                 rig.BOX_FACES, [GIFT], smooth=False)
    rig.modifier(parcel, "BEVEL", width=0.01, segments=2)
    for dims in ((0.158, 0.04, 0.158), (0.04, 0.158, 0.158)):
        ribbon = add("Parcel ribbon", [tuple(foot + axis * 0.73 - e1 * 0.07 - e2 * 0.02 + spin @ Vector(p)) for p in rig.box_verts((0, 0, 0), dims)],
                     rig.BOX_FACES, [CORD], smooth=False)
    # The strap: a gold cord round his neck, running up to the sack's tie.
    c, t, side, up = at(1.12)
    loop = []
    for i in range(33):
        a = TAU * i / 32
        ca, sa = math.cos(a), math.sin(a)
        y = (TOP(1.12) + FIN(1.12) * 0.3) * sa if sa >= 0 else BELLY(1.12) * sa
        loop.append(c + side * (WIDTH(1.12) + 0.012) * ca + up * (y * 1.03) + t * (0.10 * sa))
    v, f, _ = rig.sweep(loop, [(0.016, 0.016)] * len(loop), 8, cap=False)
    add("Strap", v, f, [CORD])
    tie = foot + axis * 0.545 - e1 * 0.11 + e2 * 0.03
    lead = rig.smooth_path([loop[5], (loop[5] + tie) / 2 + up * 0.03, tie], 5)
    v, f, _ = rig.sweep(lead, [(0.013, 0.013)] * len(lead), 8)
    add("Strap lead", v, f, [CORD])
    return made


def clear(made):
    for obj in made:
        mesh = obj.data
        bpy.data.objects.remove(obj)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


# ---- the animation ---------------------------------------------------------------------
def idle(phase):
    """The seamless loop: sway, a look round, one slow breath."""
    w = TAU * phase
    breath = min(max((phase - 0.08) / 0.5, 0.0), 1.0)
    return dict(out=1.0 - 0.02 * (1 - math.cos(w)), phase=phase, sway=1.0, yaw=0.20 + 0.10 * math.sin(w + 0.6),
                gape=9.0 * math.sin(math.pi * breath) ** 2, hat_tilt=12 + 4 * math.sin(w + 2.0), hat_bend=118 + 8 * math.sin(2 * w + 0.5),
                sack_tilt=20 + 3 * math.sin(w + 1.0), sack_lift=0.006 * math.sin(w + 2.5))


def pop_poses(times):
    """He launches like a sprung coil and overshoots; the hat lies flat in the cave, then snaps
    up and wobbles; the sack is dragged along and bounces as it clears the mouth."""
    dt, t, poses = 1 / 480, 0.0, {}
    hat = dict(tilt=80.0, v=0.0, bend=26.0, bv=0.0)
    sack = dict(tilt=58.0, v=0.0, lift=-0.05, lv=0.0)
    rest = idle(0.0)
    wanted = sorted(times)
    while wanted:
        out = 1 - math.exp(-7.2 * t) * (math.cos(10.2 * t) + 0.70 * math.sin(10.2 * t))
        up = out > 0.40          # the hat has cleared the cave lip
        free = out > 0.72        # so has the sack
        for state, key, vel, target, k, c in ((hat, "tilt", "v", rest["hat_tilt"] if up else 80.0, 190, 6.5),
                                              (hat, "bend", "bv", rest["hat_bend"] if up else 26.0, 150, 6.0),
                                              (sack, "tilt", "v", rest["sack_tilt"] if free else 58.0, 120, 5.5),
                                              (sack, "lift", "lv", rest["sack_lift"] if free else -0.05, 170, 7.0)):
            state[vel] += (k * (target - state[key]) - c * state[vel]) * dt
            state[key] += state[vel] * dt
        if t >= wanted[0] - 1e-9:
            settle = smoothstep(0.95, 1.25, t)
            pose = dict(out=out, phase=0.0, sway=smoothstep(0.3, 1.0, t), yaw=rest["yaw"] * smoothstep(0.1, 0.7, t),
                        gape=17.0 * math.sin(math.pi * min(max((t - 0.04) / 0.8, 0), 1)) ** 2,
                        hat_tilt=hat["tilt"], hat_bend=hat["bend"], sack_tilt=sack["tilt"], sack_lift=sack["lift"])
            poses[wanted.pop(0)] = {k: pose[k] + (rest[k] - pose[k]) * settle for k in pose}
        t += dt
    return poses


POP_TIMES = [0.0, 0.033, 0.067, 0.1, 0.133, 0.167, 0.2, 0.25, 0.3, 0.367, 0.433, 0.5, 0.6, 0.7, 0.8, 0.933, 1.067, 1.25]
POP_BLEND_FROM = 8          # frames from here on move slowly enough to cross-fade
IDLE_FRAMES, IDLE_PERIOD = 12, 4.8

rig.tank_light(scene, key=4.2, sky=0.75, sand=0.16)
cam = rig.camera(scene, elevation=0)
cam.location = ((VIEW_X0 + VIEW_X1) / 2 / rig.PX, -30, -(VIEW_Y0 + VIEW_Y1) / 2 / rig.PX)
scene.render.resolution_x, scene.render.resolution_y = VIEW_X1 - VIEW_X0, VIEW_Y1 - VIEW_Y0
cam.data.ortho_scale = max(scene.render.resolution_x, scene.render.resolution_y) / rig.PX

if STILL:
    kind, value = STILL.split(":")
    pose = idle(float(value)) if kind == "idle" else pop_poses([float(value)])[float(value)]
    build(pose)
    rig.render(scene, rig.HERE / "_still.png")
    print("STILL", STILL, {k: round(v, 3) for k, v in pose.items()})
    sys.exit(0)

pop = pop_poses(POP_TIMES)
poses = [pop[t] for t in POP_TIMES] + [idle(i / IDLE_FRAMES) for i in range(IDLE_FRAMES)]
crops = []
for index, pose in enumerate(poses):
    made = build(pose)
    path = rig.HERE / f"_moray_{index:02d}.png"
    rig.render(scene, path)
    pixels = rig.read_pixels(path)
    path.unlink()
    # The cave's own darkness falls on him: his body dims as it runs back from the mouth.
    xs = (np.arange(pixels.shape[1]) + VIEW_X0 - 2195.0) / (2305.0 - 2195.0)
    depth = np.clip(xs, 0, 1)
    pixels[..., :3] *= (1 - 0.82 * depth * depth * (3 - 2 * depth))[None, :, None]
    solid = pixels[..., 3] > 2 / 255
    rows, cols = np.flatnonzero(solid.any(axis=1)), np.flatnonzero(solid.any(axis=0))
    x0, x1, y0, y1 = int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1
    crops.append((x0, y0, pixels[y0:y1, x0:x1].copy()))
    if index == len(POP_TIMES):
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
    clear(made)

# Shelf-pack the tight crops, tallest first.
ATLAS_W = 2048
order = sorted(range(len(crops)), key=lambda i: -crops[i][2].shape[0])
placed, ax, ay, shelf = {}, 0, 0, 0
for i in order:
    h, w = crops[i][2].shape[:2]
    if ax + w > ATLAS_W:
        ax, ay, shelf = 0, ay + shelf + 2, 0
    placed[i] = (ax, ay)
    ax, shelf = ax + w + 2, max(shelf, h)
atlas = np.zeros((ay + shelf, ATLAS_W, 4), dtype=np.float32)
frames = []
for i, (x0, y0, crop) in enumerate(crops):
    px, py = placed[i]
    h, w = crop.shape[:2]
    atlas[py:py + h, px:px + w] = crop
    frames.append([px, py, w, h, VIEW_X0 + x0, VIEW_Y0 + y0])
used = np.flatnonzero(atlas[..., 3].any(axis=0))
atlas = atlas[:, :int(used[-1]) + 1]
rig.write_pixels(rig.HERE / "santa_moray.png", atlas)
(rig.HERE / "santa_moray.json").write_text(json.dumps({
    "frames": frames, "popTimes": POP_TIMES, "popBlendFrom": POP_BLEND_FROM,
    "idleFirst": len(POP_TIMES), "idleCount": IDLE_FRAMES, "idlePeriod": IDLE_PERIOD,
}, separators=(",", ":")) + "\n")
print("MORAY", len(frames), "frames, atlas", atlas.shape[1], "x", atlas.shape[0])
