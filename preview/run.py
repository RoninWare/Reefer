"""Package Rellie Reef and serve its local BrightScript preview on loopback.

The channel's source is app/ (source, components, manifest, the reef's own pictures and the
base scene). The art made in authoring/ is laid into the scene here, at package time: the
placed models, the moving water and anemone, the peppermint shrimp, the refined yellow tang and
the Christmas set.
"""
import argparse
import importlib.util
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = HERE / "node_modules/brs-engine"
APP = ROOT / "app"
ART = ROOT / "authoring"
XMAS = ART / "christmas"
SHRIMP = ART / "shrimp"
ROUTES = {
    "/": HERE / "index.html",
    "/lib/brs.api.js": ENGINE / "lib/brs.api.js",
    "/lib/brs.worker.js": ENGINE / "lib/brs.worker.js",
    "/assets/common.zip": ENGINE / "assets/common.zip",
}


def add_model(scene, contents, placement, folder=ART, xmas=False):
    name = placement["model"]
    if not name.isidentifier():
        raise ValueError(f"Invalid model name: {name}")
    asset = f"images/custom_{name}.png"
    data = (folder / f"{name}.png").read_bytes()
    x, y = placement["x"], placement["y"]
    with Image.open(BytesIO(data)) as image:
        if image.mode != "RGBA" or max(image.size) > 2048:
            raise ValueError(f"{name} needs an RGBA sprite no larger than 2048 px")
        alpha = image.getchannel("A")
    contents[asset] = data
    piece = {"img": "pkg:/" + asset, "x": x, "y": y, "shadow": False}
    if xmas:
        piece["xmas"] = True        # season.brs drops these when the Christmas reef is off
    if placement.get("front"):
        piece["front"] = True       # stands before the reefs: drawn after the anemone and light strings
    # Pieces are drawn in list order. "behind" names a model this one must be drawn before.
    pieces = scene["pan"]["pieces"]
    behind = f'pkg:/images/custom_{placement["behind"]}.png' if "behind" in placement else None
    at = next((i for i, other in enumerate(pieces) if other["img"] == behind), len(pieces))
    pieces.insert(at, piece)
    # Preserve the existing occupancy and extend it by one cell around the new silhouette.
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


def add_reef_motion(contents):
    contents["images/anemone_current.png"] = (ART / "anemone_current.png").read_bytes()


def add_shrimp(scene, contents):
    """The peppermint shrimp's frames, and the routes they walk."""
    contents["images/shrimp.png"] = (SHRIMP / "shrimp.png").read_bytes()
    routes = json.loads((SHRIMP / "routes.json").read_text())["routes"]
    scene["shrimp"] = {**json.loads((SHRIMP / "shrimp.json").read_text()), "routes": [{"pts": route["pts"], "shadow": route.get("shadow", False)} for route in routes]}


def add_tang_turns(scene, contents):
    directory = ART / "tang_turns"
    views = json.loads((directory / "views.json").read_text())
    scene["species"]["yellowtang"]["views"] = views
    for page in range(views["pages"]):
        filename = f"yellowtang_atlas{page}.png"
        contents[f"images/{filename}"] = (directory / filename).read_bytes()


def add_christmas(scene, contents):
    """The tree, fireplace, gifts, coral lights and the Santa moray, from authoring/christmas.
    They are always packaged; the season setting decides at start-up whether they are used."""
    # What the fish steer by when the Christmas reef is switched off.
    scene["coralPlain"] = list(scene["coral"]["rows"])
    layout = json.loads((XMAS / "layout.json").read_text())
    for placement in layout["pieces"]:
        add_model(scene, contents, placement, XMAS, xmas=True)
    hearth = next(piece for piece in layout["pieces"] if piece["model"] == "fireplace")
    fireplace = json.loads((XMAS / "fireplace.json").read_text())
    lights = json.loads((XMAS / "lights.json").read_text())

    def placed(point):
        return [round(hearth["x"] + point[0]), round(hearth["y"] + point[1])]

    fire = dict(fireplace["fire"])
    fire["x"], fire["y"] = placed((fire["x"], fire["y"]))

    # The tree stands in front of the reefs, so a reef string passing behind it loses the glow
    # of every bulb the tree covers. The tree's own bulbs follow, in the order they hang.
    spot = next(piece for piece in layout["pieces"] if piece["model"] == "tree")
    tree = json.loads((XMAS / "tree.json").read_text())
    with Image.open(XMAS / "tree.png") as image:
        cover = image.getchannel("A")

    def hidden(x, y):
        x, y = round(x - spot["x"]), round(y - spot["y"])
        return 0 <= x < cover.width and 0 <= y < cover.height and cover.getpixel((x, y)) > 127

    bulbs = [bulb for bulb in lights["bulbs"] if not hidden(bulb[0], bulb[1])]
    bulbs += [[round(spot["x"] + x, 1), round(spot["y"] + y, 1), color, group] for x, y, color, group in tree["bulbs"]]
    scene["christmas"] = {
        "fire": fire, "hearth": placed(fireplace["hearth"]), "chimney": placed(fireplace["chimney"]),
        "surface": layout["surface"], "tiles": lights["tiles"], "bulbs": bulbs,
        "star": [round(spot["x"] + tree["star"][0]), round(spot["y"] + tree["star"][1])],
    }
    contents["images/star_glow.png"] = (ART / "star_glow.png").read_bytes()
    with Image.open(XMAS / "fireplace.png") as picture:
        contents["images/xmas_embers.png"], at = embers(picture, fireplace["fire"])
    scene["christmas"]["embers"] = placed(at)
    for source, packaged in (("glows", "xmas_glows"), ("bubbles", "xmas_bubbles"), ("fire_frames", "xmas_fire"),
                             ("lights", "xmas_lights"), ("santa_moray", "santa_moray")):
        contents[f"images/{packaged}.png"] = (XMAS / f"{source}.png").read_bytes()

    # The Santa moray reaches out past the cave mouth, so the shade that hides his body must
    # leave the mouth clear: keep the back wall and shadow, fading in from the left.
    moray = json.loads((XMAS / "santa_moray.json").read_text())
    moray["shade"] = scene["moray"]["shade"]
    scene["santaMoray"] = moray
    with Image.open(BytesIO(contents["images/cave_shade.png"])) as shade:
        shade = shade.convert("RGBA")
    ramp = Image.new("L", shade.size)
    ramp.putdata([min(255, max(0, round((x - 86) * 255 / 34))) for _ in range(shade.height) for x in range(shade.width)])
    shade.putalpha(ImageChops.multiply(shade.getchannel("A"), ramp))
    out = BytesIO()
    shade.save(out, "PNG")
    contents["images/santa_cave.png"] = out.getvalue()


def embers(fireplace, fire):
    """Embers for the Night Lite, when the fire is out: what glows in the fireplace's own picture
    (the cracks in the logs and the bed under the grate), with the logs themselves left dim.
    Returns the picture as PNG data and where it lies in the fireplace's picture."""
    left, top = fire["x"] + 2, fire["y"] + 66
    picture = fireplace.convert("RGBA").crop((left, top, left + 98, top + 60))
    pixels = picture.load()
    for y in range(picture.height):
        for x in range(picture.width):
            r, g, b, a = pixels[x, y]
            heat = max(0.0, min(1.0, (r - 140) / 60)) * max(0.0, min(1.0, (r - 1.5 * b) / 45)) if a else 0.0
            logs = 6 <= x <= 90 and 6 <= y <= 42       # the logs alone, not the hearth round them
            wood = max(0.0, min(1.0, ((r + g + b) / 3 - 55) / 50)) * 0.34 if a and logs else 0.0
            pixels[x, y] = (r, round(g * 0.9), round(b * 0.6), round(255 * heat)) if heat >= wood else (150, 40, 12, round(255 * wood))
    out = BytesIO()
    picture.save(out, "PNG")
    return out.getvalue(), (left, top)


def enable_720p(contents):
    """Preview only: draw into a 1280x720 screen through wrappers that scale every call."""
    contents["source/draw720.brs"] = (HERE / "draw720.brs").read_bytes()
    contents["manifest"] = contents["manifest"].replace(b"ui_resolutions=fhd", b"ui_resolutions=hd")
    draw_calls = {
        b"DrawObject": b"PreviewObject",
        b"DrawScaledObject": b"PreviewScaled",
        b"DrawRotatedObject": b"PreviewRotated",
        b"DrawTransformedObject": b"PreviewTransformed",
        b"DrawRect": b"PreviewRect",
    }
    for path in [p for p in contents if p.startswith("source/") and p != "source/draw720.brs"]:
        for method, wrapper in draw_calls.items():
            contents[path] = contents[path].replace(b"screen." + method + b"(", wrapper + b"(screen, ")
    contents["source/main.brs"] = contents["source/main.brs"].replace(
        b'CreateObject("roScreen", true, 1920, 1080)',
        b'CreateObject("roScreen", true, 1280, 720)',
    )


def add_preview_entry(contents, opts=None):
    """The preview's Main. Dev options of the renderer: cam pins the camera, hour pins the
    tank clock, nightLite enables dim lighting, and christmas=false runs the everyday reef.
    With none, the saved settings apply."""
    call = "RunScreenSaver()"
    if opts:
        pairs = ", ".join(f"{key}: {value}" for key, value in opts.items())
        call = f"RunReef({{ {pairs} }}, false)"
    contents["source/preview.brs"] = f"sub Main()\n    {call}\nend sub\n".encode()


def archive(contents):
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as package:
        for name, data in contents.items():
            package.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
    return out.getvalue()


def package(*, device=False, moving_water=True, preview_720=False, refined_tang=True, opts=None):
    """The channel ZIP: app/ with the authored art laid into its scene. For the preview a Main
    entry point is added (and, on request, the 720p drawing wrappers)."""
    contents = {path.relative_to(APP).as_posix(): path.read_bytes() for path in sorted(APP.rglob("*")) if path.is_file()}
    scene = json.loads(contents["scenes/tank.json"])
    placements = json.loads((ART / "placements.json").read_text())
    for placement in placements:
        add_model(scene, contents, placement)
    add_reef_motion(contents)
    add_shrimp(scene, contents)
    if moving_water:
        contents["images/surface_ripple.jpg"] = (ART / "surface_ripple.jpg").read_bytes()
    if refined_tang:
        add_tang_turns(scene, contents)
    add_christmas(scene, contents)
    contents["scenes/tank.json"] = json.dumps(scene, separators=(",", ":")).encode()
    if not device:
        add_preview_entry(contents, opts)
        if preview_720:
            enable_720p(contents)
    return archive(contents)


def package_upstream(*, preview_720=False):
    """Reef Glass v1.1.3 as released, for side-by-side comparison in the preview."""
    with ZipFile(ROOT / "baseline/reefglass-1.1.3.zip") as source:
        contents = {name: source.read(name) for name in source.namelist()}
    add_preview_entry(contents)
    if preview_720:
        enable_720p(contents)
    return archive(contents)


def package_market(*, preview_720=False, opts=None):
    """The store edition, which market/build.py builds from market/app, with the preview's Main."""
    spec = importlib.util.spec_from_file_location("market_build", ROOT / "market/build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    contents = build.contents()
    add_preview_entry(contents, opts)
    if preview_720:
        enable_720p(contents)
    return archive(contents)


def preview_options(query):
    opts = {key: float(query[key][0]) for key in ("cam", "hour") if key in query}
    if query.get("nightlite") == ["1"]:
        opts["nightLite"] = "true"
        opts["hour"] = 'LightingHour("nightlite")'
    if query.get("christmas") == ["0"]:
        opts["christmas"] = "false"
    return opts


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path == "/reef.zip":
                query = parse_qs(url.query)
                preview_720 = query.get("resolution") == ["720"]
                if query.get("baseline") == ["1"]:
                    data = package_upstream(preview_720=preview_720)
                elif query.get("market") == ["1"]:
                    data = package_market(preview_720=preview_720, opts=preview_options(query))
                else:
                    data = package(
                        moving_water=query.get("water") != ["still"],
                        preview_720=preview_720,
                        refined_tang=query.get("turns") != ["original"],
                        opts=preview_options(query),
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

    def do_POST(self):
        """Saves a picture of the display that the preview page sends (capture() in its console)
        as build/captures/<name>.png."""
        url = urlsplit(self.path)
        name = parse_qs(url.query).get("name", ["frame"])[0]
        length = int(self.headers.get("Content-Length") or 0)
        if url.path != "/capture" or not name.isidentifier() or not 0 < length <= 16 * 2 ** 20:
            return self.send_error(400)
        folder = ROOT / "build/captures"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.png").write_bytes(self.rfile.read(length))
        self.send_response(204)
        self.end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device-zip", type=Path, help="Build the standalone screensaver and exit")
    args = parser.parse_args()
    if args.device_zip:
        args.device_zip.write_bytes(package(device=True))
        raise SystemExit(0)
    port = args.port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Reef preview at http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()
