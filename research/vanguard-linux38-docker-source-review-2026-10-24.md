# Linux38 Docker provider source candidate 1

The intake dependency is resolved. This candidate implements the selected
ordinary Docker route from [the capacity decision](/TJS/issues/TJS-1882#document-linux38-capacity-decision),
revision `7d23df43-8e7b-497d-bf0a-8beca2e98b2f`. It needs independent exact-source
review by `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` before live use. This is a
comment-only source handoff. The existing final release stage remains reserved
for exact artifacts and native acceptance. No release-stage decision is requested.

The existing writer workspace and branch remain the sole implementation slot.
The original helpers and inputs are unchanged. A checked export applies
`vanguard/patches/linux38-native-docker.patch` to private copies and names the
new controller `run-portable-linux-docker.py`. Its provider identity is
`NATIVE_X64_UBUNTU22_DOCKER_USERLAND`. The staged builder, preparation and runtime
workers have new source hashes; they must never be substituted into old carriers.

## What changes

`vanguard/linux38_docker.py` binds actual Ubuntu24/glibc2.39 controller,
x86_64 architecture, kernel, machine, boot, default local Unix endpoint, Docker
identity/version/data root and cgroup v2 capabilities. Raw identities remain
private. It refuses hosted identity variables and Docker redirects. It does
not infer unsafety from a container marker, a shared daemon name or existing
workloads. A same-kernel boot and bind-file witness must pass before workers.
Thus a containerized controller still needs the actual filesystem mapping and
kernel evidence. A matching kernel version alone cannot satisfy the witness.

Before the full controller and each phase, admission uses the existing shared
heavy lock and preserves its inode. The controller checks availability, then
releases its descriptor. Existing preparation, build and runtime workers each
acquire the canonical flock for their full heavy operation. This avoids a
controller/worker deadlock and allows other legitimate holders between phases.
Fetch and packaging retain their existing supervised behavior. A busy lock
refuses before output creation or any workload. No lock is created or unlinked.

Fresh small task-owned probes use the exact pinned Ubuntu22 image. They verify
native x64, the actual kernel boot, provenance-file mount bytes, Ubuntu22 and
glibc2.35 userland, at least six GiB host available memory, and ten GiB output
and Docker-data disk reserves. The probes also check actual cgroup files for
64 MiB memory, zero swap, one CPU and 16 PIDs. They have no network, writable
root, capabilities, devices, published ports or Docker socket mount. The
existing capacity helper's read-only Docker-data filesystem bind is used only
for `stat -f`. All probe commands have 30-second timeouts. Probe receipts retain
exact owned IDs and cleanup evidence privately, including failure cases.

Compilation keeps two CPUs, four GiB total memory-and-swap, 256 PIDs, offline
execution and 3600 seconds. It repeats fresh headroom checks immediately before
compilation and checks the actual cgroup limits inside the worker. Success also
requires a measured peak within four GiB and zero OOM events. Runtime retains
two CPUs, two GiB with no extra swap, 256 PIDs, offline/read-only execution and
1500 seconds, with actual cgroup and Ubuntu22/glibc2.35 checks. The controller
retains its 6900-second budget and 180-second supervisor cleanup interval.
Runtime now retains the full ten GiB disk reserve.

The staged workers additionally recover a container accepted before the CLI
wrote its CID file. They reuse `docker/docker_support.py` for exact name,
invocation-label and image verification before removal. Existing CID-file
ownership checks and signal-protected finalizers remain. Pre-existing container
IDs are recorded before the controller and checked between phases and on exit.
An externally removed pre-existing container also causes a refusal; this check
cannot distinguish an independent administrator's deletion from interference.

The acceptance assertions, source/Rust/dependency/image pins, package inventory,
license/privacy filtering, ABI floor, journey and ten controls retain their
existing implementation. No crypto, consensus or transaction code changes.
Kernel and userland are separate receipt fields. This cannot establish an
Ubuntu22 kernel or another distribution's runtime acceptance.

## Evidence and reproduction

The evidence directory is
`research/evidence/vanguard-linux38-docker-tjs1882-2026-10-24/`.

- All 19 staged helper bindings validate after zero-fuzz, zero-offset patching.
  All staged Python sources parse. The actual controller's allowlist-only path
  succeeds without contacting Docker. Missing provenance refuses before output.
- Eleven focused tests pass. Their subcases cover wrong host, daemon, boot,
  architecture, libc/Python, stale hashes, redirected endpoints, reduced cgroup
  support, insufficient memory/disk, wrong image userland, and busy flock.
  A mocked controller traverses all five phases, checking provenance forwarding,
  phase deadlines and ten GiB reserves, then stops before a real runtime.
- Create-response loss, start timeout and invalid-witness fixtures verify exact
  named cleanup and unrelated-ID preservation with mocked Docker operations.
  These fixtures do not prove actual Docker cancellation or live containment.
- Real small normal-exit, deadline and cancellation process fixtures pass using
  the unchanged source-bound supervisor. Each proves wrapper/descendant reaping
  and preservation of an unrelated process. All fixture processes were reaped.
- All 36 frozen Git bindings and their four input/workflow carriers pass.
  All 16 current local helper bindings and five pre-existing regular-file hashes
  remain unchanged. The canonical lock retains inode `657237`.

Source-only reproduction from this exact checkout:

```sh
python3 -B vanguard/stage-linux38-docker.py --out build/linux38-source-review
LINUX38_TEST_KIT=build/linux38-source-review python3 -B vanguard/test-linux38-docker.py
python3 -B research/evidence/vanguard-linux38-docker-tjs1882-2026-10-24/supervision-fixtures.py --kit build/linux38-source-review --out build/linux38-process-proof
```

The frozen helpers, patch, provider, source export receipt and independently
verifiable staged kit are included in the source packet. Do not reuse an
existing output path. The raw host/daemon identity record and credentials are
excluded from the packet.

Read-only Docker access succeeded. The host reports Ubuntu24.04.4 x86_64,
kernel `6.8.0-146-generic`, Docker29.5.3 and cgroup v2 with all required support
flags. The recorded snapshot had 7,848,546,304 available memory bytes and about
1.05 TB disk free, with 52 pre-existing container IDs. This is neither a
reservation nor live qualification. Inspection found the exact pinned Ubuntu22
base absent from the local cache. No image was pulled and no container launched.

## Reviewer and execution path

The original reviewer should challenge this exact source candidate, especially
the shared-daemon premise, mount/topology witness, lock lifetime, refusal paths,
actual worker limits and owned cleanup. Return source findings or clearance by
comment, then return the same issue to writer `92a7b4f2-787b-4cbb-954e-46831397ab09`.
Do not approve or close the full release. The reviewer is read-only for product
source; the writer retains corrections. Candidate 1 has not received an
independent verdict. The two allowed correction rounds remain available.

After source clearance, the same writer owns fresh qualification and the bounded
controller. First recheck native host memory/disk and the shared flock. If the
base remains absent, use the established task-private anonymous Docker client
with the exact pinned digest and a 180-second pull deadline. This is a public
base-image fetch, not an account or host-configuration change. Then bind a fresh
private provenance record with exactly the fields consumed by `admit`, including
the qualification evidence digest. Run the complete staged controller with its
exact `inputs.json` checksum, `--docker-provenance` and checksum, and a fresh
owned `--out`. Never call a worker phase as the full attempt. An actual
permission/capability denial stops launch and names the failed operation/remedy.

At most one full attempt and one recovery for a distinct diagnosed and corrected
cause remain. No full attempt was started here. Changed source must return to
independent review. Source clearance adds no platform acceptance. Exact archive
acceptance still needs clean extract; native daemon/CLI/RPC; receive5; two type7
CARROT payments; restored address/balance/output/key-image equality; later
spend2/receipt; ABI/license/privacy evidence; all ten controls; owned cleanup;
and independent reproduction of the exact downloadable archive.

Four of seven scoped native acceptances remain intact. Both Windows holds,
ARM13 BUILT_UNTESTED and native Windows INSUFFICIENT_EVIDENCE remain.
ARM13 archive SHA256 is
`fff26ea94928d2756cbf4b4b59bd2277a685e980d482cf389c8be405617ae15d`.
Historical findings, owner approval, [release handoff revision 6](/TJS/issues/TJS-1882#document-release-handoff)
and [the shared-testnet stop](/TJS/issues/TJS-2504) remain unchanged. No build,
Meownero journey, platform acceptance, integration, paid dispatch, publication
or group delivery resulted from this source handoff. Needs TJ: None.

Primary contracts checked for this candidate:
[Docker resource controls](https://docs.docker.com/engine/containers/resource_constraints/)
define memory/swap and CPU flags;
[Docker container execution](https://docs.docker.com/engine/containers/run/)
defines isolated processes, mounts and exact container IDs.
These documents establish option semantics, not this host's live enforcement.
