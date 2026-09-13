# Cuprate preview DAA differential spike

This is a source-extraction experiment, **not actual Cargo crate integration or
an independent Meownero validator**. It builds unchanged Cuprate difficulty
function bodies and the actual patched C++ `difficulty.cpp`, then compares their
128-bit results. No daemon, public network, keys or consensus policy is changed.

Run with the preserved source mounted read-only and a fresh output directory:

```sh
bash spikes/cuprate/run.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-swarm-rust-daa-YOUR-UNIQUE-RUN
```

The runner acquires `/tmp/meownero-swarm-20260912-heavy.lock` non-blockingly
(exit 75 means retry later), uses the pinned immutable builder, and runs each
compiler sequentially in one isolated container capped at 512 MiB, zero swap,
one CPU and 64 processes. It installs nothing and downloads nothing. A full
Cuprate build would require a separate resource check and integration task;
this small experiment does not need a full-node build. Network-track work has
priority. Output directories must be empty; existing evidence is never replaced.

## Source and dependency boundary

`source-lock.json` pins Cuprate release tag `cuprated-0.1.0-preview` to
`318c2dea4eb404ac4ecf2bea87c1a4696b0198cc`, and the applied C++ source to
`7410c04bab0e304112710d63c3225c110bd8b4de` (tree
`4db958cb96d72943c5c2433bd5f4a8f730037148`, upstream
`4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, patches 0001–0015).
Every vendored upstream file and the affected C++ files are SHA-256 checked
before compilation. Cuprate source files are complete and unchanged; their MIT
license is retained. The pinned archive URL is in the lock file.

`extract.py` copies literal contiguous items: the DAA constants, config struct
and impl, `next_difficulty`, `get_window_start_and_end`, hard-fork block-time
constants, enum and `block_time` method. It adds only standard-library imports,
`Default/Clone/Copy` derives for the enum, an impl shell, and the local stdin
adapter. It does not rewrite arithmetic, sorting, truncation or config. The
generated `extracted.rs` is retained in evidence for direct review.

The executable uses only Rust's standard library; there is no dependency
resolution or downloaded CI binary. The upstream Cargo manifests and lockfile
are provenance and assessment inputs, **not a claim those dependencies compiled**.
The host's existing Rust toolchain is mounted read-only into the builder; its
version, compiler/LLVM/sysroot hashes are captured. This does not establish
independent toolchain reconstruction or reproducible Cuprate node builds.

## Corpus semantics

Both adapters consume identical decimal `u64` timestamps and full-width `u128`
cumulative work, oldest sample first. They receive 0–735 **post-genesis** pairs,
strictly increasing work, no fixed-difficulty override, floor 1, and 120 seconds.
Cuprate uses the actual extracted `HardFork::V16.block_time()`; the C++ adapter
passes 120 explicitly. The calculation keeps the first 720 pairs, so lag grows
from one through fifteen samples when input length grows from 721 through 735.
Sorting/selecting timestamps must not reorder cumulative work.

The existing `chain/daa-benchmark.cpp` adapter truncates results to 64 bits; this
spike uses a separate small stream adapter to preserve the full comparison domain.
C++ is compiled from its actual translation unit, not a port. An independent
Python integer formula checks expected results, with a 128-bit result-overflow
sentinel of zero matching C++.

The corpus contains 605 synthetic parity cases (startup, cut/window/lag
boundaries, equal/reversed/duplicate/outlier timestamps, variable work, high
cumulative offsets, rounding and multiplication thresholds), plus 1,265 windows
from Cuprate's unchanged `dif_3000000_3002000` fixture. Fixture pairs are
`(cumulative work, timestamp)` and are explicitly reversed at the adapter boundary.
The first 735 pairs predict the next pair's work increment; each subsequent
window advances one pair. This matches upstream
`calculate_diff_3000000_3002000`. The fixture is upstream-supplied historical
data, not independently authenticated blockchain history. Its filename is not
used to infer height alignment.

Three deliberately extreme arithmetic probes are reported separately. They obey
the primitive's type/order constraints but exceed the Rust multiplication domain
(`windowed_work * 120 > u128::MAX`). No proof-of-work, timestamp-acceptance or
reachable-history check is performed for them. Release-style arithmetic wraps;
the separately compiled checked-arithmetic build aborts. Neither result establishes
a live consensus exploit. The harness asserts these exact known mismatches, and
fails on any unexpected result.

Excluded: 90-second comparison (upstream block-time mapping has only 60/120),
other hard forks, raised floors, fixed difficulty, malformed/decreasing work,
genesis validation, real cache population/rollback, main/alternative chain
acceptance, proofs, serialization, RPC, wallets, FCMP++, network performance and
whole-node safety. Synthetic timestamps need not satisfy contextual chain rules.
No performance claim follows from this correctness harness.

## Review outputs

`summary.json`, `parity.jsonl`, deterministic `corpus.tsv.gz`, and
`boundaries.json` retain counts, inputs/digests and all mismatch outputs. Toolchain,
source-extraction, image, binary hashes, run logs and cgroup memory counters are
captured alongside them. The track report is
[`research/swarm-rust-2026-09-12.md`](../../research/swarm-rust-2026-09-12.md).

## Build-tooling recovery

September 13 recovery adds full pinned archive preparation, a bounded fetch into
an isolated cache, and a capped offline Cargo-resolution check under `recovery/`. See the
[recovery report](../../research/recovery-rust-2026-09-13.md) for exact commands,
cache inventory, passing frozen dependency resolution and a successful actual
context-crate `cargo check` with genuine pinned Git sources. The report separately
records the launcher bookkeeping failure and the subsequent passing final wrapper verification.
The historical primitive result is unchanged; runtime integration is untested.
