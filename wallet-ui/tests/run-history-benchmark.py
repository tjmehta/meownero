#!/usr/bin/env python3
"""Sequential, fresh-process samples with 60s and 512MiB process safety ceilings."""
import json
import os
import pathlib
import subprocess
import sys
import time

binary, out = sys.argv[1:]
out = pathlib.Path(out)
out.mkdir(parents=True, exist_ok=True)
cpu = min(os.sched_getaffinity(0))
env = dict(os.environ, QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic")
(out / "conditions.json").write_text(json.dumps({"cpu": cpu, "affinity": sorted(os.sched_getaffinity(0)), "backend": "software", "render_loop": "basic", "display": env.get("DISPLAY"), "ceiling_kib": 524288, "timeout_seconds": 60, "repeats": 5, "binary": str(pathlib.Path(binary).resolve())}, indent=2))
with (out / "samples.jsonl").open("w") as samples:
    for page in ("overview", "activity"):
        for n in (4, 100, 1000):
            for repeat in range(5):
                name = f"{page}-{n}-{repeat}"
                with (out / f"{name}.stdout").open("w") as stdout, (out / f"{name}.stderr").open("w") as stderr:
                    p = subprocess.Popen(["taskset", "-c", str(cpu), binary, "--benchmark", str(n), "--benchmark-page", page], env=env, stdout=stdout, stderr=stderr)
                    begin = time.monotonic()
                    while p.poll() is None:
                        status = pathlib.Path(f"/proc/{p.pid}/status")
                        if status.exists():
                            rss = next((int(l.split()[1]) for l in status.read_text().splitlines() if l.startswith("VmRSS:")), 0)
                            if rss > 524288:
                                p.kill(); p.wait(); raise RuntimeError(f"{name} exceeded 512MiB")
                        if time.monotonic() - begin > 60:
                            p.kill(); p.wait(); raise RuntimeError(f"{name} exceeded 60s")
                        time.sleep(0.02)
                if p.returncode:
                    raise RuntimeError(f"{name} exit {p.returncode}; inspect raw stderr")
                rows = [json.loads(l) for l in (out / f"{name}.stdout").read_text().splitlines()]
                assert [r["operation"] for r in rows] == ["model", "refresh", "toggle"], rows
                for r in rows:
                    r["repeat"] = repeat
                    samples.write(json.dumps(r) + "\n")
                samples.flush()
                print(name, "complete", flush=True)
