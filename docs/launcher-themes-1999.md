# 1999 and Necromancer launcher themes

The **Launcher theme** selector now includes **1999** alongside Default, Necromancer and Monk. The new theme pairs parchment lettering with bronze bevels, square stone panels and four original EverQuest-era fantasy illustrations. Art is packaged offline as WebP, without a network request or changes to world/client settings.

| Artwork | Destinations |
| --- | --- |
| City gates | Play, Setup, Server |
| Elven wilds | Gameplay, Appearance, Client |
| Wizard's spellbook | Spire, Database, Bots, Logs |
| Dragon expedition | Updates & builds, Backups & files, Fixes |

Necromancer retains its black and dark-red palette and four paintings. Tiles, the runtime toolbar, profile bar, main navigation, setup checklist and update checklist now have repeating ivory bone borders with small corner skulls. The frame is a bundled nine-slice SVG, with pointer events disabled so it does not cover touch or controller targets. All themed Play and Appearance destinations now use their own theme's artwork.

Appearance persists across reloads and all three world profiles. Both the browser and native all-profile backup/restore validators accept `1999`. Unknown saved values still fall back to Default; theme changes do not invoke runtime operations, change client options or overwrite unrelated preferences.

## Assets and provenance

The four illustrations were created with the built-in image-generation tool using the complete prompts below, then encoded as WebP for the APK. No existing EverQuest artwork was copied. Final project paths:

- `app/src/main/assets/ui/theme-1999-gates.webp`
- `app/src/main/assets/ui/theme-1999-wilds.webp`
- `app/src/main/assets/ui/theme-1999-spellbook.webp`
- `app/src/main/assets/ui/theme-1999-dragon.webp`
- `app/src/main/assets/ui/theme-necromancer-bones.svg` (original vector UI decoration)

## Verification

Run `node tests/ui_themes.cjs` for scene routing, decoding, contrast, reload/profile persistence, safe storage fallback and touch layout. Set `THEME_SCREENSHOT_DIR=ui-reports/themes-1999` to capture the themed screens. Runtime controls across all themes are covered by `tests/ui_session.cjs`; TAKP layouts by `tests/ui_takp.cjs`; full-profile appearance export/restoration by `tests/ui_all_sessions.cjs`. The improved-UI CI builds and lints the signed test APK using the verified 0.6.42 native payload and checks that the new artwork and frame bytes are packaged exactly.

On the AYN Thor, select 1999, visit each of the four scene groups, close/reopen the app and switch world profiles. Check that text remains readable and all six runtime buttons work. Select Necromancer and check bone frames on Play, Manage, setup and update checklists, including controller focus and collapsed cards. Export/restore an all-profile backup with 1999 selected; restore only a disposable backup or use your usual backup precautions. These device checks complement browser/host tests.

## Original artwork prompts

### gates

Use case: stylized-concept. Asset type: one original 16:9 landscape illustration, approximately 1536x864, bundled in the 1999 theme of an EverQuest Android launcher. Style: late-1990s EverQuest-era high-fantasy PC game box and loading-screen painting, traditional oil and gouache brushwork, rich atmospheric depth, tactile worn stone, leather and metal, earnest adventurous retro MMO mood. Palette: weathered bronze and ochre, parchment ivory, dusky indigo, forest green, restrained oxblood accents. Composition: uninterrupted wide painting; important subjects in the right half and middle distance, quieter shadowed left third suitable behind UI text; scenic detail across the picture for use as full-page wallpaper. Original composition. No words, lettering, signatures, logos, watermark, UI, panel divisions, border or frame. Avoid modern cinematic photorealism, neon, anime and cartoon rendering. Scene: dusk at the gates of a sprawling medieval human city, crenellated weathered stone towers, warm lanterns, a winding road past old forest oaks. A small party of adult adventurers in travel-worn cloaks, armor and leather approaches the gate in the right half: a warrior, an elf ranger and a robed wizard. Distant mountain silhouettes and a smoky amber sunset suggest an enormous world awaiting exploration. Grounded natural anatomy and modestly scaled figures; architecture and landscape dominate.

### wilds

Use case: stylized-concept. Asset type: one original 16:9 landscape illustration, approximately 1536x864, bundled in the 1999 theme of an EverQuest Android launcher. Style: late-1990s EverQuest-era high-fantasy PC game box and loading-screen painting, traditional oil and gouache brushwork, rich atmospheric depth, tactile worn stone, leather and metal, earnest adventurous retro MMO mood. Palette: weathered bronze and ochre, parchment ivory, dusky indigo, forest green, restrained oxblood accents. Composition: uninterrupted wide painting; important subjects in the right half and middle distance, quieter shadowed left third suitable behind UI text; scenic detail across the picture for use as full-page wallpaper. Original composition. No words, lettering, signatures, logos, watermark, UI, panel divisions, border or frame. Avoid modern cinematic photorealism, neon, anime and cartoon rendering. Scene: a remote ancient elven forest in the early evening, colossal mossy trees, a rope bridge and carved wooden lookout platforms, pale shafts of light through leaves, a stream reflecting the blue-violet sky. An adult elf ranger in a weathered green cloak and an adult human traveler with a lantern stand on a stone path at the right, surveying a distant ruined watchtower. Expansive mysterious wilderness, hand-painted natural foliage, grounded anatomy and small scenic figures.

### spellbook

Use case: stylized-concept. Asset type: one original 16:9 landscape illustration, approximately 1536x864, bundled in the 1999 theme of an EverQuest Android launcher. Style: late-1990s EverQuest-era high-fantasy PC game box and loading-screen painting, traditional oil and gouache brushwork, rich atmospheric depth, tactile worn stone, leather and metal, earnest adventurous retro MMO mood. Palette: weathered bronze and ochre, parchment ivory, dusky indigo, forest green, restrained oxblood accents. Composition: uninterrupted wide painting; important subjects in the right half and middle distance, quieter shadowed left third suitable behind UI text; scenic detail across the picture for use as full-page wallpaper. Original composition. No words, lettering, signatures, logos, watermark, UI, panel divisions, border or frame. Avoid modern cinematic photorealism, neon, anime and cartoon rendering. Scene: the interior of a medieval wizard's study in a stone tower, a heavy open grimoire with abstract illegible geometric marks on an oak desk toward the right, an astrolabe, brass candlestick, rolled maps, jewel-toned potion bottles and a carved staff. Beyond an arched window are ancient spires and an indigo night sky. Warm amber candlelight and subtle blue magical illumination, believable materials, evocative nostalgic fantasy rather than bright magical effects. No legible text anywhere.

### dragon

Use case: stylized-concept. Asset type: one original 16:9 landscape illustration, approximately 1536x864, bundled in the 1999 theme of an EverQuest Android launcher. Style: late-1990s EverQuest-era high-fantasy PC game box and loading-screen painting, traditional oil and gouache brushwork, rich atmospheric depth, tactile worn stone, leather and metal, earnest adventurous retro MMO mood. Palette: weathered bronze and ochre, parchment ivory, dusky indigo, forest green, restrained oxblood accents. Composition: uninterrupted wide painting; important subjects in the right half and middle distance, quieter shadowed left third suitable behind UI text; scenic detail across the picture for use as full-page wallpaper. Original composition. No words, lettering, signatures, logos, watermark, UI, panel divisions, border or frame. Avoid modern cinematic photorealism, neon, anime and cartoon rendering. Scene: the vaulted ruins of an ancient dwarven mountain fortress, broken stone columns and a narrow bridge above a misty chasm. A great crimson dragon with folded leathery wings coils beside a distant doorway on the right, lit by embers and a shaft of moonlight. On the near bridge a small party of adult armored adventurers with shields, a staff and a torch faces the distant creature. Classic dangerous dungeon expedition, impressive scale, natural clear silhouettes, no gore; the architecture and blue-black cavern dominate, with restrained bronze and crimson light.

