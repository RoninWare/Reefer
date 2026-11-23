"""Serve the local BrightScript aquarium preview on loopback."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = HERE / "node_modules/brs-engine"
ART = ROOT / "authoring"
ROUTES = {
    "/": HERE / "index.html",
    "/lib/brs.api.js": ENGINE / "lib/brs.api.js",
    "/lib/brs.worker.js": ENGINE / "lib/brs.worker.js",
    "/assets/common.zip": ENGINE / "assets/common.zip",
}


def add_model(scene, contents, placement):
    name = placement["model"]
    if not name.isidentifier():
        raise ValueError(f"Invalid model name: {name}")
    asset = f"images/custom_{name}.png"
    data = (ART / f"{name}.png").read_bytes()
    x, y = placement["x"], placement["y"]
    with Image.open(BytesIO(data)) as image:
        if image.mode != "RGBA" or max(image.size) > 2048:
            raise ValueError(f"{name} needs an RGBA sprite no larger than 2048 px")
        alpha = image.getchannel("A")
    contents[asset] = data
    scene["pan"]["pieces"].append({"img": "pkg:/" + asset, "x": x, "y": y, "shadow": False})
    # Preserve baseline occupancy and extend it by one cell around the new silhouette.
    coral = scene["coral"]
    cell = coral["cell"]
    rows = [list(row) for row in coral["rows"]]
    for j in range(max(0, y // cell), min(len(rows), (y + alpha.height + cell - 1) // cell)):
        for i in range(max(0, x // cell), min(len(rows[j]), (x + alpha.width + cell - 1) // cell)):
            left, top = i * cell - x, j * cell - y
            hist = alpha.crop((left, top, left + cell, top + cell)).histogram()
            if sum(k * n for k, n in enumerate(hist)) > 0.1 * cell * cell * 255:
                for row in rows[max(0, j-1):j+2]:
                    for col in range(max(0, i-1), min(len(row), i+2)):
                        row[col] = "#"
    coral["rows"] = ["".join(row) for row in rows]


def insert_after(contents, module, anchor, addition):
    path = f"source/{module}.brs"
    if contents[path].count(anchor) != 1:
        raise ValueError(f"Unexpected integration point in {path}")
    contents[path] = contents[path].replace(anchor, anchor + b"\n" + addition)


def add_reef_motion(scene, contents, placements):
    contents["source/reef_motion.brs"] = (ROOT / "runtime/reef_motion.brs").read_bytes()
    for filename in ("star_glow.png", "anemone_current.png"):
        contents[f"images/{filename}"] = (ART / filename).read_bytes()
    tree = next((piece for piece in placements if piece["model"] == "candy_tree"), None)
    if tree is not None:
        scene["candyStar"] = {"x": tree["x"] + 126, "y": tree["y"] + 53}
    insert_after(contents, "reef", b"    FishMirrorMode(s)", b"    InitReefMotion(s)")
    insert_after(contents, "pan", b"    PanDrawPieces(s, screen, s.pan.near)", b"    DrawReefMotion(s, screen, t)")


def add_surface(contents):
    contents["source/surface.brs"] = (ROOT / "runtime/surface.brs").read_bytes()
    contents["images/surface_ripple.jpg"] = (ART / "surface_ripple.jpg").read_bytes()
    for name, anchor, replacement in [
        ("reef", b'    LogMemory("loaded")', b'    s.surface = LoadSurface()\n    LogMemory("loaded")'),
        ("pan", b"    PanDrawPieces(s, screen, s.pan.far)", b"    DrawSurface(s, screen, t)\n    PanDrawPieces(s, screen, s.pan.far)"),
    ]:
        path = f"source/{name}.brs"
        if contents[path].count(anchor) != 1:
            raise ValueError(f"Unexpected water surface integration point in {path}")
        contents[path] = contents[path].replace(anchor, replacement)


def enable_720p(contents):
    contents["source/draw720.brs"] = (HERE / "draw720.brs").read_bytes()
    contents["manifest"] = contents["manifest"].replace(b"ui_resolutions=fhd", b"ui_resolutions=hd")
    draw_calls = {
        b"DrawObject": b"PreviewObject",
        b"DrawScaledObject": b"PreviewScaled",
        b"DrawRotatedObject": b"PreviewRotated",
        b"DrawTransformedObject": b"PreviewTransformed",
        b"DrawRect": b"PreviewRect",
    }
    for module in ("main", "pan", "reef", "fish", "moray", "critters", "surface", "reef_motion"):
        path = f"source/{module}.brs"
        if path in contents:
            for method, wrapper in draw_calls.items():
                contents[path] = contents[path].replace(b"screen." + method + b"(", wrapper + b"(screen, ")
    contents["source/main.brs"] = contents["source/main.brs"].replace(
        b'CreateObject("roScreen", true, 1920, 1080)',
        b'CreateObject("roScreen", true, 1280, 720)',
    )


def add_tang_turns(scene, contents):
    directory = ART / "tang_turns"
    views = json.loads((directory / "views.json").read_text())
    scene["species"]["yellowtang"]["views"] = views
    for page in range(views["pages"]):
        filename = f"yellowtang_atlas{page}.png"
        contents[f"images/{filename}"] = (directory / filename).read_bytes()


def package(include_models, *, device=False, moving_water=True, preview_720=False, refined_tang=True):
    with ZipFile(ROOT / "baseline/reefglass-1.1.3.zip") as source:
        contents = {n: source.read(n) for n in source.namelist()}
    if device:
        contents["manifest"] = contents["manifest"].replace(b"screensaver_title=Reef Glass", b"screensaver_title=Rellie Reef")
    else:
        contents["source/preview.brs"] = b"sub Main()\n    RunScreenSaver()\nend sub\n"
    if include_models and moving_water:
        add_surface(contents)
    if include_models:
        scene = json.loads(contents["scenes/tank.json"])
        placements = json.loads((ART / "placements.json").read_text())
        for placement in placements:
            add_model(scene, contents, placement)
        add_reef_motion(scene, contents, placements)
        if refined_tang:
            add_tang_turns(scene, contents)
        contents["scenes/tank.json"] = json.dumps(scene).encode()
    if not device:
        if preview_720:
            enable_720p(contents)
        contents["source/main.brs"] = contents["source/main.brs"].replace(
            b"    screen.SetMessagePort(port)",
            b'    print "PREVIEW render target "; screen.GetWidth(); " x "; screen.GetHeight()\n'
            b"    screen.SetMessagePort(port)",
            1,
        )
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path == "/reef.zip":
                query = parse_qs(url.query)
                data = package(
                    query.get("baseline") != ["1"],
                    moving_water=query.get("water") != ["still"],
                    preview_720=query.get("resolution") == ["720"],
                    refined_tang=query.get("turns") != ["original"],
                )
                mime = "application/zip"
            elif url.path in ROUTES:
                path = ROUTES[url.path]
                data = path.read_bytes()
                mime = mimetypes.guess_type(path)[0]
            else:
                return self.send_error(404)
        except (OSError, ValueError, KeyError) as error:
            return self.send_error(500, str(error))
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device-zip", type=Path, help="Build the standalone screensaver and exit")
    args = parser.parse_args()
    if args.device_zip:
        args.device_zip.write_bytes(package(True, device=True))
        raise SystemExit(0)
    port = args.port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Reef preview at http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()
