#!/usr/bin/env python3
"""Reconcile a two-process Vanguard sync run's sources and receipts."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
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
    spec = importlib.util.spec_from_file_location("runner", ROOT / "vanguard/run-sync-process.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    receipt = json.loads((out / "receipt.json").read_text())
    assert json.loads((out / "source-lock.json").read_text()) == runner.PIN
    assert receipt["source_sha256"] == {str(p.relative_to(ROOT)): runner.sha(p) for p in runner.SOURCE_FILES}
    commit = receipt["commit"]
    assert len(commit) == 40 and all(c in "0123456789abcdef" for c in commit)
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    for name, digest in receipt["source_sha256"].items():
        source = subprocess.check_output(["git", "-C", str(ROOT), "show", commit + ":" + name])
        assert hashlib.sha256(source).hexdigest() == digest, "receipt commit source mismatch: " + name
    assert receipt["upstream"] == runner.PIN["upstream"]["commit"]
    assert receipt["image"] == runner.PIN["builder"]["image_id"]
    assert receipt["rustc"] == runner.PIN["builder"]["rustc"]
    assert receipt["transport"] == "AF_UNIX/SOCK_STREAM"
    assert len(receipt["commands"]) == 3
    assert receipt["binary"]["bytes"] > 0 and len(receipt["binary"]["sha256"]) == 64
    for stage, argv in zip(("build", "run1", "run2"), receipt["commands"]):
        for flag in ("--pull=never", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                     "--cpus=2", "--memory=4g", "--memory-swap=4g",
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
        assert len(checks) > 450 and all(len(row) == 2 and row[1] == "pass" for row in checks)
        names = [row[0] for row in checks]
        for required in ("distinct_process_ids", "private_unix_stream_connected",
                         "socket_reconnected_same_peer", "replayed_tip_keeps_chain_state",
                         "oversized_frame_reconnect", "malformed_frame_keeps_chain_state",
                         "truncated_frame_reconnect", "truncated_frame_keeps_chain_state",
                         "socket_path_removed", "peer_reordered_block_not_applied",
                         "spend_delivered_to_both_processes", "initial_cross_process_convergence",
                         "restart_cross_process_catchup", "reference_after_v17_fork_60",
                         "trusted_root_changed_across_processes", "fork_cross_process_convergence_and_rollback",
                         "stale_root_supplement_rejected_both_processes",
                         "stale_root_pool_rejected_both_processes",
                         "invalid_blocks_leave_both_processes_unchanged",
                         "source_alt_spend_flushed", "source_alt_supplement_admitted",
                         "reverse_cross_process_convergence_and_key_image_reapplication", "peer_clean_exit"):
            assert names.count(required) == 1, required
        processes = [line.split("\t") for line in (out / run / "processes.tsv").read_text().splitlines()]
        assert [row[0] for row in processes] == ["source", "peer"]
        assert all(len(row) == 2 and int(row[1]) > 1 for row in processes)
        assert processes[0][1] != processes[1][1]
        assert not (out / run / "nodes" / "peer.sock").exists()
        assert (out / run / "rejected-frames.tsv").read_text().splitlines() == [
            "oversized_or_short\tbad socket frame", "oversized_or_short\tshort socket frame"]
        states = [line.split("\t") for line in (out / run / "states.tsv").read_text().splitlines()]
        assert [row[0] for row in states] == ["before_a", "before_b", "restart_b", "fork_prefix_a", "fork_a", "fork_b", "reverse_a", "reverse_b"]
        assert all(len(row) == 8 and len(row[2]) == 64 and len(row[3]) == 64 for row in states)
        assert states[0][1:] == states[1][1:] == states[2][1:]
        assert states[4][1:] == states[5][1:]
        assert states[6][1:] == states[7][1:]
        assert states[0][3] != states[4][3] and states[0][4] == states[4][4]
        assert states[0][5:7] == ["1", "1"] and states[4][5:7] == ["0", "0"]
        assert states[6][3] == states[0][3] and states[6][5:7] == ["1", "1"]
        assert states[4][7] == states[5][7] == "1", "stale pool transaction remained on v17"
        controls = [line.split("\t") for line in (out / run / "controls.tsv").read_text().splitlines()]
        assert [row[0] for row in controls] == ["stale_root_a", "stale_root_b",
                                               "stale_root_pool_a", "stale_root_pool_b", "reverse_spend_alt_a",
                                               "reverse_extension_a", "reverse_extension_b",
                                               "reverse_extension_a", "reverse_extension_b",
                                               "reverse_extension_a", "reverse_extension_b"]
        assert all(len(row) == 6 for row in controls)
        assert all(row[1:] == ["1", "0", "0", "1", "0"] for row in controls[:4])
        assert controls[4][1:] == ["0", "0", "0", "1", "0"]
        assert controls[-2][1:] == controls[-1][1:] == ["0", "1", "0", "0", "1"]
        log = (out / run / "core-a.log").read_text()
        peer_log = (out / run / "core-b.log").read_text()
        for node_log in (log, peer_log):
            assert node_log.count("Failed to batch verify FCMP++ txs") >= 2, "stale spend rejection stage absent"
            assert node_log.count("Failed to verify input FCMP++ signatures") >= 1, "pool-path rejection absent"
            assert "Validating txpool for v17" in node_log and "txpool contents for v17" in node_log
        removals = list(re.finditer(r"Removing txid <([0-9a-f]{64})> from the pool", log))
        assert len(removals) == 1, "source pre-supplement pool flush absent"
        assert log.find("Transaction added to pool: txid <" + removals[0].group(1) + ">", removals[0].end()) > 0, \
            "alternative spend supplement admission absent"
    print("PASS_VANGUARD_SYNC_PROCESS two_runs=2")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]))
    except (AssertionError, KeyError, ValueError, OSError, IndexError, TypeError, subprocess.CalledProcessError) as error:
        raise SystemExit("FAIL_VANGUARD_SYNC_PROCESS: " + str(error))
