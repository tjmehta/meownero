# `chain/` — Meownero node (provisional lineage: Monero v0.18.5.1)

Governed by ADR-001 (PROPOSED). Until it is signed, everything here is a **patch series against an unmodified upstream tag**, so it can be reviewed line by line and discarded without residue.

| File | Purpose |
|---|---|
| `upstream.lock` | upstream URL, tag, commit, and every submodule commit; `build.sh` refuses to build if any differs |
| `patches/0001…0008` | reviewable `git am` patches: emission, identity, hard-fork table, trust-surface removal, tests, launch difficulty floor, v16 protocol fixture, and startup/genesis/recalculation floor coverage (see `docs/security/code-map.md`) |
| `Dockerfile` | Ubuntu 24.04 builder; base-image digest and package versions are not yet pinned (M1 gap); the only host dependency is Docker |
| `build.sh` | verify pins → apply series → build daemon, wallets and both test targets → run consensus/protocol and floor checks → print SHA-256s |
| `test-difficulty.sh` | run eight floor cases plus inherited hash test at floor 1 and separately compiled 150M; requires `unit_tests` and `meow_difficulty_floor_tests` built first; read-only source mount |

```bash
chain/build.sh                # fresh ./build/chain (gitignored), two compiler jobs
MEOW_JOBS=8 chain/build.sh /tmp/meow-build  # fresh workdir; more jobs only if RAM allows
```

Consensus parameters live in the patches and are specified in `docs/spec/emission.md` and `docs/spec/network-identity.md`. Testing and devnet harnesses currently live in `spikes/candidate-m/` and will move here as they are promoted (M1/M2).

**Upstream tracking rule (PLAN §9.9, 72 h security-merge SLA):** bump `upstream.lock` to the new tag, re-run `build.sh`; any patch that fails `git am` is rebased explicitly in its own commit, never silently.

## Current verification

2026-09-07: all eight patches apply cleanly to the pinned tag and produce the tested source tree (`aa6c75f0aec359d17884c24496bd07403e993cf1`). Incremental build and focused consensus/protocol tests pass (18/18); floor variants each pass 9/9, including core initialization and recalculation. The broader suite still has 20 recorded identity/wallet-fixture failures; see [`research/verification-2026-09-07-m1.md`](../research/verification-2026-09-07-m1.md). The artifact hashes below describe the earlier six-patch build, not the current eight-patch series.

## Build record

| Date | Series | Result | SHA-256 (monerod / wallet-cli / wallet-rpc) |
|---|---|---|---|
| 2026-09-05 | 0001–0005 | pins verified; 5 patches applied (11 files, +170/−384); build OK; `meow_emission.*` 7/7 | `2fe29c01…eef2de` / `002410b2…6c832e` / `9666c767…9a75b2` |
| 2026-09-06 | 0001–0006 (single-jump HF table) | fresh upstream clone; all pins verified; 6 patches applied (14 files, +184/−385); build OK; `meow_*` 8/8 | `7917ce98…4c8ac9` / `8fca7a8a…1b519d` / `b1761545…db3f1` |

Full hashes and devnet/regression results: [`research/verification-2026-09-06-m1.md`](../research/verification-2026-09-06-m1.md). The fresh build used the existing builder image and shared ccache; it is not independent reproducibility evidence.

Reproducibility (two independent builds → identical hashes) is not yet verified. The current `.github/workflows/chain.yml` step only removes binaries and relinks existing objects; replace that with independent builds before marking the M1 criterion complete. Image digest/package pinning is also outstanding.
