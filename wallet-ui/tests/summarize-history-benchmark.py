#!/usr/bin/env python3
import json
import pathlib
import statistics
import sys

root = pathlib.Path(sys.argv[1])
summary = {}
metrics = ["sync_ms", "frame_ms", "sync_cpu_ms", "frame_cpu_ms", "peak_rss_kib", "model_resets", "data_changes", "delegate_creates", "delegate_destroys", "find_comparisons", "detail_calls", "sort_calls"]
for build in ["baseline", "optimized"]:
    rows = [json.loads(l) for l in (root / build / "samples.jsonl").read_text().splitlines()]
    assert len(rows) == 90
    summary[build] = {}
    for page in ["overview", "activity"]:
        for n in [4, 100, 1000]:
            for op in ["model", "refresh", "toggle"]:
                samples = [r for r in rows if r["page"] == page and r["n"] == n and r["operation"] == op]
                assert len(samples) == 5
                assert sorted(r["repeat"] for r in samples) == list(range(5))
                summary[build][f"{page}/{n}/{op}"] = {m: {"median": statistics.median(r[m] for r in samples), "min": min(r[m] for r in samples), "max": max(r[m] for r in samples)} for m in metrics}
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
for page in ["overview", "activity"]:
    for n in [4, 100, 1000]:
        key = f"{page}/{n}/toggle"
        a, b = [summary[build][key] for build in ["baseline", "optimized"]]
        print(page, n, f"frame {a['frame_ms']['median']:.3f} -> {b['frame_ms']['median']:.3f} ms, CPU {a['frame_cpu_ms']['median']:.3f} -> {b['frame_cpu_ms']['median']:.3f} ms, RSS {a['peak_rss_kib']['median']/1024:.1f} -> {b['peak_rss_kib']['median']/1024:.1f} MiB")
