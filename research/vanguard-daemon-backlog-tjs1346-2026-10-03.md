# Finite native backlog and drain witness

Blocked on TJ: none. Independent exact-candidate review and lead integration
remain pending. This report is writer evidence, not independent acceptance.

## Changed

The task branch starts at the configured local policy base
`9653842cc358eb8f2864ce5a5478f46de82cfc77`. The accepted load candidate and
P2P rollback gate stay closed and unchanged. Four separate files implement the
new gate: `daemon-backlog.py`, `run-daemon-backlog.py`,
`verify-daemon-backlog.py`, and `test-daemon-backlog-refusals.py` under
`vanguard/`. The native scenario ran from committed source
`36c82383187c405330d63f0db8981db2ec651650`. Later changes correct a refusal
control's recursion and bind seed digests and the bridge's observed socket mode
in the post-run verifier. They do not change the executed native scenario or
its runner. The final exact review candidate is recorded in the Paperclip result.

Each of two fresh native trials funds a sender with 90 regtest blocks. It submits
eight separately constructed type-7 FCMP++ transactions, refreshing the sender
after each admission, while mining stays paused. Both daemon pools must contain
exactly the expected hashes after each arrival and all eight simultaneously
before draining. One generated block drained each observed cohort. The same
trial then queues and drains eight fresh transactions. Selected key images and
their original input identities are disjoint across all sixteen transactions.

The verifier requires distinct native RPC transcripts, disposable wallet seed
digests and transaction identities across trials. It reconciles raw RPC
references with queue snapshots, selected inputs,
decoded CARROT output keys, generated block responses, exact transaction
membership in both nodes' blocks, confirmation heights, wallet outputs and
balances. It accounts for every `generateblocks` and `transfer` call, checks all
four native child exits, container exits, resource limits and source/executable
pins. Queue and completion events are checked against the result. It preserves
the explicit historical-tip limitation.

Independent review TJS-1347, revision `b14c23bb-2a87-47bf-8718-e364c6805e0c`,
returned changes-needed for `6214523a517a1dab338b674e1b2834e8b6f89a79`.
Its original-trial audit passed, while eight rehashed contradictions passed the
old verifier. Corrections bind RPC indices and finite, nonoverlapping timestamps
from construction through pending snapshots and the complete queue to generation,
confirmations and receiver observations. Reused queue/refill snapshots and mining
RPCs are refused. Both nodes' block headers must identify the generated main-chain
block and agree with its body. Each pending decoded response must have the exact
transaction hash, pool state and any returned full native hex. Transfer requests
must pay the recorded receiver address and seeded amount. Final cgroup peaks
replace pre-shutdown samples in the resource table below.

These are verifier, control and reporting corrections. The executed scenario,
runner and original native receipts remain byte-identical. Validation and the
new exact-candidate review are recorded separately from historical execution.

## Source and build evidence

Upstream is `seraphis-migration/monero` at
`e151643c5269c83bf24a83b2548e2493876026b2`, with the exact submodule and Rust
dependency locks in `vanguard/source-lock.json`. The image is
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`;
Rust is `rustc 1.93.0 (254b59607 2026-01-19)`.

The existing primary checkout's primitive source/cache was copied read-only
into run-owned scratch. Its daemon targets were absent, so both native targets
were rebuilt offline under the shared heavy lock. Preparation took 396.451 s,
peaked at 3,042,131,968 bytes, and exited zero with no OOM events. The scenario
runner then used these verified cached binaries. Public preparation commands,
source excerpts, native build logs, exits, counters and hashes are archived
under the evidence bundle's `preparation/`. The primary checkout and other
worktrees were not written.

| Executable | SHA-256 | Bytes |
| --- | --- | ---: |
| monerod | `5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509` | 29,872,608 |
| monero-wallet-rpc | `cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2` | 33,545,392 |

Funding is source-grounded at this exact upstream pin. In
`src/cryptonote_config.h:43`, `CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW` is 60;
the ordinary spendable age at line 48 is 10. Wallet RPC reports selected key
images from the actual input vector at `src/wallet/wallet_rpc_server.cpp:1208`.
Wallet pool processing marks observed pending inputs spent at
`src/wallet/wallet2.cpp:4072`. CARROT's output key field is serialized at
`src/cryptonote_basic/cryptonote_basic.h:87`. The archived excerpts and full-file
hashes in `preparation/source-pins.json` identify these source bytes. No funding,
cohort-size or block-budget adjustment was needed.

## Verified

Both trials observed eight transactions simultaneously on both peer pools twice,
with unchanged tips during each submission cohort. Every one of the sixteen
distinct hashes occurs exactly once in the two drain blocks and is confirmed
at the same height on both nodes. Both pools end empty, native tips converge,
and all daemon and wallet RPC processes exit zero. Trial 1 selected 25 distinct
inputs, trial 2 selected 24. All selected inputs reconcile to original sender
outputs and final spent flags. Each receiver has sixteen distinct unspent CARROT
output identities and balance 16,830,000,000,000 atomic units, with zero unlocked
balance at the final height. Earlier cohort identities persist into the final
wallet view.

| Trial | Cohort | Queue s | Drain s | Backlog s | Full cohort s | Confirmed tx/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 34.529 | 0.391 | 32.659 | 35.060 | 0.228 |
| 1 | 2 | 12.983 | 0.374 | 12.523 | 13.464 | 0.594 |
| 2 | 1 | 31.975 | 0.375 | 30.107 | 32.481 | 0.246 |
| 2 | 2 | 10.783 | 0.358 | 9.930 | 11.235 | 0.712 |

Queue time starts before the first construction and ends after the eighth peer
observation and sender refresh. Drain time includes the final queue snapshot,
block generation, peer convergence and observing empty pools. Backlog time runs
from first origin admission to observing drained pools. Confirmed rate divides
eight by the full cohort duration, including the wallet reconciliation.

| Trial/cohort | Construction s | Origin admission s | Peer observation s | Sender refresh s |
| --- | ---: | ---: | ---: | ---: |
| 1/1 | 9.229 | 0.408 | 24.464 | 0.311 |
| 1/2 | 8.708 | 0.637 | 3.038 | 0.460 |
| 2/1 | 8.875 | 0.413 | 22.200 | 0.356 |
| 2/2 | 7.467 | 0.341 | 2.420 | 0.447 |

These columns sum each transaction's measured phase. Origin admission includes
native validation. Peer observation includes native relay, validation, polling
and scheduling. Neither isolates cryptographic verification cost.

| Trial | Container wall s | Scenario s | Cgroup CPU s | Peak bytes | Final daemon A/B RSS bytes | Generated blocks |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | 76.547 | 73.480 | 44.933 | 933,072,896 | 356,585,472 / 386,760,704 | 92 |
| 2 | 70.027 | 68.759 | 43.185 | 947,458,048 | 359,882,752 / 388,755,456 | 92 |

RSS is sampled, not a per-process high-water mark. Cgroup peak is the whole
container high-water mark from the final `run1.memory` and `run2.memory`
receipts, including shutdown. Pre-shutdown `final_sample` peaks were
871,133,184 and 870,830,080 bytes. Both trials have zero OOM/OOM-kill events, no
non-loopback interface or route, and only loopback listeners. Caps are two CPUs,
4 GiB memory/swap, 256 PIDs, no capabilities and no new privileges. The runner
holds the existing shared heavy lock nonblocking. Both 1,000-second scenario and
180-second phase limits passed, as did the 96-block maximum. Task-owned
containers and private wallet/database directories were removed.

The receipt verifier reports:

```text
PASS_BACKLOG_RECEIPT_RECONCILIATION two_trials=2 cohorts=8+8
PASS_LOCAL_EXECUTABLE_BYTES monerod+wallet_rpc
UNVERIFIED_LIVE_TIPS post-run RPC records are historical claims, including writer /proc hashes
```

The corrected refusal suite passes with 41 refused contradictions and one explicit
historical limit. It rebuilds each mutated manifest and checks that it passes
`sha256sum -c` before invoking the verifier. Named controls cover missing and
duplicate transactions, pending-input reuse, fake pool convergence, a coherent
seven-transaction pool, all five wallet identity fields, a coherent wrong CARROT
output key, child and container failures, count/budget mismatch, zero generated
blocks, a wrong raw generate count, silent cohort reduction, binary and upstream
claims, conflicting containment options and time limits. A wrong local
executable is also refused. A coherent equal-wrong genesis hash across results,
events and raw RPC remains accepted only with `UNVERIFIED_LIVE_TIPS`.
The added controls cover replayed transcripts, reused seed digests, replayed
transaction identities with relabeled seeds, queue/drain chronology and stale
snapshots, timestamps, mining RPCs, block identity/main-chain status, decoded
native identity/bytes/count/pool state and actual transfer destinations. The
original bundle retains its historical 24-control log. Current correction checks
are archived separately under
`research/evidence/vanguard-daemon-backlog-tjs1346-qa-corrections-2026-10-03`.

The first control-suite invocation failed in that final historical-limit
mutation because it traversed RPC reference IDs as tip arrays. The corrected
control limits mutation to actual arrays. Its failed log is preserved alongside
the final check receipts. No third native trial was run.

## Reproduce and interpret

Use a clean checkout of the exact candidate, the pinned prepared private source
and a new output directory. If only the primary primitive cache remains, copy it
into your own run scratch, preserving other workers' paths. The runner rebuilds
missing native targets. CMake configuration must already exist at
`monero-fcmp/build/vanguard`, as in the accepted `build.sh` preparation flow.

```sh
python3 -B vanguard/run-daemon-backlog.py --src "$PAPERCLIP_RUN_SCRATCH_DIR/vanguard-src" \
  --out research/evidence/vanguard-backlog-new
python3 -B vanguard/verify-daemon-backlog.py \
  research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 \
  --src "$PAPERCLIP_RUN_SCRATCH_DIR/vanguard-src"
python3 -B vanguard/test-daemon-backlog-refusals.py \
  research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03 \
  --src "$PAPERCLIP_RUN_SCRATCH_DIR/vanguard-src" --scratch "$PAPERCLIP_RUN_SCRATCH_DIR"
```

The committed evidence was generated with the run-specific scratch path recorded
in its exact command arrays. That scratch is transient; recreate the pinned
cache before reusing the verification commands. Wallet mnemonics are represented
only by hashes, and private keys or databases are excluded from public evidence.

## Assurance limits and next owner

This is native accelerated, fixed-difficulty, valueless regtest with eight
pending transactions at a time. It proves the finite observed workload, not a
capacity ceiling, saturation, sustained arrival rate, production 90/120-second
timing or public-network behavior. It does not independently prove FCMP++
soundness, commitment arithmetic, inflation resistance, anonymity or range-proof
security. No consensus or cryptographic implementation changes were made.

The writer records `/proc/<pid>/exe` hashes while the native processes are alive.
Those are writer-side execution claims, not independent historical provenance.
The post-run verifier hashes actual caller-supplied local executable bytes but
cannot authenticate stopped daemons or their stored RPC state. A reviewer making
live-state claims must bind their own executing binary bytes and current RPC
observations. A wholly coherent forged historical bundle is outside this gate.

Rust & Cuprate Parity owns exact-candidate independent QA through a native
Paperclip child dependency. Findings must be delivered on that review issue;
the writer owns corrections. The studio lead owns final acceptance and verified
local policy-base integration after QA. No external push, release, public P2P,
mainnet, real spending, runtime change or production policy decision is included.

Observed behavior: 90 funding blocks support both native 8+8 cohorts without
pending-input reuse in both fresh trials. TJ decision: local Vanguard engineering
is renewed in this bounded scope; the earlier accepted tasks remain closed.
