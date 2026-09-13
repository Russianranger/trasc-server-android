# Third-party components

The app release bundles PRoot and links talloc statically. Source is pinned and the complete build recipe is in `scripts/build-proot.sh`:

- [Termux PRoot](https://github.com/termux/proot/tree/7266fb3e8516535682f5a9c8f3a7e70f6506eddb), commit `7266fb3e8516535682f5a9c8f3a7e70f6506eddb`, GPL-2.0-or-later. The relevant source licenses are in that repository. Its Android modifications are reused without depending on the Termux app.
- [Samba talloc 2.4.3](https://www.samba.org/ftp/talloc/talloc-2.4.3.tar.gz), LGPL-3.0-or-later for the library (see its source `talloc.h` and license files). The source archive is SHA-256 pinned in the build script. The cross-build configuration follows the [Termux package recipe](https://github.com/termux/termux-packages/blob/master/packages/libtalloc/build.sh).
- Debian Bookworm packages: the runtime archive includes `/etc/trasc-packages.txt` with the exact package versions and `/usr/share/doc/<package>/copyright` with license notices. Source packages are available from [Debian](https://www.debian.org/distrib/packages). Runtime includes MariaDB, Python, Git, GCC, CMake, Ninja and dependencies listed in `runtime/Dockerfile`.

The runtime is built separately from imported server source. Server and quest licenses remain those supplied by the selected repository. No proprietary EverQuest client files, maps, Winlator binaries or modified `dinput8.dll` are included.

The APK release includes `launcher-sources.tar.gz` with the pinned PRoot/talloc source archives, build recipe and patches. The recipe recreates the generated loader helper. Retain these notices and corresponding component sources when redistributing binaries. Debian package notices and the exact package list remain inside the runtime archive.
