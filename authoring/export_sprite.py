"""Render the active camera to <blend filename>.png beside its editable source."""
from pathlib import Path
import bpy

out = Path(bpy.data.filepath).with_suffix(".png")
scene = bpy.context.scene
if not scene.camera:
    raise ValueError("Set an active camera for the sprite.")
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.render.filepath = str(out)
bpy.ops.render.render(write_still=True)
