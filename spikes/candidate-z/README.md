# Candidate Z control — Zebra v6.3.0 + Meownero delta

Feasibility only, never security (PLAN.md §2.3). Upstream pin: `ZcashFoundation/zebra` `v6.3.0` (commit `d1fd7ad`, 2026-09-04), Rust toolchain 1.91.0 per `rust-toolchain.toml`.

## What the delta does (`apply.py`, exported as `meownero-z-v6.3.0.diff`)

| Area | Change | Files |
|---|---|---|
| Emission | `block_subsidy` returns the constant `MEOW_BLOCK_SUBSIDY` = 90,000,000 zatoshi (0.9 coin at 8 dp) for every height ≥ 1; genesis 0; halving/slow-start code unreachable | `parameters/network/subsidy.rs`, `subsidy/constants.rs` |
| Supply bound | `MAX_MONEY` raised from 21M to 46B coin (largest value keeping upstream's `2 * MAX_MONEY` test arithmetic inside i64): perpetual issuance crosses Zcash's cap after ~88 years at 120 s, after which every value-pool check would fail | `amount.rs` |
| Mandatory privacy | new consensus check `mandatory_shielded`: non-coinbase transactions may have no transparent inputs or outputs; coinbase transparent outputs must be zero-value (subsidy goes to a shielded receiver per ZIP-213). Wired into `check_structure_and_network_rules` so it applies to blocks and mempool | `transaction/check.rs`, `transaction.rs`, `error.rs` |
| Block time | `POST_BLOSSOM_POW_TARGET_SPACING` 75 → 120 s (working value) | `parameters/network_upgrade.rs` |
| Tests | `meow_tests` (subsidy invariants, supply fits `MAX_MONEY`, no funding streams on the control network); `meow_mandatory_shielded` (rule restated independently and checked against every transaction in the upstream mainnet/testnet block vectors; transparent coinbase rejected) | `subsidy.rs`, `transaction/tests.rs` |

Not changed: identity (the control runs on Zebra's **Regtest** network because Zebra cannot generate genesis blocks; a Meownero genesis, magic, name and address prefixes are an M1 task); PoW (Equihash inherited, PoW disabled on Regtest; RandomX integration is the E5 scope item and is **not** built); funding streams and lockbox (empty by Regtest configuration, would be a code delta on a real fork); wallet.

## Build (no sudo; user-space toolchain)

```bash
python3 -m venv .venv && .venv/bin/pip install cmake libclang
export PATH=$PWD/.venv/bin:$PATH
export LIBCLANG_PATH=$PWD/.venv/lib/python3.*/site-packages/clang/native
export BINDGEN_EXTRA_CLANG_ARGS="-I/usr/lib/gcc/x86_64-linux-gnu/13/include"   # gcc builtin headers for rocksdb bindgen
git clone --depth 1 https://github.com/ZcashFoundation/zebra.git && cd zebra && git checkout d1fd7ad
python3 ../spikes/candidate-z/apply.py .
cargo build --release -p zebrad --features internal-miner
```

## Run (single node, Regtest identity, NU6.3 rules from height 1)

`zebrad.toml`:

```toml
[network]
network = "Regtest"
[network.testnet_parameters.activation_heights]
"NU6.3" = 1
[mining]
miner_address = "uregtest1efxggx6…"   # Zebra's default Regtest unified address (Sapling+Orchard receivers)
[rpc]
listen_addr = "127.0.0.1:19332"
enable_cookie_auth = false
```

Mine with the Regtest `generate` RPC (Zebra's internal miner is disabled upstream, issue #8180):

```bash
curl -s -X POST -H 'content-type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"generate","params":[10]}' http://127.0.0.1:19332
curl -s -X POST -H 'content-type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"getblockchaininfo","params":[]}' http://127.0.0.1:19332
```

Adversarial run: the same config with a transparent `miner_address` (`tmJymvcUCn1ctbghvTJpXBwHiMEB8P6wxNV`) must fail to produce blocks with `TransparentValueForbidden`.

## Baseline observation (unpatched zebrad, same config)

Three blocks mined; every coinbase is a v6 transaction with an Ironwood output and zero transparent outputs; `getblockchaininfo` value pools: transparent 0, sapling 0, orchard 0, ironwood 18.75 (3 × 6.25 Regtest subsidy). So ZIP-213 shielded coinbase into the Ironwood pool works in stock Zebra 6.3.0, and a mandatory-shielded chain needs no transparent-coinbase carve-out (confirms E2 §3a).

## Patched run (2026-09-05, zebrad 6.3.0 + delta, Regtest, NU6.3 at height 1)

`generate 10` succeeded. Per-block observation via `getblock <h> 2`:

| height | coinbase version | transparent vout | transparent value | Ironwood output | block size (bytes) |
|---|---|---|---|---|---|
| 0 (Regtest genesis) | 1 | 1 | 0 | no | 382 |
| 1 | 6 | 0 | 0 | yes | 7,579 |
| 2 … 10 | 6 | 0 | 0 | yes | 7,579 |

`getblockchaininfo` value pools after 10 blocks: transparent 0, sprout 0, sapling 0, orchard 0, lockbox 0, **ironwood 9.00000000** (`chainValueZat` 900,000,000 = 10 × 90,000,000). Supply equals height × 0.9 exactly; genesis contributed 0.

Adversarial run (same binary, `miner_address` = transparent `tmJymvcUCn1ctbghvTJpXBwHiMEB8P6wxNV`): `generate 1` returned `{"error":{"code":-1,"message":"block was rejected: Rejected"}}` and the node log shows `submit block failed verification error=Ok(Block { source: Transaction(TransparentValueForbidden) })`. The rule bites at block validation, before the block enters the state.

Measured facts for ADR-001:
- An empty block carrying only an Ironwood shielded coinbase is **7,579 bytes** (the coinbase proof); a Candidate M coinbase-only block is a few hundred bytes. This is the per-block floor for propagation/validation on the Z path.
- Stock Zebra 6.3.0 already routes the coinbase to the Ironwood pool at NU6.3 from a unified miner address, so the mandatory-shielded chain needs no template changes and no transparent-coinbase exception.
- Delta size: 8 files, 250 diff lines, of which the consensus-bearing lines are one constant (subsidy), one constant (spacing), one bound (`MAX_MONEY`) and one 12-line check plus its wiring.

