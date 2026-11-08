# Persistent isolated topology recipe (TJS-3920)

This is the private operator recipe for the milestone-2 topology: three native
nodes from the accepted retained build, persistent owner-only data, a tested
recovery path and a 24-hour run that survives a full stop/start of every node and
of the host-side manager. It does not create a public node. `public_launch` and
`launch_ready` stay false. Limits L1-L6 below bind every step.

## Security limits L1-L6 (binding for any persistent or shared operation)

These come from the accepted TJS-2504 Security review. This persistent recipe
supersedes the matching lines of `../operators.md` for any persistent or shared
use. `../operators.md` stays byte-identical because its SHA256 is part of the
retained build's compiled-input identity (`inputs.json`
`reference.repository_files` → `run-profile.py:build_identity`); editing it would
void the published retained-build authority `3eedebc0`. The launcher
(`../run-topology.py` with `topology_driver.py`) enforces these limits in code
through `topology_contract.py`.

- **L1, wallet RPC is a full-key service even when restricted.** Upstream
  `get_tx_key`, `get_tx_proof`, `get_spend_proof` and `get_reserve_proof` have no
  restricted check. Every wallet RPC, observer or signer, stays on its owner's
  loopback. The launcher refuses any wallet argv with a non-loopback bind,
  `--disable-rpc-login`, `--confirm-external-bind`, a non-loopback daemon address
  or TLS-less non-loopback RPC. Never forward, proxy or publish a wallet RPC port.
- **L2, daemon RPC runs `--restricted-rpc` and still stays private.** Every
  daemon start must pass `--restricted-rpc`; the launcher refuses an argv without
  it. `send_raw_transaction` and `submit_block` stay mapped in restricted mode,
  so restricted daemon RPC is still a private loopback service, never a public
  node. `--public-node`, `--rpc-restricted-bind-*`, ZMQ and bootstrap-daemon
  options are refused.
- **L3, witness digests are salted or dropped.** On any shared chain, public
  evidence must not carry plain SHA256 of txids, key images or tips. The topology
  driver exports only HMAC-SHA256 values under a private per-topology 32-byte
  salt (mode 0600, never exported) and carries no txid or key-image witness.
  The accepted F1 rows keep unsalted digests only because that chain was private
  and deleted; do not reuse them on a shared chain.
- **L4, auth in configs (rewording of `../operators.md:115`).** Read that line
  as: "Never put auth values into commands, public, proposal or evidence configs,
  receipts, screenshots or evidence." The one accepted config channel is a wallet
  owner's private mode-0600 `cli.conf` `daemon-login` line inside that owner's
  0700 root (accepted by Privacy and Security on TJS-2504). The topology driver
  writes no config file with a credential at all: daemon logins pass only
  through each child's environment.
- **L5, plaintext RPC is loopback only.** RPC runs `--rpc-ssl disabled`; the
  launcher refuses any non-loopback or wildcard `--rpc-bind-ip`,
  `--p2p-bind-ip`, IPv6 bind or exclusive peer. It accepts only the reviewed
  `--rpc-ssl disabled` on 127.0.0.1. Off-loopback transport needs TLS and a new
  Security review; it is outside this recipe.
- **L6, hygiene.** Write every receipt, cleanup record and inspection note with
  `umask 077` (mode 0600 under 0700 parents). The two 0664 cleanup receipts
  named in the review were changed to 0600 in place on 2026-11-08 (TJS-3920
  evidence `l6-chmod-receipt.txt`, contents unchanged). The daemon login is
  fresh per daemon launch in the topology driver. The restore-mode signer's auth
  bracket is documented in [the F1 addendum](funded-operators.md).

## Roles and topology

| Node | Role | P2P / RPC (127.0.0.1) | Exclusive peers | Mines |
| --- | --- | --- | --- | --- |
| A | primary seed | 48080 / 48081 | B | yes (one thread, RandomX light mode) |
| B | recovery seed | 48180 / 48181 | A | only while A is lost or partitioned |
| C | late-joining client | 48280 / 48281 | A, B | never |

All three run in one accepted network-none container (`--cpus=2 --memory=4g
--memory-swap=4g --pids-limit=256 --cap-drop=ALL --security-opt=no-new-privileges`,
no published ports). Each node has its own owner-only data root
(`persistent/nodes/<name>`, mode 0700), its own process and a fresh daemon
RPC login per launch passed only through the child environment. Every daemon
launch passes `--restricted-rpc`, loopback binds, `--rpc-ssl disabled`,
`--max-connections-per-ip 4` (three loopback peers share one address) and
`MONERO_RANDOMX_UMASK=4`. `integration/topology_contract.py:check_argv` refuses
anything else before a process or root is created. The only wallet is a one-time
`--wallet-dir` signer in F1's accepted restore-signer shape (private 0600
`cli.conf` daemon-login for node A, generated RPC login, loopback only). It
creates the miner address and exits; its password exists only in the loopback
RPC body and the owner's 0600 file, and the `cli.conf` is deleted afterwards. It
is never a service.

## Launch (needs a fresh exact Platform grant on TJS-3920)

The grant is a Platform-authored comment on TJS-3920 with one
`meownero-topology-grant` block. `run-topology.py:grant_payload` binds the exact
candidate commit, `integration/inputs.json`, runner and driver hashes, the source
packet attachment and digest, the output root, the retained build authority
(`3eedebc0`, root `401698da…/native-profile-attempt`, manifest `1b2815e2…`), the
container flags, the 100,800 s wall, the 86,400 s uptime, the 2,400-block
ceiling, one mining thread, zero transactions, a keeper-held heavy lock, the
load rule and the host-overhead allowance, with at least 48 h validity.

Run from a clean exact checkout of the candidate (a temporary `/tmp` worktree, so
later edits to the managed worktree cannot change the running source). The
wrapper restarts the manager on the two planned exits.

```sh
umask 077
setsid bash -c '
  python3 -B vanguard/network/run-topology.py start --grant-comment "$GRANT" \
    --artifact-sha256 "$PACKET_SHA256" --reuse-build "$RETAINED_ROOT" --out "$ROOT"
  rc=$?
  while [ "$rc" -eq 10 ] || [ "$rc" -eq 11 ]; do
    sleep 60
    python3 -B vanguard/network/run-topology.py resume --out "$ROOT"
    rc=$?
  done
  echo "$rc" > "$ROOT.wrapper-exit"
' > "$RUN_DIR/topology-controller.private.log" 2>&1 < /dev/null &
```

`start` checks the clean commit, inputs, retained build, grant and artifact,
runs the first admission (memory >= 5 GiB, disk >= 20 GiB, grant load rule, no
native collision), creates the one-use output root, starts the detached lock
keeper on the original heavy lock (device 66306 / inode 657237), stages the
harness and the three retained binaries, runs the second admission, creates and
starts the container. Exit 10 means the planned full cycle: every node is stopped
and sealed, the container has exited and the manager stops. Exit 11 is the
planned manager-only restart after one steady hour; the container keeps running.
`resume` refuses unless the previous manager is gone, the candidate is unchanged
and exactly one planned restart is pending.

## What the driver proves, in order

1. **Third seed/client.** A and B start fresh at genesis; A mines to count 6;
   C joins late from an empty root and syncs from genesis through only A and B.
   Kernel socket tables show exactly the three peer edges and no foreign remote.
   Daemon auth controls (missing/wrong login rejected) pass on all three.
2. **Cold backup.** A stops and seals; its root is copied with
   `copy_stopped` into `persistent/backups/A-1`. The backup is never opened by a
   writer. A starts once offline to bind its saved count/top/work.
3. **Corrupt/incomplete backup refusal.** Copies of the real backup with a
   flipped LMDB byte, truncation, missing `data.mdb`/`lock.mdb`/manifest, empty or
   unsealed manifest, extra file, symlink, 0755 mode, hard link, appended bytes or
   log drift are all refused by the launcher manifest check before any process
   starts; an intact copy is accepted; four foreign-binding roots (profile,
   overlay, binaries, kind) are refused. The original backup is unchanged.
4. **Primary loss and recovery.** A is SIGKILLed with exact PID identity. Its
   unsealed root is refused against its last seal, then moved to
   `persistent/quarantine/A-lost-1` (never erased). B restarts mining (dialing the
   synced client) and C follows it for three blocks. With B also stopped, C keeps
   zero peer connections, no foreign connection and a frozen height for 90 s:
   no fallback. B resumes; A is restored from `backups/A-1` into a new root,
   attested offline against the backup's saved state, then catches up the
   missing blocks from B. Mining returns to A.
5. **Detach/rejoin.** C stops, the chain advances two blocks, C restarts and
   catches up.
6. **Partition and reorg.** B restarts with `--in-peers 0` dialing only C, and
   C dials only B, so A (still running and synchronized) mines alone at least two
   blocks while B mines the majority side. An `--offline` node never mines
   (`miner.cpp:493-498`), which is why the isolated side keeps its process. A
   restarts frozen; once B's side has at least two more blocks and greater
   cumulative work, peers are restored: A reorganizes to the majority tip, keeps
   its old tip as an alternative block, and B and C never saw A's side.
7. **Full cycle.** Mining stops, every node is sealed, the driver exits, the
   container exits and the manager stops. After the manager restarts and the
   same container starts again, each node is attested offline against its sealed
   count/top/work before reconnecting. Process generations change.
8. **24-hour steady uptime.** A mines; every 300 s the driver requires all three
   processes alive with unchanged generations, at least two peer edges, no
   foreign connection and a height spread of at most two blocks (a failed sample
   is retried for 30 s, then it is a fault). One manager-only restart happens
   during this phase. After 86,400 s the chain must have advanced at least 100
   blocks; every node stops gracefully and is sealed.

Public rows carry counts, booleans and salted tips only (L3). The manager adds
`manager_cycle`, `manager_restart`, resources and cleanup rows and writes the
closed evidence set with 0600 files under a controller-only `evidence/`.

## Recovery recipe

- **Restart the whole topology** after a planned or crash stop: never open a root
  whose `creation.json` is missing, unsealed or does not match its last seal.
  Start each sealed node `--offline` first and compare `get_info` count, top hash
  and wide cumulative difficulty with the sealed values; then start B, C, A
  (A mining) with their exclusive peers.
- **Lost primary:** move the crashed root to `quarantine/` (never delete it),
  restore the newest cold backup with `copy_stopped` into a fresh root, attest it
  offline, then reconnect and let it catch up from B. B may mine meanwhile.
- **Both seeds lost:** the client stays at its height with zero peers. Recover a
  seed from its backup first; there is no automatic fallback to any other peer.
- **Corrupt or partial backup:** the launcher refuses it before start. Use an
  older sealed backup; never edit a manifest to make a root acceptable.
- **Foreign or other-profile root:** refused by its binding; it needs a different
  network namespace and data root.

## Operator-route gaps (TJS-2504 operator-route rev 6)

Each gap is either implemented in this route or recorded as a limit with its
reason. Reviewers can accept or reject each row.

| Gap | Disposition | Reason and evidence |
| --- | --- | --- |
| Protected pre-import immutable launch | **Limit.** Approximated, not protected. | The manager verifies the clean exact commit, runner/driver hashes, `inputs.json` candidate hashes and the retained binaries' SHA256 (`reuse_build`, `binary_copy`) before staging, and mounts harness/binaries read-only. A same-uid writer could still change the checkout before import. The lead withdrew installed/protected launch as a prerequisite (TJS-2504 decision `bf88af40`); Platform found no supported primitive (`3b0652a0`). Run from a fresh `/tmp` exact checkout. |
| Producer-loss recovery that survives separately | **Implemented for this route.** | The container and the persistent root survive manager loss; the separate keeper process keeps the lock; `resume` re-attaches by label, name and remembered container ID and records continuity (`manager_restart` row). The driver itself refuses unplanned restarts instead of reconstructing state. |
| PID1 same-open-description lock/namespace custody | **Limit.** | The heavy lock is held by one detached keeper process (one open description, `keeper.json` binds PID and start time, verified by a second non-blocking flock). It is not PID1-backed custody; systemd 255/cgroup v2 offers no supported primitive (`3b0652a0`), and `bf88af40` withdrew it. The network namespace is Docker's `--network=none`. |
| External-writer confinement | **Limit.** | The container writes only its mounts (`persistent`, `public`, `control`, `tmp`); harness, binaries and inputs are read-only. Host same-uid writers are not confined. Persistent roots are owner-only (0700/0600, `persistent_root_owner_only` row) and the launcher manifest refuses drift, but the manifest is same-uid provenance, not tamper evidence (Security, TJS-2504). |
| Full conditional OS cleanup | **Implemented for owned objects; limit beyond.** | `finish` stops owned children, removes the exact container, confirms CID/name/label absence with exit-0 listings, releases the keeper and verifies the lock is free. The persistent root is retained deliberately. No OS-level cleanup of foreign state, Docker images or shared caches is attempted. |
| Independent terminal exit/tail | **Limit.** | Terminal state comes from Docker's container state, the driver's closed heartbeat, cgroup counters written by `topology-runtime.sh` on exit and the wrapper's exit file. There is no separately privileged observer; a same-uid process could falsify the heartbeat but not the Docker exit code or the closed row schema. |

## Excluded (NOT_RUN by design)

Wallet payments on this topology (covered by accepted F1), a native exercise of
the L1 proof methods, TLS or any off-loopback transport, more than one host
(the only qualifying dev host is this Linux machine; TJ's Mac/phone and rented
hosts are excluded), and the installed operator-route custody above.
