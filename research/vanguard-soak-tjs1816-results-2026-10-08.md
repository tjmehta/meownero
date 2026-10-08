# TJS-1816 native payment and recovery writer results

Two entirely fresh native ARM64 trials passed on build-mac under frozen protocol revision 5. Each ran for more than 1,800 measured seconds after warmup, confirmed 32 exactly-once workload payments in four depth-eight cohorts, and confirmed one additional restored-wallet spend. Both completed persistent restarts, queued reconnect, a controlled reorg and native rejection controls followed by a healthy cohort. The two-trial verifier passed against the actual ARM executable bytes; all 31 rehashed refusal invocations were refused after a passing baseline.

These are writer results awaiting independent acceptance by `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`. Parent local integration, the isolated cross-host follow-up and group delivery remain pending. No accepted-candidate or next-step readiness claim is made here. Offline reconciliation retains `UNVERIFIED_LIVE_TIPS`.

## F1 export correction awaiting independent closure

The independent reviewer found four populated ring-database files in candidate `04493d6e8eb7734b9b833bb97839f9cea0a2f146` and withheld acceptance. The prior report's database-free claim and public-export privacy PASS were incorrect. That 60-file archive, its package index attachment `3d16b8fb-fe4c-40e5-bd91-5830fe011bb7`, and its original checks/audit are superseded for acceptance. Historical bytes remain in the prior commit; no old archive or database content is included in the new export or incremental bundle.

The exporter copies only 56 named UTF-8 text receipts/logs, checks each against the original manifest, and creates a deterministic regular-file archive with a fresh manifest. It never recursively publishes the native output. The public checker rejects extra files/directories, symlinks, non-regular files and binary content, including database bytes under a permitted log name. The frozen native runner still retains full state privately. Future reproduction must run the explicit exporter before verification or upload.

[export-transformation.json](evidence/vanguard-daemon-soak-tjs1816-2026-10-08/export-transformation.json) records the original manifest/archive hashes, the four excluded names and hashes, and all 56 retained hashes. Both trials' RPC/event/sample/wire/result files and all other permitted evidence match their original bytes. The original private remote artifacts were read without modification. The existing trials are retained under the reviewer's stated acceptance condition; no native rerun or new native-duration credit is claimed.

The corrected baseline passed with the same actual ARM executable files copied from build-mac through strict SCP. All 31 rehashed invocations were refused after a passing baseline. The three new invocations insert a synthetic ring database, an unlisted wallet cache, and database bytes disguised as an allowed log. Exporter checks also prove unknown files are omitted and disguised binary input is refused. The actual old 60-file package is refused by the corrected public boundary. The historical P2P baseline/refusals passed again; load/backlog gates again refused substituting ARM bytes for x86 pins. All 12 accepted legacy gates remain unchanged. Full old x86 suites remain NOT_RUN; the independent reviewer explicitly allowed that bounded gap for this ARM milestone.

F1 remains open until the existing reviewer independently closes it on the same stage. Parent integration and next-step readiness remain pending.

## Frozen code and execution

Accepted base: `72e572bd2c6725eb59d5598852d782185e225504`. The owned branch is `TJS-1816-meownero-vanguard-longer-payment-and-recovery-tests-on-build-mac`. Dirty dev and build-mac primary checkouts were preserved. No accepted load/P2P/backlog gate was changed.

Native candidate: `978d2d10b0eb48c6143c09ccf494da640804df0a`. Original checker candidate: `b6c46cd8526b34822ecdbd62a2c5b84ec3372cec`. Corrected export/checker candidate: `f26a14956dc73b63c821260d48527ce6b50d68e9`. The correction adds an explicit public text-file export boundary, database refusals and reproduction instructions. The final evidence commit preserves every measured runner/logger/protocol byte and every retained raw trial byte; the offline verifier and refusal script change to enforce the export boundary. Its exact commit and downloadable bundle hashes are bound in the Paperclip handoff after freezing, rather than self-referenced inside this commit.

The [frozen protocol](vanguard-soak-tjs1816-protocol-2026-10-08.md) SHA256 is `e7fa5c4a908a6f13e1bec802b539c11e647cce1fba2e5f323251c140b8d98d8e`. Board document `test-protocol`, revision 5 (`ff455711-f58c-4eeb-b9fe-419e4352ef8a`), was published at 16:55:19Z before the native runner started at 16:55:50Z. [Publication receipt](evidence/vanguard-soak-tjs1816-repair-2026-10-08/protocol-v5-publication.json).

The new runner extends the existing private native P2P harness with timed recovery phases, chronological redacted RPC/events, live generation identities and cgroup sampling. The verifier binds native bytes, exact main-chain blocks, CARROT recipient keys and amounts, inputs, fees, restore history, negative controls and cleanup. Portability changes use the cached ARM image and pinned task-owned Rust toolchain; only the transient bridge socket uses a private 1 MiB tmpfs. Persistent wallet/chain state remains in the private bind mount.

## Native results and resources

| Observation | Trial 1 | Trial 2 |
| --- | ---: | ---: |
| Measured duration, seconds | 1800.180243631 | 1800.172313108 |
| Warmup excluded, seconds | 31.748608 | 29.653463 |
| Workload payments | 32 | 32 |
| Additional restored spends | 1 | 1 |
| Generated blocks, cap 210 | 200 | 200 |
| Chronological RPC rows | 2805 | 2843 |
| Resource samples | 186 | 186 |
| Start cgroup memory, bytes | 942698496 | 944427008 |
| Measured-end cgroup memory, bytes | 1198067712 | 1195782144 |
| Final shutdown peak memory, bytes | 1198231552 | 1195913216 |
| Current-memory fitted trend, bytes/minute | 5182071.39 | 5075804.20 |
| Measured cgroup CPU, seconds | 45.484620 | 45.398825 |
| Final cgroup CPU, seconds | 79.884555 | 76.825296 |
| Child generations exited 0 | 9/9 | 9/9 |
| Every memory/OOM event counter | 0 | 0 |
| Final native pools | Empty on both | Empty on both |
| Matching final main-chain tip height | 199 | 199 |
| Runner/container exit | 0 | 0 |
| Exact owned container absent | Yes | Yes |

The nine generations in each trial are daemon0/daemon1, senderA/senderB, recipientA/recipientB, restarted senderB, restarted daemon0 and the restored wallet. Every generation has a live executable hash, command, PID/start identity and controlled exit record. Both `cleanup_errors` lists are empty. Start/end memory is sampled while the workload is live; final peak and CPU include shutdown. Every `low`, `high`, `max`, `oom`, `oom_kill` and `oom_group_kill` counter is zero. The fitted memory trend includes newly generated chain/wallet state and caches; this experiment does not isolate a leak.

The final hashes are `1c2da50d7760827c6d384b23023b5862fbe6fd46f6841ab8f41dffa24cda5f31` (trial 1) and `d8c29f665c797c6ecc270caacc459fef68bd2a36e392f1f52e2da323e1850782` (trial 2). Each trial's two nodes agree. Both exact test containers (`tjs1816-soak-60462-1` and `tjs1816-soak-60462-2`) were removed. Overall native execution ended at 17:56:56Z with exit 0 and wall time 3,666.099 seconds; build/warmup/waiting are not throughput evidence.

| Per-payment timing, seconds (median / p95 / maximum) | Trial 1 | Trial 2 |
| --- | ---: | ---: |
| Construction RPC | 0.6522 / 0.8939 / 1.5235 | 0.5019 / 0.7939 / 1.7589 |
| Origin admission RPC | 0.0185 / 0.0438 / 0.9074 | 0.0174 / 0.1046 / 0.8910 |
| Admission to first peer-pool observation | 4.1813 / 6.5943 / 7.5738 | 4.5016 / 7.5747 / 7.7872 |
| Admission to confirmation observation | 6.8773 / 42.2463 / 44.0366 | 7.8685 / 42.1339 / 45.7774 |
| Construction to confirmation observation | 7.5713 / 43.0332 / 45.5793 | 8.4627 / 43.9128 / 46.5706 |

Cohort work durations and observed completion rates, in cohort order:

- Trial 1: durations 6.2854, 45.7869, 11.6030, 43.1953 seconds; rates 1.2728, 0.1747, 0.6895, 0.1852 payments/second.
- Trial 2: durations 5.9819, 44.1180, 12.0134, 46.7268 seconds; rates 1.3374, 0.1813, 0.6659, 0.1712 payments/second.

These rates use each cohort's actual construction, queue and drain work, excluding the scheduled idle intervals. Observation delays are bounded by RPC sampling and include planned queuing/partition delays. They are neither network latency measurements nor sustained-capacity claims. Detailed values and the calculation script are in [summary.json](evidence/vanguard-daemon-soak-tjs1816-2026-10-08/summary.json).

## Recovery and rejection evidence

Each trial scheduled cohort 1 at measured start, persistent sender-B wallet restart and cohort 2 after minute 6, persistent node-A restart and partitioned cohort 3 after minute 12, controlled competing branches after minute 18, and restore/negative controls/healthy cohort 4 after minute 24. Reconciliation and heartbeats continued past minute 30.

The partitioned cohort first filled A's pool with exactly eight transactions while B remained empty. Reconnect completed the native handshake, then one explicit native `relay_tx` request retried those exact txids; both pools held the exact queue before mining resumed. This measures explicit retry recovery, not automatic relay-timer behavior. No peer-pool injection was used.

The reorg started from matching empty-pool tips, generated one branch block on A and two on B, and made both nodes adopt B's exact longer tip. Raw orphan evidence is from node A, which held the losing branch. Every prior payment was rebound to the main chain with unchanged wallet credits.

A fresh restore of recipient A matched the original address, outputs, amounts, balances and spent flags. Both the redacted restore request and native echoed-seed response digest match the original wallet digest. A later valid spend of a received output was confirmed on both nodes. Two distinct transactions shared that restored input key image; the second was rejected with the native double-spend indication after the first was confirmed.

Both nodes also rejected malformed transaction encoding and an otherwise serialized transaction whose final byte was XORed with 1, with unchanged pool/tip observations. The latter is labeled `altered_transaction`; it is not a signature-only mutation or a cryptographic soundness test. All these controls were followed by the healthy eight-payment cohort 4. Full RPC responses and before/after observations are linked from each result's `controls`, `reorg`, `restore`, `restored_spend` and `cohorts` objects.

## Provenance and containment

Host build-mac is macOS 26.5.1/Darwin ARM64. Docker 29.5.2 runs Linux/aarch64 with cgroup v2 and 6,197,448,704 bytes VM RAM. Actual available VM RAM exceeded 5 GiB before each 4 GiB trial; final host free disk was 105,150,214,144 bytes. The saved Colima profile SHA256 remains `953069eb536626c5b04906c9122d3f35d54e4d3091c50f5bc4adf7cc7f627697`.

All heavy build/native work ran on build-mac through strict-host-key `ssh build-mac`. The original upstream commit `e151643c5269c83bf24a83b2548e2493876026b2`, five submodule pins and Cargo.lock SHA `6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239` are unchanged. The cached ARM image is `sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b`. GCC 13.3, CMake 3.28.3 and official Rust 1.93.0 archive hashes are recorded in preparation/build receipts and the protocol. No ARM bytes are claimed to match accepted x86 executable pins.

| ARM64 executable (ELF machine 183) | Bytes | SHA256 |
| --- | ---: | --- |
| monerod | 27832112 | `b4becc6efbdc922f0fac93a0730de6f9397c1637a60b95630140e9ace677b920` |
| monero-wallet-rpc | 31426016 | `9ab761894ace8a84e3563619ba978e4d8a2c86ee07d7d38e5a5c8c364c4c450b` |

Each trial used `--pull=never --network=none --cap-drop=ALL --security-opt=no-new-privileges --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 --ulimit core=0`, no published ports, no route and loopback native listeners. Native Levin traffic used the mode-0600 private AF_UNIX bridge. The shared nonblocking heavy-work lock serialized both trials; deadlines and per-phase/block limits stayed enforced.

Final read-only inspection found no Docker containers and the heavy lock available. Existing dockerman `Runner.Listener` PID 10739 (Oct 4 09:13:03 start) and unrelated simulator `deviceaccessd` PID 75180 (Oct 8 02:22:27 start) remain intact. Colima stays running for the existing CI consumer. Task-owned caches/source/evidence and the reversible stale-entry quarantine remain; no host restart, force-stop, global settings/auth/network policy change or destructive cleanup occurred. [Final observations](evidence/vanguard-soak-tjs1816-repair-2026-10-08/final-live-v5/observations.jsonl).

## Excluded attempts and regression limits

`soak01` failed before warmup or any native process/payment because Colima virtiofs rejected chmod on the bind-mounted socket. Its exact container was removed. Revision 4 put only that transient socket on capped private tmpfs.

`soak02` trial 1 passed its native scenario, but a prepublication privacy check found that wallet restore echoed its mnemonic in the native response. The entire trial set is excluded. The exact second owned container was stopped after 425 seconds, removed and recorded with exit 143/transport exit 1. The original unredacted RPC is retained only in a mode-0600 remote private directory; it was not transferred or uploaded. A sanitized diagnostic hash is recorded. Revision 5 redacts the echo and checks both restore digests. `soak03` then created two entirely fresh trials, rather than reusing the earlier pass. These exclusions are visible failures/limitations, not acceptance credit.

All 12 accepted source/runner/verifier/refusal/source-lock gates are byte-identical to the accepted base. The old P2P receipt baseline and refusal suite passed against the current candidate, as historical regressions. Old load/backlog gates correctly refused substituting the ARM binaries for their pinned x86 bytes. Full old x86 load/backlog refusal suites are **NOT_RUN** because those original executables are absent; the earlier P2P `--src` unrecognized-argument diagnostic is not coverage. Independent review must decide whether this explicit gap blocks the bounded ARM writer milestone without reopening accepted work.

## Protocol matrix

PASS means the writer's measured evidence and applicable offline checks passed; it does not mean independent acceptance. The machine-readable [matrix](evidence/vanguard-daemon-soak-tjs1816-2026-10-08/protocol-matrix.json) records the same rows.

| Row | Requirement | Writer status | Evidence |
| ---: | --- | --- | --- |
| 1 | Published frozen revision 5 before fresh trials | PASS | Board revision 5 published 16:55:19Z; native start 16:55:50Z; protocol-v5-publication.json. |
| 2 | Exact native source/ARM64 image/toolchain/binary provenance | PASS | receipt.json, preparation/receipt.json and live/final probes; ARM64 machine 183; actual binary hashes. |
| 3 | Fresh independent workload and disposable-wallet seeds | PASS | Verifier rejects workload/wallet/tx replay; eight unique wallet seed digests and addresses; freshness audit. |
| 4 | Trial 1 at least 1800 measured seconds after warmup | PASS | run1/public/result.json: 1800.180243631 s after 31.748607991 s warmup. |
| 5 | Trial 2 at least 1800 measured seconds after warmup | PASS | run2/public/result.json: 1800.172313108 s after 29.653462992 s warmup. |
| 6 | 32 confirmed exactly-once payments per trial | PASS | Both result.transactions plus chronological RPC and final_bindings: 32 each, 64 total; two additional restored spends. |
| 7 | Four depth-eight queued cohorts with paused mining and bounded drains | PASS | Four cohort records per trial, exact queues before mining; 200 generated blocks per trial below cap 210. |
| 8 | Both-node tx bytes/hash/block/previous-hash/main-chain binding | PASS | Both result.final_bindings and get_transactions/get_block RPC rows; exact membership, previous hash and non-orphan status. |
| 9 | Exact recipient CARROT key/destination/amount and principal/fee/input accounting | PASS | Construction RPC destinations/amounts/fees/key images and recipient CARROT output keys; native input/credit reconciliation. |
| 10 | Persistent sender wallet restart and later payment | PASS | wallet_restart before/after wallet RPC observations, same files/address/state and later cohort 2. |
| 11 | Persistent daemon restart with same state and live executable identity | PASS | daemon_restart before/after tips, generation 2 live identity, same persistent chain command. |
| 12 | Partitioned full queue, reconnect and explicit native relay retry | PASS | cohort 3 isolated full A queue, empty B queue, reconnect handshake, explicit relay_tx and exact peer queue. |
| 13 | Controlled partition, longer-chain rejoin and losing-branch orphan | PASS | reorg records and raw losing-branch orphan RPC on node A; exact longer B tip adopted on both. |
| 14 | Restored recipient history and later confirmed spend | PASS | restore request/echo digests match original; restored history/output states and restored_spend bindings. |
| 15 | Both-node malformed transaction rejection without state change | PASS | controls.malformed: native non-admission and unchanged pools/tips on both nodes. |
| 16 | Both-node altered final-byte transaction rejection without state change | PASS | controls.altered_transaction: final byte XOR 1; native rejection and unchanged pools/tips on both nodes. |
| 17 | Distinct conflicting-spend double-spend rejection | PASS | controls.conflicting_spend: distinct transaction shares restored key image; native double_spend indication on both. |
| 18 | Healthy eight-payment cohort after all negative controls | PASS | Healthy cohort 4 follows restored spend and all six node rejection responses. |
| 19 | Final empty queues, peers and complete main-chain/wallet reconciliation | PASS | final pools empty on both, matching tips, final_peer_rpc_ids and complete wallet/binding checks. |
| 20 | Chronological raw RPC/events and linked references | PASS | 2805/2843 chronological RPC rows; events, wire and linked method/port/timing references. |
| 21 | Live executable/command/PID-start identities for all generations | PASS | Nine generations per trial, /proc executable hash/command/PID/start identities including replacements. |
| 22 | Start/end/final peak memory, trend, CPU and payment timings | PASS | 186 samples per trial, start/end/shutdown resources and final cgroup files; summary.json timings/trend/CPU. |
| 23 | All nine child-generation exits 0 per trial and OOM counters 0 | PASS | All 18 child generations exit 0, cleanup_errors empty, every memory event counter 0. |
| 24 | Private offline container containment, caps and serial heavy lock | PASS | Exact docker commands, inspect/cgroup/interface/listener receipts; offline network none, caps and shared serial lock. |
| 25 | Exact owned-container cleanup and shared runtime preservation | PASS | Both exact containers absent, runner exit 0, final docker inventory empty and heavy lock available; CI/simulator preserved. |
| 26 | Public-export database/private-field/credential audit | PASS | Current database-free export PASS; original 60-file export FAIL under F1 and superseded. Exporter allows only 56 text files. Original manifest and excluded hashes retained, not database contents. |
| 27 | Passing fresh two-trial verifier baseline with local executable bytes | PASS | Corrected public archive baseline passed with the retained actual ARM executable bytes; checks/receipt.json and baseline.stdout.log. |
| 28 | Rehashed targeted adversarial refusals with no overlapping coverage credit | PASS | 31 rehashed REFUSED invocations after passing baseline: original 28 plus ring-database inclusion, unlisted wallet cache and database renamed as log. Exporter exclusion/refusal also exercised; overlapping checks are not distinct coverage claims. |
| 29 | Accepted 12 legacy source gates unchanged | PASS | accepted-gate-preservation.json: 12 source files SHA-identical to accepted base. |
| 30 | Legacy P2P receipt baseline and refusal suite | PASS | Corrected checker candidate reran historical P2P baseline and refusal suite; both exit 0. checks/legacy-p2p-* logs. |
| 31 | Legacy load/backlog ARM-substitution identity guards | PASS | Corrected checker candidate reran load/backlog ARM-substitution guards; both refuse different monerod bytes. Full old x86 suites not credited. |
| 32 | Full old x86 load/backlog refusal suites | NOT_RUN | Original pinned x86 executables absent; ARM substitutions correctly refused. Full suites not credited. |
| 33 | Hashed public raw package and exact candidate for independent reviewer | PASS | Corrected 56-file database-free public archive plus regenerated manifest, hashed current checks/report/source bindings and database-free incremental bundle. Exact final commit/attachment hashes in new handoff; old package superseded. |
| 34 | Independent exact-candidate acceptance | NOT_RUN | F1 remains open until existing reviewer ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6 independently closes it on this same review stage. |
| 35 | Parent local integration and next cross-host handoff | NOT_RUN | Pending independent acceptance; parent owns local integration, isolated cross-host follow-up and WhatsApp delivery. |

## Public raw package and reproduction

The corrected committed [public-native.tar.gz](evidence/vanguard-daemon-soak-tjs1816-2026-10-08/public-native.tar.gz) is 50,470,168 bytes with SHA256 `6044bfd703b6821707c77661993f3ef36bd2eae1fe5aa8ceeeec91f35b7fc9bb`. It contains 56 public text evidence files plus a regenerated manifest, all as unique regular members. It excludes the four original `.shared-ringdb` files and every unlisted wallet/private artifact. The exporter ran on build-mac before transfer; strict SCP readback, the archive inventory, the nested manifest and every retained original hash match. Current raw-RPC private-field checks and selected-file credential checks pass. These results correct the original export violation, whose historical checks did not establish the database exclusion.

The separate current and historical check logs, original/new native manifests, transformation, protocol matrix and source bindings are committed alongside the archive. `checks/prior-export`, `prior-public-package-audit.json` and `prior-source-byte-bindings.json` are historical records, not current export acceptance. The new downloadable incremental bundle uses superseded candidate `04493d6e8eb7734b9b833bb97839f9cea0a2f146` as its prerequisite and contains only the new commits/objects. It does not retransmit the old database-containing archive from ancestor history. Reviewers already have that prerequisite from the earlier stage; fetching the incremental bundle into that prerequisite produces the corrected current tree. Attachments are split below the server's 10 MiB limit, with per-part and concatenated hashes and verified content readbacks. The new package index binds the final exact commit.

Lightweight offline reproduction from a clean checkout of the final candidate:

```sh
(cd research/evidence/vanguard-daemon-soak-tjs1816-2026-10-08 && sha256sum -c MANIFEST.sha256)
(cd research/evidence/vanguard-soak-tjs1816-repair-2026-10-08 && sha256sum -c MANIFEST.sha256)
mkdir /owned/path/review-soak03
# Inspect names first; the recorded archive has only public regular files.
tar -tzf research/evidence/vanguard-daemon-soak-tjs1816-2026-10-08/public-native.tar.gz
tar -xzf research/evidence/vanguard-daemon-soak-tjs1816-2026-10-08/public-native.tar.gz -C /owned/path/review-soak03
(cd /owned/path/review-soak03 && sha256sum -c MANIFEST.sha256)
python3 -B vanguard/verify-daemon-soak.py /owned/path/review-soak03
python3 -B vanguard/test-daemon-soak-refusals.py /owned/path/review-soak03 --work /owned/path/review-controls03
python3 -B research/evidence/vanguard-daemon-soak-tjs1816-2026-10-08/summarize-soak.py /owned/path/review-soak03
```

The original baseline used `--src ~/Developer/tjs1816-5a24c6b6/build01` on build-mac. The corrected baseline used local copies of only those same two executable files; their hashes and ELF architecture matched. Independently hash the retained ARM files when reproducing that stronger byte check. The original native commands are in `receipts/receipt.json` and `soak03-command.json`. No native rerun is needed for offline review.

For a separately approved future native reproduction on build-mac only, use a clean owned checkout of the named native candidate, the verified `build01` cache, strict SSH, a fresh output directory and the same serial runner. Do not overwrite an existing run or compete for the heavy lock. The preparation command in `vanguard/README.md` documents rebuilding only if approved/needed; this run reused its verified build.

## Review and handoff

Route one independent review stage on this existing issue to `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`, binding the final exact commit and readback-verified attachment hashes. The reviewer should reconcile both fresh trials and all protocol rows, rerun lightweight baseline/refusals, verify source/architecture/privacy and retain concrete findings until independently closed. Source fixes belong to the sole writer. The reviewer must keep `UNVERIFIED_LIVE_TIPS`: offline evidence does not independently authenticate historical process or chain observations.

Parent owns accepted-candidate local integration/verification, the next isolated cross-host authorization and WhatsApp group delivery. This accelerated contained regtest establishes only the measured local payment/recovery behavior. It does not establish production security, cryptographic soundness, WAN behavior, sustained capacity, 90s/120s block behavior or public-launch readiness.
