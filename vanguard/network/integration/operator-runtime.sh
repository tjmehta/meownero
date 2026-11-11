#!/bin/bash
# TJS-4238 operator-package container entry (seed, client or monitor role, from /out/control/role).
# SIGTERM is forwarded: in the serving step it is the planned rollback (stop, seal, last rows, exit 0).
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
python3 -B /out/harness/integration/operator_driver.py &
child=$!
trap 'kill -TERM "$child" 2>/dev/null || true' TERM INT HUP
status=0
wait "$child" || status=$?
# A trapped signal makes the first wait return 128+signal while the driver is still sealing.
# Wait again for the driver's own exit; bash keeps an exited child's status until it is waited for.
# (Rehearsal 2: the old re-wait kept 143 when the driver then exited 0, so a sealed rollback read as failed.)
if [ "$status" -gt 128 ]; then status=0; wait "$child" || status=$?; fi
exit "$status"
