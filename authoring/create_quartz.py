"""Build the original engraved quartz floor stone in Blender."""
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

out = Path(__file__).resolve().with_name("rellie_quartz.blend")
if out.exists():
    raise FileExistsError(out)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
scene = bpy.context.scene
rng = random.Random(46)


def mineral(name, colors, roughness, transmission, opacity=1.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*colors[1], 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Transmission Weight"].default_value = transmission
    shader.inputs["IOR"].default_value = 1.54
    shader.inputs["Alpha"].default_value = opacity
    tex = nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 2.8
    tex.inputs["Detail"].default_value = 4.2
    tex.inputs["Distortion"].default_value = 0.42
    ramp = nodes.new("ShaderNodeValToRGB")
    stops = ramp.color_ramp.elements
    stops[0].position, stops[0].color = 0.18, (*colors[0], 1)
    stops[1].position, stops[1].color = 0.80, (*colors[2], 1)
    stops.new(0.50).color = (*colors[1], 1)
    stops.new(0.56).color = (*colors[2], 1)
    links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    return mat


polish = mineral("Polished milky quartz", [(0.22,0.42,0.50),(0.51,0.72,0.76),(0.83,0.92,0.91)], 0.14, 0.61, 0.33)
fracture = mineral("Blue-grey fracture planes", [(0.13,0.27,0.35),(0.31,0.49,0.56),(0.73,0.83,0.83)], 0.24, 0.42, 0.49)
cut = mineral("Recess · rough smoky quartz", [(0.035,0.070,0.083),(0.075,0.13,0.15),(0.13,0.22,0.23)], 0.64, 0.02)


def mesh(name, vertices, faces):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


# The sawn face is planar; the uneven shoulders break into smaller cleavage facets.
outline = [(-1.95,0.25),(-1.78,0.65),(-1.29,0.85),(-0.47,0.88),(0.20,0.83),
           (0.93,0.91),(1.52,0.78),(1.85,0.51),(1.94,0.13),(1.65,-0.32),
           (0.87,-0.40),(-0.12,-0.43),(-1.30,-0.42),(-1.74,-0.31)]
n = len(outline)
verts = [(x,-0.44,z) for x,z in outline]
for y,scale in [(-0.19,1.14),(0.35,1.08),(0.84,0.75)]:
    for x,z in outline:
        verts.append((x*scale+rng.uniform(-0.08,0.08),y+rng.uniform(-0.10,0.10),
                      max(-0.52,z*scale+rng.uniform(-0.10,0.10))))
faces = [tuple(reversed(range(n)))]
for ring in range(3):
    for i in range(n):
        a = ring*n+i
        b = ring*n+(i+1)%n
        faces.extend([(a,b,b+n),(a,b+n,a+n)])
faces.append(tuple(range(3*n,4*n)))
stone = mesh("Rellie Reef · cut quartz", verts, faces)
for mat in (polish,fracture,cut):
    stone.data.materials.append(mat)
for face in list(stone.data.polygons)[1:]:
    face.material_index = 1

# Convert the exact inscription into a solid cutter. Material transfer shades
# the excavated floor and walls. The original cut remains editable as a modifier.
bpy.ops.object.text_add(rotation=(math.pi/2,0,0))
letters = bpy.context.object
letters.name = "Engraving tool · Rellie Reef"
letters.data.body = "Rellie Reef"
letters.data.align_x = "CENTER"
letters.data.align_y = "CENTER"
font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
letters.data.font = bpy.data.fonts.load(str(font))
letters.data.resolution_u = 12
letters.data.extrude = 0.19
bpy.context.view_layer.update()
scale = 3.06/letters.dimensions.x
letters.scale = (scale,scale,1)
letters.location = (0,-0.28,0.20)
bpy.ops.object.convert(target="MESH")
letters.data.materials.append(cut)
wall = mineral("Freshly chiselled walls", [(0.17,0.28,0.30),(0.31,0.46,0.48),(0.58,0.70,0.70)], 0.42, 0.10)
letters.data.materials.append(wall)
for face in letters.data.polygons:
    if abs(face.normal.z) < 0.5:
        face.material_index = 1
boolean = stone.modifiers.new("Deep inscription · 0.35 units", "BOOLEAN")
boolean.object = letters
boolean.operation = "DIFFERENCE"
boolean.solver = "EXACT"
boolean.material_mode = "TRANSFER"
letters.hide_render = True
letters.hide_set(True)
bevel = stone.modifiers.new("Light on cut edges", "BEVEL")
bevel.width = 0.009
bevel.segments = 2
bevel.harden_normals = True

# A few naturally terminated points grow from the back shoulder.
for idx,(x,y,z,r,h,lean) in enumerate([(1.44,0.46,0.62,0.19,0.68,0.30),(1.78,0.35,0.46,0.15,0.54,0.45),
                                       (1.19,0.63,0.68,0.14,0.45,-0.12),(-1.72,0.36,0.43,0.13,0.37,-0.32)]):
    v = []
    phase = rng.random()
    for height,radius in [(0,r),(h*0.67,r*0.91)]:
        for i in range(6):
            a = i*math.tau/6 + phase
            v.append((radius*math.cos(a)+height*lean,radius*math.sin(a),height))
    v.append((h*lean+r*0.18,0,h))
    f = [tuple(reversed(range(6)))]
    for i in range(6):
        j = (i+1)%6
        f.extend([(i,j,6+j,6+i),(6+i,6+j,12)])
    point = mesh(f"Quartz termination {idx+1}",v,f)
    point.location = (x,y,z)
    point.data.materials.append(polish)

target = Vector((0,0,0.40))
def aim(obj):
    obj.rotation_euler = (target-obj.location).to_track_quat("-Z","Y").to_euler()

bpy.ops.object.camera_add(location=(0.34,-7.5,2.0))
cam = bpy.context.object
aim(cam)
cam.data.type, cam.data.ortho_scale = "ORTHO",4.68
scene.camera = cam
for pos,energy,size,color in [((-3,-3,5),520,2.8,(0.94,0.98,1)),((2,2,3),580,2.2,(0.63,0.84,1)),((3,-3,1),58,3,(0.8,0.94,1))]:
    bpy.ops.object.light_add(type="AREA",location=pos)
    light=bpy.context.object
    light.data.energy,light.data.size,light.data.color=energy,size,color
    aim(light)
scene.world.color=(0.16,0.23,0.27)
scene.render.engine="CYCLES"
scene.cycles.samples=96
scene.cycles.use_denoising=True
scene.render.resolution_x, scene.render.resolution_y=376,176
scene.render.resolution_percentage=100
scene.render.image_settings.color_mode="RGBA"
scene.render.film_transparent=True
scene.render.filepath="//rellie_quartz.png"
for area in bpy.context.screen.areas:
    if area.type=="VIEW_3D":
        area.spaces.active.region_3d.view_perspective="CAMERA"
bpy.ops.wm.save_as_mainfile(filepath=str(out))
