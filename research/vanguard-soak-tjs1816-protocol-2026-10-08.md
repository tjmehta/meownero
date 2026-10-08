# Longer native payment and recovery protocol

Protocol revision 2 for TJS-1816, frozen on 2026-10-08 before native execution.
The assigned outcome remains incomplete until both fresh trials, verifier
controls and independent acceptance finish. The scenario and verifier are now
implemented; no passing native result is inferred from that implementation.

The accepted starting commit is
`72e572bd2c6725eb59d5598852d782185e225504`. Extend the existing native private P2P
bridge, load and backlog code without changing their accepted gates. Keep the
FCMP++ upstream, submodule and Cargo.lock pins in `vanguard/source-lock.json`.
Changing the protocol requires a new dated revision published before its trial.
Do not reuse historical runs as either new trial.

Revision 2 records the observed Linux/ARM64 builder
`sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b`
already cached on build-mac. The accepted x86 image and executable pins remain
unchanged in the existing gates. The new build uses native ARM64 GCC 13.3,
CMake 3.28.3 and Rust 1.93.0, installed only under the owned staging directory
from the official standalone rustc, cargo and rust-std archives. Record each
archive's official SHA256 and actual bytes. Dependency preparation may use a
task-owned capped container with ordinary bridge networking and no published
ports; native build and trials are offline. No host toolchain is installed.
The three Rust archive hashes observed during preparation are respectively
`1a9045695892ec08d8e9751bf7cf7db71fe27a6202dd12ce13aca48d0602dbde`,
`5998940b8b97286bb67facb1a85535eeb3d4d7a61e36a85e386e5c0c5cfe5266`, and
`84e82ff52c39c64dfd0e1c2d58fd3d5309d1d2502378131544c0d486b44af20a`.
The original upstream/submodule/Cargo.lock pins and every measured protocol
row below remain required. Selected workload inputs are bound to the sender's
current unspent-output snapshot before each cohort, allowing native selection
of newly mature change without allowing input reuse. The losing-branch orphan
receipt is required on node A, which actually held that branch.

The documented Colima recovery moved only the three stale PID/socket entries
and made one successful unchanged-profile startup retry. The live dockerman
CI listener is a separate potential runtime consumer. Leave the shared runtime
running while that consumer remains; clean only exact task-owned containers.

## Environment and containment

All heavy builds and native execution run on build-mac. Use strict host-key SSH to
the documented `build-mac` target, an owned clean staging checkout of the frozen
candidate, and a running authorized local Docker endpoint. Neither the dev
primary nor build-mac's dirty primary checkout is a staging directory.

Record host name, OS, host and container architecture, available memory and
disk, Docker endpoint and server version, image ID and architecture, upstream
HEAD, submodule HEADs, Cargo.lock digest, toolchain versions, CMake arguments,
actual executable digests and sizes. Compare source pins before building. ARM
builds get new actual executable digests. The accepted Linux/x86 executable
digests cannot stand in for those bytes. Reuse only verified compatible caches.
Do not install global tools or change host runtime settings to pass preflight.

Hold a nonblocking build-mac heavy-work lock shared by both trials and their build.
Run one build job and one trial at a time. A running Docker VM must have at least
5 GiB available memory and disk before accepting a 4 GiB trial cap. Preserve
other workers. Use task-owned names, `--pull=never`, `--network=none`,
`--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--cpus=2`,
`--memory=4g`, `--memory-swap=4g`, `--pids-limit=256`, and core size zero.
No published ports, host networking, privileged mode or public peers. Inside the
container require only loopback, no route, and loopback RPC/P2P listeners. Native
Levin frames cross the existing private mode-0600 AF_UNIX bridge.

Use a fresh evidence directory for every attempt. Budget the offline build at
3,600 seconds, warmup at 900 seconds per trial, and the measured window at
2,400 seconds per trial. The whole runner deadline is 11,000 seconds. Record
timeouts and partial failures before cleanup. Terminate, reap and record every
owned child generation, then remove only the exact owned container. Keep final
cgroup peak, CPU counters and memory/OOM events through shutdown. A failed
trial is never relabeled or replaced in place.

## Two fresh trials

Each trial creates independent disposable wallets and fresh chain directories.
Draw its workload seed from the OS random source and record it. Reject repeated
workload seeds, wallet-seed digests, transaction identities or shared trial
history. Workload seeds are not wallet secrets. Keep wallet mnemonics, private
keys, wallet files and databases outside uploaded evidence. Redact mnemonic
responses and restore requests before writing any RPC log, exception or stdout.

Create sender A on node A, sender B on node B, and one fresh recipient per node.
During warmup mine 90 blocks to each sender in sequence, synchronize both nodes,
refresh both wallets and verify at least 16 independent mature outputs per
sender. Record the exact generated chain, funding outputs and balances. Warmup
and build time do not count toward the measured duration.

Start the measured clock only after funding, handshake, executable/process
binding and empty pools pass. Run four sequential depth-eight cohorts, with
origins A, B, A, B. Each cohort pays the opposite node's recipient. Amounts are
`10**12 + rng.randrange(1, 10) * 10**10` atomic units. Require the wallet's exact
destination list, actual fee, native FCMP++ type 7, CARROT outputs and input key
images to agree with the recorded payment. Preserve the accepted sender refresh
reservation route after each origin admission. No selected input or key image
may be reused by another valid workload payment.

| Earliest measured time | Required actions |
| --- | --- |
| 0 minutes | Cohort 1 from A: queue eight distinct payments with mining paused, observe the exact pool on both nodes, drain and confirm exactly once. |
| 6 minutes | Gracefully stop, reap and reopen sender B's wallet RPC with the same wallet files. Compare address, outputs and balances. Execute cohort 2 from B. |
| 12 minutes | Gracefully restart node A with its persistent chain directory and unchanged command. Compare its pre/post chain and reestablish native handshake. Partition the bridge, queue all eight cohort-3 payments at A, require B's pool remains empty, then reconnect, require both exact pools and drain. |
| 18 minutes | Record a common tip with empty pools, partition, generate one empty branch block on A and two on B, require distinct branches, reconnect and require both nodes adopt B's exact longer tip. Verify A's losing block is orphaned and all prior payments remain on the main chain with unchanged wallet credits. |
| 24 minutes | Unlock received outputs with 12 synchronized empty blocks, restore recipient A from its disposable mnemonic into a fresh wallet, rescan and compare address, outputs, amounts, balances and spent flags. Build two distinct spends of one received key image. Both nodes must reject a malformed transaction encoding and a changed-signature transaction without state change. Confirm the valid restored-wallet spend on both nodes. Both nodes must reject the distinct conflicting spend with the native double-spend indication and unchanged state. Execute cohort 4 from B after those rejections. |
| 29 minutes | Reconcile all 32 workload payments and the restored spend, both wallets and the main chain. Require empty pools, native peer connections, healthy RPC and live executable identities. Continue heartbeats and sampling until at least 1,800 measured seconds have elapsed, then record final observations and controlled shutdown. |

Wait to each earliest time only after the preceding phase succeeds. Keep native
processes, 30-second RPC heartbeats and 10-second resource samples running during
the intervals. If a phase runs late, continue within the measured deadline;
never shorten the required measured window. Allow at most three drain blocks
per cohort and 210 generated blocks total per trial, including funding, unlock,
restored spend and competing branches. Every phase has a 180-second deadline
except construction/drain and wallet restoration, which each allow 300 seconds.
If that budget is insufficient on build-mac, preserve the failure and publish a
revised bounded protocol before rerunning.

## Required evidence and refusal checks

Every public RPC/event row carries an ordered identity and monotonic begin/end
times. Receipt references bind construction, origin admission, peer observation,
full queue, generation, main-chain block inspection, confirmation and recipient
observation in that order. Capture raw native frames for malformed delivery where
used. Keep full native transaction bytes and their decoded identity. Record raw
RPC rejection responses rather than only a claimed `state_unchanged` flag.

For each valid transaction compare both native `get_transactions` results and
both `get_block` headers/bodies: exact hash, byte identity, height, previous hash,
non-orphan status and exactly one main-chain membership. Bind destinations and
amounts to wallet construction and each recipient's unique CARROT output. Reconcile
sender input spent status, principal and fee changes separately from coinbase
funding. Require no duplicate recipient public key, credit or input spend.
After restore, compare the original and restored wallet histories and confirm
the later spend and its resulting balances. Save state on both sides of each
restart, disconnect, reorg and negative control.

Read `/proc/<pid>/exe`, process command line and start identity while each child
generation is live, including replacements after restart. These are writer
observations. An offline verifier must retain `UNVERIFIED_LIVE_TIPS` and cannot
claim independent authentication of historical state.

Sample cgroup current/peak memory and CPU counters plus each child's RSS/CPU
every 10 seconds. Report measured start, end and final shutdown peak, every OOM
counter, memory trend and per-generation exits. Report construction, admission,
peer arrival, confirmation and end-to-end payment delay separately. Cohort
completion rates use actual cohort work duration; the 30-minute wall clock is
neither a throughput denominator nor proof of capacity.

The new offline verifier requires both live trial baselines before its writer
refusal suite is credited. Rehash each mutated bundle. Test independently:
insufficient measured time, fewer than 32 payments, replayed trials, mining
before a full queue, input reuse, changed destination/amount, unrelated native
bytes, wrong peer block or orphan status, duplicate credit, failed persistent
restart, restored wallet mismatch, missing later spend, accepted invalid or
conflicting input, no later healthy payment, unrecovered reorg, nonempty final
pool, mismatched live binary generation, missing child exit, positive OOM counter,
and missing final shutdown metrics. Do not count mutations of one underlying
contradiction as separate coverage claims. Retain the accepted load, P2P and
backlog verifier/refusal checks unchanged, and run their relevant regression
checks against the frozen candidate.

## Disposition

Publish PASS, FAIL or NOT_RUN for every row, raw hashes, exact source commit,
commands, limits and cleanup outcome. No PASS may be inferred from preflight,
elapsed wall time, old receipts, a manifest alone or a writer assertion.

Once actual native trials and verifier checks finish, freeze the exact code and
evidence, then activate one independent review stage on the existing issue for
`ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`. Retain findings until corrected and
independently closed. The parent owns accepted-candidate local integration and
group delivery. This bounded accelerated regtest does not establish production
security, cryptographic soundness, WAN behavior, 90s/120s capacity or readiness
for public launch.
