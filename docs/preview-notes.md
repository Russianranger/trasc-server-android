# TRASC Android 0.6.12 / code 61

Traditional now offers optional camera-only mouse recentering. A bundled,
verified 32-bit proxy forwards system DirectInput; it preserves and restores
any original DLL automatically. Custom loading, particle, boat and gameplay
hooks remain disabled for Traditional. No SDK import or client compilation is
needed. See [camera acceptance and restore](docs/client-camera-0612.md).

The new **Name / sky compatibility (experimental, Turnip)** checkbox changes
only DXVK shader-constant handling. It is a candidate correction for distorted
character-selection labels and a black sky, requiring Thor acceptance. Disabling
it restores the existing rendering configuration. The launcher also records
bounded rendering-setting and asset-hash evidence without changing INIs or
client assets. See [evidence and focused acceptance](docs/traditional-name-sky-0612.md).

Existing viewport gear actions and **Return to Launcher** are retained. Update
the APK in place; keep the compiled servers, imported client, Wine prefix,
runtime, DirectX helpers and character preferences. No server/runtime builds
are part of this scoped release. The 19 existing native payload files and the
signing certificate are checked against the published 0.6.11 baseline.

The separate updated StoneUI skin removes the projecting chat title strip,
uses black Main/Other Chat titles, and replaces oversized decorative hotbar
tiles with continuous stone behind the native button frames. Import the
matching class ZIP with replacements enabled; no included-layout merge is
needed for these cosmetic changes.
