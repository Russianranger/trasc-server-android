# TRASC 0.6.31 — profile backups and prefix browsing

Update in place; keep the existing installation and its data.

- Files → **Export all profiles** backs up Custom, Traditional and TAKP in one
  ZIP. The same button remains in Server → Session backups.
- Stop the client first, choose a destination with sufficient space, and watch
  progress in the activity panel. Cancel stops the transfer. Runtime shutdown
  and SQL snapshots precede export; reopen the runtime afterward.
- Large ZIPs stream directly to the destination with fixed buffers and ZIP64.
  Use exFAT or a provider supporting files over 4 GB. Keep backups private.
- Files → Old Wine prefixes displays an empty-state explanation if no old
  prefix has been saved in that profile. Existing backups remain listed.

Test Traditional and TAKP separately. Export all profiles to external storage,
wait for success, and retain the archive. For restore testing, use Setup →
Restore all profiles on a separate test installation/device; restoring replaces
included profile data. Full physical export/restore acceptance is pending.

Accepted 0.6.30 mouse-look helpers and native components are preserved. No
server rebuild or Wine prefix reset is required for this update.
