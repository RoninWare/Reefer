"""Bake intermediate yellow tang headings with Reef Glass's mesh renderer."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream/reef_glass_roku_screensaver"
sys.path.insert(0, str(UPSTREAM / "tools"))
import fishviews

scene = json.loads((ROOT / "app/scenes/tank.json").read_text())
species = scene["species"]["yellowtang"]
headings = species["views"]["deg"]
fishviews.ANGLES = sorted(headings + [
    (a + b) / 2 for a, b in zip(headings, headings[1:]) if b - a >= 4
])
mesh = UPSTREAM / "gen/meshes/yellowtang.ply"
renderer = fishviews.Renderer(mesh, 1024, fat=1.2)
renderer.set_photo(mesh.with_name("yellowtang_full.png"))
out = ROOT / "authoring/tang_turns"
out.mkdir(exist_ok=True)
with TemporaryDirectory() as work:
    fishviews.IMAGES = Path(work)
    fishviews.SCENE = Path(work) / "tank.json"
    fishviews.SCENE.write_text(json.dumps({"species": {"yellowtang": species}}))
    fishviews.export_views(renderer, "yellowtang")
    views = json.loads(fishviews.SCENE.read_text())["species"]["yellowtang"]["views"]
    for index in range(views["pages"]):
        name = f"yellowtang_atlas{index}.png"
        (out / name).write_bytes((Path(work) / name).read_bytes())
    (out / "views.json").write_text(json.dumps(views, separators=(",", ":")) + "\n")
