#!/usr/bin/env python3
"""Prove that changed boundary outcomes and pins fail even after re-manifesting."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

VERIFY = Path(__file__).with_name("verify-boundary.py")


def replace(d, name, old, new):
    p = d / name
    before = p.read_text()
    assert old in before, "mutation did not reach its target"
    p.write_text(before.replace(old, new, 1))


def receipt(d, edit):
    p = d / "receipt.json"
    value = json.loads(p.read_text())
    edit(value)
    p.write_text(json.dumps(value))


def check(d):
    return subprocess.run([sys.executable, str(VERIFY), str(d)], capture_output=True, text=True)


def main():
    evidence = Path(sys.argv[1])
    control = check(evidence)
    assert control.returncode == 0 and control.stdout.startswith("PASS_VANGUARD_BOUNDARY"), control.stderr
    cases = [
        ("guarded abort", lambda d: replace(d, "run1.tsv", "1.full.guard.trailing\tfalse\tfalse", "1.full.guard.trailing\tfalse\tsignal_6")),
        ("relabelled acceptance", lambda d: replace(d, "run1.tsv", "1.full.guard.trailing\tfalse\tfalse", "1.full.guard.trailing\ttrue\ttrue")),
        ("missing positive control", lambda d: replace(d, "run2.tsv", "1.full.guard.valid\ttrue\ttrue\n", "")),
        ("hidden raw abort", lambda d: replace(d, "run1.tsv", "1.full.raw.layer_minus_1\tsignal_6\tsignal_6", "1.full.raw.layer_minus_1\tfalse\tfalse")),
        ("changed source", lambda d: receipt(d, lambda r: r["source_sha256"].update({"vanguard/boundary/verify.cpp": "0" * 64}))),
        ("changed fixture", lambda d: receipt(d, lambda r: r["fixture_sha256"].update({"fcmp_pp_verify_inputs_1in.bin": "0" * 64}))),
        ("nonfinite wall time", lambda d: receipt(d, lambda r: r["metrics"]["run1"].update(wall_seconds=float("inf")))),
        ("network enabled", lambda d: receipt(d, lambda r: r["commands"][1].remove("--network=none"))),
        ("duplicate receipt key", lambda d: replace(d, "receipt.json", '"base_commit":', '"base_commit": "hidden", "base_commit":')),
    ]
    for name, edit in cases:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "evidence"
            shutil.copytree(evidence, d)
            edit(d)
            (d / "MANIFEST.sha256").write_text("".join(
                f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                for p in sorted(d.iterdir()) if p.is_file() and p.name != "MANIFEST.sha256"))
            result = check(d)
            assert result.returncode != 0 and result.stderr.startswith("FAIL_VANGUARD_BOUNDARY"), (name, result)
            print("REFUSED " + name)
    print(f"PASS_VANGUARD_BOUNDARY_REFUSALS cases={len(cases)}")


if __name__ == "__main__":
    main()
