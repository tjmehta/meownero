# `chain/` — Meownero node (provisional lineage: Monero v0.18.5.1)

Governed by ADR-001 (PROPOSED). Until it is signed, everything here is a **patch series against an unmodified upstream tag**, so it can be reviewed line by line and discarded without residue.

| File | Purpose |
|---|---|
| `upstream.lock` | upstream URL, tag, commit, and every submodule commit; `build.sh` refuses to build if any differs |
| `patches/0001…0005` | the Meownero delta as reviewable `git am` patches: emission, identity, hard-fork table, trust-surface removal, tests (see `docs/security/code-map.md` for what each touches) |
| `Dockerfile` | Ubuntu 24.04 builder with pinned distro toolchain; the only host dependency is Docker |
| `build.sh` | one command: verify pins → apply series → build `monerod`, `monero-wallet-cli`, `monero-wallet-rpc`, `unit_tests` → run emission tests → print SHA-256s |

```bash
chain/build.sh                # builds into ./build/chain (gitignored)
MEOW_JOBS=8 chain/build.sh    # more parallelism if RAM allows
```

Consensus parameters live in the patches and are specified in `docs/spec/emission.md` and `docs/spec/network-identity.md`. Testing and devnet harnesses currently live in `spikes/candidate-m/` and will move here as they are promoted (M1/M2).

**Upstream tracking rule (PLAN §9.9, 72 h security-merge SLA):** bump `upstream.lock` to the new tag, re-run `build.sh`; any patch that fails `git am` is rebased explicitly in its own commit, never silently.
