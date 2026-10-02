# TJS-1171 — bounded native two-daemon Vanguard load witness (2026-10-01)

## Scope and lineage

This is a local engineering measurement on the provisional FCMP++/CARROT
lineage. The assigned baseline was `e4eee48e9f56281b8f2c19b6f7847349b45f6db3`;
it was merged into this isolated task branch without editing the primary checkout.
TJS-1038's independent QA (`3a352dc0a696e9178a50b3b23cc1a69aad1b7648`)
gave the restore verifier a bounded PASS and found that equal, wrong tips can
still pass a receipt-only check. TJS-1010/1038 stay closed.

The measured scenario and runner were committed at
`ef796e182c035727921fed92c7473e1ca525a204` (after the initial harness
commit `61b39a0`). The corrected post-run verifier is `0250a2e`; it checks
source hashes against the exact scenario commit recorded in the receipt.
The evidence bundle is committed at
`48e657fb227661b1d81a7482785dd5954ec9eaf1`; its `MANIFEST.sha256`
digest is `714bc667e2aae7e465ec981a6491d1c4f2da255543175ee899e78352c0c073aa`.

The upstream scratch source is `e151643c5269c83bf24a83b2548e2493876026b2`
with the dependency locks in `vanguard/source-lock.json`. The accepted builder
image is `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.
Both executable byte hashes were checked from this task's own scratch source:

| Executable | SHA-256 | Bytes |
| --- | --- | ---: |
| `monerod` | `5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509` | 29,872,608 |
| `monero-wallet-rpc` | `cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2` | 33,545,392 |

## Workload and acceptance condition

Each trial starts two fresh fixed-difficulty regtest daemons and a native P2P
bridge, mines 70 valueless funding blocks, takes a three-second idle sample,
submits one transaction in level 1 and two in level 2, confirming each level in
one block. The amount sequence is selected with Python `Random(1171)`; fresh
disposable wallet mnemonics differ between runs, and only their SHA-256 digests
are recorded. The receiver's three CARROT outputs are restored from its mnemonic
into a new wallet below their first height, rescanned, and compared with the
original. A selected output is swept by the restored wallet and confirmed on
both daemons. A one-block/two-block empty-branch partition and reconnection
then tests reorg recovery and preservation of the confirmed transactions.

The scripted gate requires both run exits zero, exactly the 1/2 transaction
levels, four confirmed transactions, five wallet constructions and at most 90 blocks, no phase over 180
seconds and no scenario over 1,000 seconds. It checks type-7 FCMP++ and CARROT
outputs; origin pool acceptance, peer pool observation, block confirmation,
equal recorded tips, matching restored/rescanned outputs and key images, a
wallet-visible confirmed spend, and recovery to the longer branch. Both nodes
must refuse the changed last byte of an otherwise valid transaction as an
invalid input, and independently refuse a distinct transaction using the same
confirmed key image with `double_spend=true`; state must remain unchanged.
Container limits are two CPUs, 4 GiB memory and swap, 256 PIDs, no network,
no capabilities, no new privileges and no image pull. The runner holds the
shared heavy-work lock nonblocking and uses a 1,100-second inner timeout and
1,200-second outer run timeout. No shared worker was running when the lock was
claimed. Only this run's containers and child processes are stopped.

These bounds constitute a finite integration smoke gate. They are not a
throughput target for a 90- or 120-second production block interval.
Construction is timed separately; origin `send_raw_transaction` time includes
daemon validation and pool admission, so cryptographic verification alone is
not isolated. Inter-daemon pool observation includes relay and verification.

## Two trial measurements

Seconds are wall time except CPU. Level construction, origin admission and
peer-pool times are sums over that level's transactions. The throughput is
confirmed transactions divided by the whole level duration, including block
and wallet observation. The idle sample follows funding and is not a cold
startup measure.

| Run | Level | Txs | Construction | Origin admission | Peer pool | Block admission / convergence | Level duration | Confirmed tx/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | idle | 0 | — | — | — | — | 3.003 | — |
| 1 | 1 | 1 | 2.133 | 1.007 | 5.555 | 0.045 / 0.268 | 9.146 | 0.109 |
| 1 | 2 | 2 | 1.545 | 0.088 | 3.812 | 0.047 / 0.269 | 5.929 | 0.337 |
| 2 | idle | 0 | — | — | — | — | 3.003 | — |
| 2 | 1 | 1 | 1.900 | 1.073 | 3.926 | 0.040 / 0.268 | 7.344 | 0.136 |
| 2 | 2 | 2 | 2.153 | 0.095 | 4.073 | 0.049 / 0.273 | 6.824 | 0.293 |

| Run | Trial wall | Cgroup CPU | Cgroup peak RAM | Final daemon RSS A / B | Restore / rescan | Restored spend construction | Reorg convergence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 63.334 s | 42.587 s | 897,568,768 B | 360,136,704 / 384,651,264 B | 2.093 / 0.490 s | 2.040 s | 1.262 s |
| 2 | 75.742 s | 49.106 s | 883,638,272 B | 358,064,128 / 380,813,312 B | 6.554 / 0.539 s | 1.853 s | 0.507 s |

Final RSS is a sampled state, not a per-process high-water mark. Cgroup peak
is the run's high-water mark. Both OOM and OOM-kill counters were zero. The
receipt contains phase CPU deltas, sampled RSS and memory, exact commands,
transaction IDs, levels, wallet comparisons, recorded tips, and native logs.
The different wallet seeds and host scheduling make the trials comparable
workloads, not byte-identical executions.

## Commands and controls

The local scratch source was copied read-only from an existing pinned cache
into this task worktree. No public network was used in the build or trials.
The completed two-trial command was:

```sh
python3 -B vanguard/run-daemon-p2p.py --scenario load \
  --src build/vanguard-src --out build/vanguard-load-tjs1171-attempt02
python3 -B vanguard/verify-daemon-load.py \
  research/evidence/vanguard-daemon-load-tjs1171-2026-10-01 --src build/vanguard-src
python3 -B vanguard/test-daemon-load-refusals.py \
  research/evidence/vanguard-daemon-load-tjs1171-2026-10-01 \
  --src build/vanguard-src --scratch build
(cd research/evidence/vanguard-daemon-load-tjs1171-2026-10-01 && \
  sha256sum -c MANIFEST.sha256)
```

The scenario command's two containers exited zero and wrote complete receipts.
Its first post-run verifier invocation exited one because the verifier expected
an FCMP input-signature log; the actual native refusal was
`rct signature semantics check failed: simple-style batch verification failed`
on both daemons, paired with RPC `invalid_input=true`. The verifier correction
at `0250a2e` passes both preserved receipts, with:

```text
PASS_LOAD_RECEIPT_STRUCTURE two_runs=2
PASS_LOCAL_EXECUTABLE_BYTES monerod+wallet_rpc
UNVERIFIED_LIVE_TIPS post-run tips are reconciled receipt claims
```

The independent hash-consistent controls produced:

| Control | Result |
| --- | --- |
| Replace local `monerod` bytes with a wrong executable | Refused: `local executable bytes: monerod` |
| Re-sign manifest after making one invalid-proof response `status=OK` | Refused: `invalid_proof refusal` |
| Re-sign manifest after changing both idle tips to the same wrong hash in result and event | Receipt checks still pass, explicitly labeled `UNVERIFIED_LIVE_TIPS` |

The previous `attempt01` was not used as evidence: its level-two sender spend
reused a pending key image and the daemon refused it. Refreshing the sender
after each pool observation fixed that workload construction issue before
the two preserved trials.

## Privacy and integrity assurance map

| Property | Direct local observation | Limit / assumption |
| --- | --- | --- |
| Spend authorization and membership | Native wallet constructs type-7 transactions; both daemon pools and blocks accept them (`daemon-load.py:174-176`, per-run `result.json`). | This is acceptance by the pinned implementation. No independent FCMP membership-proof oracle or soundness result was run here. |
| Commitment and balance integrity | Restored and original wallet output/key-image/balance views match before and after a spend (`daemon-load.py:211-218,258-264`). | Wallet agreement shares the same implementation; it does not independently prove commitment arithmetic or absence of inflation. |
| RCT signature/proof refusal | One changed last byte is refused by both daemons as `invalid_input`; each native log reports `rct signature semantics check failed: simple-style batch verification failed` (run 1 `daemon0.log:1449`, `daemon1.log:1580`; run 2 `daemon0.log:1448`, `daemon1.log:1561`). | The mutation is not an isolated range-proof or FCMP membership-proof vector. The exact proof subcomponent remains unclassified. |
| Key-image linkability | Distinct same-key-image candidate is refused with `double_spend=true` on both daemons in both runs (`result.json.controls.duplicate_key_image`; run 1 `daemon0.log:1549`, `daemon1.log:1743`). | Only a single selected received output and one confirmed-chain conflict were exercised. |
| Privacy | Native CARROT outputs and FCMP++ transaction type are observed, with no public network (`daemon-load.py:174-176`; `containment.json`). | No anonymity-set, network metadata, side-channel or cross-implementation privacy measurement was made. |

The most consequential evidence limitation is **medium for this local gate**:
an internally consistent false tip can pass post-run receipt checks, as the
equal-wrong-tip control reproduces. It prevents an authenticated-chain-state
claim from this bundle. It is not evidence of a consensus exploit. The
unclassified RCT mutation is a **coverage limit**, so this run cannot serve
as a standalone FCMP membership or range-proof negative gate.

## Assurance boundary and remaining gates

The verifier hashes actual executable files in the caller's private scratch,
which rejects a forged binary *claim* when those files are supplied. It runs
after the daemons exit; the stored tips, timings and container records remain
receipt claims, not independently queried live facts. The equal-wrong-tip
control demonstrates this limit. The exact historical executable bytes that
ran were not independently observed by the post-run verifier, although the
runner's build and local byte check agree. No aggregate PASS claims live-tip
or execution provenance.

This is small sequential offered load with a short empty-branch reorg, not a
matched-capacity or sustained-backlog test. The invalid mutation is an RCT
signature/proof failure, not a separately isolated FCMP membership-proof
benchmark. Fee paths, mining payouts, larger input/output sets, public network,
mainnet, external audit and release readiness remain separate gates. Agent
review of this author-owned candidate remains required before acceptance.

**Observed behavior:** both measured local trials met the finite gate.
**Agent proposal:** route exact-commit QA on `ef796e1` + `0250a2e` + `48e657f`
to Rust & Cuprate Parity; require the reviewer to challenge the tip/provenance
limit and whether these smoke thresholds are sufficient for the next load gate.
