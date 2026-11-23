# Ubuntu reef preview and Blender authoring

Start the preview from the project root with `python3 preview/run.py`. Open <http://127.0.0.1:8765/> in Chrome or Firefox. Reload the page to pick up newly rendered PNGs and placements. Open <http://127.0.0.1:8765/?baseline=1> to see the upstream tank composition. Ctrl+C in the server terminal stops it. On a fresh machine install the locked simulator dependencies with `npm ci --prefix preview --ignore-scripts` and provide Python 3.9+ with Pillow. The running preview serves its assets on loopback.

The host uses brs-engine 2.7.1 (MIT) and executes Reef Glass's BrightScript. An in-memory preview ZIP adds a Main entry point that calls RunScreenSaver. The browser handles the simulated display. Roku startup, settings, memory and frame pacing still need hardware testing. [Simulator documentation](https://github.com/lvcabral/brs-engine/blob/master/docs/integrating.md)

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

## Build the Roku ZIP

From the repository root, with Python and Pillow installed, run:

```sh
mkdir -p build
python3 preview/run.py --device-zip build/rellie-reef-current.zip
python3 tools/check_scene.py build/rellie-reef-current.zip
```

The repository includes the pinned baseline ZIP and the packaged art inputs. Source models are in `authoring/`. Upstream checkouts are optional for this build and are needed when regenerating the baseline or the yellow tang atlas. Keep local measurements and generated device ZIPs in `measurements/` and `build/`, respectively.
