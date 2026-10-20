# Core consultation response

The October 20 Core source ruling is incorporated. This remains an uncompiled,
non-public candidate preparation, not final acceptance. The ten-file overlay
SHA256 is `32c40224dcd618995ef4d846cab411a85783314da79a803ed16074241780312c`.
The prior overlay was
`0f971c34e3401f2faf85fa98862f7f28698af3b5ee28765c17657f8bee5eb044` at
`ebb953530ecfc3bf712e9cb08e042cf11b7f272c`. The profile remains
`56a25f173448b3caa34ae9bb29761f5d467376df4470902fd89824ddc11fe4e8`.
Upstream, Cargo/toolchain pins, genesis, settled 9/90 policy and existing native
genesis evidence are unchanged.

## Narrow correction and evidence

The two projections in `Blockchain::get_adjusted_time` now share a local target
selected by `m_nettype == TESTNET ? get_difficulty_target() : DIFFICULTY_TARGET_V2`.
Foreign v1 difficulty continues to use60 seconds, while its adjusted-time RPC
retains the upstream120-second projection. This corrects an RPC behavior
regression. It is not evidence of a v1 timestamp-spend consensus defect.

Only `blockchain.cpp` differs between the prior and corrected generated source.
The [exact delta](evidence/projection-correction/projection-only.diff),
[original/changed hashes](evidence/projection-correction/policy-overlay.json), and
[correction receipt](evidence/projection-correction/correction.json) bind it.
The runner checks this new receipt before applying the overlay. Existing
`evidence/selected-policy/` and Core's independently committed consultation files
remain historical evidence. Core's checker reproduces its original reviewed
overlay using the tools at `c4e0dde0d38e100d9541c5c0f7ba1c5285bc8de5`; running that
historical checker against this changed generator correctly reports overlay drift.

| Invariant | Source/arithmetic observation | Native limit |
| --- | --- | --- |
| Dedicated projection | Regular 90-second window gives 1700005400; flat/max/median branches give 1700000090/1700001090/1700002745 | Linked execution not run |
| Foreign projection | Core's v1 counterexample stays 1700003660; old generic helper gives 1700003600 and is detected as a known-bad control | Native foreign-selector differential not run |
| Startup and sample order | Function comparison retains the wall-clock path below 60 samples, median sorting before `back()`, and final minimum; reordered-median control fails | Native counts59/60 and non-monotone DB windows not run |
| Inherited unlock domain | Existing v17 Rule 8 and v18@1 activation stay unchanged; no verifier or lock-mapping file is patched | Funded unlock0 control and specific nonzero verifier refusals not run |
| Coinbase | Exact h+60 check and genesis unlock 60 stay unchanged | Height 1 unlock 61 admission and maturity not run |

All 38 bound source files match their pinned Git objects. Fourteen policy tests,
seventeen existing tooling checks and six provenance checks pass. Full patch
apply/reverse reproduces every changed byte. Adjacent logs and JSON retain the
results. The arithmetic is a Python reference and source comparison, not native
consensus, wallet, proof, database or P2P execution.

Primary revision locators are
[upstream projection](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/src/cryptonote_core/blockchain.cpp#L4323),
[Rule8](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/src/cryptonote_core/tx_verification_utils.cpp#L349),
and [median sorting](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/contrib/epee/include/misc_language.h#L53).
Browser retrieval of the first two failed with cache misses during this run;
claims were checked against local pinned Git objects and working bytes.

Reproduce the current checks using fresh task-owned paths:

```sh
python3 -B vanguard/network/test_policy.py --source "$PINNED_UPSTREAM_SOURCE" \
  --scratch "$TASK_PRIVATE_SCRATCH" --evidence "$TASK_PRIVATE_SCRATCH/correction-checks-new"
python3 -B vanguard/network/test_network.py --source "$PINNED_UPSTREAM_SOURCE" \
  --scratch "$TASK_PRIVATE_SCRATCH" --evidence "$TASK_PRIVATE_SCRATCH/tooling-checks-new"
python3 -B vanguard/network/test_admission.py --scratch "$TASK_PRIVATE_SCRATCH"
```

## Unlock ruling and remaining native contract

Retain inherited ordinary-transaction unlock 0 at v18 and exact coinbase h+60.
Do not add an epoch, reinterpret timestamps, pass network selectors into FCMP
metadata or change persisted lock buckets. Ordinary output created at h=1 has
last-locked index 10 and is eligible at wallet block count 11; coinbase h=1 has
last-locked index 60 and is eligible at count 61. Root existence alone does not
prove spend eligibility. This reasoning is bounded to coinbase heights below
499999940, the inherited height/timestamp representation limit documented by Core.
It adds no consensus height cap or unbounded-lifetime assurance.

Core's full [native acceptance matrix](core-review/lock-consultation.md) remains
required for funded unlock 0/nonzero controls, pool/supplement/main/alternative
admission and caches, wallet transfer/split/sweep routes, exact coinbase, early
and mature spends, projection windows, persistence/reconstruction and isolation.
The helper-only workload must not acquire those additional scopes implicitly.
The independent [Privacy ruling](privacy-response.md) now confirms this direction
and the same foreign-selector correction. Both source consultations are complete.
Neither replaces the native checks or final Core/Security review stages.

## Native attempt and authority

No native runner, build, upstream source export, Cargo staging, container,
listener, wallet or payment was started for this correction. The previous fresh
admission at 06:26:08 UTC had 3800657920 available bytes, below 5368709120 required.
It is historical evidence, not a current reservation or admission result.

Grant `3127e4f4-46ae-4e8d-9732-128640aca67a` remains unconsumed and binds the old
artifact. The platform owner must explicitly update its artifact binding before
the writer uses the corrected runner and overlay. Request only the same one
900-second offline cold helper/template attempt, one 2 CPU/4 GiB/256 PID container,
one compiler job, original lock inode, two fresh-root 60-second invocations, and
the same 13,608 reward vectors/39 address checks/24 coinbase constructions plus
target 90/v18, height-one template and positive reset control. No native time
test, non-genesis admission/mining, daemon listener, wallet or peer exposure is
added. Fresh memory/disk/load/collision and original-lock admission must still
pass. Failure consumes the finite attempt; there is no retry or reservation.

P2P/Mining owns securing the exact rebind and then fresh admission, the bounded
attempt and cleanup evidence. Final peer/bootstrap/persistence/recovery and
cross-node receive/payment/restore/later-spend integration remain open, followed
by native Core/Security stages and accepted-only lead integration. Public launch
stays disabled. Needs TJ: None.
