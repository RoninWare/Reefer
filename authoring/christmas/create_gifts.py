"""Build two clusters of wrapped gifts and render each as a sprite.

    blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_gifts.py

Writes gifts.blend (editable; one collection per cluster), gifts_hearth.png and gifts_tree.png.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig
from rig import Graph, TAU

OUT = rig.HERE / "gifts.blend"
rig.guard(OUT)
scene = rig.reset(samples=224)


# ---- wrapping paper and ribbon ---------------------------------------------------------
def paper(name, kind, a, b=None, scale=9.0, foil=False):
    mat = rig.material(name, a, 0.24 if foil else 0.42, Coat_Weight=0.35, Metallic=0.85 if foil else 0.0)
    g = Graph(mat)
    uv = g.node("ShaderNodeUVMap").outputs["UV"]
    if kind == "stripes":
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL", wave_profile="SIN")
        wave.inputs["Scale"].default_value = scale
        g.set(wave.inputs["Vector"], uv)
        g.to("Base Color", g.mix(g.math("SMOOTHSTEP", 0.44, 0.56, wave.outputs["Fac"]), a, b))
    elif kind == "dots":
        dots = g.node("ShaderNodeTexVoronoi", voronoi_dimensions="2D", feature="F1")
        dots.inputs["Scale"].default_value = scale
        dots.inputs["Randomness"].default_value = 0.0
        g.set(dots.inputs["Vector"], uv)
        g.to("Base Color", g.mix(g.math("SMOOTHSTEP", 0.30, 0.24, dots.outputs["Distance"]), a, b))
    elif kind == "plaid":
        bands = []
        for direction in ("X", "Y"):
            wave = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction=direction, wave_profile="SIN")
            wave.inputs["Scale"].default_value = scale
            g.set(wave.inputs["Vector"], uv)
            bands.append(g.math("SMOOTHSTEP", 0.62, 0.74, wave.outputs["Fac"]))
        both = g.math("MAXIMUM", bands[0], bands[1])
        cross = g.math("MULTIPLY", bands[0], bands[1])
        g.to("Base Color", g.mix(cross, g.mix(both, a, b), (0.95, 0.80, 0.30)))
    # Paper never lies perfectly flat: a faint crinkle catches the light.
    crinkle = g.noise(g.coords(), scale=11, detail=3, roughness=0.6).outputs["Fac"]
    g.bump(crinkle, strength=0.16 if foil else 0.10, distance=0.02)
    return mat


RED_STRIPE = paper("Candy stripe", "stripes", (0.62, 0.012, 0.024), (0.93, 0.92, 0.88), 7.5)
GREEN_DOT = paper("Holly dots", "dots", (0.015, 0.25, 0.085), (0.92, 0.90, 0.80), 7.0)
BLUE_DOT = paper("Snowfall", "dots", (0.03, 0.13, 0.42), (0.86, 0.92, 0.98), 9.0)
PLAID = paper("Tartan", "plaid", (0.50, 0.015, 0.03), (0.02, 0.17, 0.07), 5.0)
GOLD_FOIL = paper("Gold foil", "plain", (0.95, 0.60, 0.16), foil=True)
RED_PLAIN = paper("Berry red", "plain", (0.60, 0.012, 0.03))
TEAL = paper("Lagoon teal", "stripes", (0.02, 0.33, 0.36), (0.03, 0.44, 0.45), 10.0)
WHITE = paper("Pearl", "dots", (0.90, 0.89, 0.85), (0.72, 0.03, 0.05), 6.0)
PURPLE = paper("Plum foil", "plain", (0.30, 0.04, 0.38), foil=True)

R_GOLD = rig.material("Gold ribbon", (1.0, 0.66, 0.18), 0.26, Metallic=1.0)
R_RED = rig.material("Red ribbon", (0.66, 0.01, 0.02), 0.30, Coat_Weight=0.5)
R_WHITE = rig.material("White ribbon", (0.93, 0.93, 0.90), 0.34, Coat_Weight=0.4)
R_GREEN = rig.material("Green ribbon", (0.02, 0.33, 0.10), 0.30, Coat_Weight=0.5)
R_SILVER = rig.material("Silver ribbon", (0.82, 0.86, 0.90), 0.22, Metallic=1.0)


def box(name, size, mats, collection):
    """A box about its own centre with a real-size UV on every face, so patterns keep their scale."""
    obj = rig.add_mesh(scene, name, rig.box_verts((0, 0, 0), size), rig.BOX_FACES, mats)
    layer = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        axis = max(range(3), key=lambda i: abs(poly.normal[i]))
        u, v = [i for i in range(3) if i != axis]
        for loop in poly.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            layer.data[loop].uv = (co[u] + axis * 0.37, co[v] + axis * 0.21)
    scene.collection.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def gift(collection, at, size, yaw, wrap, ribbon, lid=False, bow=1.0, stand=0.0, cross=True):
    w, d, h = size
    root = bpy.data.objects.new("Gift", None)
    collection.objects.link(root)
    root.location = (at[0], at[1], stand + h / 2)
    root.rotation_euler.z = math.radians(yaw)
    parts = []
    body = box("Gift box", size, [wrap], collection)
    rig.modifier(body, "BEVEL", width=0.014, segments=3)
    parts.append(body)
    top = h / 2
    if lid:
        cover = box("Gift lid", (w + 0.035, d + 0.035, 0.11), [wrap], collection)
        cover.location.z = h / 2 - 0.04
        rig.modifier(cover, "BEVEL", width=0.012, segments=3)
        parts.append(cover)
        top = h / 2 + 0.015
    band = 0.075 if max(w, d) > 0.5 else 0.055
    grow = 0.05 if lid else 0.014
    strips = [(w + grow, band, h + 0.014 + (0.03 if lid else 0))]
    if cross:
        strips.append((band, d + grow, h + 0.014 + (0.03 if lid else 0)))
    for i, dims in enumerate(strips):
        strip = box("Ribbon band", dims, [ribbon], collection)
        strip.location.z = 0.008 if lid else 0.0
        rig.modifier(strip, "BEVEL", width=0.004, segments=2)
        parts.append(strip)
    for part in parts:
        part.parent = root
    if bow:
        # The bow always faces the viewer, whatever way the box is turned.
        knot = Vector((at[0], at[1], stand + h + (0.025 if lid else 0.012) + 0.045 * bow))
        for part in rig.bow(scene, knot, ribbon, size=bow * 1.25, tails=False, lift=0.03):
            scene.collection.objects.unlink(part)
            collection.objects.link(part)
        for side in (-1, 1):
            # Two tails trailing down over the lid.
            tail = rig.smooth_path([knot, knot + Vector((side * 0.07 * bow, -0.05, -0.035)),
                                    knot + Vector((side * 0.13 * bow, -0.09, -0.05 * bow - 0.03))], 5)
            verts, faces, _ = rig.sweep(tail, [(0.028 * bow, 0.005)] * len(tail), 8)
            ribbon_tail = rig.add_mesh(scene, "Bow tail", verts, faces, [ribbon], smooth=True)
            scene.collection.objects.unlink(ribbon_tail)
            collection.objects.link(ribbon_tail)
    return stand + h


def cluster(name):
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    return collection


# By the hearth: a generous pile, tallest at the back.
hearth = cluster("Gifts by the hearth")
gift(hearth, (-0.52, 0.30), (0.82, 0.62, 0.58), 14, RED_PLAIN, R_GOLD, lid=True, bow=1.25)
top = gift(hearth, (0.42, 0.34), (0.66, 0.56, 0.46), -11, BLUE_DOT, R_SILVER, bow=0)
gift(hearth, (0.45, 0.33), (0.40, 0.36, 0.30), 21, GOLD_FOIL, R_RED, stand=top, bow=0.95)
gift(hearth, (-0.02, -0.02), (0.44, 0.44, 0.84), 33, GREEN_DOT, R_RED, lid=True, bow=1.0)
gift(hearth, (-0.66, -0.36), (0.46, 0.40, 0.34), -24, RED_STRIPE, R_GREEN, bow=0.9)
gift(hearth, (0.50, -0.36), (0.56, 0.42, 0.30), 9, PLAID, R_GOLD, bow=1.0)
gift(hearth, (1.04, 0.02), (0.34, 0.34, 0.50), 40, PURPLE, R_WHITE, lid=True, bow=0.8)

# Beside the tree: a pile stacked up against its foot, tallest at the back.
tree = cluster("Gifts under the tree")
gift(tree, (0.02, 0.66), (0.50, 0.46, 0.92), -6, RED_PLAIN, R_GOLD, lid=True, bow=1.1)
gift(tree, (0.70, 0.52), (0.48, 0.42, 0.50), 20, GREEN_DOT, R_RED, bow=0.9)
gift(tree, (-0.64, -0.34), (0.30, 0.28, 0.24), 30, PURPLE, R_SILVER, bow=0.75)
top = gift(tree, (-0.36, 0.20), (0.62, 0.50, 0.40), -16, TEAL, R_WHITE, lid=True, bow=0)
gift(tree, (-0.36, 0.18), (0.36, 0.32, 0.26), 12, RED_STRIPE, R_GOLD, stand=top + 0.015, bow=0.9)
gift(tree, (0.34, 0.22), (0.46, 0.44, 0.62), 28, WHITE, R_RED, bow=1.0)
gift(tree, (0.06, -0.28), (0.50, 0.38, 0.28), -8, GOLD_FOIL, R_GREEN, bow=0.95)
gift(tree, (0.78, -0.12), (0.34, 0.32, 0.30), 48, PLAID, R_GOLD, lid=True, bow=0.8)

rig.tank_light(scene)
cam = rig.camera(scene, elevation=9)
catcher = rig.ground(scene)
drifts = {hearth: rig.sand_drift(scene, -1.05, 1.22, -0.58, 0.62, seed=2.0, height=0.026),
          tree: rig.sand_drift(scene, -0.84, 1.02, -0.54, 0.92, seed=5.0, height=0.026)}
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))

for collection, filename in ((hearth, "gifts_hearth.png"), (tree, "gifts_tree.png")):
    for other in (hearth, tree):
        other.hide_render = other is not collection
        drifts[other].hide_render = other is not collection
    meshes = [o for o in collection.all_objects if o.type == "MESH"]
    w, h = rig.frame(scene, cam, meshes, pad=(8, 6, 22, 10))
    rig.render(scene, rig.HERE / filename)
    print("GIFTS", filename, w, h)
