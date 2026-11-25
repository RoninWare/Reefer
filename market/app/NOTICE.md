# Seasons Reef tank

Seasons Reef tank is the store edition of Rellie Reef. Rellie Reef is built on [Reef Glass](https://github.com/timsaucer/reef_glass_roku_screensaver) v1.1.3 (commit `270f1b06c4b5e5f4279dc12815e16121388659c6`). Reef Glass's code is licensed under Apache-2.0 ([LICENSE](LICENSE)) and its images are dedicated to the public domain under CC0 1.0 ([LICENSE-ART](LICENSE-ART)). [CREDITS.md](CREDITS.md) records how those images were made and lists the images added since.

The Reef Glass release was brought into this tree on 2026-11-22. The files below have changed since. Each changed source file also says so in its first line.

## Changed from Reef Glass

| File | Change |
|---|---|
| `manifest` | Title and version. |
| `source/main.brs` | Reads the season setting and applies it to the scene before the tank loads. |
| `source/reef.brs` | Loads and updates the added modules after the reef and the fish. |
| `source/pan.brs` | Draws the water surface, the anemone, the shrimp and the Christmas set. Pieces marked `front`, the critters and the near fish are drawn after the coral light strings, the night's dark and the reef's glow, and take the dark as a tint of their own (`NightDim` in `source/reef.brs`). |
| `source/critters.brs` | The cave's moray is run by `santa_moray.brs`. Feather dusters and the starfish are drawn only where the scene has them. |
| `source/moray.brs`, `images/moray*.png`, `images/cave_shade.png`, `images/duster_*.png`, `images/starfish.png` | Removed. |
| `images/wide_bg*.jpg`, `images/reef_left.png`, `images/reef_right.png`, `images/mound_*.png` | Removed. The tank and its reef are new pictures, rendered for this edition (`images/wide_bg*.jpg`, `images/reef_*.png`). |
| `source/settings.brs` | Adds the season setting. Settings are stored in the `rellieReef` registry section. |
| `components/SettingsScene.xml`, `components/SettingsScene.brs` | Two lists, lighting and season, with focus moving between them. |
| `images/splash_*.jpg`, `images/icon_*.jpg` | Re-rendered with the title "Seasons Reef tank". |
| `source/fish.brs` | Shows one strength of body bend toward each flank, which is what the fish sheets hold. Draws a rowing pectoral fin from the poses a view carries. At night a fish in front of the reef, or in open water behind it, is drawn after the night's dark in the night's tint, with its glow over it. |
| `images/*_atlas0.png`, `images/ray.png`, `images/mote.png`, `images/puff.png` | Removed. The fish and the light sprites are new pictures, made for this edition. |
| Every PNG | Saved again more tightly when the package is built, to fit Roku's 4 MB limit. |
| `scenes/tank.json` | The added models, the Christmas set, the shrimp's routes and a second coral map are written into the scene. |

`source/fish.brs`, `source/moray.brs` and the remaining images are as released.

## Added for Rellie Reef

| File | Purpose |
|---|---|
| `source/surface.brs` | Moving water surface. |
| `source/glow.brs` | The reef's glow at night and in Night Lite, and the light it throws on the sand. |
| `source/season.brs` | Takes the Christmas set out of the scene when it is switched off. |
| `source/christmas.brs` | Hearth fire, chimney bubbles, the bulbs on the coral light strings and on the tree, the glow of the tree's star, and embers in the hearth in Night Lite. |
| `source/santa_moray.brs` | The green moray in a Santa hat. |
| `source/shrimp.brs` | Peppermint shrimp that walk routes over the sand and rock, stopping to clean. |
| `images/custom_*.png`, `images/star_glow.png`, `images/surface_ripple.jpg`, `images/xmas_*.png`, `images/santa_moray.png`, `images/santa_cave.png`, `images/shrimp.png` | Added art, laid in when the channel is packaged. |

No licence has been chosen yet for the files added for Rellie Reef.
