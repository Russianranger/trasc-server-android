# 0.6.35 client customization and controller navigation

User request: sync Russianranger/Triptych-Triumvirate with its parent while preserving Android compatibility; expose the upstream 4 GB client patch in TRASC Custom; per-profile eqhost.txt address editing with port preservation and protected originals; default controller menus; publish beta from main.

Release baseline: main 7a8df1df8a3417bbb0ba96e338a1c4080dfafdf5, app 0.6.34/code83. New beta is 0.6.35/code84. Keep applicationId and pinned signing certificate. Reuse the unchanged native payload from the verified 0.6.34 APK (SHA256 7d787bc90c7c53a73f60c1eb1f79820cbb310d90db8149c5e929512d7971f307), retaining native source attribution.

Client file edits are explicit queued operations bound to the selected profile, require a stopped client and use revision checks. eqhost.txt is the correct client login filename; eqclient.ini is unrelated game settings. Existing file contents and endpoint ports survive normal Prepare. Missing host files use 127.0.0.1 and the selected profile's login port. The four-gigabyte operation sets the PE COFF Large Address Aware flag; it does not download or execute a separate Windows patcher.

Recovery copies must be visible under backups/client-connection, protected against file-cleanup deletion, and included in full session exports. Restore actions must validate their original and refuse stale or unsafe files. Existing server login-IP controls remain separate.

## Triptych upstream sync

Prepared draft [PR #4](https://github.com/Russianranger/Triptych-Triumvirate/pull/4), review commit 57a1269c5a306e64ee6b33c062aa7e27a83e311f, integrating upstream 9e62980552d6ef484a974df87e8342a673319c73. It preserves the original Lua include path, disabled UCS Discord forwarding, Android client-version/Bazaar bypass and Android documentation. All 473 zone CMake references exist. Full ARM64 compilation/device verification was unavailable. Automatic approval review rejected updating Triptych main, interpreting the explicit main publication instruction as launcher-only; the review branch is preserved and the default branch is unchanged pending explicit approval.

## Device acceptance

1. Install in place and open the Custom runtime. Client → Login address should show the imported eqhost.txt address and its original port.
2. Save an external address, run Prepare client, verify the address and port persist; restore the original. Repeat in Traditional and TAKP with their own ports.
3. With the Custom game stopped, apply the 4 GB patch; reapply should be a no-op. Start the client, then stop and restore the original when desired. Other profiles should not expose a patch action.
4. Use LB/RB through all visible tabs; D-pad focus, A to expand/activate and enter text, and B to collapse. Test with keyboard dismissal and controller input diagnostics.
5. Confirm existing mouse look, profile switching and all-profile export remain usable. No physical acceptance is claimed before the user's results.

## Validation status

Initial local full regression attempts were obstructed by a full 32 GB shared scratch filesystem, producing storage-guard failures rather than a qualified pass. The main-branch beta workflow is the release gate for the full Python/JVM/C/browser suite, assembly, lint, pinned signing and native reuse. Publication is allowed only after those checks pass and current main equals the built commit.

Local final regression: 592 Python tests completed with 30 dependency-dependent skips and no failures using a memory-backed temporary directory. Production JVM/C management regressions passed. New native launcher-controller Java test, protected-recovery tests and Node VM UI race tests passed. Browser and Android qualification remain CI gates.

The TAKP legacy section-name launch repair is included in the recovery checksum journal before host changes, so protected Restore remains available after the known conversion. Regression covers legacy Save → launch repair → Restore → launch repair → Save → Restore.

## Published qualification

Release run [39091813067](https://github.com/Russianranger/trasc-server-android/actions/runs/39091813067), attempt 2 succeeded for source 589606cf239749709cfa95fcbc27189464984589. All 592 Python tests ran without skips, all 18 browser scripts and the JVM/C/DirectX suites passed, followed by APK assembly, Android lint, pinned signing and exact native reuse checks. The same verified build artifact was retained for a publication-only retry after the initial newly created draft took time to appear in the release list. See release-proof-0635.json for public artifact digests. Device acceptance remains pending.
