"""Build the reef's Christmas tree: a tall cone of living corals, dressed for the season.

    blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_tree.py

The tree is a rock spire grown over with coral colonies (staghorn, finger, table, brain,
lettuce and bubble corals, sea fans and tube sponges), larger at the foot and smaller toward
the tip, in five tiers like the boughs of a fir. It is strung with a spiral of lights and a
swagged rope of pearls, hung with glass baubles, candy canes and small sea stars, and topped
with a golden sea star.

Writes tree.blend, tree.png and tree.json (in sprite pixels: the foot of the tree, the centre
of the topper, and the bulbs the camera can see, each [x, y, colour, twinkle group]).
Pass `-- --draft` for a quick low-sample render that leaves tree.blend alone.
"""
import json
import math
import random
import sys
from math import cos, sin
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig
from rig import Graph, TAU

OUT = rig.HERE / "tree.blend"
DRAFT = "--draft" in rig.script_args()
if not DRAFT:
    rig.guard(OUT)
scene = rig.reset(samples=40 if DRAFT else 288)
rng = random.Random(1225)
UP = Vector((0, 0, 1))

# Heights in units of 100 px: the foot stands on the sand at 0, the lowest boughs hang at RIM
# and the coral runs out at APEX, where the sea star sits.
RIM, APEX = 0.9, 7.85
TIERS = (0.0, 0.25, 0.47, 0.66, 0.83, 1.0)
BULB_COLORS = [(1.0, 0.035, 0.03), (0.03, 0.85, 0.12), (0.04, 0.22, 1.0), (1.0, 0.55, 0.04), (1.0, 0.10, 0.55)]


def height(z):
    return min(1.0, max(0.0, (z - RIM) / (APEX - RIM)))


def tier(u):
    """Which bough a height fraction is in, and how far up that bough (0 at its lower edge)."""
    for k in range(len(TIERS) - 1):
        if u < TIERS[k + 1] or k == len(TIERS) - 2:
            return k, (u - TIERS[k]) / (TIERS[k + 1] - TIERS[k])


def spire(z):
    """Radius of the rock the corals are rooted on."""
    u = height(z)
    return 1.62 * (1 - u) + 0.06 * u


def drape(z):
    """Radius the decorations hang at: about where the coral tips reach."""
    u = height(z)
    return 2.32 * (1 - u) + 0.24 * u


def colony_size(u):
    return 1.0 - 0.55 * u


# ---- geometry helpers ------------------------------------------------------------------

class Soup:
    """One mesh gathered from many parts. Each vertex carries a colour ('tint') and a value
    ('tip') that the materials read: 0 at a colony's root up to 1 at its growing edge."""

    def __init__(self, name):
        self.name = name
        self.verts, self.faces, self.tint, self.tip = [], [], [], []

    def add(self, verts, faces, tint, tip):
        n = len(self.verts)
        self.verts += [tuple(v) for v in verts]
        self.faces += [tuple(n + i for i in face) for face in faces]
        self.tint += tint if isinstance(tint, list) else [tint] * len(verts)
        self.tip += tip if isinstance(tip, list) else [tip] * len(verts)

    def build(self, mat):
        obj = rig.add_mesh(scene, self.name, self.verts, self.faces, [mat], smooth=True)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        attr = obj.data.attributes.new("tint", "FLOAT_COLOR", "POINT")
        attr.data.foreach_set("color", [c for t in self.tint for c in (t[0], t[1], t[2], 1.0)])
        rig.point_attribute(obj, "tip", self.tip)
        return obj


def perp(v):
    """A random unit vector at right angles to v."""
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


def revolve(origin, axis, profile, sides, bend=None, cap=True):
    """Rings around an axis: profile is [(distance along the axis, radius), ...]. bend =
    (direction, amount) curves the axis sideways with the square of the distance."""
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


def ball(soup, centre, radius, tint, tip=0.5, rings=7, sides=12, axis=UP, squash=1.0):
    profile = []
    for i in range(rings + 1):
        lat = math.pi * (0.04 + 0.92 * i / rings)
        profile.append((-radius * squash * cos(lat), radius * sin(lat)))
    verts, faces = revolve(centre, axis, profile, sides)
    soup.add(verts, faces, tint, tip)


def limb(soup, p, d, length, r0, r1, tint, t0, t1, bend=0.2, lift=0.06, sides=8, rounded=False, n=4):
    """One wandering branch from p along d. Returns where it ends and which way it points."""
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
    soup.add(verts, faces, tint, [t for t in tips for _ in range(sides)])
    return cur, dirv


# ---- the corals ------------------------------------------------------------------------

def branching(soup, p, axis, s, tint, levels=3, trunks=4, kids=(2, 3), spread=(0.4, 0.8), thick=0.07,
              taper=0.74, reach=0.40, decay=0.76, bend=0.22, lift=0.07, sides=8):
    """Staghorn and finger corals: trunks that fork again and again into rounded tips."""
    def grow(p, d, length, r, level):
        last = level == levels - 1
        end, dirv = limb(soup, p, d, length, r, r * (0.86 if last else taper), tint, level / levels,
                         (level + 1) / levels, bend, lift, sides, rounded=last)
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
        start = lean(axis, side0 * cos(ang) + side1 * sin(ang), rng.uniform(0.25, 0.6) if trunks > 1 else 0.0)
        grow(p, start, s * reach * rng.uniform(0.85, 1.1), s * thick, 0)


def sea_fan(soup, p, axis, s, tint):
    """A gorgonian: a flat lace of thin branches, turned to face the glass."""
    ax = Vector((axis.x, 0, axis.z))
    ax = ((ax.normalized() if ax.length > 0.2 else UP) + UP * 0.7).normalized()
    side = Vector((ax.z, 0, -ax.x))
    levels = 5

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
        forks = [-1, 1] + ([0] if rng.random() < 0.3 else [])
        for sign in forks:
            turn = sign * rng.uniform(0.3, 0.6) + rng.uniform(-0.1, 0.1)
            grow(end - d * (r * 0.5), ang + turn, length * rng.uniform(0.68, 0.86), r * 0.76, level + 1)

    grow(p, 0.0, s * 0.33, s * 0.034, 0)


def table(soups, p, axis, s, tint):
    """A table coral: a ruffled plate on a short stalk, its top studded with branchlets."""
    soup = soups["plate"]
    ax = (axis * 0.45 + UP).normalized()
    end, _ = limb(soup, p, axis, s * 0.42, s * 0.10, s * 0.14, shade(tint, 0.7), 0.0, 0.3, bend=0.05, lift=0.25)
    a, b = frame_of(ax)
    radius, rings, sides = s * 0.64, 9, 44
    ph1, ph2 = rng.uniform(0, TAU), rng.uniform(0, TAU)

    def at(rho, phi, under=False):
        rr = radius * rho * (1 + 0.12 * sin(3 * phi + ph1) + 0.07 * sin(7 * phi + ph2))
        h = s * (0.10 * rho * rho + 0.028 * sin(9 * phi + ph1) * rho ** 3)
        if under:
            h -= s * (0.018 + 0.07 * (1 - rho * rho))
        return end + a * (rr * cos(phi)) + b * (rr * sin(phi)) + ax * h

    profile = [(0.04 + 0.96 * i / rings, False) for i in range(rings + 1)]
    profile += [(1 - 0.96 * i / rings, True) for i in range(1, rings + 1)]
    verts, faces, tips = [], [], []
    for i, (rho, under) in enumerate(profile):
        for k in range(sides):
            verts.append(at(rho, TAU * k / sides, under))
            tips.append(0.25 * rho if under else rho)
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    faces.append(tuple(range(sides)))
    soup.add(verts, faces, tint, tips)
    for _ in range(84):
        base = at(math.sqrt(rng.random()) * 0.93, rng.uniform(0, TAU))
        limb(soups["branch"], base - ax * (s * 0.01), lean(ax, perp(ax), rng.uniform(0, 0.35)), s * rng.uniform(0.03, 0.07),
             s * 0.017, s * 0.013, tint, 0.75, 1.0, bend=0.0, lift=0.0, sides=6, rounded=True, n=1)


def brain(soup, p, axis, s, tint):
    """A brain coral: a lumpy dome. Its grooves are in the material."""
    ax = (axis + UP * 0.5).normalized()
    a, b = frame_of(ax)
    radius, rings, sides = s * 0.47, 10, 26
    ph = rng.uniform(0, TAU)
    centre = p + ax * (s * 0.10)
    verts, faces = [], []
    for i in range(rings + 1):
        lat = 0.03 + 1.75 * i / rings          # from the crown down past the shoulder
        for k in range(sides):
            phi = TAU * k / sides
            rr = radius * sin(lat) * (1 + 0.08 * sin(3 * phi + ph) * sin(2 * lat + 1) + 0.05 * sin(5 * phi - ph))
            verts.append(centre + a * (rr * cos(phi)) + b * (rr * sin(phi)) + ax * (radius * 0.86 * cos(lat)))
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    faces.append(tuple(range(sides)))
    soup.add(verts, faces, tint, 0.5)


def tubes(soup, p, axis, s, tint):
    """A cluster of tube sponges, each a flared chimney with a dark throat."""
    count = rng.randint(3, 6)
    side0 = perp(axis)
    side1 = axis.cross(side0)
    phase = rng.uniform(0, TAU)
    dark = shade(tint, 0.07)
    for j in range(count):
        ang = phase + TAU * j / count
        side = side0 * cos(ang) + side1 * sin(ang)
        d = (lean(axis, side, rng.uniform(0.15, 0.55) if j else 0.0) + UP * 0.3).normalized()
        length = s * rng.uniform(0.5, 0.95) * (1.0 if j == 0 else 0.82)
        r = s * rng.uniform(0.085, 0.125)
        profile = [(0, r * 0.7), (length * 0.3, r * 0.8), (length * 0.7, r * 0.96), (length * 0.94, r * 1.06),
                   (length, r * 0.98), (length * 0.985, r * 0.78), (length * 0.8, r * 0.66), (length * 0.5, r * 0.5)]
        sides = 14
        verts, faces = revolve(p + side * (s * 0.07 * (j > 0)), d, profile, sides, bend=(perp(d), rng.uniform(-0.3, 0.3) / length))
        tints = [tint] * (5 * sides) + [shade(tint, 0.35)] * sides + [dark] * (2 * sides)
        tips = [t for t in (0.1, 0.35, 0.7, 0.92, 1.0, 0.6, 0.2, 0.0) for _ in range(sides)]
        soup.add(verts, faces, tints, tips)


def bubbles(soup, p, axis, s, tint):
    """Bubble coral: a clutch of glossy pearls of tissue."""
    centre = p + axis * (s * 0.16)
    for _ in range(rng.randint(13, 19)):
        d = (axis * rng.uniform(0.1, 1.0) + perp(axis) * rng.uniform(0, 0.95)).normalized()
        ball(soup, centre + d * (s * 0.27), s * rng.uniform(0.09, 0.155), shade(tint, rng.uniform(0.8, 1.1)),
             rng.random(), axis=d, squash=rng.uniform(0.85, 1.0))


def lettuce(soup, p, axis, s, tint):
    """Lettuce coral: whorls of thin ruffled plates opening like a rose."""
    ax = (axis + UP * 0.4).normalized()
    a, b = frame_of(ax)
    n = 10
    for scale, leaves, flare in ((1.0, rng.randint(5, 6), 1.0), (0.62, 4, 0.55)):
        phase = rng.uniform(0, TAU)
        for j in range(leaves):
            base = phase + TAU * j / leaves
            wide, tall, ph = rng.uniform(0.8, 1.1), rng.uniform(0.75, 1.1), rng.uniform(0, TAU)
            verts, faces, tips = [], [], []
            for it in range(n + 1):
                for ia in range(n + 1):
                    aa = -1 + 2 * ia / n
                    t = (it / n) * (1 - 0.24 * aa * aa)
                    ang = base + aa * wide
                    radial = a * cos(ang) + b * sin(ang)
                    out = s * scale * 0.55 * flare * t ** 0.75
                    rise = s * scale * (0.5 * tall * t ** 1.6 + 0.055 * sin(aa * 6 + ph) * t * t)
                    verts.append(p + radial * (out + s * 0.03) + ax * rise)
                    tips.append(t)
                    if it and ia:
                        k = it * (n + 1) + ia
                        faces.append((k - n - 2, k - n - 1, k, k - 1))
            soup.add(verts, faces, shade(tint, rng.uniform(0.85, 1.1)), tips)


def sea_star(soup, centre, radius, tint, facing=Vector((0, -1, 0)), spin=0.0, thickness=0.2):
    """A five-armed sea star lying in the plane facing `facing`, one arm up. Arms taper and
    curl a little, each its own way."""
    right = Vector((facing.y, -facing.x, 0)).normalized() * -1
    upward = facing.cross(right).normalized()
    if upward.z < 0:
        upward = -upward
    rin = 0.40
    curl = [rng.uniform(-0.3, 0.3) for _ in range(5)]
    stretch = [rng.uniform(0.92, 1.06) for _ in range(5)]
    bx, by = rin * cos(TAU / 10) - 1, rin * sin(TAU / 10)
    rings, sides = 14, 120
    for face_side, depth in ((1, 1.0), (-1, 0.45)):
        verts, faces, tips = [], [], []
        for i in range(rings + 1):
            rho = i / rings
            for k in range(sides):
                phi = TAU * k / sides
                rel = (phi - math.pi / 2 - spin) % (TAU / 5)
                arm = int(((phi - math.pi / 2 - spin) % TAU + TAU / 10) / (TAU / 5)) % 5
                delta = min(rel, TAU / 5 - rel)                 # 0 on an arm's ridge, 36 degrees in a valley
                edge = by / (cos(delta) * by - sin(delta) * bx)   # the star polygon's outline
                edge *= (1 - 0.11 * math.exp(-(delta / 0.13) ** 2)) * stretch[arm]
                dist = rho * edge
                weight = max(0.0, cos(2.5 * delta)) ** 2
                turned = phi + curl[arm] * weight * dist * dist
                h = thickness * radius * math.sqrt(max(0.0, 1 - rho ** 2.4)) * (1 - 0.6 * dist) * depth
                verts.append(centre + right * (radius * dist * cos(turned)) + upward * (radius * dist * sin(turned))
                             + facing * (h * face_side))
                tips.append(dist)
                if i:
                    j = (k + 1) % sides
                    faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
        soup.add(verts, faces, tint, tips)


# ---- materials -------------------------------------------------------------------------

def coral_material(name, pattern="polyps", scale=30.0, pale=0.6, roughness=0.5, bump=0.5, **inputs):
    """Reads each vertex's tint; darkens toward the root and pales toward the growing edge."""
    mat = rig.material(name, (0.5, 0.5, 0.5), roughness, **inputs)
    g = Graph(mat)
    tint = g.attribute("tint").outputs["Color"]
    tip = g.attribute("tip").outputs["Fac"]
    color = g.mix(g.math("SMOOTHSTEP", 0.45, 0.0, tip), tint, (0.48, 0.46, 0.54), "MULTIPLY")
    color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.78, 1.0, tip), pale), color, (1.0, 0.95, 0.84))
    where = g.coords()
    if pattern == "polyps":         # a skin of small raised cups, paler than the tissue between
        cells = g.node("ShaderNodeTexVoronoi", feature="F1")
        cells.inputs["Scale"].default_value = scale
        g.set(cells.inputs["Vector"], where)
        relief = g.math("SMOOTHSTEP", 0.42, 0.12, cells.outputs["Distance"])
        color = g.mix(g.math("MULTIPLY", relief, 0.14), color, (1.0, 0.97, 0.88))
    elif pattern == "brain":        # winding ridges with dark valleys between
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", wave_profile="SIN")
        wave.inputs["Scale"].default_value = scale
        wave.inputs["Distortion"].default_value = 6.0
        wave.inputs["Detail"].default_value = 2.0
        wave.inputs["Detail Scale"].default_value = 1.3
        g.set(wave.inputs["Vector"], where)
        relief = g.math("SMOOTHSTEP", 0.25, 0.75, wave.outputs["Fac"])
        color = g.mix(relief, g.mix(1.0, color, (0.42, 0.52, 0.44), "MULTIPLY"), g.mix(0.14, color, (1.0, 0.95, 0.8)))
    elif pattern == "rings":        # growth lines following the plate's edge
        lines = g.math("SINE", g.math("MULTIPLY", tip, scale))
        grain = g.noise(where, scale=22, detail=3).outputs["Fac"]
        relief = g.math("ADD", g.math("MULTIPLY", lines, 0.5), grain)
        color = g.mix(g.math("SMOOTHSTEP", 0.2, 1.0, lines), color, (0.82, 0.82, 0.82), "MULTIPLY")
    else:                           # "pores": a fine open texture
        relief = g.noise(where, scale=scale, detail=4, roughness=0.7).outputs["Fac"]
    g.to("Base Color", color)
    g.bump(relief, strength=bump, distance=0.014)
    return mat


def rock_material():
    mat = rig.material("Live rock", (0.1, 0.07, 0.09), 0.9)
    g = Graph(mat)
    where = g.coords()
    grain = g.noise(where, scale=7, detail=6, roughness=0.65).outputs["Fac"]
    algae = g.noise(where, scale=2.6, detail=3, roughness=0.5).outputs["Fac"]
    stone = g.ramp(grain, [(0.3, (0.035, 0.025, 0.035)), (0.55, (0.12, 0.085, 0.10)), (0.8, (0.26, 0.20, 0.20))])
    crust = g.mix(g.math("SMOOTHSTEP", 0.54, 0.64, algae), stone.outputs["Color"], (0.30, 0.09, 0.28))
    g.to("Base Color", crust)
    g.bump(grain, strength=0.9, distance=0.05)
    return mat


def cane_material():
    mat = rig.material("Candy cane", (0.9, 0.9, 0.9), 0.16, Coat_Weight=0.8)
    g = Graph(mat)
    stripe = g.math("SMOOTHSTEP", -0.12, 0.12, g.attribute("tip").outputs["Fac"])
    g.to("Base Color", g.mix(stripe, (0.96, 0.95, 0.92), (0.72, 0.012, 0.03)))
    return mat


def tinted(name, roughness, **inputs):
    mat = rig.material(name, (0.5, 0.5, 0.5), roughness, **inputs)
    g = Graph(mat)
    g.to("Base Color", g.attribute("tint").outputs["Color"])
    return mat, g


soups = {name: Soup(label) for name, label in (
    ("rock", "Rock spire"), ("branch", "Branching corals"), ("fan", "Sea fans"), ("plate", "Table corals"),
    ("brain", "Brain corals"), ("tube", "Tube sponges"), ("bubble", "Bubble corals"), ("lettuce", "Lettuce corals"),
    ("star", "Sea stars"), ("wire", "Light string"), ("socket", "Bulb sockets"), ("bulb", "Bulbs"), ("pearl", "Pearl rope"),
    ("bauble", "Glass baubles"), ("cap", "Bauble caps"), ("cane", "Candy canes"))}

# ---- rock spire and foot ---------------------------------------------------------------
verts, faces = [], []
rings, sides = 46, 56
for i in range(rings + 1):
    z = (APEX + 0.05) * i / rings
    for k in range(sides):
        phi = TAU * k / sides
        lump = 1 + 0.07 * sin(5 * phi + 3.1 * z) + 0.05 * sin(11 * phi - 4.7 * z) + 0.04 * sin(23 * z + 2 * phi)
        r = (spire(z) if z > RIM else 1.62 - 0.22 * (1 - z / RIM) ** 2) * lump * 0.96
        verts.append((r * cos(phi), r * sin(phi), z))
        if i:
            j = (k + 1) % sides
            faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
faces.append(tuple(range(rings * sides, (rings + 1) * sides)))
soups["rock"].add(verts, faces, (0.1, 0.07, 0.09), 0.0)
for _ in range(16):         # boulders round the foot
    phi = rng.uniform(-2.2, 2.2)
    r = rng.uniform(1.45, 1.75)
    size = rng.uniform(0.16, 0.34)
    ball(soups["rock"], Vector((r * sin(phi), -r * cos(phi), size * 0.45)), size, (0.1, 0.07, 0.09), rings=6, sides=10,
         squash=rng.uniform(0.55, 0.8))

# ---- coral colonies, bough by bough ----------------------------------------------------
GREENS = [(0.02, 0.30, 0.07), (0.04, 0.42, 0.10), (0.12, 0.50, 0.06), (0.01, 0.32, 0.20), (0.25, 0.55, 0.05)]
RED, CRIMSON, PINK, ORANGE = (0.72, 0.02, 0.03), (0.90, 0.07, 0.15), (0.95, 0.28, 0.40), (1.0, 0.30, 0.05)
GOLD, PURPLE, CREAM, TEAL, MAGENTA = (1.0, 0.60, 0.05), (0.40, 0.06, 0.62), (0.90, 0.86, 0.74), (0.03, 0.40, 0.55), (0.90, 0.10, 0.48)
FESTIVE = [RED, CRIMSON, PINK, ORANGE, GOLD, PURPLE, CREAM, TEAL, MAGENTA]
PALETTE = {
    "staghorn": GREENS * 3 + [RED, PINK, CREAM, ORANGE, PURPLE, CRIMSON],
    "finger": GREENS + [PINK, CRIMSON, GOLD, PURPLE, CREAM],
    "lettuce": GREENS * 2 + [GOLD, ORANGE, PURPLE, MAGENTA],
    "table": [RED, CRIMSON, GOLD, ORANGE, PURPLE, TEAL, CREAM] + GREENS[:2],
    "brain": [GOLD, CREAM, TEAL, PURPLE, ORANGE, GREENS[2], GREENS[4]],
    "fan": [RED, CRIMSON, PINK, ORANGE, PURPLE, MAGENTA],
    "tube": [GOLD, PURPLE, RED, TEAL, ORANGE, MAGENTA],
    "bubble": [CREAM, PINK, (0.70, 0.90, 0.55), (0.95, 0.80, 0.55)],
}
SKIRT = [("staghorn", 30), ("table", 16), ("lettuce", 20), ("fan", 12), ("finger", 10), ("tube", 5), ("bubble", 5)]
BOUGH = [("staghorn", 34), ("finger", 15), ("brain", 13), ("tube", 10), ("lettuce", 11), ("bubble", 8), ("fan", 9)]
recent = []


def pick(kinds):
    roll = rng.uniform(0, sum(weight for _, weight in kinds))
    for kind, weight in kinds:
        roll -= weight
        if roll <= 0:
            break
    for _ in range(8):
        tint = rng.choice(PALETTE[kind])
        if tint not in recent[-3:]:
            break
    recent.append(tint)
    return kind, shade(tint, rng.uniform(0.88, 1.12))


def colony(kind, tint, p, axis, s):
    if kind == "staghorn":
        branching(soups["branch"], p, axis, s, tint)
    elif kind == "finger":
        branching(soups["branch"], p, axis, s * 0.9, tint, levels=2, trunks=5, kids=(2, 3), spread=(0.3, 0.6),
                  thick=0.105, taper=0.86, reach=0.44, decay=0.7, bend=0.12)
    elif kind == "fan":
        sea_fan(soups["fan"], p, axis, s * 1.05, tint)
    elif kind == "table":
        table(soups, p, axis, s, tint)
    elif kind == "brain":
        brain(soups["brain"], p, axis, s, tint)
    elif kind == "tube":
        tubes(soups["tube"], p, axis, s, tint)
    elif kind == "bubble":
        bubbles(soups["bubble"], p, axis, s, tint)
    else:
        lettuce(soups["lettuce"], p, axis, s, tint)


SWEEP = math.radians(118)       # colonies are planted this far round each side from the glass
colonies = 0
for k in range(len(TIERS) - 1):
    u0, u1 = TIERS[k], TIERS[k + 1]
    span = (u1 - u0) * (APEX - RIM)
    rows = max(2, round(span / (0.5 * colony_size((u0 + u1) / 2))))
    for row in range(rows):
        f = (row + 0.25) / rows
        u = u0 + (u1 - u0) * f
        z = RIM + u * (APEX - RIM)
        s0 = colony_size(u) * (1.12 if row == 0 else 0.95)
        count = max(3, round(2 * SWEEP * (spire(z) + 0.5 * s0) / (0.64 * s0)))
        for j in range(count):
            theta = -SWEEP + 2 * SWEEP * (j + 0.5 + 0.5 * (row % 2) + rng.uniform(-0.3, 0.3)) / (count + 0.5)
            outward = Vector((sin(theta), -cos(theta), 0))
            rise = math.radians(8 + 50 * f ** 0.8 + rng.uniform(-8, 8))
            kind, tint = pick(SKIRT if row == 0 else BOUGH)
            root = outward * (spire(z) * 0.93) + UP * (z + rng.uniform(-0.08, 0.08))
            colony(kind, tint, root, lean(outward, UP, rise), s0 * rng.uniform(0.86, 1.14))
            colonies += 1
for j in range(8):              # low growth round the foot
    theta = -1.9 + 3.8 * (j + rng.uniform(0.2, 0.8)) / 8
    outward = Vector((sin(theta), -cos(theta), 0))
    kind, tint = pick(BOUGH)
    colony(kind, tint, outward * 1.5 + UP * rng.uniform(0.2, 0.5), lean(outward, UP, math.radians(rng.uniform(30, 60))),
           rng.uniform(0.42, 0.6))
    colonies += 1
# The very tip: a tuft of green staghorn for the star to sit in.
branching(soups["branch"], Vector((0, 0, APEX - 0.25)), UP, 0.5, GREENS[1], trunks=4)

# ---- the topper ------------------------------------------------------------------------
STAR = Vector((0.0, -0.16, APEX + 0.42))
sea_star(soups["star"], STAR, 0.56, (1.0, 0.40, 0.03), facing=Vector((0.05, -1, 0.1)).normalized(), thickness=0.27)


# ---- lights, pearls and ornaments ------------------------------------------------------
def spiral(z0, z1, start, hand, offset, pitch, sag=0.0, swags=9, step=math.radians(2.5)):
    """A rope wound up the tree: (angle round the tree, point) pairs. The turns close up as the
    tree narrows, and the rope dips between the corals it rests on."""
    out, z, theta = [], z0, start
    while z < z1:
        r = drape(z) + offset
        dip = sag * (0.5 - 0.5 * cos(theta * swags))
        out.append((theta, Vector((r * sin(theta), -r * cos(theta), z - dip))))
        z += pitch(z) * step / TAU
        theta += hand * step
    return out


def facing_glass(theta, limit):
    return abs((theta + math.pi) % TAU - math.pi) < limit


wire = spiral(1.02, APEX - 0.35, 0.6, 1, 0.03, lambda z: 0.34 + 0.40 * drape(z), sag=0.07)
verts, faces, _ = rig.sweep([p for _, p in wire], [(0.0105, 0.0105)] * len(wire), 6)
soups["wire"].add(verts, faces, (0.006, 0.055, 0.02), 0.0)
BULB_SCALE = 1.2
BULB = [(0.036, 0.020), (0.052, 0.033), (0.078, 0.041), (0.105, 0.038), (0.132, 0.026), (0.150, 0.012), (0.158, 0.003)]
lamps, travelled, due = [], 0.0, 0.2
for (theta, a), (_, b) in zip(wire, wire[1:]):
    step = (b - a).length
    while travelled + step >= due:
        base = a + (b - a) * ((due - travelled) / step)
        due += 0.40 * rng.uniform(0.9, 1.1)
        color = len(lamps) % len(BULB_COLORS)
        lamps.append(None)
        if not facing_glass(theta, math.radians(100)):
            continue
        tilt = math.radians(rng.uniform(-38, 38) if rng.random() < 0.8 else rng.choice((-1, 1)) * rng.uniform(60, 105))
        outward = Vector((base.x, base.y, 0)).normalized()
        d = (Vector((sin(tilt), 0, -cos(tilt))) + outward * 0.35).normalized()
        sv, sf = revolve(base, d, [(0, 0.024 * BULB_SCALE), (0.05 * BULB_SCALE, 0.024 * BULB_SCALE)], 10)
        soups["socket"].add(sv, sf, (0.008, 0.07, 0.025), 0.0)
        bv, bf = revolve(base, d, [(h * BULB_SCALE, r * BULB_SCALE) for h, r in BULB], 12)
        soups["bulb"].add(bv, bf, BULB_COLORS[color], 0.0)
        lamps[-1] = (base + d * (0.092 * BULB_SCALE), color, theta)
    travelled += step

rope = spiral(1.25, APEX - 0.7, 2.4, -1, 0.07, lambda z: 0.5 + 0.62 * drape(z), sag=0.2, swags=5)
travelled, due = 0.0, 0.0
for (theta, a), (_, b) in zip(rope, rope[1:]):
    step = (b - a).length
    while travelled + step >= due:
        if facing_glass(theta, math.radians(108)):
            ball(soups["pearl"], a + (b - a) * ((due - travelled) / step), 0.036, (0.93, 0.89, 0.84), rings=5, sides=9)
        due += 0.083
    travelled += step

taken = []


def hang(count, low, high, gap, reach=math.radians(74)):
    """Places on the front of the tree, spread out, more of them where it is wide."""
    spots = []
    for _ in range(4000):
        if len(spots) == count:
            break
        z = low + (high - low) * rng.random() ** 1.5
        theta = rng.uniform(-reach, reach)
        r = drape(z) * 0.98 + 0.06
        p = Vector((r * sin(theta), -r * cos(theta), z))
        flat = Vector((p.x, 0, p.z))
        if all((flat - q).length > gap for q in taken):
            taken.append(flat)
            spots.append((p, theta))
    return spots


GLASS = [(0.70, 0.015, 0.02), (1.0, 0.58, 0.10), (0.03, 0.10, 0.62), (0.80, 0.84, 0.90), (0.62, 0.02, 0.30), (0.02, 0.36, 0.40)]
for i, (p, theta) in enumerate(hang(22, 1.0, APEX - 0.9, 0.62)):
    radius = (0.105 + 0.085 * (1 - height(p.z))) * rng.uniform(0.9, 1.1)
    centre = p - UP * (radius + 0.05)
    ball(soups["bauble"], centre, radius, GLASS[i % len(GLASS)], rings=14, sides=26)
    cv, cf = revolve(centre + UP * (radius * 0.94), UP, [(0, radius * 0.30), (radius * 0.22, radius * 0.27), (radius * 0.26, radius * 0.1)], 12)
    soups["cap"].add(cv, cf, (1.0, 0.70, 0.22), 0.0)
    loop = [centre + UP * (radius * 1.2) + Vector((cos(a), 0, sin(a))) * (radius * 0.16) for a in (TAU * k / 10 for k in range(11))]
    lv, lf, _ = rig.sweep(loop, [(0.006, 0.006)] * len(loop), 5, cap=False)
    soups["cap"].add(lv, lf, (1.0, 0.70, 0.22), 0.0)

for p, theta in hang(8, 1.1, APEX - 1.3, 0.55):
    tilt = rng.uniform(-0.45, 0.45)
    up = Vector((sin(tilt), 0, cos(tilt)))
    side = Vector((cos(tilt), 0, -sin(tilt))) * rng.choice((-1, 1))
    foot = p - up * 0.42 + Vector((0, -0.05, 0))
    crook, shaft = 0.085, 0.5
    path = [foot + up * (shaft * i / 6) for i in range(7)]
    path += [foot + up * shaft + side * crook - side * (crook * cos(a)) + up * (crook * sin(a))
             for a in (math.pi * 1.18 * k / 10 for k in range(1, 11))]
    verts, faces, uv = rig.sweep(path, [(0.036, 0.036)] * len(path), 10)
    soups["cane"].add(verts, faces, (1, 1, 1), [sin(TAU * (7.5 * u + v)) for u, v in uv])

for i, (p, theta) in enumerate(hang(6, 1.2, APEX - 1.6, 0.6)):
    facing = (Vector((sin(theta), -cos(theta), 0)) * 0.5 + Vector((0, -1, 0.15))).normalized()
    sea_star(soups["star"], p + Vector((0, -0.05, 0)), rng.uniform(0.17, 0.23), (CRIMSON, CREAM, ORANGE)[i % 3],
             facing=facing, spin=rng.uniform(0, TAU), thickness=0.26)

# ---- build -----------------------------------------------------------------------------
star_mat = coral_material("Sea star skin", "polyps", scale=34, pale=0.25, roughness=0.55, bump=0.7)
g = Graph(star_mat)
g.to("Emission Color", g.attribute("tint").outputs["Color"])
g.to("Emission Strength", 0.14)
bulb_mat, g = tinted("Bulb glass", 0.12, Coat_Weight=1.0)
g.to("Emission Color", g.attribute("tint").outputs["Color"])
g.to("Emission Strength", 1.0)
materials = {
    "rock": rock_material(),
    "branch": coral_material("Branching coral", "polyps", scale=30, pale=0.2, Coat_Weight=0.12, Sheen_Weight=0.3),
    "fan": coral_material("Sea fan", "polyps", scale=46, pale=0.3, roughness=0.6, bump=0.35),
    "plate": coral_material("Table coral", "polyps", scale=38, pale=0.3, Coat_Weight=0.1),
    "brain": coral_material("Brain coral", "brain", scale=15, pale=0.0, roughness=0.6, bump=0.9),
    "tube": coral_material("Tube sponge", "pores", scale=55, pale=0.22, roughness=0.7, bump=0.55),
    "bubble": coral_material("Bubble coral", "pores", scale=14, pale=0.2, roughness=0.16, bump=0.05, Coat_Weight=0.7,
                             Subsurface_Weight=0.45),
    "lettuce": coral_material("Lettuce coral", "rings", scale=42, pale=0.35, roughness=0.55, bump=0.4),
    "star": star_mat,
    "wire": tinted("Wire", 0.5)[0],
    "socket": tinted("Socket", 0.45)[0],
    "bulb": bulb_mat,
    "pearl": tinted("Pearl", 0.2, Coat_Weight=1.0, Sheen_Weight=0.5, Metallic=0.2)[0],
    "bauble": tinted("Blown glass", 0.07, Metallic=0.92, Coat_Weight=1.0)[0],
    "cap": tinted("Brass", 0.25, Metallic=1.0)[0],
    "cane": cane_material(),
}
objects = [soup.build(materials[name]) for name, soup in soups.items()]

rig.tank_light(scene)
cam = rig.camera(scene, elevation=9)
rig.ground(scene, size=9)
w, h = rig.frame(scene, cam, objects, pad=(10, 10, 10, 8))

# A glow belongs only on a bulb the camera can see: cast from each bulb toward the lens.
bpy.context.view_layer.update()
deps = bpy.context.evaluated_depsgraph_get()
toward = cam.matrix_world.to_3x3() @ Vector((0, 0, 1))
bulbs = []
for i, lamp in enumerate(lamps):
    if lamp is None:
        continue
    centre, color, theta = lamp
    hit = scene.ray_cast(deps, centre + toward * 0.09, toward, distance=40)[0]
    if not hit and facing_glass(theta, math.radians(84)):
        x, y = rig.project(scene, cam, centre)
        bulbs.append([round(x, 1), round(y, 1), color, i % 8])

if not DRAFT:
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
rig.render(scene, rig.HERE / ("_tree_draft.png" if DRAFT else "tree.png"))
info = {"size": [w, h], "foot": list(rig.project(scene, cam, (0, 0, 0))), "star": list(rig.project(scene, cam, STAR)), "bulbs": bulbs}
if not DRAFT:
    (rig.HERE / "tree.json").write_text(json.dumps(info, separators=(",", ":")) + "\n")
print("TREE", w, "x", h, "|", colonies, "colonies,", sum(len(s.verts) for s in soups.values()), "vertices,", len(bulbs), "bulbs",
      "| foot", info["foot"], "star", info["star"])
