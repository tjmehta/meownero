# Funded Core correction source audit

Authority: answered lead interaction47e4e350, resolver8f050fb0/run c7989f95,
2026-11-05T02:30:07Z. Baseline68963718. Native F1 remains NOT_RUN.

| Finding / invariant | Pinned source and correction |
| --- | --- |
| Active CARROT refusal | e151643c wallet2.cpp:10684-10701 chooses CARROT at active version18; wallet/tx_builder.cpp:77-95 filters locked inputs and628-635 throws not_enough_usable_money; carrot_core/exceptions.h:60-64 derives from std::runtime_error. wallet_rpc_server.cpp:1324,3925-3928 uses default GENERIC_TRANSFER_ERROR (-4, wallet_rpc_server_error_codes.h:37). Legacy -37 catch3881 does not apply. |
| Context establishes maturity | Exact b1 miner transaction hash, reward9 MEOW, unlock61; incoming output matches tx hash/amount/block1 and is unspent/locked. N60 get_balance requires strict positive integer total and strict integer0 unlocked. Both peers agree at60 and both pools are empty before transfer. Error -4 with no result, pools still empty, identical peer count/hash/work afterward. |
| Same native request and lineage | Both N60 and N61 use identical transfer bodies with do_not_relay=false. This makes early signing/relay an immediate failure, never a dry-run success. N61 requires identical amount, tx hash, pubkey, key image, global index, block height and spent state with unlocked=true, then the successful response must spend exactly that b1 key image. Native confirmations/fee and decoded FCMP/CARROT checks remain. |
| Effective light mode | e151643c miner.cpp:580-583 enters miner-thread RandomX; rx-slow-hash.c:549-560 calls rx_alloc_dataset(...,1), bypassing only the opt-in check. disabled_flags102-132 reads MONERO_RANDOMX_UMASK;230-234 refuses dataset allocation if FULL_MEM is masked;278-309/330 use full memory only with a dataset. Parent Git tree pins external/randomx at aaafe71322df6602c21a5c72937ac284724ae561; src/randomx.h:46 defines FULL_MEM=4. |
| Every actual daemon launch | node() constructs the explicit funded-only child environment with string mask4. launch_daemon() validates that exact environment before calling the accepted launch helper and records each successful launch. The final witness requires nonempty all-light history and derives light_mode from it. This includes A mining, nonmining reopen, initial B and B restart. Missing/ineffective masks fail before d.launch; genesis ENV/helper remain unchanged. |
| Closed export | coinbase_maturity exports code-4 plus fixed balance/no-result/pool/chain/output-lineage witnesses. No raw balance, tx ID, key image, address, response, credential or error message is added. Existing digest witnesses, signer authority and controller export machinery are unchanged. |

Connected tests use the actual Journey, actual closed-row validator and actual
controller main, with native/Docker/admission/grant effects substituted. The
baseline controls compile only the exact Journey class from the68963718 Git blob
into already guarded globals: no baseline imports, lock helper or native process.
F1 runs baseline against source-derived-4, stops at N60 with zero relayed txs.
F2 holds the old fixture's legacy-37 response solely to traverse the baseline,
then observes its unconditional light_mode=true despite all daemon masks absent.
That F2 bypass is explicit; it is not native maturity evidence.

Negative fixtures cover zero/boolean total, nonzero/boolean unlocked balance,
wrong unlock, wrong code, result plus error, early success, changed pools/chain,
changed eligible pubkey and wrong spent input, as well as prior wrong-network,
confirmation, restore, transaction-type and genesis failures. Every captured
daemon environment must have mask4. Separate controls remove/alter the mask
before A/B start and B restart; no daemon is launched. A corrupted launch-history
entry cannot produce the light-mode PASS row.

Pinned parent and RandomX submodule Git objects, lengths and SHA256 are checked
by the connected suite. New source bindings add only wallet/tx_builder.cpp,
carrot_core/exceptions.h and RandomX src/randomx.h. This changes no compiled input.
The attempted primary GitHub fetch returned cache miss; exact local pinned Git
objects supply source evidence. No claim depends on mutable web content.

Platform reviews this corrected exact source first, then Core F1 semantics, then
Security signer/credentials/export. All three ACCEPTs precede a separately fresh
15000s detached runtime-only reuse grant on published3eedebc0/1b2815e2 authority
with every058ab9ae condition including no-heavy-lock-conflict confirmation. Old
grants remain consumed. Formal Core47234b59/count2 and later Security remain;
no formal reentry until F1 native PASS. launch_ready=false; public_launch=false.
