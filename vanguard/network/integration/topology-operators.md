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
container flags, the uptime mode, the 2,400-block ceiling, one mining thread,
zero transactions, a keeper-held heavy lock, the load rule and the host-overhead
allowance (1 GiB RSS, 4,000 CPU-s, 32 PIDs), with at least
48 h validity. Two uptime modes exist and the grant picks one:

| Mode | `uptime_seconds` | `wall_seconds` | `verdict_label` | Best verdict |
| --- | --- | --- | --- | --- |
| full | 86,400 | 100,800 | `full` | `PASS_PERSISTENT_ISOLATED_TOPOLOGY_ONLY` |
| rehearsal | 3,600 | 14,400 | `rehearsal` | `REHEARSAL_PASS_UPTIME_NOT_RUN` (never satisfies the 24 h row) |

A rehearsal runs the same code and every other row, including the full cycle and
the manager-only restart (after 30 steady minutes instead of 60).

The host-overhead allowance is a sampled abort, not a kernel limit: every 60 s the
manager (inheriting `run-profile.py:Controller.sample_host`) measures its own
process tree and aborts the attempt with `metrology_host_overhead` /
`allowance_exceeded` when any value exceeds the grant. The peaks are per manager
generation, so a full run has up to three generations, each under the same cap.
The keeper is a separate session and keeps the heavy lock while a manager is
down. Admission is the grant load rule (1/5/15 ≤ 9.0) plus memory ≥ 5 GiB and
disk ≥ 20 GiB; at most three first admissions per grant, on separate wakes at
least 2 h apart (lead decision on interaction `a9e5430f`).

Run from a clean exact checkout of the candidate (a temporary `/tmp` worktree, so
later edits to the managed worktree cannot change the running source). The
wrapper restarts the manager on the two planned exits. Each manager runs as its
own session leader (`setsid -w`); the manager refuses otherwise.

```sh
umask 077
setsid bash -c '
  setsid -w python3 -B vanguard/network/run-topology.py start --grant-comment "$GRANT" \
    --artifact-sha256 "$PACKET_SHA256" --reuse-build "$RETAINED_ROOT" --out "$ROOT"
  rc=$?
  while [ "$rc" -eq 10 ] || [ "$rc" -eq 11 ]; do
    sleep 60
    setsid -w python3 -B vanguard/network/run-topology.py resume --out "$ROOT"
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
closed evidence set with 0600 files under a controller-only `evidence/`. After
collection it removes the exact container and `staging/` (public harness and
binary copies, counters); `persistent/` is retained owner-only on every path,
including failure, for the recovery recipe and private diagnosis.

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

## Public exposure (TJS-4177, milestone 3 candidate, not activated)

This section covers the first candidate in which a listener leaves loopback. It
runs only on the dev host, on an owned Docker `--internal` bridge with no
published host port. `public_launch` and `launch_ready` stay false. Activation
is a TJ decision that the lead raises after Core and Security accept this
candidate; the checklist at the end is what that decision needs. The
milestone-2 recipe above is unchanged and still governs every loopback launch.

### Transport and TLS choice (pinned fork `monero-fcmp` e151643c)

- **P2P stays plaintext Levin.** The fork hard-disables P2P TLS
  (`net_node.inl:1090`, `m_ssl_support = e_ssl_support_disabled`), as upstream
  Monero does. P2P carries chain data and transaction relay. Plaintext Levin
  lets a peer or an observer link a transaction's first relay to an IP.
  Dandelion++ (`cryptonote_config.h:111-116`, 2 stems, 20% fluff) helps only
  when there are enough honest peers, which a few-node testnet lacks. The
  testnet is therefore not private. Tor and I2P are upstream options outside
  this candidate.
- **Daemon RPC off loopback is TLS only.** The exposed seed runs
  `--rpc-ssl enabled` with no key or certificate path, so monerod generates an
  RSA-4096 self-signed certificate in memory at every launch
  (`net_ssl.cpp:265-290`). A non-loopback `--rpc-bind-ip` needs
  `--confirm-external-bind` even with TLS (`rpc_args.cpp:159`).
  `exposure_contract.check_exposed` accepts that option only together with TLS,
  `--restricted-rpc` and the exact owned bridge IP. Every milestone-2 shape still
  refuses it.
- **Custody.** The private key exists only in the seed process's memory and
  dies with it. It is never in argv, logs, the exchange, evidence or the repo.
  Disabled swap (`--memory-swap` equals `--memory`) and the container core limit
  (`--ulimit core=0`) keep it off disk. Note one exception: this host's
  `core_pattern` pipes crash dumps to apport, and the kernel does not apply
  RLIMIT_CORE to piped dumps.
  The seed driver reads the launch certificate's SHA-256(DER) pin by a TLS
  handshake from its own namespace, which is trust on first use there only. It
  passes the pin, which is not secret, to the client through the owner-only
  exchange directory. The client compares the pin before sending the first
  request byte. The pin's authenticity rests on namespace locality and listener
  ownership: the handshake never leaves the seed's namespace, `listeners()`
  confirms that the launched monerod PID holds the listener, and
  `confirm_pin()` then re-reads the pin and requires it to be unchanged. Digest
  does not authenticate the server, because the client never checks `rspauth`.
  A closed TLS session is never reopened (`auto_open = 0`), so the Digest header
  cannot leave over plaintext. The daemon login is 192 random bits, fresh per
  launch, and stays in the seed child's environment (L4); the client never holds
  it. Privacy/Cryptography was
  consulted on this design before the pinning code (TJS-4177 consultation
  comment).

### Topology and launch

| Namespace (container) | Bridge IP | Node | P2P / RPC | Role |
| --- | --- | --- | --- | --- |
| seed | 10.231.77.2 | S | 10.231.77.2:48080 / TLS 10.231.77.2:48081 | exposed seed, only miner (1 thread, light mode) |
| client | 10.231.77.3 | K | 127.0.0.1:48280 / 48281 | first client; exclusive peer `10.231.77.2:48080` |
| client | 10.231.77.3 | N | 127.0.0.1:48380 / 48381 | cold newcomer from genesis |
| foreign | 10.231.77.4 | F | 127.0.0.1:48480 / 48481 | `--stagenet` foreign peer |

The foreign peer has its own namespace and address. The seed blocks a host for
24 h after more than 10 wrong-network handshakes (`net_node.inl:2687`,
`add_host_fail`, `P2P_IP_FAILS_BEFORE_BLOCK`). Sharing the client address would
cut off K and N.

The network is `docker network create --internal --subnet 10.231.77.0/29
--gateway 10.231.77.1`, labelled and named by the grant. Containers on it get
no default route and no NAT. The manager refuses the launch if any Docker
network or host route overlaps the /29. All three containers keep the accepted
kernel limits (`--cpus=2 --memory=4g --memory-swap=4g --pids-limit=256
--cap-drop=ALL --security-opt=no-new-privileges`, core 0, owner uid). The only
change is `--network <owned> --ip <role IP>` in place of `--network=none`.
`run-exposure.py:verify_limits` refuses any port binding, `PublishAllPorts`,
published `Ports` entry, a second network or a wrong IP. Cleanup binds container
identity only, so a container that fails the limit check is still removed.

The seed's exclusive peer is the client address, where nothing listens. The
seed never dials beyond the owned subnet, and every seed/client connection is
client-initiated to the exposed listener. Each container's census
(`exposure_driver.classify`) refuses a default route, a route outside the /29, a
wildcard listener, any UDP socket and any connection outside the planned
edges.

The grant is a Platform-authored `meownero-exposure-grant` block on TJS-4177
(schema `meownero-exposure-grant/1`). It binds the same fields as the topology
grant: candidate commit, inputs, runner `run-exposure.py`, driver
`integration/exposure_driver.py`, packet, output root, retained build
`3eedebc0`/`1b2815e2…`, keeper-held heavy lock and the host-overhead allowance
(1 GiB, 4,000 CPU-s, 32 PIDs, sampled abort). It also binds the network (`internal`,
subnet, the three role IPs, `published_ports: 0`), `listeners:
internal-bridge-no-published-port` and `launch_ready: false`. A topology grant
never binds this runner, and an exposure grant never binds the topology runner.

| Mode | `uptime_seconds` | `wall_seconds` | `verdict_label` | Best verdict |
| --- | --- | --- | --- | --- |
| rehearsal | 1,800 | 10,800 | `rehearsal` | `REHEARSAL_PASS_STEADY_NOT_RUN` |
| full | 21,600 | 32,400 | `full` | `PASS_EXPOSURE_CANDIDATE_DEV_HOST_ONLY` |

Admission, spacing and the lock rules are the milestone-2 host contract (lead
decision `a9e5430f`): load 1/5/15 ≤ 9.0, memory ≥ 5 GiB, disk ≥ 20 GiB, and at
most three first admissions per grant on wakes at least 2 h apart. Both
admissions run before the first owned container exists. Run it from a clean
exact `/tmp` checkout as a session leader:

```sh
umask 077
setsid bash -c '
  setsid -w python3 -B vanguard/network/run-exposure.py start --grant-comment "$GRANT" \
    --artifact-sha256 "$PACKET_SHA256" --reuse-build "$RETAINED_ROOT" --out "$ROOT"
  echo "$?" > "$ROOT.wrapper-exit"
' > "$RUN_DIR/exposure-controller.private.log" 2>&1 < /dev/null &
```

### What the drivers prove, in order

1. **Exposed listener.** S starts once offline on loopback, in the milestone-2
   shape, so that the F1 restore signer can create the miner address. It then
   restarts on the bridge IP. Its listening sockets are exactly
   `10.231.77.2:48080` and `:48081` (no wildcard). From the seed's own
   namespace, the correct login over pinned TLS succeeds and missing or wrong
   logins return 401.
2. **Refusals from the other namespace.** These are checked before any client
   node starts:
   - a wrong pin is refused before any request byte;
   - a plaintext HTTP client gets no HTTP response;
   - a missing Digest login returns 401 over pinned TLS;
   - a wrong Digest login returns 401 over pinned TLS.
3. **Cold bootstrap.** K connects and S starts mining. Once S is at count ≥ 6, N
   starts from an empty root at genesis and syncs to the seed tip, through
   exactly one client-initiated connection to `10.231.77.2:48080`.
4. **Foreign network.** F (`--stagenet`, fresh, third namespace) dials the
   exposed seed for 90 s. S logs `WRONG NETWORK AGENT CONNECTED!`. F stays at
   its own genesis, S never learns F's genesis block, and both client
   connections stay up throughout.
5. **Seed restart.** S stops, seals, and restarts with a new process and a new
   certificate. The old pin is refused, and the new pin reaches 401 without the
   login. K and N reconnect and catch up two blocks.
6. **Client restart.** K stops while the chain advances two blocks, then
   restarts and catches up.
7. **Steady exposure.** K and N must follow the seed every 300 s, with no
   foreign socket. The window is 6 h for full mode. In rehearsal it runs 30 min
   and the row stays NOT_RUN.
8. **Cleanup.** The manager writes `host.json` (internal network, no published
   ports, three distinct namespaces) and then removes all three containers and
   the network, confirming absence by label and name. It also removes `staging/`
   and the exchange directory (steps, counts, tips and pins only). It releases
   the keeper and retains `persistent/{seed,client,foreign}` owner-only. No evidence
   file carries a `/home/…` or `/tmp/…` path (source test). Before any wider
   distribution, check archives for host names as well.

### L1-L6 and TLS under exposure

| Limit | Exposure candidate | Enforced by |
| --- | --- | --- |
| L1 wallet RPC full-key | Unchanged. The only wallet is the one-time signer on the seed's private offline loopback launch; no wallet runs while anything is exposed. | `t.check_argv` wallet branch; driver order |
| L2 daemon RPC restricted, still private | Every exposed daemon RPC is `--restricted-rpc` with TLS and a per-launch login, reachable only on the owned internal bridge. `send_raw_transaction`/`submit_block` stay mapped, so a public RPC is an activation decision, not a default. | `check_exposed`; `owner_namespace_auth`, `missing_auth_refused`, `wrong_auth_refused` rows |
| L3 salted witnesses | Unchanged. Public rows carry salted tips and counts only. Pins and raw tips stay in the private exchange. | `x.shapes`; source test scans public rows |
| L4 auth only in the environment | `--rpc-login`/`--daemon-login` are now refused by name, and abbreviations are refused by the allowlist. The seed login never enters argv, the exchange or any file. | `t.FORBIDDEN`, `t.allowlisted`; journey test |
| L5 plaintext RPC loopback only | Still true. The one off-loopback RPC is TLS with a pinned in-memory certificate. P2P is off loopback in plaintext because the fork has no P2P TLS. | `check_exposed`; `wrong_tls_refused` row |
| L6 hygiene | 0600 evidence under 0700 parents, `umask 077`, no host paths in evidence. | `r.publish_evidence`; manager test |
| TLS | RSA-4096 self-signed per launch, SHA-256(DER) pin, TLS ≥ 1.2 on the client, no request before the pin matches, stale pin refused after restart. | `exposure_driver.TLSRPC`; local TLS server test |

### Operator-route gaps re-examined for exposure

| Gap (milestone 2) | Once a peer outside the host can reach the listener | Control for this candidate / needed before activation |
| --- | --- | --- |
| Protected pre-import immutable launch | **Still holds.** A remote peer reaches monerod's P2P and the TLS RPC only, never the checkout, launcher or harness (mounted read-only). The same-uid host writer is the same boundary as before. | Same: fresh exact `/tmp` checkout, hash-bound grant. **Before activation:** the public host runs only this workload under a dedicated uid, so no other same-uid process exists. |
| Producer-loss recovery that survives separately | **Changes.** A remote peer can now crash or exhaust the seed. The exposure manager has no planned restart; a crash is a FAIL, and the crashed root is refused against its last seal (milestone-2 rule). | **Before activation:** a supervised restart path that keeps the seal/manifest check (offline attest, then reopen), plus cold backups on a schedule, named in the operator runbook. |
| PID1 lock/namespace custody | **Changes meaning.** The namespace is a Docker user-defined internal bridge instead of `none`, and its custody is still dockerd, so Docker socket access stays root-equivalent. A remote peer cannot reach the socket. | **Before activation:** only the operator uid can reach the Docker socket. Publishing a port goes through one explicit, reviewed rule (`-p` or firewall). Host networking is never used. |
| External-writer confinement | **Needs a different control.** Untrusted remote input now drives monerod, the writer of the persistent root. A monerod compromise acts as the container uid on its rw mounts (`persistent`, `public`, `control`, `tmp`, `exchange`). The kernel limits (cap-drop ALL, no-new-privileges, pids/memory) bound it, but the uid is the host owner's. | **Before activation:** run the public seed under a dedicated unprivileged uid or user-namespace remap (not TJ's uid), with only its data root writable and no exchange mount (the exchange is a test-harness channel). |
| Full conditional OS cleanup | **Still holds, extended.** Cleanup also removes the owned network and confirms its absence, alongside the three containers. | **Before activation:** DNS records, firewall rules and port mappings become new owned objects. Each needs a written rollback with an absence check (see checklist). |
| Independent terminal exit/tail | **Changes.** There are three containers. The terminal state comes from every Docker exit code plus per-role heartbeats. Every container can write the shared exchange, so a compromised seed could forge the client's view of the seed tip or pin; this affects only the harness. | Rows bind facts each role observes itself: client nodes' own tips and kernel sockets, and the seed's own log. **Before activation:** an outside monitor in a different uid or host checks the public node, and clients take the pin out of band. |

### Activation checklist (for the lead to carry to TJ; nothing here is done)

1. **Host and interface.** Which owned host runs the public seed, under which
   dedicated uid, on which interface or IP. The dev host's LAN address and
   tailnet are not public. No rented host, no phone.
2. **Ports.** P2P TCP 48080 public. Daemon RPC 48081 takes one of three
   options. No wallet RPC, ever.
   - **Stays private (recommended).** Operators reach it over the tailnet or an
     SSH tunnel.
   - **Published as TLS + login for operators only.** No CA certificate is
     needed, but this requires:
     - each operator receives the pin over an authenticated channel that does
       not use the public path, never TOFU across the internet;
     - a key-lifecycle decision: either per-launch keys with a fresh pin
       distribution at each restart, or a persistent 0600 key file under a
       dedicated uid with a written rotation and revocation step;
     - clients accept exact pins only, never `--rpc-ssl-allow-any-cert` or
       autodetect (check the text encoding of
       `--daemon-ssl-allowed-fingerprints`);
     - logins of at least 128 random bits per launch and per operator.
   - **Login-less public restricted RPC (a remote node for wallets).** This is
     a separate privacy decision: the node sees each wallet's IP and timing, and
     `send_raw_transaction`/`submit_block` are mapped. It needs its own
     Privacy/Cryptography consultation before it is offered.
3. **DNS.** Record name, owner and TTL. None was created by this candidate.
4. **Firewall/router.** Allow inbound TCP 48080 only (plus 48081 if item 2
   chooses it). Deny everything else. Set a connection-rate limit. The single
   reviewed rule is recorded with its removal command.
5. **Operator.** Who starts, monitors and restarts the seed; the supervised
   restart path with the seal check; the backup schedule; the outside monitor.
6. **Rollback.** Stop the seed (seal), remove the port mapping/firewall rule and
   the DNS record, confirm absence from outside, and retain the data root
   owner-only. State the expected time to rollback.
7. **Incident.** Who is alerted, the kill switch (rollback step 1), evidence
   retention, and the public notice that this testnet is valueless and not
   private. On the public host, the crash handler either drops the seed's dumps,
   or `core_pattern` is a plain path with the core limit at 0.
8. **Labels that stay.** The build identity (`1b2815e2…`/`3eedebc0`) stays
   unchanged. `launch_ready` flips only by TJ's decision recorded on the issue.

## Operator package (TJS-4238, milestone 4, not activated)

This section adds what activation needs and does not depend on the host, DNS or
RPC decisions. It still runs only on the dev host, on the milestone-3 owned
`--internal` /29 with no published host port. `public_launch` and
`launch_ready` stay false. Nothing here creates a uid, a firewall or router
rule, a DNS record or a published port.

### Public seed shape (`operator_contract.check_public_seed`)

A public seed launch is checked against an activation plan
(`operator_contract.plan`, schema `meownero-public-seed-plan/1`) before any
process starts:

- **Binds:** P2P on the planned interface address (`--p2p-bind-ip`, never a
  wildcard, loopback, link-local or multicast address), port 48080; IPv6 P2P
  stays `::1`.
- **Not the internal-bridge shape:** no `--allow-local-ip`, no `--hide-my-port`,
  no `--add-exclusive-node`, no `--add-priority-node`, `--seed-node`,
  `--add-peer` or `--ban-list`.
- **Peer bounds (explicit):** `--in-peers` 1-64, `--max-connections-per-ip` 1-4,
  both equal to the plan, and `--out-peers 0`. A daemon with no exclusive peer
  dials the five hard-coded upstream testnet seed IPs whenever its white peer
  list is empty, whatever `--out-peers` says (`net_node.inl:836-842,2016`; the
  identity overlay changes only the port and network ID). Every outbound
  attempt, seed dials included, returns before connecting when the out-peer
  count equals `--out-peers` (`net_node.inl:1541`). A single public seed is
  therefore a listener only and never contacts a third-party host. A second
  public seed is a later decision (it needs a peering rule between owned seeds).
- **Connection rate:** monerod has no connection-rate option
  (`net_node.cpp:145-165` has peer counts, the per-IP count and bandwidth
  only). The plan's `connection_rate` (new connections per minute 1-120, burst
  1-60) is enforced by the port rule, an owned object (see Rollback).
- **RPC variants:** `private` (recommended: `127.0.0.1`, plaintext, operators
  use their own tunnel) or `operator-tls` (TLS on the planned interface with
  `--confirm-external-bind`, the milestone-3 key and pin rules). A login-less
  public RPC is refused; it needs its own Privacy/Cryptography decision.
- **Every milestone-3 adverse argv is still refused** (wildcards, prefixes,
  login options, `--public-node`, restricted-port options, exclusive or extra
  peers, TLS off or autodetect, missing `--restricted-rpc` or
  `--confirm-external-bind`, two mining threads).

### Rehearsal topology

| Namespace (container) | Bridge IP | Node | Role |
| --- | --- | --- | --- |
| seed | 10.231.77.2 | S | public seed shape (`in-peers 16`, `out-peers 0`, `max-connections-per-ip 4`, `operator-tls` RPC), only miner (1 thread, light mode); its driver is the supervisor |
| client | 10.231.77.3 | K, N | K follows every seed launch; N is the newcomer that joins at depth |
| monitor | 10.231.77.5 | M | the outside monitor and its own validating follower; no exchange mount |

The manager is `run-operator.py` (derived from `run-exposure.py`), the driver
`integration/operator_driver.py`, the entry `integration/operator-runtime.sh`.
The grant is a Platform-authored `meownero-operator-grant/1` block on TJS-4238.
It binds the milestone-3 fields plus the monitor address, `listeners:
internal-bridge-public-seed-shape-no-published-port`,
`firewall_or_dns_change: false` and `uid_creation: false`.

| Mode | `uptime_seconds` (monitor window) | `wall_seconds` | Best verdict |
| --- | --- | --- | --- |
| rehearsal | 600 | 10,800 | `REHEARSAL_PASS_NEWCOMER_DEPTH_NOT_RUN` |
| full | 1,800 | 28,800 | `PASS_OPERATOR_PACKAGE_DEV_HOST_ONLY` |

The host contract, admission and launch command are the milestone-3 ones, with
`run-operator.py start`.

### What the drivers and the manager prove, in order

1. **Public shape.** S starts once offline on loopback for the miner address,
   then in the public seed shape. Each role's adverse argv list is refused
   before any launch. The owner-namespace TLS/Digest checks of milestone 3 hold.
2. **Cold bootstrap.** M (monitor) connects first, so S mines. K joins from
   genesis once S is at count ≥ 6.
3. **Scheduled cold backups (planned restarts).** Every 3 blocks, three times:
   S stops and seals; the supervisor attests the root against that seal
   (`c.root_manifest`: manifest, `stopped_saved`, file digests, modes, no
   alias); the root is copied to `backups/NNNN/S` and the copy is attested
   (`d.copy_stopped`); backups beyond the newest two are pruned and the
   remaining set is checked; S reopens (attested again) with a new process and
   a new certificate, and K and M reconnect.
4. **Crash.** At least 2 blocks after the newest backup, S is killed with
   SIGKILL (exact PID identity). The unsealed root fails attestation; a reopen
   with the last seal record is refused before any process starts (launch
   count unchanged); the root moves to `quarantine/S-0001` (owner-only, never
   opened again). The newest backup is attested, copied back and attested, and
   S reopens. It recovers the lost blocks from K and reaches K's exact tip.
5. **Follows restarts.** K, with an unchanged process, reached the seed tip in
   every seed launch (5).
6. **Newcomer depth (full only).** N joins when the chain is at count ≥ 121,
   so it needs at least two 100-block sync batches (tiny blocks sync
   `BLOCKS_MAX_WINDOW` = 100 at a time, `cryptonote_core.cpp:929-940`); its log
   must show at least two `Synced` lines (one per added span,
   `cryptonote_protocol_handler.inl:1821`). The rehearsal leaves this row
   NOT_RUN.
7. **Host reach.** While S serves, the manager, in the host namespace, opens
   one TCP connection to `10.231.77.2:48080` and one to `:48081`, sends no
   byte, holds each for 5 s and records the outcome (`host_reach.py`). The
   seed census counts gateway-sourced sockets as planned `host` edges.
8. **Outside monitor.** M's role gets the pin and the seed's operator status
   only through the manager (copied from the seed's control directory into the
   monitor's). In the rehearsal "out of band" means "never taken from the
   listener": the copy runs under the same host uid, so its authenticity rests
   on the same-uid boundary, not on an authenticated channel; that is why the
   different-uid and different-host rows stay NOT_RUN. It first checks that a wrong pin raises an alert, then samples
   every 60 s for the window: pin by TLS handshake (no request byte), M's own
   validated tip against the status tip, the status's inbound count against
   `in-peers` with M's own edge in it, and the status age.
9. **Timed rollback.** When every role serves, the manager stops the seed
   first (the kill switch; S seals on SIGTERM), then the client and monitor,
   attests the seed's seal offline on the host, removes the three containers
   and the network, checks that no route overlaps the /29 and that a
   host-namespace connection to `10.231.77.2:48080` fails, and runs the
   port-rule and DNS-record absence checks, which fail closed (UNVERIFIED)
   because the dev host has no outside vantage and created neither. It records
   the elapsed seconds. Cleanup, keeper release and evidence are as in
   milestone 3.

### Operator runbook

Plain steps for whoever operates the public seed after activation. Commands
name the owned objects only; the host, interface, DNS name and RPC variant are
the activation decisions.

**Start.**
1. Check the plan with `operator_contract.check_plan`, then the exact argv with
   `check_public_seed`. Never edit the argv by hand.
2. Start from a sealed root only (a fresh root, a planned stop, or a restored
   backup). The supervisor attests it before the process starts.
3. Confirm the listener is exactly the planned interface on 48080 (and 48081
   only for `operator-tls`), no wildcard.
4. Deliver the new TLS pin (operator RPC only) to every operator and the
   monitor over an authenticated operator channel, never over the public path.
   The pin is public, so the channel needs integrity and a known origin, not
   secrecy: SSH with a known host key, the tailnet, or a committed record. The
   pin comes only from the supervisor's record for that launch (the seed's
   own-namespace handshake after `listeners()` and `confirm_pin()`).

**Monitor.**
- Run `outside_monitor.py` under a different uid or on a different host, with
  its own follower node, the out-of-band pin file and the seed's operator
  status. Exit 2 (ALERT) pages the operator; exit 3 (UNVERIFIED) means an input
  is missing and the seed is not known healthy.
- The public path cannot show peer counts: restricted RPC zeroes them
  (`core_rpc_server.cpp:316-321`). The count comes from the supervisor's status.
  The supervisor identifies the follower's connection as `inbound.monitor`.
  The reference monitor requires that count to be at least one: zero or a
  missing entry is ALERT even when cached tips agree. An unreadable or malformed
  status is UNVERIFIED; other peers alone cannot establish monitor health.
- **Never clear a pin ALERT with the pin the monitor saw.** After a restart
  the monitor reports a mismatch until the new pin arrives over the operator
  channel. A pin read off the listener (the monitor's own handshake, or
  `openssl s_client` from the monitor host) is trust on first use across the
  public path. A mismatch with no known restart is an incident.
- **The pin check needs the `operator-tls` RPC variant.** Under the
  recommended `private` variant the public address has no TLS listener, so
  `outside_monitor.py` as written reports ALERT (unreachable) on every sample,
  and public P2P (plaintext Levin) has nothing to pin. Under `private` the
  monitor's anchor is the tunnel's own key (SSH host key or tailnet node key),
  which authenticates the status it carries, plus the follower's tip
  comparison; a pin-less monitor mode is a later change, not part of this
  candidate.
- The pin authenticates the RPC listener only, never the status file: the
  count, top and inbound figures are only as trustworthy as the operator
  channel.

**Restart (planned).** Stop gracefully (seal), attest, reopen; distribute the
new pin over the authenticated operator channel (Start step 4). A planned
restart also clears every in-memory host block.

**Backup.** A cold backup is a planned restart with a copy: stop and seal,
attest, copy, attest the copy, prune to the newest two, reopen. Rehearsal
schedule: every 3 blocks. Suggested public schedule: daily (about 960 blocks),
plus before any upgrade. Key lifecycle is tied to this schedule: with
per-launch keys and `operator-tls`, a daily backup means a daily pin delivery
to every operator and the monitor and an expected ALERT window each day; a
persistent 0600 key file under the dedicated uid (activation checklist item 2)
avoids that and makes any pin change a signal in itself. The choice belongs to
the activation decision. Backups stay owner-only and are never distributed
(signer artefacts live in the persistent root).

**Crash.** Never reopen an unsealed root. Quarantine it (owner-only, kept for
review), restore the newest attested backup, reopen, and let the seed recover
the lost blocks from its peers. If no backup attests, the seed stays down and
the operator escalates; a fresh chain is a reset (below).

**Rollback (kill switch).** In this order:
1. Stop the seed (it seals). `run-operator.py rollback --out <attempt root>`
   does this for an attempt whose manager is gone.
2. Remove the port rule: `nft delete table inet meownero_seed` (the rule
   template is `operator_contract.OBJECT_CLASSES['port-rule']['rule']`).
3. Remove the DNS record with the provider's delete command for the planned
   name.
4. Remove the owned containers and network.
5. Absence checks, each failing closed: a TCP connect to the public address
   on 48080 from an outside vantage must fail; the DNS name must not resolve
   from an outside resolver; no route or container remains. Without an outside
   vantage the result is UNVERIFIED, never "absent".
6. Keep the data root owner-only. The rehearsal records the time to rollback
   in `rollback.json` `rollback_timing`.

**Incident.**
- Alert: the monitor's ALERT or UNVERIFIED, a crash, or an unexpected reorg.
- Kill switch: rollback step 1.
- Evidence: keep the quarantined root, the native log and the monitor output,
  owner-only.
- Notice: this testnet is valueless and not private (plaintext P2P).
- **Open-consensus reorg (Core note 3).** P2P is open, there are no
  checkpoints, and the seed mines with one light-mode thread, so anyone with
  more hash can mine or reorg this testnet at any depth. A reorg is expected
  behaviour, not a compromise: record its depth and the competing tip, do not
  roll back on reorg alone, and roll back only if the seed misbehaves, the
  host is at risk or the network ID is abused. Adding checkpoints or a
  permissioned miner is a consensus decision for the lead, not an operator
  step.
- **Crash dumps (Security note 3).** On the public host either the crash
  handler drops the seed's dumps or `core_pattern` is a plain path with the
  core limit at 0. A piped `core_pattern` ignores RLIMIT_CORE, so the
  container's `core=0` alone does not keep the in-memory TLS key off disk.

**Unblock (Core note 4).** monerod blocks an address for 24 h after more than
10 failures (`add_host_fail`, `net_node.inl:2682-2688`), and
`--max-connections-per-ip` counts per IPv4 address, so peers behind one NAT
share both. The blocks live in memory only (`net_node.inl:266-281,346-356`):
a planned restart (seal, attest, reopen) clears them. Unrestricted
`set_bans` is not available on the restricted RPC and is never exposed.
`--ban-list` is refused by the public shape.

**Reset (Core note 2).** Foreign networks are refused by network ID at the
handshake. A peer with the same ID on another chain (an earlier reset of this
testnet) passes the handshake and is rejected only at sync. Rule: a testnet
reset changes `NETWORK_ID` (and therefore the build identity), as a separate
recorded decision on the issue. Until such a decision, the runbook accepts
same-identity rejection at sync: the old chain's peers fail sync, and the
protocol handler's drops add failure scores (`drop_connection_with_score`,
`cryptonote_protocol_handler.inl:2851-2862`) that can lead to an address block;
the unblock step clears it.
