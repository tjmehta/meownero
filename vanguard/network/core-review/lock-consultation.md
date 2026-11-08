# Core timestamp-lock consultation, 2026-10-20 UTC

Core accepts retaining the inherited nonzero-unlock restriction for this fresh,
bounded, non-public v1@0/v18@1 network. No dedicated timestamp epoch, new
timestamp-to-height mapping, or `nettype` threading is needed for this candidate.
This is a source consultation on `ebb953530ecfc3bf712e9cb08e042cf11b7f272c`,
overlay SHA256 `0f971c34e3401f2faf85fa98862f7f28698af3b5ee28765c17657f8bee5eb044`.
It is not final candidate acceptance or a native review-stage decision.

The consultation's premise missed an existing consensus rule. At upstream
`e151643c5269c83bf24a83b2548e2493876026b2`,
[`HF_VERSION_REJECT_UNLOCK_TIME` is 17](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/src/cryptonote_config.h#L206).
[`ver_non_input_consensus_templated`, Rule 8](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/src/cryptonote_core/tx_verification_utils.cpp#L349)
rejects any ordinary transaction with nonzero `unlock_time` at v17 or later,
setting `m_nonzero_unlock_time` and `m_verifivation_failed`. Its
[documented contract](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/src/cryptonote_core/tx_verification_utils.h#L239)
explicitly applies to non-coinbase transactions. The overlay changes neither
that verifier nor the lock conversion. The configured genesis contains no
ordinary transactions; every subsequent block must be v18. There is no
pre-v17 ordinary-transaction history to convert on this chain.

Preserve this rule and the accepted fresh-genesis/fork profile. Do not add a new
blanket timestamp denial, relax nonzero height locks, reinterpret timestamps as
heights, or retrofit a mainnet epoch. If a later network permits timestamp locks
or imports older history, that is a separate protocol and persistent-state
change requiring an exact mapping and independent review before activation.

The source and arithmetic check is reproducible without staging or compilation:

```sh
python3 -B vanguard/network/core-review/check-lock-domain.py \
  --source /absolute/path/to/pinned/monero-fcmp
```

[The receipt](source-and-arithmetic.json) binds 16 inspected upstream files to
their pinned Git objects and regenerates the exact ten-file overlay in memory.
It records a known-bad removed-rule control and explicit arithmetic expectations.
It does not execute the C++ verifier, wallet, LMDB, proof system or network.
Public source URLs above are revision locators; browser retrieval failed, so
claims were checked against the available pinned Git objects and working bytes.

The following paths establish the inherited restriction and agreement boundary.
Line numbers refer to upstream before the overlay.

| Boundary | Inspected source and implication |
| --- | --- |
| Pool ingress | `src/cryptonote_core/tx_pool.cpp:228,254` refuses nonzero unlock for ordinary relay and invokes non-input consensus unless the same fork version was already verified. A relay-only rejection is insufficient evidence of consensus rejection. |
| Main/alternative block supplements | `src/cryptonote_core/blockchain.cpp:2176,4625` invokes the shared non-input verifier, including transactions arriving with blocks. Native tests must cover supplement/cache paths, not just RPC submission. |
| Wallet creation | `src/wallet/wallet_rpc_server.cpp:1276,1344,1822,1896` rejects nonzero requests for transfer, split transfer, sweep all and sweep single. `src/carrot_impl/format_utils.cpp:248` constructs CARROT transactions with unlock 0. The pre-CARROT pending-transaction sanity check also requires unlock 0; that check alone does not establish CARROT behavior. |
| Ordinary output metadata | `src/cryptonote_basic/cryptonote_format_utils.cpp:2095,2102` maps unlock 0 at creation index h to last-locked index L=h+9. Default age remains 10 blocks. |
| Coinbase metadata | `src/cryptonote_core/blockchain.cpp:1420` separately requires unlock=h+60. For the bounded height domain below, the unchanged helper yields L=h+59. Preserve genesis unlock 60 and height-one unlock 61; Rule 8 must not be applied to coinbase. |
| Daemon and wallet tree construction | `blockchain.cpp:2854` and `wallet/wallet2.cpp:3219` share `get_outs_by_last_locked_block`, whose helper calls the unchanged conversion at `cryptonote_format_utils.cpp:126`. No new timestamp mapping can diverge between them for these admitted outputs. |
| Wallet path and spend selection | `wallet2.cpp:2026,7676` uses L for path requests and post-FCMP unlocked status. `wallet/tx_builder.cpp:84` compares L with the top block index. With synced block count N, the wallet condition is N>=L+1. |
| Stored-state operations | `blockchain_db/blockchain_db.cpp:535` uses L for path lookup. `blockchain_db/lmdb/db_lmdb.cpp:1202,7360` uses it for removal and legacy tree initialization. `blockchain.cpp:2587` uses it for recent-output reconstruction. Changing the helper after a DB exists can change persisted lock buckets, paths and reconstructed roots. No such change is accepted here. |

Tree construction stages future roots in advance. A stored root's existence does
not by itself prove spend maturity. Compare the same tree block index, header
commitment, reference block and leaf tuple count across daemon and wallet;
enforce the existing reference-root and maturity rules. At creation h=1,
ordinary unlock 0 gives L=10 and wallet N>=11. Coinbase unlock 61 gives L=60 and
wallet N>=61. Keep the zero-valued genesis exception separate from funded
height-one coinbase and later payment evidence.

This reasoning is bounded to coinbase heights h<499999940, where h+60 remains
below `CRYPTONOTE_MAX_BLOCK_NUMBER=500000000`. At h=499999940 the inherited
helper would interpret coinbase unlock 500000000 as a timestamp. That distant
representation limit needs separate review; this consultation provides no
unbounded-lifetime assurance or new height-cap consensus rule.

Core confirms the proposed projection's algebra for the dedicated v18/90-second
chain. Retaining the 60-sample window, use a 2745-second median projection
`(60+1)*90/2`, a 90-second last-element projection, and the existing minimum.
For samples `1700000000 + 90*i`, i=0..59, both branches give 1700005400. Upstream
120-second samples/projectors give 1700007200. These are deterministic projection
calculations, not a timestamp-lock-to-height mapping or FCMP maturity schedule.
The inherited `<60` sample path still returns local wall time. Do not describe
that startup path as deterministic, and do not change it in this consultation.

There are two details to preserve:

- `epee::misc_utils::median` sorts its vector in place at
  `contrib/epee/include/misc_language.h:53`. Consequently `timestamps.back()`
  after that call is the maximum sampled timestamp, not necessarily the most
  recent chronological block's timestamp. Preserve the upstream operation order
  and include non-monotone windows in later native comparisons.
- The overlay's two `get_adjusted_time` replacements use `get_difficulty_target()`
  for every selector. At foreign v1, that returns 60 where upstream always
  used literal 120. For samples `1700000000+60*i`, the old result is 1700003660
  and the proposed result is 1700003600. Pre-v13 spend checks use wall time,
  so this counterexample concerns the adjusted-time RPC behavior, rather than
  showing a v1 timestamp-spend consensus change. It nevertheless violates exact
  foreign behavior preservation. The P2P writer should restrict the two
  projection substitutions to dedicated TESTNET, retaining literal
  `DIFFICULTY_TARGET_V2` for other selectors. For example, choose a local
  projection target `m_nettype == TESTNET ? get_difficulty_target() :
  DIFFICULTY_TARGET_V2`. Do not change the difficulty algorithm's own 60/120
  selection or the legacy unlock tolerance as part of that correction.

The proposed legacy seconds tolerance of target*1 is 90 seconds for the dedicated
chain and preserves 60/120 for foreign pre/post-v2 selection. Under this fresh
v18 profile it does not authorize timestamp-locked transactions; Rule 8 rejects
their creation. The historical hardcoded mainnet conversion remains unsuitable
as a general dedicated-network timestamp mapping. Its unreachability for valid
ordinary outputs is the reason to leave it alone here.

These native acceptance cases remain to be executed by the existing writer
under the appropriate finite platform grant. They are not claimed as passed by
the source/arithmetic receipt.

| Case | Required observation |
| --- | --- |
| Valid funded FCMP++/CARROT unlock 0 | Positive ordinary transaction passes the full unchanged verifier and wallet construction; proper proof, fee, point and root checks remain active. |
| Nonzero unlock domain | Test 1, 499999999, 500000000, 1656629117, 1656629118, 1656629119, 1700000000 and 18446744073709551615. Reject at v18 with `m_nonzero_unlock_time`; use a valid unlock 0 control and fresh transaction hashes. Merely invalidating a proof by changing its prefix is not a specific Rule 8 observation. |
| Admission routes | Repeat nonzero refusal through normal pool ingress, block supplement, main-chain block and alternative/reorg validation. An invalid alternative must never become accepted state. Cover cached supplement/verified-fork handling and restart with a populated pool. |
| Wallet request routes | Each of transfer/split/sweep-all/sweep-single refuses nonzero unlock. Use a valid unlocked positive control and an authorized transfer-capable test context, so restricted/auth/funding errors cannot masquerade as the unlock guard. Retain deployed RPC restrictions. |
| Exact coinbase | At h=1, unlock 61 succeeds; unlock 0, 60, 62 and timestamp-valued unlocks fail the miner prevalidation rule. Genesis stays the accepted exact unlock 60 zero-valued transaction. |
| Maturity | For ordinary output created h=1, wallet N=10 remains locked and N=11 is eligible. For coinbase h=1, N=60 remains locked and N=61 is eligible. Prove actual early-spend rejection and later spend using valid reference roots; do not infer either from balance displays. |
| Time arithmetic | At chain counts 59 and 60, distinguish wall-clock fallback from full-window projection. Use regular, flat, skewed and non-monotone windows; compare foreign selectors/versions 1, 2, 13, 17, 18 against unchanged upstream. |
| Persistence and reconstruction | Match header roots, tree block indices, leaves/counts, output lock buckets and wallet paths across peers, cold restart, fresh replay, wallet restoration and bounded rollback/rejoin. Rejected nonzero transactions must leave these and balances unchanged. |
| Profile isolation | Refuse upstream/historical DB and wallet assumptions; do not import pre-v17 timestamp-lock history into this fresh profile or infer agreement from matching helper names. |

The next already-proposed helpers/address/coinbase/template trial can remain
within its existing scope and grant. It need not add timestamp transactions or
non-genesis block admission to answer this consultation. The foreign-v1
projection correction belongs in the writer's subsequent candidate; changing a
frozen overlay changes its digest and requires checking the grant's candidate
binding before executing that changed artifact.

The [platform decision](<private-tracker>/TJS/issues/TJS-2504#comment-3127e4f4-46ae-4e8d-9732-128640aca67a)
grants one exact frozen helper attempt subject to fresh admission; its latest
snapshot fails the 5 GiB memory requirement. The P2P/Mining writer owns that
admission and the subsequent complete native peer/wallet candidate. Privacy's
independent consultation and Core/Security final stages remain separate. Keep
the launch issue blocked with its existing writer-owned unblock action; this
Core ruling resolves the need for a new mapping decision, not those remaining
capabilities or final acceptance. Needs TJ: None.
