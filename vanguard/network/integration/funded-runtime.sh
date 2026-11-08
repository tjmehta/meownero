#!/bin/bash
set -eu
export PYTHONDONTWRITEBYTECODE=1 LC_ALL=C HOME=/out/tmp
trap 'python3 -B - <<'"'"'PY'"'"'
import json
from pathlib import Path
root = Path("/sys/fs/cgroup")
events = dict(line.split() for line in (root/"memory.events").read_text().splitlines())
cpu = dict(line.split() for line in (root/"cpu.stat").read_text().splitlines())
value = dict(oom=int(events["oom"]), oom_kill=int(events["oom_kill"]),
             memory_peak_bytes=int((root/"memory.peak").read_text()),
             cpu_usage_usec=int(cpu["usage_usec"]))
Path("/out/resources-runtime.json").write_text(json.dumps(value)+"\n")
PY' EXIT
timeout --signal=TERM --kill-after=5 14700 python3 -B /out/harness/integration/funded_driver.py
