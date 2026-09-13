# Network workstream recovery — September 13, 2026

The recovered selected runner was reviewed and executed once for selected 9/90
from a reconstructed, pinned source tree. The source-only path verified the
historical HEAD/tree, clean recursive submodules, and frozen source manifest
before copying. It refused inherited build output and dirty or mismatched
fixture inputs. Economic, approved emission, and source-locked gamma overlays
were applied only to the disposable copy.

## Verification evidence

- `research/evidence/recovery-network-2026-09-13/recovered-verification.json`
  verifies all 39 recovered commit/hash records; recovered evidence remains
  byte-identical where the original file was available.
- `research/evidence/recovery-network-2026-09-13/gamma-probe-01/summary.json`
  records the literal pinned picker and original crypto RNG probe. Conversion
  alone failed 8/16 controls; preserving the original wallclock horizon and
  drawing 1,000,000 samples passed 16/16 for both 9/90 and 12/120. This is a
  fixture diagnosis, not a wallet, cryptography, capacity, or FCMP certification.
- `runner-validation-02.log` records source staging, exact overlay reversal,
  refusal paths, direct `--locked` guard rejection, wait validation, and six
  synthetic Docker/tee phase-exit cases. The guard's exported `docker()` wrapper
  supplies `--memory=4g --memory-swap=4g --cpus=2`; no redundant runner limits
  are needed. The shell runner suppresses SC2317 only for its indirect EXIT trap.

## Selected 9/90 build checkpoint

Launch receipt: `build/recovery-network-20260913/selected-9-90-launch-01/`
(`launcher.json`, frozen input hashes, driver log/PID/exit, and copied evidence
are also retained under `research/evidence/recovery-network-2026-09-13/`). The
guard passed with approximately 5.7 GiB available RAM at launch. The build and
both test containers terminated cleanly with final `build.exit=0` and
`container.exit=0`; no network build container remains live.

The selected copy compiled the daemon, CLI wallet, wallet RPC,
`unit_tests`, and `meow_difficulty_floor_tests` with one compiler job. Consensus,
difficulty, and floor selections passed 24, 10, and 10 tests. The unchanged CI
native selection passed all 1,237 tests: 1,228 in the offline partition and 9
DNS cases in a separate bridge-network container. The partition merger required
an exact, disjoint union of the original GTest list and rejected failures,
skips, duplicates, missing, and extra cases.

The offline build and non-DNS tests use `--network none`. The DNS-only phase uses
ordinary bridge networking, matching `.github/workflows/chain.yml`, with no
published ports and only the existing public fixtures (`example.com`,
`example.invalid`, `dnssec-failed.org`, and Monero donation records). No custom
DNS infrastructure or runtime service was added.

The receipt is explicitly a fresh selected source build, not a clean15
reproduction or preserved historical build. Historical source provenance is
preserved; capacity normalization, loaded-network performance, FCMP,
wallet/RPC authority and launch readiness remain unverified. The coordinator
verified the five executable hashes and exact native XML coverage independently.
[Complete selected native receipts](evidence/recovery-network-2026-09-13/selected-9-90-native/)
are now retained in the repository. The P2P continuation below passed; fallback
12/120 proceeds as a separate gated run.

## P2P gate result

The first selected 9/90 P2P attempt is archived at
`build/recovery-network-20260913/selected-9-90-launch-01/p2p/` with its durable
log at `research/evidence/recovery-network-2026-09-13/selected-9-90-p2p-01.log`.
The RPC response lacked `blocks`, so the harness stopped before block
generation. The first exit-capture file contains only a newline; it does **not**
establish exit 0. Successful daemon shutdown in Python's `finally` block does
not suppress the original exception. The first response body was not captured,
so its precise status is unavailable.

Both daemons logged an allocation exception, but peak cgroup usage was
599,232,512 bytes and all limit/OOM counters were zero. Address-to-symbol
resolution places the trace in RandomX cache allocation; the pinned code tries
large pages and then ordinary allocation. A cap-induced failure was therefore
not established, and the memory cap was retained.

The pinned `generateblocks` RPC returns a successful JSON-RPC envelope with
`status=BUSY` and no block list until the core reports synchronized. The harness
previously waited only for an HTTP/RPC response. It now starts both peers, waits
up to 30 seconds for both `get_info.synchronized` values, and includes the
actual response in any missing-block failure. No spending request is blindly
retried and no consensus assertion changes.

Retry setup failures (nonempty output directory and nested acquisition of the
same heavy lock) were preserved separately and did not execute the P2P test.
The correctly launched fourth retry used the wrapper's own resource checks,
frozen harness files and a fresh work directory. It returned **0**, with a
`PASS` result: twelve relayed block samples, partition/rejoin with a depth-three
reorg, malformed transport rejection, and healthy subsequent relay. Both
daemons shut down cleanly; peak usage was 646,606,848 bytes under the unchanged
1.5 GiB/no-swap/two-CPU cap, with no limit/OOM events.

[Passing P2P result, resources, events and logs](evidence/recovery-network-2026-09-13/selected-9-90-p2p-pass/)
were archived and reviewed by the coordinator. This is accelerated empty-block,
fixed-difficulty correctness evidence, not loaded-network or FCMP performance.

Validation performed: shell syntax, Python AST parsing, capped 512 MiB runner
validation, and guarded 9/90 build/test execution. No production patches,
historical evidence, keys, host services, or shared documents were modified.

## Fallback status (live checkpoint)

After the readiness-corrected selected 9/90 P2P pass, a fresh frozen
`fallback-12-120-run-01` build was started through the guarded source-only
runner. Compilation is still active; no fallback test, binary, or P2P result is
claimed yet. Its launcher, frozen scripts, and output directory are retained
separately under `build/recovery-network-20260913/fallback-12-120-run-01/`.
