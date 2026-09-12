#!/usr/bin/env python3
"""Deterministic primitive differential corpus; no chain-validity claim."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

MAX = (1 << 128) - 1
SEED = 20260912


def oracle(ts, work):
    ts = sorted(ts[:720])
    if len(ts) <= 1:
        return 1, 0
    start = max(0, (len(ts) - 600 + 1) // 2)
    end = min(len(ts), start + 600)
    span = max(1, ts[end - 1] - ts[start])
    product = (work[end - 1] - work[start]) * 120
    value = (product + span - 1) // span
    return (0 if value > MAX else max(1, value)), product


def row(ts, work):
    assert len(ts) == len(work) <= 735
    assert all(0 <= t < 1 << 64 for t in ts)
    assert all(0 < w <= MAX for w in work)
    assert all(a < b for a, b in zip(work, work[1:]))
    return " ".join([str(len(ts))] + [str(v) for pair in zip(ts, work) for v in pair]) + "\n"


def invoke(binary, data):
    return subprocess.run([str(binary)], input=data, text=True, capture_output=True, timeout=60)


def main():
    out = Path(sys.argv[1])
    rng = random.Random(SEED)
    cases = []
    lengths = [0, 1, 2, 3, 59, 60, 599, 600, 601, 602, 719, 720, 721, 734, 735]
    for n in lengths:
        for pattern in ("constant", "ascending", "descending", "duplicates", "outliers", "lag-poison"):
            ts = [1700000000 + i * 120 for i in range(n)]
            if pattern == "constant":
                ts = [1700000000] * n
            elif pattern == "descending":
                ts.reverse()
            elif pattern == "duplicates":
                ts = [1700000000 + (i // 7) * 120 for i in range(n)]
            elif pattern == "outliers":
                ts = [0 if i % 3 == 0 else (1 << 64) - 1 if i % 3 == 1 else ts[i] for i in range(n)]
            elif pattern == "lag-poison":
                ts[720:] = [(1 << 64) - 1] * max(0, n - 720)
            # Large cumulative offset ensures the adapter does not truncate u128.
            work, cumulative = [], 1 << 100
            for i in range(n):
                cumulative += (1 + (i * 7919) % 100000) if i < 720 else 1 << 64
                work.append(cumulative)
            cases.append((f"{pattern}-{n}", ts, work))
    for i in range(512):
        n = rng.choice(lengths) if i % 2 else rng.randrange(736)
        ts = [rng.randrange(1700000000, 1700200000) for _ in range(n)]
        work, cumulative = [], rng.choice([1, 1 << 64, 1 << 100, 1 << 127])
        for _ in range(n):
            cumulative += rng.randrange(1, 1 << 70)
            work.append(cumulative)
        cases.append((f"random-{i}", ts, work))
    # The exact multiplication threshold, rounding with a u64-max span,
    # and a full-width cumulative value are still in the non-overflow domain.
    for name, ts, work in [
        ("mul-threshold", [0, 120], [1, 1 + MAX // 120]),
        ("wide-rounding", [0, (1 << 64) - 1], [1, 1 + MAX // 120]),
        ("max-cumulative", [0, 120], [MAX - 100, MAX]),
    ]:
        cases.append((name, ts, work))

    synthetic_count = len(cases)
    fixture_path = Path(__file__).resolve().parent / "upstream/consensus/src/tests/context/data/dif_3000000_3002000"
    fixture = ast.literal_eval(fixture_path.read_text())
    assert len(fixture) == 2000
    # Match upstream calculate_diff_3000000_3002000: 735 cached pairs,
    # predict work[i] - work[i-1], append pair i, evict the oldest pair.
    # Do not reinterpret the fixture's filename as independently verified heights.
    for i in range(735, len(fixture)):
        work, ts = map(list, zip(*fixture[i - 735:i]))
        expected = fixture[i][0] - fixture[i - 1][0]
        assert oracle(ts, work)[0] == expected, f"fixture alignment {i}"
        cases.append((f"upstream-fixture-index-{i}", ts, work))

    corpus = "".join(row(ts, work) for _, ts, work in cases)
    (out / "corpus.tsv.gz").write_bytes(gzip.compress(corpus.encode(), mtime=0))
    values = {}
    for name in ("cpp", "rust-release", "rust-checked"):
        result = invoke(out / name, corpus)
        if result.returncode:
            raise RuntimeError(f"{name}: {result.returncode}: {result.stderr}")
        values[name] = [int(v) for v in result.stdout.splitlines()]
        assert len(values[name]) == len(cases)

    records = []
    for i, (name, ts, work) in enumerate(cases):
        expected, product = oracle(ts, work)
        assert product <= MAX, name
        record = {"name": name, "samples": len(ts), "input_sha256": hashlib.sha256(row(ts, work).encode()).hexdigest(),
                  "oracle": str(expected), **{k: str(v[i]) for k, v in values.items()}}
        assert all(v[i] == expected for v in values.values()), record
        records.append(record)
    (out / "parity.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))

    # Separate expected incompatibilities: valid primitive types/invariants,
    # but no evidence that these extreme windows are reachable on a real chain.
    probes = [
        ("intermediate-overflow-quotient-fits", [0, 120], [1, 2 + MAX // 120]),
        ("result-overflow-sentinel", [0, 1], [1, 2 + MAX // 120]),
        ("large-intermediate", [0, (1 << 64) - 1], [1, 1 << 127]),
    ]
    boundaries = []
    for name, ts, work in probes:
        data = row(ts, work)
        expected, product = oracle(ts, work)
        assert product > MAX
        results = {k: invoke(out / k, data) for k in values}
        cpp, release, checked = (results[k] for k in values)
        assert cpp.returncode == release.returncode == 0
        assert int(cpp.stdout) == expected
        span = max(1, max(ts) - min(ts))
        wrapped = ((product & MAX) + span - 1) // span
        assert int(release.stdout) == wrapped != expected
        assert checked.returncode != 0 and "attempt to multiply with overflow" in checked.stderr
        boundaries.append({"name": name, "input": data.strip(), "oracle": str(expected),
                           "results": {k: {"exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
                                       for k, r in results.items()}})
    (out / "boundaries.json").write_text(json.dumps(boundaries, indent=2) + "\n")
    summary = {"seed": SEED, "parity_cases": len(cases), "unexpected_mismatches": 0,
               "synthetic_parity_cases": synthetic_count, "upstream_fixture_windows": len(fixture) - 735,
               "expected_release_mismatches": len(probes), "expected_checked_overflow_failures": len(probes),
               "target_seconds": 120, "floor": 1, "full_node_or_cache_integration": False,
               "corpus_uncompressed_sha256": hashlib.sha256(corpus.encode()).hexdigest()}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
