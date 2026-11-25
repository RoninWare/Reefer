# Rellie Reef

Rellie Reef is built on [Reef Glass](https://github.com/timsaucer/reef_glass_roku_screensaver) v1.1.3 (commit `270f1b06c4b5e5f4279dc12815e16121388659c6`). Reef Glass's code is licensed under Apache-2.0 ([LICENSE](LICENSE)) and its images are dedicated to the public domain under CC0 1.0 ([LICENSE-ART](LICENSE-ART)). [CREDITS.md](CREDITS.md) records how those images were made and lists the images added since.

The Reef Glass release was brought into this tree on 2026-11-22. The files below have changed since. Each changed source file also says so in its first line.

## Changed from Reef Glass

| File | Change |
|---|---|
| `manifest` | Title and version. |
| `source/main.brs` | Selects the scene and its asset directory at launch and applies the season setting. |
| `source/reef.brs` | Loads and updates the added modules after the reef and the fish. |
| `source/pan.brs` | Draws the water surface, the anemone, the shrimp and the Christmas set, including a pass over the night tint. Pieces marked `front` are drawn after the anemone and the coral light strings. |
| `source/critters.brs` | The cave's moray is run by `santa_moray.brs`, which falls back to `moray.brs`. |
| `source/settings.brs` | Adds the season and developer-build tank settings. Settings are stored in the `rellieReef` registry section. |
| `components/SettingsScene.xml`, `components/SettingsScene.brs` | Lighting, season, and a tank list when both tanks are packaged. |
| `images/splash_*.jpg`, `images/icon_*.jpg` | Re-rendered with the Rellie Reef title. |
| `images/yellowtang_atlas0.png`, `scenes/tank.json` | Replaced or extended when the channel is packaged: the yellow tang has more headings, and the added models, the Christmas set and a second coral map are written into the scene. |

`source/fish.brs` supports both bend layouts, pectoral fins, and optional glow atlases. `source/moray.brs` uses the optional snowflake eel config. The shared renderer resolves artwork from the selected tank’s asset directory.

## Added for Rellie Reef

| File | Purpose |
|---|---|
| `source/surface.brs` | Moving water surface scaled to the selected tank. |
| `source/glow.brs` | Optional nighttime coral fluorescence for Seasons Reef tank. |
| `source/reef_motion.brs` | Swaying anemone. |
| `source/season.brs` | Takes the Christmas set out of the scene when it is switched off. |
| `source/christmas.brs` | Hearth fire, chimney bubbles, the bulbs on the coral light strings and on the tree, the glow of the tree's star, and embers in the hearth in Night Lite. |
| `source/santa_moray.brs` | The green moray in a Santa hat. |
| `source/shrimp.brs` | Peppermint shrimp that walk routes over the sand and rock, stopping to clean. |
| `images/custom_*.png`, `images/star_glow.png`, `images/anemone_current.png`, `images/surface_ripple.jpg`, `images/xmas_*.png`, `images/santa_moray.png`, `images/santa_cave.png`, `images/shrimp.png` | Added art, laid in when the channel is packaged. |

No licence has been chosen yet for the files added for Rellie Reef.
