# Direct profile runner candidate

Authority: studio-lead comment `bf88af40-a84e-4960-a37c-3c8d6d385bf3`.
Baseline: `fa7c19622a31439cbd386d8f8698fb4898508ef5`.
This is source preparation. Native execution, complete launch acceptance and public
launch remain unconfirmed. No funding, transactions or non-genesis blocks are allowed.

F1/F2 correction authority: lead interaction `b4df75a6-ad2c-4007-8675-e9da8376905e`,
answered 2026-11-01. Correction baseline: `cc5718f625c59ecc31518d4e54d8ed6e36d347fd`;
one implementation plus one correction, at most45 minutes from first production edit.
The clock/pass receipt is in `evidence/direct-runner-f1-f2/implementation-budget.json`.

F3/P2 correction: Platform interaction `8005b5ca-dc3a-467e-a0fa-eaa48854d55f`
found incomplete PASS witnesses on `c79018acf1e281494f5c33582878d698fab1092a`.
The same lead standing allowance covers this ordinary correction from that clean
head; its clock/pass receipt is `evidence/direct-runner-f3/implementation-budget.json`.

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
Keep `consumed.json` and controller-written `evidence/` after cleanup. Do not delete or reuse
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
A failed inspect alone never proves absence. Successful exit-0 `docker ps --all
--no-trunc` listings must each be empty for the exact task label, anchored exact
name and, once learned, the full container ID. Separate filters prevent one
identity from hiding another; any nonzero response or matching row refuses.
Docker stderr wording is ignored. An inspected replacement ID is refused.

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
The runner leaves `staging/private` absent so the frozen driver's own exclusive mkdir
creates it. After the owned container is absent, the runner imports any partial public
rows on both success and failure, before removing staging. Imports are restricted to
the six native/build filenames, known rows/statuses and the frozen producer's witness
fields. Files must be owned single-link regular files, opened without following
symlinks, at most64 KiB each; resource counters have a separate1 KiB numeric allowlist.
Malformed files, duplicate JSON keys, unknown fields and unexpected public entries
fail the attempt. The container-mounted `public/` directory is untrusted input only. After removal
is attempted, final rows and receipt are exclusively created under fresh mode0700
`evidence/`, which is never mounted. All file writes use mode0600 descriptor-relative
O_CREAT|O_EXCL|O_NOFOLLOW opens. A preexisting marker (including a symlink or FIFO)
refuses before runtime; final publication also refuses an existing evidence directory.
The runtime marker uses the same exclusive write anchored to a no-follow staging FD.
If public cleanup or container-absence confirmation fails, the attempt stays FAIL;
producer entries remain quarantined and final evidence still goes only into the
unmounted controller directory. Resource/cleanup rows remain controller-owned. Already-measured host peaks and
sample counts are serialized into resources and every cleanup row even when
cleanup fails; the failed cleanup row remains FAIL.
Publish only the nine regular evidence JSON files and, on eligible failed builds,
`build-diagnostics.json` (ten named exports total) from `evidence/`. Never package
`public/`, retained staging or the entire attempt root.

Every PASS row requires every frozen producer witness field recursively. Build
evidence must include all three binaries, each hash and dependency inventory, and
the RPC translation-unit object hash before runtime can start. Missing native PASS
witnesses fail the attempt. Partial files and omitted unreached rows remain valid;
FAIL/NOT_RUN rows may contain a validated subset of known witness fields. Unknown
fields and invalid present values are refused for every status.

The receipt retains only fixed phase names, numeric CLI/container exit codes and an
OOM boolean as phase diagnostics. Failure class and rejection labels contain no raw
exception messages, filenames from unexpected entries, stdout, stderr or private log
content. A failed phase stays FAIL while reached public rows survive and unreached
rows stay NOT_RUN. The lead decision [f44e6422](/TJS/issues/TJS-2504#comment-f44e6422-ea8c-4f5d-a211-78eab75077ca)
classifies compiler output from the pinned pre-runtime build as nonprivate. Only
a failed build, before any runtime phase and without any BUILD_COMPLETE entry,
may export `build-diagnostics.json`, after the owned container is confirmed absent.
It contains presence flags and the final 256 KiB each of configure.log/build.log,
plus rustc.txt, cargo.txt and cmake-version.txt. Logs over 16 MiB or versions over
4 KiB refuse the entire diagnostic export. Files must be owned single-link regular
files, opened no-follow/nonblocking through a no-follow staging directory FD.
Metadata/size changes during the bounded positional read refuse publication. Any
BUILD_COMPLETE entry, including a planted alias or FIFO, suppresses diagnostics.
Controller phase history also prevents export if a runtime marker is later removed.
Native/RPC/wallet/frame/environment transcripts and all runtime output remain private.
Security must review this changed boundary before a new grant.

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
The connected staging test runs the actual staging prefix and frozen driver entry,
stopping at a missing-binary sentinel before any native child. Failure tests exercise
actual `main` finalization with substituted Docker responses, including CLI nonzero,
container nonzero, partial runtime rows and private-sentinel rejection controls.
F3 tests remove every required top-level and nested PASS witness field, exercise
missing binary-hash and native-witness failures through actual controller finalization,
and retain complete frozen-driver fixtures and valid partial failure evidence.

Primary API references consulted for this implementation: Python 3.15.2
[subprocess](https://docs.python.org/3.15/library/subprocess.html) and
[signal](https://docs.python.org/3.15/library/signal.html), and Docker's
[container create reference](https://docs.docker.com/reference/cli/docker/container/create/).
F1/F2 file/JSON validation also uses Python3.15.2's
[os file-descriptor APIs](https://docs.python.org/3.15/library/os.html) and
[bounded JSON parsing guidance](https://docs.python.org/3.15/library/json.html).
Recursive PASS completeness uses the standard
[dictionary key-view equality](https://docs.python.org/3.15/library/stdtypes.html#dictionary-view-objects).

Security S1/P2 correction: answered question `70580605-1d3d-4aef-8967-570cb3d2f06d`
on baseline `35240d74a304f0ca57a972b7a34656e33966844f`, under the same standing
per-round allowance. Connected main/finalization tests cover marker symlink/FIFO,
public-root/subdirectory mode0500 and early container-cleanup failure with planted
links for every final filename. These are disposable source fixtures with substituted
Docker/native effects, not native execution. Python3.15 descriptor/flag semantics:
https://docs.python.org/3.15/library/os.html#os.open and
https://docs.python.org/3.15/library/os.html#os.mkdir .
