"""Render the store edition's own tank: the empty plate and its reef structures.

    blender -b --factory-startup --python-exit-code 1 -P market/authoring/create_reefscape.py -- [--draft]

The tank is built once, in tank units (x across its 3400 px, y back from the front glass, z up;
one unit is 100 px), and looked at through one fixed camera, level with the sprites' own. Two
kinds of picture come out of it, into market/art/reefscape:

  plate.jpg     the empty tank: sand, water and back wall, 3400x1080
  <name>.png    each reef structure on its own, with its shadow on the sand, cut to its bounds
  <name>.json   where that picture sits in the tank
  preview.jpg   the structures laid over the plate, to look at

--draft renders with few samples. --only <name> renders one structure and reuses the rest.
"""
import json
import math
import sys
from math import cos, sin
from pathlib import Path

import bpy
from mathutils import Vector, noise

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reef_kit as kit  # noqa: E402
from reef_kit import rig, rng  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "art/reefscape"
OUT.mkdir(parents=True, exist_ok=True)
ARGS = rig.script_args()
DRAFT = "--draft" in ARGS
ONLY = ARGS[ARGS.index("--only") + 1] if "--only" in ARGS else None
WIDTH, HEIGHT, DEPTH = 34.0, 10.8, 22.0     # the tank, in units; the plate is WIDTH x HEIGHT hundred px
ELEVATION = 9.0

scene = rig.reset(samples=48 if DRAFT else 192)
# A camera exposed for the lit coral lets everything else fall dark: deepen the mid-tones.
scene.view_settings.gamma = 0.78
scene.render.resolution_x, scene.render.resolution_y = int(WIDTH * 100), int(HEIGHT * 100)

# ---- light and camera ------------------------------------------------------------------
def reef_light():
    """A reef tank's light: a hard blue-white key from straight overhead and very little else.
    Open water all round is dark, so whatever the key misses falls away to deep blue, and the
    pale sand throws a little light back up."""
    world = bpy.data.worlds.new("Tank water")
    world.use_nodes = True
    scene.world = world
    tree = world.node_tree
    tree.nodes.clear()
    coord = tree.nodes.new("ShaderNodeTexCoord")
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    remap = tree.nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value, remap.inputs["From Max"].default_value = -1, 1
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    stops = [(0.0, (0.06, 0.09, 0.14, 1)), (0.40, (0.006, 0.02, 0.06, 1)), (0.62, (0.006, 0.025, 0.07, 1)), (1.0, (0.07, 0.14, 0.30, 1))]
    while len(ramp.color_ramp.elements) < len(stops):
        ramp.color_ramp.elements.new(0.5)
    for element, (at, color) in zip(ramp.color_ramp.elements, stops):
        element.position, element.color = at, color
    back = tree.nodes.new("ShaderNodeBackground")
    out = tree.nodes.new("ShaderNodeOutputWorld")
    tree.links.new(coord.outputs["Generated"], split.inputs[0])
    tree.links.new(split.outputs["Z"], remap.inputs["Value"])
    tree.links.new(remap.outputs[0], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], back.inputs["Color"])
    tree.links.new(back.outputs[0], out.inputs["Surface"])
    lamp = bpy.data.lights.new("Tank light", "SUN")
    lamp.energy, lamp.angle, lamp.color = 4.8, math.radians(22), (0.66, 0.80, 1.0)
    obj = bpy.data.objects.new("Tank light", lamp)
    scene.collection.objects.link(obj)
    obj.rotation_euler = (math.radians(11), math.radians(-4), math.radians(-14))
    return obj


sun = reef_light()
cam = rig.camera(scene, elevation=ELEVATION)
cam.data.ortho_scale = WIDTH
bpy.context.view_layer.update()
# Put the front edge of the sand on the bottom edge of the picture, and the tank's middle on its middle.
foot = cam.matrix_world.inverted() @ Vector((WIDTH / 2, 0, 0))
cam.location += cam.matrix_world.to_3x3() @ Vector((foot.x, foot.y + HEIGHT / 2, 0))
bpy.context.view_layer.update()
TOWARD = cam.matrix_world.to_3x3() @ Vector((0, 0, 1))      # from the tank toward the viewer


def pixel(point):
    """Tank pixel (x from the left, y from the top) of a point in the tank."""
    p = cam.matrix_world.inverted() @ Vector(point)
    return WIDTH * 50 + p.x * 100, HEIGHT * 50 - p.y * 100


# ---- the empty tank --------------------------------------------------------------------
def sand_height(x, y):
    dune = 0.16 * noise.noise(Vector((x * 0.21, y * 0.21, 0.0))) + 0.06 * noise.noise(Vector((x * 0.7, y * 0.7, 5.0)))
    drift = noise.noise(Vector((x * 0.3, y * 0.3, 9.0)))
    ripple = 0.014 * sin((x + 1.6 * drift) * math.tau / 0.62 + y * 1.7)
    return dune + ripple + 0.25 * (y / DEPTH) ** 2


def build_sand():
    step = 0.1
    nx, ny = int((WIDTH + 2) / step) + 1, int((DEPTH + 1) / step) + 1
    verts, faces = [], []
    for j in range(ny):
        for i in range(nx):
            x, y = -1 + i * step, -0.5 + j * step
            verts.append((x, y, sand_height(x, y)))
            if i and j:
                k = j * nx + i
                faces.append((k - nx - 1, k - nx, k, k - 1))
    mat = rig.material("Sand", (0.8, 0.78, 0.72), 0.85)
    g = rig.Graph(mat)
    where = g.coords()
    grain = g.noise(where, scale=95, detail=3, roughness=0.7).outputs["Fac"]
    patch = g.noise(where, scale=1.1, detail=4, roughness=0.6).outputs["Fac"]
    color = g.ramp(grain, [(0.3, (0.40, 0.40, 0.41)), (0.55, (0.60, 0.60, 0.61)), (0.8, (0.76, 0.76, 0.77))]).outputs["Color"]
    color = g.mix(g.math("MULTIPLY", g.math("SMOOTHSTEP", 0.45, 0.7, patch), 0.22), color, (0.46, 0.48, 0.53))
    # Water takes the colour out of the sand with distance.
    back = g.node("ShaderNodeSeparateXYZ")
    g.set(back.inputs[0], where)
    haze = g.math("MULTIPLY", g.math("SMOOTHSTEP", 1.5, DEPTH, back.outputs["Y"]), 0.93)
    g.to("Base Color", g.mix(haze, color, (0.035, 0.10, 0.24)))
    # Light through the rippled surface: a net of bright lines that fades with depth too.
    net = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    net.inputs["Scale"].default_value = 1.35
    warp = g.noise(where, scale=0.9, detail=2).outputs["Color"]
    g.set(net.inputs["Vector"], g.mix(0.22, where, warp))
    lines = g.math("SMOOTHSTEP", 0.09, 0.0, net.outputs["Distance"])
    g.to("Emission Color", (0.75, 0.92, 1.0))
    g.to("Emission Strength", g.math("MULTIPLY", lines, g.math("SUBTRACT", 0.16, g.math("MULTIPLY", haze, 0.17))))
    g.bump(grain, strength=0.35, distance=0.01)
    obj = rig.add_mesh(scene, "Sand", verts, faces, [mat], smooth=True)
    return obj


def build_wall():
    """The back of the tank: water going dark with distance, lit only near the surface."""
    mat = rig.material("Open water", (0, 0, 0), 1.0)
    g = rig.Graph(mat)
    where = g.node("ShaderNodeSeparateXYZ")
    g.set(where.inputs[0], g.coords())
    rise = g.math("DIVIDE", where.outputs["Z"], 9.0)
    drift = g.noise(g.coords(), scale=0.12, detail=2).outputs["Fac"]
    color = g.ramp(g.math("ADD", rise, g.math("MULTIPLY", g.math("SUBTRACT", drift, 0.5), 0.25)),
                   [(0.0, (0.004, 0.018, 0.055)), (0.4, (0.007, 0.036, 0.11)), (0.75, (0.016, 0.085, 0.23)), (1.0, (0.06, 0.26, 0.50))]).outputs["Color"]
    g.to("Emission Color", color)
    g.to("Emission Strength", 1.0)
    g.to("Specular IOR Level", 0.0)
    return rig.add_mesh(scene, "Back wall", [(-2, DEPTH, -1), (WIDTH + 2, DEPTH, -1), (WIDTH + 2, DEPTH, 13), (-2, DEPTH, 13)], [(0, 1, 2, 3)], [mat])


# ---- reef structures -------------------------------------------------------------------
# Most of a reef is blue, purple and bone white. Strong colour comes in small doses.
LAVENDER, MAUVE, PLUM, COBALT = (0.50, 0.42, 0.80), (0.42, 0.24, 0.55), (0.26, 0.11, 0.52), (0.07, 0.18, 0.70)
SKY, SLATE, CREAM, BONE, SAGE = (0.30, 0.50, 0.88), (0.30, 0.38, 0.54), (0.80, 0.75, 0.62), (0.88, 0.88, 0.84), (0.52, 0.62, 0.42)
NEON, PINK, ORANGE, RED, YELLOW, TEAL = (0.22, 0.92, 0.10), (1.0, 0.25, 0.50), (1.0, 0.35, 0.04), (0.80, 0.04, 0.06), (0.95, 0.80, 0.10), (0.0, 0.60, 0.55)
COOL = [LAVENDER, MAUVE, PLUM, COBALT, SKY, SLATE, CREAM, BONE, SAGE, LAVENDER, COBALT, BONE]
POP = [NEON, PINK, ORANGE, RED, YELLOW, TEAL]
PALE = (0.90, 0.94, 1.0)
recent = []


def colour(pop=0.16, choices=None):
    """A coral's body colour: usually one of the cool ones, now and then a strong one."""
    pool = choices or (POP if rng.random() < pop else COOL)
    for _ in range(10):
        tint = rng.choice(pool)
        if tint not in recent[-3:]:
            break
    recent.append(tint)
    return kit.shade(tint, rng.uniform(0.9, 1.1))


def other(tint, choices=POP + COOL):
    return max(choices, key=lambda c: sum(abs(a - b) for a, b in zip(c, tint)) + rng.uniform(0, 0.8))


def tips(tint):
    """Growing tips: nearly white on most corals; on the pale ones, often blue or purple."""
    if min(tint) > 0.36 and rng.random() < 0.6:
        return rng.choice([COBALT, LAVENDER, PLUM, SKY, PINK])
    return kit.blend(tint, PALE, 0.7)


def grow(soups, kind, p, axis, s, pop=0.16):
    if kind in ("staghorn", "bush", "table"):
        tint = colour(pop)       # the largest colonies are never the loud ones
        make = {"staghorn": kit.staghorn, "bush": kit.bush}.get(kind)
        if make:
            make(soups["branch"], p, axis, s, tint, tips(tint))
        else:
            kit.table(soups, p, axis, s, tint, tips(tint))
    elif kind == "birdsnest":
        tint = colour(choices=[PINK, LAVENDER, BONE, NEON, MAUVE])
        kit.birdsnest(soups["branch"], p, axis, s, tint, kit.blend(tint, PALE, 0.6))
    elif kind == "plating":
        base = colour(choices=[MAUVE, SLATE, SAGE, LAVENDER, SAGE, ORANGE, TEAL])
        kit.plating(soups["plating"], p, axis, s, base, kit.blend(base, PALE, 0.6))
    elif kind == "brain":
        tint = colour(pop=0.4)
        kit.dome(soups["brain"], p, axis, s, tint, kit.shade(tint, 0.3))
    elif kind == "stars":
        kit.dome(soups["stars"], p, axis, s, kit.shade(colour(pop=0.0), 0.6), rng.choice([NEON, TEAL, ORANGE, PINK]))
    elif kind == "zoas":
        tint = colour(pop=0.45)
        kit.polyp_mat(soups["discs"], p, axis, s, tint, other(tint))
    elif kind == "mushrooms":
        tint = colour(choices=[RED, PLUM, TEAL, COBALT, ORANGE])
        kit.polyp_mat(soups["discs"], p, axis, s, tint, kit.shade(tint, 0.55), size=0.19, crowd=0.25)
    else:
        kit.sea_fan(soups["fan"], p, axis, s, colour(choices=[RED, ORANGE, PLUM, YELLOW, MAUVE]))


def pick(table):
    roll = rng.uniform(0, sum(weight for _, weight in table))
    for kind, weight in table:
        roll -= weight
        if roll <= 0:
            return kind


def arch():
    """An arch of rock on two legs, open water under the shelf, with a crown at one end."""
    kit.seed(11)
    recent.clear()
    d = 9.0
    blobs = kit.along((8.2, d - 0.3, 0.3), (9.4, d, 3.3), 1.35, 1.0)                 # left leg
    blobs += kit.along((16.0, d + 0.6, 0.3), (15.0, d + 0.3, 3.3), 1.15, 0.9)         # right leg
    blobs += kit.along((7.3, d, 3.6), (10.6, d, 4.3), 0.95, 1.05)                      # the shelf, arched
    blobs += kit.along((10.6, d, 4.3), (13.4, d + 0.1, 4.35), 1.05, 0.95)
    blobs += kit.along((13.4, d + 0.1, 4.35), (16.0, d + 0.2, 3.95), 0.95, 0.9)
    blobs += kit.along((16.0, d + 0.2, 3.95), (18.3, d + 0.1, 3.6), 0.85, 0.6)         # an overhang past the right leg
    blobs += kit.along((9.2, d + 0.3, 4.7), (10.5, d + 0.6, 6.4), 0.95, 0.55)          # crown
    blobs += kit.along((14.8, d + 0.4, 4.5), (15.3, d + 0.6, 5.2), 0.75, 0.5)
    blobs += [(6.9, d - 1.0, 0.3, 0.95), (17.0, d - 0.6, 0.3, 0.9), (10.2, d - 1.2, 0.25, 0.85)]
    holes = [(8.9, d - 1.1, 1.7, 0.6), (15.6, d - 0.5, 1.6, 0.5), (12.0, d - 0.9, 4.3, 0.42), (17.2, d - 0.7, 3.5, 0.35)]
    stone = kit.rock(scene, "Arch rock", blobs, holes, resolution=0.08, seed_value=3.0)     # the same in a draft: corals are placed by its mesh
    stone.data.materials.append(ROCK)

    soups = kit.new_soups()
    # Sunlit tops: the stony corals that want light.
    # Spaced so that the coralline rock shows between colonies; a few are much larger than the rest.
    tops = kit.surface_points(stone, 0.8, TOWARD, lambda p, n: n.z > 0.45 and p.z > 1.2)
    for p, n in tops:
        high = p.z > 4.6
        kind = pick([("staghorn", 34), ("table", 18 if not high else 6), ("bush", 30), ("birdsnest", 12), ("plating", 6)])
        hero = rng.random() < 0.2
        size = rng.uniform(0.9, 1.5) * (1.25 if kind in ("table", "staghorn") else 1.0) * (1.7 if hero else 1.0)
        if p.z > 5.0:       # the crown stays under the water
            size *= 0.6
        grow(soups, kind, p - n * 0.1, (n + kit.UP * 0.8).normalized(), size, pop=0.0 if hero else 0.16)
    # Faces of the rock that show from the front: shelves, mats and domes.
    faces = kit.surface_points(stone, 0.76, TOWARD, lambda p, n: -0.3 < n.z <= 0.45 and n.y < 0.1 and p.z > 0.5)
    for p, n in faces:
        kind = pick([("plating", 20), ("zoas", 26), ("stars", 12), ("brain", 8), ("bush", 18), ("fan", 6), ("mushrooms", 8), ("birdsnest", 8)])
        size = rng.uniform(0.7, 1.15)
        grow(soups, kind, p - n * 0.08, (n + kit.UP * (1.3 if kind == "plating" else 0.6 if kind in ("bush", "fan", "birdsnest") else 0.15)).normalized(), size)
    # On the sand round the feet.
    for x, y, kind, size in ((6.3, d - 2.0, "brain", 1.2), (7.6, d - 2.5, "zoas", 1.3), (9.6, d - 2.4, "mushrooms", 1.2), (11.4, d - 1.6, "stars", 0.9),
                             (13.4, d - 1.9, "zoas", 1.1), (15.2, d - 2.2, "plating", 1.3), (17.4, d - 1.8, "brain", 1.0), (18.5, d - 1.0, "zoas", 0.9)):
        grow(soups, kind, Vector((x, y, sand_height(x, y) - 0.03)), kit.UP, size)
    objects = [stone] + [obj for obj in (soup.build(scene, CORAL[name]) for name, soup in soups.items()) if obj]
    print("ARCH", len(tops), "top colonies,", len(faces), "on the faces,", sum(len(s.verts) for s in soups.values()), "vertices")
    return objects


def on_rock(stone, x, y):
    """The point of a rock's surface under (x, y), and which way it faces; the sand if it misses."""
    hit, at, normal, _ = stone.ray_cast(Vector((x, y, 20)), Vector((0, 0, -1)))
    return (at, normal) if hit else (Vector((x, y, sand_height(x, y))), kit.UP)


def bommie():
    """A low mound made of four big corals with small ones filling in round them: a folded
    brain coral, a tall sea fan, an antler coral and a cup coral."""
    kit.seed(23)
    recent.clear()
    d = 7.8
    blobs = kit.along((22.4, d, 0.2), (29.6, d + 0.4, 0.2), 1.55, 1.45)               # a low ridge on the sand
    blobs += kit.along((23.2, d + 1.5, 1.2), (28.4, d + 1.7, 1.5), 1.35, 1.25)        # a higher one behind it
    blobs += [(29.7, d + 0.6, 0.9, 1.25), (21.6, d - 0.3, 0.2, 1.05), (25.8, d + 1.9, 2.3, 1.0)]
    stone = kit.rock(scene, "Bommie rock", blobs, resolution=0.08, seed_value=8.0)
    stone.data.materials.append(ROCK)
    soups = kit.new_soups()
    big = []        # where the large corals stand, and how much room each keeps: (x, y, radius)

    def stand(x, y, room):
        big.append((x, y, room))
        return on_rock(stone, x, y)

    # The four that make the structure.
    at, n = stand(23.3, d - 0.7, 1.7)
    kit.folded_brain(soups["relief"], at - kit.UP * 0.35, Vector((0, -0.35, 1)).normalized(), 1.5, (0.13, 0.17, 0.56), (0.035, 0.03, 0.17))
    at, n = stand(22.9, d + 2.0, 0.9)
    kit.great_fan(soups["fan"], at - kit.UP * 0.1, Vector((-0.12, 0, 1)), 3.9, (0.56, 0.48, 0.80))
    at, n = stand(25.9, d + 1.0, 1.0)
    kit.antler(soups["branch"], at - kit.UP * 0.1, Vector((0.05, -0.1, 1)).normalized(), 3.4, (0.62, 0.46, 0.27), (0.92, 0.86, 0.72))
    at, n = stand(28.2, d - 0.5, 1.5)
    kit.cup(soups["cup"], at + kit.UP * 0.1, Vector((0.05, -0.3, 1)).normalized(), 2.4, (0.34, 0.16, 0.66), (0.86, 0.10, 0.52))
    # Two of middle size, so the eye has somewhere to go between large and small.
    at, n = stand(28.6, d + 2.0, 0.7)
    kit.great_fan(soups["fan"], at - kit.UP * 0.1, Vector((0.15, 0, 1)), 2.5, (0.92, 0.56, 0.42), levels=8)
    at, n = stand(25.6, d - 1.0, 0.9)
    kit.folded_brain(soups["relief"], at - kit.UP * 0.25, Vector((0, -0.3, 1)).normalized(), 0.8, (0.62, 0.74, 0.60), (0.20, 0.34, 0.30))

    # Small corals fill what is left, keeping clear of the big ones.
    spots = kit.surface_points(stone, 0.52, TOWARD, lambda p, n: n.z > -0.2 and p.z > 0.35 and (n.z > 0.4 or n.y < 0.2))
    filled = 0
    for p, n in spots:
        if any((p.x - x) ** 2 + (p.y - y) ** 2 < room * room for x, y, room in big):
            continue
        top = n.z > 0.5
        kind = pick([("bush", 30), ("birdsnest", 10), ("plating", 16), ("staghorn", 10)] if top else
                    [("zoas", 28), ("stars", 14), ("plating", 20), ("bush", 16), ("mushrooms", 8), ("brain", 8)])
        lift = 0.9 if kind in ("bush", "birdsnest", "staghorn") else 1.2 if kind == "plating" else 0.2
        grow(soups, kind, p - n * 0.07, (n + kit.UP * lift).normalized(), rng.uniform(0.5, 0.95), pop=0.2)
        filled += 1
    for x, y, kind, size in ((21.0, d - 1.6, "zoas", 0.9), (22.6, d - 2.6, "stars", 0.7), (24.6, d - 2.5, "mushrooms", 0.9), (26.6, d - 2.6, "zoas", 1.0),
                             (29.4, d - 2.2, "brain", 0.8), (30.6, d - 0.6, "zoas", 0.8)):
        grow(soups, kind, Vector((x, y, sand_height(x, y) - 0.03)), kit.UP, size)
    objects = [stone] + [obj for obj in (soup.build(scene, CORAL[name]) for name, soup in soups.items()) if obj]
    print("BOMMIE", len(big), "large corals,", filled, "small ones,", sum(len(s.verts) for s in soups.values()), "vertices")
    return objects


def nearest(stone, target, want):
    """The point of a rock's surface nearest a target, among faces that want(normal) accepts."""
    target = Vector(target)
    best = min((poly for poly in stone.data.polygons if want(poly.normal)), key=lambda poly: (poly.center - target).length)
    return best.center.copy(), best.normal.copy()


NOTES = {}      # extra facts about a structure, written into its .json


def grotto():
    """A rock outcrop with the moray's cave under it. The cave is a dark hollow in the front
    of the rock, closed at its left end and open at its right, under a roof that carries a
    big table coral. The moray lies in it facing right and comes out over open sand."""
    kit.seed(31)
    recent.clear()
    d = 6.3
    blobs = kit.along((1.3, d + 0.6, 0.4), (3.5, d + 0.8, 0.45), 1.45, 1.45)           # the mass the cave is cut into
    blobs += kit.along((1.2, d + 0.5, 2.2), (3.8, d + 0.3, 2.3), 1.25, 1.1)            # its roof, reaching out past the mouth
    blobs += kit.along((1.4, d + 0.9, 3.3), (2.6, d + 1.0, 3.8), 1.0, 0.7)             # crown
    blobs += [(0.8, d - 0.4, 0.3, 1.0)]
    stone = kit.rock(scene, "Grotto rock", blobs, resolution=0.08, seed_value=17.0)
    stone.data.materials.append(ROCK)
    deep, mouth = 2.3, 4.3
    kit.hollow(stone, (deep, 0.72), (5.2, 0.92), depth=1.05, height=1.55, seed_value=4.0)
    soups = kit.new_soups()
    big = []

    def stand(x, y, room):
        big.append((x, y, room))
        return on_rock(stone, x, y)

    def by_cave(point):
        """In the cave, or in front of it where the moray comes and goes."""
        return deep - 0.4 < point.x < 6.8 and point.z < 1.65

    # The large corals.
    at, n = stand(3.5, d + 0.1, 0.9)
    kit.table(soups, at - kit.UP * 0.15, Vector((0.22, -0.25, 1)).normalized(), 2.4, (0.20, 0.30, 0.72), (0.84, 0.90, 1.0))
    at, n = stand(2.2, d + 0.9, 0.8)
    kit.staghorn(soups["branch"], at - kit.UP * 0.15, Vector((-0.08, -0.1, 1)).normalized(), 3.0, (0.50, 0.42, 0.80), (0.92, 0.95, 1.0))
    at, n = nearest(stone, (1.5, d - 0.7, 2.1), lambda normal: normal.y < -0.35 and normal.z > -0.2)
    big.append((at.x, at.y, 0.8))
    kit.plating(soups["plating"], at - n * 0.1, (n + kit.UP * 1.2).normalized(), 1.8, (0.40, 0.60, 0.40), (0.86, 0.94, 0.84))
    spot = Vector((1.1, d - 2.0, sand_height(1.1, d - 2.0)))
    big.append((spot.x, spot.y, 0.8))
    kit.folded_brain(soups["relief"], spot - kit.UP * 0.2, Vector((0, -0.3, 1)).normalized(), 0.78, (0.22, 0.56, 0.26), (0.04, 0.17, 0.10))

    # Small corals fill in, keeping clear of the big ones and of the cave.
    spots = kit.surface_points(stone, 0.5, TOWARD, lambda p, n: n.z > -0.2 and p.z > 0.35 and (n.z > 0.4 or n.y < 0.2))
    filled = 0
    for p, n in spots:
        if by_cave(p) or any((p.x - x) ** 2 + (p.y - y) ** 2 < room * room for x, y, room in big):
            continue
        top = n.z > 0.5
        kind = pick([("bush", 30), ("birdsnest", 10), ("plating", 14), ("staghorn", 12)] if top else
                    [("zoas", 28), ("stars", 14), ("plating", 18), ("bush", 18), ("mushrooms", 8), ("brain", 8)])
        lift = 0.9 if kind in ("bush", "birdsnest", "staghorn") else 1.2 if kind == "plating" else 0.2
        grow(soups, kind, p - n * 0.07, (n + kit.UP * lift).normalized(), rng.uniform(0.5, 0.95), pop=0.2)
        filled += 1
    for x, y, kind, size in ((0.5, d - 2.5, "zoas", 0.8), (2.4, d - 2.9, "stars", 0.6)):
        grow(soups, kind, Vector((x, y, sand_height(x, y) - 0.03)), kit.UP, size)
    objects = [stone] + [obj for obj in (soup.build(scene, CORAL[name]) for name, soup in soups.items()) if obj]
    # For the moray: the sand at the closed end of the cave and under the edge of its roof,
    # and the height of the roof, in tank pixels.
    y = d - 0.2
    NOTES["grotto"] = {"cave": {"deep": [round(v) for v in pixel((deep + 0.25, y, sand_height(deep, y)))], "mouth": [round(v) for v in pixel((mouth, y, sand_height(mouth, y)))],
                                "roof": round(pixel((3.3, d - 0.5, 1.4))[1])}}
    print("GROTTO", len(big), "large corals,", filled, "small ones,", sum(len(s.verts) for s in soups.values()), "vertices")
    return objects


STRUCTURES = {"arch": arch, "bommie": bommie, "grotto": grotto}
ROCK = kit.rock_material()
CORAL = kit.materials()
sand = build_sand()
wall = build_wall()

# ---- render ----------------------------------------------------------------------------
def soften(path, haze=0.07, edge=28):
    """The sand catches a faint shade far beyond a structure. Drop that haze and fade whatever
    shadow is left toward the sides and bottom of the picture, so it has no visible edge."""
    import numpy as np
    pixels = rig.read_pixels(path)
    alpha = np.clip((pixels[..., 3] - haze) / (1 - haze), 0, 1)
    h, w = alpha.shape
    ramp = np.minimum(np.minimum(np.arange(w), np.arange(w)[::-1])[None, :], (np.arange(h)[::-1])[:, None]) / edge
    solid = alpha > 0.97
    alpha = np.where(solid, alpha, alpha * np.clip(ramp, 0, 1))
    pixels[..., 3] = alpha
    rig.write_pixels(path, pixels)


built = {name: make() for name, make in STRUCTURES.items() if ONLY in (None, name)}

if ONLY is None:
    # The plate: no reef in it.
    for objects in built.values():
        for obj in objects:
            obj.hide_render = True
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 95
    rig.render(scene, OUT / "plate.jpg")

# Each structure alone: the sand only catches its shadow and the water is left out.
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
sand.is_shadow_catcher = True
wall.hide_render = True
for name, objects in built.items():
    for other_objects in built.values():
        for obj in other_objects:
            obj.hide_render = other_objects is not objects
    x0, x1, y0, y1 = rig._bounds(cam, objects)
    left, right = max(0, int(WIDTH * 50 + x0 * 100) - 16), min(int(WIDTH * 100), int(WIDTH * 50 + x1 * 100) + 60)
    top, bottom = max(0, int(HEIGHT * 50 - y1 * 100) - 16), min(int(HEIGHT * 100), int(HEIGHT * 50 - y0 * 100) + 30)
    rig.crop_to(scene, (left, top, right, bottom))
    rig.render(scene, OUT / f"{name}.png")
    rig.uncrop(scene)
    soften(OUT / f"{name}.png")
    (OUT / f"{name}.json").write_text(json.dumps({"x": left, "y": top, "w": right - left, "h": bottom - top, **NOTES.get(name, {})}) + "\n")
    print("STRUCTURE", name, "at", left, top, "size", right - left, bottom - top)
