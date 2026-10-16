# Streaming all-profile backups (0.6.32)

The physical 0.6.31 export stopped at the legacy 200,000-entry inventory cap.
The counter includes files, directories and links across all profiles. That
handled refusal was safe, but prevented the requested complete backup.

The production `SessionArchive.createAll` now writes format
`trasc-all-sessions-3`. A standard ZIP has exactly two members:
`session-stream.bin` and `session.properties`. The payload begins with a
four-byte magic, then bounded binary records. Each regular file streams through
one reusable 1 MiB buffer and has a trailing SHA256. The manifest records whole
payload SHA256, record/byte/metadata totals, profile/component presence, active
profile, architecture and clean database state. There is no per-file ZIP central
directory and no aggregate index map in the Java heap.

Restore checks the small ZIP/manifest first, reserves staging capacity, then
reads the payload sequentially. Each name passes existing component mapping,
namespace/traversal and depth checks. Parent directories must already be real
staged directories. Exclusive creation rejects duplicate files, directories,
links and mapped aliases. Links initially occupy inert regular placeholders,
so they cannot redirect extraction. No live profile is replaced during this
phase. Per-file hashes, whole payload hash, exact counts/sizes and all component
presence flags must agree before a disk journal applies links and directory
modes in reverse order. The existing staged validation, sync, atomic swap and
rollback/recovery transaction then run unchanged.

Bounds: 2,000,000 records; 256 GiB regular file contents; 512 MiB total path,
link, record and digest metadata; 16 KiB per UTF-8 text field; 256 path components.
These bounds refuse malformed/excessive archives safely without making metadata
memory grow with the installation. Disk journal storage is budgeted; no second
private export archive is made. Destination capacity/provider errors still
abort and remove the incomplete SAF document where the provider permits it.
File payloads and record metadata are all retained; source/build trees and old
prefixes are not silently omitted to meet the old cap.

Single-profile/v2 readers and the legacy writer retained for compatibility
fixtures are unchanged. New all-profile backups require 0.6.32 or newer for
restore; that requirement appears beside both export controls. Existing native
payload, signing identity, data, server binaries and accepted camera fixes are
preserved. No server rebuild, client import or prefix reset is needed.

Qualification: production forward/restore path under a 48 MiB heap; a real
600,661-record three-profile fixture with 200,001 client files per world; the
same fixture is rejected by the old 200k writer. Small tests cover every profile,
DB/client/settings values, permissions, guest absolute/broken symlinks, legacy
read compatibility, staged activation, absent-world preservation, malformed and
duplicate paths, link ancestor refusal, corruption, cancellation, provider
failure and journal cleanup. A >4 GiB payload roundtrip compares independent
source/restored SHA256. See release CI receipts for final results.

Device next: install in place, camp/stop the client, Files → Export all profiles,
choose a destination with adequate capacity and >4 GB support, and wait for
success. Open runtime afterward. Retain the completed ZIP and export a fresh
log bundle. Full physical restore/provider/lifecycle qualification is separate;
use a separate test installation/device for a destructive restore test.
