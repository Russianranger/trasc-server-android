Warning: truncated output (original token count: 104543)
Total output lines: 2596

# 0.6.34 published — session preparation after the file picker

Read [session-handoff-0634.md](session-handoff-0634.md) and
[release-status-0634.md](release-status-0634.md). Source `cff8beb`, release run
38998882560 passed and published version 0.6.34/code 83. The APK SHA256 is
`7d787bc90c7c53a73f60c1eb1f79820cbb310d90db8149c5e929512d7971f307`.

The new 0.6.33 Thor report failed twice in WorldProfiles.beginMaintenance before
archive writing. No session transfer is active in the report. The immediate
one-lease test races launcher resume/poll leases after SAF. The session gate now
reserves admission and drains existing requests outside the runtime monitor,
with bounded timeout/interruption cleanup and retry tests. Cleanup remains
immediate. Old immediate-gate behavior fails the new concurrency regression;
new behavior passes locally and in exact-source CI.

569 Python tests/zero skips, JVM/C, all 16 browser scripts, 600,661-record and
4,294,967,313-byte production roundtrips at 48 MiB, assembly/lint/signing and
exact 0.6.33 native reuse passed. No archive format/native camera change and no
server/client rebuild or prefix reset. Install in place and retry Files → Export
all profiles. Physical Thor SAF/lifecycle/restore acceptance remains pending.

---

# 0.6.33 published, merged and independently downloaded — October 16 UTC / October 15 Chicago

Read [release-status-0633.md](release-status-0633.md) and
[release-proof-0633.json](release-proof-0633.json) first. PR #39 merged as
`5e86e6b`; source `de3d2a5`, release CI 38847312963 passed. Public APK
18,970,100 bytes / SHA256 `34a55129b0e46a09f2659abee8141fa664c3d059474a2b45475fcc8d11ab54f4`; code 82.

The 0.6.31 physical all-profile export failure is confirmed: combined 200k-entry
preflight ceiling. Production v3 streaming export/restore now passed 600,661
records (200,001 fixture client files per world) and >4 GiB content with hashes
at 48 MiB heap, plus 569 Python/zero skips, 16 browser scripts, JVM/C, lint,
signing and exact native reuse. Hashing contexts are reused and archive path
validation is literal. Existing v1/v2 read support and atomic activation remain.

New v3 backups need 0.6.32+ to restore. Accepted native input/camera/helpers,
server/client binaries and installed data are preserved. Next is physical Thor
Files → Export all profiles; retain ZIP and fresh report. Reopen runtime after
export. Physical external-provider export/restore remains pending; do not mark
it passed from host CI. No rebuild/import/reset is required.

---

# 0.6.33 final hashing-context safeguard — current continuation

The v3 streaming format passed full release CI in run 38845198585, including
600,661 records and a >4 GiB roundtrip at 48 MiB, all 569 Python tests/zero
skips, browser flows, Android lint/signing and native reuse. An intermediate
0.6.32 preview was published from 6c89973; it is not physically accepted.

Final 0.6.33 additionally reuses one file SHA256 context per sequential
writer/reader, with explicit reset between files, avoiding per-file digest
provider/native allocations. This does not change the v3 wire format.
Basic/legacy/adversarial/activation/cancellation tests passed locally after
that change. Final exact-source stress CI and publication remain pending.
New v3 backups require 0.6.32+ to restore. Existing v1/v2 readers are retained.
Do not rebuild/reset the user's working server, client, prefixes or camera.

---

# 0.6.32 scalable all-profile backup — current continuation

0.6.31 physical export FAILED on October 15 at 21:56 Chicago. Device bundle
`logs-8167277602799695405.zip` records the handled 200,000-entry preflight
ceiling in SessionArchive, not an export-time OOM. The old 190k qualification
was below this real combined installation. The exact total count is unknown.

Format 3 now streams records within one ZIP payload, with a second small
manifest. ZIP metadata is constant-size; restore verifies sequentially in
isolated staging and finalizes links/modes using a reverse disk journal.
No whole-archive heap inventory or private export ZIP copy is introduced.
The same production createAll entry point and existing quiesce/checkpoint,
SAF cancellation/failure cleanup and atomic activation are retained.

Read docs/session-stream-0632.md. Local 600,661-record roundtrip (200,001 real
client files per world) and 4,294,967,313-byte streaming roundtrip with independent
SHA256 both passed at 48 MiB heap; CI/publication status must be checked before delivery. Existing
single-profile/v2 archives remain readable; v3 backups need 0.6.32+ to restore.
Physical Thor large export/restore remains pending; accepted native camera,
server binaries, clients and installed prefixes must remain preserved.

---

# 0.6.31 published and independently downloaded — October 15, 2026

Read [release-status-0631.md](release-status-0631.md) and
[release-proof-0631.json](release-proof-0631.json) first. PR #38 merged; release
run 38815690385 passed, including all 569 Python tests/zero skips, 16 browser
scripts, all three heavy archive cases at 96 MiB, Android lint/signing and
exact accepted 0.6.30 native reuse. Public APK 18,960,032 bytes / SHA256
`132243827df0dcf2d275e9a01396111861b8a94a35a0d2b267be5727b9537105`; version 0.6.31/code 80.
Files → Export all profiles and readable absent-prefix collections are ready
for Thor testing. Existing runtimes/data/clients/prefixes and accepted native
camera helpers are preserved. Physical external-provider export/restore
remains pending. No server rebuild/import/reset is required.

---

# 0.6.31 profile export discoverability and absent prefix collections

Current work starts at main `47ede4f` (physically accepted 0.6.30 camera).
Scope: Files now has **Export all profiles**, sharing the existing direct SAF
ZIP64 exporter with Server → Session backups. Both controls use the same busy,
installation and transfer gates. No archive buffering or second private ZIP
is introduced. Existing quiesce/snapshot, progress, cancellation, memory/file
count/index limits, destination failure cleanup and verified restore remain.

Files → Old Wine prefixes returns a profile-scoped empty listing when the
lazily created collection does not exist, instead of exposing a Java private
path exception. Known missing backup/export/import collection roots are also
empty. Browsing creates no folders. Unknown paths, symlinks, protected files
and deletion confirmation remain guarded. Clearing browser results now clears
stale per-page cleanup entries. Existing prefix contents remain browsable.

Physical large external-storage export/restore remains pending. Use exFAT or a
provider supporting >4 GB files; source size alone does not guarantee destination
capacity. No claim of guaranteed immunity to Android/system/provider failure.
APK must preserve the current certificate and all 0.6.30 native components.
No server/runtime/client rebuild, reimport or prefix repair is needed to test.

Validation/publication status: see the profile-backup-launcher Actions run for
this commit. Local host ZIP64 roundtrip passed at 4,294,967,313 bytes with a
96 MiB Java heap and matching source/restored SHA256. Other checks are recorded
below after completion; do not infer physical Thor qualification.

---

# 0.6.30 physical TAKP mouse-look acceptance — PASS

On October 14, 2026, the user reports: “That worked!! It's perfect now.”
The fresh AYN Thor / Android 13 / TAKP / 1280×720 / Turnip 26 / DXVK 2.5.3 /
Native Surface / accurate CPU / right-stick capture confirms the fix.
Read `docs/device-camera-0630.md` and `docs/device-camera-evidence-0630.json`
first. This supersedes the camera-pending status in the publication snapshot
and the historical 0.6.29 camera failure for this tested configuration.

Bundle `logs-1420871679027905814.zip`: 783,177 bytes, SHA-256
`f3001e2135723deadfff8a0819a3241e68fadc52bb8ea07d95387a6049c62f9a`.
Exported October 14 at 17:37:37.104783 UTC / 12:37:37.104783 Chicago.
Device explicitly reports 0.6.30; code 79 is the published release mapping.
The installed official V3 helper upgraded to exact V4 ae556d… and the V2
focus helper fcec1f… ran. Existing Wine prefix was reused.

One guarded PointerRoot → Client1 repair wrote sequence 1; the actual game
consumed that sequence with successful same-owned-clip refresh 23 ms later.
Twenty inspector and 44 XI2 held samples show centered capture afterward.
125/125 sampled XI2 motions within packet-log coverage match signed input
with 0–5 ms delivery. Of 98 physically held nonempty DI buffer samples within
coverage, 97 reconstruct uniquely with conservative 0–8 ms endpoint delivery;
67 same-frame game consumers match those signed sums, both signs/both axes.
Thirty-five post-refresh zero-result consumers produce zero camera delta
and unchanged accumulators. Six successful clip releases and Look-off records
support leaving/reentering Look. The user's usability acceptance closes this
camera-failure gate; retain 0.6.30 as the working baseline.

Queue drops are zero. Diagnostic limits differ: pointer log hit its byte cap
with one unwritten selected record; window inspector cap dropped two records;
camera trace reached its inferred byte cap. XI2 is sampled. One 2 ms-old brief
RMB press lacks camera-trace coverage; background/resume is not separately
labeled. Five XI2 errors occur only during RMB-up teardown, not held gameplay;
the focus helper ends with zero errors/drops. Export still said Stopping/alive,
so there is no final fully stopped/server-shutdown receipt.

The existing server started in seven seconds; saved character ID 4 entered
Paineel and camped normally. Forty-eight selected stable configuration/runtime
fields match the previous launch; registry bytes are not identical and
backup binaries are not in this log bundle. No new build/import/reset is
recorded. Server/update/deploy/Yaulp completion remains confirmed from prior
user reports. Full inventory/saved-bot/all-profile backup persistence,
classic skeleton visual/exact restoration, physical incremental/no-work
receipts, NPC visibility and Traditional StoneUI remain separate checks.

The records below describe publication-time status before this physical pass.

---

## 0.6.30 publication receipt — before physical acceptance

Read `docs/release-status-0630.md`, `docs/release-proof-0630.json`,
`docs/takp-camera-client1-0630.md` and the physical
`docs/device-camera-0629.md` / `device-camera-evidence-0629.json` first.

APK 0.6.30/code 79: 18,959,432 bytes, SHA-256
`ef0237e0d0d767f7a6e0e37403803b5de0b7bc1d765e496930d422a57fd9fb31`.
Published October 14 at 16:03:22 UTC / 11:03:22 Chicago.
Source/tag `875e9dcc68f7aae10cc372077d00b3da2c7e84a3`, tree
`0ad1ca75e76d9fbb000c95c0b2d5fc75a067ddff`; PR 37 merged as
`e0da75f45dbdc3882212ec564c82224b53a3b5d9` with the exact qualified tree.
Main adds documentation receipts only; preview keeps the qualified source.

All five release jobs in run 38593150423 passed: 569 Python tests, zero skips,
management JVM/C/browser/controller, assembly/lint/signature and all three
production profiles. Independent actual public audit verified all four
asset digests, cryptographic v2 signature with original certificate/no
errors or warnings, 132 source assets, 610 archived Git files, all 21 retained
native components and exact successful CI helpers/proofs.

Native run 38590631222 at `08f373040e7e0a4dbc59c14f7858868ddd620062`
passed three scoped repair/notification/owned-refresh sequences, 24 exact
signed segments including centered restore, 32 focus refusals and nine reader
refusals. Actual MSVC EQW: 95,232 bytes /
`ae556d045a0b64586b1e4f0c0957a75c99626f9f149f8e95b7bb99ed7a738fc8`;
ARM focus: 72,744 bytes /
`fcec1f6a4f0d1101efef56f58671b47944fd19219f0eeb3a4591a66607f5b364`.
Five build/22 fixture fingerprints and shared V4 headers match. Observer
phases end normally/drop 0; one RMB-up startup X error precedes the helper,
none during focus actions/resume. Eight exports/11 DLL dependencies match V3.
The fixed-address game DLL cannot run in the open PE32 fixture; shared
capture/reader code was exercised on the actual published ARM runtime.
Exact Wine 10 source review confirms normal explorer launch passes current
event paths and nonce despite desktop reuse. Five protected known-V3 upgrade/
repeat/no-write refusal transaction checks passed.

Latest physical 0.6.29 result remains FAIL: user reports weird right-stick
movement. Exact visible Client1/STRING8/7 window and 22-byte eqgame.exe class,
correct pointer ancestry and PID were captured. The old title-only mismatch
caused zero requests. Native input retains sign/timing; escaped physical cursor
offsets explain reconstructed fresh wrong/opposite game deltas. Full facts,
14 source-log hashes and limitations are in the physical evidence documents.

V4 addresses the centered-focus capture gap found by stricter qualification:
12 fresh +1 became 78 while Wine returned a cached centered cursor. The
companion writes a canonical private <=96-byte launch-token/sequence event
only after scoped native focus success; the reader polls <=once/20 ms.
One same already-owned clip submission requires current generation, physical
Look, foreground and visibility. No added warp/drain/axis conversion,
registry change or runtime replacement. Events have no age binding: a paused
hook can later refresh its currently owned clip once, never acquire foreign
capture. Capture-disabled/unknown prefixes remain preserved. Known official
V3 upgrades with exact eqw.0626.dll backup and earlier originals retained;
changed/custom helpers or unsafe/changed backups refuse before writes.

Next gate is PHYSICAL CAMERA ACCEPTANCE, not another source/build/import/reset.
Camp/stop normally; update in place without uninstalling; reopen TAKP with
the working server/Yaulp/data. Keep settings and test short right-stick both-axis
reversals/neutral/Look off-on/background-resume within five minutes. Camp/stop,
wait stopped, export fresh bundle. Check V2 focus_repair/event_written and
matching V4 focus_clip_refresh plus native physical confinement, signed game
reversals, neutral stop and free menu pointer. No usability claim before
device behavior and measurements agree.

Confirmed server start/saved-character load, source update/build/deployment
and Yaulp correction remain separate from unresolved camera acceptance.
NPC visibility, Traditional StoneUI, post-camp expired session key,
all-profile external backup/restore, saved-bot/full-character persistence,
classic skeleton visual/exact restoration and physical incremental/no-work
object receipts remain separate. No release build remains running.

---

# Published 0.6.29 — read-only TAKP window diagnostics (October13 Chicago)

Read docs/release-status-0629.md, release-proof-0629.json, takp-window-0629.md and device-camera-0628.md / device-camera-evidence-0628.json first. Public APK0.6.29/code78:18,952,880B, SHAe81e6afe2ac639a292d7c048cc7575a9cbd1af6a19f2cfe4a934f2c723e40fcf; uploaded2026-10-14T03:32:36Z/October13at22:32:36Chicago. Source/tagaff675a1564c1bfee850dc5400de2b4cbed410bb, treeb7995938db2dfc8324c3e966d0b3651c98021bcf; PR36 merged4032f5922e07f9278706b947c02b03dfee0d8148 with exact qualified tree. Main adds documentation receipts only; preview remains qualified source.

All5 release jobs38505887209 passed,566Python tests/zero skips, management/JVM/C/browser/controller, assembly/lint/signing and all3profiles. Independent actual public audit verified cryptographicv2 signature/no errors or warnings/existing cert, all132 APKsources/all598 archivedGitfiles/all4asset hashes. All21native components, V3, oldfocus/observer/TAKP assets and olddiagnostic modules byte-equalactual0.6.28. Inspector/proof byte-equal actual successfulCI artifacts.

Latest physical0.6.28 FAIL: user says mouse weird/not functioning. Qualified90dda77c focus companion ran with attempts0/successes0/errors0. HeldRMB+PointerRoot gates pass; targetdiscovery returns no_exact_visible_game_under_pointer. Unknown actual title/type/length/class/visibility/layout predicate. Do not broaden ownership or claim XSetInputFocus failed—it was never called. All31held native snapshots PointerRoot;113/113sampledXI2 equal signed Androidpackets0–3ms/zero drops. Physical719,326 minus7left pixels -> game72,-34 atcenter640,360;3moreleft ->69,-34. Eventsfresh. Same savedcharacter Paineel/camp, no newcrash/import/reset; expiredpostcamp session key separate.

0.6.29 adds NEW read-only native window inspector and supervised launcher assets/finalchildstatus refresh. Existing camera/settings/ownership unchanged. Bounded16node pointerpath/128node once-held candidate tree/128byte properties/type/count/hex/geometry/parents/PID; nofocus/warp/grab/injection/propertywrite/atomcreation. Duration300/hard301/log128KiB; collection failure never blocksclient. ARM38505023364 at50ae39a550a6597a294f92502693e28b625ef993 passed14actualproperty/layout cases, focus/pointer/buttons unchanged, normalend/drop0/Xerror0/max15928B, CLI0/301/NaN refusal andSIGTERM. Exact publishedruntime/input/focus/observer reused. ELF72,232B/SHAe1df07509f870d35f8feea87e64f20101597bd14dbc5ed0632335906b312d21c; build4sources+fixture12hashes matched. Receipt max_seconds300. Collection is qualified; actualgame identity and usableThorcamera are not.

Nextdevice: camp/stop clients+servers normally, installinplace without uninstall, reopenTAKP. Preserve workingserver/Yaulp/data/clients/prefixes/runtimes/settings; no server source/build/deploy/import/reset. Within first5minutes enter savedcharacter, Lookon, rightstickright/left/up/down10s, Lookoff, normalcamp/stop, waitstopped, exportfreshbundle withclient-takp-windows.log plusfocus/XI/packet/state/EQW. Use actual rejectedwindow/path facts for smallest ownership-preserving matcher correction. Camera remainsfailed/pending. NPC/TraditionalStoneUI/postcamp sessionkey/allprofilebackup/bots/skeleton/physicalno-workobjects separate. No owned build remains.

---

# Published 0.6.28 — scoped TAKP native focus recovery (October13 evening Chicago)

Read `docs/release-status-0628.md`, `docs/release-proof-0628.json`, `docs/takp-camera-focus-0628.md` and `docs/device-camera-0627.md` and `docs/device-camera-evidence-0627.json` first. Public APK0.6.28/code77:18,936,371B, SHA-256 `0073d46cc5b58c2a7f27c68d11e5fd3cc58a0b6afb8f208d19c7615bbba02859`; uploaded2026-10-14T02:38:02Z/October13at21:38:02Chicago. Source`8d650b2537acbb2ca3a05b34e5a98e9c2e9a7225`, tree`589bf58ce3f5cdd4c3b1554b554c0aac724f3ed3`; PR35mergedas`42781b8d1799c88110a92a9f5f2203830d93d579` with exacttree. Preview remainsqualifiedsource; main adds docsreceipt only.

All5releasejobs in38501118405passed,562Pythontests/zero skips,management/JVM/C/browser,assembly/lint/signing/threeprofiles. Independent actualpublic audit verified cryptographicv2signature/no errors or warnings/existingcert,128APKsources,582archivedGitfiles/all4assetdigests. All21existingnativecomponents,V3,TAKPassets andobserver byte-equalactual0.6.27. NewfocusELF72,232B/SHA90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865; build/proof bytes matchactualsuccessfulCIartifacts,all8repairrows strictlyscope-valid/6refusal outcomes/nativecountclosedtransport verified.

Physical0.6.27failed: userweird/unwieldy;40held snapshotsXfocusPointerRoot whileWineforegroundtrue;71sampledXI2motionsmatchAndroid0–2ms; freshpacket306(-1,0)->game(+16,-96), escapedpointeroffset. Registryenableddefault,source/master/RELvalid,eventsfresh. ExactARM38500575431atd0bd98e387727a7eae14a728eea4541c05610674 reproducedfault-1->+2, then actualfocus/physicalcapture recovery,10signedstate+buffersegments,zeroidle,menu/RMBrelease,6guards,Noneafterresume. OpenPE32fixture800x600,notproprietarygame/Android/Thor success.

RecoveryonlyNone/PointerRoot + physicalRMB + actualpointerdescendant through exactvisibleEqW-TAKP/eqgame.exe; rejectsconcreteforeignfocus/wrongmissingidentity/hidden/RMBup; capturedisabled/unknownpreserved. No global search/warps/grabs/injection/propertywrites/registrychanges. Supervisedlifetime,100mspoll/500msretry/2sXrequesttimeout/128KiBlog; capdoesnotstoprepair,exitreported/no blindrestart. Originalruntime/inputbridge/wineserver/observer/V3 unchanged. Keepworkingserver/Yaulp/data/clientassets/prefixes/runtimes/settings;no rebuild/import/reset.

Nextphysicalgate: installupdateinplace,enterexistingcharacter,keepinputsettings,testThor rightstickhorizontal+verticalshortreversals/diagonals/neutral withinobserverfirst5min,Lookoffmenu/backgroundresume/campreopen,stopnormally/exportfreshlogs includingclient-takp-focus.log +native/pointer/state/EQW. No cameraacceptanceclaimbeforeusabledevicebehavior/nativeconfinement/signcorrelation. NPC/StoneUI/all-profilebackup/bots/skeleton/no-workobjectreceipts separate. Noownedbuild remains.


---

# Published 0.6.27 diagnostic update (2026-10-14 UTC)

Read `docs/release-status-0627.md`, `docs/release-proof-0627.json` and `docs/takp-input-0627.md` first. Published APK 0.6.27/code76: 18,923,551 bytes, SHA-256 `603776458fb2d245262bb36febdec5380557270cc39f5bc476267e21095f5595`, uploaded 00:41:48 UTC (October 13, 19:41:48 Chicago). Source `8086fc2bc5a13a4c385bdf7910f7d941310da233`, tree `e685e2f149ac3358d842744cd3647e3f1b69e3f2`; PR #34 merged as `bca4328715625a11f64071c42217d8155d0c4017` with the exact tree. Preview remains on the qualified source; main adds only documentation receipts.

All five jobs in run38490628425 passed: 559 Python tests/zero skips, management/JVM/C, APK assembly/lint/signing and three server-profile gates. Independent public audit cryptographically verified v2 signature/no errors or warnings and preserved certificate; 124 bundled source assets, 566 archived Git files and all public asset digests matched. All21 existing native launcher components and the V3 DLL match actual0.6.26 bytes. New observer ELF SHA5f5cf7e8f8d2d3df475284f72fa0f2944e1cadb9ba334927021799615b35744b and its source/build/runtime/observer receipts match.

Exact published ARM64 runtime/production bridge/patched wineserver passed five controlled prefix cases in run38489151047 at3511ce6260ccef33478983d79356a205b8b43c5d: default/Y deliver signed reversals; N reproduces API-success/physical escape. Actual observer logs qualified under held grabs. This does not identify the user's registry setting or establish proprietary-game/Android/Thor usability. No runtime/helper/native Android rebuild.

User confirmed V3 slight improvement but still unusable, similar to previous behavior. 0.6.27 adds observation only: read-only named prefixsettings, bounded native XI2/core/focus/pointer and Android queued/sent signed packets (bounded256 queue+daemon disk writer, no keys/chat). Keep working server/Yaulp/data/prefixes/runtimes/settings; no server source/build/deploy/import/reset. Next: install in place, enter saved character, test short right-stick reversals/bothaxes/diagonals promptly within the firstfive minutes, stopclient normally and exportfresh logs. Compare all three layers before changing capture settings or camera delivery. Camera,NPC,StoneUI and other preservation/object-reuse gates remainopen. No owned build remains.


---

# Latest device follow-up: V3 loaded, confinement still fails (2026-10-13 18:12 Chicago)

Read `docs/device-camera-0626.md` / `docs/device-camera-evidence-0626.json` before earlier release history. New `logs-836710138545428717.zip` confirms 0.6.26/code75, expected V3 helper/native module, upgrade from prior official bytes and prefix reuse. Existing server and saved-character world entry logged; no new source/build/deploy/database initialization. Client still alive at export, no new crash. Full bots/inventory/three-profile preservation not proved by these logs.

Physical capture invariant fails: 48 ClipCursor recovery calls all ok=1, but 36/60 held clip samples escaped; retries >=250ms; REL/no PEEK, held event ages1–25ms; 34/35 nonempty held buffers have individual last-axis >19px, max92. Startup19.238s-old event is Lookoff, not held backlog. Look release restores fullclip. Do not mark camera fixed or equate API success with confinement. At bundle review there was no subjective report; the subsequent user follow-up confirms slight improvement but still unusable, similar to previous behavior.

Next: read preserved global/app GrabPointer registry values without overwriting; correlate actual X focus/master/source devices/relative valuators/core vs raw events/XQueryPointer/DirectInput with known signed inputs and intended stick directions. Real Box64+Bookworm/TigerVNC1.12 runtime differs from host-native fixture. Complete root cause unresolved; no more blind retry/ABS/queue-drain changes. Keep working server/Yaulp and data. NPC/StoneUI, all-profile backup/bots/persistence/skeleton restore/no-work-object receipts separate. This historical checkpoint preceded the diagnostic qualification/publication now recorded above.

---

# Released 0.6.26 — physical right-stick acceptance (2026-10-13 UTC)

Read `docs/release-status-0626.md`, `docs/release-proof-0626.json` and `docs/takp-camera-0626.md` first. Qualified/published source `72f482c58986d4b9d62f7d7e264cf5eadb4c80c1`, tree `6ace7009cb7b5aa891ad66d5583b34429384928c`; PR #33 merged as `6ebe155ed8ae02c0b8eeff90d716a448c5509fb0` with the exact tree. Run `38350483443` passed all five jobs, 553 Python tests/no skips, JVM/browser/controller/DirectX, APK assembly/lint/signing and all native profile checks. Native camera run `38349508008` separately passed actual lost-X-grab recovery and exact signed movement/zero drift. No owned build remains.

Public APK 0.6.26/code75: 18,901,782 bytes, SHA-256 `7bb7a902c5695a430e396ddd035703b4cce278c11896b371a98363090290fa85`. Prefer the release download URL with `?v=0.6.26`; a bare URL initially returned cached 0.6.25, then verified current. Independent public audit verified original cert identity (signature validity by CI), 119 exact APK source assets, all 544 archived Git files, preserved 0.6.24 source archive and all 21 native bytes equal actual verified 0.6.25. V3 helper SHA `875056a62d2df3c7434bf05d23d73186d6565d2bd5a14f2f53a58fa7d015bab3`.

User physically confirmed existing-server/saved-character startup before update, source apply/build/deploy and stopped cleric idle Yaulp. Log: only player_bot.cpp.o compiled then zone linked; 55s/two jobs, deploy21s, server-start6s excluding login. Failed mouse-look reproduction was Thor right stick; fresh REL consumer trace showed escaped cursor despite cached clip. V3 only retries observed escaped owned clip at 250ms bounds. Known helper upgrades retain originals, custom/unsafe backups refuse; no server/database/runtime/settings/native Android changes.

Next: install APK in place, stop/relaunch TAKP client, retain working server without rebuild/reimport/prefix reset. Test right-stick short reversals/vertical/diagonal/neutral, Look off/on, menu/chat, resume and zone change; export short fresh trace including V3/clip_repair rows. No actual Thor camera success claimed. NPC visibility/Traditional StoneUI remain separate; full all-profile backup/persistence, skeleton visuals/exact restore and physical no-work rebuild/object receipts remain open. Documentation checkpoint does not require APK rebuild.


---

# Released 0.6.25 — move to AYN Thor acceptance (2026-10-12 UTC)

Read `docs/release-status-0625.md`, `docs/release-proof-0625.json`, `docs/device-acceptance-0625.md`, `docs/source-updates-0625.md` and `docs/takp-skeletons-0625.md` before older history. Qualified source `92a2bd663e1a7d4a433494c6e7cb59a82e41bd4a`, tree `20b024d19095fb68ff642c511aed77f708b82135`, branch `codex/takp-world`/alias `codex/source-updates-skele-0625`; PR #31 merged as `5d6b581c44d1a05816ed2b6288c34a0220d58805` with the exact tree. Main adds only documentation receipts after merge, with no rebuild. Preview points to qualified source.

Verified APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 18,901,006 bytes, SHA-256 `cfef9fffc28285e95913b8782f98c9d0822e67a06414f86c37180a9b9cc85feb`, uploaded 2026-10-12T04:44:46Z. Run `38204284306` passed all five jobs, 551 Python tests/zero skips, JVM/DirectX/browser regressions, Android assembly/lint/signing and native integrations. Independent public download checks package 0.6.25/code 74, original signing identity, 119 bundled source assets, 541 exact archived files and all 21 native bytes equal verified 0.6.24; preserved source archive and receipts remain intact.

Repairs stale TAKP source reuse and known released deployment receipt invalidation that disabled Start server. All-profile Builds → Updates applies only reviewed deltas, preserves local work/source stamps, uses compatible compiler objects and deploys strict verified sets. Production old TAKP → new app/source qualification started the old server, preserved database/settings/stage/deployment, recompiled one of 375 objects and required a true no-op build. Historical Custom cache needs one explicit fresh build to establish missing provenance; old cache retained. Both modern native profiles passed 28 checks with exact compiler cache reuse.

Optional classic skeleton assets: pinned MIT EqSkelePatcher adaptation, bounded two-archive validation, retained originals/related caches, durable activation/recovery and explicit restore. Requires open TAKP runtime and stopped client. Reopen runtime after all-profile backup export before Updates/model controls. Existing all-world command exports, combined TAKP spawn/revive and all-profile ZIP64 backups are preserved.

No camera-delivery change: helper SHA `495d6e1711e21f012d1f8c9581af74fdbdccac5f45e2e93508e40b4bd3dbca1d`. Current screenshot/log bundle contains no fresh diagnostic consumer trace. Next: physical Start-server check; external all-world checkpoint; explicit source/build/deploy for already-qualified Yaulp; short camera touch/stick both-axis trace; all-world bots/social/hotbar and large Android SAF/lifecycle acceptance; skeleton appearance and restore. NPC visibility and Traditional StoneUI stay separate; do not speculate. Preserve all databases, clients/prefixes, binaries/receipts, runtimes, mappings, renderer/themes/settings and signing identity.

Recovery: exact main `0742d1367a3cf5bf26b69231c7df9e97bc25d6d1` recovered after scratch maintenance removed prior checkout; committed 0.6.24 source and handoff were recovered, no accessible unfinished work/active build was assumed. Failed runs `38201744261` / `38203254344` finished before subsequent qualification. Three harness corrections only: stale pin, stopped bootstrap database, and redundant content re-import. Production code unchanged; no competing jobs. No unfinished implementation/owned build remains; current worktree should be clean on main after receipt commit. Inaccessible previous-agent workspace work remains unknown. Use release proof for final exact commits/assets/CI evidence.

---

# Released 0.6.24 — device acceptance remains (2026-10-11 UTC)

Read `docs/release-status-0624.md`, `docs/release-proof-0624.json`, `docs/device-acceptance-0624.md`, `docs/takp-camera-0624.md` and `docs/modern-bot-commands-0624.md` before older history below.

Latest qualified/published source: `02a1af7aa8d7a808aafcf4421971a15e9110a8cc`, 0.6.24/code73, tree `cef59fa3bd5a1b9f655b9a2d48eec02ec6a53531`, on `codex/takp-world` and `codex/takp-input-bots-backup-0624`. Preview tag points to that exact source. PR #30 merged as `dab13281d191e94ea06c3e8ad1fcf1f28f08dc6e` with the exact tree; main adds the documentation checkpoint after this merge. These receipts do not need an APK rebuild.

Run `38103647834` passed all five jobs, 505 Python tests with zero skips, JVM/browser regressions, Android assembly/lint/signing, full TAKP Bookworm and both modern native integrations, then publication. Lint: zero errors/37 warnings. Existing Custom/Traditional qualified native build caches were reused. No competing app build ran.

Published APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 18,866,614 bytes, SHA-256 `df748f8794aae4e33afe73c3c2eef6018ef77b2c3995112962f6304a37874feb`, uploaded 02:08:42 UTC. Independent download verified package/code/version, original signing certificate, all 112 bundled source assets, all 522 archived source files, actual EQW DLL and all 21 native components equal to independently verified 0.6.23. Full public digests/asset IDs/CI/build receipts are in release proof.

Completed: Custom/Traditional 23-action multi-select social/hotbar exports with existing ownership/stale-file/free-slot protections; TAKP retains 39 actions and combined Spawn/Revive. One ZIP64 backup covers all installed profile components and global preferences; destination-first streaming export, bounded metadata/heap/disk checks, staging verification, cancellation before activation, transaction journal/restart rollback, retained previous trees and one-time theme/control restoration. Selected-profile archives remain supported. Final actual >4 GiB, 190,000-file and 58,256,144-byte-index export/import passed under 96 MiB; exact source/log hashes and test-scope notes are in `all-session-qualification-0624.json`. Do not infer physical Android safety from host tests.

TAKP cleric idle-Yaulp policy: source `03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167`; Servertakp PR #2 merged as `b28b529e857784def1671b3d2759d0a7ac6c0084`. Native x86_64/AArch64/MariaDB run 38102400606 and full production Bookworm app integration passed. Six seed ranks become permitted-melee combat buffs after higher-priority support; mana/recast/stacking/native permissions remain. **Device needs explicit source update, build and deployment**, preserving its existing server/database/receipts. APK alone does not change deployed binaries.

**Camera reversal remains unresolved.** Uploaded 0.6.23 logs confirmed V2 loaded but lacked actual game-consumer input telemetry. Keep V2 motion delivery unchanged. Diagnostic helper recipe `f6f354b41d41cf93fc4d2d0672c183771856083f`, run 38102758503, actual DLL SHA-256 `495d6e1711e21f012d1f8c9581af74fdbdccac5f45e2e93508e40b4bd3dbca1d`; qualified exact production transport and consumer fixtures passed. It records bounded actual-contract observations, not an asserted fix. Next: short Thor touch/stick reversal reproduction, then Logs → Export log bundle within the first minute; inspect `eqw-camera-diagnostics.log` before the smallest evidence-supported camera change. Preserve original/V1 helpers and `eqw.0623.dll`.

Remaining device gates: camera axes/touch/controller and gear/Look controls; Yaulp after new deployment; all-world creation/commands/grouping/socials/hotbars and restore guards; real SD/USB large export/import, cancellation, insufficient-space/corrupt refusal, Activity recreation and interrupted activation on a spare test install. TAKP NPC visibility and Traditional StoneUI remain separate. Cosmetic inherited footer still labels 0.6.23; Android package metadata is 0.6.24/code73. Correct the footer on the next necessary code change, without rebuilding this qualified release for its label.

Recovery: initial accessible launcher was clean/no active build, main `a029afaecd6567cfd8309418f0e7c86b7afb9f69`; 0.6.23 source `cf6bec71d6f3171de27851d7df625cf84da096f8`, PR #29 / run 38081870434 and published artifacts were recovered beyond the user's old 0.6.22 checkpoint. Previous native scratch `/workspace/scratch/68f7303215aa` was inaccessible; unpublished work there is unknown and was not assumed. Accessible launch/native changes are committed and recovered. No owned active builds/tests remain. Check current Actions/local worktrees before any future build; do not repeat completed features or recreate databases, imports, prefixes, runtimes or settings.

---

# Released: 0.6.23 camera and combined bot commands (2026-10-10 UTC)

Read [release-status-0623.md](release-status-0623.md),
[takp-camera-0623.md](takp-camera-0623.md),
[bot-commands-0623.md](bot-commands-0623.md) and
[device-acceptance-0623.md](device-acceptance-0623.md) first. These and the
0.6.22 release-specific documents take precedence over the older entries below.

The latest qualified/published source is
`cf6bec71d6f3171de27851d7df625cf84da096f8`, 0.6.23/code72, on both
`codex/takp-world` and `codex/takp-controls-socials-0623`. Preview points to that
source. PR #29 merged at 20:10:19 UTC as
`342efe9d93a577fc91f1a85461a12c3369962ba7`, with its exact tree. Main has a
subsequent documentation checkpoint and restored verifier executable bit;
the qualified APK does not need rebuilding for this checkpoint.

All five jobs in [38081870434](https://github.com/Russianranger/trasc-server-android/actions/runs/38081870434)
passed: APK, TAKP production, Custom native bots, Traditional native bots and
preview publication. CI passed all 495 Python tests with no skips, every browser
suite, native/JVM checks, Android build/lint/signing and integration qualification.
Camera source `202ff0d995b45302d8cfb6a78e47ceea87a5b965` separately passed
Windows build and real Wine10/Xvnc in run 38081609076. No duplicate app build ran.

[Published APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk):
18,833,650 bytes, SHA-256
`0bd0081eefeb44eeb72a2f54491355409d79eb9cbbbd8f8e24a8dd530feefe57`, uploaded
20:08:27 UTC. Independent download verified package/version/code, signature,
unchanged update certificate, exact camera source/proof, all 112 bundled source
assets, all 504 archived files and all 21 native components equal to 0.6.22.
Full public asset/CI/digest metadata is in [release-proof-0623.json](release-proof-0623.json).

The recovery verified complete 0.6.22 and found no unfinished launcher edits,
stash or local build in accessible workspaces. The related native checkout was
clean and preserved. A previous agent's inaccessible private workspace could
not be recovered; no unpublished build was assumed. New physical Thor evidence
of camera veering and the requested command export justified 0.6.23.

Completed changes: Wine-only stable raw mouse look with release/focus/login
restoration; managed helper upgrade backups; 39 selectable TAKP commands;
combined selected-name Spawn party and separate Revive party; explicit five-line
chunking and protected character/social/hotbar export. Revive fallen companions
out of combat after at least 60 seconds, then spawn them. It restores one HP and
zero mana. The working TAKP server needs no rebuild. Custom/Traditional existing
offline-generation utilities and storage/full-backup safeguards remain intact.

**Next: physical AYN Thor acceptance.** Install as an update without uninstalling.
Test both-axis reversals with controller/touch, neutral/focus/menu releases,
gear/Look placement and visibility, selected-party buttons, persistence and
backup/restore refusal after personal edits. Preserve existing bots, databases,
imports, prefixes, compiled servers, runtimes, mappings, renderers, themes and
settings. Use the full device guide; do not repeat completed implementation or
start another build without fresh evidence. TAKP NPC visibility and Traditional
StoneUI remain separate tracked concerns, with no speculative fixes added.

---

# Released: 0.6.10 client UI activation and Return to Launcher (2026-10-07 UTC)

The user confirmed client startup on Thor with 0.6.9. StoneUI fallback remains
unresolved physically: latest `UI_Rusuty_Traditional(1).ini` is 18,544 bytes,
SHA256 `f9094ad8efd7ed7f1ed4d941552aa8e8b5e2d2a3e5e5d4fa5a858ab92de62a38`,
identical to the earlier file and saves `UISkin=Default`. `UIErrors.txt` contains
only its creation timestamp. Neither identifies a native XML rejection.

0.6.10/code59 is now implemented, fully qualified, published and made available
as the signed APK. Both profiles offer installed-skin activation for an existing
character INI, optional matching included window layout, byte-exact backups and
Restore previous UI settings. Surgical edits preserve unrelated colors, fonts,
chat filters and unknown preferences. Native stopped-client/queued-job guards,
profile affinity, revision checks and anchored atomic replacement protect the
operation. Restore remains available after normal game exit rewrites the INI.

Root case-insensitive `UIErrors.txt` now participates in inventory, tail, export,
retention and explicit log cleanup with settings/chat/binary/symlink exclusions.
The shared ClientActivity gear button, startup-failure dialog and disconnect
message all say **Return to Launcher** for Custom and Traditional; their finish
behavior is unchanged. Returning to Launcher alone does not stop the game.

## Release and independent evidence

- PR #21 head `22ed170756eb40e6736f16b859f884ae29c7c4ae` qualified successfully
  on run `37562619222`. Squash source is
  `270b0bbb485e80397148112ebca66a5d98c0f69e`, identical reviewed tree
  `9089bff9967ff4b49162c51850b6c9b5d6016200`.
- Signed main run `37563916833` passed all 11 jobs, including APK
  `112609291732`, client runtime `112609292547`, Traditional runtime
  `112607192913` and preview publication `112618260626`. Separate cleanup run
  `37563916543` also passed. CI ran 341 backend tests, eight Lua/protocol tests,
  all ten browser suites, native management and Android build/lint; signing
  verification passed. The 43 focused UI tests and independent review passed.
- APK-only artifact `11457658097` is 15,108,343 bytes; ZIP SHA256
  `6653593a4f7000515c5aabee88e6c6e188423c48d3eeef5d3c7f3938f03830c4`.
  Independently verified APK is 15,288,293 bytes, SHA256
  `ead3312ec676fd10f0940598a1f14eb8b9835f61e5678d933f5abfd6294f2488`,
  package `io.github.russianranger.trasc.preview`, 0.6.10/code59, certificate
  `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
  ZIP integrity, all six changed bundled assets and all DEX operation/menu/log
  markers passed. Library item `libfile_97c97277b61c819184241df828810224`, version 0,
  retains `TRASC-Android-0.6.10.apk`; local delivery is
  `/workspace/scratch/fdc325fcf8db/deliverables/TRASC-Android-0.6.10.apk`.
- Public preview APK asset `617458219` size/digest match the delivered APK;
  source archive SHA256
  `19171b673d5eb1ba5e5c287ca7bdc254f355b0715e17469ed39337d253e4c65d`.
  Preview, client-runtime-v1 and traditional-runtime-v1 tags all point to the
  release source above. Documentation checkpoint follows only after all
  publishers completed; keep those build tags on the qualified source.
- Independent replay of the exact 22,021,350-byte StoneUI activation ZIP
  (SHA256 `9b0e764b57bf9da37fa4cb7470d4e6f663dbc574d8bab9e434af08e08aeae478`)
  and actual uploaded INI passed both profiles. Selection-only changes only
  Main/UISkin. Optional layout checks verify player/group/target/viewport
  geometry while retaining 531 unrelated original lines and chat preferences.
  Original backups and restores are byte-exact, including restore after a
  simulated normal game rewrite. All other client/default/skin bytes remain
  exact. Evidence is ignored `runtime-work/client-ui-0610/replay.json` and
  `release-proof.json`; do not publish the user's full INI.
- PR Traditional evidence artifact `11457704230` digest was verified. Main
  artifact `11459920751` is 129,016 bytes, SHA256
  `2df9843cd896e3a6ae936541e60d33c83e2a8299469f5182753c51963f5b192d`.
  Native and PRoot each passed 13 checks: PEQ 117,944 items / 40,722 spells /
  schema [9328,0,0], genuine encrypted UDP login accepted/rejected/restored/
  restarted/autocreated, world authentication, PoK on port 7000, dynamic-zone
  sleep, exports, deployment/rollback and complete session round-trip.
  All nine ARM64 reports agree and loader dependencies/providers resolve.
  Published Traditional archive is 252,936,328 bytes, SHA256
  `7d6f7b7b7c4d5920b0e2e5431d97b167e6110d7d3b6cbd0251cd48a5d50632ae`;
  manifest source/tag and release digest were verified.
- Main client evidence covers actual PE32/native DLL/D3D9, direct+PRoot DXVK,
  compact-path SHM/socket/Wine regression, native session hash round-trip,
  GLES lifecycle and animated direct/PRoot VirGL models/input/audio.
  Published Wine 10 WoW64/Box64 0.4.4 archive is 353,710,680 bytes, SHA256
  `2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4`.
  Client tag, public manifest/source and asset size/digest match.

## Next device acceptance

Install in place after stopping both runtimes, then freshly Start runtime in
Traditional. Keep the current runtimes, Wine prefix, imported client, DirectX
helpers and compiled server. `backend/traditional_build.py` and
`backend/traditional_verify.py` remain byte-identical; do not invalidate the
existing device receipt with recipe edits. No renderer/translator/server changes
were made for this UI action.

Follow [the StoneUI test](client-ui-activation-0610.md): select existing
`UI_Rusuty_Traditional.ini` and `stoneui_rof2_720_v011`, optionally apply its
included window layout, launch at 1280x720 with Load Default UI unchecked, camp/exit
normally and check persistence. Reimport current
`StoneUI-RoF2-0.1.1-activation.zip` if its matching layout is missing. Current ZIP
Library item `libfile_99df6acf12208191b77dfefaad5fb092`, version 5, is unchanged.
If fallback persists, immediately export Logs before another reload/restart and
retain the native chat response/screenshot. Root UIErrors is now included.
Restore previous UI settings is available with the client stopped.

Actual native StoneUI loading and appearance on Thor are still pending. Do not
claim an XML/parser fix or physical acceptance from host activation or graphics
probe tests. Startup was already physically accepted on 0.6.9.

# Device follow-up: 0.6.9 startup accepted; StoneUI selection unresolved (2026-10-07 UTC)

User supplied root `UIErrors.txt` after the follow-up: its entire 48 bytes are
`UIErrorLog created at Wed Oct 07 01:55:31 2026` plus CRLF. It contains no
error entries and does not establish the active skin or explain a rejection.
Read-only launch/settings audit confirms no launcher writes to `UISkin` or
force-default flags. Launcher hints use `/loadskin <name> 1` (retain layout),
while StoneUI's package requests `0` for its XML geometry. Needed next evidence:
the in-game chat response immediately after the exact installed-name command,
and `UI_Rusuty_Traditional.ini` exported after normal camp/game exit so its
`[Main] UISkin` reflects the saved attempt. Do not substitute the older supplied
INI or infer a successful load from an empty error file. No speculative skin
or launcher fix has been applied.

User confirms the client launches without issues, but loading StoneUI returns
to default. New supplied scratch bundle: `logs-8906858434605027694(1).zip`.
Status identifies 0.6.9/Traditional and the compact transient paths. The client
log reaches world initialization and has UI reloads at 01:26:10/01:28:27 UTC;
it does not identify the requested skin or the parser rejection. The generic
`Loading default UI resources` line alone does not prove a skin load failure.

Imports completed at 00:42:12, 01:09:59 and 01:24:07 UTC. The current StoneUI
Library item `libfile_99df6acf12208191b77dfefaad5fb092`, version 5,
`StoneUI-RoF2-0.1.1-activation.zip`, contains `stoneui_rof2_720_v011`.
Independent replay against aab4fb6 in both profiles installs 273 files with
every byte/hash matching the archive; all 162 XML includes resolve exactly,
and existing default UI/client-root files remain unchanged. The two supplied
menu/chat XML Library files match this revision. The separately supplied
`UI_Rusuty_Traditional.ini` has `[Main] UISkin=Default`; it is not a saved-INI
snapshot in this new log bundle, so do not infer the current requested skin.

The importer deliberately does not activate a skin or replace character INI
files. Retry the exact 0.1.1 name with `/loadskin stoneui_rof2_720_v011 0`
(or Load UI Skin with Keep Your Layout unchecked). Keep Load Def…80543 tokens truncated…oid build/lint/signing, UI/JVM management checks, full offline database import, complete server/client runtime backup/restore, and native GPU parent/worker cleanup.
- Passed Software and VirGL through both direct ARM64 Wine and real PRoot: native proxy forwarding, held-key release, model libraries/animation, D3D compressed artwork, SM1/2 shader pixels and bounded logging. GLES CI uses host Mesa, not a physical Adreno.
- `graphics_probe.py` now samples all eight S3TC formats, partial updates, 4/2/1-pixel mip levels, sRGB and blended alpha before GPU launch. Local decoder tests also passed address/undefined-behavior sanitizers (leak detection unavailable in this workspace).
- Direct VirGL tests explicitly restrict guest GL to **2.1 / GLSL 120** to exercise the Thor capability path. The original unmodified Wine module reproduces the named undeclared-specular compiler error plus wrong pixels (exit 42); patched Wine renders both shader versions correctly (exit 0). Keep both controls. D3D9 SM1 fixtures need explicit input declarations too, and Mesa may open diagnostic identifiers with a backtick rather than an apostrophe. The test normalizes only that punctuation.
- **Next:** on the Thor, stop both runtimes, update in place, start the server, select **Android GPU / VirGL (experimental), 800×600**, retain native dinput8/model helpers, leave verbose diagnostics off. Check EULA/menu backgrounds, loading artwork, character textures, then enter the same zone and test animation/movement/performance. Export Logs. Confirm `wined3d_patch=legacy-specular-fog-v1` and all texture checks pass. Actual game visuals and playable FPS remain pending this device test; Software stays available for recovery.
- Preserve `eqgame.exe patchme`, `dinput8=n,b`, native D3DX30/35, quiet default Wine logging and all server/client/prefix data. Never ship a higher GL version override as a substitute for actual driver capability. Test-only GL downgrades live in scripts, not Android launch settings.

## Published: 0.3.5 experimental Android GPU path

- Latest device bundle `logs-7569883861190000028.zip` is app 0.3.4. User confirms visible models, animations and movement. Both Microsoft D3DX helpers and native/system DirectInput load; HMD failures are zero. Global asset initialization 20:59:42–21:01:40 UTC (1m58s, previously 9m14s). Greater Faydark main loop ready 21:05:09; normal camp 21:08:37 and quit 21:09:42. Wine log is 31,524 bytes. Actual rendering remains llvmpipe/Accelerated:no; the game's Nvidia adapter label is emulated. A shader-effect failure and a few texture/backbuffer messages remain, without a proven new fatal launch error. VNC updates are not game FPS.
- Published code / both release tags: `c8bf91416a05396ad101a232fede1e85574854f3`. App **0.3.5**, version code **11**. Main release workflow **34902060609** passed database, APK, full client runtime and publication: https://github.com/Russianranger/trasc-server-android/actions/runs/34902060609 . This handoff-only follow-up changes no packaged code.
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — **767,434 bytes**, SHA256 `dc483a95c48ea262e91b9c945895e8c65b6d5f339edbc0d16802af6d4aa1e4a9`. Downloaded APK hash/size match the manifest and GitHub asset digest. Archive includes the ARM64 VirGL/PRoot/cabextract executables and both client_runner.py/graphics_probe.py. Preview manifest confirms commit/version/application identity; preserved-certificate verification passed in CI.
- Application ID stays `io.github.russianranger.trasc.preview`; certificate stays `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`. Never regenerate the signing key if the pinned main cache is unavailable. Server runtime remains 1.1. Client Wine 10 WoW64 / Box64 0.4.4 / Mesa 22.3.6 image is unchanged; the newly repacked client 1.0 archive is 353,710,711 bytes / SHA256 `87981e3ec141716dcb40a96bfa788c0b6454c1f45daf53de12ad0206b88919b6`. Existing installations only need the APK. Do not request a runtime download, helper reinstall, Prepare, prefix repair or client/database reimport for this update.
- **Client → Graphics** offers Software/default and **Android GPU / VirGL (experimental)**. Guest Mesa virpipe forwards WineD3D commands over an app-private Unix socket to native Android EGL/GLES, outside PRoot. The existing embedded TigerVNC display/controller input remains. Native dinput8=n,b, `eqgame.exe patchme`, Microsoft D3DX30/35, quiet logging and conservative Box64 settings are unchanged. Prefix repair explicitly uses Software. No Termux installation, ANGLE, Vulkan driver or external client/display app is needed.
- Native build: pinned VirGL 1.3.0 and static libepoxy 1.5.10, selected Android patches from Termux commit `4f48a30edadeff906a3cad7adfaa17e5f8d10605`, MIT/gl4es notices included. Source SHA256: VirGL `56170f8caa1bb642a2624b649e3bcca095ec2834814e5c308efc8a85a709e4ce`; epoxy `a7ced37f4102b745ac86d6a70a9da399cc139ff168ba6b8002b4d8d43c900c15`. Published launcher-sources includes archives, patches and build/wrapper sources; its SHA256 is `314d9c9f15ee18b4b13f754a8780228cd5c6d7b9b3debfaad0172f383595ae10` (3,095,665 bytes). See THIRD_PARTY_NOTICES.md.
- Lifecycle: `GraphicsBridge` owns startup, bounded logs, private socket and stop/failure cleanup; `ClientRuntime` owns it for the client session and backup checks. A native-driver probe runs in a separate reaped child so the renderer parent never initializes Android graphics threads before forking. The parent has a death signal; patch 0014 gives every vtest worker a race-checked SIGKILL parent-death signal. An open-connection JVM regression verifies parent and workers all terminate on Stop. **Do not switch to --no-fork --multi-clients:** installed Mesa's older protocol rejects that mode. Retain the supported worker model and enforced ownership.
- GPU preflight uses `graphics_probe.py`: map a GLX drawable, query actual driver strings, render/read back a red pixel, swap and clean up. This avoids the reproduced glxinfo X_GetImage BadMatch on an unmapped window. Software retains glxinfo. `client-gpu.log` records actual native vendor/renderer/version; `client-graphics.log` records guest renderer and drawing check. State records graphics_backend, host_gl_renderer and graphics_acceleration. Do not equate a requested GPU mode with actual acceleration. Log exports work through the existing native path, including after a failed launch.
- Verification: 46 Python tests; JVM archive/log/controller/RFB/prefix checks; browser launch/graphics selection and recovery; full ARM64 database seed/rules/backup checks and complete runtime archive roundtrips; Android build/lint and signing. **Both Software and VirGL** pass real PE32 Direct3D9 output, native/system DirectInput, held W and release, quiet/verbose diagnostic comparison, Microsoft model registration/sampling/compression/skinning and visible animated-model pixels, **directly and through pinned PRoot**. Native bridge lifecycle and guest pixel tests also passed in 34901143010. CI uses Linux llvmpipe GLES as the host, validating the graphics/protocol path rather than physical Adreno performance.
- Test infrastructure pitfalls fixed: the PRoot GPU fixture is `runtime-work/gpu-proot`, keeping the translated display socket below 108 bytes (the previous longer name caused bind EINVAL). Windows fixtures publish marker/result files with close+atomic MoveFileEx; existence checks previously raced an empty file and failed JSON parsing. Keep the full pixel/model/input assertions and main publication gate.
- **Next device pass:** stop both runtimes; install 0.3.5 in place; start server; choose **Android GPU / VirGL (experimental)** explicitly at the same **800×600**, native DLL/model helpers enabled, verbose diagnostics off. Check character models, animation and held movement in the same zone; report loading/responsiveness and export Logs. If GPU setup or rendering fails, Stop → Software → Launch for comparison using the same prefix. Physical Adreno 740 / Android 13 compatibility and playable FPS are **not yet confirmed**. Preserve the working server, database, client files and bindings.

## Published: 0.3.4 model helper compatibility fix

- Device bundle `logs-3194322454755682154.zip`: app 0.3.3 on Android 13 / AYN Thor, 800x600, native and system DirectInput loaded, quiet Wine logging. User reached character selection and Greater Faydark with invisible models, limited movement and responsive UI.
- Global asset initialization improved from 53m11s to 9m14s (19:44:48–19:54:02 UTC). Character selection 19:54:07; gfaydark main loop ready 19:58:39; normal camp 20:01:51 and quit 20:02:42. Latest Wine log 31,746 bytes. Server accepted/saved the character and saved 404 zone spawns on shutdown; this alone does not verify later state restoration.
- Game log contains 573 HMD/model initialization failures. Wine loads built-in d3dx9_30/35. Previous verbose bundle includes repeated RegisterAnimationSRTKeys, Compress and ConvertToIndexedBlendedMesh stubs. Wine 10 source returns E_NOTIMPL: https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/d3dx9_36/animation.c and https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/d3dx9_36/skin.c. Native-model tests reproduce this failure with built-ins and pass with Microsoft libraries. Actual ROF2 model rendering remains pending device verification.
- Graphics remains llvmpipe LLVM 15 / Mesa 22.3.6, Accelerated:no. This update provides model compatibility, not hardware acceleration or promised playable FPS. A few texture/framebuffer errors remain in the device log. Movement hold/release passes open-fixture tests; verify the game's own movement bindings and performance on device before diagnosing further.
- APK-only installer: official Microsoft June 2010 DirectX redist 100,275,120 bytes / SHA256 `053f76dcbb28802e23341b6a787e3b0791c0fa5c8d4d011b1044172dbf89c73b`. Client tab supports online installation or picking the matching offline EXE. Original source installer retained; only app cache copy removed. Microsoft DLLs are not included in the APK, Git repository, runtime image or published artifacts.
- Native Android cabextract 1.11 source SHA256 `b5546db1155e4c718ff3d4b278573604f30dd64c3c5bfd4657cd089b823a3ac6`, downloaded from Debian's mirror of the same upstream tarball after the upstream host returned 403 on an x64 CI runner. Source/build recipe accompanies APK in launcher-sources.tar.gz. Built ARM64 PIE with /system/bin/linker64 and 16 KiB alignment. Android SDK setup requests platform-tools explicitly; obsolete SDK tools package caused the initial CI setup failure.
- Portable Java installer verifies the entire redist, extracts only x86 D3DX30/35, verifies PE32 headers, stages both files and a hash manifest, preserves previous install, and recovers interrupted directory swaps. Helper source directory work/client/directx; previous generation work/client/directx-previous. Runner validates both files before replacing only prefix/drive_c/windows/syswow64/D3DX30/35, snapshots originals under prefix/trasc-directx-originals, and rolls back partial-copy failure.
- Verified library hashes: d3dx9_30.dll 2,388,176 bytes `5edeed79f2359527a55b8189cfa8b9b121cd608d44eead905a0f3436938ad532`; d3dx9_35.dll 3,727,720 bytes `2198022938156b790e9cfb0f7997494b66a11a1ad49b395be58251d635b66b26`.
- Native helpers default on for client launch (installation required), off for Wine desktop. Disable model helpers explicitly for built-in comparison. Actual native/builtin model-load evidence is recorded separately from DirectInput and retained across log rotation. Preserve patchme, dinput8=n,b, quiet logs, CPU translation settings, existing client/prefix/server data and both runtime recipes.
- Tested code commit `af45c8af790aa143fa43fcf1cc6202dab7d2b2e3`. Branch Android/UI/database https://github.com/Russianranger/trasc-server-android/actions/runs/34893658488 and ARM64 client https://github.com/Russianranger/trasc-server-android/actions/runs/34893658055 passed. 44 Python tests, native session/controller/RFB tests, browser management flows, full seed/database backup+restore, APK compilation/lint, native Android extractor/source packaging all passed.
- Production Java extraction test downloaded the official package, extracted both correct 32-bit DLLs, rejected a corrupt same-size archive before extraction, retained existing installation, and recovered an interrupted swap. Full client runtime extraction/backup/restore with all hashes passed.
- Direct ARM64 and pinned PRoot both passed: real PE32 launch, native proxy/system DirectInput forwarding and its native-only negative control; W held/release in polled DirectInput state; native D3DX30/35 registration, sampling, compression, indexed skinning and visible animated model pixels over private RFB. Built-in negative control exits 31 on E_NOTIMPL. Test code uses C vtables for MinGW D3DX interfaces and DIDFT_OPTIONAL for standard 256-key format; initial fixture failures were corrected without changing user input settings.
- Local exec workspace disconnected during implementation. Logs were read and upstream downloads verified before disconnect; source changes continued through the GitHub plugin, with CI providing compile/runtime validation. No claim of testing the modified APK directly on Thor.

- Published Preview 0.3.4 / version code 10 from `af45c8af790aa143fa43fcf1cc6202dab7d2b2e3` on main: https://github.com/Russianranger/trasc-server-android/actions/runs/34894293758 passed APK, database, full ARM64/PRoot and publication jobs. Pinned preview signing identity was reused and verified by apksigner; application ID remains `io.github.russianranger.trasc.preview`, certificate SHA256 `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
- Published APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 298,346 bytes, SHA256 `b784e444b23b1fc1e9a0fa555cb4caea497d6a1538d9aa7ec375c51950753d41`. Launcher source archive 1,499,943 bytes, SHA256 `a113082ac8fc944a1470e5567e831cc42e7363ef4c8db89edc3d25d1be0a6328`; includes cabextract source/build recipe.
- Repacked client runtime 1.0: 353,710,669 bytes, SHA256 `5248e5d3720881b8d8c1fbaea10667b944a28f86e2fcd78ca75c349a7a3d736f`. Runtime recipe/image unchanged; existing device installations need only the APK and one-time DirectX helper installation. Both published tags point to tested code `af45c8af790aa143fa43fcf1cc6202dab7d2b2e3`.
- Verification read back release tags, versioned release notes and GitHub asset digests, plus successful CI signing/build gates. Local execution remained unavailable; a local APK download/hash computation was not performed. The connector/browser could not fetch the release JSON asset bodies. Do not describe those as independently downloaded/verified.
- Next user test: stop both runtimes, install APK in place, Client → Install DirectX model helpers (or matching offline Microsoft EXE), keep current runtime/prefix/imported client, start server, launch 800x600 with native dinput8 and model helpers on, verbose off. Verify character models, world rendering and movement, then export Logs. Check `native_d3dx_requested`, both native `model_libraries_loaded` entries and game HMD errors. Preserve user movement bindings; compare with the game's configured movement keys if movement still fails. No Prepare, prefix repair, runtime redownload, server rebuild or client/database import is required.
- After device model validation, major next work is a feasible hardware graphics path for the Thor's Adreno GPU; llvmpipe is still CPU-only. Audio remains later work. This documentation follow-up does not change the published APK.

## Previous release: 0.3.3 client logging performance fix published

- Latest device evidence: `logs-547215203498946041.zip`, Android 13 / AYN Thor, app 0.3.2, native and system dinput8 loaded, 800x600 llvmpipe. User confirms client boots but is abysmally slow. `patchme` is present. No prefix repair needed.
- Full new bundle read from scratch. Wine trace: 1,059,025,481 bytes / 9,258,244 lines. Most output is routine DBG_PRINTEXCEPTION_C / unwind tracing plus 240,177 D3DX RegisterAnimationSRTKeys fixme lines. Do not misdiagnose debug-print exceptions as crashes. Game dbg.txt: initialization starts 17:38:02 UTC, global data 17:42:54–18:36:05 (53m11s), character selection 18:36:11. Session stopped explicitly at 18:51:59.
- Graphics reports llvmpipe LLVM15 / Mesa22.3.6, Accelerated:no. Software GPU emulation is a remaining limit. Xvnc's 3,230 updates across the long session include idle time; not an FPS benchmark. Box64's Cortex-A510 banner does not establish forced CPU affinity. No unsupported CPU/GPU tuning in this pass.
- Implemented normal WINEDEBUG `-all,+timestamp,+pid,err+all,trace+loaddll`; removed always-on module/seh/fixme output. Explicit verbose checkbox defaults off and records mode in state. Kept patchme, dinput8=n,b, conservative dynarec flags and current images. Source reference: Wine 10 dlls/kernelbase/debug.c (OutputDebugString still raises a debug exception even with tracing off).
- Wine output uses a dedicated pipe drain/rotation thread, captures DLL/fatal evidence before rotation, retains two 8MiB segments plus one capped previous session. Old huge logs are shortened to start/final excerpts on next launch, avoiding another gigabyte export. State includes emitted byte/rotation counts, not inferred FPS. Module events cannot evict actual DLL-load proof.
- App version 0.3.3/code9; application ID, pinned certificate, server runtime1.1 and client runtime1.0 unchanged. User only needs APK update; no runtime download, prefix repair, Prepare or data import.
- Local 41 Python tests passed, including rotation, early-load evidence, fragmented fatal messages and oversized previous-log migration. Host JVM/native input/archive checks run. ARM64 CI adds a 512-call OutputDebugString comparison with output-volume assertions and informational timings; DirectInput negative/positive controls, D3D pixels and controller input remain required.
- Tested code commit: `321d42103336b2a5a41d3a1fa47aa31149283634`. Branch APK/UI/database https://github.com/Russianranger/trasc-server-android/actions/runs/34884617744 and ARM64 client https://github.com/Russianranger/trasc-server-android/actions/runs/34884617402 passed all checks. APK compilation/lint, 41 Python tests, native archive/input, browser flows and database seed/cold migration passed. Native/system forwarding, D3D visible pixels and mouse/keyboard passed both directly and through PRoot. Full runtime extraction/backup/hash roundtrip passed.
- 512-call OutputDebugString workload, including process startup: direct ARM64 normal 0.365s / 8,389 bytes; verbose 0.577s / 2,396,722 bytes. PRoot normal 1.573s / 8,471 bytes; verbose 2.638s / 2,396,804 bytes. This confirms suppression and reduced overhead in that fixture; do not extrapolate to ROF2 FPS or the whole 53-minute asset load. Wine still handles debug-string exceptions with tracing off.
- Main release https://github.com/Russianranger/trasc-server-android/actions/runs/34885237951 passed all jobs and published both assets. Main PRoot comparison repeated successfully: normal 1.522s / 8,471 bytes; verbose 2.486s / 2,396,804 bytes. Pinned-certificate verification and Android lint passed. Both release tags point to `321d42103336b2a5a41d3a1fa47aa31149283634`; this follow-up changes only the handoff.
- APK 0.3.3/code9: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 256,626 bytes, SHA-256 `65e8ec0ebfca100999dc61afe973b39ad99652b3d92f01146dc83ab7f2e082e9`. Preview manifest confirms commit, version, application ID and the preserved pinned certificate.
- Repacked client-1.0 archive: 353,710,659 bytes, SHA-256 `b370ec771fb4d6d9b2b6ff6ae6af2efebc1e731007284cb623d462af96078250`. Runtime recipe/image unchanged; existing installations need only the APK.
- Publication verified by reading back both tags/release asset digests, downloading the APK, matching its SHA-256/size, inspecting its packaged supervisor/UI fixes, and checking both release manifests.
- Device retest at same 800x600 with verbose diagnostics off, native DLL on; report time to character select/responsiveness, then attempt world entry if practical and export Logs. No device speedup/playable FPS is claimed before retest.

## Previous release: 0.3.2 system DirectInput fix published

- Workspace access recovered. Full `logs-5544659252330987853.zip`, client-runtime.log, client-state.json and client-wine.log have now been read. Earlier text-only notes below are historical.
- Device is Preview 0.3.1, Android 13 / AYN Thor, 800x600 software graphics. Prefix repair completed at 12:13:54 UTC; subsequent 32-bit preflight passes and native DINPUT8 loads.
- Confirmed configuration defect: during native DLL process attach, `C:\windows\system32\dinput8.dll` resolves to syswow64 and Wine reports environment override `n`, then status c0000135. The add-on's `Release-NMS-Client/eqgame_dll/dllmain.cpp` loads that absolute system path and returns E_FAIL from DirectInput8Create if its function pointer is missing. This is an input initialization blocker, not another missing kernel32 failure.
- The later `wined3d_swapchain_resize_buffers` back-buffer diagnostic occurs before teardown. Wine 10 source logs that error and continues to return WINED3D_OK in that path; it does not alone establish the game's exit cause. No unsupported renderer/DXVK changes in this pass. Original game exit code remains uncaptured: launcher_exit is Explorer's result.
- Fix: `dinput8=n,b`, separate native-imported and built-in-system load evidence, sticky evidence across log tail windows, +seh exception traces, timestamped session boundaries and stop_request/signal reasons. Do not equate two load traces with successful plugin functionality.
- Native log inventory/export now includes selected root client and Logs/logs startup diagnostics, with case-insensitive names and symlink/traversal checks. Settings, game binaries and character chat are excluded. This addresses the missing dbg.txt / dinput8.log evidence in the old bundle.
- Expanded open fixture matches the add-on's GetSystemDirectory + LoadLibrary pattern and creates DirectInput keyboard/mouse devices. ARM64 tests must pass native forwarding plus D3D/display input, with negative control native-only exit 23 and fixed n,b exit 0, directly and through production archive extraction + pinned PRoot. No proprietary client files in CI.
- Verified code commit: `52d3a1b6d0187eb9e47517f180ea79e12c0e44d1`. Branch APK/UI/database checks passed: https://github.com/Russianranger/trasc-server-android/actions/runs/34868688109 . ARM64 runtime/PRoot checks passed: https://github.com/Russianranger/trasc-server-android/actions/runs/34868687404 . Both environments reproduced native-only exit 23 and corrected n,b exit 0; keyboard/mouse device creation, D3D rendering and display input passed. 38 Python tests and JVM archive/log/input/prefix checks passed. APK 0.3.2 / version code 8 keeps the application ID and signing certificate. Runtime images are unchanged; no runtime download or prefix repair required.
- Main release workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34869328238 — all jobs passed, including both DirectInput controls in PRoot, preserved certificate verification, database/session tests, browser flows and APK compilation/lint. Both release tags point to `52d3a1b6d0187eb9e47517f180ea79e12c0e44d1`. This handoff follow-up changes no packaged code.
- Published APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 254,894 bytes, SHA-256 `7ea59d659b483f999772772548db73f9372468b9db3175628801b0e129745d66`.
- Repacked client-1.0 archive: 353,710,716 bytes, SHA-256 `3d9a423f750c00fcdb72545690cb07f6b5850ff6b580b58465ab0924a9f1a2cb`. Both runtime images remain unchanged; existing users only need the APK.
- Publication verified: release tags and asset digests read back; downloaded APK matches the published SHA-256 and size. Preview manifest confirms 0.3.2, the expected commit/application ID and pinned certificate; client manifest matches the same commit and published archive hash.
- Next device pass: stop runtimes, update in place, keep current prefix, start server, launch native ROF2, export logs. Preserve server/client data. No new physical ROF2 acceptance is claimed.
- Primary diagnosis references: https://github.com/Russianranger/Triptych-Triumvirate/blob/main/Release-NMS-Client/eqgame_dll/dllmain.cpp and https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/wined3d/swapchain.c .

## Previous text-only device follow-up: 32-bit Wine and native dinput8 confirmed

- Following the 0.3.1 update, the user reports that the ROF2 window appeared for approximately ten seconds before disappearing. Latest bundle is `logs-5544659252330987853.zip`; individual client-runtime.log, client-state.json and client-wine.log were also attached. The analysis workspace failed to initialize, so these attachments have NOT been read. Evidence below comes only from text pasted by the user.
- Pasted client-state.json reports `prefix_files_ready: true`, `wine32_ready: true`, `native_loaded: true`, mode client, resolution 800x600, launcher_exit 0, final phase stopped, and no error field. Wine's actual native-load trace identifies `D:\\DINPUT8.dll` at 7AE60000 in process 0194. This confirms imported native DLL loading, not successful plugin behavior or game acceptance.
- The pasted Wine tail contains process-detach/shutdown traces at approximately 146758–146759. It does not include the reason for shutdown. Do not diagnose a missing dependency, graphics failure, plugin failure, or clean game exit from this tail alone.
- Code review confirms `launcher_exit` is the return code of Wine Explorer, not a captured eqgame.exe exit code. The final supervisor phase stopped can follow a stop request/signal and cleanup; it does not identify why the earlier game window disappeared.
- Next evidence needed: client-runtime.log and the earlier client-wine.log section immediately preceding the first shutdown/detach sequence, including any errors/exceptions. Clarify whether the user pressed Stop after the window disappeared to distinguish later supervisor cleanup from the original game exit. Preserve the working prefix; no further repair/reimport is indicated by the pasted state.
- No new APK or runtime change has been made for this follow-up. Keep 0.3.1 and the existing published artifact hashes below.

## Previous milestone: ROF2 black-screen recovery, Preview 0.3.1 published

- Published code commit: `01138918df6d9a68a45af8f36a3860be3b4771b5`. Both `preview` and `client-runtime-v1` tags point to this commit. This handoff-only follow-up changes no APK/runtime code.
- Main release workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34800190134 — database, APK, client runtime and publication jobs all passed. Includes 36 Python tests, JVM archive/input/prefix preservation, browser management flows, Android compile/lint, preserved signing certificate, full server database/runtime integration, client archive roundtrip and PE32/DLL/Direct3D/input probes both directly and through pinned PRoot.
- APK 0.3.1 / version code 7: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 253,622 bytes; SHA-256 `f81d0d826ec3883ee904de5b01f3d96ce1647e9ac7f7f2020fda09003548966c`. Application ID and certificate remain the pinned values documented below.
- Repacked client-1.0 archive: 353,710,662 bytes; SHA-256 `e1f37b8b29f47ded4eb859d6b7cd8add86b113843a3aec06933be309fbf3bece`. The Wine/Box64 image and recipe are unchanged; no client runtime redownload is required. Server runtime remains 1.1.
- Publication verification: both tags and release asset digests read back from GitHub; downloaded APK hash/size and preview/client manifests match the code commit, version and preserved application identity.

- Previous 0.3.0 failure bundle: `logs-8799882545351199396.zip`, user confirms right-stick mouse input but black display on ROF2 launch.
- Device evidence: VNC frames/input and llvmpipe OpenGL 4.5 initialize. `eqgame.exe patchme` is correctly passed and the PE32 EXE loads. Wine then reports `could not load kernel32.dll, status c0000135`; native dinput8 is not reached. Explorer returns 0 and the old supervisor continues presenting an empty display. First prefix setup was interrupted by Stop. This suggests a prefix or Android loader problem; do not claim the exact underlying cause is established from these logs alone.
- Existing optional libXcomposite/codec/Bluetooth and CPU-info warnings are separate from the confirmed fatal loader error. No runtime dependency upgrade is required for this APK checkpoint. `/sys` is now bound for CPU discovery.
- Working branch `codex/client-loader-fix`, base main `662b24f8a2fdbcb4fd73828909fa1e284c22af85`. Baseline commit `80663be45652a436b2c9e37e577ec747e19159c6` added real production archive extraction followed by the same pinned PRoot code compiled for Linux ARM64. Baseline PRoot probe passed: https://github.com/Russianranger/trasc-server-android/actions/runs/34799154722 . This narrows the failure but does not reproduce Android SELinux/kernel behavior.
- Shipped changes: 32-bit runtime/prefix core-file inventory (`client-prefix.json`), actual SysWOW64 cmd.exe bootstrap before launching ROF2, separate prefix logs, fatal-loader/dependency detection and visible failure dialog, normal Stop handled without a spurious failure traceback, backed-up Repair Wine prefix action, and launch `patchme` retained.
- Repair moves only `client/prefix` to a unique `client/prefix-backups/` directory and starts a fresh prefix/Wine desktop. Game files, controller profile and server data remain intact. Host JVM regression verifies settings/drive symlinks preserved and game untouched.
- ARM64 tests passed with a non-large-address-aware PE32 fixture with a 20 MiB image and 32-bit preflight enabled, both directly in the runtime and through PRoot: https://github.com/Russianranger/trasc-server-android/actions/runs/34799675371 . This remains an infrastructure test, not actual ROF2 acceptance.
- APK/UI/database gates also passed for `7641d28e6196a77ffad3b4ff28f8465fb76ba59a`: https://github.com/Russianranger/trasc-server-android/actions/runs/34799675523 . Final refinements disable duplicate launch controls and require a terminating loader error before treating optional missing dependencies as fatal; the main release gates passed with these refinements included.
- Next device sequence: update in place, stop the client, Repair Wine prefix, wait for desktop and 32-bit check, stop, start server and Launch ROF2. No reimport/recompile/runtime redownload is needed. Export logs after the attempt, including client-prefix.log/json and client-wine.log.


## Previous milestone: embedded client 0.3.0

The user confirmed: “Session backup and restore worked perfectly. control inputs work, client input works. Lets move to the next step with the client.” Latest bundle `logs-338733800756477711.zip` reports 0.2.1 on Thor Android 13, completed client ZIP import, and no current runtime-start failure. The confirmation concerns the previous input diagnostic; actual ROF2 execution inside this app remains the next physical test. Do not redo server/database installation.

### Code and verification

- Client milestone merged into main: `a472dea0d914f6279a2d4179920d0b050823ec07`, developed on `codex/client-bootstrap`. APK 0.3.0 / version code 6. Server runtime stays 1.1.
- Final branch APK/UI/database workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34788669730 — passed.
- Final branch ARM64 client workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34788669699 — passed.
- Main release workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34788877454 — all jobs passed; signed APK and client runtime published. Both release tags point to the code commit above. This handoff-only follow-up changes no APK/runtime code.
- 34 Python tests passed; host JVM archive/RFB/input tests passed; management browser flows passed; Android compilation/lint passed. Existing full server-runtime archive, offline seed import, SQL/rules and cold database migration checks passed.
- Real ARM64 probe passed: Box64/Wine executes our own PE32 Windows EXE, loads our native test dinput8 DLL, presents Direct3D9 pixels through the private RFB socket, and receives mouse/keyboard events. The probe contains no EverQuest code. This does not establish compatibility with the user's modified ROF2 client.
- The actual client runtime archive passed production TarExtractor/SessionArchive extraction and full roundtrip: executable permissions, multiarch paths, file inventory and all restored hashes verified. Existing full server runtime has its own separate gate.
- Development issues resolved: missing emulated x86 libgcc/libstdc++/libunwind; display test waited too early and assumed a value for RGB888's undefined padding byte; client-only archive fixture needed the required server marker. Do not weaken production archive checks to accommodate test fixtures.

### Published artifacts

- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 250,918 bytes; SHA-256 `e96e53c6347470ea3f19f7be1edb67e64004fec0ed6bc6310eda859e0f9381df`.
- Client runtime: https://github.com/Russianranger/trasc-server-android/releases/download/client-runtime-v1/client-runtime-arm64.tar.gz — 353,710,645 bytes; SHA-256 `31fa8092b9679d861e853542d0ee05a7762c5740398b5efe8271486b64a98e18`.
- `preview-build.json` identifies 0.3.0 / code commit above / the preserved application ID and certificate. `client-runtime-manifest.json` identifies client-1.0 / the same source commit / matching archive hash and bytes. Both tags and asset digests were read back from GitHub; the downloaded APK hash and manifest contents were independently checked.
- Main release gates passed: 34 Python tests, host JVM, browser flows, APK compile/lint/preserved signing certificate, full server database/runtime integration, actual ARM64 Windows/DLL/Direct3D/input probe, actual client-runtime archive roundtrip.
- Reuse the existing server runtime and imported game. Only the separate client runtime is new. Actual Thor Wine/ROF2 acceptance remains pending.

### Implementation

- Separate Debian rootfs in `work/client/runtime`, Wine 10.0 WoW64 + pinned Box64 0.4.4, WineD3D/llvmpipe baseline. Existing server rootfs/database is retained.
- `ClientRuntime` uses the packaged PRoot loader for the second environment; it installs the release runtime online with checksum validation or from an offline archive, and preserves the prefix/game during replacement.
- `backend/client_runner.py` supervises Wine and TigerVNC. RFB listens only on a private Unix socket, mode 0600; no TCP RFB/X11 listeners, random X11 authorization cookie. Prefix initialization is bounded and supports stopping.
- `ClientActivity`, `RfbConnection`, `DisplayInput` implement native display, saved controller mappings, touch, physical keyboard/mouse, text Type/Send + Enter, focus releases and combined input reference counts. Android Back returns to management without stopping the client.
- Client tab offers runtime setup, Wine desktop, resolution, ROF2 launch, return/stop and preparation. Preparation generates the four handshake files into the root/Resources, writes login endpoint and windowed resolution, preserves unrelated INI settings/DLL, and retains originals in `backups/client-setup/` with rollback on errors.
- Native dinput8 is the default request (`dinput8=n`); PE32 executable/DLL architecture must match. Only Wine's actual native loaddll trace marks it confirmed. Built-in mode is an explicit diagnostic comparison. Desktop mode does not claim DLL loading.
- Client start is coordinated with queued/running import/preparation jobs. Rejecting a second launch does not kill the current client. Stopping the server runtime retains the foreground service while the client is active; notification Shut down stops both.
- Client runtime, imported files, controller profile and Wine prefix are part of the complete session client component. Temporary sockets/auth/process state stay under home/tmp outside archives. Complete backup/restore stops the client first. Prefix D: maps to `/client`.
- Logs include client-runtime.log, client-wine.log, client-display.log, client-graphics.log and client-state.json; native log export remains usable with the server closed.
- Build recipes/workflow live in `client-runtime/`, `scripts/build-client-runtime.sh`, `.github/workflows/client-runtime.yml`. Main preview publication is gated on the client workflow as well as APK/database jobs. Sources accompany runtime binaries.

### Next device pass

Follow `docs/client-runtime.md`: update in place, download the separate client runtime, try Wine desktop at 800x600, stop, prepare the already imported client, start the server, then launch ROF2 with native dinput8 enabled. Return and export Logs after the attempt, reporting visible screen/error and native DLL status. No server rebuild, seed import or client ZIP reimport is needed for the update.

Software graphics only. Hardware acceleration, sound, performance tuning and actual ROF2 login/world entry remain unverified/later work. Keep the existing Winlator fallback. Preserve application ID `io.github.russianranger.trasc.preview` and pinned certificate `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; never regenerate a lost preview key.

## Previous request: 0.2.1 export fixes

Latest device report: Preview 0.2.0 session export fails with `Unsafe session path: runtime/var/lib/dpkg/info/binutils-common:arm64.conffiles`. Log export then fails with `Failed to connect to /127.0.0.1:18775`, because backup preparation closed the runtime. Fix both and publish an in-place APK update; preserve the existing world and signing key.

### 0.2.1 fixes published

- Base: `fe84687345bcb4328ec6ab85a71c453829bd2073` (handoff after the published 0.2.0 code).
- `SessionArchive.confined` accepts ordinary Linux colons and still rejects drive prefixes, traversal, absolute paths, backslashes and NULs. Both export and restore share the fix.
- New platform-independent `LocalLogs` reads/lists/zips app and nested server logs without a backend; checks symlink parents/leaves, tails 64 KB for viewing and streams full snapshot lengths into bundles. Native status is included without loading credentials/settings/API tokens.
- MainActivity routes logs/export_logs directly to Android. Both UI log export buttons now consume the direct result instead of polling Python jobs. Backup failure persists to app.log and explicitly reports stopped-runtime recovery. The game server is not automatically restarted.
- Version 0.2.1 / code 5, same application ID and pinned certificate. No new runtime or server rebuild required.
- Local checks: 29 Python tests passed; native host-JVM roundtrip/log regressions passed; JavaScript syntax and whitespace checks passed. CI now also backs up/restores the complete published Debian ARM64 runtime, verifying every file hash; UI regression simulates backup failure with backend unavailable and tests both log buttons and readers.
- Published code commit / preview tag: `e61761bd0ea725061ffcd2305ff82edd158b1cdc`. This handoff-only follow-up changes no APK code.
- Successful workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34780884423 — database, APK and preview jobs all passed.
- Actual runtime roundtrip passed using the production TarExtractor/SessionArchive classes: more than 28,000 regular files restored with SHA-256 verification, plus inventory counts and executable-mode checks. The exact `binutils-common:arm64.conffiles` path roundtripped.
- ARM64 full seed import, rules/SQL checks and cold database migration passed. Browser tests passed both native log export buttons and nested log reading after a simulated session failure with the backend unavailable. APK compilation, Android lint and the pinned-certificate check passed.
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — **225,637 bytes**, SHA-256 `5667d5fc697cc48f347b2952b5065c8405083c3ad0aeae652a7fffa66136a2aa`. Release asset and preview tag were read back from GitHub after publication.
- Runtime 1.1 and the pinned signing certificate remain unchanged. The user subsequently confirmed session backup/restore and input on Thor; preserve those working paths. No reset, recompile or database reimport is required for this APK update.

## Previous feature request (retained context)

Implement in `Russianranger/trasc-server-android`:

1. All database rules in searchable, collapsible categories, with typed controls and field-specific validation for established limits.
2. Setup actions to back up and replace `maps/base/nektulos.map` and `maps/nav/nektulos.nav` from their matching `maps/legacy/` paths, and revert the pair.
3. Complete session ZIP export/import, usable by a fresh app before runtime installation. Include runtime, database, binaries, maps, logs, source, settings and client files. Preserve permissions/symlinks and validate before replacement.
4. Client tab, client ZIP import with removal of only the app's temporary ZIP copy, and configurable gamepad-to-keyboard/mouse input groundwork. Client execution/Wine/dinput8 loading is a later phase, not an acceptance claim for this build.
5. Publish a test APK and keep this handoff current.

The user explicitly declined any faction/deity change. Yukovis was a disposable Iksar beastlord testing login/persistence; Prexus (209) explained Cabilis hostility. Do not change the server fork or seed for that issue.

## Starting state and verified device progress

- Main starts at `f9dfa3ee14c7f0d4655780743a4967e24911c0d2`, app 0.1.2 / runtime 1.1.
- User confirmed on-device compilation, connection and character testing on AYN Thor Max, Android 13 ARM64.
- Runtime 1.1 includes uuid-dev. APK 0.1.2 fixes offline MariaDB initialization and nonzero default ruleset IDs.
- Current server source: `Russianranger/Triptych-Triumvirate` commit `18141ae0c9a11813733f08fa77db986951b853d6`.
- Preview application ID must stay `io.github.russianranger.trasc.preview` for in-place updates.
- Preserve the signing certificate pinned in `docs/preview-signing.sha256`. GitHub Actions cache `trasc-preview-signing-v2` contains `runtime-work/signing/preview.keystore`. Never generate a replacement key if the cache is missing.
- Main's Android workflow tests ARM64 MariaDB, builds/lints APK and publishes the preview release automatically after all gates pass.

## Implementation decisions

- Read every applicable `rule_values` row and source `common/ruletypes.h`; do not infer numeric bounds merely from a name containing Min/Max. Preserve sentinel negatives and very small XP multipliers.
- Nektulos layout comes from the server README: legacy/base → base, legacy/nav → nav. Do not copy files directly into the maps root or change water files.
- Native Android session archive is needed because a new installation has no Python/runtime yet. Stop server/database cleanly; stage and verify all files before swapping app data. No source ZIP deletion outside the app's private staging copy.
- Input mappings belong only to a focused client surface. Release held inputs on focus loss/tab change, disconnection or profile change. The initial surface is an input diagnostic; no game launch is advertised.

## Previous feature implementation: 0.2.0

- Feature implementation is committed and published: `rule_catalog.py`, `managed_content.py`, expanded Engine; native `SessionArchive`, `ControllerInput`, `ControllerManager`; RuntimeManager/MainActivity integration; rules/client UI and docs.
- APK version 0.2.0 / code 4; application ID/signing unchanged. Runtime 1.1 remains compatible.
- Local Python: 29 tests passed (including detection of map edits/imports after Apply). Host JVM archive/input tests passed (the local javac launcher is missing, but `java -m jdk.compiler/com.sun.tools.javac.Main` works; script includes fallback).
- Source parsing found all 1,122 active rules, 47 categories; no definitions missed. Static JS syntax and HTML-ID checks passed.
- Expanded ARM64 integration now checks all-rule visibility, escaped values, invalid-batch atomicity, clean snapshot/shutdown and cold physical database migration. The ARM64 job in workflow 34770980656 passed these checks, including the actual full seed import and cold database restore.
- Final workflow **34771227274** passed all gates and published the APK from **bf9c8d718f177c08af6c0bd1036c9e4d249a85c8**. This includes detection of map edits/imports after Apply: revert first, preserving intervening files. No new device acceptance claimed.
- Browser tests ran successfully in CI with Playwright 1.55.0. They cover 1,105 fixture rules, collapsed/lazy categories, tiny/negative values, bounds errors, changed-only saves, controller binding save and capture release, and mobile horizontal overflow. UI screenshots are in the workflow artifact `management-ui-reports`; downloading its temporary file URL locally returned HTTP 403, so do not claim manual screenshot inspection.
- Session archive excludes incoming/exports/run; includes rootfs, database, binaries, maps, logs, server data, source, builds, backups, configuration and client. Native restore works without Python and stages/validates before swapping. Previous session stays in work-session-previous/rootfs-session-previous.
- Physical Android acceptance still pending: in-place update, rule editing, Nektulos apply/revert and complete session migration. Client execution remains unimplemented by design; controller input is a diagnostic/future injection boundary.

## Previous release: 0.2.0

Published **0.2.0**, version code **4**, on 2026-09-13.

- Code commit / preview tag: `bf9c8d718f177c08af6c0bd1036c9e4d249a85c8`. This handoff-only update follows it; no APK code changes accompany these notes.
- Final successful workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34771227274
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk
- APK size: **221,721 bytes**. GitHub release asset SHA-256: `1627425c11235269cbf629fc1107ddc4d349afe2e2ccb8a1c21480c93d351a98`.
- Pinned certificate: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; APK verification passed in CI before publication.
- `python3 -m unittest discover -s tests -v`: **29 passed**.
- `bash scripts/check-management.sh`: passed JVM archive/input checks.
- `node tests/ui_management.cjs`: passed browser management-flow checks in CI.
- ARM64 database job: reproduced original hostname failure, imported the full pinned seed offline, then passed rule inheritance/editor validation, SQL/backup/restore and cold physical database migration.
- `gradle --no-daemon :app:assembleDebug :app:lintDebug`: passed; stable-signature verification and preview publication passed.
- Preview tag and final APK release asset were read back from GitHub to verify the published commit and checksum.

## Current device follow-up

The 0.2.1 backup/restore and input pass is confirmed by the user. Continue with the 0.3.0 client sequence at the top of this file and in `docs/client-runtime.md`. Retain `docs/device-tests.md` for server regressions if a later support bundle indicates one. Do not claim actual ROF2 device acceptance until the user reports results.
