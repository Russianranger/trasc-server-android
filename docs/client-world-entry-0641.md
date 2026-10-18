# Custom RoF2 world entry after the October 16 update

The October 16 Triptych server sends a **1,440-slot spellbook** in the player profile. The older 720-slot `eqgame.exe` cannot parse that profile and can remain at the character-selection transition. The separate **4 GB patch** only enables large-address memory access; it does not expand the spellbook. The client needs the spellbook executable patch and a rebuilt current-source `dinput8.dll` together.

## Evidence from the reported device

The supplied 0.6.40 logs show that **both deployment tools worked**: LoN import completed at 19:21:48 UTC and quest/plugin synchronization completed at 19:25:04 UTC on October 18. At 19:32:32, world loaded **6,027 card archetypes, zero unreadable, 16 booster sets, 46 starter decks and 179 scenarios**, then reported the card service listening on port 15792. This confirms LoN initialization on the user's Thor for that run.

Neriakc then booted successfully and accepted the character connection at 19:33:57. The client received `MSG_SEND_PC` and the item timestamp at 19:33:58, then stopped advancing before zone loading. Its installed DLL metadata still identifies the September 26 build. These observations match the upstream compatibility contract; they do not indicate a failed quest or card import. The temporary-merchant table warning occurs earlier and does not prevent the successful zone boot.

The repository documents the incompatible profile in [the October 16 spellbook contract](https://github.com/Russianranger/Triptych-Triumvirate/blob/38a4f2ad03203cb2f12dbff26fd613cc47efba0a/Release-NMS-Server/docs/spellbook-1440.md). The executable expansion originates in [thezerodivide/SpellbookSizeUpdate](https://github.com/thezerodivide/SpellbookSizeUpdate). The update doubles the book from 720 to 1,440 entries, relocates its memory storage and extends the client code. Rebuilding the DLL alone cannot perform those executable changes.

The launcher pins that MIT-licensed patch recipe to revision `38a153d273f448ad1953d0b89497470443fd590e`. The supported executable is 8,774,656 bytes with SHA-256 `4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3`, allowing only its known LAA-bit variant before patching. That hash matches the executable reported in the supplied logs. All 115 original byte sites are checked before constructing the expanded output; the resulting exact output hash and original hash are retained with the protected backup. No game executable is distributed in the APK.

## In-app repair

1. Install TRASC 0.6.41 over the existing app. Keep the existing runtime, database, characters, client import and synchronized content.
2. Select **TRASC Custom**, open its runtime, and stop both server and client.
3. Open **Client → Custom client · 1,440-slot spellbook compatibility**. Press **Check client compatibility**. Read the selected source, deployed server and executable reports separately: selecting newer source alone does not change deployed binaries.
4. For the deployed October 16 expanded server, press **Apply 1,440-slot client patch**, review the confirmation and approve. The tool supports only its checksum-verified executable; it retains a protected copy before replacement. An already-patched executable is verified without repeatedly changing it. An unsupported executable is refused, leaving it untouched.
5. Press **Open DLL compiler and deployment**, then **Compile dinput8.dll**. This uses the already imported Microsoft x86 toolchain and selected Triptych source. Wait for a successful build, then choose **Deploy staged DLL**. Re-deploying the old September build does not rebuild it. If the installed compiler is absent, use the compiler tile's toolchain setup before compiling.
6. Check compatibility again and keep **native dinput8.dll** enabled in launch options. Start the server and client, enter the world and confirm that zone loading completes. Check normal inventory, spells and casting, then camp/relog once.

If the executable is unsupported, stop at the displayed checksum report and export logs. Do not rename another client executable to bypass verification. If the deployed server is still the older 720-slot build, keep its matching client until the server and client are updated together. There is no protocol negotiation between these server versions.

**Restore pre-patch executable** restores the protected original after review with server/client stopped. Restoring a 720-slot executable while retaining a 1,440-slot server recreates the incompatibility. The existing 4 GB restore action also refuses to replace an executable that has subsequently changed; perform the spellbook restore first when reverting both changes.

## What this repair preserves

The executable repair does not import `release-peq.zip`, change the database, alter character spell rows, synchronize quests again or downgrade the server. Traditional and TAKP retain their own clients and server content. Existing protected backup and controller flows remain available.

The compatibility report distinguishes selected-source indication from deployed evidence. A recorded deployed commit is trusted for enforcement only after the actual ARM64 zone executable matches its build receipt. New builds record the exact spellbook header and hash. Missing or unverifiable old receipts remain **unknown** and do not silently assert that a newly downloaded source revision is already deployed.

## Qualification and remaining device check

Automated qualification covers supported/prior-patched/unsupported executable inspection, byte verification and exact protected restore, source-versus-deployed compatibility, DLL compiler settings, profile isolation and the full Client UI. CI results and APK/source/signature evidence belong in the release proof after publication. A physical successful world entry with this repair remains a Thor acceptance check; the earlier logs prove the original stop point and successful LoN service, not the repaired client's entry.
