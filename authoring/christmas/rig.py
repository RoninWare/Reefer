"""Shared Blender rig for the Christmas reef set: pixel scale, tank lighting, camera and mesh helpers.

Every model in this folder is built in Blender units where one unit is PX tank pixels, and is
rendered through an orthographic camera framed to whole pixels, so a sprite's size and the
positions of its anchors (chimney mouth, bulbs, eel jaw) come out in tank coordinates.
"""
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

PX = 100.0
HERE = Path(__file__).resolve().parent
TAU = math.tau


def script_args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def guard(blend, force_flag="--overwrite"):
    """Hand edits to a saved model are kept unless the caller asks to regenerate it."""
    if blend.exists() and force_flag not in script_args():
        raise FileExistsError(f"Preserving editable model: {blend} (pass -- {force_flag} to regenerate)")


def reset(samples=160):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.filter_width = 1.3
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    return scene


def tank_light(scene, key=3.2, sky=1.0, sand=0.55):
    """Aquarium light: a broad cool key from above the front glass, blue water all round and
    pale sand bouncing light back up from below."""
    world = bpy.data.worlds.new("Tank water")
    world.use_nodes = True
    scene.world = world
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    remap = nt.nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value = -1
    remap.inputs["From Max"].default_value = 1
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    stops = [
        (0.0, (0.80 * sand, 0.93 * sand, 1.0 * sand, 1)),
        (0.42, (0.12, 0.32, 0.46, 1)),
        (0.62, (0.10, 0.34, 0.56, 1)),
        (1.0, (0.62 * sky, 0.86 * sky, 1.0 * sky, 1)),
    ]
    elements = ramp.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (pos, color) in zip(elements, stops):
        element.position, element.color = pos, color
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], remap.inputs["Value"])
    nt.links.new(remap.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])

    sun = bpy.data.lights.new("Surface light", "SUN")
    sun.energy, sun.angle, sun.color = key, math.radians(14), (0.84, 0.95, 1.0)
    obj = bpy.data.objects.new("Surface light", sun)
    scene.collection.objects.link(obj)
    obj.rotation_euler = (math.radians(38), math.radians(-14), math.radians(-18))
    return obj


def camera(scene, elevation=9.0, distance=30.0):
    data = bpy.data.cameras.new("Sprite camera")
    data.type = "ORTHO"
    data.clip_start, data.clip_end = 0.1, 200
    cam = bpy.data.objects.new("Sprite camera", data)
    scene.collection.objects.link(cam)
    e = math.radians(elevation)
    cam.location = (0, -distance * math.cos(e), distance * math.sin(e))
    cam.rotation_euler = (math.radians(90) - e, 0, 0)
    scene.camera = cam
    return cam


def _bounds(cam, objects):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    inv = cam.matrix_world.inverted()
    xs, ys = [], []
    for ob in objects:
        ev = ob.evaluated_get(deps)
        try:
            mesh = ev.to_mesh()
        except RuntimeError:
            continue
        if mesh is None:
            continue
        m = inv @ ev.matrix_world
        for v in mesh.vertices:
            p = m @ v.co
            xs.append(p.x)
            ys.append(p.y)
        ev.to_mesh_clear()
    return min(xs), max(xs), min(ys), max(ys)


def frame(scene, cam, objects, pad=(6, 6, 6, 6), px=PX):
    """Fit the camera to the objects on a whole-pixel grid. pad = left, top, right, bottom px."""
    x0, x1, y0, y1 = _bounds(cam, objects)
    left, top, right, bottom = pad
    w = math.ceil((x1 - x0) * px) + left + right
    h = math.ceil((y1 - y0) * px) + top + bottom
    scene.render.resolution_x, scene.render.resolution_y = w, h
    cam.data.ortho_scale = max(w, h) / px
    # Camera-space centre of the padded picture, moved onto the camera's own axis.
    cx = x0 - left / px + w / (2 * px)
    cy = y1 + top / px - h / (2 * px)
    cam.location = cam.matrix_world @ Vector((cx, cy, 0))
    bpy.context.view_layer.update()
    return w, h


def project(scene, cam, point, px=PX):
    """Sprite pixel (x from the left, y from the top) of a world point."""
    p = cam.matrix_world.inverted() @ Vector(point)
    return (round(scene.render.resolution_x / 2 + p.x * px, 2),
            round(scene.render.resolution_y / 2 - p.y * px, 2))


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def crop_to(scene, box):
    """Render only box = (x0, y0, x1, y1) in sprite pixels (y from the top) and crop to it."""
    w, h = scene.render.resolution_x, scene.render.resolution_y
    x0, y0, x1, y1 = box
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    scene.render.border_min_x, scene.render.border_max_x = x0 / w, x1 / w
    scene.render.border_min_y, scene.render.border_max_y = 1 - y1 / h, 1 - y0 / h


def uncrop(scene):
    scene.render.use_border = False
    scene.render.use_crop_to_border = False


def ground(scene, size=40):
    """An invisible sand plane that only receives the model's contact shadow."""
    mesh = bpy.data.meshes.new("Sand shadow")
    s = size / 2
    mesh.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new("Sand shadow", mesh)
    scene.collection.objects.link(obj)
    obj.is_shadow_catcher = True
    mat = material("Sand", (0.72, 0.80, 0.82), 0.9)
    mesh.materials.append(mat)
    return obj


# ---- materials -------------------------------------------------------------------------

def material(name, color=(0.8, 0.8, 0.8), roughness=0.5, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color[:3], 1)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color[:3], 1)
    shader.inputs["Roughness"].default_value = roughness
    for key, value in inputs.items():
        socket = shader.inputs[key.replace("_", " ")]
        socket.default_value = (*value, 1) if isinstance(value, tuple) and len(value) == 3 else value
    return mat


class Graph:
    """Small wrapper for building shader node graphs without the boilerplate."""

    def __init__(self, mat):
        self.tree = mat.node_tree
        self.shader = self.tree.nodes.get("Principled BSDF")
        self.output = next(n for n in self.tree.nodes if n.type == "OUTPUT_MATERIAL")

    def node(self, kind, **props):
        node = self.tree.nodes.new(kind)
        for key, value in props.items():
            setattr(node, key, value)
        return node

    def set(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, socket)
        elif isinstance(value, (tuple, list)) and len(value) == 3 and socket.type == "RGBA":
            socket.default_value = (*value, 1)
        else:
            socket.default_value = value

    def math(self, op, a, b=None, c=None, clamp=False):
        if op == "SMOOTHSTEP":      # (edge0, edge1, value); the Math node has no smoothstep
            node = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
            self.set(node.inputs["From Min"], a)
            self.set(node.inputs["From Max"], b)
            self.set(node.inputs["Value"], c)
            return node.outputs["Result"]
        node = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for socket, value in zip(node.inputs, (a, b, c)):
            if value is not None:
                self.set(socket, value)
        return node.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        node = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.set(node.inputs["Factor"], fac)
        self.set(node.inputs["A"], a)
        self.set(node.inputs["B"], b)
        return node.outputs["Result"]

    def ramp(self, fac, stops, interpolation="LINEAR"):
        node = self.node("ShaderNodeValToRGB")
        node.color_ramp.interpolation = interpolation
        elements = node.color_ramp.elements
        while len(elements) < len(stops):
            elements.new(0.5)
        for element, (pos, color) in zip(elements, stops):
            element.position = pos
            element.color = color if len(color) == 4 else (*color, 1)
        self.set(node.inputs["Fac"], fac)
        return node

    def noise(self, vector=None, scale=5.0, detail=3.0, roughness=0.55, dims="3D", w=None, distortion=0.0):
        node = self.node("ShaderNodeTexNoise", noise_dimensions=dims)
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = roughness
        node.inputs["Distortion"].default_value = distortion
        if vector is not None:
            self.set(node.inputs["Vector"], vector)
        if w is not None:
            self.set(node.inputs["W"], w)
        return node

    def attribute(self, name):
        return self.node("ShaderNodeAttribute", attribute_name=name)

    def coords(self, kind="Object"):
        return self.node("ShaderNodeTexCoord").outputs[kind]

    def bump(self, height, strength=0.3, distance=0.02, normal=None):
        node = self.node("ShaderNodeBump")
        node.inputs["Strength"].default_value = strength
        node.inputs["Distance"].default_value = distance
        self.set(node.inputs["Height"], height)
        if normal is not None:
            self.set(node.inputs["Normal"], normal)
        self.tree.links.new(node.outputs[0], self.shader.inputs["Normal"])
        return node.outputs[0]

    def to(self, name, value):
        self.set(self.shader.inputs[name], value)


# ---- meshes ----------------------------------------------------------------------------

def add_mesh(scene, name, verts, faces, materials=(), smooth=False, sharp_angle=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for mat in materials:
        mesh.materials.append(mat)
    if smooth:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        if sharp_angle is not None:
            mesh.set_sharp_from_angle(angle=math.radians(sharp_angle))
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def point_attribute(obj, name, values):
    attr = obj.data.attributes.new(name, "FLOAT", "POINT")
    attr.data.foreach_set("value", values)


def modifier(obj, kind, name=None, **props):
    mod = obj.modifiers.new(name or kind.title(), kind)
    for key, value in props.items():
        setattr(mod, key, value)
    return mod


def box_verts(center, size, rot=None):
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    corners = [Vector((x * sx, y * sy, z * sz)) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    if rot is not None:
        corners = [rot @ c for c in corners]
    return [(c.x + cx, c.y + cy, c.z + cz) for c in corners]


BOX_FACES = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


class Blocks:
    """Many separate boxes (bricks, slats) gathered into one mesh. Each block carries its own
    point attributes (for example a colour 'tone'), which survive bevelling."""

    def __init__(self, *names):
        self.names = names or ("tone",)
        self.verts, self.faces = [], []
        self.attrs = {name: [] for name in self.names}

    def _add(self, corners, values):
        n = len(self.verts)
        self.verts += corners
        self.faces += [tuple(n + i for i in f) for f in BOX_FACES]
        for name in self.names:
            self.attrs[name] += [values.get(name, 0.0)] * 8

    def box(self, center, size, rot=None, **values):
        self._add(box_verts(center, size, rot), values)

    def hexa(self, corners, **values):
        """Eight corners ordered like box_verts."""
        self._add([tuple(c) for c in corners], values)

    def build(self, scene, name, materials, bevel=0.006):
        obj = add_mesh(scene, name, self.verts, self.faces, materials)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        for name in self.names:
            point_attribute(obj, name, self.attrs[name])
        if bevel:
            modifier(obj, "BEVEL", width=bevel, segments=2, limit_method="ANGLE")
        return obj


def sweep(path, radii, sides=24, cap=True, twist=0.0):
    """A tube along path (list of Vector) with per-point (rx, ry) half-widths. Returns verts,
    faces and, per vertex, (u along the path 0..1, v around 0..1)."""
    n = len(path)
    tangents = []
    for i in range(n):
        a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    # Parallel transport keeps the cross-section from spinning along the bend.
    up = Vector((0, 0, 1))
    if abs(tangents[0].dot(up)) > 0.9:
        up = Vector((0, -1, 0))
    side = tangents[0].cross(up).normalized()
    frames = []
    for i, t in enumerate(tangents):
        if i:
            axis = tangents[i - 1].cross(t)
            if axis.length > 1e-8:
                side = Matrix.Rotation(tangents[i - 1].angle(t), 3, axis.normalized()) @ side
        side = (side - t * side.dot(t)).normalized()
        frames.append((side, t.cross(side).normalized()))
    lengths = [0.0]
    for i in range(1, n):
        lengths.append(lengths[-1] + (path[i] - path[i - 1]).length)
    total = lengths[-1] or 1.0
    verts, faces, uv = [], [], []
    for i, (p, (sx, sy), (rx, ry)) in enumerate(zip(path, frames, radii)):
        for k in range(sides):
            a = TAU * k / sides + twist * i
            verts.append(tuple(p + sx * (rx * math.cos(a)) + sy * (ry * math.sin(a))))
            uv.append((lengths[i] / total, k / sides))
            if i:
                j = (k + 1) % sides
                faces.append(((i - 1) * sides + k, (i - 1) * sides + j, i * sides + j, i * sides + k))
    if cap:
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple(range((n - 1) * sides, n * sides)))
    return verts, faces, uv


def smooth_path(points, steps=8):
    """Catmull-Rom through the control points."""
    pts = [Vector(p) for p in points]
    pts = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1:i + 3]
        for s in range(steps):
            t = s / steps
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-2])
    return out


def evergreen(scene, name, path, radius, mat, seed=0, per_unit=900, length=(0.07, 0.12), width=0.012):
    """Fir needles along a path: thin blades fanning out and forward from the stem."""
    rng = random.Random(seed)
    verts, faces, tone = [], [], []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        seg = b - a
        t = seg.normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(ref).normalized()
        v = t.cross(u)
        for _ in range(max(1, int(seg.length * per_unit))):
            p = a + seg * rng.random()
            ang = rng.uniform(0, TAU)
            out = u * math.cos(ang) + v * math.sin(ang)
            direction = (out + t * rng.uniform(-0.9, 0.9)).normalized()
            base = p + out * radius * rng.uniform(0.0, 0.5)
            ln = rng.uniform(*length) * (0.7 + radius * 3)
            tip = base + direction * ln
            wide = direction.cross(out if abs(direction.dot(out)) < 0.95 else t).normalized() * width / 2
            n = len(verts)
            verts += [tuple(base - wide), tuple(base + wide), tuple(tip)]
            faces.append((n, n + 1, n + 2))
            tone += [rng.random()] * 3
    obj = add_mesh(scene, name, verts, faces, [mat])
    point_attribute(obj, "tone", tone)
    return obj


def needle_material(name="Fir needles"):
    mat = material(name, (0.03, 0.2, 0.07), 0.55)
    g = Graph(mat)
    tone = g.attribute("tone").outputs["Fac"]
    ramp = g.ramp(tone, [(0.0, (0.012, 0.10, 0.045)), (0.6, (0.03, 0.22, 0.07)), (1.0, (0.10, 0.36, 0.10))])
    g.to("Base Color", ramp.outputs["Color"])
    g.to("Sheen Weight", 0.3)
    return mat



def bow(scene, center, mat, size=1.0, tails=True, lift=0.0):
    """A ribbon bow facing the camera: two loops, a knot and two tails. lift raises the loops
    for a bow sitting on top of a box."""
    cx, cy, cz = center
    parts = []
    for side in (-1, 1):
        loop = smooth_path([(cx, cy, cz), (cx + side * 0.07 * size, cy - 0.02, cz + (0.055 + lift) * size),
                            (cx + side * 0.125 * size, cy - 0.01, cz + (0.01 + lift) * size),
                            (cx + side * 0.07 * size, cy - 0.02, cz - (0.04 - lift * 0.6) * size), (cx, cy, cz)], 6)
        verts, faces, _ = sweep(loop, [(0.006 * size, 0.028 * size)] * len(loop), 10)
        parts.append(add_mesh(scene, "Bow loop", verts, faces, [mat], smooth=True))
        if tails:
            tail = smooth_path([(cx, cy, cz), (cx + side * 0.05 * size, cy - 0.01, cz - 0.10 * size),
                                (cx + side * 0.075 * size, cy, cz - 0.20 * size)], 5)
            verts, faces, _ = sweep(tail, [(0.005 * size, 0.024 * size)] * len(tail), 10)
            parts.append(add_mesh(scene, "Bow tail", verts, faces, [mat], smooth=True))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.026 * size, location=(cx, cy - 0.01, cz), segments=16, ring_count=8)
    knot = bpy.context.object
    knot.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    parts.append(knot)
    return parts


def sand_drift(scene, x0, x1, y0, y1, seed=0.0, height=0.034, reach=0.13):
    """Sand settled against a footprint. The mound is a holdout: the tank's own sand shows
    through the sprite there, so the model reads as bedded in rather than set on top."""
    nx, ny = 150, 70
    verts, faces = [], []
    for j in range(ny):
        for i in range(nx):
            x, y = x0 - 0.2 + (x1 - x0 + 0.4) * i / (nx - 1), y0 - 0.2 + (y1 - y0 + 0.4) * j / (ny - 1)
            away = max(x0 - x, x - x1, y0 - y, y - y1, 0.0)
            drift = (height + 0.65 * height * math.sin(6.1 * x + 1.3 + seed) * math.sin(4.3 * y + 0.4 + seed)
                     + 0.47 * height * math.sin(15.7 * x + 3.1 * y + seed) + 0.3 * height * math.sin(31 * x - 9 * y))
            verts.append((x, y, max(0.0, drift) * max(0.0, 1 - away / reach) - 0.001))
            if i and j:
                k = j * nx + i
                faces.append((k - nx - 1, k - nx, k, k - 1))
    sand = add_mesh(scene, "Sand drift", verts, faces)
    sand.is_holdout = True
    sand.visible_shadow = False
    return sand

# ---- sprite sheets ---------------------------------------------------------------------

def read_pixels(path):
    """Float RGBA rows from the top of a saved PNG, untouched by colour management."""
    import numpy as np
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "Non-Color"
    w, h = image.size
    data = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(data)
    bpy.data.images.remove(image)
    return data.reshape(h, w, 4)[::-1]


def write_pixels(path, rows):
    """Save float RGBA rows (top first, straight alpha) as an 8-bit PNG."""
    import numpy as np
    h, w = rows.shape[:2]
    image = bpy.data.images.new("sheet", w, h, alpha=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "STRAIGHT"
    image.pixels.foreach_set(np.ascontiguousarray(rows[::-1], dtype=np.float32).ravel())
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def pack_grid(paths, out, cols):
    """Equal-size frames packed row by row into one sheet; the frame files are removed."""
    import numpy as np
    frames = [read_pixels(p) for p in paths]
    h, w = frames[0].shape[:2]
    rows = math.ceil(len(frames) / cols)
    sheet = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
    for i, frame in enumerate(frames):
        sheet[i // cols * h:(i // cols + 1) * h, i % cols * w:(i % cols + 1) * w] = frame
    write_pixels(out, sheet)
    for p in paths:
        Path(p).unlink()
    return w, h
