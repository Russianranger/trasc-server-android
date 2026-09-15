#!/usr/bin/env bash
# CI-only kernel observations; never attach ptrace to PRoot's tracees.
set -euo pipefail
cd "$(dirname "$0")/.."
out="$PWD/runtime-work/exit-trace"
instance=/sys/kernel/tracing/instances/trasc-client-exits
mkdir -p "$out"
case "${1:-}" in
  start)
    date -u --iso-8601=seconds > "$out/start.txt"
    cat /proc/uptime >> "$out/start.txt"
    uname -a >> "$out/start.txt"
    if ! sudo test -e /sys/kernel/tracing/events/signal/signal_generate/format; then
      sudo mount -t tracefs tracefs /sys/kernel/tracing || true
    fi
    # If the CI kernel lacks tracefs, retain that fact and keep all real gates.
    if ! sudo test -e /sys/kernel/tracing/events/signal/signal_generate/format; then
      echo 'Kernel signal tracing unavailable on this runner' > "$out/unavailable.txt"
      exit 0
    fi
    sudo mkdir "$instance"
    echo mono | sudo tee "$instance/trace_clock" >/dev/null
    echo 1024 | sudo tee "$instance/buffer_size_kb" >/dev/null
    echo 'sig == 9' | sudo tee "$instance/events/signal/signal_generate/filter" >/dev/null
    sudo cat "$instance/events/signal/signal_generate/format" > "$out/event-format.txt"
    echo 1 | sudo tee "$instance/events/signal/signal_generate/enable" >/dev/null
    echo 1 | sudo tee "$instance/tracing_on" >/dev/null
    ;;
  collect)
    if sudo test -d "$instance"; then
      echo 0 | sudo tee "$instance/tracing_on" >/dev/null
      sudo cat "$instance/trace" > "$out/sigkill.log"
      echo 0 | sudo tee "$instance/events/signal/signal_generate/enable" >/dev/null
      sudo rmdir "$instance"
      cat "$out/sigkill.log"
    fi
    ;;
  *) echo 'Expected start or collect' >&2; exit 2 ;;
esac
