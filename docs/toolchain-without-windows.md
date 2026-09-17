# Prepare the Microsoft toolchain entirely on Thor

No work-computer downloads or installations are needed. This one-time route uses
the existing Ubuntu environment in Termux on the Thor to download and package the
toolchain. Import the resulting ZIP into TRASC 0.4.10, then compile in the app.
Termux is only used to prepare the ZIP; subsequent app compilation does not use it.
An automatic download button inside TRASC is not implemented yet.

The portable helper uses a pinned, checksum-verified
[msvc-wine downloader](https://github.com/mstorsjo/msvc-wine/tree/514f8ea34842cd6d831804d0e9658d3a32870ae1)
to fetch original Microsoft packages. It selects the Visual Studio 2019 channel,
MSVC v142/14.29, Windows SDK 10.0.19041, x64-host compiler and x86 target libraries.
The x64 host is intentional even on ARM64: TRASC runs these tools through Box64.
No Windows installation, Windows VM, or Wine on the preparation host is needed.
The downloader asks you to review and accept Microsoft's license before downloading
the packages. Keep the generated toolchain for your own use; it is not published
with the repository or APK.

## One-time commands on the Thor

1. Open Termux on the Thor and enable shared-storage access if needed:

   ```sh
   termux-setup-storage
   ```

2. Enter your existing Ubuntu environment. For a standard proot-distro Ubuntu:

   ```sh
   proot-distro login ubuntu --bind /sdcard:/sdcard
   ```

3. Run these commands **inside Ubuntu**, not the ordinary Termux shell. They install
   the extraction tools only on the Thor:

   ```sh
   apt update
   apt install -y python3 msitools ca-certificates curl
   curl -fL https://raw.githubusercontent.com/Russianranger/trasc-server-android/main/tools/pack-client-sdk.py -o pack-client-sdk.py
   python3 pack-client-sdk.py --download --output /sdcard/Download/trasc-msvc-sdk-x86.zip
   ```

   Review the license URL printed by the downloader and answer its prompt.
   The September 17 catalog selects about 974 MB of downloads; allow approximately
   8 GB of free device storage for downloads, extraction, staging and the final ZIP.
   Keep Termux active until it prints `Created ...trasc-msvc-sdk-x86.zip`.
   Downloaded packages are cached in `~/trasc-toolchain-work` inside Ubuntu;
   rerunning the same command reuses checksum-verified cached packages. A completed
   output ZIP is never overwritten; use another `--output` filename for a new copy.

4. Open TRASC, start its server runtime, and keep the game/server stopped. In
   **Client → Build dinput8.dll on this device**, choose **Import Microsoft SDK ZIP**
   and select the ZIP from Android's Downloads folder. Then use **Compile dinput8.dll**.
   Compilation stages the DLL; **Deploy built DLL** is a separate, backed-up action.

If your Ubuntu environment uses a custom launch script, enter it using your usual
method and make sure `/sdcard/Download` is writable. Do not install a second Ubuntu
environment solely because its existing name differs.

## Validation and remaining device check

The live Microsoft VS2019 16.11.60 catalog was read and the exact downloader
arguments resolved successfully to v142/14.29, HostX64/TargetX86 and SDK19041 packages.
Fixture ZIPs produced by the helper passed the app's actual import implementation,
including differently capitalized Windows headers and empty required directories.
Wrong host architecture, missing runtime DLLs, symlinks and unsupported toolset
versions are rejected before an output ZIP is created.

The full download/extraction on Android and the real Microsoft compiler running
through Android Wine/Box64 remain device checks. The earlier Windows CI result
only proves the original source compiles with MSVC. Export Logs from TRASC if
compilation fails; if package preparation fails, capture the terminal error.

The same helper can also run on another personal Linux/macOS machine where tools
can be installed, or pack an existing unmodified `vsdownload.py` extraction:

```sh
python3 pack-client-sdk.py --vs-root /path/to/extraction --output trasc-msvc-sdk-x86.zip
```
