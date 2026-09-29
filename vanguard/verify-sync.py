#!/usr/bin/env python3
"""Reconcile a Vanguard sync run's sources, containment, checks and states."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def verify(out):
    if not __debug__:
        raise ValueError("assertions required")
    manifest = {}
    for line in (out / "MANIFEST.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert name not in manifest and not Path(name).is_absolute() and ".." not in Path(name).parts
        manifest[name] = digest
    actual = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.rglob("*") if p.is_file() and p != out / "MANIFEST.sha256"}
    assert actual == manifest, "manifest mismatch"
    spec = importlib.util.spec_from_file_location("runner", ROOT / "vanguard/run-sync.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    receipt = json.loads((out / "receipt.json").read_text())
    assert json.loads((out / "source-lock.json").read_text()) == runner.PIN
    assert receipt["source_sha256"] == {str(p.relative_to(ROOT)): runner.sha(p) for p in runner.SOURCE_FILES}
    assert receipt["upstream"] == runner.PIN["upstream"]["commit"]
    assert receipt["image"] == runner.PIN["builder"]["image_id"]
    assert receipt["rustc"] == runner.PIN["builder"]["rustc"]
    assert len(receipt["commands"]) == 3
    assert receipt["binary"]["bytes"] > 0 and len(receipt["binary"]["sha256"]) == 64
    for stage, argv in zip(("build", "run1", "run2"), receipt["commands"]):
        for flag in ("--pull=never", "--network=none", "--cpus=2", "--memory=4g", "--memory-swap=4g",
                     "--pids-limit=256", receipt["image"]):
            assert flag in argv, "containment missing: " + flag
        metric = receipt["metrics"][stage]
        assert metric["exit"] == 0 and math.isfinite(metric["wall_seconds"]) and 0 < metric["wall_seconds"] < 900
        assert 0 < int((out / (stage + ".memory")).read_text()) <= 4 * 1024**3
        events = dict(line.split() for line in (out / (stage + ".memory-events")).read_text().splitlines())
        assert events["oom"] == events["oom_kill"] == "0"
        cpu = dict(line.split() for line in (out / (stage + ".cpu")).read_text().splitlines())
        assert int(cpu["usage_usec"]) > 0
    for run in ("run1", "run2"):
        checks = [line.split("\t") for line in (out / run / "checks.tsv").read_text().splitlines()]
        assert len(checks) > 400 and all(len(row) == 2 and row[1] == "pass" for row in checks)
        names = [row[0] for row in checks]
        for required in ("reordered_block_not_applied", "source_tx_admitted", "peer_tx_admitted",
                         "initial_convergence", "restart_catchup_convergence", "trusted_root_changed",
                         "reference_after_v17_fork_60", "fork_convergence", "source_key_image_rolled_back",
                         "fork_pool_convergence", "stale_root_spend_rejected", "invalid_block_state_unchanged",
                         "reverse_convergence", "reverse_tip_restored", "reverse_key_image_reapplied"):
            assert names.count(required) == 1, required
        states = [line.split("\t") for line in (out / run / "states.tsv").read_text().splitlines()]
        assert [row[0] for row in states] == ["before_a", "before_b", "restart_b", "fork_prefix_b", "fork_a", "fork_b", "reverse_a", "reverse_b"]
        assert all(len(row) == 8 and len(row[2]) == 64 and len(row[3]) == 64 for row in states)
        assert states[0][1:] == states[1][1:] == states[2][1:]
        assert states[4][1:] == states[5][1:]
        assert states[6][1:] == states[7][1:]
        assert states[0][3] != states[4][3] and states[0][4] == states[4][4]
        assert states[0][5:7] == ["1", "1"] and states[4][5:7] == ["0", "0"]
        assert states[6][3] == states[0][3] and states[6][5:7] == ["1", "1"]
        assert states[4][7] == states[5][7] == "1", "stale pool transaction remained on v17"
        controls = [line.split("\t") for line in (out / run / "controls.tsv").read_text().splitlines()]
        assert [row[0] for row in controls] == ["stale_root_a", "stale_root_b", "reverse_spend_alt_b",
                                               "reverse_extension_a", "reverse_extension_b",
                                               "reverse_extension_a", "reverse_extension_b",
                                               "reverse_extension_a", "reverse_extension_b"]
        assert all(len(row) == 6 for row in controls)
        assert all(row[1:] == ["1", "0", "0", "1", "0"] for row in controls[:2])
        assert controls[2][1:] == ["0", "0", "0", "1", "0"]
        assert controls[-2][1:] == controls[-1][1:] == ["0", "1", "0", "0", "1"]
        log = (out / run / "core.log").read_text()
        assert log.count("Failed to batch verify FCMP++ txs") >= 4, "stale spend rejection stage absent"
        assert "Validating txpool for v17" in log and "txpool contents for v17" in log
    print("PASS_VANGUARD_SYNC two_runs=2")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]))
    except (AssertionError, KeyError, ValueError, OSError, IndexError, TypeError) as error:
        raise SystemExit("FAIL_VANGUARD_SYNC: " + str(error))
