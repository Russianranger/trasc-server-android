# TRASC Android 0.6.36 — database sorting

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.36/trasc-server-android-0.6.36.apk)

Install over your existing TRASC app. This release is marked Latest on GitHub.

In **Setup → Select database / Database files**, use **Sort database files**:

- **Size — largest first** sorts database files by descending size.
- **Modified — newest first** sorts by descending modification date and time.
- **Recommended** retains the existing complete-seed-first ordering.

The dropdown is available in Custom, Traditional and TAKP. Changing sort preserves your selected database, and works with search, individual SQL files and refreshed scans. Selected file details show the size and modification date; unavailable dates appear last when sorting by date. ZIP entries use their recorded member dates, and complete PEQ bundles use the newest component date.

TAKP's sortable file catalog is available for review. New TAKP database deployment continues through its matching Initialize fresh TAKP database action.

Includes the 0.6.35 per-profile eqhost.txt IP controls with protected originals, Custom's reversible 4 GB client patch, and default controller menu navigation. Existing application identity and signing certificate support an in-place update.

Automated regression and APK verification evidence is recorded in the release workflow. Physical Thor acceptance of the new sorting control remains pending.
