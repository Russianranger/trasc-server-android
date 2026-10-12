# TRASC Android preview 0.6.25 · code 74

Adds **Builds → Updates** in Custom, Traditional and TAKP: check/review source differences, apply changed files, build updated source and deploy a complete verified binary set. Unchanged files and compatible Ninja output are retained. Historical Custom caches need one explicit fresh build because their old receipts lack compiler/runtime provenance; the old cache is kept. Future updates use the new receipts.

Repairs stale TAKP source setup and accepts known qualified older deployed build receipts so an app update does not require replacing a working server merely to start it. The Yaulp source remains pinned to 03e934d0 and requires explicit source update/build/deploy.

TAKP's **Client → Skeleton models** offers a reversible classic-skeleton option adapted from MIT EqSkelePatcher. Only validated user-imported model archives and their related caches are changed, with retained originals and interruption recovery. No game assets are redistributed, and no client DLL is replaced by this option.

Preserves the 0.6.24 all-profile streaming backup/restore and all-world bot command exports, existing databases/bots/characters, imported clients/Wine prefixes, compiled servers, runtime installations, renderer options, mappings, themes and signing identity. The exact previously qualified native launcher payload and camera helper are reused. Camera reversal remains unresolved; no new camera-delivery change or NPC/StoneUI fix is claimed.

See [source updates](https://github.com/Russianranger/trasc-server-android/blob/main/docs/source-updates-0625.md), [skeleton option](https://github.com/Russianranger/trasc-server-android/blob/main/docs/takp-skeletons-0625.md), [Thor acceptance](https://github.com/Russianranger/trasc-server-android/blob/main/docs/device-acceptance-0625.md) and [release status](https://github.com/Russianranger/trasc-server-android/blob/main/docs/release-status-0625.md) for exact qualification, limitations and instructions.
