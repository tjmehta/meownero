# Inherited-vs-modified code map (provisional — Candidate M, Monero v0.18.5.1 `4f92268`)

Audit-scope input per PLAN.md §2.3: re-review covers *the delta plus everything whose assumptions the delta touches*. Regenerated 2026-09-12 from a fresh application of `chain/patches/0001…0015` against upstream `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, using `git diff --numstat`. Applied HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`; tested source tree `4db958cb96d72943c5c2433bd5f4a8f730037148`. This is a scope map, not an audit-completion claim.

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
| `src/wallet/wallet2.cpp` | +15/−7 | resolve block versions by actual fork-table entry, not version-as-index | live refresh/seed restore; skip/version/activation rejection retained; two new boundary tests; no mismatched-daemon override |
| `src/cryptonote_basic/difficulty.h`, `difficulty.cpp` | +10/−2 | floor on computed and zero/one-sample difficulty | main/alt-chain DAA callers; explicit genesis exemptions above; floor stays 1; 10/10 arithmetic/core checks each at 1 and 150M; real depth-3 reorg beyond h738 at native floor 1; high-work/long-alt-chain adversarial cases remain open |
| `tests/unit_tests/block_reward.cpp` | +85/−195 | replaces emission fixtures with seven Meownero cases | subsidy and weight-penalty expectations |
| `tests/unit_tests/difficulty.cpp`, `meow_difficulty.cpp` | +187/−0 | nine floor cases, including startup, main/alt sampling, full/partial recalculation and rollback across 720/735 | synthetic varying-work DB coverage at floors 1/150M; separate daemon reorg tests cover actual acceptance |
| `tests/unit_tests/CMakeLists.txt` | +23/−0 | added test sources and separately compiled 150M-floor target | generated header assertion prevents testing floor 1 twice |
| `tests/unit_tests/node_server.cpp` | +4/−1 | active-HF miner output via existing `set_tx_out` helper | synthetic v16 protocol fixture only; production validation unchanged |
| `tests/unit_tests/hardfork.cpp` | +70/−0 | pins single-jump table; production wallet helper accepts valid versions and rejects invalid/skipped/early/late versions | mainnet sparse table plus inherited testnet/stagenet activation boundaries |
| `tests/unit_tests/base58.cpp` | +58/−1 | Meownero mainnet fixture; nine network/type encodings, rejection and checksum cases | fixed upstream public-key payloads; subaddress encoding, not subaddress key derivation; legacy hex parsing unchanged |
| `tests/unit_tests/uri.cpp` | +8/−2 | Meownero testnet address fixtures; original Monero address rejection | all 32 URI cases pass; inherited `monero:` scheme unchanged |
| `tests/unit_tests/meow_authorities.cpp` | +20/−0 | update helper fails closed, stale outputs cleared, no download URLs | actual shared helpers exercised without network dependency |
| `tests/unit_tests/multisig.cpp` | +6/−5 | five fixed addresses re-encoded for Meownero testnet | keys and multisig assertions unchanged; all seven cases pass; CI exclusion removed |
| `tests/unit_tests/wallet_storage.cpp` | +34/−7 | historical keys initialize fresh current-chain cache before file/password tests; original cache explicitly rejected | seven cases pass; original fixture bytes retained; fresh-cache storage checks do not replace historical field portability |
| `tests/unit_tests/serialization.cpp` | +27/−18 | existing friend access separates historical cache decoding from genesis acceptance; updated address-display vectors | original archive bytes and field assertions retained; normal load and explicit genesis check reject historical wallet; existing key-unlock guard reused; all 15 serialization cases pass |

Total: **16 production source/header files + 11 test sources + test CMake configuration = 28 files, +643/−616**. Grouped table rows sum to that total. The older `spikes/candidate-m/meownero-m-v0.18.5.1.diff` is historical control evidence, not the current series. Repository harnesses, CI and docs are separate from this upstream-source delta.

## Inherited unchanged but inside re-review scope (assumptions changed)

- `src/ringct/*`, `src/crypto/*`, `external/randomx`: unchanged; privacy/PoW gadget-layer review is still required by §2.3.
- Remainder of `src/cryptonote_core/blockchain.cpp`: reorg handling, main/alt-chain difficulty and post-genesis validation under the single-jump table.
- `src/cryptonote_core/tx_pool.cpp`: fees with changed base reward.
- Remaining `src/wallet/*`, remaining `src/simplewallet/*`: prefix/genesis consumers, recovery and 12-dp display. `wallet/api/wallet_manager.cpp` calls the disabled shared update helper.
- `src/rpc/core_rpc_server.cpp`: update RPC calls the disabled shared helper; local ban operations preserved and smoke-tested.
- `src/serialization/*`, `contrib/epee`: unchanged, but encoding remains readiness-review scope.

## Other inherited code (still in the general audit)

P2P transport, levin, LMDB, wallet2, multisig, hardware-wallet paths, Dandelion++, Tor/I2P and ZMQ remain inherited except for the exact deltas above. Being outside the edited lines does not establish security or test completion.

## Known upstream test effects and verification limits

| Test | Cause | Disposition |
|---|---|---|
| `get_account_address_as_str.*`, `get_account_address_from_str.*` | inherited Monero base58 fixture under changed prefixes | **Fixed by patch 0009**; all eight cases pass, CI exclusion removed |
| `uri.*` | inherited Monero testnet fixtures | **Fixed by patch 0009**; all 32 cases pass, including new original-address rejection |
| `multisig.make_*` | inherited testnet address expectations | **Fixed by patch 0011**; five address vectors updated, test keys/assertions preserved; all seven `multisig.*` cases pass and CI exclusion is removed |
| `ban.subnet`, `http_server.response_soft_limit`, `notify.works` | also fail on unpatched baseline in the same container (2026-09-05: 1,228 passed, these 3 failed) | existing environment-attributed CI exclusions; local host-ban smoke does not close subnet coverage |
| `cryptonote_protocol_handler.race_condition` | untagged synthetic miner output rejected at v16, previously timed out at 300 s | **Fixed by patch 0007**, bounded regression passes; production validation unchanged; real-block devnet separately passed 2026-09-06 at h2,841 |
| `Serialization.portability_{wallet,unsigned_tx,signed_tx}`, three wallet-storage cases | historical Monero fixtures; wallet storage reports genesis mismatch; related baseline selection passes 40/40 | **Fixed by patches 0012/0013**; original archives unchanged, storage uses current-chain caches from historical keys, historical field decoding tested separately from explicit genesis rejection; production checks unchanged |
| `AddressFromURL.{Success,Failure}`, four `DNSResolver` cases | DNS lookups with Docker networking disabled in patch-0009 broader run | six additional failures in that offline run, not added to CI exclusions |
| `meow_*` and targeted regressions | Meownero-specific cases plus inherited address/URI/DAA/protocol selections | ten-patch rebuilt selection **280/280**, raised-floor target **9/9**; live authority runner passes |

Latest full CI selection (patch 0015, networking enabled for inherited DNS cases):
**1,237/1,237 in 79.174 s**, with only the three historical environment exclusions.
This is not an unfiltered suite or remote CI pass. Seed recovery passes with 130
coinbase entries and exact balance/reopen assertions; floor targets each pass
10/10. Historical archive bytes are unchanged. The current wallet fix does not
bypass genesis or fork-version validation.

Same-host fixed-image **thirteen-patch** clean binary reproduction now passes for
all three binaries. The fifteen-patch verification build reuses a copy of that
build tree; it is not a clean fifteen-patch reproduction. Full evidence:
[`verification-2026-09-12-m1.md`](../../research/verification-2026-09-12-m1.md).
The earlier thirteen-patch selection (1,234/1,234) and eight-patch reproduction
remain historical results in `research/verification-2026-09-07-m1.md`.
