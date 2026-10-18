# Official NTCore 4 GB patch download

Version 0.6.37 / code 86 adds **Client → Custom client · 4 GB patch → Download NTCore 4 GB Patch**. Open the Custom server runtime, import the Custom client and stop the client before downloading. The button saves `client/current/4gb_patch.exe` next to `eqgame.exe`. The Windows patcher can then be opened from the client's Wine desktop if desired. Downloading never executes it or modifies `eqgame.exe`.

The existing **Apply 4 GB patch** button directly enables the PE Large Address Aware flag without requiring a separate tool. Its protected original and **Restore original executable** remain available. Host editing, controller menus and all-profile database sorting are retained.

## Upstream verification

The [official NTCore page](https://ntcore.com/4gb-patch/) links to `https://ntcore.com/files/4gb_patch.zip`. The app downloads from this fixed HTTPS address only when requested; no NTCore binary is bundled with the APK or redistributed in the source archive.

Verified official ZIP: 21,464 bytes, SHA256 `1e13c263dc55e85cf62e3e30c6b2ce936d4c7e16e3bba3e311a5a8bed4be16ca`.

Verified member `4gb_patch.exe`: 45,056 bytes, SHA256 `980bf5eb62d30c749e5fbf7593e9d25094a4d849a959aa2b7b3fc979b1c93b5a`.

The downloader bounds the response and archive, checks both hashes and installs only the expected executable. An existing verified tool is reused. An unrelated existing file or symbolic link is preserved and reported as a conflict. Custom profile, imported installation, executable revision and stopped-client checks also apply to the download operation. A network or verification failure leaves the client executable and its recovery copies intact.

## Device acceptance

1. Install the update in place, choose TRASC Custom, open its runtime and stop the client.
2. Open the Client tab and expand **Custom client · 4 GB patch**. Download the official tool and confirm its saved path is shown.
3. Find `4gb_patch.exe` beside `eqgame.exe` in the imported client folder. Download again to confirm the verified copy is reused. Downloading should leave the current patch state unchanged.
4. Use **Apply 4 GB patch** and **Restore original executable** to verify the existing protected recovery flow, then start the client normally.
5. Check the new button with controller navigation. Traditional and TAKP retain their independent client settings and do not expose the Custom patch tools.

Physical Android/Wine execution remains device acceptance. Release qualification and artifact hashes are recorded separately after publication.

## Published qualification

Release run [39144890527](https://github.com/Russianranger/trasc-server-android/actions/runs/39144890527) passed for source `6787353e51f50c824e6ec3836086b65f30d8257c`: 616 Python tests without skips, all 19 browser scripts, JVM/C/DirectX, APK assembly/lint, pinned signing and unchanged native payload. The normal v0.6.37 release is verified as GitHub Latest and the compatibility preview contains identical APK bytes. The public APK was independently downloaded, hashed and inspected for the new backend/UI operation. See [release-proof-0637.json](release-proof-0637.json).

A live production downloader call also fetched and verified the official file, preserved eqgame.exe and recovery data, and reused the existing verified tool on a repeat request. Physical Android/Wine execution remains pending.
