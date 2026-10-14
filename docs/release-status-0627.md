# 0.6.27 input diagnosis — APK qualification pending

Package 0.6.27/code76 adds bounded read-only capture settings, native X event
and Android sent-packet observations for the still-unusable Thor right-stick
camera. This is a diagnostic update; physical camera acceptance remains open.
APK assembly, signing, profile checks and publication must pass before this
draft is described as a published release.

The exact published ARM64 runtime and native-host qualification passed run
38489151047 at source3511ce6260ccef33478983d79356a205b8b43c5d. Default/enabled
capture delivers signed reversals; disabled controls reproduce accepted cached
clipping with an escaped physical pointer. The observer actually collected
bounded XI2, device, focus and pointer evidence under held capture in all cases.
See [takp-input-0627.md](takp-input-0627.md) for sources, limitations and test.

The existing V3 helper and 21 native launcher components are reused. The
working TAKP server/Yaulp, all databases/characters/bots, client assets/prefixes,
installed runtimes, settings, source-update and backup systems remain. This
camera measurement needs no server update/build/deployment, client import or
prefix reset. NPC visibility and Traditional StoneUI remain separate.
