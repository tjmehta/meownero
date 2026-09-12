# Mining track — exact P2Pool compatibility boundary

**Policy update:** the reward/fork compatibility matrix and default/branding wording below record historical controls. TJ subsequently selected 9/90, with gated 12/120 fallback; [decision](decision-2026-09-12-issuance.md). Selected-parameter P2Pool compatibility remains untested; nominal rewards do not guarantee purchasing power or hashpower.

Base: `39070e8e3ab32a695d80c90b7c0ad74cf39fb581`, including `81b3182`.
Work is confined to `spikes/p2pool/`, this report, and
`research/evidence/swarm-2026-09-12/mining/`. Complete swarm decisions and resumed
handoff were read before implementation. Closed reproduction, seed recovery,
DAA and reorg evidence was reused, not repeated.

**Result: unmodified current P2Pool is incompatible.** An RPC/address wrapper
cannot fix its independent subsidy construction and share consensus validation.
Stop at this concrete compatibility boundary; no pool process, public peer,
deployment, production patch or policy change was performed. The deliverable is
a source-pinned executable gate plus isolated real-daemon negative/positive
controls, not a working decentralized pool.

## Source provenance and evidence

GitHub's public API returned master
[`9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4`](https://github.com/SChernykh/p2pool/commit/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4),
committed September 8, 2026, `docs: add Arti Tor proxy setup (#422)`.
This is the current master snapshot observed September 12, not a released or
audited Meownero-compatible version.

- [API receipt](evidence/swarm-2026-09-12/mining/upstream-master.json).
- [Pin and 19 per-file SHA-256 values](../spikes/p2pool/upstream.json).
- Archive SHA-256: `212f59cc6c3d693917e90f7b863413f8399f21375751a59769c5804f3630dc7d`.
- [Reproduction instructions](../spikes/p2pool/README.md).
- [Compiled source results](evidence/swarm-2026-09-12/mining/source-results.json).
- [Daemon results](evidence/swarm-2026-09-12/mining/devnet-results.json),
  [RPC transcript](evidence/swarm-2026-09-12/mining/rpc-transcript.json),
  [ZMQ notification](evidence/swarm-2026-09-12/mining/zmq-miner-data.txt),
  [runner log](evidence/swarm-2026-09-12/mining/run.log).

The archive checksum verifies repeat retrieval against this observed artifact;
it is not independent maintainer signature verification. Full P2Pool dependencies
and binary reproducibility were not investigated because the source boundary
already prevents a pool PoC. Only two exact source routines and unchanged
hardfork tables are compiled, in the immutable authorized builder. The Meownero
daemon is reused read-only from the handoff's incremental fifteen-patch build;
its binary checksum is recorded. No new clean reproduction claim.

## Final verification

Final runner exit **0**, `/tmp/meow-swarm-mining-probe-run-04`, using a second
checksum-verified source retrieval. Seven compiled cases, 19 file hashes, eight
RPC methods, both incompatible amount rejections, original-template acceptance
and ZMQ delivery passed. Final assertions also require the daemon's exact
overpayment and underpayment diagnostic messages, avoiding attribution from a
generic RPC rejection alone. Source-drift negative control rejected before any
compilation; shell and Python syntax checks passed. No mining container remains.

Earlier harness failures are retained: an off-by-one expected arithmetic value
and an incorrect assumption that an empty HTTP backlog is always serialized.
Run 03 passed; run 04 followed the added diagnostic assertions, not an unchanged
repeat. Evidence hashes are in [sha256.json](evidence/swarm-2026-09-12/mining/sha256.json).

The full daemon log includes caught allocation exceptions while trying RandomX
cache/large-page VM allocation and a ZMQ shutdown exception; the cache initialized,
all controls passed and daemon exit was 0. These logs are retained, not suppressed.
This small 1 GiB-capped run is neither a performance nor sustained-uptime result.
There was no full P2Pool build, no host package installation and no cache purge.

## Compatibility matrix

All upstream links below resolve to the pinned source. “Source” is code
inspection/hash-guard evidence; “executed” is a compiled routine or daemon test,
not an unrun full P2Pool integration.

| Surface | Exact current behavior and Meownero gap | Evidence |
|---|---|---|
| Address identity | Regular prefixes 18/53/24 and subaddress prefixes 42/63/36; fixed 95 characters and a single prefix byte. Meownero's mainnet regular prefix 120 is rejected. Its test/stage regular prefixes 156/150 require two-byte varints and 97-character encoding, so changing only the prefix constants would still fail. Integrated addresses are unsupported. | Source: [wallet.cpp](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/wallet.cpp#L36), [wallet.h](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/wallet.h#L34); local patch 0002. Full wallet parser not executed. |
| Network/genesis | Daemon handshake compares mainnet/testnet/stagenet booleans, not an explicit chain genesis identity. Meownero reports mainnet too. Seed height 0 is fetched dynamically, so a changed genesis is not itself a hardcoded-hash rejection. A future adapter must bind the intended chain explicitly. | Source: [handshake](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/p2pool.cpp#L1581), [seed headers](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/p2pool.cpp#L1257). Executed: zero-reward genesis header equals initial previous/seed hash. |
| Subsidy construction | `max((~already_generated_coins) >> 19, 600000000000)` gives 35,184,372,088,831 atomic units at Meownero height 1; required reward is 900,000,000,000. P2Pool builds its own template from `get_miner_data`, not the daemon's full reward template. Saturation yields 0.6, also wrong. | Executed exact [get_base_reward](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/block_template.cpp#L169), call at line 320. Real daemon rejects both amount substitutions; original 0.9 template accepted. |
| Coinbase/share validation | Share parser insists on the historical Monero version at the coinbase height. Its table returns v1 at height 1; Meownero requires v16 there. It accepts only tagged output form, tx v2, unlock height +60 and total reward at least 0.6. The 0.9 and 0.675 unpenalized totals exceed that floor; this does not make the subsidy constructor correct. The 0.6 constant also enters output-size estimation, so a reward port must trace all uses. | Executed exact [network_major_version](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/side_chain.cpp#L1165) with upstream tables; source [parser](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/pool_block_parser.inl#L64), [size estimate](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/block_template.cpp#L855). Daemon template has tagged output and unlock 61. |
| Mainchain difficulty/PoW | Daemon supplies hex 128-bit difficulty and seed hash; P2Pool copies them into template state. Its seed schedule is 2048 blocks with 64-block lag. Mainchain DAA is not replaced by P2Pool. Initial real daemon difficulty is 1 without an override. | Source: [parser](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/json_parsers.h), [template](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/block_template.cpp#L238); executed native-DAA submission. No full P2Pool RandomX/seed-transition differential test. |
| Sharechain difficulty/PPLNS | Mainnet config minimum share difficulty is 100,000; `min_diff:1` is rejected by source config checks even in a named custom mainnet pool. This is distinct from Meownero mainchain floor 1. Dynamic PPLNS limits weight to twice the seed-height mainchain difficulty, allowing one non-uncle share to exceed it. At launch difficulty 1, a 100,000-work share exceeds that limit: a useful multi-miner payout window is not established by merely changing addresses. | Source: [config checks](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/side_chain.cpp#L2605), [PPLNS](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/side_chain.cpp#L382). Low-hashrate effect is a source-derived inference, not measured payouts. |
| Sidechain identity/peers | Consensus ID includes network enum, pool name/password, block time, share minimum, window and uncle penalty; it does not include a Meownero genesis field. Default/mini/nano have Monero IDs and seed discovery. A custom config changes identity but cannot fix mainchain reward/fork consensus. | Source: [ID construction](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/side_chain.cpp#L119), [discovery](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/p2p_server.cpp#L734). No peers contacted. |
| Timing | `MONERO_BLOCK_TIME=120` matches current Meownero. It enters hashrate display, header retention, pruning and alternate sharechain comparison. The approved 90/.675 comparison would require tracing these uses, not only changing mainchain issuance. | Source: [side_chain.h](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/side_chain.h#L28) and `side_chain.cpp`. No timing policy changed. |
| Daemon RPC/ZMQ | Required RPC >=3.10, network booleans, miner fields, header retrieval and submit flow exist. Empty HTTP `tx_backlog` may be omitted; P2Pool handles that. P2Pool requires daemon ZMQ **PUB**, distinct from the ZMQ RPC socket, with `json-full-miner_data` and `json-full-chain_main`. | Executed RPC transcript and real `json-full-miner_data` reception via installed libzmq. Source: [RPC requirements](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/p2pool.cpp#L1696), [ZMQ subscriptions](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/src/zmq_reader.cpp#L101). Chain-main event parsing, populated backlog and failover not tested. |

## Factual corrections (not policy choices)

1. A custom P2Pool name/password does not make a Monero fork compatible; reward
   construction and hardfork validation remain Monero-specific.
2. A new genesis is dynamically used as the initial RandomX seed; the inspected
   handshake does not establish an independent genesis identity check.
3. Current wallet code supports subaddresses despite its stale comment saying
   otherwise: explicit subaddress prefix cases exist. Meownero prefixes still
   fail, and test/stage encoding additionally needs varints.
4. The current chain starts v16 at height 1, as the resumed source and actual RPC
   show. Older prototype documentation saying v16 at height 16 is not the current
   flow and was not used to configure the test.
5. Empty `tx_backlog` is omitted by the tested HTTP RPC. The first harness assumed
   an explicit empty array; that assumption was corrected to match P2Pool's
   optional HTTP parsing. This was a harness error, not a daemon incompatibility.

## Normative choices and safety limits

Recommend a separately reviewed P2Pool chain profile/fork before providing mining
onboarding. Explicit genesis binding, address support, flat subsidy, exact fork
table and independent peer/sharechain identity are required implementation work.
Whether to tune share difficulty/window for low hashpower needs measured payout
and adversarial sharechain tests; no share/mainchain policy is adopted here.

Noncustodial direct coinbase payouts remove a central pool wallet's custody and
can let miners choose their own daemon and templates. They **do not create
hashpower, protect a small chain against majority/reorg attacks, guarantee payout
frequency, or make a hosted pool endpoint independent of its operator**. The
pinned [upstream payout description](https://github.com/SChernykh/p2pool/blob/9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4/README.md#how-payouts-work-in-p2pool)
itself makes payouts conditional on shares and found mainchain blocks. A new
Meownero chain inherits neither Monero's work nor its pool population.

No ticker, public identity, checkpoint, signer, audit-budget, fair-launch,
premine, perpetual-issuance, default 120/.9, floor-1 or human-gate choice changed.
The 90/.675 comparison is only noted for compatibility scope; 9/90 branding is
not an implemented emission change.

Missing integration: full P2Pool build/start, share mining/propagation, multi-miner
PPLNS payouts, wallet payout recovery, pool reorg/partition tests, loaded fee and
penalty cases, RandomX transition tests, independent review and user onboarding.
None is inferred from the one-block daemon experiment.
