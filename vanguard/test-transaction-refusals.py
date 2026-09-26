#!/usr/bin/env python3
"""Challenge transaction receipt checks with re-manifested mutations."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

VERIFY = Path(__file__).with_name("verify-transaction.py")


def manifest(out):
    (out / "MANIFEST.sha256").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n"
        for p in sorted(out.rglob("*")) if p.is_file() and p != out / "MANIFEST.sha256"))


def receipt_edit(out, edit):
    path = out / "receipt.json"
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data) + "\n")


def replace(out, path, old, new):
    file = out / path
    data = file.read_bytes()
    if old not in data:
        raise ValueError("mutation did not match: " + path)
    file.write_bytes(data.replace(old, new, 1))


def main():
    source = Path(sys.argv[1]).resolve()
    subprocess.run([sys.executable, "-B", str(VERIFY), str(source)], check=True)
    cases = {
        "positive_control": lambda out: replace(out, "run1/results.tsv", b"boundary_valid_transaction\tpass", b"boundary_valid_transaction\tFAIL"),
        "missing_rejection": lambda out: replace(out, "run2/results.tsv", b"proof_corrupt.core_reject\tpass\n", b""),
        "wrong_pin": lambda out: receipt_edit(out, lambda d: d.update(upstream="0" * 40)),
        "wrong_source": lambda out: receipt_edit(out, lambda d: d["source_sha256"].update({"vanguard/transaction/transaction_tests.cpp": "0" * 64})),
        "network_enabled": lambda out: receipt_edit(out, lambda d: d["commands"][1].remove("--network=none")),
        "bad_duration": lambda out: receipt_edit(out, lambda d: d["metrics"]["run2"].update(wall_seconds=-1)),
        "oom": lambda out: replace(out, "run1.memory-events", b"oom 0", b"oom 1"),
        "false_suffix_fixture": lambda out: (out / "run1/blob_suffix.tx.bin").write_bytes((out / "run1/valid.tx.bin").read_bytes()),
    }
    with tempfile.TemporaryDirectory(prefix="vanguard-tx-refusals-") as temp:
        for name, mutate in cases.items():
            out = Path(temp) / name
            shutil.copytree(source, out)
            mutate(out)
            manifest(out)
            result = subprocess.run([sys.executable, "-B", str(VERIFY), str(out)], capture_output=True, text=True)
            if result.returncode == 0 or "FAIL_VANGUARD_TRANSACTION:" not in result.stderr:
                raise SystemExit("unexpected verifier result for " + name + ": " + result.stderr)
            print("refused " + name)
    print(f"PASS_VANGUARD_TRANSACTION_REFUSALS cases={len(cases)}")


if __name__ == "__main__":
    main()
