# Optional classic TAKP skeletons

The TAKP Client option adapts the MIT-licensed [EqSkelePatcher](https://github.com/Russianranger/EqSkelePatcher/tree/c3382bc492a9810bcbea50e78cda4463f514c95b), written by Nick Gal. It changes `SKE` to `LSK` in the string tables of `gequip5.wld` and `global6_chr.wld`, inside the two corresponding `.s3d` archives. The audited upstream source, license and pinned provenance accompany the app in `backend/takp-skeleton-patcher`.

This is an optional model asset change. It does not alter server rules, databases, skeleton spawn records, EQW, DirectInput, Wine, graphics DLLs, controller mappings or renderer selection. It does not resolve the separately tracked TAKP NPC visibility problem. Physical client appearance remains an AYN Thor acceptance test.

## Enable and restore

1. Stop the client. Select **TAKP World**, then the **Client** tab.
2. Enable the classic skeleton option and apply it. The app first validates both archive structures, their compressed blocks and matching WLDs. Both must contain the upstream `SKE` identifiers; unfamiliar or already modified archives are refused before activation.
3. Launch the client and check skeleton NPC/pet appearances in a familiar zone. Keep the renderer and camera settings unchanged for this comparison.
4. Stop the client, disable the option and apply it to restore the exact original archive bytes. Check the same NPCs/pets again.

The app retains the original archives and the two related root texture caches (`gequip5.wld.txc` and `global6_chr.wld.txc`) under the imported client's `.trasc-skeletons` directory. Enable removes only those two cache files so the client can regenerate them. Restore reinstates any caches that existed before enable. An unrelated cache is never removed.

Any model edits or newly generated caches made while enabled are retained in the restore transaction's `before` directory. They are not silently discarded. Restore refuses corrupt or linked original backups. A replacement client import requires restoring the original skeletons first, preserving the association between the managed patch and its originals. Existing full session/all-profile backups include these originals and receipts as part of the client tree.

## Qualification and limits

The parser uses the primary PFS/S3D format: 12-byte header, independently checked non-reflected filename CRCs, directory sentinel `0x61580ac9`, bounded zlib blocks of at most 8 KiB, and exact WLD fragment boundaries. It accepts differing directory/index orders, zero-sized unrelated entries, gaps/orphan data and either optional timestamp byte order. It preserves the original index order, compressed directory, footer, all unrelated compressed assets, WLD string offsets, fragment bodies and trailer. Only the new WLD's compressed blocks and its index offset are changed.

Limits are 256 MiB per archive, 32 MiB per target WLD, 2 MiB filename directory, 10,000 archive entries, 512 MiB total uncompressed archive contents and 64 MiB per related texture cache. Untrusted size declarations are rejected before large allocation. Enable checks space for original/before/after copies, atomic replacement and rollback, then repeats the free-space check after staging.

Every backup and replacement is hashed before a durable transaction is written. No live asset changes until both archives and cache backups qualify. Parent directories, new files and transaction receipts are fsynced. After interruption, the next server/runtime startup or TAKP game launch rolls all four targets back to the prior state; unexpected changes are preserved before rollback, and an invalid receipt refuses recovery before writing live files. A completed transaction can finish its receipt cleanup without repeating activation.

Automated fixtures use public format data and contain no proprietary game assets. They cover independent CRC/XOR known answers and upstream replacement semantics, block and XOR boundaries, non-ASCII strings, both WLD versions, untouched compressed data/fragments/footer, malformed ranges/zlib/headers, bounded bomb refusal, byte-identical restore, modes, caches, cancellation, disk pressure, copied-file corruption, concurrent edits, changed originals, imported-client identity, and interruption during enable/restore. They establish archive/recovery behavior; they do not establish the visual result on the Thor. Upstream also tracks possible zone skeleton texture conflicts, so compare multiple skeleton zones and revert if needed.
