# Client startup retry for 0.6.9

The Thor 0.6.8 bundle `logs-6853557731548116328.zip` fails during Wine prefix
setup, before `eqgame.exe` starts. PRoot reports `Temporary path too long`,
and Wine's server reports `bind: Invalid argument`. The Traditional profile's
long host temporary directory exceeds Unix socket pathname limits after Wine
and PRoot append their socket names. The later display connection failure is
consistent with that failed startup; it does not establish a renderer failure.

0.6.9/code58 uses short, separate Custom and Traditional transient directories
under app-private data. Wine still sees `/tmp` and the existing `/prefix`.
Client/runtime imports, Wine prefix, DirectX helpers, controller settings,
renderer selection, prepared data and the compiled Traditional server stay in
their existing locations. The server build receipt/recipe is unchanged.

The same bundle shows a rejected StoneUI ZIP because it contains
`STONE_THEME_MANIFEST.json`. The importer now validates and ignores that bounded
JSON metadata file at the skin root. XML and texture bytes are installed as
supplied; unsupported files and unsafe archive paths remain rejected.

1. Stop the client and server runtime, then install 0.6.9 in place.
2. Freshly **Start runtime** so the updated backend is copied, then start the
   Traditional server if it is stopped.
3. Keep the existing client runtime, imported client, Wine prefix and DirectX
   model helpers. Their installation/data sync succeeded in this log bundle;
   no repair, reimport, server rebuild or runtime download is required.
4. In the Traditional profile, retry **Launch ROF2** with the same graphics and
   800×600 settings. Traditional continues to use built-in DirectInput without
   Custom hooks. First prefix setup may take a minute.
5. Retry the StoneUI ZIP import if desired while the client is stopped, then
   select its skin in the game's existing UI controls.
6. Export fresh Logs after the launch attempt and report the visible result.

CI checks the short-path budget and profile separation on the host JVM, UI ZIP
compatibility/rejection cases, and actual Wine/PRoot startup with Android-length
temporary paths. Passing these infrastructure checks is not physical Thor
gameplay acceptance.
