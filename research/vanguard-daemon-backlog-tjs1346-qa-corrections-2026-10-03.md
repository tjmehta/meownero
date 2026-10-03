# TJS-1346 QA correction handoff

Blocked on TJ: none. The corrected candidate requires independent review.

TJS-1347 revision b14c23bb-2a87-47bf-8718-e364c6805e0c found six required corrections on 6214523a517a1dab338b674e1b2834e8b6f89a79. Its independent audit reconciled the original two native 8+8 trials. This handoff addresses that verdict without changing the executed scenario, runner or historical native receipts.

| Finding | Correction | Regression evidence |
| --- | --- | --- |
| F1, high | Reject duplicate canonical RPC transcripts, wallet seed digests and transaction identities across trials. | Full trial replay, coherent seed reuse, replay with altered seed labels and shifted timestamps. |
| F2, high | Require finite sequential RPC times and strictly ordered references from construction/admission through pending snapshots, full queue, generation, confirmation and receiver observation. Reject reused queue/refill snapshots and mining RPCs. | Reviewer drain-before-eighth-submission recipe, snapshot reuse, timestamp inversion/nonfinite values and mining RPC. |
| F3, medium | Bind both native block header hashes, heights, main-chain status and previous hashes to generated blocks and decoded bodies. | Wrong peer hash and orphan-status controls. |
| F4, medium | Require one pending decoded response with the requested transaction hash and pool state. Bind any nonempty full native hex to construction/admission bytes. | Wrong hash, unrelated native blob, wrong pool state and duplicate response controls. |
| F5, medium | Reconcile sender/receiver address RPCs and require the exact receiver destination list and seeded amount. | Wrong amount and transfer-to-sender controls. |
| F6, low | Report final cgroup peak counters, including shutdown. | Original run1.memory 933,072,896 bytes and run2.memory 947,458,048 bytes. Both remain below 4 GiB. |

The previous 871,133,184/870,830,080-byte values are labeled as pre-shutdown samples. The corrected report provides final peaks; native reruns are unnecessary for the reporting correction.

The original native evidence manifest remains 88242884ddf5761e0c6aad8325d86d6fc8ddaff26980c14ba829dc76650a640d. It records two historical trials, 16 distinct transactions per trial, 92 generated blocks per trial, disjoint selected inputs, exact peer pools and confirmations, sixteen receiver outputs and successful native child exits. Local executable hashing and historical RPC reconciliation do not authenticate live stopped daemons. UNVERIFIED_LIVE_TIPS and coherent-history limitations remain explicit.

The writer owns these corrections and their test results. Rust & Cuprate Parity owns independent exact-candidate re-review. The studio lead owns final acceptance and verified local policy-base integration after QA. No public-network, release or cryptographic soundness claim is made.

Validation passed with real local executable bytes. The expanded writer suite refused 41 rehashed contradictions and retained one explicit historical-tip limit. The unmodified independent QA recipe was rerun by the writer: the original raw audit passed and all eleven counterexamples were refused, including all eight that previously passed. This rerun is a regression check, not independent acceptance of the corrected candidate. Accepted load and P2P receipt verifiers also passed. All recorded check exits are zero; Python compilation without bytecode writes and source/document whitespace checks pass.

The correction run rebuilt both missing native targets offline in an owned copy of the pinned primitive cache. Preparation exited zero in 640.678 seconds, with a 2,970,746,880-byte final cgroup peak and zero OOM/OOM-kill events. Both actual executable byte sizes and SHA-256 values match the accepted pins. This was an incremental target rebuild, not a fresh toolchain reconstruction. No new native backlog trial was run.

Correction evidence is archived at `research/evidence/vanguard-daemon-backlog-tjs1346-qa-corrections-2026-10-03`. It preserves raw preparation commands/logs/exits/counters, actual local executable pins, checked source hashes, writer command/exit receipts, expanded refusal output and the unmodified QA mutation recipe with its writer rerun results. Original native execution evidence remains at `research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03`.

Reproduce from the exact corrected candidate with a new owned copy of the pinned source/cache and real executables:

```sh
python3 -B vanguard/verify-daemon-backlog.py \
  research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 --src /absolute/private/vanguard-src
python3 -B vanguard/test-daemon-backlog-refusals.py \
  research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 \
  --src /absolute/private/vanguard-src --scratch /absolute/owned/scratch
python3 -B research/evidence/vanguard-daemon-backlog-tjs1346-qa-corrections-2026-10-03/writer-rerun-qa/qa-backlog.py \
  --repo "$PWD" --bundle research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 \
  --src /absolute/private/vanguard-src --out /absolute/owned/new-qa-output
```

The QA script requires a passing baseline and records its mutation results. Independently require all eleven counterexamples to have nonzero verifier exits; that script's own zero exit is not an acceptance verdict. Source pins identify the tested code. The exact clean committed candidate and review dependency are recorded in the revisioned Paperclip result and native bridge result.md. The configured local policy base remains `9653842cc358eb8f2864ce5a5478f46de82cfc77`; lead integration is pending after independent QA.
