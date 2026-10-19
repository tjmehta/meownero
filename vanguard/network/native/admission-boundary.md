# Next native boundary at the pinned source

This source inspection does not establish admission. It specifies the next
runtime check after the reproducible native genesis helper succeeds. Sources
below refer to `seraphis-migration/monero` at
`e151643c5269c83bf24a83b2548e2493876026b2`, already bound by
`../source-bindings.json`.

`src/cryptonote_core/blockchain.cpp:317-389` is the decisive boundary:
`Blockchain::init` changes the network to FAKECHAIN whenever `test_options` is
non-null. The next witness must use actual TESTNET and null test options. It
must not reuse the FAKECHAIN options in `vanguard/sync/process_tests.cpp`.
TESTNET selects its native table and version-one cutoff. On a fresh open LMDB,
initialization obtains genesis from `get_config(TESTNET)`, calls
`generate_genesis_block`, and sends it through `add_new_block`. A standalone
serializer or a call to the torsion helper does not exercise that path.

Only after helper success, combine the existing identity overlay and
activation/height-zero admission patch with its exact native-produced genesis
transaction and actual nonce in an owned source export. Bind every changed
source hash. Keep MAINNET/STAGENET and crypto verifiers byte-identical to their
originals. The selected 9/90 policy is still a separate missing overlay; a
prerequisite admission witness must disclose upstream reward/difficulty where
they are unchanged and cannot be called the final network candidate.

Use native core initialization with `--testnet`, `--offline`, disabled DNS
checkpoints, fast-block-sync disabled, a fresh owned data root, null test
options and no fixed-difficulty substitution. Assert the returned core network
type before inspecting the database. No listener or RPC is required to test
this first admission boundary. Separate daemon peers and authenticated RPC
remain subsequent requirements.

Record native height1 (genesis index0), tip hash and the exact admitted genesis
blob; database `get_block_already_generated_coins(0)` must be zero. The
native database interfaces in `src/blockchain_db/blockchain_db.h` expose
`get_output_key`, output-to-transaction/index lookup and
`get_tree_root_at_blk_idx`. Record the stored output key/commitment and actual
scheduled tree state with those interfaces, distinguishing an immature output
and unavailable root from an admitted mature root. Reopen the same database,
compare accounting/output/root metadata, and record fork state for the next
block at height1. Two independent TESTNET databases must agree before claiming
cross-peer agreement; two serializer runs do not satisfy that condition.

Negative genesis variants require separate fresh databases and attribution to
native rejection: positive reward, wrong height/unlock, empty outputs, invalid
coinbase form and malformed/identity/small-order/torsion-bearing outputs.
RCTNull has no transmitted commitment field; negative commitment controls
belong to the unchanged native helper, not fabricated wire fields. Native
admission, maturity, height-one funding and full two-peer continuity remain
unverified until executed and independently accepted under the existing
Cryptography ruling.
