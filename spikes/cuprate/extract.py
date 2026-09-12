#!/usr/bin/env python3
"""Verify pinned files; extract unchanged Rust items, without async/database deps."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def item(source, marker):
    start = source.index(marker)
    pos = source.index("{", start)
    depth = 1
    end = pos + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


def main():
    cpp, output = map(Path, sys.argv[1:])
    lock = json.loads((HERE / "source-lock.json").read_text())
    for root, key in ((HERE / "upstream", "cuprate_files_sha256"),
                      (cpp, "cpp_files_sha256")):
        for path, expected in lock[key].items():
            actual = hashlib.sha256((root / path).read_bytes()).hexdigest()
            if actual != expected:
                raise SystemExit(f"source mismatch: {root / path}")
    diff = (HERE / "upstream/consensus/context/src/difficulty.rs").read_text()
    hf = (HERE / "upstream/types/types/src/hard_fork.rs").read_text()
    # Items are literal contiguous slices. Only derives/imports/impl shell are local.
    parts = ["// Generated from hash-verified upstream; see extract.py.\n",
             "use std::{collections::VecDeque, time::Duration};\n"]
    for source, prefix in ((diff, "const DIFFICULTY_"), (hf, "const BLOCK_TIME_")):
        parts += [line + "\n" for line in source.splitlines() if line.startswith(prefix)]
    parts += ["#[derive(Default, Clone, Copy)]\n", item(hf, "pub enum HardFork {"),
              "impl HardFork {\n", item(hf, "pub const fn block_time("), "}\n",
              item(diff, "pub struct DifficultyCacheConfig {"),
              item(diff, "impl DifficultyCacheConfig {"),
              item(diff, "fn next_difficulty(\n"),
              item(diff, "fn get_window_start_and_end(\n"),
              (HERE / "driver.rs").read_text()]
    output.write_text("\n".join(parts))
    print("Pinned source hashes verified; unchanged Rust items extracted.")


if __name__ == "__main__":
    main()
