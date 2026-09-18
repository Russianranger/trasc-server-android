# Installed add-on identified: reconnect overflow (2026-09-18)

This continues [the 0.4.15 device investigation](reconnect-0415-device.md). The user exported the actual installed `client/current/dinput8.dll` and `client/toolchain/sdk.json` using 0.4.16's file search. Both were inspected read-only. No app, runtime, client file, source add-on or database change is made by this investigation, and no new APK is needed.

## Confirmed identity mismatch

| Item | Installed DLL supplied by user | Successful device compiler output in earlier logs |
| --- | --- | --- |
| Bytes | 3,445,760 | 1,695,232 |
| SHA256 | `0a59be5dbd0c746ecd4168d3628b056dc490e0eabbaa6050c3d533802b13465b` | `556ead4699b1af797eb2c676ef40dacc92ade932526ebe551f36382de7424c28` |
| PE | x86 PE32 DLL, seven sections, preferred base `0x10000000` | x86 PE32 DLL, production recipe |
| Linker / toolchain | PE linker version 14.40 | Microsoft v142 14.29 |

The uploaded SDK manifest says `trasc-msvc-sdk-1`, target `x86`, MSVC `14.29.30133`, Windows SDK `10.0.19041.0`. These are the intended imported toolchain versions. It does not prove the installed add-on was built with that toolchain; the binary and recorded output are demonstrably different.

The supplied DLL's PE timestamp is August 11, 2026, 21:54:30 UTC. Treat this as a header value, not authoritative build provenance. Its CodeView record points to a different build workspace, not the on-device compiler. Do not copy the private absolute PDB path into public documentation or logs.

The current binary contains Dear ImGui 1.92.9 WIP, NMS loot/pop-out/browser UI strings, and `nms_imgui.ini`. This ImGui integration is absent from the imported client source at `Russianranger/Triptych-Triumvirate` commit `4c653ca2d16aaede33b7011d07254c520ac5f5df`. It is also absent from the checked upstream client source trees (`saltamontes5k/Triptych-Triumvirate` at `a6a11bb725f56820bb0e28b373bfcfd02c2d2e3d`, `tunaria/NMS-Release` at `4d9f2224938fe4784b8ff3a923954f9e37ffd80c`). Public code search for `NMSImGui` and `nms_crash.txt` returned no matches. This establishes that the examined source does not contain this integration, not that matching source cannot exist elsewhere.

The earlier Windows symbol build is still not a match. Do not apply its function names to this binary or infer that rebuilding the imported project preserves all features in the installed add-on.

## Exact first-fault mapping

The diagnostic device log records native `DINPUT8.dll` at `0x7AE60000`. The first overflow is at `0x7AE69EE4`, therefore RVA `0x9EE4`. Disassembling that RVA in the supplied binary gives:

```asm
; Preferred base shown here; runtime base is different.
10009ED0  push  ebp
10009ED1  mov   ebp,esp
10009ED3  sub   esp,140h
10009ED9  movzx eax,byte ptr [10333B2Fh]
10009EE0  test  eax,eax
10009EE2  je    10009EF7h
10009EE4  call  dword ptr [1023A284h] ; KERNEL32!GetTickCount
```

This is an exact instruction/stack-state match, unlike the earlier unrelated map:

- Device EAX is 1, matching the initialized flag and taken call path.
- Device EBP minus ESP is `0x140`, matching this local stack allocation.
- Device ESP is `0x7F011F0C`; the fault is a write to `0x7F011F08`, exactly ESP minus four, where `call` attempts to save its return address.
- The stack is already exhausted before `GetTickCount` executes. This is not evidence that `GetTickCount` itself is defective.

The containing function (`RVA 0x9ED0`) is a four-argument Windows window procedure, identified from its actual code, imports and registration:

- It handles keyboard/mouse Windows message constants and calls an ImGui input handler.
- At `RVA 0xA297`, an initializer passes this function to `SetWindowLongA(hwnd, GWL_WNDPROC, handler)`.
- At `RVA 0xA2AB`, it stores the returned prior procedure at data RVA `0x333B64`.
- The faulting procedure forwards messages through `CallWindowProcA` using that saved pointer, at RVAs `0x9F0E` and `0xA1E9`.
- The initializer checks a global initialized flag and sets it at the end. There is also a teardown routine at RVA `0xBAB0` that attempts to restore the saved procedure before clearing state. Its existence alone does not establish that reconnect invokes it correctly.

These API semantics are documented by Microsoft: [SetWindowLongA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowlonga) returns the previous window procedure, and [CallWindowProcA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-callwindowproca) forwards to it. A cycle in that chain can repeatedly re-enter the handler and exhaust the stack.

**Leading hypothesis:** an ImGui/add-on window-procedure chain or lifecycle problem during the character-select → server-select → Play transition. This is a materially narrower finding than “somewhere in dinput8.” It remains a hypothesis: the exported Wine log does not contain a caller backtrace, the saved procedure pointer's runtime value, or the handler installation sequence. An already-deep call stack could fail in this function without this function having created that depth. Do not claim double installation or a particular cycle as proven, and do not blindly add a guard, patch binary bytes, or replace the handler with `DefWindowProc`.

## Add-on crash report discovered

The vectored exception handler recorded in Wine at `0x7AF4FD90` maps exactly to RVA `0xEFD90` in this binary. Its code includes `EXCEPTION_STACK_OVERFLOW` and constructs **`nms_crash.txt` beside the game executable**. Its embedded format strings show exception/time/registers, a module list, and a scan labelled "code addresses on the stack (probable call path)". This is a candidate-address scan, not a fully unwound backtrace. Wine's secondary stack overflow can interrupt it. The file may be missing, incomplete or from an older crash.

The 0.4.15 exported bundle contains `client/current/Logs/dbg.txt`, but not this root-level report. If available, the user can use Files → folder `client/current` → search `nms_crash.txt` → Select → Export file. Correlate any contents with the latest reconnect timestamp/address before relying on them. No repeat crash or extra Mac software is required just to check for this file.

## Safe next action and limits

Ask where the installed add-on came from (download link, client pack name, or matching source repository), and obtain `nms_crash.txt` if it exists. Matching source/symbols and a caller chain are the most useful next evidence for a targeted fix preserving the installed add-on's features. No matching-source fix has been established yet.

A comparison with the successfully compiled project DLL is possible through Client → Build dinput8.dll on this device → Deploy staged DLL after stopping the client. The production deploy path resolves the existing filename case-insensitively, verifies the staged hash, and backs up the previous DLL under `backups/client-setup/<timestamp>-<suffix>/`. The uploaded original is also available. However, this is a **different-feature add-on comparison**, not a confirmed repaired build; it can remove the ImGui loot/browser features. Do not silently recommend it as an equivalent upgrade or infer deployment history merely from absent retained logs. A current staged build could also differ from the old log record.

Keep the experimental force-recenter option off; its separate graphics-startup failure is not resolved here. Preserve the user-confirmed working `#tim` sequence and shared-memory capture. Restarting the game client before re-entering the server remains the temporary reconnect workaround. Leave the camp/database issue parked.

Local scratch analysis (not committed): `runtime-work/installed-dinput8-headers.txt`, `installed-dinput8-disassembly.txt`, `installed-dinput8-imports.json`. Original uploads are unchanged and neither proprietary/client binary nor SDK payload is added to git. Main remains the tested 0.4.16 implementation plus documentation; all existing release gates and signing identity remain intact.
