"""Generate the original candy ornament and its portrait render rig in Blender."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

out = Path(__file__).resolve().with_name("candy_tree.blend")
if out.exists():
    raise FileExistsError(f"Preserving editable model: {out}")
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
scene = bpy.context.scene
tau = math.tau


def candy(name, color, roughness=0.29):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Coat Weight"].default_value = 0.24
    return mat


def mesh(name, vertices, faces, materials):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    for mat in materials:
        data.materials.append(mat)
    return obj


mint = candy("Evergreen mint", (0.017, 0.28, 0.13))
cream = candy("Vanilla icing", (0.97, 0.87, 0.69))
berry = candy("Cherry pulled sugar", (0.58, 0.012, 0.032))
gold = candy("Amber sugar", (1, 0.51, 0.041))
# A short peppermint sweet anchors the tree on the sand.
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.32, depth=0.20, location=(0, 0, 0.10))
base = bpy.context.object
base.name = "Peppermint foot"
for mat in (cream, berry):
    base.data.materials.append(mat)
for face in base.data.polygons:
    if len(face.vertices) == 4:
        face.material_index = (face.index // 4) % 2
bevel = base.modifiers.new("Rounded candy edge", "BEVEL")
bevel.width, bevel.segments = 0.035, 3

for tier, (bottom, radius, height) in enumerate([(0.20, 0.70, 0.92), (0.80, 0.54, 0.80), (1.34, 0.39, 0.73)]):
    verts, faces = [], []
    rings, sides = 26, 96
    for j in range(rings):
        t = j / (rings-1)
        for i in range(sides):
            a = tau*i/sides
            ripple = math.sin(9*a - 2*t + tier)
            r = radius * ((1-t)**1.24 * 0.985 + 0.015) * (1 + 0.045*ripple)
            z = bottom + height*t + 0.039*ripple*(1-t)**3
            verts.append((r*math.cos(a), r*math.sin(a), z))
            if j:
                k = j*sides+i
                n = j*sides+(i+1)%sides
                faces.append((k-sides,n-sides,n,k))
    faces += [tuple(reversed(range(sides))), tuple(range((rings-1)*sides,rings*sides))]
    obj = mesh(f"Mint swirl {tier+1}", verts, faces, [mint,cream])
    for face in obj.data.polygons:
        face.use_smooth = True
        if face.index < sides:
            face.material_index = 1

    # Lay two sugar strands around each tier, twisted around one another.
    for strand, material in enumerate((berry, cream)):
        curve = bpy.data.curves.new("Twisted garland", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = 0.024
        curve.bevel_resolution = 3
        spline = curve.splines.new("POLY")
        spline.points.add(255)
        for i, point in enumerate(spline.points):
            u = i/255
            t = 0.10 + 0.58*u
            a = tau*(1.2*u+0.28*tier)
            twist = tau*12*u + strand*math.pi
            ripple = math.sin(9*a - 2*t + tier)
            r = radius*((1-t)**1.24*0.985+0.015)*(1+0.045*ripple) + 0.018 + 0.016*math.cos(twist)
            z = bottom + height*t + 0.039*ripple*(1-t)**3 + 0.016*math.sin(twist)
            point.co = (r*math.cos(a), r*math.sin(a), z, 1)
        obj = bpy.data.objects.new(material.name + " garland", curve)
        scene.collection.objects.link(obj)
        curve.materials.append(material)

# A double-sided, faceted five-point boiled-sugar star.
vertices = [(0,-0.088,2.18),(0,0.088,2.18)]
faces = []
for i in range(10):
    a = tau*i/10
    radius = 0.205 if i%2 == 0 else 0.094
    vertices.append((radius*math.sin(a),0,2.18+radius*math.cos(a)))
    faces.extend([(0,2+(i+1)%10,2+i),(1,2+i,2+(i+1)%10)])
star = mesh("Star topper", vertices, faces, [gold])
shader = gold.node_tree.nodes.get("Principled BSDF")
shader.inputs["Emission Color"].default_value = (1.0, 0.67, 0.19, 1.0)
shader.inputs["Emission Strength"].default_value = 0.45

# Grow upward from the peppermint base while preserving the horizontal footprint.
for obj in scene.objects:
    if obj != star:
        obj.scale.z *= 1.26
        obj.location.z *= 1.26
star.location.z = 0.55


def aim(obj):
    obj.rotation_euler = (Vector((0,0,1.45))-obj.location).to_track_quat("-Z","Y").to_euler()


bpy.ops.object.camera_add(location=(0,-6,2.47))
camera = bpy.context.object
aim(camera)
camera.data.type, camera.data.ortho_scale = "ORTHO", 3.325
scene.camera = camera
for pos, power, color in [((-3,-4,5),420,(1,0.93,0.84)),((2,1,4),490,(0.55,0.83,1))]:
    bpy.ops.object.light_add(type="AREA", location=pos)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = power,3,color
    aim(light)
scene.world.color = (0.18,0.23,0.28)
scene.render.engine = "CYCLES"
scene.cycles.samples = 32
scene.render.resolution_x, scene.render.resolution_y = 252,450
scene.render.resolution_percentage = 100
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.render.filepath = "//candy_tree.png"
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.region_3d.view_perspective = "CAMERA"
bpy.ops.wm.save_as_mainfile(filepath=str(out))
