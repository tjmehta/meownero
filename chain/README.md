# `chain/` — Meownero node (provisional lineage: Monero v0.18.5.1)

Governed by ADR-001 (PROPOSED). Until it is signed, everything here is a **patch series against an unmodified upstream tag**, so it can be reviewed line by line and discarded without residue.

| File | Purpose |
|---|---|
| `upstream.lock` | upstream URL, tag, commit, and every submodule commit; `build.sh` refuses to build if any differs |
| `patches/0001…0006` | the Meownero delta as reviewable `git am` patches: emission, identity, hard-fork table, trust-surface removal, tests, launch difficulty floor (see `docs/security/code-map.md` for what each touches) |
| `Dockerfile` | Ubuntu 24.04 builder with pinned distro toolchain; the only host dependency is Docker |
| `build.sh` | one command: verify pins → apply series → build `monerod`, `monero-wallet-cli`, `monero-wallet-rpc`, `unit_tests` → run emission tests → print SHA-256s |

```bash
chain/build.sh                # builds into ./build/chain (gitignored)
MEOW_JOBS=8 chain/build.sh    # more parallelism if RAM allows
```

Consensus parameters live in the patches and are specified in `docs/spec/emission.md` and `docs/spec/network-identity.md`. Testing and devnet harnesses currently live in `spikes/candidate-m/` and will move here as they are promoted (M1/M2).

**Upstream tracking rule (PLAN §9.9, 72 h security-merge SLA):** bump `upstream.lock` to the new tag, re-run `build.sh`; any patch that fails `git am` is rebased explicitly in its own commit, never silently.

## Build record

| Date | Series | Result | SHA-256 (monerod / wallet-cli / wallet-rpc) |
|---|---|---|---|
| 2026-09-05 | 0001–0005 | pins verified; 5 patches applied (11 files, +170/−384); build OK; `meow_emission.*` 7/7 | `2fe29c01…eef2de` / `002410b2…6c832e` / `9666c767…9a75b2` |
| 2026-09-05 | 0001–0006 | _pending_ | |

Reproducibility (two builds → identical hashes) is not yet verified; it is a CI step in `.github/workflows/chain.yml` and an M1 exit criterion.
