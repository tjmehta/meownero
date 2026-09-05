# Stage 2 control prototypes (M0-S2)

**Feasibility only, never security** (PLAN.md §2.3). Nothing here is promoted; the selected lineage gets a fresh M1 layout from the pinned tag with these diffs re-derived as a reviewable patch series.

| Control | Upstream pin | Delta script | Diff | Build | Run |
|---|---|---|---|---|---|
| Candidate M | monero-project/monero `v0.18.5.1` (`4f92268`, 2026-06-30) | `candidate-m/apply.py` | `candidate-m/meownero-m-v0.18.5.1.diff` | `candidate-m/README.md` (Docker builder) | `candidate-m/devnet.sh` |
| Candidate Z | ZcashFoundation/zebra `v6.3.0` (`d1fd7ad`, 2026-09-04) | `candidate-z/apply.py` | `candidate-z/meownero-z-v6.3.0.diff` | `candidate-z/README.md` (native, user-space toolchain) | `candidate-z/README.md` |

Both controls implement the same binding parameters: perpetual flat subsidy of 0.9 coin per block, genesis pays 0, 120-second target spacing, mandatory privacy, no funding streams, no premine.

## Measurements

Filled in from the actual runs; see each control's README for the raw commands and outputs.

| Axis (PLAN §5.4 / §2.2) | Candidate M | Candidate Z |
|---|---|---|
| Files touched for the consensus delta | _pending_ | _pending_ |
| Diff size (lines) | _pending_ | _pending_ |
| Consensus invariants touched | _pending_ | _pending_ |
| Mandatory privacy | inherited (RingCT/CLSAG since HF 6/13); zero delta | new consensus rule + ZIP-213 shielded coinbase; delta measured |
| Emission integration | `get_block_reward` constant; penalty math inherited | `block_subsidy` constant; `MAX_MONEY` raised; funding streams off by config |
| Identity (name/magic/ports/prefixes/genesis) | done in delta | **not done** (runs on Regtest identity; genesis generator is an M1 task) |
| PoW | RandomX inherited | Equihash inherited; RandomX integration **not built** (E5 scope estimate only) |
| Boots + mines 0.9/block | _pending_ | _pending_ |
| Follower nodes sync | _pending_ (3 nodes) | n/a on Regtest (single node; multi-node needs custom testnet + genesis) |
| Adversarial: transparent value rejected | n/a (no transparent type exists) | _pending_ |
| Emission unit tests | `tests/block_reward.cpp` | `meow_tests` in `subsidy.rs`, `meow_mandatory_shielded` in `transaction/tests.rs` |
| Upstream tests broken by the delta | _pending_ | _pending_ |
| Validation cost / block | _pending_ | _pending_ |
| Maintenance surface (upstream velocity) | C++; 0.18.x LTS line; FCMP++ rewrite pending upstream | Rust; ~weekly releases; NU7 in flight |
| Audit burden (rubric lines b–d) | gadget layer: none inherited beyond CLSAG/BP+; FFI: none | halo2/Ironwood gadget layer inherited; Tachyon proof scope (E1 §4) |

## Toolchain notes

- No sudo on the build host. Monero builds in a Docker image (`candidate-m/Dockerfile`); Zebra builds natively with cmake and libclang from a Python venv plus `BINDGEN_EXTRA_CLANG_ARGS` pointing at gcc's builtin headers (`candidate-z/README.md`).
- RAM on the host is constrained (about 3 GB free); builds run with 3 jobs.
