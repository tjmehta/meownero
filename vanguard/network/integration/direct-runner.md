# Direct profile runner candidate

Authority: studio-lead comment `bf88af40-a84e-4960-a37c-3c8d6d385bf3`.
Baseline: `fa7c19622a31439cbd386d8f8698fb4898508ef5`.
This is source preparation. Native execution, complete launch acceptance and public
launch remain unconfirmed. No funding, transactions or non-genesis blocks are allowed.

`run-profile.py` directly uses the existing `run-genesis.py` host lock, admission
observations and pinned Docker endpoint. It imports no retired manager, outer,
bootstrap, constructor, ingress, handoff or helper module. Those modules remain
committed for historical evidence. The unused `controller_create` receipt validator
remains only for the old dispatch tests. The native integration driver is unchanged.

The controller obtains the original nonblocking lock for the entire attempt. An
absent lock can be exclusively created with mode 0600; an existing lock must retain
the recorded device/inode and is never replaced or unlinked. Admission requires
5 GiB MemAvailable, 20 GiB free on the output filesystem, no native collision and
Platform's explicit load rule, before staging and again immediately before create.
Contention or failed admission releases the lock without waiting for capacity.

The output parent must be owned by the controller user, have no group/other write
permission, have no symlink alias and be outside a Git checkout, using the existing
`network.fresh_directory` checks. All exports, overlays, offline Cargo copies, harness copies, private native files,
archives and public evidence live below one fresh, grant-bound output directory.
Its durable creation consumes this attempt; an existing directory is refused.
Keep `consumed.json` and the public evidence after cleanup. Do not delete or reuse
this directory to replay a grant. Staging is removed only after the owned container
is confirmed absent. Unconfirmed cleanup is a failure and retains staging evidence.

The one task-named container uses the exact flags in `CONTAINER_FLAGS`, current
uid/gid, the pinned local image, no published ports and a read-only pinned Rust
mount. The same container is restarted once for runtime after building `daemon`,
`simplewallet` and `wallet_rpc_server` with one compile job. Inspect verifies the
effective resource and isolation settings before it starts. No Docker socket,
Paperclip credential or host credential environment enters the container.

The controller watchdog reserves 3600 seconds for staging/build, 600 for runtime,
and 300 exclusively for cleanup, inside 4500 seconds total. It terminates only
its own identified process groups and exact container (name, label, image and
staging mount), escalates TERM to KILL, verifies absence, removes staging and closes
the sole non-inherited lock descriptor. A lost create reply is recovered using the
same exact ownership checks. A daemon that cannot confirm removal produces failed
cleanup; this runner does not claim that SIGKILL or host failure is recoverable.

Container CPU, memory, swap and PID settings are kernel limits. Host controller
and child CPU/RSS/PIDs are measured and compared with Platform's separately stated
allowance. Sampling occurs every two seconds and at copy/phase boundaries; RSS
also includes conservative lifetime high-water observations. `du` measures allocated
blocks under the owned directory; the controller aborts above 15 GiB or below 4 GiB
backing free space. These are sampled abort rules, not a filesystem quota or an
aggregate host kernel enclosure. Container cgroup counters are captured after both
phases. The legacy `limits`/installation inventory and null bootstrap fields remain
bound historical source metadata; they cannot enable this direct entrypoint.

The public contract remains `build.json`, `peer.json`, `wallet.json`, `auth.json`,
`isolation.json`, `reopen.json`, `resources.json` and `cleanup.json`, with explicit
NOT_RUN exclusions. `resources.json.parent_enclosure` retains its old row name for
compatibility and explicitly describes container limits plus measured host overhead.
Private transcripts, wallets and credentials are never copied into the source packet.

Platform must read the changed source and issue one new authenticated comment on
TJS-2504 containing exactly one fenced `meownero-direct-profile-grant` JSON block:

```json
{
  "schema": "meownero-direct-profile-grant/1",
  "authorized": true,
  "candidate_commit": "<exact committed candidate>",
  "inputs_sha256": "<integration/inputs.json SHA-256>",
  "artifact_sha256": "<downloaded review packet SHA-256>",
  "runner_sha256": "<run-profile.py SHA-256>",
  "artifact_attachment_id": "<authenticated packet attachment UUID>",
  "output_root": "<fresh absolute owned host path>",
  "attempts": 1,
  "retry": false,
  "wall_seconds": 4500,
  "build_seconds": 3600,
  "runtime_seconds": 600,
  "cleanup_seconds": 300,
  "container_flags": ["--pull=never", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--cpus=2", "--memory=4g", "--memory-swap=4g", "--pids-limit=256", "--ulimit", "core=0"],
  "workload": "three-production-binaries-genesis-only",
  "non_genesis_blocks": 0,
  "transactions": 0,
  "valid_from_unix": 0,
  "valid_until_unix": 0,
  "load_rule": {"metric": "host-load-1-5-15", "maximum": [0, 0, 0]},
  "host_overhead_allowance": {
    "mode": "measured-controller-and-descendants-not-kernel-enforced",
    "peak_rss_bytes": 0,
    "cpu_seconds": 0,
    "peak_pids": 0
  }
}
```

Zeros and angle-bracket values are deliberately invalid placeholders. Platform
supplies a current validity window allowing all 4500 seconds, positive measured
host overhead allocations and its chosen positive load ceilings. No existing
v2 bootstrap grant is accepted. The source owner must also consume Security's
independent loopback/auth/operator review before invoking the runner; this source
packet itself grants no native authority. Core stage/decision and changes-requested
count two remain unchanged. No fourth conductor or manager-custody review is required.

After those reviews, invoke only the exact clean committed candidate:

```text
python3 -B vanguard/network/run-profile.py --grant-comment <new UUID> --artifact-sha256 <packet hash> --out <grant-bound output root>
```

The source freezer checks all pinned candidate, upstream, overlay, Cargo and
toolchain bytes. Direct-controller tests substitute Docker/native calls and use
disposable host children/locks to check process deadlines and cleanup; they are
source behavior evidence, not native acceptance.

Primary API references consulted for this implementation: Python 3.15.2
[subprocess](https://docs.python.org/3.15/library/subprocess.html) and
[signal](https://docs.python.org/3.15/library/signal.html), and Docker's
[container create reference](https://docs.docker.com/reference/cli/docker/container/create/).
