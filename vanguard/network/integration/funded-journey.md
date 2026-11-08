# F1 funded two-peer journey — source candidate

Current correction authority: lead interaction `47e4e350-879c-40c0-b330-a41c82652b6c`,
resolved by Meownero lead `8f050fb0` in run `c7989f95` on 2026-11-05.
One implementation plus at most one correction, 2,700 seconds from the first edit
in `evidence/funded-core-correction/edit-budget.json`, from clean `68963718`;
only the funded driver/contract, connected tests, bindings/audit, affected
operator/item-5 docs and required inventories/evidence in `vanguard/network/`.
Original F1 authority `058ab9ae` and its unchanged workload/resource constraints
remain binding. Its earlier implementation allowance is spent.

The observable outcome is two native peers at real difficulty, a b1 coinbase
spend across its maturity boundary, a cross-peer payment, private seed restoration
at explicit height0, and a later spend of that exact received output. Source
fixtures do not establish that outcome. Native F1 is **NOT_RUN**. Both launch
flags remain false. The genesis driver, its evidence, the compiled source/overlay,
`build.sh`, `freeze-profile.py` and retained-build identity are preserved.

## Height and operation contract

`b` is a zero-based admitted block index; `N` counts blocks including genesis.
Only A mines. It uses native `--start-mining <public wallet address>
--mining-threads 1`, never a restricted mining RPC, accelerated block generator,
fixed difficulty, changed timestamp, premine or external funding. RandomX's
light mode is enforced by `MONERO_RANDOMX_UMASK=4` in every funded daemon child,
including B's restart. Missing/ineffective masks refuse before launch; the final
light-mode witness derives from every successful daemon launch environment. Each mining phase stops A gracefully and
reopens its same sealed data root without mining. If the observed target was
overshot the attempt fails; it never truncates or rewinds the chain to pass.

| Native boundary | Required observation |
| --- | --- |
| N1 | Fresh private CLI wallets A/B, each setter/store and separate-process getter at height0; authenticated private signer processes |
| N≥3 then at least two more blocks, below60 | Stop B, continue A mining, restart B from its same sealed root while A mines, match count/hash/cumulative work; changed process identity. Initial low-difficulty blocks need no exact N3 stop |
| N60 | b1 reward9 MEOW, unlock61, exact received unspent output, positive total balance and zero unlocked balance; identical transfer request refused with active CARROT -4 and no result, empty pools before/after, unchanged count/hash/work on both peers |
| N60 | Foreign-network payment refused with native -2 before signing/relay, pools unchanged |
| N61 | Same exact b1 output/pubkey/index/key image/amount/height/spent lineage now unlocked; identical native transfer request A→B for1 MEOW succeeds and consumes it |
| N62 | Payment included at b61, exact transaction and block membership/confirmation on both peers; wallet marks b1 spent |
| N62, mining stopped | B's original signer stores/exits/releases; fresh wallet-directory signer restores private mnemonic with restore_height0; refreshed output/pubkey/index/key image/amount/height match. Store/exit, separate CLI getter verifies persisted0, then reopen restored signer |
| N71 | Restored B spends0.1 MEOW, native fee below its remaining1 MEOW funding; response key image must equal the received output |
| N72 | Spend included at b71 with one confirmation on both peers, received output marked spent |
| N73 | b72 is admitted on both peers; final inventory contains exactly the two payments. This additional block honors the lead's literal “b72 confirmed” finish line while preserving the N72 spend witness |

Both confirmations require identical native decoded transaction data, main-chain
block hashes/membership, FCMP++ RingCT type7, CARROT outputs, unlock0, empty ring
offsets and exact fee/input-key-image agreement with the native transfer response.
The N60 and N61 transfer RPC bodies are identical (including `do_not_relay=false`):
N60 must return an error without a transaction result; an early successful transfer
is an immediate failure. No extra dry-run or retry is inserted. The N61 success
then receives native confirmation and exact spent-input lineage checks.
Only SHA256 digests of transaction IDs, outputs and key images are exported.
No seed, address, authentication, request body, native response or console text
is a public witness. Ordinary unlock negatives and independent proof assurance
remain outside this milestone.

The block-count cap is N≤80 including genesis (at most79 non-genesis blocks),
and at most10 ordinary transactions. The driver refuses at N80, on overshoot,
on a semantic mismatch or on its original deadline. It never retries a failed
transfer or continues mining after a failed milestone. The outer controller
retains the single attempt and private failure staging for same-run inspection.

## Source, credentials and reuse

`funded_driver.py` loads the accepted genesis module under a non-entry name and
calls its one-shot CLI, RPC, redactor, process ownership, save/release and manifest
functions unchanged. A/B signer wallet RPC uses native generated per-process
private logins, loopback and SSL-disabled transport inside the network-none
container. It deliberately has no restricted flag because transfers and restore
require signer authority. No auth-disable option exists. The original restricted
observer controls remain in the accepted genesis evidence; F1 is not another
claim that restricted wallets can sign. Wallets never share a file owner.

Mnemonic query/restore bodies and the generated wallet password stay in memory
or private0600 files. Each child has the accepted allowlisted environment;
only daemon children receive RPC_LOGIN and the funded FULL_MEM-disable mask.
The accepted genesis environment and shared launch helper remain byte-unchanged. Private wallet configs hold only their
intended daemon login. Native login files are read with the accepted no-follow,
owner/mode/single-link check. They never enter argv, comments or public JSON.

The controller adds an explicit workload rather than changing genesis semantics.
`funded-runtime.sh` is a separate runtime entry, with the existing cgroup counter
sampling pattern. No build recipe or freezer change is necessary. The exact
input manifest automatically binds these integration files. Additional inspected
native files are bound in `funded-native-bindings.json`, independently checked
against the same upstream Git commit; they do not change compiled identity.

## Pinned source audit

All locators refer to upstream `e151643c5269c83bf24a83b2548e2493876026b2`.
The packet contains original Git-object snapshots and byte hashes.

| Behavior | Exact source locator / disposition |
| --- | --- |
| Native mining options | `src/cryptonote_basic/miner.cpp:96-97,580-583`, OK; miner-thread dataset allocation requires the explicit environment mask below |
| Coinbase window | `src/cryptonote_config.h` CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW=60; accepted overlay retains it |
| Block count versus last locked index | `cryptonote_format_utils.cpp:2102-2117` subtracts1 from explicit block unlock; `wallet2.cpp:7651-7676` compares N≥L+1 and retains ordinary age10; no conversion edit |
| Transfer native estimator and restriction | `wallet_rpc_server.cpp:1261-1320`, unrestricted signer required; priority0/ring_size0 use native adjustment/create_transactions_2; nonzero unlock remains refused |
| Native refusal codes | `wallet2.cpp:10684-10701` selects active CARROT; `wallet/tx_builder.cpp:77-95,628-635` filters locked input then throws `carrot::not_enough_usable_money`; `carrot_core/exceptions.h:60-64` derives from std::runtime_error; `wallet_rpc_server.cpp:1324,3925-3928` maps to generic transfer -4. Legacy -37 catch at3881 is inapplicable. -4 alone is never a maturity proof; surrounding balance/output/pool/chain and later exact-input success are required |
| RandomX light-mode enforcement | `rx-slow-hash.c:102-132,230-239,278-309,330,549-560`: UMASK disables FULL_MEM before miner-thread allocation despite ignore_env=1; pinned RandomX submodule `aaafe71322df6602c21a5c72937ac284724ae561`, `src/randomx.h:46`, FULL_MEM=4. Every funded launch passes exactly string4; no compiled change |
| Input lineage | `wallet_rpc_server.cpp:1184-1217` fill_response exposes spent key images; `2278-2329` incoming_transfers exposes exact output/key image/index/height/spent/unlocked state |
| Private recovery | `wallet_rpc_server.cpp:2333-2385` mnemonic query; `4133-4342` wallet-dir restore validates seed and sets/re-writes req.restore_height; password/seed are RPC data, never child argv |
| Wallet server options | `wallet_rpc_server.cpp:5201-5212` registers wallet-file, wallet-dir and RPC options; `5039-5043` rejects wallet-dir with password-file, so the empty restore server omits password-file and receives its password only in the private restore body. Later file reopen uses password-file. daemon-ssl belongs to wallet2 options; accepted CLI option audit is reused |
| Confirmations | `core_rpc_server_commands_defs.h:406-464,1381-1415`; `core_rpc_server.cpp:1074` reports N−b confirmations; main-chain block hash and transaction membership checked on each peer |
| Positive transaction format | `rctTypes.h:308` type7; `cryptonote_basic.h:798` JSON carrot_v1 tag; existing `vanguard/daemon-cross-host.py:147-164` provides the reused native binding pattern, not funding commands |
| Checkpoints | **Source-established N/A for this runtime:** `cryptonote_core.cpp:363-370` installs defaults only for MAINNET, and `265-267` returns immediately outside MAINNET. Upstream checkpoints.cpp contains TESTNET entries, but this core path does not install them. Formal Core concurrence pending |
| Foreign DB | **Upstream limitation:** `blockchain.cpp:376-398` generates genesis only for an empty DB and does no genesis comparison in the nonempty branch. Accepted launcher-manifest refusal plus the one-profile/one-data-dir operator rule mitigate accidental reuse; no startup fix or native foreign-DB refusal claim. Formal Core disposition pending |

## Review and runtime prerequisites

Platform source consultation comes first, then Core source consultation limited
to F1 maturity/mining/no difficulty or timestamp manipulation, then Security on
signer credentials/export. A repeated finding failing twice returns to lead.
Formal Core stays at changes_requested/count2 until the complete post-F1 submission;
later formal Security and lead integration remain open. No stage is advanced here.

Only after all three source acceptances may Platform issue one separately fresh,
exact runtime-only grant bound to the committed candidate/runner/inputs/packet.
It must bind published authority3eedebc0 and retained manifest digest1b2815e2,
the original published retained root, at least48h validity, one use, detached
session, and explicit confirmation that no other heavy-lock workload is scheduled
in the 15,000s window. It does not displace [TJS-1882](/TJS/issues/TJS-1882).

The wall cap is15,000s:14,700 work including staging/runtime and300 exclusive
outer cleanup. The inner driver leaves30s for its own process cleanup. Container
caps remain2CPU/4GiB/no swap/256PIDs; sampled host caps1GiB RSS/4,000CPU-s/32PIDs.
Both admissions require load≤9 in all three windows,5GiB available RAM and20GiB
backing disk; owned disk15GiB, abort below4GiB free. Same first-admission rules,
one-use output marker, bounded foreground waits and no preparation round apply.
See [the current operator addendum](funded-operators.md) and
[item-5 integration requirements](funded-integration-requirements.md).

After F1 native PASS, reconcile the full matrix, submit formal Core then Security,
and request accepted-only lead integration. Source fixture success is not native
PASS, independent native acceptance, integration or public release.
