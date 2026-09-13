# Third-party components

The app release bundles PRoot and links talloc statically. Source is pinned and the complete build recipe is in `scripts/build-proot.sh`:

- [Termux PRoot](https://github.com/termux/proot/tree/7266fb3e8516535682f5a9c8f3a7e70f6506eddb), commit `7266fb3e8516535682f5a9c8f3a7e70f6506eddb`, GPL-2.0-or-later. The relevant source licenses are in that repository. Its Android modifications are reused without depending on the Termux app.
- [Samba talloc 2.4.3](https://www.samba.org/ftp/talloc/talloc-2.4.3.tar.gz), LGPL-3.0-or-later for the library (see its source `talloc.h` and license files). The source archive is SHA-256 pinned in the build script. The cross-build configuration follows the [Termux package recipe](https://github.com/termux/termux-packages/blob/master/packages/libtalloc/build.sh).
- Debian Bookworm packages: the runtime archive includes `/etc/trasc-packages.txt` with the exact package versions and `/usr/share/doc/<package>/copyright` with license notices. Source packages are available from [Debian](https://www.debian.org/distrib/packages). Runtime includes MariaDB, Python, Git, GCC, CMake, Ninja and dependencies listed in `runtime/Dockerfile`.

The runtime is built separately from imported server source. Server and quest licenses remain those supplied by the selected repository. No proprietary EverQuest client files, maps, Winlator binaries or modified `dinput8.dll` are included.

The APK release includes `launcher-sources.tar.gz` with the pinned PRoot/talloc source archives, build recipe and patches. The recipe recreates the generated loader helper. Retain these notices and corresponding component sources when redistributing binaries. Debian package notices and the exact package list remain inside the runtime archive.

## Optional embedded client runtime

`client-runtime/Dockerfile` builds a separate Debian ARM64 environment:

- [Box64 0.4.4](https://github.com/ptitSeb/box64/tree/2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a), commit `2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a`, MIT; its license is installed under `/usr/share/doc/box64/`.
- [Wine 10.0](https://dl.winehq.org/wine/source/10.0/), LGPL-2.1-or-later, vanilla WoW64 binary from [Kron4ek's 10.0 release](https://github.com/Kron4ek/Wine-Builds/releases/tag/10.0). The exact binary archive SHA-256 is pinned in the Dockerfile. Upstream Wine source and the Box64 source accompany the release as `client-runtime-sources.tar.gz`; Kron4ek's repository documents the compiler flags and Ubuntu build environment used for its binaries.
- Debian's TigerVNC/X server, Mesa llvmpipe, fonts and support libraries. `/etc/trasc-client-packages.txt` records exact package versions and `/usr/share/doc/*/copyright` retains the package license notices. Corresponding versioned source packages are available from Debian. TigerVNC is GPL-2.0-or-later; Mesa and X components retain their respective upstream licenses.

The Android RFB client is implemented in this repository from the public protocol specification. The Windows integration-test EXE/DLL are built from `tests/client_probe*.c`; they contain no proprietary client code. No EverQuest executables, modified client DLLs, copyrighted game assets or Winlator binaries are redistributed.
