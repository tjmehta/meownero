# Candidate M control — Monero v0.18.5.1 + Meownero delta

Feasibility only, never security (PLAN.md §2.3). Upstream pin: `monero-project/monero` tag `v0.18.5.1` (commit `4f92268`, 2026-06-30) with submodules randomx `6c4340b`, rapidjson `129d19b`, supercop `633500a`, trezor-common `bff7fdf`.

## What the delta does (`apply.py`, exported as `meownero-m-v0.18.5.1.diff`)

| Area | Change | Files |
|---|---|---|
| Emission | `get_block_reward` returns the constant `MEOW_BLOCK_REWARD` = 900,000,000,000 atomic (0.9 MEOW at 12 dp) for every hard-fork version and supply level; block-weight penalty math untouched | `cryptonote_basic_impl.cpp`, `cryptonote_config.h` |
| Genesis | reward forced to 0 at height 0 on both the template side (`construct_miner_tx`) and the validation side (`validate_miner_transaction`); genesis coinbase blob has one output of amount 0 | `cryptonote_tx_utils.cpp`, `blockchain.cpp`, `cryptonote_config.h` |
| Hard forks | `{v1 @ 0, v16 @ 1}` single jump (regtest precedent); the control's first table (v1..v16 at heights 1..16) burned the first blocks' plaintext coinbases and broke P2P handshakes for ten heights — caught by the upstream `race_condition` unit test; testnet/stagenet tables left as upstream (unused) | `hardforks.cpp` |
| Identity | `CRYPTONOTE_NAME` "meownero"; network IDs = sha256("meownero-<net>-network-id-v1")[0:16]; ports 19080/19081/19082 (testnet 29xxx, stagenet 39xxx); base58 prefixes 120/121/123 → addresses start with `M` (testnet 156/157/158 → `T`, stagenet 150/151/152 → `S`) | `cryptonote_config.h` |
| Trust surfaces removed | no hardcoded checkpoints, no embedded block-hash blobs, no DNS checkpoints, no IP/DNS/Tor/I2P seed nodes, update checks default off | `checkpoints.cpp`, `blocks.cpp`, `net_node.h/.inl`, `cryptonote_core.cpp` |
| Tests | `tests/block_reward.cpp` replaces the upstream file: constant reward, version independence, penalty math, supply = h × 0.9, tally saturation horizon, 1/(N−1) dilution | `tests/unit_tests/block_reward.cpp` |

Not changed: RandomX, difficulty algorithm (Monero's 720-block window; launch floor is an E5 open item), RingCT/CLSAG (mandatory privacy inherited), dynamic block size, fees, wallet.

Why the `M` prefix is single-byte: base58 has no `O`, so "MEOW" cannot lead an address; `M` is index 20 and only single-byte varint prefixes 120–124 always produce it. `T`/`S` need two-byte prefixes (156+, 150+).

## Recorded finding for ADR-001

With 12 decimal places, `already_generated_coins` (u64) reaches its saturation point after 20,496,382 blocks ≈ 78 years at 120 s. Emission continues correctly (the constant does not depend on the tally) but the on-chain supply counter stops being exact. Atomic-unit choice (PLAN §8.1 open parameter) must be decided with this number: 10 dp pushes the horizon to ~7,800 years.

## Build (no sudo required; Docker)

```bash
docker build -t meownero-monero-builder -f spikes/candidate-m/Dockerfile spikes/candidate-m
git clone --depth 1 --branch v0.18.5.1 --recurse-submodules --shallow-submodules https://github.com/monero-project/monero.git monero
python3 spikes/candidate-m/apply.py monero
cp spikes/candidate-m/tests/block_reward.cpp monero/tests/unit_tests/block_reward.cpp
docker run --rm -v "$PWD/monero:/src" -w /src meownero-monero-builder bash -c \
  "mkdir -p build/release && cd build/release && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=ON ../.. && make -j3 daemon simplewallet unit_tests"
```

## Tests

```bash
docker run --rm -v "$PWD/monero:/src" -w /src/build/release meownero-monero-builder \
  ./tests/unit_tests/unit_tests --gtest_filter='meow_emission*:*hardfork*:*difficulty*'
```

Results (2026-09-05, patched build in the builder container): `meow_emission.*` — **7 passed**; `meow_difficulty.floor_is_applied_by_next_difficulty` — **passed** (patch 0006); upstream `difficulty.check_hash` still passes (constant_is_0_9_meow, reward_independent_of_supply, reward_independent_of_version, penalty_math_unchanged, supply_is_height_times_reward, tally_saturates_and_never_wraps, dilution_is_one_over_n_minus_one). Full upstream `unit_tests` run: 759 OK; failures attributable to the delta are the Monero address-vector tests (`get_account_address_*`, `multisig.make_*` — Meownero prefixes); `ban.subnet`, `http_server.response_soft_limit` and an abort in `cryptonote_protocol_handler.race_condition` are container/environment-class and still need a baseline run to attribute (`docs/security/code-map.md`).

## Devnet

```bash
spikes/candidate-m/devnet.sh monero /path/to/workdir 30
```

Three `monerod` containers on a private Docker network; node1 mines with `--fixed-difficulty 1` to an offline-generated `M…` address; node2/node3 follow via `--add-exclusive-node`. The script asserts every block's reward is exactly 0.9 MEOW, genesis is 0, and cumulative supply equals height × 0.9.

Results (2026-09-05, `devnet.sh … 30`):

```
miner address: MEGMXucw…nUFg                      (prefix 120 → "M")
node1 height: 50
height 0: reward 0             major_version 1     (genesis: zero-amount v2 coinbase)
height 1: reward 900000000000  major_version 1
height 2: reward 900000000000  major_version 2
height 50: reward 900000000000 major_version 16    (fresh hard-fork table reached v16 at height 16)
sampled 51 blocks: every reward == 0.9 MEOW (genesis 0)
node's get_coinbase_tx_sum over heights 0..50: emission 45000000000000 atomic = 45.0 MEOW = 50 * 0.9  OK; fees 0
meow-n2 height: 1588
meow-n3 height: 1590                               (followers sync at the miner's pace; ~2 blocks/s at difficulty 1)
```

Genesis lesson recorded: a v1 coinbase output with amount 0 is rejected by the DB layer as "RCT output without commitment"; the genesis coinbase is therefore a v2 (`RCTTypeNull`) transaction, which the DB commits with `zeroCommit(0)`.

Wallet round-trip (2026-09-05, `monero-wallet-rpc` built from the same tree, two instances on nodes n1 and n2):

```
wallet1 (miner, on n1): balance 28938.6 unlocked 28885.5   (= 32,154 blocks x 0.9; every coinbase recognised)
transfer 1.0 MEOW -> wallet2: tx cf9ed9ae… fee 0.00006564 weight 2188; mined at height 32218
node n3 view of the tx: version 2, rct_type 6 (BP+/CLSAG), 2 inputs, ring size 16, 2 outputs, amount fields [0, 0]
transfer 2.0 MEOW -> wallet3 (created via wallet-rpc on n2): tx 06a5a131… fee 0.00008574
wallet3 (on n2): balance 2.0 unlocked 2.0, incoming tx at height 46107
```

Harness lessons: (1) `monero-wallet-cli --password ''` is ignored and the CLI prompts instead, consuming piped stdin; use an explicit password. (2) A CLI-generated wallet's refresh height is estimated from the hard-fork table and wall clock; `set refresh-from-block-height 0` + `rescan_bc hard` (each prompting for the password) is needed before it scans a fresh chain. (3) The CLI-generated `meow2` wallet never recognised its incoming output while an RPC-created wallet on the same node did — a harness artefact of the piped-stdin creation, not reproduced with `create_wallet`; the M1 wallet path will use `monero-wallet-rpc` for automation and re-test the CLI path deliberately.
