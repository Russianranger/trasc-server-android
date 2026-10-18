# 0.6.38 client status and compiler repair

The 0.6.37 device report shows a ready Custom runtime and a stopped, idle client, while the patch controls remain at “Waiting for this world’s client status…”. The exported native client status lacks a top-level `profile`. The client-file UI requires that identity to match the active world before inspecting or changing its files, so the official download was never requested.

`ClientRuntime.state()` now includes the current profile while the bridge holds its existing world request lease. The UI keeps its strict identity check and its running-client, busy-job and session-transfer guards. Client-file status loads through the normal polling hook, enabling the Custom download and per-world host controls when ready.

The prior browser fixture constructed the missing profile itself. The regression now compiles and executes the real native state method with the real `WorldProfiles` lease and feeds its JSON into the shipped browser interface. It covers all three profiles, stopped/running/busy clients, saved launch metadata that is absent, stale or malformed, automatic runtime-open inspection, and an explicit download through the real UI/API/job functions. The old native method fails all 36 profile combinations in the contract probe.

The same report also contains `'Compiler' object has no attribute 'profile'`. The separate Microsoft DLL worker now validates the current `/session/request.json`, written by the native launcher immediately before starting that worker. It accepts only the Custom compiler request, initializes its profile, and reports invalid requests before starting Wine. Saved game launch options are not used as the worker's identity. Tests exercise the real build recipe and staging with mocked compiler processes, preserving the installed DLL and game prefix.

## Update and retry

1. Install 0.6.38 over the existing app. Keep the imported client, database, runtimes and Wine prefix.
2. Select TRASC Custom, open its runtime and leave the client stopped.
3. Open **Client → Custom client · 4 GB patch**. The status should finish loading and enable **Download NTCore 4 GB Patch**.
4. Download the official tool. The saved path should be `client/current/4gb_patch.exe`. The existing **Apply 4 GB patch** action enables the client flag directly and retains its protected Restore.

No server rebuild, client reimport or prefix reset is required for these fixes. Physical AYN Thor download and compiler execution remain device acceptance; automated release evidence is recorded separately after publication.
