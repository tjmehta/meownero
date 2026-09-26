#!/usr/bin/env python3
"""Reconcile local transaction receipts, expected checks, pins and containment."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def expected():
    names = ["generate_wallet_transaction_and_chain", "upstream_event_shape", "initialize_isolated_core", "core_is_fakechain",
             "one_constructed_transaction", "constructed_fcmp_transaction", "constructed_carrot_outputs", "constructed_range_proof",
             "initial_pool_empty", "database_anchor_matches_claim", "expand_constructed_transaction", "boundary_valid_transaction",
             "boundary_trailing_proof_byte", "boundary_truncated_proof", "boundary_wrong_depth", "boundary_corrupt_proof",
             "serialize_valid_transaction"]
    for name in ("blob_suffix", "blob_truncated"):
        names += [name + ".parse", name + ".state_unchanged"]
    for name in ("proof_corrupt", "fee_changed", "range_proof_corrupt", "carrot_view_tag_changed", "unknown_reference_block", "wrong_depth_exact_size"):
        names += [name + suffix for suffix in (".serialized_mutation", ".parse", ".core_reject", ".state_unchanged")]
    names += ["boundary_valid_after_rejections", "valid_transaction_in_pool", "valid_block_is_tip", "valid_transaction_in_chain",
              "confirmed_pool_empty", "confirmed_key_image_spent", "replay_through_core", "receipt_streams_ok"]
    return "".join(name + "\tpass\n" for name in names).encode()


def verify(out):
    if not __debug__:
        raise ValueError("verification requires assertions enabled")
    manifest = {}
    for line in (out / "MANIFEST.sha256").read_text().splitlines():
        sha, name = line.split("  ", 1)
        assert name not in manifest and not Path(name).is_absolute() and ".." not in Path(name).parts
        manifest[name] = sha
    actual = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.rglob("*") if p.is_file() and p != out / "MANIFEST.sha256"}
    assert actual == manifest, "manifest mismatch"
    spec = importlib.util.spec_from_file_location("runner", ROOT / "vanguard/run-transaction.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    receipt = json.loads((out / "receipt.json").read_text())
    pin = runner.PIN
    assert json.loads((out / "source-lock.json").read_text()) == pin
    assert receipt["upstream"] == pin["upstream"]["commit"] and receipt["monero_oxide"] == pin["rust"]["monero_oxide_rev"]
    assert receipt["image"] == pin["builder"]["image_id"] and receipt["rustc"] == pin["builder"]["rustc"]
    assert receipt["source_sha256"] == {str(p.relative_to(ROOT)): runner.digest(p) for p in runner.sources()}, "source mismatch"
    assert len(receipt["commands"]) == 3
    for stage, argv in zip(("build", "run1", "run2"), receipt["commands"]):
        for flag in ("--network=none", "--pull=never", "--cpus=2", "--memory=4g", "--memory-swap=4g", "--pids-limit=256", receipt["image"]):
            assert flag in argv, "missing containment " + flag
        metric = receipt["metrics"][stage]
        assert metric["exit"] == 0 and math.isfinite(metric["wall_seconds"]) and 0 < metric["wall_seconds"] < 1800
        assert 0 < int((out / (stage + ".memory")).read_text()) <= 4 * 1024**3
        events = dict(line.split() for line in (out / (stage + ".memory-events")).read_text().splitlines())
        assert events["oom"] == events["oom_kill"] == "0"
    for run in ("run1", "run2"):
        assert (out / run / "results.tsv").read_bytes() == expected(), run + " outcomes mismatch"
        observations = dict(line.split("\t") for line in (out / run / "observations.tsv").read_text().splitlines())
        assert int(observations["inputs"]) == 1 and int(observations["outputs"]) >= 2
        assert 1 <= int(observations["anchor_layers"]) <= 12
        assert int(observations["reference_block"]) < int(observations["final_height"])
        blob = (out / run / "valid.tx.bin").read_bytes()
        assert int(observations["tx_bytes"]) == len(blob) > int(observations["proof_bytes"]) > 0
        assert (out / run / "blob_suffix.tx.bin").read_bytes() == blob + bytes([0])
        assert (out / run / "blob_truncated.tx.bin").read_bytes() == blob[:-1]
        for field in ("generation_seconds", "replay_seconds"):
            value = float(observations[field])
            assert math.isfinite(value) and 0 < value < 900
    print(f"PASS_VANGUARD_TRANSACTION checks={len(expected().splitlines())} runs=2")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]))
    except (AssertionError, KeyError, ValueError, OSError, IndexError, TypeError) as error:
        raise SystemExit("FAIL_VANGUARD_TRANSACTION: " + str(error))
