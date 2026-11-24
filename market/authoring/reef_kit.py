"""Corals and rock for the store edition's rendered reef.

Everything is built in Blender units where one unit is 100 tank pixels, like the models in
authoring/christmas, whose camera and lighting helpers (rig.py) this uses. A coral is grown at
a point on the rock along an axis; its vertices carry two colours and a 0 to 1 value ("tip":
0 at the root or centre, 1 at the growing edge) that the materials read.
"""
import math
import random
import sys
from math import cos, sin
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "authoring/christmas"))
import rig  # noqa: E402
from rig import Graph, TAU  # noqa: E402

UP = Vector((0, 0, 1))
rng = random.Random(7)


def seed(value):
    rng.seed(value)


# ---- geometry helpers ------------------------------------------------------------------

class Soup:
    """One mesh gathered from many parts, with per-vertex colours (tint, core) and tip."""

    def __init__(self, name):
        self.name = name
        self.verts, self.faces, self.tint, self.core, self.tip = [], [], [], [], []

    def add(self, verts, faces, tint, tip, core=None):
        n = len(self.verts)
        self.verts += [tuple(v) for v in verts]
        self.faces += [tuple(n + i for i in face) for face in faces]
        self.tint += tint if isinstance(tint, list) else [tint] * len(verts)
        core = tint if core is None else core
        self.core += core if isinstance(core, list) else [core] * len(verts)
        self.tip += tip if isinstance(tip, list) else [tip] * len(verts)

    def build(self, scene, mat):
        if not self.verts:
            return None
        obj = rig.add_mesh(scene, self.name, self.verts, self.faces, [mat], smooth=True)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        for name, values in (("tint", self.tint), ("core", self.core)):
            attr = obj.data.attributes.new(name, "FLOAT_COLOR", "POINT")
            attr.data.foreach_set("color", [c for t in values for c in (t[0], t[1], t[2], 1.0)])
        rig.point_attribute(obj, "tip", self.tip)
        return obj


def perp(v):
    while True:
        r = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
        r -= v * r.dot(v)
        if r.length > 1e-3:
            return r.normalized()


def frame_of(axis):
    ref = UP if abs(axis.z) < 0.92 else Vector((1, 0, 0))
    a = axis.cross(ref).normalized()
    return a, axis.cross(a).normalized()


def lean(axis, side, angle):
    return (axis * cos(angle) + side * sin(angle)).normalized()


def shade(color, k):
    return tuple(min(1.0, c * k) for c in color)


def blend(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def revolve(origin, axis, profile, sides, bend=None, cap=True):
    a, b = frame_of(axis)
    verts, faces = [], []
    for i, (h, r) in enumerate(profile):
        c = origin + axis * h
        if bend:
            c = c + bend[0] * (bend[1] * h * h)
        for k in range(sides):
            ang = TAU * k / sides
            verts.append(c + a * (r * cos(ang)) + b * (r * sin(ang)))
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    if cap:
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple(range((len(profile) - 1) * sides, len(profile) * sides)))
    return verts, faces


def limb(soup, p, d, length, r0, r1, tint, t0, t1, bend=0.2, lift=0.06, sides=8, rounded=False, n=4, core=None):
    pts, cur, dirv = [p], p, d
    for _ in range(n):
        dirv = (dirv + perp(dirv) * (bend * rng.random()) + UP * lift).normalized()
        cur = cur + dirv * (length / n)
        pts.append(cur)
    radii = [r0 + (r1 - r0) * i / n for i in range(n + 1)]
    tips = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    if rounded:
        for step, k in ((0.75, 0.84), (1.3, 0.55), (1.62, 0.2)):
            pts.append(cur + dirv * (r1 * step))
            radii.append(r1 * k)
            tips.append(t1)
    verts, faces, _ = rig.sweep(pts, [(r, r) for r in radii], sides)
    soup.add(verts, faces, tint, [t for t in tips for _ in range(sides)], core)
    return cur, dirv


# ---- corals ----------------------------------------------------------------------------

def branching(soup, p, axis, s, tint, levels=4, trunks=4, kids=(2, 3), spread=(0.35, 0.75), thick=0.06,
              taper=0.76, reach=0.34, decay=0.78, bend=0.2, lift=0.08, sides=8, core=None):
    """Staghorn, bush and bird's-nest corals: trunks that fork again and again."""
    def grow(p, d, length, r, level):
        last = level == levels - 1
        end, dirv = limb(soup, p, d, length, r, r * (0.86 if last else taper), tint, level / levels,
                         (level + 1) / levels, bend, lift, sides, rounded=last, core=core)
        if last:
            return
        side0 = perp(dirv)
        side1 = dirv.cross(side0)
        phase = rng.uniform(0, TAU)
        count = rng.randint(*kids)
        for j in range(count):
            ang = phase + TAU * j / count + rng.uniform(-0.5, 0.5)
            fork = lean(dirv, side0 * cos(ang) + side1 * sin(ang), rng.uniform(*spread))
            grow(end - dirv * (r * 0.4), fork, length * decay * rng.uniform(0.8, 1.15), r * taper, level + 1)

    side0 = perp(axis)
    side1 = axis.cross(side0)
    phase = rng.uniform(0, TAU)
    for j in range(trunks):
        ang = phase + TAU * j / trunks
        start = lean(axis, side0 * cos(ang) + side1 * sin(ang), rng.uniform(0.2, 0.75) if trunks > 1 else 0.0)
        grow(p, start, s * reach * rng.uniform(0.85, 1.1), s * thick, 0)


def staghorn(soup, p, axis, s, tint, core=None):
    branching(soup, p, axis, s, tint, levels=4, trunks=5, spread=(0.3, 0.7), thick=0.055, reach=0.36, lift=0.12, core=core)


def bush(soup, p, axis, s, tint, core=None):
    """A rounded head of short stubby fingers."""
    branching(soup, p, axis, s * 0.8, tint, levels=3, trunks=11, kids=(2, 3), spread=(0.25, 0.55), thick=0.07,
              taper=0.84, reach=0.33, decay=0.72, bend=0.1, lift=0.03, core=core)


def birdsnest(soup, p, axis, s, tint, core=None):
    """A thicket of needle-thin branches."""
    branching(soup, p, axis, s * 0.85, tint, levels=5, trunks=6, kids=(2, 3), spread=(0.4, 0.9), thick=0.028,
              taper=0.78, reach=0.26, decay=0.8, bend=0.3, lift=0.04, sides=6, core=core)


def table(soups, p, axis, s, tint, core=None):
    """A table coral: a ruffled plate on a short stalk, its top crowded with branchlets."""
    soup = soups["plate"]
    ax = (axis * 0.35 + UP).normalized()
    end, _ = limb(soup, p, axis, s * 0.36, s * 0.10, s * 0.15, shade(tint, 0.7), 0.0, 0.3, bend=0.05, lift=0.25)
    a, b = frame_of(ax)
    radius, rings, sides = s * 0.7, 10, 56
    ph1, ph2 = rng.uniform(0, TAU), rng.uniform(0, TAU)

    def at(rho, phi, under=False):
        rr = radius * rho * (1 + 0.12 * sin(3 * phi + ph1) + 0.07 * sin(7 * phi + ph2))
        h = s * (0.09 * rho * rho + 0.022 * sin(9 * phi + ph1) * rho ** 3)
        if under:
            h -= s * (0.018 + 0.07 * (1 - rho * rho))
        return end + a * (rr * cos(phi)) + b * (rr * sin(phi)) + ax * h

    profile = [(0.04 + 0.96 * i / rings, False) for i in range(rings + 1)] + [(1 - 0.96 * i / rings, True) for i in range(1, rings + 1)]
    verts, faces, tips = [], [], []
    for i, (rho, under) in enumerate(profile):
        for k in range(sides):
            verts.append(at(rho, TAU * k / sides, under))
            tips.append(0.25 * rho if under else rho)
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    faces.append(tuple(range(sides)))
    soup.add(verts, faces, tint, tips, core)
    for _ in range(int(190 * min(1.6, s))):
        base = at(math.sqrt(rng.random()) * 0.95, rng.uniform(0, TAU))
        limb(soups["branch"], base - ax * (s * 0.01), lean(ax, perp(ax), rng.uniform(0, 0.4)), s * rng.uniform(0.04, 0.10),
             s * 0.016, s * 0.012, tint, 0.7, 1.0, bend=0.0, lift=0.0, sides=6, rounded=True, n=1, core=core)


def plating(soup, p, axis, s, tint, core=None):
    """Plating montipora: whorls of thin scrolled plates, pale at the growing rim."""
    ax = (axis + UP * 0.25).normalized()
    a, b = frame_of(ax)
    n = 12
    for scale, leaves, flare in ((1.0, rng.randint(3, 4), 1.0), (0.6, 3, 0.7)):
        phase = rng.uniform(0, TAU)
        for j in range(leaves):
            base = phase + TAU * j / leaves
            wide, tall, ph = rng.uniform(1.0, 1.45), rng.uniform(0.12, 0.34), rng.uniform(0, TAU)
            verts, faces, tips = [], [], []
            for it in range(n + 1):
                for ia in range(n + 1):
                    aa = -1 + 2 * ia / n
                    t = (it / n) * (1 - 0.32 * aa ** 4)
                    ang = base + aa * wide
                    radial = a * cos(ang) + b * sin(ang)
                    out = s * scale * 0.62 * flare * t ** 0.8
                    rise = s * scale * (0.42 * tall * t ** 1.5 + 0.03 * sin(aa * 4 + ph) * t * t + 0.1 * (1 - flare))
                    verts.append(p + radial * (out + s * 0.03) + ax * rise)
                    tips.append(t)
                    if it and ia:
                        k = it * (n + 1) + ia
                        faces.append((k - n - 2, k - n - 1, k, k - 1))
            soup.add(verts, faces, shade(tint, rng.uniform(0.88, 1.08)), tips, core)


def dome(soup, p, axis, s, tint, core=None):
    """A brain or star coral: a lumpy dome. Its pattern is in the material."""
    ax = (axis + UP * 0.5).normalized()
    a, b = frame_of(ax)
    radius, rings, sides = s * 0.5, 12, 32
    ph = rng.uniform(0, TAU)
    centre = p + ax * (s * 0.08)
    verts, faces = [], []
    for i in range(rings + 1):
        lat = 0.03 + 1.75 * i / rings
        for k in range(sides):
            phi = TAU * k / sides
            rr = radius * sin(lat) * (1 + 0.09 * sin(3 * phi + ph) * sin(2 * lat + 1) + 0.05 * sin(5 * phi - ph))
            verts.append(centre + a * (rr * cos(phi)) + b * (rr * sin(phi)) + ax * (radius * 0.8 * cos(lat)))
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    faces.append(tuple(range(sides)))
    soup.add(verts, faces, tint, 0.5, core)


def polyp_mat(soup, p, axis, s, tint, core, size=0.05, crowd=1.0):
    """Zoanthids or mushrooms: a low mound crowded with flat discs, each a ring of one colour
    round a centre of another."""
    a, b = frame_of(axis)
    radius = s * 0.5
    placed = []
    for _ in range(int(2600 * crowd)):
        rho, phi = math.sqrt(rng.random()) * radius, rng.uniform(0, TAU)
        r = size * rng.uniform(0.75, 1.2)
        spot = (rho * cos(phi), rho * sin(phi))
        if any((spot[0] - q[0]) ** 2 + (spot[1] - q[1]) ** 2 < (0.82 * (r + q[2])) ** 2 for q in placed):
            continue
        placed.append((spot[0], spot[1], r))
        height = s * 0.16 * (1 - (rho / radius) ** 2) + r * rng.uniform(0.5, 1.1)
        root = p + a * spot[0] + b * spot[1]
        face = lean(axis, a * cos(phi) + b * sin(phi), 0.5 * rho / radius + rng.uniform(-0.15, 0.15))
        profile = [(0, r * 0.45), (height * 0.8, r * 0.5), (height, r), (height + r * 0.12, r * 0.94), (height + r * 0.1, r * 0.55),
                   (height + r * 0.03, r * 0.2), (height + r * 0.09, r * 0.02)]
        verts, faces = revolve(root, face, profile, 10)
        tips = [t for t in (1.0, 1.0, 1.0, 0.9, 0.55, 0.2, 0.0) for _ in range(10)]
        soup.add(verts, faces, shade(tint, rng.uniform(0.85, 1.1)), tips, core)


def sea_fan(soup, p, axis, s, tint):
    """A gorgonian: a flat lace of thin branches, turned to face the glass."""
    ax = Vector((axis.x, 0, axis.z))
    ax = ((ax.normalized() if ax.length > 0.2 else UP) + UP * 0.7).normalized()
    side = Vector((ax.z, 0, -ax.x))
    levels = 6

    def grow(p, ang, length, r, level):
        d = ax * cos(ang) + side * sin(ang)
        across = Vector((d.z, 0, -d.x))
        last = level == levels - 1
        end = p + d * length
        pts = [p, p + d * (length * 0.5) + across * (length * 0.07 * rng.uniform(-1, 1)), end]
        radii = [r, r * 0.9, r * 0.8]
        if last:
            pts.append(end + d * (r * 1.1))
            radii.append(r * 0.3)
        verts, faces, _ = rig.sweep(pts, [(q, q) for q in radii], 6)
        tips = [(level + i / 2) / levels for i in range(3)] + ([1.0] if last else [])
        soup.add(verts, faces, tint, [t for t in tips for _ in range(6)])
        if last:
            return
        for sign in [-1, 1] + ([0] if rng.random() < 0.3 else []):
            grow(end - d * (r * 0.5), ang + sign * rng.uniform(0.3, 0.6) + rng.uniform(-0.1, 0.1), length * rng.uniform(0.68, 0.86), r * 0.78, level + 1)

    grow(p, 0.0, s * 0.3, s * 0.03, 0)


def folded_brain(soup, p, axis, radius, tint, core):
    """A large brain coral: a dome whose whole surface is folded into fat winding ridges with
    grooves between them. The folds are real, cut into the mesh, so they catch the light."""
    ax = (axis + UP * 0.6).normalized()
    a, b = frame_of(ax)
    rings, sides = max(60, int(radius * 96)), max(120, int(radius * 192))
    fold, depth, bands = radius * 0.42, radius * 0.06, 4.6
    drift = Vector((rng.uniform(0, 40), rng.uniform(0, 40), rng.uniform(0, 40)))
    ph = rng.uniform(0, TAU)
    verts, faces, tips = [], [], []
    for i in range(rings + 1):
        lat = 0.02 + 1.74 * i / rings
        for k in range(sides):
            phi = TAU * k / sides
            lump = 1 + 0.07 * sin(3 * phi + ph) * sin(2 * lat + 1) + 0.05 * sin(5 * phi - ph)
            out = a * (cos(phi) * sin(lat)) + b * (sin(phi) * sin(lat)) + ax * (0.82 * cos(lat))
            pos = out * (radius * lump)
            # Grooves follow the level lines of a smooth field: closed, evenly spaced, wandering.
            q = pos / fold + drift
            field = noise.noise(q) + 0.18 * noise.noise(q * 2.3 + drift)
            ridge = min(1.0, abs(sin(math.pi * bands * field)) / 0.55)
            ridge = ridge * ridge * (3 - 2 * ridge)
            verts.append(p + pos - out.normalized() * (depth * (1 - ridge)))
            tips.append(ridge)
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    faces.append(tuple(range(sides)))
    soup.add(verts, faces, tint, tips, core)


def great_fan(soup, p, axis, s, tint, levels=11):
    """A large sea fan: one flat, close net of fine branches on a short stalk, broad as it is
    tall, facing the glass."""
    ax = Vector((axis.x, 0, axis.z))
    ax = ((ax.normalized() if ax.length > 0.2 else UP) + UP * 1.2).normalized()
    side = Vector((ax.z, 0, -ax.x))
    reach = s * 0.92

    def grow(p, ang, length, r, level):
        ang = max(-1.25, min(1.25, ang))
        d = ax * cos(ang) + side * sin(ang)
        across = Vector((d.z, 0, -d.x))
        end = p + d * length
        # The net stops at the fan's rounded outline.
        last = level == levels - 1 or (end - root).length > reach * (1 - 0.18 * abs(ang))
        pts = [p, p + d * (length * 0.5) + across * (length * 0.1 * rng.uniform(-1, 1)), end]
        radii = [r, r * 0.93, r * 0.86]
        if last:
            pts.append(end + d * (r * 1.2))
            radii.append(r * 0.3)
        verts, faces, _ = rig.sweep(pts, [(q, q * 0.8) for q in radii], 5)
        tips = [min(1.0, (p - root).length / reach), min(1.0, (pts[1] - root).length / reach), min(1.0, (end - root).length / reach)] + ([1.0] if last else [])
        soup.add(verts, faces, tint, [t for t in tips for _ in range(5)])
        if last:
            return
        turns = [-rng.uniform(0.16, 0.36), rng.uniform(0.16, 0.36)]
        if level < 3 or rng.random() < 0.3:
            turns.append(rng.uniform(-0.07, 0.07))
        for turn in turns:
            grow(end - d * (r * 0.4), ang + turn, length * rng.uniform(0.8, 0.94), max(0.0065, r * 0.84), level + 1)

    root = p + ax * (s * 0.07)
    stalk, _, _ = rig.sweep([p, root], [(s * 0.03, s * 0.026), (s * 0.026, s * 0.022)], 6)
    soup.add(stalk, [(i, (i + 1) % 6, 6 + (i + 1) % 6, 6 + i) for i in range(6)], shade(tint, 0.7), 0.0)
    for start in (-0.75, -0.38, 0.0, 0.38, 0.75):
        grow(root, start + rng.uniform(-0.08, 0.08), s * 0.13, s * 0.02, 0)


def cup(soup, p, axis, s, tint, rim):
    """A cup or lettuce coral: a few broad plates scrolled upward, ruffled at the rim, running
    to another colour at the edge."""
    ax = (axis + UP * 0.6).normalized()
    a, b = frame_of(ax)
    n = 18
    for scale, leaves, flare in ((1.0, 7, 1.0), (0.64, 5, 0.86), (0.34, 4, 0.7)):
        phase = rng.uniform(0, TAU)
        for j in range(leaves):
            base = phase + TAU * j / leaves + rng.uniform(-0.15, 0.15)
            wide, tall, ph = rng.uniform(0.95, 1.25), rng.uniform(0.9, 1.2), rng.uniform(0, TAU)
            verts, faces, tips = [], [], []
            for it in range(n + 1):
                for ia in range(n + 1):
                    aa = -1 + 2 * ia / n
                    t = (it / n) * (1 - 0.3 * aa ** 4)
                    ang = base + aa * wide
                    radial = a * cos(ang) + b * sin(ang)
                    out = s * scale * flare * (0.42 * t ** 0.7 + 0.12 * t ** 4)
                    rise = s * scale * (0.5 * tall * t ** 1.35 + (0.045 * sin(aa * 5 + ph) + 0.02 * sin(aa * 9 - ph)) * t ** 2.5 - 0.04 * t ** 6)
                    verts.append(p + radial * (out + s * 0.03) + ax * rise)
                    tips.append(t)
                    if it and ia:
                        k = it * (n + 1) + ia
                        faces.append((k - n - 2, k - n - 1, k, k - 1))
            soup.add(verts, faces, shade(tint, rng.uniform(0.9, 1.06)), tips, rim)


def antler(soup, p, axis, s, tint, core=None):
    """A tall open coral of long, sparsely forked branches, like antlers."""
    branching(soup, p, axis, s, tint, levels=5, trunks=5, kids=(2, 3), spread=(0.3, 0.62), thick=0.04,
              taper=0.8, reach=0.3, decay=0.8, bend=0.18, lift=0.14, core=core)


# ---- materials -------------------------------------------------------------------------

def coral_material(name, pattern="polyps", scale=30.0, pale=0.3, roughness=0.5, bump=0.5, glow=0.05, **inputs):
    """Tint darkens toward the root and pales toward the growing edge; glow is the share of
    its colour a coral gives off, as corals fluoresce under a reef tank's blue light."""
    mat = rig.material(name, (0.5, 0.5, 0.5), roughness, **inputs)
    g = Graph(mat)
    tint = g.attribute("tint").outputs["Color"]
    core = g.attribute("core").outputs["Color"]
    tip = g.attribute("tip").outputs["Fac"]
    where = g.coords()
    if pattern == "relief":         # folded ridges: one colour on the crests, another in the grooves
        color = g.mix(g.math("SMOOTHSTEP", 0.1, 0.85, tip), core, tint)
        relief = g.math("ADD", tip, g.math("MULTIPLY", g.noise(where, scale=scale, detail=2).outputs["Fac"], 0.2))
    elif pattern == "cup":          # plates with growth lines, running to the other colour at the rim
        lines = g.math("SINE", g.math("MULTIPLY", tip, scale))
        grain = g.noise(where, scale=24, detail=3).outputs["Fac"]
        relief = g.math("ADD", g.math("MULTIPLY", lines, 0.4), grain)
        color = g.mix(g.math("SMOOTHSTEP", 0.2, 1.0, lines), tint, (0.84, 0.84, 0.84), "MULTIPLY")
        streak = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(where, scale=10, detail=2).outputs["Fac"], 0.5), 0.14)
        color = g.mix(g.math("SMOOTHSTEP", 0.82, 1.0, g.math("ADD", tip, streak)), color, core)
    elif pattern == "discs":        # zoanthids: centre, a dark band, then the skirt
        color = g.mix(g.math("SMOOTHSTEP", 0.28, 0.4, tip), core, g.mix(1.0, core, (0.22, 0.2, 0.3), "MULTIPLY"))
        color = g.mix(g.math("SMOOTHSTEP", 0.5, 0.66, tip), color, tint)
        relief = g.noise(where, scale=60, detail=2).outputs["Fac"]
    else:
        # The oldest part of a colony is bare skeleton, bone white where it is clean and
        # crusted pink and purple with coralline algae where it is not.
        growth = g.noise(where, scale=3.2, detail=3, roughness=0.6).outputs["Fac"]
        crust = g.ramp(growth, [(0.36, (0.74, 0.71, 0.66)), (0.5, (0.50, 0.17, 0.28)), (0.64, (0.28, 0.10, 0.33))]).outputs["Color"]
        color = g.mix(g.math("SMOOTHSTEP", 0.34, 0.06, tip), tint, crust)
        color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.72, 1.0, tip), pale), color, core)
    if pattern == "polyps":
        cells = g.node("ShaderNodeTexVoronoi", feature="F1")
        cells.inputs["Scale"].default_value = scale
        g.set(cells.inputs["Vector"], where)
        relief = g.math("SMOOTHSTEP", 0.42, 0.12, cells.outputs["Distance"])
        color = g.mix(g.math("MULTIPLY", relief, 0.10), color, (1.0, 0.97, 0.9))
    elif pattern == "brain":        # winding ridges in one colour, valleys in the other
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", wave_profile="SIN")
        wave.inputs["Scale"].default_value = scale
        wave.inputs["Distortion"].default_value = 7.0
        wave.inputs["Detail"].default_value = 2.0
        wave.inputs["Detail Scale"].default_value = 1.3
        g.set(wave.inputs["Vector"], where)
        relief = g.math("SMOOTHSTEP", 0.25, 0.75, wave.outputs["Fac"])
        color = g.mix(relief, core, tint)
    elif pattern == "stars":        # star coral: round cups, each with a centre of the other colour
        cells = g.node("ShaderNodeTexVoronoi", feature="F1")
        cells.inputs["Scale"].default_value = scale
        g.set(cells.inputs["Vector"], where)
        relief = g.math("SMOOTHSTEP", 0.18, 0.42, cells.outputs["Distance"])
        color = g.mix(relief, core, tint)
    elif pattern == "rings":        # growth lines following a plate's edge
        lines = g.math("SINE", g.math("MULTIPLY", tip, scale))
        grain = g.noise(where, scale=26, detail=3).outputs["Fac"]
        relief = g.math("ADD", g.math("MULTIPLY", lines, 0.5), grain)
        color = g.mix(g.math("SMOOTHSTEP", 0.2, 1.0, lines), color, (0.82, 0.82, 0.82), "MULTIPLY")
        color = g.mix(g.math("SMOOTHSTEP", 0.93, 1.0, tip), color, core)
    g.to("Base Color", color)
    g.to("Emission Color", color)
    g.to("Emission Strength", glow)
    g.bump(relief, strength=bump, distance=0.014)
    return mat


def rock_material():
    """Reef rock: bone-white porous limestone, most of it crusted with coralline algae in
    pink, purple and maroon, with a film of green in places. The crust is what gives a
    healthy tank its colour."""
    mat = rig.material("Reef rock", (0.3, 0.25, 0.3), 0.92)
    g = Graph(mat)
    where = g.coords()
    grain = g.noise(where, scale=5, detail=7, roughness=0.68).outputs["Fac"]
    crust = g.noise(where, scale=2.3, detail=5, roughness=0.65, distortion=0.6).outputs["Fac"]
    film = g.noise(where, scale=2.2, detail=3, roughness=0.5, w=3.0, dims="4D").outputs["Fac"]
    pits = g.node("ShaderNodeTexVoronoi", feature="F1")
    pits.inputs["Scale"].default_value = 17.0
    g.set(pits.inputs["Vector"], g.mix(0.3, where, g.noise(where, scale=3.0, detail=2).outputs["Color"]))
    sparse = g.noise(where, scale=2.4, detail=2, w=7.0, dims="4D").outputs["Fac"]
    pit = g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.16, 0.03, pits.outputs["Distance"]), g.math("SMOOTHSTEP", 0.42, 0.6, sparse))
    stone = g.ramp(grain, [(0.25, (0.34, 0.32, 0.30)), (0.5, (0.64, 0.61, 0.56)), (0.8, (0.88, 0.86, 0.80))]).outputs["Color"]
    shade_of = g.noise(where, scale=2.1, detail=3, roughness=0.55, w=11.0, dims="4D").outputs["Fac"]
    algae = g.ramp(shade_of, [(0.30, (0.26, 0.035, 0.07)), (0.44, (0.52, 0.16, 0.27)), (0.58, (0.30, 0.10, 0.34)), (0.72, (0.13, 0.045, 0.21))]).outputs["Color"]
    color = g.mix(g.math("SMOOTHSTEP", 0.40, 0.47, crust), stone, algae)
    color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.62, 0.74, film), 0.75), color, (0.10, 0.34, 0.14))
    color = g.mix(pit, color, (0.02, 0.015, 0.03))
    # Hollows hold shadow and silt; the knobs that stand proud are scoured pale.
    shape = g.node("ShaderNodeNewGeometry").outputs["Pointiness"]
    color = g.mix(g.math("SMOOTHSTEP", 0.50, 0.38, shape), color, (0.30, 0.24, 0.34), "MULTIPLY")
    color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.54, 0.62, shape), 0.45), color, (0.86, 0.82, 0.78))
    # Inside a cave (hollow() marks it) almost no light comes back out.
    color = g.mix(g.attribute("dark").outputs["Fac"], color, (0.004, 0.004, 0.01))
    g.to("Base Color", color)
    height = g.math("SUBTRACT", grain, g.math("MULTIPLY", pit, 1.6))
    g.bump(height, strength=1.0, distance=0.08)
    return mat


def materials():
    return {
        "branch": coral_material("Branching coral", "polyps", scale=34, pale=0.85, Coat_Weight=0.1, Sheen_Weight=0.3),
        "plate": coral_material("Table coral", "polyps", scale=40, pale=0.8, Coat_Weight=0.1),
        "plating": coral_material("Plating coral", "rings", scale=46, pale=0.0, roughness=0.55, bump=0.4),
        "brain": coral_material("Brain coral", "brain", scale=19, pale=0.0, roughness=0.55, bump=0.9, glow=0.09),
        "stars": coral_material("Star coral", "stars", scale=21, pale=0.0, roughness=0.55, bump=0.8, glow=0.09),
        "discs": coral_material("Zoanthids", "discs", pale=0.0, roughness=0.4, bump=0.2, glow=0.14, Coat_Weight=0.4),
        "fan": coral_material("Sea fan", "polyps", scale=50, pale=0.2, roughness=0.6, bump=0.3),
        "relief": coral_material("Folded brain coral", "relief", scale=70, roughness=0.5, bump=1.0),
        "cup": coral_material("Cup coral", "cup", scale=40, roughness=0.5, bump=0.4),
    }


def new_soups():
    return {name: Soup(label) for name, label in (
        ("branch", "Branching corals"), ("plate", "Table corals"), ("plating", "Plating corals"), ("brain", "Brain corals"),
        ("stars", "Star corals"), ("discs", "Zoanthids and mushrooms"), ("fan", "Sea fans"), ("relief", "Folded brain corals"),
        ("cup", "Cup corals"))}


# ---- rock ------------------------------------------------------------------------------

def rock(scene, name, blobs, holes=(), resolution=0.11, seed_value=0.0):
    """Reef rock from overlapping blobs (x, y, z, radius) with holes cut by others, roughened.
    Returns the mesh object."""
    balls = bpy.data.metaballs.new(name)
    balls.resolution = balls.render_resolution = resolution
    balls.threshold = 0.6
    for group, negative in ((blobs, False), (holes, True)):
        for x, y, z, r in group:
            ball = balls.elements.new(type="BALL")
            ball.co, ball.radius, ball.use_negative = (x, y, z), r, negative
    source = bpy.data.objects.new(name + " blobs", balls)
    scene.collection.objects.link(source)
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(source.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(source)
    bpy.data.metaballs.remove(balls)
    # Break up the blobs' roundness: broad lumps, then knobs and hollows.
    # The blobs come as loose patches that share positions but not vertices. Weld them first,
    # or every seam tears open when its two sides are pushed along different normals.
    skin = bmesh.new()
    skin.from_mesh(mesh)
    bmesh.ops.remove_doubles(skin, verts=skin.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(skin, faces=skin.faces)
    skin.normal_update()
    for v in skin.verts:
        p = v.co.copy()
        lump = noise.noise(Vector((p.x * 0.55 + seed_value, p.y * 0.55, p.z * 0.55))) * 0.34
        knob = noise.noise(Vector((p.x * 1.5, p.y * 1.5 + seed_value, p.z * 1.5))) * 0.2
        grit = noise.noise(Vector((p.x * 4.2, p.y * 4.2, p.z * 4.2 + seed_value))) * 0.06
        cave = noise.voronoi(Vector((p.x * 1.15, p.y * 1.15, p.z * 1.15 + seed_value)))[0][0]
        cell = noise.voronoi(Vector((p.x * 2.9, p.y * 2.9, p.z * 2.9 + seed_value)))[0][0]
        v.co = p + v.normal * max(-0.16, lump + knob + grit - 0.16 * (max(0.0, 0.3 - cave) / 0.3) ** 2 - 0.09 * (max(0.0, 0.28 - cell) / 0.28) ** 2)
    skin.to_mesh(mesh)
    skin.free()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def hollow(stone, start, end, depth, height, seed_value=0.0):
    """Press a cave into the front of a rock: a rough hollow lying along x from `start` (its
    closed end) to `end`, open to the glass along its length. start and end are (x, z); the
    hollow follows the rock's front face, reaching `depth` into it, and is `height` tall.
    Every vertex inside the hollow is moved straight back onto its far wall, and marked
    "dark" for the rock material by how far it went."""
    (x0, z0), (x1, z1) = start, end
    steps = max(8, int(abs(x1 - x0) / 0.2))
    stations, face = [], None
    for i in range(steps + 1):
        t = i / steps
        x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
        hit, at, _, _ = stone.ray_cast(Vector((x, -40, z)), Vector((0, 1, 0)))
        face = at.y if hit else face
        wobble = noise.noise(Vector((x * 1.9 + seed_value, 3.1, z)))
        grow = min(1.0, 0.3 + 2.4 * t)                  # narrow at the closed end
        stations.append((face, z + 0.08 * wobble, depth * grow * (1 + 0.15 * wobble), height / 2 * grow * (1 - 0.12 * wobble)))
    first = next(station[0] for station in stations if station[0] is not None)
    stations = [(first if f is None else f, z, ry, rz) for f, z, ry, rz in stations]
    mesh = stone.data
    dark = [0.0] * len(mesh.vertices)
    for v in mesh.vertices:
        t = (v.co.x - x0) / (x1 - x0) * steps
        if not 0 <= t <= steps:
            continue
        k = min(steps - 1, int(t))
        a, b, f = stations[k], stations[k + 1], t - k
        face, cz, ry, rz = (a[n] + (b[n] - a[n]) * f for n in range(4))
        up = (v.co.z - cz) / rz
        if abs(up) >= 1 or v.co.y > face + ry:
            continue
        wall = face - 0.1 + (ry + 0.1) * math.sqrt(1 - up * up)        # the far wall, an arch in section
        if v.co.y < wall:
            dark[v.index] = min(1.0, (wall - v.co.y) / (0.45 * depth))     # darker the farther in
            v.co.y = wall + 0.03 * noise.noise(v.co * 3.0)
    mesh.update()
    rig.point_attribute(stone, "dark", dark)


def along(a, b, r0, r1, step=0.45, wobble=0.12):
    """Blobs strung from a to b, their radius running from r0 to r1."""
    a, b = Vector(a), Vector(b)
    count = max(2, int((b - a).length / step))
    out = []
    for i in range(count + 1):
        t = i / count
        p = a.lerp(b, t) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * wobble
        out.append((p.x, p.y, p.z, (r0 + (r1 - r0) * t) * rng.uniform(0.9, 1.12)))
    return out


def surface_points(obj, spacing, toward, want):
    """Points on a rock where coral could grow: (point, normal) pairs at least `spacing` apart,
    on faces that show from `toward` and that `want(point, normal)` accepts."""
    faces = []
    for poly in obj.data.polygons:
        if poly.normal.dot(toward) > -0.15 and want(poly.center, poly.normal):
            faces.append((poly.center.copy(), poly.normal.copy()))
    rng.shuffle(faces)
    kept, cell, grid = [], spacing, {}
    for p, n in faces:
        key = (int(p.x // cell), int(p.y // cell), int(p.z // cell))
        near = (grid.get((key[0] + i, key[1] + j, key[2] + k), ()) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1))
        if all((p - q).length >= spacing for group in near for q in group):
            grid.setdefault(key, []).append(p)
            kept.append((p, n))
    return kept
