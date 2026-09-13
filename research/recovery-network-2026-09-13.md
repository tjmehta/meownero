# Network workstream recovery — September 13, 2026

The recovered runner was reviewed and executed for selected 9/90 and fallback
12/120, each from a fresh copy of a reconstructed, pinned source tree. Both
profiles passed the native selection and bounded P2P checks. The source-only path verified the
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
validation, and guarded 9/90 build/test execution. Production patches,
historical evidence, keys and host services remain unchanged.

## Fallback launch checkpoint (superseded by completion below)

After the readiness-corrected selected 9/90 P2P pass, a fresh frozen
`fallback-12-120-run-01` build was started through the guarded source-only
runner. At that checkpoint compilation was active, with no fallback test,
binary or P2P result claimed. Its launcher, frozen scripts, and output directory are retained
separately under `build/recovery-network-20260913/fallback-12-120-run-01/`.

## Fallback completion

The existing fallback run completed with `build.exit=0`, `offline.exit=0`,
`dns.exit=0`, and `container.exit=0` in
`build/recovery-network-20260913/fallback-12-120-run-01/output/`. Consensus,
difficulty, and floor selections passed 24, 10, and 10 tests. The exact native
CI union passed 1,237/1,237 tests: 1,228 offline and 9 DNS-only tests using
ordinary bridge networking. The final receipt is `output/result.json`; source,
overlay, binary, version, package, cgroup, and XML receipts remain beside it.

The direct fallback P2P run used the readiness-corrected harness without a
second guard wrapper. It used a fresh empty `p2p/work` child and captured an
external subprocess return code of 0 in
`build/recovery-network-20260913/fallback-12-120-run-01/p2p/subprocess.json`.
Its durable log is
`research/evidence/recovery-network-2026-09-13/fallback-12-120-p2p-01.log`;
the work directory contains PASS result, events, resources, and daemon logs.
Warmup, connected relay, partition/rejoin, malformed transport rejection, and
12/120 issuance checks passed. This remains accelerated empty-block P2P
evidence, with no loaded-capacity, FCMP, or launch-readiness claim.

The coordinator independently verified all five executable hashes, regenerated
the exact native XML union, and matched the P2P daemon hash to the native build
receipt. Both P2P daemons exited 0; peak usage was 614,367,232 bytes under the
original 1.5 GiB cap, with no memory-limit or OOM events. The depth-three reorg
and healthy relay after malformed transport rejection passed.

Durable [native receipts](evidence/recovery-network-2026-09-13/fallback-12-120-native/)
and [P2P receipts](evidence/recovery-network-2026-09-13/fallback-12-120-p2p-pass/)
include raw logs, XML, phase exits, binary hashes and resource records.
`fallback-SHA256SUMS` covers these artifacts and the coordinator's final review.
Both recovered network assignments are complete at this bounded checkpoint;
selected-family reproduction pairs, wallet/fee/aggregate integration and the
matched-capacity intended-cryptography workload remain open.
