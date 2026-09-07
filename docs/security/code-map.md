# Inherited-vs-modified code map (provisional — Candidate M, Monero v0.18.5.1 `4f92268`)

Audit-scope input per PLAN.md §2.3: re-review covers *the delta plus everything whose assumptions the delta touches*. Regenerated 2026-09-07 from a fresh application of `chain/patches/0001…0010` against upstream `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, using `git diff --numstat`. Applied HEAD `8c24067c9e2f7a0b855d3d239c9ccf2e7e7be8a9`; tested source tree `1e7f5e4347968c8824b4fe4284ccc6db298e42fb`. This is a scope map, not an audit-completion claim.

## Modified (Meownero delta)

| File | Lines (+/−) | What changed | Assumptions touched → re-review scope |
|---|---|---|---|
| `src/cryptonote_config.h` | +43/−32 | fixed subsidy; floor 1; network name, prefixes, ports, IDs, genesis blob/nonce | all constant consumers: address parsing, P2P identity, genesis and monetary accounting; `COIN` precision unchanged |
| `src/cryptonote_basic/cryptonote_basic_impl.cpp` | +5/−9 | constant block reward | supply tally, dynamic fee derivation and unchanged weight-penalty logic with changed subsidy magnitude |
| `src/cryptonote_core/cryptonote_tx_utils.cpp` | +4/−0 | height-0 miner reward zero | block-template construction |
| `src/cryptonote_core/blockchain.cpp` | +6/−2 | height-0 reward zero; genesis difficulty 1 in next-block calculation and recalculation | coinbase validation, genesis PoW, cumulative-work accounting under a raised floor |
| `src/hardforks/hardforks.cpp` | +8/−42 | mainnet single jump `{v1@0, v16@1}`; `version_1_till=0` | handshake activation assumptions, transaction/output encoding from block 1; `meow_hardforks.single_jump_table` and protocol regression |
| `src/checkpoints/checkpoints.cpp` | +5/−70 | default checkpoints removed; DNS checkpoints disabled | checkpoint initialization, externally supplied checkpoints, reorg policy without shipped finality anchors; empty default set does not imply all checkpoint checks are unconditional passes |
| `src/blocks/blocks.cpp` | +1/−3 | embedded block-hash blobs disabled | fast-sync and block-hash assumptions |
| `src/p2p/net_node.h` | +1/−6 | DNS seed hostnames removed | explicit operator bootstrap required |
| `src/p2p/net_node.inl` | +9/−74 | IP/Tor/I2P seeds removed; DNS-blocklist callback disabled; opt-in warns and remains false | bootstrap and remote banning authority; local host/subnet ban implementation unchanged; RPC host-ban smoke passes |
| `src/p2p/net_node.cpp` | +1/−1 | DNS-blocklist option help states it is ignored | config compatibility without silently claiming protection |
| `src/cryptonote_core/cryptonote_core.cpp` | +2/−2 | update default disabled; help states all modes are unavailable | parsing remains compatible; shared helper below prevents opt-in authority access |
| `src/common/updates.cpp` | +8/−78 | shared update check clears outputs and fails closed; download URL helper returns empty | daemon periodic checks, update RPC, wallet-manager API; RPC check/download/update tested, wallet API caller reviewed but not separately runtime-tested |
| `src/simplewallet/simplewallet.cpp` | +3/−59 | donate command returns disabled message; help updated; inherited destination/transfer path removed | no implicit donation recipient; disposable offline CLI checks pass on all three networks; unused header constant remains referenced by the inherited URL test |
| `src/cryptonote_basic/difficulty.h`, `difficulty.cpp` | +10/−2 | floor on computed and zero/one-sample difficulty | main/alt-chain DAA callers; explicit genesis exemptions above; floor stays 1; arithmetic/core accounting checks at 1 and 150M, adversarial reorg tests still open |
| `tests/unit_tests/block_reward.cpp` | +85/−195 | replaces emission fixtures with seven Meownero cases | subsidy and weight-penalty expectations |
| `tests/unit_tests/difficulty.cpp`, `meow_difficulty.cpp` | +133/−0 | eight floor cases including actual core initialization/recalculation/fixed override | synthetic DB accounting is not high-difficulty PoW or adversarial reorg evidence |
| `tests/unit_tests/CMakeLists.txt` | +23/−0 | added test sources and separately compiled 150M-floor target | generated header assertion prevents testing floor 1 twice |
| `tests/unit_tests/node_server.cpp` | +4/−1 | active-HF miner output via existing `set_tx_out` helper | synthetic v16 protocol fixture only; production validation unchanged |
| `tests/unit_tests/hardfork.cpp` | +13/−0 | pins single-jump table | test passes |
| `tests/unit_tests/base58.cpp` | +58/−1 | Meownero mainnet fixture; nine network/type encodings, rejection and checksum cases | fixed upstream public-key payloads; subaddress encoding, not subaddress key derivation; legacy hex parsing unchanged |
| `tests/unit_tests/uri.cpp` | +8/−2 | Meownero testnet address fixtures; original Monero address rejection | all 32 URI cases pass; inherited `monero:` scheme unchanged |
| `tests/unit_tests/meow_authorities.cpp` | +20/−0 | update helper fails closed, stale outputs cleared, no download URLs | actual shared helpers exercised without network dependency |

Total: **15 production source/header files + 8 test sources + test CMake configuration = 24 files, +450/−579**. Grouped table rows sum to that total. The older `spikes/candidate-m/meownero-m-v0.18.5.1.diff` is historical control evidence, not the current series. Repository harnesses, CI and docs are separate from this upstream-source delta.

## Inherited unchanged but inside re-review scope (assumptions changed)

- `src/ringct/*`, `src/crypto/*`, `external/randomx`: unchanged; privacy/PoW gadget-layer review is still required by §2.3.
- Remainder of `src/cryptonote_core/blockchain.cpp`: reorg handling, main/alt-chain difficulty and post-genesis validation under the single-jump table.
- `src/cryptonote_core/tx_pool.cpp`: fees with changed base reward.
- `src/wallet/*`, remaining `src/simplewallet/*`: prefix/genesis consumers, recovery and 12-dp display. `wallet/api/wallet_manager.cpp` calls the disabled shared update helper.
- `src/rpc/core_rpc_server.cpp`: update RPC calls the disabled shared helper; local ban operations preserved and smoke-tested.
- `src/serialization/*`, `contrib/epee`: unchanged, but encoding remains readiness-review scope.

## Other inherited code (still in the general audit)

P2P transport, levin, LMDB, wallet2, multisig, hardware-wallet paths, Dandelion++, Tor/I2P and ZMQ remain inherited except for the exact deltas above. Being outside the edited lines does not establish security or test completion.

## Known upstream test effects and verification limits

| Test | Cause | Disposition |
|---|---|---|
| `get_account_address_as_str.*`, `get_account_address_from_str.*` | inherited Monero base58 fixture under changed prefixes | **Fixed by patch 0009**; all eight cases pass, CI exclusion removed |
| `uri.*` | inherited Monero testnet fixtures | **Fixed by patch 0009**; all 32 cases pass, including new original-address rejection |
| `multisig.make_*` | inherited testnet address expectations | still open; existing `multisig.*` exclusion remains, not claimed as a pass |
| `ban.subnet`, `http_server.response_soft_limit`, `notify.works` | also fail on unpatched baseline in the same container (2026-09-05: 1,228 passed, these 3 failed) | existing environment-attributed CI exclusions; local host-ban smoke does not close subnet coverage |
| `cryptonote_protocol_handler.race_condition` | untagged synthetic miner output rejected at v16, previously timed out at 300 s | **Fixed by patch 0007**, bounded regression passes; production validation unchanged; real-block devnet separately passed 2026-09-06 at h2,841 |
| `Serialization.portability_{wallet,unsigned_tx,signed_tx}`, three wallet-storage cases | historical Monero fixtures; wallet storage reports genesis mismatch; related baseline selection passes 40/40 | still open M1 fixture work; production genesis/network checks must not be weakened |
| `AddressFromURL.{Success,Failure}`, four `DNSResolver` cases | DNS lookups with Docker networking disabled in patch-0009 broader run | six additional failures in that offline run, not added to CI exclusions |
| `meow_*` and targeted regressions | Meownero-specific cases plus inherited address/URI/DAA/protocol selections | ten-patch rebuilt selection **280/280**, raised-floor target **9/9**; live authority runner passes |

Latest broader run (patch 0009, offline): **1,212/1,224**, not green. The whole upstream suite was not rerun after patch 0010; targeted and authority tests are not a substitute. Same-host fixed-image binary reproduction was verified for **patches 0001–0008 only**; no ten-patch binary equality claim. Full evidence: `research/verification-2026-09-07-m1.md`.
