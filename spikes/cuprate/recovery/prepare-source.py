#!/usr/bin/env python3
"""Restore the complete historical Cuprate archive without changing its pins.

All input paths are explicit, so a shallow container mount works too.
Requires Python 3.12+ for tarfile's data extraction filter.
This restores archive files only. The constants crate also needs a genuine Git
checkout for commit metadata; see the recovery report before compiling.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(archive, destination, spike, receipt_path):
    lock = json.loads((spike / "source-lock.json").read_text())
    receipt = json.loads(receipt_path.read_text())
    if receipt["commit"] != lock["cuprate_commit"]:
        raise ValueError("receipt commit differs from source lock")
    if sha256(archive) != receipt["archive_sha256"]:
        raise ValueError("archive SHA-256 differs from historical receipt")
    if destination.exists():
        raise ValueError("destination must not exist; existing sources are never overwritten")
    root = "cuprate-" + lock["cuprate_commit"]
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] != root or ".." in parts:
                raise ValueError("unexpected archive member: " + member.name)
        # Validate every retained source pin before creating output.
        for name, expected in lock["cuprate_files_sha256"].items():
            stream = source.extractfile(root + "/" + name)
            if stream is None:
                raise ValueError("missing pinned file: " + name)
            with stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("source SHA-256 mismatch: " + name)
        destination.mkdir(parents=True)
        source.extractall(destination, filter="data")
    prepared = destination / root
    return {
        "source": str(prepared),
        "commit": lock["cuprate_commit"],
        "archive_sha256": receipt["archive_sha256"],
        "verified_pinned_files": len(lock["cuprate_files_sha256"]),
        "cargo_lock_sha256": sha256(prepared / "Cargo.lock"),
        "archive_members": len(members),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--spike", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.archive, args.destination, args.spike, args.receipt)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        parser.exit(2, f"preparation refused: {error}\n")
    print(json.dumps(result, indent=2))
