#!/usr/bin/env bash
# Host regression checks for the TAKP world and existing launcher profiles.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash scripts/check-management.sh
bash scripts/check-directx.sh
for script in tests/ui_*.cjs; do
    timeout 180 node "$script"
done
