# TRASC 0.6.32 — large all-profile backup fix

Install over the existing app without uninstalling.

Files → Export all profiles now uses a streaming format that supports more than
the previous 200,000 total entries without building a per-file heap inventory.
Clients, prefixes, databases, runtimes, sources, builds and settings are retained.
New backups require TRASC 0.6.32 or newer to restore. Older backups remain readable.

Camp/stop the client before export. Choose a destination with sufficient free
space and support for files over 4 GB, such as exFAT. Progress and cancellation
remain in the activity panel. Reopen the runtime afterward. Retain the completed
ZIP and export fresh logs. Physical large SAF export/restore remains pending.

Traditional/TAKP prefix browsing and accepted native camera helpers are preserved.
No server rebuild, client import or prefix repair is required.
