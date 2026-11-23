# Ubuntu reef preview and Blender authoring

Start the preview from the project root with `python3 preview/run.py`. Open <http://127.0.0.1:8765/> in Chrome or Firefox. Reload the page to pick up newly rendered PNGs and placements. Open <http://127.0.0.1:8765/?baseline=1> to see Reef Glass v1.1.3 as released, from the ZIP in `baseline/`. Ctrl+C in the server terminal stops it. On a fresh machine install the locked simulator dependencies with `npm ci --prefix preview --ignore-scripts` and provide Python 3.9+ with Pillow. The running preview serves its assets on loopback.

The host uses brs-engine 2.7.1 (MIT) and executes the channel's BrightScript from `app/`. An in-memory preview ZIP adds a Main entry point that calls RunScreenSaver. The browser handles the simulated display. The simulator has no SceneGraph support, so the settings screen cannot be previewed. Roku startup, settings, memory and frame pacing still need hardware testing. [Simulator documentation](https://github.com/lvcabral/brs-engine/blob/master/docs/integrating.md)

## Source layout

Rellie Reef began as Reef Glass v1.1.3. That release now lives in this repository as our own source, and the channel is built from it directly.

| Path | Contents |
|---|---|
| `app/` | The channel: `manifest`, `source/*.brs`, the settings screen in `components/`, the reef's pictures in `images/` and the base scene `scenes/tank.json`. `NOTICE.md` lists what has changed from Reef Glass, and the upstream licences and credits ship with it. |
| `authoring/` | Blender sources, generator scripts and rendered sprites for the art added since, with their placements. |
| `preview/run.py` | Packages `app/` and lays the authored art into its scene, for the preview and for the device ZIP. |
| `tools/` | `check_scene.py` checks a packaged ZIP, `make_branding.py` renders the splash screens and icons, and `build_baseline.py` rebuilds the Reef Glass reference ZIP. |
| `baseline/` | Reef Glass v1.1.3 as released, kept as the reference for device measurements and for `?baseline=1`. Nothing is built from it. |

Edit BrightScript in `app/source/` and reload the preview. The draw order is in `PanFrame` in `pan.brs`, and what loads when is in `ReefInit` in `reef.brs`.

## Edit a colony

1. Open `blender authoring/plate_coral.blend`. The colony consists of individually editable plate meshes with a pigment color attribute and a procedural surface material. The file includes the orthographic camera and area lights. Save your edits.
2. Export its active camera at the intended in-tank pixel size. From the project root run `blender -b authoring/plate_coral.blend --python-exit-code 1 -P authoring/export_sprite.py`. The PNG sits beside the blend file, with transparency. A reload shows the new render.
3. Adjust its x and y in `authoring/placements.json`. Coordinates specify the upper-left corner in the 3400 × 1080 tank. The example at (325, 815) is visible near the sand on the initial left-hand view. The preview adds it to the near reef layer and expands the coral occupancy grid from the sprite alpha so fish can pass on either side of the reef.
4. For another species, save a new blend file under authoring, choose an identifier such as `purple_fan`, model it under the same rig and export it. Append another placement with model, x and y. The PNG basename must match model. Keep each side at or below 2048 pixels. For a seeded plate variant, generate a fresh editable file with the command below, then export and place it as above.

```sh
blender -b --factory-startup --python-exit-code 1 -P authoring/create_plate_coral.py -- authoring/plate_variant.blend --seed 42
```

The sample is an original procedural model. The 240 × 150 sample sprite represents approximately 0.14 MiB at four bytes per pixel. Blender meshes, the modeling recipe and the simulator are host-side tools. The preview builds each variation in memory, leaving the frozen sideload ZIP available for the first device test.

Add `?resolution=720` to render the local preview into a 1280×720 surface. The default is 1920×1080. Add `turns=original` to the query to compare with the original yellow tang poses in the same scene. In the updated preview the yellow tang uses 44 headings, with intermediate views rendered from the original mesh and side texture for both straight and bent poses.

To regenerate the yellow tang atlas, retrieve `gen/meshes/yellowtang.ply` and `gen/meshes/yellowtang_full.png` from the primary checkout through Git LFS. Run `python3 authoring/create_tang_turns.py` in a Python environment with ModernGL, Trimesh, NumPy, SciPy, Pillow, OpenCV and imagequant, with an OpenGL context available. The renderer and base artwork come from Reef Glass. [Upstream artwork credits](https://github.com/timsaucer/reef_glass_roku_screensaver/blob/270f1b06c4b5e5f4279dc12815e16121388659c6/CREDITS.md)

## Christmas set

`authoring/christmas/` holds a seasonal set: a brick fireplace with a burning fire and a bubbling chimney, two piles of gifts, strings of lights on the corals, and a green moray in a Santa hat who replaces the snowflake moray and pops out of the cave with a sack. The set is always packaged, and the season setting switches it on or off when the screensaver starts. Add `?christmas=0` to the preview URL to see the everyday reef.

Each model is generated and rendered by its own script, run from the project root. The set was built and tested with Blender 5.2 only.

```sh
blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_fireplace.py -- --overwrite
blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_gifts.py -- --overwrite
blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_lights.py -- --overwrite
blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_santa_moray.py -- --overwrite
blender -b --factory-startup --python-exit-code 1 -P authoring/christmas/create_effects.py
```

Without `--overwrite` a script stops when its `.blend` already exists, so hand edits are kept. `rig.py` is the shared camera, tank lighting and mesh helpers. One Blender unit is 100 tank pixels.

- **Placement.** `layout.json` gives the upper-left corner of the fireplace and gift sprites, and the height where chimney bubbles vanish at the surface.
- **Lights.** `strings.json` lists each string's anchor points in tank pixels, where the wire rests on a coral, and the bulb spacing. The wire sags between anchors.
- **Moray.** `create_santa_moray.py` rebuilds the eel for every frame from a pose. `-- --still pop:0.2` or `-- --still idle:0.5` renders one pose to `_still.png` for a quick look. The cave track, pop timing and idle loop are near the top and bottom of the script.

`app/source/christmas.brs` animates the fire, bubbles and bulb glows. `app/source/santa_moray.brs` plays the moray's clips. Both load after the reef and the fish. If the moray's sheet does not fit in graphics memory, the snowflake moray keeps the cave.

When the set is switched off, `app/source/season.brs` removes it from the scene before anything loads: the fireplace and gift pieces are dropped, the fish steer by the coral map made without them, and the snowflake moray keeps the cave. None of the set's pictures are loaded.

Add `?cam=1400` to pin the preview camera at a tank x position and `?hour=22` to pin the tank clock. At night the bulbs and the fire are drawn over the night tint.

## Settings

On a Roku, **Change screensaver settings** opens two lists. Lighting holds the tank at daytime, dusk or night, or follows the Roku's clock. Season chooses the Christmas reef or the everyday reef. Each choice is saved to the registry at once and shows the next time the screensaver starts. The choices are defined in `app/source/settings.brs` and the screen in `app/components/`.

## Build the Roku ZIP

From the repository root, with Python and Pillow installed, run:

```sh
mkdir -p build
python3 preview/run.py --device-zip build/rellie-reef.zip
python3 tools/check_scene.py build/rellie-reef.zip
```

The build needs only `app/` and `authoring/`. An upstream Reef Glass checkout is needed only to regenerate the reference ZIP in `baseline/` or the yellow tang atlas. Keep local measurements and generated device ZIPs in `measurements/` and `build/`, respectively.
