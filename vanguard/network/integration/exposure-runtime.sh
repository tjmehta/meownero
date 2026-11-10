#!/bin/bash
# TJS-4177 exposure container entry (seed or client role, from /out/control/role).
# SIGTERM is forwarded so the driver stops and seals every node it owns.
set -eu
export PYTHONDONTWRITEBYTECODE=1 LC_ALL=C HOME=/out/tmp
counters() {
python3 -B - <<'PY'
import json, time
from pathlib import Path
root = Path("/sys/fs/cgroup")
events = dict(line.split() for line in (root/"memory.events").read_text().splitlines())
cpu = dict(line.split() for line in (root/"cpu.stat").read_text().splitlines())
value = dict(oom=int(events["oom"]), oom_kill=int(events["oom_kill"]),
             memory_peak_bytes=int((root/"memory.peak").read_text()),
             cpu_usage_usec=int(cpu["usage_usec"]))
Path("/out/control/resources-%d.json" % time.time_ns()).write_text(json.dumps(value)+"\n")
PY
}
trap counters EXIT
python3 -B /out/harness/integration/exposure_driver.py &
child=$!
trap 'kill -TERM "$child" 2>/dev/null || true' TERM INT HUP
status=0
wait "$child" || status=$?
# A forwarded signal interrupts the first wait; collect the driver's real exit.
if kill -0 "$child" 2>/dev/null; then wait "$child" || status=$?; fi
exit "$status"
