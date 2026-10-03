# Independent QA of 6214523, revision 1

Blocked on TJ: none.

Verdict: **changes-needed** for exact candidate `6214523a517a1dab338b674e1b2834e8b6f89a79`. The supplied historical native trials satisfy the requested finite workload under independent raw-receipt reconciliation. The verifier accepts eight independently rehashed contradictions that undermine its required acceptance conditions. Six required findings follow, including a separate resource-report correction. Severity describes the local acceptance gate, not a demonstrated consensus or funds-loss defect.

Changed: created independent review scripts, check receipts and this report outside the writer workspace. No repository edits, commits, branch changes or integration. Writer checkout remains clean at the candidate; primary checkout remains `9653842cc358eb8f2864ce5a5478f46de82cfc77`. The lead owns acceptance and integration; the writer owns corrections for [TJS-1346](/TJS/issues/TJS-1346).

## Reviewed evidence and checks

The four downloaded attachment parts match their supplied SHA-256 and byte counts. Their concatenated 31,012,515-byte archive hashes to `fe1620e1e2f39128f9e46988549f819dfb733f550a862e3b34a097182c9aaf92`. Downloaded sources and receipts match this checkout. The writer manifest is `88242884ddf5761e0c6aad8325d86d6fc8ddaff26980c14ba829dc76650a640d`, and every listed file verifies.

Native execution source was `36c82383187c405330d63f0db8981db2ec651650`. `daemon-backlog.py` and `run-daemon-backlog.py` are byte-identical between that execution commit and the reviewed candidate. Review used the final candidate's verifier and controls, not the execution commit's older verifier. The diff from policy base changes only the backlog files, backlog report/evidence and Vanguard README. Existing small-load and rollback sources are unchanged.

Verified upstream `e151643c5269c83bf24a83b2548e2493876026b2`, all five source-lock submodule pins and their cleanliness, Cargo.lock `6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239`, both Rust Git dependency revisions, Rust 1.93.0 and installed builder image `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`. The four semantic source-file hashes match the writer's archived pins. Source inspection confirms the 60-block coinbase maturity window, wallet RPC's actual selected input vector, pool-based spent-input reservation and serialized CARROT output keys.

Copied the existing primitive source/cache read-only into owned scratch, then rebuilt the missing native targets offline under the existing shared heavy lock. This was an incremental target rebuild from copied cached objects, not a clean toolchain reconstruction. Exit 0, 481.721 s, cgroup peak 3,031,072,768 bytes and zero OOM/OOM-kill events. The owned preparation container is removed. Actual rebuilt bytes match both accepted pins:

| Executable | SHA-256 | Bytes |
| --- | --- | ---: |
| monerod | `5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509` | 29,872,608 |
| monero-wallet-rpc | `cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2` | 33,545,392 |

The final verifier accepts the original bundle with `PASS_BACKLOG_RECEIPT_RECONCILIATION` and `PASS_LOCAL_EXECUTABLE_BYTES`, retaining `UNVERIFIED_LIVE_TIPS`. The writer's refusal suite exits 0 with 24 refused cases and one historical-genesis limit. The separate QA script first requires that clean baseline, independently audits raw receipts, then verifies every mutated manifest before invoking the exact-candidate verifier. Eight of eleven new cases wrongly pass; cross-cohort transaction duplication, unaccounted generation and unaccounted transfer correctly fail. Existing load and P2P rollback receipt verifiers also pass. Python source compilation without bytecode writes, repository cleanliness and `git diff --check` pass.

The first QA mutation invocation began before native binaries existed. Its refusals all arose from the missing executable and are invalid as coverage. That failed precondition log is retained. The final QA script adds the passing-baseline precondition and its second invocation is the authoritative result.

## Original outcome against raw receipts

`qa-backlog.py` checks the original bundle independently of the writer's assertions. It reconciles native request/response identity, RPC sequencing, queue/drain chronology, block hashes and main-chain flags, decoded transaction bytes, transfer destinations, wallet output fields and accounting. It also checks the clean facts missing from the production verifier below.

| Required condition | Independent historical observation |
| --- | --- |
| Two fresh trials | Distinct sender/receiver seed digests, distinct transaction sets; 489 and 467 raw RPC rows. Fresh private daemon paths are specified by separate run containers. This is receipt evidence, not authenticated historical execution. |
| Two successive cohorts of eight | Exactly 16 distinct transfers and submissions in each trial, eight per cohort; all transfer and generate calls accounted. |
| Mining paused until eight coexist | Every incremental pool snapshot contains exactly the submitted prefix on both nodes; submission tips stay at height 90 then 91. Both final queue snapshots precede drain RPCs and have the exact eight hashes. No mining RPC is recorded or enabled in daemon launch commands. |
| Native exact-once confirmation | Funding produces 90 hashes. Drain blocks are heights 91 and 92; each cohort's eight hashes occur exactly once in matching main-chain block responses on both nodes. Block hashes, previous hashes and confirmation heights reconcile. |
| Both pools drain and tips converge | Empty before refill and after drain; equal final tip at height 92. |
| Disjoint actual inputs | 25 and 24 unique selected key images respectively, disjoint across all sixteen transactions per trial. Input identities match funded sender outputs and decoded native vin; mature funding heights and final spent flags reconcile. |
| Native FCMP++/CARROT | Every native decoded transaction reports type 7 and CARROT targets. Native response transaction hashes and nonempty hex blobs match constructed/submitted transactions. |
| Receiver identities and balances | Eight then sixteen unique unspent receiver outputs. Amounts, public keys, key images, tx hashes and confirmation heights reconcile; earlier identities persist. First balance 8,350,000,000,000, final balance 16,830,000,000,000 atomic units, unlocked balance zero. |
| Successful completion and budgets | All four child exits, matching exit events and both container exits are zero. Each trial generates 92 blocks below the 96 cap; scenario times 73.480/68.759 s. All 70 measured phases per trial meet 180 s; no OOM events. Recorded commands enforce network-none, two CPUs, 4 GiB memory/swap, 256 PIDs, no capabilities and no-new-privileges. Loopback listeners, routes and bridge socket mode reconcile. |

## Required findings

### F1, high: replayed trial passes the two-fresh-trial gate

Location: `vanguard/verify-daemon-backlog.py:88`, the per-trial loop has no cross-trial freshness check.

Reproduction: `replayed-trial1-as-trial2` replaces `run2/public` with `run1/public`, regenerates the whole manifest and leaves the original valid resource/exit files. The verifier exits 0 and reports `two_trials=2`. Both claimed trials now contain the exact same native RPC transcript, disposable wallet seed digests, transaction hashes and process observations. One recorded trial satisfies a requirement for two fresh trials.

Acceptance: refuse this replay with a named assertion. Bind the existing run evidence across trials sufficiently to reject duplicate native transcripts and wallet/transaction identities produced by this scenario. Add a rehashed control; keep the two original distinct trials passing. This does not require authenticating arbitrary coherent historical forgeries.

### F2, high: RPC ordering does not bind the queue to its drain

Locations: `vanguard/verify-daemon-backlog.py:96`, `:198`, `:203` and `:212`.

Reproduction: `drain-before-eighth-submission` moves the first successful drain RPC before the eighth transfer construction, preserves all request/response contents, rebinds every result/event RPC index and keeps raw timestamps increasing. All other claimed pool and block contents remain unchanged. The verifier exits 0 despite a block claiming to confirm a transaction before construction and despite tip/pool claims taken after an earlier drain. It compares snapshot values without enforcing the native call chronology that establishes paused mining and eight hashes before drain.

Acceptance: bind construction, admission, decoded/pending observations, the final eight-hash queue, generation and confirmations in order. Reject drain before complete queue and stale/reused snapshots, including the supplied control, while preserving original receipts. Check recorded call timing consistently with RPC indices.

### F3, medium: native block identity and main-chain status are unchecked

Location: `vanguard/verify-daemon-backlog.py:216`. The verifier checks the requested hash, decoded JSON and header height, but never requires the response header hash to match that requested/generated hash or checks `orphan_status`.

Reproductions: `peer-block-header-wrong-hash` changes only the peer get_block response header hash to 64 zeroes; `peer-block-marked-orphan` changes only its main-chain flag to orphan. Each rehashed bundle exits 0, although exact block identity or main-chain membership contradicts the generated block and confirmation claims.

Acceptance: bind both nodes' native response headers to the exact generated hash and expected height, and require main-chain status. Refuse both cases with targeted rehashed controls. Preserve native block-body and transaction-membership checks.

### F4, medium: decoded native transaction identity and bytes can contradict admission

Location: `vanguard/verify-daemon-backlog.py:189`.

Reproductions: `decoded-native-tx-wrong-hash` changes only the returned native transaction hash, leaving its requested hash and decoded body intact. `decoded-native-tx-unrelated-blob` replaces only the returned `as_hex` with another transaction's real native blob. Both bundles pass. The verifier binds the request and examines `as_json` without validating the returned transaction's hash, pool state, count or available serialized bytes.

Acceptance: require one decoded response for the requested hash, correct queue pool status and equality of any returned full native hex with the constructed/admitted blob. Add both rehashed controls. This is serialized-byte consistency, not a request for new cryptography or a proof-soundness audit.

### F5, medium: the actual transfer request's recipient and amount are unbound

Location: `vanguard/verify-daemon-backlog.py:177`.

Reproductions: `transfer-request-wrong-amount` increases the first request destination amount by one atomic unit. `transfer-request-pays-sender` replaces the requested recipient with the actual sender address from get_address. Both leave the native response and receiver claims unchanged, rehash cleanly and pass. Only relay/hex flags and response-side amounts are checked, so contradictory sender-to-receiver RPC evidence is accepted.

Acceptance: reconcile wallet address RPCs and require every transfer request's exact destination list, recipient and amount to match the prescribed receiver workload. Add both controls and keep the original raw requests passing.

### F6, low: report understates whole-container peak memory

Location: `research/vanguard-daemon-backlog-tjs1346-2026-10-03.md:104`.

Reproduction: compare the table and its whole-container high-water description against `run1/run1.memory` and `run2/run2.memory`. The report uses the pre-shutdown `final_sample` peaks 871,133,184 and 870,830,080 bytes. The final cgroup peak receipts are **933,072,896** and **947,458,048** bytes. The table understates observed container peaks by 61,939,712 and 76,627,968 bytes. Both actual peaks remain within the 4 GiB cap.

Acceptance: report the final cgroup peaks, or label pre-shutdown samples separately and provide the final peaks. Correct any handoff result that repeats the sampled numbers as whole-container peaks. Native reruns are unnecessary for this correction; the original raw counters supply the values.

## Reproduction and limits

Extract the review evidence archive. From the clean exact-candidate checkout, prepare a new owned copy of the pinned primitive source/cache as in the task reproduction instructions. The archive includes the preparation script, pins and raw build receipts. Then run:

```sh
python3 -B /path/to/qa-backlog.py --repo "$PWD" \
  --bundle research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 \
  --src "$PAPERCLIP_RUN_SCRATCH_DIR/vanguard-src" \
  --out "$PAPERCLIP_RUN_SCRATCH_DIR/new-qa-output"
python3 -B vanguard/test-daemon-backlog-refusals.py \
  research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 \
  --src "$PAPERCLIP_RUN_SCRATCH_DIR/vanguard-src" \
  --scratch "$PAPERCLIP_RUN_SCRATCH_DIR"
```

The independent script records the acceptance/refusal of each mutation; its process exit is not an acceptance verdict. On this candidate the expected adverse evidence is eight accepted contradictory cases and three correctly refused cases. All manifests are rehashed and independently verified first. `counterexamples.json` includes verifier stdout/stderr, exits and manifest digests. The archive includes compact changed-field receipts and the complete deterministic mutation recipe; original raw inputs remain in the pinned writer attachments.

**No fresh live backlog execution was done.** This review rebuilt and hashed local executable bytes, inspected source and independently reconciled historical native records. It did not independently observe the writer's running `/proc/<pid>/exe` or live RPC state. Writer /proc hashes remain writer claims. The coherent equal-wrong-genesis control still correctly advertises `UNVERIFIED_LIVE_TIPS`. The required findings concern inconsistent evidence that the gate can detect, not authentication of a wholly coherent fabricated history.

No inference about capacity, throughput scaling, proof soundness, anonymity, inflation resistance, public P2P, mainnet or release readiness. No policy-base integration, external push, publication, spending, key custody, runtime/model/account/device changes or delegation. The missing named `verification` routing policy was observed in the current routing file; the existing session route was retained.

Observed behavior: original finite 8+8 evidence reconciles, but eight new contradictory bundles are accepted. Next owner is the parent writer for F1-F6 correction, followed by exact-revision independent QA. This review issue is complete when this verdict and evidence are saved; an adverse verdict does not leave the review issue blocked.
