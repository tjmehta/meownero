# `chain/` — Meownero node (provisional lineage: Monero v0.18.5.1)

Governed by ADR-001 (PROPOSED). Until it is signed, everything here is a **patch series against an unmodified upstream tag**, so it can be reviewed line by line and discarded without residue.

| File | Purpose |
|---|---|
| `upstream.lock` | upstream URL, tag, commit, and every submodule commit; `build.sh` refuses to build if any differs |
| `patches/0001…0008` | reviewable `git am` patches: emission, identity, hard-fork table, trust-surface removal, tests, launch difficulty floor, v16 protocol fixture, and startup/genesis/recalculation floor coverage (see `docs/security/code-map.md`) |
| `Dockerfile` | Ubuntu 24.04 base pinned by digest; apt package versions are not yet pinned (M1 gap); Docker is the host build dependency |
| `build.sh` | verify pins → apply series → build daemon, wallets and both test targets → run consensus/protocol and floor checks → print SHA-256s |
| `test-difficulty.sh` | run eight floor cases plus inherited hash test at floor 1 and separately compiled 150M; requires `unit_tests` and `meow_difficulty_floor_tests` built first; read-only source mount |

```bash
chain/build.sh                # fresh ./build/chain (gitignored), two compiler jobs
MEOW_JOBS=8 chain/build.sh /tmp/meow-build  # fresh workdir; more jobs only if RAM allows
```

Consensus parameters live in the patches and are specified in `docs/spec/emission.md` and `docs/spec/network-identity.md`. Testing and devnet harnesses currently live in `spikes/candidate-m/` and will move here as they are promoted (M1/M2).

**Upstream tracking rule (PLAN §9.9, 72 h security-merge SLA):** bump `upstream.lock` to the new tag, re-run `build.sh`; any patch that fails `git am` is rebased explicitly in its own commit, never silently.

## Current verification

2026-09-07: all eight patches apply cleanly to the pinned tag and produce the tested source tree (`aa6c75f0aec359d17884c24496bd07403e993cf1`). Incremental build and focused consensus/protocol tests pass (18/18); floor variants each pass 9/9, including core initialization and recalculation. The broader suite still has 20 recorded identity/wallet-fixture failures; see [`research/verification-2026-09-07-m1.md`](../research/verification-2026-09-07-m1.md). The historical build record below retains the earlier hashes; the reproducibility section records the verified eight-patch hashes.

## Build record

| Date | Series | Result | SHA-256 (monerod / wallet-cli / wallet-rpc) |
|---|---|---|---|
| 2026-09-05 | 0001–0005 | pins verified; 5 patches applied (11 files, +170/−384); build OK; `meow_emission.*` 7/7 | `2fe29c01…eef2de` / `002410b2…6c832e` / `9666c767…9a75b2` |
| 2026-09-06 | 0001–0006 (single-jump HF table) | fresh upstream clone; all pins verified; 6 patches applied (14 files, +184/−385); build OK; `meow_*` 8/8 | `7917ce98…4c8ac9` / `8fca7a8a…1b519d` / `b1761545…db3f1` |

Full hashes and devnet/regression results: [`research/verification-2026-09-06-m1.md`](../research/verification-2026-09-06-m1.md). The fresh build used the existing builder image and shared ccache; it is not independent reproducibility evidence.

## Reproducibility

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
