# TRASC 0.6.34 — backup file-picker handoff fix

Install over the existing app without uninstalling.

Fixes an all-profile export/restore preparation race that reported "Finish file
transfers and close the file picker" when the launcher was only resuming or
refreshing its status. Preparation now reserves profile admission, drains
already-started requests for up to five seconds, and then starts the transfer.
Timeout or interruption releases the pending reservation so you can retry.
Actual overlapping transfers, pickers and client displays remain protected.

The bounded-memory streaming backup format from 0.6.33 remains unchanged, with
legacy backup readers retained. New all-profile backups require 0.6.32+ to restore.
Camp/stop the client, use Files → Export all profiles, and select storage with
adequate free space and support for files over 4 GB. Reopen the runtime afterward.

Existing worlds, Wine prefixes and accepted native camera helpers are preserved.
No server rebuild, client import or prefix repair is required. Physical Thor
large SAF export/restore acceptance remains pending.
