# Rust track — source-pinned Cuprate DAA comparison, 2026-09-12

Bounded deliverable complete: **1,870 primitive parity cases passed**, with
**three separately expected arithmetic-boundary mismatches**. This builds
unchanged extracted Cuprate functions against the actual patched C++ DAA. It is
**not Cargo crate integration, a Cuprate node build, or an independent Meownero
validator**. No policy or production code changed.

Worktree base: verified `39070e8e3ab32a695d80c90b7c0ad74cf39fb581`, including
`81b3182`. The complete decision note and resumed handoff were read first.
Previously closed binary/wallet/reorg evidence was not rerun. All changes are
inside `spikes/cuprate/` and this track's report/evidence paths; all scratch writes
used `/tmp/meownero-swarm-rust-*`. The preserved C++ tree was mounted read-only.

## Source assessment and selected integration boundary

The release tag resolves to **`318c2dea4eb404ac4ecf2bea87c1a4696b0198cc`**.
The release API was fetched directly from GitHub on September 12, and the pinned
source archive was downloaded from GitHub codeload. No CI binary was downloaded.
All vendored source bytes were matched both to SHA-256 pins and to GitHub's
commit-tree blob IDs. Receipts: [release metadata](evidence/swarm-2026-09-12/rust/release.json),
[source receipt](evidence/swarm-2026-09-12/rust/source-receipt.json), and
[source lock](../spikes/cuprate/source-lock.json).

| Preview module | Source finding | Bounded usefulness / boundary |
|---|---|---|
| `consensus/context` | DAA pure function is colocated with async database/cache code; normal config is window 720, cut 60, lag 15. | Selected: compare the unchanged function and its actual config/block-time items. Full crate pulls rules, types, async services and RandomX dependencies. |
| `consensus/rules` | PoW threshold, block checks, Monero genesis and miner reward logic. | Future primitive comparison possible; current Monero genesis/reward logic requires explicit Meownero integration. No whole-rules compatibility claim. |
| `types/types` | Hard-fork block time maps V1 to 60 seconds and V2–V16 to 120. | Exact block-time method extracted; this run uses V16 only. A 90-second adapter would change upstream semantics and is excluded. |
| `net/epee-encoding` | Separate serialization crate with bytes, ref-cast, paste and local fixed-bytes/hex dependencies. | Plausible later byte-corpus comparison; this track does not build it or claim transaction-serialization coverage. |

Primary source references are the pinned
[DAA module](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/consensus/context/src/difficulty.rs),
[context manifest](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/consensus/context/Cargo.toml),
[genesis module](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/consensus/rules/src/genesis.rs),
[reward module](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/consensus/rules/src/miner_tx.rs),
[hard-fork mapping](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/types/types/src/hard_fork.rs),
and [epee manifest](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/net/epee-encoding/Cargo.toml).
Complete copies of these assessed files are retained in the spike.

The preserved upstream Cargo.lock pins, among other dependencies,
`monero-oxide` to `946ec5f00ff071b129758ee8cba5528539fccfe4` and `randomx-rs` to
`76c2385771ca5aca941e0991ebd822e6edb8d94d`. These dependencies were **not built**.
The extracted harness needs only Rust std. Its release-style arithmetic and
checked-arithmetic builds use the same source, `opt-level=3`, one codegen unit,
and `panic=abort`; they differ only in overflow checking. They do not reproduce
the entire upstream Cargo release profile (including LTO/dependency resolution).

## Comparison and verified results

C++ uses applied HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, tree
`4db958cb96d72943c5c2433bd5f4a8f730037148`, upstream
`4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, patches 0001–0015. The actual
`src/cryptonote_basic/difficulty.cpp` is compiled into the adapter. This avoids
the existing benchmark adapter's 64-bit output restriction. The harness preserves
full-width cumulative work and results.

Inputs are post-genesis samples in chain order, 0–735 pairs, strictly increasing
cumulative work, 120-second target, floor 1, and no fixed-difficulty override.
Both implementations retain the first 720 samples, then compute timestamp order
statistics without reordering cumulative work. The inspected C++ main/alternative
callers and Cuprate cache initializer all skip genesis; **those callers and cache
transitions are not executed by this harness**.

| Evidence class | Result | Meaning |
|---|---|---|
| 605 deterministic synthetic windows | C++, Rust unchecked, Rust checked and Python wide-integer oracle all agree | Startup, 600/720/735 boundaries, duplicate/reversed/outlier timestamps, ignored lag, varying work, high cumulative offsets and rounding. Type-valid inputs are not necessarily chain-reachable. |
| 1,265 pinned upstream fixture windows | All three binaries and oracle agree with the fixture's next cumulative-work increment | Matches upstream fixture test indexing exactly: 735 prior pairs predict the next increment; slide by one. Source-authenticated fixture, not independently authenticated chain history. |
| Three extreme arithmetic probes | Three known unchecked mismatches and three checked aborts; no unexpected mismatch | Deliberately beyond the `u128` multiplication domain; no chain-reachability or exploit claim. |

The [upstream fixture test](https://github.com/Cuprate/cuprate/blob/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc/consensus/src/tests/context/difficulty.rs)
interprets pairs as cumulative work then timestamp. The harness maps them
explicitly into timestamp/work adapter order and checks each predicted increment.
It does not infer real heights from the fixture filename or reuse the cache test's
height labels as independently verified metadata.

For example, with timestamps `[0, 120]` and cumulative work
`[1, 2835686391007820528861455061931401764]`, the C++ result is
`2835686391007820528861455061931401763`, while unchecked Rust returns `1`.
The multiplication overflows even though the correct quotient fits `u128`.
With span 1, C++ returns its overflow sentinel `0`, while unchecked Rust returns
`104`. Checked Rust aborts on multiplication in both cases. Exact inputs, all
outputs and the third probe are in
[boundaries.json](evidence/swarm-2026-09-12/rust/run/boundaries.json).
Cuprate's source already includes an unchecked-multiplication TODO, and its
property-test generator explicitly restricts work to avoid overflow; this report
does not claim a newly discovered live vulnerability.

The arithmetic probes obey adapter type/order constraints, but the harness does
not construct valid proof-of-work histories or establish their reachability.
Some synthetic timestamps deliberately violate plausible contextual time rules.
The preserved historical fixture exercises ordinary inherited DAA behavior; it
does not establish Meownero chain integration or FCMP++ readiness.

## Execution and evidence

Command, exit **0**:

```sh
bash spikes/cuprate/run.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-swarm-rust-daa-fixture-run-20260912
```

The run used immutable builder
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`,
a read-only mount of the existing Rust toolchain, the shared flock, one compiler
at a time, one CPU, a 512 MiB container limit with no swap, no networking, no port
bindings, and automatic container removal. Busy-lock attempts exited 75 without
compiling; the runner never waited holding the lock for host RAM. This was a
bounded module build, not the large build subject to the 5 GiB availability gate.

The final run's cgroup peak was 499,380,224 bytes (about 476.25 MiB), with no
limit-hit, OOM or OOM-kill event recorded. Raw peak/events counters are retained.
Existing host toolchain provenance is recorded; independent compiler
reconstruction and cross-host reproducibility remain unproved.

- [Summary](evidence/swarm-2026-09-12/rust/run/summary.json),
  [run log](evidence/swarm-2026-09-12/rust/run/run.log),
  [per-case outputs](evidence/swarm-2026-09-12/rust/run/parity.jsonl),
  [compressed exact inputs](evidence/swarm-2026-09-12/rust/run/corpus.tsv.gz).
- [Compiled extraction](evidence/swarm-2026-09-12/rust/run/extracted.rs),
  [binary/extraction hashes](evidence/swarm-2026-09-12/rust/run/build.sha256),
  [Rust version](evidence/swarm-2026-09-12/rust/run/rust-toolchain.txt),
  [C++ version](evidence/swarm-2026-09-12/rust/run/cpp-toolchain.txt).
- Memory counters, compiler/LLVM/std hashes and C++ git refs are in the same
  [evidence directory](evidence/swarm-2026-09-12/rust/run/).
  Binaries remain only in the unique scratch run directory; source rebuild is
  supported by the runner. Bash/Python syntax and `git diff --check` also pass.

## Factual corrections, separate from normative choices

**Factual:** release metadata says August 1, 2026 for publication of this tag;
the decision note's August 4 date concerns its social announcement. These are
different events. The preview is beta with initial wallet support and explicitly
non-reproducible CI artifacts, as the
[release page](https://github.com/Cuprate/cuprate/releases/tag/cuprated-0.1.0-preview)
states. No readiness upgrade follows from the available release or this harness.
The source DAA multiplication differs from C++ outside its non-overflow domain;
matching ordinary windows is not universal 128-bit equivalence.

**Normative recommendation:** retain Cuprate as a bounded differential-testing
candidate. Before extending this into a validator, integrate the actual locked
crate/cache path, prove compatible handling or exclusion of arithmetic domains,
and test the Meownero-specific genesis, rewards, hard forks, trust surfaces,
proofs, malformed inputs, reorgs and persistence. These are follow-on gates, not
changes implemented here. Rust's language choice is not cryptographic assurance.

Parent integration/review remains missing by design: this worker does not edit
shared plans, chain README, CI or existing handoffs. No timing, subsidy, floor,
identity, checkpoint, signer, audit-budget or launch decision is made. No push,
deployment, third-party message, host-service change or additional agent was used.
