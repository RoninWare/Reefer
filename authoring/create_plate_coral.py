"""Create an editable Montipora-inspired colony. Run with Blender --factory-startup."""
import argparse
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--seed", type=int, default=17)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
out = args.output.resolve()
if out.exists():
    raise FileExistsError(f"Choose a new file to preserve existing edits: {out}")
rng = random.Random(args.seed)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
scene = bpy.context.scene

# Pigment toward the rims and fine, raised corallites across each plate.
mat = bpy.data.materials.new("Copper tissue · pale growing rim")
mat.use_nodes = True
nodes = mat.node_tree.nodes
link = mat.node_tree.links.new
shader = nodes.get("Principled BSDF")
shader.inputs["Roughness"].default_value = 0.77
attr = nodes.new("ShaderNodeAttribute")
attr.attribute_name = "pigment"
link(attr.outputs["Color"], shader.inputs["Base Color"])
cells = nodes.new("ShaderNodeTexVoronoi")
cells.inputs["Scale"].default_value = 82
bump = nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.38
bump.inputs["Distance"].default_value = 0.018
link(cells.outputs["Distance"], bump.inputs["Height"])
link(bump.outputs["Normal"], shader.inputs["Normal"])

def plate(index, center, size, direction):
    rings, sectors = 22, 128
    verts = [(0, 0, 0)]
    colors = [(0.24, 0.043, 0.032, 1)]
    faces = []
    phase = rng.uniform(0, 2 * math.pi)
    for ring in range(1, rings + 1):
        r = ring / rings
        for i in range(sectors):
            a = math.tau * i / sectors
            wave = math.sin(5*a + phase) + 0.36 * math.sin(13*a - phase)
            radius = r * size * (1 + 0.085 * wave)
            z = size * (0.37*r*r + 0.15*r*math.cos(a-direction) + 0.054*r*r*wave)
            verts.append((radius*math.cos(a), radius*0.88*math.sin(a), z))
            rim = max(0, (r - 0.89) / 0.11) ** 2
            ridges = 0.035 * math.sin(47*a + 5*r)*r
            colors.append((0.33 + 0.17*r + 0.33*rim + ridges,
                           0.053 + 0.065*r + 0.36*rim, 0.047 + 0.02*r + 0.22*rim, 1))
            cur = 1 + (ring-1)*sectors + i
            nxt = 1 + (ring-1)*sectors + (i+1)%sectors
            faces.append((0, cur, nxt) if ring == 1 else
                         (cur-sectors, cur, nxt, nxt-sectors))
    mesh = bpy.data.meshes.new(f"Plate {index:02}")
    mesh.from_pydata(verts, [], faces)
    color = mesh.color_attributes.new(name="pigment", type="FLOAT_COLOR", domain="POINT")
    for item, value in zip(color.data, colors):
        item.color = value
    for face in mesh.polygons:
        face.use_smooth = True
    obj = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(obj)
    obj.location = center
    obj.data.materials.append(mat)
    obj.modifiers.new("Skeleton thickness", "SOLIDIFY").thickness = size*0.037
    return verts

points = []
for level, (count, radius, size, height) in enumerate([(7,0.69,0.65,0), (5,0.43,0.57,0.23), (3,0.23,0.4,0.43), (1,0,0.32,0.58)]):
    for i in range(count):
        a = math.tau*i/count + level*0.75 + rng.uniform(-0.12,0.12)
        center = Vector((radius*math.cos(a),radius*math.sin(a),height + rng.uniform(-0.05,0.05)))
        points.extend(center + Vector(v) for v in plate(len(scene.objects), center, size*rng.uniform(0.87,1.12), a))

def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z","Y").to_euler()

target = Vector((0,0,0.33))
bpy.ops.object.camera_add(location=(0,-5,2.25))
camera = bpy.context.object
aim(camera,target)
scene.camera = camera
camera.data.type = "ORTHO"
scene.render.resolution_x, scene.render.resolution_y = 240, 150
scene.render.resolution_percentage = 100
bpy.context.view_layer.update()
local = [camera.matrix_world.inverted() @ v for v in points]
xmin, xmax = min(v.x for v in local), max(v.x for v in local)
ymin, ymax = min(v.y for v in local), max(v.y for v in local)
camera.location += camera.rotation_euler.to_matrix() @ Vector(((xmin+xmax)/2,(ymin+ymax)/2,0))
camera.data.ortho_scale = 1.10 * max(xmax-xmin,(ymax-ymin)*240/150)
for pos, power, color in [((-3,-4,5),580,(1,0.9,0.80)),((2,1,3),470,(0.50,0.82,1.0))]:
    bpy.ops.object.light_add(type="AREA", location=pos)
    light = bpy.context.object
    light.data.energy, light.data.color, light.data.size = power,color,3
    aim(light,target)
scene.world.color = (0.18,0.23,0.28)
scene.render.engine = "CYCLES"
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = "//" + out.stem + ".png"
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.region_3d.view_perspective = "CAMERA"
bpy.ops.wm.save_as_mainfile(filepath=str(out))
