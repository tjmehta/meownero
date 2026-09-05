# Inherited-vs-modified code map (provisional — Candidate M, Monero v0.18.5.1 `4f92268`)

Audit-scope input per PLAN.md §2.3: re-review covers *the delta plus everything whose assumptions the delta touches*. Generated from `spikes/candidate-m/apply.py`; regenerate when the M1 patch series is cut. Line counts from `git diff --stat` of the control.

## Modified (Meownero delta)

| File | Lines (+/−) | What changed | Assumptions touched → re-review scope |
|---|---|---|---|
| `src/cryptonote_config.h` | +40/−34 | `MEOW_BLOCK_REWARD`; `MEOW_MIN_DIFFICULTY` (1); `CRYPTONOTE_NAME`; per-network prefixes, ports, network IDs, genesis blob + nonce | every consumer of these constants: address parsing (`cryptonote_basic_impl.cpp`, `base58`), P2P handshake (`net_node.inl`), genesis generation, fee constants that reference `COIN` (unchanged value) |
| `src/cryptonote_basic/cryptonote_basic_impl.cpp` | +5/−9 | `get_block_reward` base reward is a constant | supply tally (`blockchain.cpp` line ~4434, saturation), dynamic fee derivation (`get_dynamic_base_fee`, denominated in base reward → fees are 1.5× Monero's per unit weight at the same price), block-weight penalty (unchanged code, changed magnitude) |
| `src/cryptonote_core/cryptonote_tx_utils.cpp` | +4/−0 | height-0 block reward = 0 in `construct_miner_tx` | block-template path only |
| `src/cryptonote_core/blockchain.cpp` | +3/−0 | height-0 base reward = 0 in `validate_miner_transaction` | coinbase validation; `already_generated_coins` accounting for genesis (0) |
| `src/hardforks/hardforks.cpp` | +10/−43 | mainnet table `{v1@0, v16@1}` (single jump); `version_1_till = 0` | `HardFork` logic; ideal version is 16 from height 1, so no activation boundary above v6 exists (handshake check in `cryptonote_protocol_handler.inl:449`) and no pre-RingCT coinbase output is ever created. Test: `meow_hardforks.single_jump_table` |
| `src/checkpoints/checkpoints.cpp` | +4/−71 | no default checkpoints; DNS checkpoints disabled | `Blockchain::init` checkpoint validation (empty set), `m_checkpoints.check_block` (always passes), reorg depth policy now relies solely on `CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW`/no finality — **threat model §deep-reorg** |
| `src/blocks/blocks.cpp` | +1/−3 | no embedded block-hash blobs | `Blockchain::init` `m_blocks_hash_check` (empty), fast-sync path disabled |
| `src/p2p/net_node.h` | +1/−6 | no DNS seed hostnames | bootstrap: node starts with zero peers unless configured — **operator docs** |
| `src/p2p/net_node.inl` | +4/−26 | no IP/Tor/I2P seeds | same |
| `src/cryptonote_core/cryptonote_core.cpp` | +2/−2 | `--check-updates` default `disabled` | none (no update authority exists) |
| `src/cryptonote_basic/difficulty.h/.cpp` | +8/−2 | `apply_min_difficulty` clamp applied inside `next_difficulty` (patch 0006) | every difficulty consumer (main chain, alt chains, checkpoints) gets the same clamp — no split possible; identity while `MEOW_MIN_DIFFICULTY == 1` |
| `tests/unit_tests/block_reward.cpp` | replaced | Meownero emission tests + difficulty-floor test | n/a |

Total: 12 source files + 1 test file (patch series `chain/patches/0001…0006`; diff export `spikes/candidate-m/meownero-m-v0.18.5.1.diff`).

## Inherited unchanged but inside re-review scope (assumptions changed)

- `src/ringct/*`, `src/crypto/*`, `external/randomx` — **unchanged**; in scope for the §2.3 gadget-layer controls because they are the privacy/PoW layer we ship (readiness record lines b–c), not because the delta touched them.
- `src/cryptonote_core/blockchain.cpp` (rest): difficulty (`get_difficulty_for_next_block`, no launch floor), reorg handling (no checkpoints), coinbase decomposition and output-type checks under a rapidly advancing hard-fork table.
- `src/cryptonote_core/tx_pool.cpp` fee logic (base reward magnitude changed).
- `src/wallet/*`, `src/simplewallet/*`: address prefix consumers; display of amounts (12 dp unchanged).
- `src/serialization/*`, `contrib/epee`: unchanged, but encoding is line (c) of the readiness record.

## Inherited unchanged and out of delta scope (still in the general audit)

Everything else: P2P protocol, levin, LMDB, RPC, wallet2, multisig, hardware-wallet paths, Dandelion++, Tor/I2P, ZMQ.

## Known upstream tests affected by the delta (from the full `unit_tests` run, 2026-09-05)

| Test | Cause | Disposition |
|---|---|---|
| `get_account_address_as_str.works_correctly`, `get_account_address_from_str.handles_valid_address` | Monero address vectors; prefixes changed | replace vectors with Meownero addresses (M1) |
| `multisig.make_*` | same address vectors (asserts against `TESTNET` address strings) | same |
| `ban.subnet`, `http_server.response_soft_limit`, `notify.works` | **also fail on the unpatched v0.18.5.1 baseline in the same container** (baseline run 2026-09-05: 1,228 passed, these 3 failed) → environment class, not the delta | excluded from CI's pass criterion with this note as the reason |
| `cryptonote_protocol_handler.race_condition` (hung under the first delta; passes on baseline) | reproduced twice (full suite and alone). Diagnosis: the test adds blocks straight into the DB (bypassing `HardFork` state) and stamps them with `get_current_hard_fork_version()`, which stays 1, then handshakes two cores; the handler compares the peer's `top_version` with `get_ideal_hard_fork_version(height)`. On Monero's table both are 1 for the first ~1M blocks; on the Meownero table the ideal version climbs to 16 by height 16, so the peer is dropped as "wrong hard fork version" and `handshaked.wait()` never returns. A test-harness assumption about the schedule, not a consensus defect (the 3-node devnet handshakes and syncs with real blocks). | **fixed at the root**: the hard-fork table is now a single jump `{v1@0, v16@1}` (patch 0003 rewritten), which removes the launch-window handshake boundaries the test exposed; re-run pending |
| `meow_emission.*` (7) | new | pass |
