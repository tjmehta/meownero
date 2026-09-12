# Private draft: make one hash kernel faster without changing its answers

**Status:** local challenge materials and measured baseline only. No optimized
candidate, prize, deadline, recruitment, winner or public event is claimed.
These are proposed evaluation rules, not a change to protocol or project policy.

## Precise scope

Target `cn_fast_hash` through its existing Keccak implementation, not mining,
wallet UX, FCMP++ or whole-chain throughput. Upstream already benchmarks this
function with 32-byte and 16,384-byte inputs in
`tests/performance_tests/cn_fast_hash.h`. The small local harness uses those sizes
and iteration counts, fixed reproducible input, consumed outputs, a warmup and
nine raw timed batches. It additionally checks all 321 preserved fast-hash vectors.
The full upstream performance executable is not built in the preserved tree.

Baseline source tree: `4db958cb96d72943c5c2433bd5f4a8f730037148`, pinned upstream
`4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5` plus the fifteen-patch state. Existing
`hash.c.o` and `keccak.c.o` are linked read-only; their hashes and the fixture hash
are in [baseline inputs](../../research/evidence/swarm-2026-09-12/demo/hash/inputs.sha256).
The harness never writes to the preserved source tree.

Proposed candidate allowlist: **only `src/crypto/keccak.c`**, including existing
function implementations; preserve all exported symbols and signatures from
`keccak.h` and `hash-ops.h`. No header, caller, vector, harness, compiler-flag,
dependency, assembly-file, protocol or allocator changes. No changed digest,
reduced rounds, SHA3 substitution, input memoization, input special cases, or
precomputed fixture answers. Changes to the allowlist require revising this
specification before measurements, rather than accepting an incomparable result.

## Fixed local measurement contract

| Item | Contract |
| --- | --- |
| Hardware | Intel Core i7-8700K, x86_64; logical CPU 0 |
| Builder | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Compiler | Ubuntu GCC 13.3.0 (`13.3.0-6ubuntu2~24.04.1`) |
| Hash object flags | Exact entries in preserved `build/release/compile_commands.json`; includes `-Ofast -DNDEBUG -fno-strict-aliasing -std=c11`, no LTO |
| Harness flags | `-std=c11 -O3 -DNDEBUG -fno-lto -Wall -Wextra -Werror` |
| Resources | One compiler at a time, shared flock; 128 MiB cap/no extra swap; one CPU quota; no network |
| Input | byte `i` is `(i * 131 + 17) mod 256`; 32 and 16,384 bytes |
| Warmup / sample | 1,000 warmup calls per length; 9 batches; 100,000 calls at 32 bytes, 1,000 at 16,384 bytes |
| Timer | `CLOCK_MONOTONIC`, nanoseconds; each output consumed by volatile sink |
| Environment | Shared host; existing governor/turbo/SMT retained; no host tuning or cache purge |

```sh
bash demos/private-payment/measure.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-swarm-demo-hash-my-run
```

Only the tiny harness is compiled, not the daemon or hash objects. This measured
baseline is useful for checking the harness and approximate kernel cost. Shared
host load, CPU-0 sibling contention and frequency changes prevent interpreting
one run as a stable ranking. No ARM, WASM or other compiler result is implied.

For a future comparison, build baseline and candidate objects separately in
unique scratch directories with the exact frozen compile commands (redirect
only source root and object output), mount each tree read-only, and invoke the
same harness. First verify their source diffs and all input hashes. Run three
complete A/B/B/A groups under the lock on the same host; preserve every sample,
group/order and container state. Do not cherry-pick the quickest run. Stop if
thermal throttling, other heavy work or failures make conditions incomparable.
The current runner measures supplied objects; the reviewer must establish the
candidate object's source provenance. This track builds no candidate.

Ready-to-run comparison command **after** the reviewer has supplied a separately
built candidate tree with the same layout (the candidate path intentionally does
not exist in this deliverable):

```sh
BASELINE_BUILT=/tmp/meownero-wallet-verified-source-20260912
CANDIDATE_BUILT=/tmp/meownero-swarm-demo-candidate-reviewed
test -f "$CANDIDATE_BUILT/build/release/src/crypto/CMakeFiles/obj_cncrypto.dir/keccak.c.o" || exit 1
COMPARISON_ID=$(date +%s)
for group in 1 2 3; do
  slot=0
  for variant in baseline candidate candidate baseline; do
    slot=$((slot + 1))
    case "$variant" in
      baseline) INPUT_BUILT=$BASELINE_BUILT ;;
      candidate) INPUT_BUILT=$CANDIDATE_BUILT ;;
    esac
    bash demos/private-payment/measure.sh "$INPUT_BUILT" \
      "/tmp/meownero-swarm-demo-compare-$COMPARISON_ID-g$group-s$slot-$variant" || exit 1
  done
done
```

The candidate directory must contain the unchanged baseline `hash.c.o` and
fixture, the candidate `keccak.c.o`, and independently reviewed build provenance.
The command serializes and labels all twelve invocations; it does not create a
candidate, perform the differential/constant-time gate, or authorize integration.

For each input length report median ns/call, min/max and batch dispersion for
both variants, plus every raw sample. Define speed factor as `median_A / median_B`
and time reduction as `1 - median_B / median_A`; never interchange the two.
Show lengths separately, with no invented weighted total. A ranking needs a
repeatable effect larger than observed run-to-run variation and correctness and
constant-time review below. A kernel speed factor is not a chain speed factor.

## Correctness and constant-time scope

The public input length may affect execution time. Treat all input bytes and
intermediate Keccak state as potentially secret at each supported fixed length.
No content-dependent branches, memory addresses, loop counts, table indices or
variable-latency arithmetic may be introduced. This contract applies specifically
to x86_64 on the stated CPU and exact GCC/toolchain/flags; it is not a portable
constant-time certification.

Passing 321 known-answer vectors is the measured baseline gate, **not** sufficient
candidate review. Require a separate baseline/candidate differential run over
lengths 0–4096, 16,384 and padding/rate boundaries, all input alignments 0–15,
zero/FF/patterned/random contents, plus canary checks for out-of-bounds writes.
Test all exported functions, including full-state `keccak1600` and permutation
behavior, since other callers use more than the 32-byte digest. Preserve supported
aliasing/length/error behavior. Run sanitizers separately from performance builds.
Inspect optimized disassembly and compare fixed-length input classes with an
appropriate leakage test; timing non-detection does not prove constant time.
Record reviewer scope and unresolved findings. No audit budget or signer choice
is made here. Full daemon/wallet integration remains a separate acceptance gate.

## Submission/result form

```text
Candidate commit and exact allowlisted diff:
Baseline/candidate source tree IDs and object hashes:
Fixture/harness hashes; immutable builder ID; compiler and complete flags:
CPU model/microcode/kernel/affinity; observed load/frequency limitations:
Correctness: vectors, differential cases, full-state APIs, sanitizers (raw logs):
Constant time: architecture/compiler, disassembly review, leakage methodology:
32-byte baseline / candidate median ns per call; all raw batches:
16,384-byte baseline / candidate median ns per call; all raw batches:
A/B/B/A group results, spread and exclusions with reasons:
Speed factors and time reductions (per length):
Integration results; unresolved limitations:
```

Leave candidate fields **not measured** until evidence exists.

## Factual correction from the Monero precedent

The [August 27, 2025 primary contest report](https://www.getmonero.org/2025/08/27/fcmp++-contest-final.html)
describes over 95% improvement to `ec-divisors` construction, affecting transaction
construction. Its separate `helioselene` result is a 22% weighted speedup on an
AMD Ryzen 5600G and 39% weighted WASM cycle improvement. The latter library serves
daemon sync, wallet sync and transaction construction, so improvements can benefit
those components; the percentages are not measured whole-chain gains. The report
also asks for precise code/API boundaries and architecture/toolchain-specific
constant-time requirements. These motivate this draft's rules. None of those
historical figures measures Meownero, proves adoption, or establishes FCMP++
integration or whole-system audit completion.
