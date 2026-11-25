"""Lay the rendered reef into market/app. Requires Pillow.

    python market/reef.py

Run after anything under market/art changes: the reefscape renders, the light strings, the
water surface, or layout.json. It rewrites the reef's pictures in app/images and every part
of app/scenes/tank.json that depends on where things are:

  * the background tiles, cut from the plate, and one reef piece per structure
  * the coral maps the fish steer by, drawn from the pieces' own outlines
  * the moray, mirrored to face right and moved into the cave, with the cave's darkness to
    draw back over his tail
  * the Christmas set at its places in layout.json, the light strings and their bulbs,
    and the embers that glow in the hearth in Night Lite
  * the fish and their sprite sheets, the shrimp's routes and the light shafts

Running it twice changes nothing more: it works from market/art and from where the scene
says things are now.
"""
import json
from io import BytesIO
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ART, APP = HERE / "art", HERE / "app"
IMAGES, REEF = APP / "images", ART / "reefscape"
CELL, COLS, ROWS = 40, 85, 27           # the coral map: 40 px cells over the 3400 x 1080 tank
TILE = 1920                             # a Roku bitmap is at most 2048 px wide
GONE = ("mound_a.png", "mound_b.png", "reef_left.png", "reef_right.png", "cave_shade.png", "anemone_current.png", "custom_plate_coral.png",
        "moray.png", "moray_jaw.png", "duster_crown.png", "duster_tube.png", "starfish.png",
        "bluetang_atlas0.png", "clown_atlas0.png", "gramma_atlas0.png", "puffer_atlas0.png", "puffer_ball_atlas0.png", "yellowtang_atlas0.png")


def image(name):
    return "pkg:/images/" + name


def occupancy(sprites):
    """Coral map rows for sprites [(alpha, x, y), ...]: '#' where a sprite covers a cell or
    its neighbour, '.' for open water. Shadows on the sand do not count."""
    grid = [[False] * COLS for _ in range(ROWS)]
    for alpha, x, y in sprites:
        solid = alpha.point(lambda v: 255 if v > 220 else 0)
        for j in range(max(0, y // CELL), min(ROWS, (y + alpha.height + CELL - 1) // CELL)):
            for i in range(max(0, x // CELL), min(COLS, (x + alpha.width + CELL - 1) // CELL)):
                left, top = i * CELL - x, j * CELL - y
                if solid.crop((left, top, left + CELL, top + CELL)).histogram()[255] > 0.12 * CELL * CELL:
                    grid[j][i] = True
    wide = [[any(grid[b][a] for b in range(max(0, j - 1), min(ROWS, j + 2)) for a in range(max(0, i - 1), min(COLS, i + 2)))
             for i in range(COLS)] for j in range(ROWS)]
    return ["".join("#" if cell else "." for cell in row) for row in wide]


def main():
    layout = json.loads((ART / "layout.json").read_text())
    scene_path = APP / "scenes/tank.json"
    scene = json.loads(scene_path.read_text())
    before = {piece["img"].rsplit("/", 1)[-1]: piece for piece in scene["pan"]["pieces"]}

    # Background and reef pieces.
    plate = Image.open(REEF / "plate.jpg").convert("RGB")
    tank = plate.convert("RGBA")
    scene["pan"]["bg"] = []
    for n, left in enumerate(range(0, plate.width, TILE)):
        plate.crop((left, 0, min(plate.width, left + TILE), plate.height)).save(IMAGES / f"wide_bg{n}.jpg", quality=93)
        scene["pan"]["bg"].append(image(f"wide_bg{n}.jpg"))
    pieces, solid = [], []
    for name in layout["structures"]:           # listed from the back of the tank to the front
        at = json.loads((REEF / f"{name}.json").read_text())
        sprite = Image.open(REEF / f"{name}.png").convert("RGBA")
        sprite.save(IMAGES / f"reef_{name}.png")
        tank.alpha_composite(sprite, (at["x"], at["y"]))
        pieces.append({"img": image(f"reef_{name}.png"), "x": at["x"], "y": at["y"], "shadow": False})
        solid.append((sprite.getchannel("A"), at["x"], at["y"]))
    for name in GONE:
        (IMAGES / name).unlink(missing_ok=True)

    # The stone and the Christmas set. Pieces marked "front" are drawn after the light strings.
    def place(name, at, **marks):
        sprite = Image.open(IMAGES / name).convert("RGBA")
        pieces.append({"img": image(name), "x": at[0], "y": at[1], "shadow": False, **marks})
        return sprite.getchannel("A"), at[0], at[1]

    spots = layout["christmas"]
    fireplace = place("custom_fireplace.png", spots["fireplace"], xmas=True)
    hearth_gifts = place("custom_gifts_hearth.png", spots["gifts_hearth"], xmas=True)
    tree = place("custom_tree.png", spots["tree"], xmas=True, front=True)
    stone = place("custom_holiday_quartz.png", layout["stone"], front=True)
    tree_gifts = place("custom_gifts_tree.png", spots["gifts_tree"], xmas=True, front=True)
    scene["pan"]["pieces"] = pieces
    scene["coralPlain"] = occupancy(solid + [stone])
    scene["coral"]["rows"] = occupancy(solid + [stone, tree, tree_gifts, fireplace, hearth_gifts])

    # Christmas: what was placed relative to the tree and the fireplace moves with them.
    xmas = scene["christmas"]
    dx, dy = (spots["tree"][k] - before["custom_tree.png"][("x", "y")[k]] for k in (0, 1))
    xmas["star"] = [xmas["star"][0] + dx, xmas["star"][1] + dy]
    own = [[round(b[0] + dx, 1), round(b[1] + dy, 1), b[2], b[3]] for b in xmas["bulbs"] if len(b) > 3]
    dx, dy = (spots["fireplace"][k] - before["custom_fireplace.png"][("x", "y")[k]] for k in (0, 1))
    xmas["fire"]["x"], xmas["fire"]["y"] = xmas["fire"]["x"] + dx, xmas["fire"]["y"] + dy
    for key in ("hearth", "chimney"):
        xmas[key] = [xmas[key][0] + dx, xmas[key][1] + dy]
    # Embers for the Night Lite, when the fire is out: what glows in the fireplace's own picture
    # (the cracks in the logs and the bed under the grate), with the logs themselves left dim.
    hearth = Image.open(IMAGES / "custom_fireplace.png").convert("RGBA")
    left, top = xmas["fire"]["x"] - spots["fireplace"][0] + 2, xmas["fire"]["y"] - spots["fireplace"][1] + 66
    embers = hearth.crop((left, top, left + 98, top + 60))
    pixels = embers.load()
    for y in range(embers.height):
        for x in range(embers.width):
            r, g, b, a = pixels[x, y]
            heat = max(0.0, min(1.0, (r - 140) / 60)) * max(0.0, min(1.0, (r - 1.5 * b) / 45)) if a else 0.0
            logs = 6 <= x <= 90 and 6 <= y <= 42       # the logs alone, not the hearth round them
            wood = max(0.0, min(1.0, ((r + g + b) / 3 - 55) / 50)) * 0.34 if a and logs else 0.0
            pixels[x, y] = (r, round(g * 0.9), round(b * 0.6), round(255 * heat)) if heat >= wood else (150, 40, 12, round(255 * wood))
    embers.save(IMAGES / "xmas_embers.png")
    xmas["embers"] = [spots["fireplace"][0] + left, spots["fireplace"][1] + top]
    lights = json.loads((ART / "lights.json").read_text())
    Image.open(ART / "lights.png").save(IMAGES / "xmas_lights.png")

    def covered(x, y):
        """Behind one of the pieces that stand in front of the strings."""
        for alpha, left, top in (tree, stone, tree_gifts):
            px, py = round(x - left), round(y - top)
            if 0 <= px < alpha.width and 0 <= py < alpha.height and alpha.getpixel((px, py)) > 127:
                return True
        return False

    xmas["tiles"] = lights["tiles"]
    xmas["bulbs"] = [bulb for bulb in lights["bulbs"] if not covered(bulb[0], bulb[1])] + own

    # The moray: rendered facing left with his hidden end at "deep"; mirrored into the new cave.
    cave = json.loads((REEF / "grotto.json").read_text())["cave"]
    moray = json.loads((ART / "moray/santa_moray.json").read_text())
    sheet = Image.open(ART / "moray/santa_moray.png").convert("RGBA")
    flipped = sheet.copy()
    deep, lift = cave["deep"][0], cave["deep"][1] - 6 - moray.pop("base")
    was_deep = moray.pop("deep")
    for frame in moray["frames"]:
        ax, ay, w, h, tx, ty = frame
        flipped.paste(sheet.crop((ax, ay, ax + w, ay + h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT), (ax, ay))
        frame[4], frame[5] = deep + was_deep - (tx + w), ty + lift
    flipped.save(IMAGES / "santa_moray.png")
    # The cave's own darkness, drawn over him: solid where he lies hidden, fading out by the mouth.
    box = (deep - 40, cave["roof"] - 70, deep + 124, cave["deep"][1] + 12)
    shade = tank.crop(box)
    ramp = Image.new("L", shade.size)
    ramp.putdata([max(0, min(255, round((shade.width - x) * 255 / 34))) for _ in range(shade.height) for x in range(shade.width)])
    shade.putalpha(ramp)
    shade.save(IMAGES / "santa_cave.png")
    moray["shade"] = [box[0], box[1]]
    scene["santaMoray"] = moray
    # Where a big fish swimming close sends him back in.
    scene["moray"] = {"x": cave["mouth"][0], "y": cave["roof"] + 60, "threat": 170}

    # Water surface, critters, fish.
    Image.open(ART / "surface_ripple.png").convert("RGB").save(IMAGES / "surface_ripple.jpg", quality=95)
    scene["shrimp"]["routes"] = [{"pts": route["pts"], "shadow": route.get("shadow", False)} for route in layout["shrimp"]]
    scene["dusters"] = []
    scene.pop("starfish", None)
    # The fish: how each species behaves is in the layout; its views come with its sprite sheet.
    scene["species"] = {}
    for name, ways in layout["fish"].items():
        Image.open(ART / f"fish/{name}_atlas0.png").save(IMAGES / f"{name}_atlas0.png")
        scene["species"][name] = {**ways, "views": json.loads((ART / f"fish/{name}.json").read_text())}
    scene["anemone"] = {"home": layout["haunt"]}        # where visiting fish with no haunt of their own gather
    scene["haze"] = layout["haze"]
    scene["roam"].update(layout["roam"])
    scene["rays"] = layout["rays"]

    scene_path.write_text("{\n" + ",\n".join(f' {json.dumps(key)}: {json.dumps(value, separators=(",", ":"))}' for key, value in scene.items()) + "\n}\n")
    tank.convert("RGB").save(REEF / "preview.jpg", quality=92)
    print(f"Reef laid in: {len(layout['structures'])} structures, {len(layout['fish'])} species, {len(xmas['bulbs'])} bulbs ({len(own)} on the tree), "
          f"moray at x {deep}, {len(layout['shrimp'])} shrimp routes.")


if __name__ == "__main__":
    main()
