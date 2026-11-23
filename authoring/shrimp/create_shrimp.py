"""Build the peppermint shrimp and render its walk and cleaning cycles.

    blender -b --factory-startup --python-exit-code 1 -P authoring/shrimp/create_shrimp.py

The shrimp (Lysmata wurdemanni: a glassy pink body ruled with fine red lines, a red tail fan,
long red feelers) is rebuilt for every frame from a pose: where each foot stands, where the
two pairs of picking arms reach, how the feelers, swimmerets and tail are held. Two looping
clips are rendered facing right, side on:

  walk    one stride. The feet stand still on the ground while the body passes over them, so
          the runtime advances the clip by distance walked ("travel" px a cycle), not by time.
  clean   standing with its head down, picking at the ground with one arm after the other
          and passing what it finds to its mouth.

The frames carry no shadow: a shrimp may be on sand or clinging to the edge of a coral, so the
runtime adds a shadow only on routes that ask for one.

Writes shrimp.blend (the first walk pose), shrimp.png (the frames in a grid) and shrimp.json
(frame size, the point on the ground under the body, and the clips).
Pass `-- --still walk:<phase>` or `clean:<phase>` to render one pose to _shrimp_still.png, four
times the size, for a close look at the model.
"""
import json
import math
import sys
from math import cos, sin
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "christmas"))
import rig
from rig import Graph, TAU

OUT = HERE / "shrimp.blend"
STILL = next((a for a in rig.script_args() if ":" in a), None) if "--still" in rig.script_args() else None
if not STILL:
    rig.guard(OUT)
scene = rig.reset(samples=160)

SIZE = 0.90                     # model units to units of 100 px: the body is about 95 px long
YAW = math.radians(9)           # turned a little toward the glass, so the far legs show
WALK_FRAMES, CLEAN_FRAMES, COLS = 12, 12, 6
STRIDE, DUTY, LIFT = 0.13, 0.62, 0.04

PALE, RED, LEG = (0.80, 0.27, 0.19), (0.50, 0.016, 0.01), (0.82, 0.22, 0.15)
FEELER, GLASS, FAN = (0.82, 0.17, 0.11), (0.95, 0.62, 0.52), (0.70, 0.04, 0.025)
ORGAN = (0.66, 0.27, 0.20)      # what shows through the glassy shell behind the head
NEAR, FAR = -1, 1               # which side of the body: toward the glass or away from it


def smooth(t):
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return a + (b - a) * t


# ---- poses -----------------------------------------------------------------------------
HIPS = {3: (0.20, 0.055, 0.185), 4: (0.15, 0.058, 0.185), 5: (0.10, 0.055, 0.190)}
FEET = {3: (0.33, 0.17), 4: (0.17, 0.21), 5: (0.00, 0.19)}
STEP = {5: 0.0, 4: 0.33, 3: 0.66}       # the stepping wave runs from the back legs forward


def walk_pose(phase):
    pose = {"bob": 0.004 * sin(TAU * 3 * phase), "pitch": math.radians(0.7) * sin(TAU * phase),
            "curl": math.radians(1.4) * sin(TAU * phase + 1.0), "feet": {}, "arm": {}, "claw": {},
            "chew": 0.012 * sin(TAU * 2 * phase), "paddle": 2 * phase,
            "feeler": {NEAR: math.radians(4) * sin(TAU * phase), FAR: math.radians(4) * sin(TAU * phase + 2.0)},
            "flick": math.radians(6) * sin(TAU * 2 * phase)}
    for side in (NEAR, FAR):
        for leg, (x0, y0) in FEET.items():
            p = (phase + STEP[leg] + (0.5 if side == FAR else 0.0)) % 1.0
            if p < DUTY:        # standing: the ground carries the foot back under the body
                x, z = x0 + STRIDE / 2 - STRIDE * p / DUTY, 0.0
            else:               # swinging forward for the next step
                q = (p - DUTY) / (1 - DUTY)
                x, z = x0 - STRIDE / 2 + STRIDE * smooth(q), LIFT * sin(math.pi * q)
            pose["feet"][side, leg] = Vector((x, side * y0, z))
        # The long arms feel the ground ahead, one then the other.
        a = TAU * (phase + (0.5 if side == FAR else 0.0))
        pose["arm"][side] = Vector((0.47 + 0.03 * cos(a), side * 0.10, 0.008 + 0.035 * max(0.0, sin(a))))
        pose["claw"][side] = Vector((0.40 + 0.008 * sin(a), side * 0.05, 0.13))
    return pose


def clean_pose(phase):
    pose = {"bob": -0.004, "pitch": math.radians(-5.5 + 1.0 * sin(TAU * phase)),
            "curl": math.radians(2.0 + 1.5 * sin(TAU * phase + 0.6)), "feet": {}, "arm": {}, "claw": {},
            "chew": 0.014 * sin(TAU * 3 * phase), "paddle": phase,
            "feeler": {NEAR: math.radians(7) * sin(TAU * phase), FAR: math.radians(7) * sin(TAU * phase + 2.4)},
            "flick": math.radians(8) * sin(TAU * 2 * phase)}
    for side in (NEAR, FAR):
        for leg, (x0, y0) in FEET.items():
            pose["feet"][side, leg] = Vector((x0, side * y0, 0.0))
        for part, ground, mouth, offset in (("arm", (0.50, 0.11, 0.0), (0.405, 0.035, 0.165), 0.0),
                                            ("claw", (0.41, 0.075, 0.0), (0.375, 0.03, 0.17), 0.25)):
            p = (phase + offset + (0.5 if side == FAR else 0.0)) % 1.0
            lift = 0.5 - 0.5 * cos(TAU * p)             # 0 picking at the ground, 1 at the mouth
            tip = Vector(ground).lerp(Vector(mouth), smooth(lift))
            tip.y *= side
            tip.z += 0.035 * sin(math.pi * lift)
            tip.x += 0.012 * sin(TAU * 3 * p) * (1 - lift)      # worrying at whatever it found
            pose[part][side] = tip
    return pose


# ---- geometry --------------------------------------------------------------------------
class Soup:
    """One mesh gathered from many parts, with named values on every vertex for the material."""
    NAMES = ("tint", "ink", "band", "u", "cv", "sv")

    def __init__(self):
        self.verts, self.faces = [], []
        self.attrs = {name: [] for name in self.NAMES}

    def add(self, verts, faces, **values):
        n = len(self.verts)
        self.verts += verts
        self.faces += [tuple(n + i for i in face) for face in faces]
        for name in self.NAMES:
            value = values.get(name, PALE if name == "tint" else 0.0)
            self.attrs[name] += value if isinstance(value, list) else [value] * len(verts)

    def build(self, name, mat):
        turn = Matrix.Rotation(YAW, 3, "Z") * SIZE
        obj = rig.add_mesh(scene, name, [tuple(turn @ Vector(v)) for v in self.verts], self.faces, [mat], smooth=True)
        for attr in self.NAMES:
            values = self.attrs[attr]
            if attr == "tint":
                layer = obj.data.attributes.new(attr, "FLOAT_COLOR", "POINT")
                layer.data.foreach_set("color", [c for t in values for c in (t[0], t[1], t[2], 1.0)])
            else:
                rig.point_attribute(obj, attr, values)
        return obj


def rings(values, sides):
    return [v for v in values for _ in range(sides)]


def tube(soup, points, radii, sides=10, tint=PALE, ink=0.0, band=0.0, u=(0.0, 1.0)):
    """A swept tube. tint and band may be one value or one per point along it."""
    verts, faces, uv = rig.sweep([Vector(p) for p in points], radii, sides)
    soup.add(verts, faces,
             tint=rings(tint, sides) if isinstance(tint, list) else tint,
             band=rings(band, sides) if isinstance(band, list) else band, ink=ink,
             u=[mix(u[0], u[1], a) for a, _ in uv], cv=[cos(TAU * b) for _, b in uv], sv=[sin(TAU * b) for _, b in uv])


def ball(soup, centre, radius, tint, sides=12, rows=7):
    points, radii = [], []
    for i in range(rows + 1):
        lat = math.pi * (0.03 + 0.94 * i / rows)
        points.append(Vector(centre) + Vector((-radius * cos(lat), 0, 0)))
        radii.append((radius * sin(lat),) * 2)
    tube(soup, points, radii, sides, tint)


def knee(hip, tip, upper, lower, pole):
    """Where a two-part limb bends, reaching from hip to tip with its elbow toward pole."""
    along = tip - hip
    d = min(max(along.length, abs(upper - lower) + 1e-3), upper + lower - 1e-3)
    along.normalize()
    x = (upper * upper - lower * lower + d * d) / (2 * d)
    out = (pole - along * pole.dot(along)).normalized()
    return hip + along * x + out * math.sqrt(max(0.0, upper * upper - x * x))


def limb(soup, hip, tip, upper, lower, pole, thick, tint=LEG, claw=0.0, toe=0.0):
    bend = knee(hip, tip, upper, lower, pole)
    points = [hip, hip.lerp(bend, 0.5), bend, bend.lerp(tip, 0.5), tip]
    radii = [thick, thick * 0.9, thick * 0.82, thick * 0.66, thick * 0.5]
    if toe:         # the last joint turns to stand on its point
        points[-1] = tip + (bend - tip).normalized() * toe + Vector((toe * 0.5, 0, 0))
        points.append(tip)
        radii.append(thick * 0.3)
    # Red at the joints, as on the real animal's banded legs.
    tints = [tuple(mix(a, b, k) for a, b in zip(tint, RED)) for k in (0.5, 0.0, 0.6, 0.0, 0.35, 0.5)[:len(points)]]
    tube(soup, points, [(r, r) for r in radii], 8, tints)
    if claw:
        heading = (tip - bend).normalized()
        tube(soup, [tip - heading * claw, tip + heading * claw * 0.6, tip + heading * claw * 1.9],
             [(claw * 0.5,) * 2, (claw * 0.62,) * 2, (claw * 0.12,) * 2], 8, tint)


def build(pose):
    for obj in [o for o in scene.objects if o.get("shrimp")]:
        bpy.data.meshes.remove(obj.data)
    shell, eyes, feelers = Soup(), Soup(), Soup()
    pivot = Vector((0.12, 0, 0.20))
    tilt = Matrix.Rotation(-pose["pitch"], 3, "Y")

    def body(x, y, z):
        """A point fixed to the body, where the pose puts it."""
        return pivot + tilt @ (Vector((x, y, z)) - pivot) + Vector((0, 0, pose["bob"]))

    # Carapace: (x, centre height, half height, half width), tail end first.
    hull = [(0.015, 0.268, 0.070, 0.052), (0.05, 0.268, 0.094, 0.067), (0.13, 0.266, 0.101, 0.072), (0.21, 0.266, 0.099, 0.070),
            (0.29, 0.270, 0.089, 0.062), (0.35, 0.276, 0.073, 0.050), (0.395, 0.282, 0.052, 0.036), (0.425, 0.287, 0.028, 0.020)]
    tube(shell, [body(x, 0, z) for x, z, _, _ in hull], [(w, h) for _, _, h, w in hull], 22,
         [PALE, PALE, ORGAN, ORGAN, PALE, PALE, PALE, PALE], ink=0.95, u=(0.45, 0.0))
    # Rostrum: the toothed blade over the eyes (the teeth are too small to show).
    spike = [(0.37, 0.340), (0.43, 0.352), (0.50, 0.360), (0.565, 0.372)]
    tube(shell, [body(x, 0, z) for x, z in spike], [(0.008, 0.016), (0.006, 0.012), (0.004, 0.008), (0.002, 0.003)], 8,
         tuple(mix(a, b, 0.5) for a, b in zip(PALE, RED)))

    # Abdomen: six rings, each overlapping the next, bending down past the hump of the third.
    lengths = [0.082, 0.080, 0.082, 0.076, 0.068, 0.074]
    droop = [-0.16, -0.06, 0.20, 0.38, 0.47, 0.44]         # radians below level, heading back
    high = [0.089, 0.087, 0.083, 0.073, 0.061, 0.048, 0.035]
    wide = [0.064, 0.062, 0.058, 0.050, 0.042, 0.034, 0.026]
    joints = [Vector((0.035, 0, 0.270))]
    for i, (length, angle) in enumerate(zip(lengths, droop)):
        a = angle + pose["curl"] * (i + 1)
        joints.append(joints[-1] + Vector((-cos(a), 0, -sin(a))) * length)
    for i in range(6):
        a, b = joints[i], joints[i + 1]
        points, radii = [], []
        for t, grow in ((0.0, 0.99), (0.3, 1.0), (0.75, 1.02), (1.0, 1.04), (1.03, 0.93)):
            points.append(body(*a.lerp(b, t)))
            radii.append((mix(wide[i], wide[i + 1], min(t, 1.0)) * grow, mix(high[i], high[i + 1], min(t, 1.0)) * grow))
        tube(shell, points, radii, 20, ink=0.9, band=[0.0, 0.0, 0.35, 0.6, 0.6], u=(0.5 + 0.08 * i, 0.58 + 0.08 * i))
        # A swimmeret under each of the first five rings, beating in a wave.
        if i < 5:
            swing = math.radians(-58 + 34 * sin(TAU * (pose["paddle"] - 0.16 * i)))
            for side in (NEAR, FAR):
                root = a.lerp(b, 0.45) + Vector((0, side * wide[i] * 0.45, -high[i] * 0.86))
                reach = Vector((sin(swing), 0, -cos(swing))) * 0.085
                tube(shell, [body(*root), body(*(root + reach * 0.5)), body(*(root + reach))],
                     [(0.006, 0.008), (0.007, 0.013), (0.003, 0.005)], 6, GLASS)

    # Tail fan: the telson between two pairs of blades, spread a little up and down as well.
    end, heading = joints[6], (joints[6] - joints[5]).normalized()
    across = Vector((0, 1, 0))
    rise = heading.cross(across)
    for yaw, pitch, length in ((0.0, 0.0, 0.20), (0.30, -0.16, 0.19), (-0.30, 0.16, 0.19), (0.62, -0.30, 0.16), (-0.62, 0.30, 0.16)):
        d = (heading + across * yaw + rise * pitch).normalized()
        blade = [body(*(end - heading * 0.01 + d * (length * t))) for t in (0.0, 0.35, 0.75, 1.0)]
        tube(shell, blade, [(0.020, 0.012), (0.034, 0.014), (0.028, 0.010), (0.005, 0.004)], 8,
             [PALE, FAN, FAN, tuple(c * 0.55 for c in FAN)])

    for side in (NEAR, FAR):
        # Eyes on short stalks.
        tube(shell, [body(0.365, side * 0.028, 0.288), body(0.385, side * 0.05, 0.296)], [(0.012,) * 2, (0.010,) * 2], 8, PALE)
        ball(eyes, body(0.392, side * 0.056, 0.298), 0.025, (0.012, 0.008, 0.008))

        # The long feelers: one swept forward and up, the other back over the body.
        base = body(0.395, side * 0.036, 0.262)
        curve = ([(0.07, -0.02, 0.03), (0.20, -0.06, 0.11), (0.36, -0.11, 0.20), (0.50, -0.16, 0.28), (0.62, -0.20, 0.33)] if side == NEAR else
                 [(0.07, 0.02, 0.05), (0.15, 0.06, 0.17), (0.14, 0.11, 0.29), (0.04, 0.15, 0.37), (-0.12, 0.18, 0.40)])
        sway = pose["feeler"][side]
        points = [base]
        for k, offset in enumerate(curve):
            bend = Matrix.Rotation(-sway * (k + 1) / len(curve), 3, "Y")
            points.append(base + tilt @ (bend @ Vector(offset)))
        path = rig.smooth_path(points, 6)
        tube(feelers, path, [(mix(0.0085, 0.0038, i / (len(path) - 1)),) * 2 for i in range(len(path))], 6, FEELER)
        # The blade beside each feeler's base.
        tube(shell, [body(0.385, side * 0.052, 0.262), body(0.46, side * 0.062, 0.268), body(0.525, side * 0.060, 0.272)],
             [(0.016, 0.006), (0.019, 0.005), (0.004, 0.002)], 8, GLASS)
        # The short forked feelers, flicking.
        root = body(0.425, side * 0.02, 0.288)
        for fork, (reach, lift) in enumerate(((0.30, 0.15), (0.27, -0.01))):
            turn = Matrix.Rotation(-(pose["flick"] if fork == 0 else -pose["flick"] * 0.6), 3, "Y")
            points = [root] + [root + tilt @ (turn @ Vector((reach * t, side * 0.05 * t, lift * t * t))) for t in (0.33, 0.66, 1.0)]
            path = rig.smooth_path(points, 5)
            tube(feelers, path, [(mix(0.007, 0.003, i / (len(path) - 1)),) * 2 for i in range(len(path))], 6, FEELER)

        # Mouth legs, working.
        chew = pose["chew"] * side
        tube(shell, [body(0.33, side * 0.03, 0.195), body(0.42, side * 0.035, 0.165 + chew * 0.5), body(0.485, side * 0.03, 0.185 + chew)],
             [(0.010,) * 2, (0.008,) * 2, (0.004,) * 2], 8, LEG)

        pole = Vector((0.0, side * 0.6, 1.0)).normalized()
        # The short clawed arms, then the long thin picking arms.
        limb(shell, body(0.29, side * 0.045, 0.19), pose["claw"][side], 0.095, 0.095, Vector((0.6, side * 0.4, -0.7)).normalized(), 0.010, claw=0.013)
        limb(shell, body(0.25, side * 0.05, 0.188), pose["arm"][side], 0.155, 0.175, Vector((0.5, side * 0.5, 0.7)).normalized(), 0.008, claw=0.009)
        # Three pairs of walking legs.
        for leg, (hx, hy, hz) in HIPS.items():
            limb(shell, body(hx, side * hy, hz), pose["feet"][side, leg], 0.165, 0.205, pole, 0.0105, toe=0.035)

    built = [shell.build("Peppermint shrimp", SHELL), eyes.build("Eyes", EYE), feelers.build("Feelers", SHELL)]
    for obj in built:
        obj["shrimp"] = True
    return built


# ---- materials -------------------------------------------------------------------------
SHELL = rig.material("Shell", PALE, 0.22, Coat_Weight=0.6, Subsurface_Weight=0.18)
g = Graph(SHELL)
value = lambda name: g.attribute(name).outputs["Fac"]
around = g.math("ARCTAN2", value("sv"), value("cv"))
# Fine red lines running the length of the body, slanting a little as they go.
lines = g.math("SINE", g.math("ADD", g.math("MULTIPLY", around, 12.0), g.math("MULTIPLY", value("u"), 26.0)))
red = g.math("MAXIMUM", value("band"), g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.4, 0.8, lines), value("ink")))
g.to("Base Color", g.mix(red, g.attribute("tint").outputs["Color"], RED))
g.to("Subsurface Radius", (0.9, 0.35, 0.25))
EYE = rig.material("Eye", (0.012, 0.008, 0.008), 0.08, Coat_Weight=1.0)

# ---- stage -----------------------------------------------------------------------------
# Lit from nearly overhead by a broad light, as a tank is.
sun = rig.tank_light(scene)
sun.rotation_euler = (math.radians(17), math.radians(-7), math.radians(-18))
sun.data.angle = math.radians(55)
cam = rig.camera(scene, elevation=9)
# Every frame shares one framing: a box round the farthest any pose reaches.
x0, x1, y0, top = -0.62 * SIZE, 1.13 * SIZE, 0.27 * SIZE, 0.76 * SIZE
box = rig.add_mesh(scene, "Frame", [(x, y, z) for x in (x0, x1) for y in (-y0, y0) for z in (0, top)], [])
box.hide_render = True
px = rig.PX * (4 if STILL else 1)
w, h = rig.frame(scene, cam, [box], pad=(3, 3, 3, 3), px=px)
anchor = rig.project(scene, cam, Matrix.Rotation(YAW, 3, "Z") @ Vector((0.15 * SIZE, 0, 0)), px=px)

if STILL:
    clip, phase = STILL.split(":")
    build(walk_pose(float(phase)) if clip == "walk" else clean_pose(float(phase)))
    rig.render(scene, HERE / "_shrimp_still.png")
    print("SHRIMP still", w, "x", h, "anchor", anchor)
else:
    build(walk_pose(0.0))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
    paths = []
    poses = [walk_pose(i / WALK_FRAMES) for i in range(WALK_FRAMES)] + [clean_pose(i / CLEAN_FRAMES) for i in range(CLEAN_FRAMES)]
    for i, pose in enumerate(poses):
        build(pose)
        paths.append(HERE / f"_frame_{i:02d}.png")
        rig.render(scene, paths[-1])
        # Nothing may reach the edge of the shared frame.
        alpha = rig.read_pixels(paths[-1])[..., 3]
        if max(alpha[0].max(), alpha[-1].max(), alpha[:, 0].max(), alpha[:, -1].max()) > 0:
            raise ValueError(f"Frame {i} runs off the edge of the picture")
    rig.pack_grid(paths, HERE / "shrimp.png", COLS)
    info = {"w": w, "h": h, "cols": COLS, "anchor": [round(v, 1) for v in anchor],
            "walk": {"first": 0, "count": WALK_FRAMES, "travel": round(STRIDE / DUTY * SIZE * rig.PX, 1)},
            "clean": {"first": WALK_FRAMES, "count": CLEAN_FRAMES, "period": 1.7}}
    (HERE / "shrimp.json").write_text(json.dumps(info, separators=(",", ":")) + "\n")
    print("SHRIMP", w, "x", h, "frames", len(poses), "anchor", info["anchor"], "travel", info["walk"]["travel"])
