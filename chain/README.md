# `chain/` — Meownero node (provisional lineage: Monero v0.18.5.1)

Governed by ADR-001 (PROPOSED). Until it is signed, everything here is a **patch series against an unmodified upstream tag**, so it can be reviewed line by line and discarded without residue.

| File | Purpose |
|---|---|
| `upstream.lock` | upstream URL, tag, commit, and every submodule commit; `build.sh` refuses to build if any differs |
| `patches/0001…0015` | reviewable `git am` patches: emission, identity, hard-fork table, trust-surface removal, tests, launch difficulty floor, v16 protocol fixture, startup/genesis/recalculation coverage, address/URI fixtures, opt-in authority/donation disabling, sparse-fork wallet compatibility and difficulty boundary tests (see `docs/security/code-map.md`) |
| `test-authorities.sh` | isolated RPC update, DNS-blocklist opt-in, local-ban and disabled-donation checks; requires built daemon and CLI wallet; called by `build.sh` |
| `test-seed-recovery.sh` | isolated seed restore with exact address/history/balance and reopen assertions; run with `bash` |
| `test-reorg.sh` | competing branches, restart and invalid-block checks; regtest and native-DAA window modes |
| `benchmark-difficulty.sh` | matched-issuance native-DAA models; explicitly not a full peer-network benchmark |
| `test-network-loaded.sh` | loaded matched 90 s/120 s P2P probe: real wallet-rpc RingCT load, competing blocks, partition/reorg, confirmation latency; same heavy lock and 5 GiB/1.5 GiB/no-swap/2-CPU guards as `test-network-p2p.sh`; fixed difficulty, no FCMP, capacity not normalized; see `research/loaded-network-2026-09-15.md` |
| `Dockerfile` | Ubuntu 24.04 base pinned by digest; apt package versions are not yet pinned (M1 gap); Docker is the host build dependency |
| `build.sh` | verify pins → apply series → build daemon, wallets and both test targets → run consensus/protocol and floor checks → print SHA-256s |
| `test-difficulty.sh` | run nine floor cases plus inherited hash test at floor 1 and separately compiled 150M; requires `unit_tests` and `meow_difficulty_floor_tests` built first; read-only source mount |

```bash
chain/build.sh                # fresh ./build/chain (gitignored), two compiler jobs
MEOW_JOBS=8 chain/build.sh /tmp/meow-build  # fresh workdir; more jobs only if RAM allows
```

Consensus parameters live in the patches and are specified in `docs/spec/emission.md` and `docs/spec/network-identity.md`. Testing and devnet harnesses currently live in `spikes/candidate-m/` and will move here as they are promoted (M1/M2).

**Upstream tracking rule (PLAN §9.9, 72 h security-merge SLA):** bump `upstream.lock` to the new tag, re-run `build.sh`; any patch that fails `git am` is rebased explicitly in its own commit, never silently.

## Current verification

**September 13 recovery:** [current workstream index](../research/recovery-index-2026-09-13.md).
Historical clean15 reproduction is complete. After recovery of seven earlier
native-test failures, fresh 9/90 and 12/120 builds each pass all 1,237 selected
native tests with the original three exclusions. Selected P2P relay and
partition/rejoin/reorg checks also pass for both profiles. The original temporary builds are absent. The
checkpoints below retain their historical scope; the selected test pass does not
establish launch readiness.

**2026-09-12:** the **thirteen-patch** clean reproduction passed: all three binary
hashes match across two fresh cache-disabled builds in the same immutable image.
Provenance and hashes are in the [foundation report](../research/verification-2026-09-12-m1.md).
Clean fifteen-patch reproduction subsequently passed, as recorded in the
[clean15 report](../research/verification-2026-09-12-clean15.md).
Independent toolchain reconstruction remains open.

**Fifteen-patch implementation:** patch 0014 fixes live wallet refresh against the
sparse `{v1@0, v16@1}` table; seed restoration now verifies address, 130 coinbase
history entries, exact total/unlocked balances and reopen. Patch 0015 exercises
real difficulty callers, recalculation and rollback across the window/lag boundaries;
**10/10 tests pass at each floor, 1 and 150M**. Production floor stays 1.
Full local CI selection passes **1,237/1,237 in 79.174 s**, retaining only the
three historical exclusions. Historical fixture bytes and production genesis
checks remain intact. Fresh patch application matches tested tree
`4db958cb96d72943c5c2433bd5f4a8f730037148`.

The builder/devnet mismatch is fixed; three-node supply/tip checks, all runner
shellchecks and workflow syntax checks pass. Actual daemon reorg/rejection tests
and 720 native-DAA modeled scenarios are documented in the
[M2 report](../research/verification-2026-09-12-m2.md). Full network performance,
private-transaction recovery, long alternative chains and sustained uptime remain
open. No timing or floor decision is made. Remote CI status is not verified here;
TJ's private snapshot publication does not authorize future pushes.

### Historical intermediate selections (superseded above)

2026-09-07: all nine patches apply cleanly to the pinned tag and produce the tested source tree (`96dbf344ae63e9772d4330fa47d33e99fb0d49ed`). Address/URI and consensus/protocol selection passes 278/278; the eight-patch floor variants each passed 9/9. Patch 0009 fixes the inherited address and fourteen URI failures without production validation changes. The broader offline selection remains non-green: six historical wallet/serialization failures and six DNS-dependent failures (1,212/1,224 passed). See [`research/verification-2026-09-07-m1.md`](../research/verification-2026-09-07-m1.md). The historical build record below retains the earlier hashes; the reproducibility section records the verified **eight-patch** hashes, not patch 0009.

Patch 0010 follow-up: all ten patches apply cleanly and match tested tree `1e7f5e4347968c8824b4fe4284ccc6db298e42fb`. Rebuild passed; targeted regressions pass 280/280, raised-floor tests 9/9, and `test-authorities.sh` passes. Explicit update modes fail closed, DNS-blocklist opt-in is ignored with a warning, and `donate` is disabled on all networks. Local bans remain usable. No replacement authority/address is configured. The eight-patch reproducibility record remains historical and is not extended to these new binaries.

Patch 0011 follow-up: five multisig testnet address vectors are corrected with the original keys/assertions retained. All seven multisig cases pass; combined regression selection **287/287**. CI no longer excludes multisig. Fresh eleven-patch application matches tested tree `cd8fa65fe527556e7d9b4996fdf84b9f57a492ae`. The broader offline run passes **1,221/1,233**, with the same six wallet/serialization and six DNS-dependent failures. This does not extend the eight-patch binary reproducibility claim.

## Build record

| Date | Series | Result | SHA-256 (monerod / wallet-cli / wallet-rpc) |
|---|---|---|---|
| 2026-09-05 | 0001–0005 | pins verified; 5 patches applied (11 files, +170/−384); build OK; `meow_emission.*` 7/7 | `2fe29c01…eef2de` / `002410b2…6c832e` / `9666c767…9a75b2` |
| 2026-09-06 | 0001–0006 (single-jump HF table) | fresh upstream clone; all pins verified; 6 patches applied (14 files, +184/−385); build OK; `meow_*` 8/8 | `7917ce98…4c8ac9` / `8fca7a8a…1b519d` / `b1761545…db3f1` |

Full hashes and devnet/regression results: [`research/verification-2026-09-06-m1.md`](../research/verification-2026-09-06-m1.md). The fresh build used the existing builder image and shared ccache; it is not independent reproducibility evidence.

## Reproducibility

**Latest verified checkpoint, September 12:** [two clean fifteen-patch builds
match](../research/verification-2026-09-12-clean15.md), including all daemon/wallet
hashes and source/input/package/version receipts. This is the historical 0.9/120
family in one immutable builder image. [Selected-profile recovery](../research/recovery-index-2026-09-13.md)
is a separate incomplete check. Earlier reproduction records below remain historical.

`build.sh` applies patches with deterministic committer dates and builds with `ARCH=default` (upstream's no-`-march` baseline) rather than the host-native CPU. It resolves the builder to an immutable image ID for every invocation and records `BUILDER_IMAGE_ID` plus a complete `packages.txt` manifest next to hashes. Set `MEOW_BUILDER_IMAGE` to use an existing image rather than rebuilding the recipe; `CCACHE_DISABLE=1` is forwarded into the compiler environment.

```bash
MEOW_JOBS=2 bash chain/test-reproducibility.sh /tmp/meow-independent-builds
```

The script creates two separate source/build trees, uses one immutable builder image, disables ccache reuse for both compilations, runs the focused tests in both and compares image identity, package manifests and binary hashes. CI now invokes this instead of merely relinking existing objects. Two independent patch applications produced identical commit `8c82c0fb55d5e8fa6743884e321a23738397683d` in a local metadata check.

**Verified 2026-09-07 — same-host fixed-image reproducibility, patches 0001–0008:** two fresh source/build trees at `/tmp/meownero-repro-20260907-CDD1jq/{first,second}` compiled with ccache disabled. Both builds and their focused tests passed; the complete comparison harness exited 0. All three binary hashes, package manifests and generated `version.cpp` files match.

| Provenance | Value (both builds) |
|---|---|
| Upstream commit | `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5` |
| Applied series HEAD | `8c82c0fb55d5e8fa6743884e321a23738397683d` |
| Series VERSIONTAG | `8c82c0fb5` |
| BUILDER_IMAGE_ID | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| packages.txt SHA-256 | `769dbcd72bac1dd528f5bd1833da29e0b788fdc50d9dee23791148ef6e6cd8d9` |
| Architecture setting | `ARCH=default` |

| Binary | SHA-256 (identical in both trees) |
|---|---|
| `monerod` | `cd880b033e8716e3ef052700a232f149e71784c9186da1332e27234f464891f5` |
| `monero-wallet-cli` | `4eb0645dd8e5c339a09cec483c276fa2cf9b170f535410c824a5e15540a87be7` |
| `monero-wallet-rpc` | `8fca2fc2b992da45c86f5819e060c3a2fa53e347c1ae25d4db1d503c557ca37c` |

All three second-tree binaries also exited 0 with `--help` inside the exact builder image, with networking disabled and a read-only source mount. That establishes startup/loader smoke coverage only, not cross-hardware portability or unchanged RandomX performance. These hashes cover the eight-patch series, not subsequent patches.

Independent toolchain reconstruction remains **open**: apt versions/repository snapshots are unpinned. This result does not establish cross-host or cross-hardware reproduction, a green full upstream suite, or an audit.

## Parallel local engineering checkpoint

The [integrated September 12 handoff](../research/handoff-2026-09-12-swarm.md)
links actual P2P partition/rejoin, strict wallet startup/observer tests, a private
received-payment recovery demo, and source-pinned P2Pool/Cuprate probes. The
fifteen production patches and preserved seed success remain unchanged.

`chain/test-network-p2p.sh` measures bounded empty-block P2P behavior.
`chain/privacy-test.sh` checks selected wallet transport and response paths;
OpenAlias can still issue DNS despite `--no-dns`. The new demo, privacy and module
runners are local fixtures tied to the recorded builder/source; CI lints them,
but their full runtime suites have not been wired into or run on remote CI.

`chain/test-reproducibility.sh` now also compares source/submodule/input/version
receipts and omits the shared cache mount when disabled. Optional
`MEOW_REPRO_BUILD_RUNNER` selects a guard such as `chain/network-build-guard.sh`.
The existing clean-fifteen waiter is preserved; do not start a duplicate or remove
its worktree. It has not compiled while host RAM remains below its gate.
Actual matched-capacity 90/120 and integrated FCMP benchmarks remain open; the
[readiness inventory](../spikes/network-benchmark/README.md) reports blockers.
