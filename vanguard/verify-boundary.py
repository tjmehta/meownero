#!/usr/bin/env python3
"""Reconcile boundary receipts against fixed outcomes and current source bytes."""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def unique(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key: " + k)
        d[k] = v
    return d


def expected():
    lines = []
    def add(count, prefix, case, value):
        lines.append(f"{count}.{prefix}{case}\t{value}\t{value}\n")
    for count in (1, 2, 4, 8, 128):
        for kind in ("full.", "membership."):
            add(count, kind, "raw.valid", "true")
            add(count, kind, "raw.trailing", "true")
            if kind == "full.":
                add(count, kind, "raw.layer_minus_1", "false" if count == 2 else "signal_6")
            for case in ("valid", "trailing", "truncated", "flip_last", "layer_delta_-2", "layer_delta_-1", "layer_delta_1", "layer_delta_2",
                         "claim_0", "anchor_0", "claim_13", "anchor_13", "claim_256", "anchor_256",
                         "claim_18446744073709551615", "anchor_18446744073709551615", "empty_inputs", "excess_inputs"):
                add(count, kind + "guard.", case, "true" if case == "valid" else "false")
            if kind == "full.":
                add(count, kind + "guard.", "mismatched_key_images", "false")
            for case in ("wrong_root", "invalid_root", "valid_after_rejections"):
                add(count, kind + "guard.", case, "true" if case == "valid_after_rejections" else "false")
    return "".join(lines).encode()


def verify(out):
    manifested = {}
    for line in (out / "MANIFEST.sha256").read_text().splitlines():
        sha, name = line.split("  ", 1)
        assert name == Path(name).name and name not in manifested
        manifested[name] = sha
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name != "MANIFEST.sha256"}
    assert actual == manifested, "manifest mismatch"
    receipt = json.loads((out / "receipt.json").read_text(), object_pairs_hook=unique)
    pin = json.loads((ROOT / "vanguard/source-lock.json").read_text())
    assert json.loads((out / "source-lock.json").read_text(), object_pairs_hook=unique) == pin
    assert receipt["upstream"] == pin["upstream"]["commit"] and receipt["monero_oxide"] == pin["rust"]["monero_oxide_rev"]
    assert receipt["image"] == pin["builder"]["image_id"] and receipt["rustc"] == pin["builder"]["rustc"]
    sources = sorted((ROOT / "vanguard/boundary").iterdir()) + [ROOT / "vanguard/run-boundary.py", ROOT / "vanguard/verify-boundary.py"]
    assert receipt["source_sha256"] == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, "source mismatch"
    # Reuse the already accepted fixed fixture pins without accepting V1 verdicts.
    import importlib.util
    spec = importlib.util.spec_from_file_location("vanguard_v1", ROOT / "vanguard/verify.py")
    v1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v1)
    assert receipt["fixture_sha256"] == v1.UPSTREAM_VECTORS
    assert len(receipt["commands"]) == 3
    for stage, argv in zip(("build", "run1", "run2"), receipt["commands"]):
        cap = "4g" if stage == "build" else "512m"
        for flag in ("--network=none", "--pull=never", "--cpus=2", "--memory=" + cap, "--memory-swap=" + cap, "--pids-limit=256", receipt["image"]):
            assert flag in argv
        metric = receipt["metrics"][stage]
        assert metric["exit"] == 0 and math.isfinite(metric["wall_seconds"]) and metric["wall_seconds"] > 0
        peak = int((out / (stage + ".memory")).read_text())
        assert 0 < peak <= (4 * 1024**3 if stage == "build" else 512 * 1024**2)
        events = dict(line.split() for line in (out / (stage + ".memory-events")).read_text().splitlines())
        assert events["oom"] == events["oom_kill"] == "0"
    for name in ("run1", "run2"):
        assert (out / (name + ".tsv")).read_bytes() == expected(), name + " outcome mismatch"
    print(f"PASS_VANGUARD_BOUNDARY cases={len(expected().splitlines())} raw_aborts=4 hardened_aborts=0")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]))
    except (AssertionError, KeyError, ValueError, OSError, IndexError, TypeError) as e:
        raise SystemExit("FAIL_VANGUARD_BOUNDARY: " + str(e))
