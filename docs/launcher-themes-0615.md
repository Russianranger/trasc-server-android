# Monk launcher theme — 0.6.15

Monk now uses sea blue surfaces, light coral-red actions and accents, and light readable text. Four original fantasy paintings give the tabs distinct scenes. The World profile and Launcher theme selectors remain together in the shared bar.

Choose **Launcher theme → Monk** beside **World profile**. Open Setup, Gameplay, Spire and Client to see all four scenes. Reopen the launcher and switch world profiles to check that the choice persists. Choose **Default** or **Necromancer** to select another appearance.

| Background | Tabs |
| --- | --- |
| Fantasy monk temples | Setup, Server |
| Human monk meditating by a flowing stream | Spire, Database |
| Training dojo | Builds, Client, Files, Logs |
| Unarmed martial combat | Gameplay, Fixes |

All four images are bundled for offline use. They were created with the built-in image-generation tool and encoded as WebP for the APK. The temple painting received a final image-generation cleanup to remove a small signature-like artifact.

The final project assets are saved at:

- `app/src/main/assets/ui/theme-monk-temple.webp`
- `app/src/main/assets/ui/theme-monk-meditation.webp`
- `app/src/main/assets/ui/theme-monk-dojo.webp`
- `app/src/main/assets/ui/theme-monk-combat.webp`

This is a launcher appearance update. The existing compiled server, imported client, Wine prefix, runtime, DirectX helpers, character UI/preferences, era settings and controller bindings are preserved. All 21 native components are reused from verified 0.6.14. No compilation of server/runtime/native components, client reimport or preference reset is needed.

## Original artwork prompts

### Temple

Use case: stylized-concept. Asset type: original wide 16:9 background painting for an EverQuest-inspired fantasy Monk Android launcher. Scene: a grand monastery of weathered stone and timber, tiered roofs and arched terraces overlooking a sea-blue mountain lake, steep cliffs, flowing waterfalls and distant misty peaks. Light coral-red prayer ribbons and faded crimson banners provide restrained accents. Detailed old hand-painted fantasy game concept art, believable architecture, worn stone, textured wood, serene martial discipline. Palette dominated by deep sea blue, ocean teal, cool slate, misty blue-gray; pale coral-red accents and subtle ivory highlights. Wide landscape around1536x864; keep the left/center subdued and spacious for UI overlays, attractive temple architecture on the right and visible silhouettes across the distant vista. No people required. No text, readable symbols, UI, logo, frame or watermark. Avoid jade/gold dominance, neon colors, purple, modern buildings or cartoon rendering.

### Meditation

Use case: stylized-concept. Asset type: original wide 16:9 background painting for a fantasy Monk Android launcher, part of a cohesive sea-blue and light coral-red series. Subject: one adult human monk with a shaved head, calm face and athletic natural build, meditating cross-legged on a smooth riverbank rock in the right third of the scene. Simple weathered sea-blue robes with a muted light coral-red sash, hands resting naturally in the lap. A clearly flowing mountain stream curls through the scene with gentle cascades, mossy stone, cool mist, distant fantasy temple terraces. Old hand-painted classic fantasy game art, atmospheric detailed textures, contemplative grounded mood. Palette sea blue, ocean teal, cool slate and blue-gray with light coral-red accents, soft ivory light. Wide landscape around1536x864; left/center spacious and lower contrast for UI overlays, monk clearly recognizable with correct human anatomy and natural hands. No text, readable symbols, UI, border, logo or watermark. Avoid extra fingers, exaggerated muscles, gold/green dominance, neon, purple or modern props.

### Dojo

Use case: stylized-concept. Asset type: original wide 16:9 background painting for a fantasy Monk Android launcher, coherent sea-blue and pale coral-red series. Scene: an ancient training dojo inside a fantasy mountain monastery, worn wooden floors and timber beams, stone threshold and broad open windows toward a sea-blue lake and misty mountains. Training posts, neatly arranged practice staves, suspended sandbags and faded pale coral-red fabric banners; disciplined, lived-in martial training hall. Old hand-painted classic fantasy game concept art, rugged real textures, believable architecture and depth, cool atmospheric daylight. Sea-blue shadows, ocean-teal painted wood, slate blue and blue-gray dominate; gentle ivory highlights and restrained light red accents. Landscape around1536x864, spacious darker left/center for launcher overlay controls, distinctive dojo details and window vista concentrated on right and edges. No text, readable symbols, UI, border, logo or watermark. Avoid modern gym equipment, neon, jade/gold dominance, purple or cartoon styles.

### Combat

Use case: stylized-concept. Asset type: original wide 16:9 background painting for a fantasy Monk Android launcher, coherent sea-blue and light coral-red series. Subject: two adult human monks engaged in skilled unarmed martial sparring in a weathered stone courtyard of a fantasy cliffside temple. Place the fighters in the right third with distinct complete silhouettes: one grounded in a balanced defensive open-hand stance while the other performs a controlled side kick. Correct anatomy, natural limbs and hands, dynamic cloth, readable silhouettes and believable movement. Sea-blue training robes with muted light coral-red sashes, cool ocean mist and distant mountain lake, a few faded coral banners along old temple pillars. Detailed old hand-painted fantasy game concept art, grounded dramatic motion, rough stone and cloth texture. Palette deep sea blue, ocean teal, cool slate, mist blue-gray with restrained pale coral-red accents and ivory light. Wide landscape around1536x864, left/center calm and spacious for UI overlays. No weapons, blood, gore, text, readable symbols, UI, border, logo or watermark. Avoid extra limbs/fingers, anime, neon, purple or jade/gold dominance.

### Temple cleanup

Remove only the faint artist-signature-like writing at the extreme lower right corner. Replace that tiny mark with matching natural weathered stone texture. Keep the entire landscape, monastery architecture, composition, lake, waterfalls, light coral ribbons, sea-blue color palette, aspect ratio and all other details unchanged. Do not add text, logos, signatures, borders or watermarks.

