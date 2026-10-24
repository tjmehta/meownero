# Linux38 Docker candidate 1, correction round 1

This correction addresses blocking F1 in the [independent source verdict](/TJS/issues/TJS-1882#document-linux38-docker-independent-source-review), revision `7630e231-c1e0-4b63-a20d-353c7d525a32`, against candidate `53112f4b1a0a799c498b25b8376201af2bc39e27`. Independent source clearance is still required. This handoff concerns source only. The final artifact stage stays dormant.

The existing writer workspace remains the implementation slot. The original helpers, frozen inputs and workflows, and all candidate 1 evidence remain byte identical. The successor patch, provider, staging script and separate correction inputs bind the corrected source. No source, transaction, cryptography or consensus implementation changes.

## F1 correction

`vanguard/linux38_docker.py` now holds the canonical exclusive flock throughout each admission probe and its owned cleanup. It verifies device and inode against the open descriptor, refuses symlinks and hardlinks, opens without following a symlink, and checks preservation before unlocking. Nested compile headroom probes reuse the worker's already-held descriptor, so they cannot deadlock or release it early.

The daemon probe mounts the existing canonical lock read only. Its shell opens that mount, compares the descriptor's device/inode, and requires a nonblocking shared flock to report contention with the controller's live exclusive lock. A different daemon lock fails identity even if another process holds it. Matching identity without real contention also fails. The probe then compares device/inode for the exact provenance file, source-kit root, owned output root and Docker capacity path. The controller checks its owned output root before each phase, rather than just the parent filesystem.

The staged preparation, compilation and runtime workers acquire this same guarded lock for their complete operation and cleanup. Each actual worker command uses explicit `--mount` binds and runs the same identity/lock prelude before its existing payload. Preparation checks its `/out`; compilation checks `/src`, `/cargo-home`, `/opt/rust` and `/out`; runtime checks `/artifact.tar.gz`, `/out` and `/harness`. Read-only settings remain on the lock, Rust toolchain, archive and runtime harness. The checks use the exact paths passed to the worker, including newly created output directories and source copies.

Docker's `--mount` refuses an absent daemon source instead of creating a directory. Existing but wrong, stale or namespace-private paths fail device/inode checks. The worker requires the existing `flock` and `stat` utilities and fails before its payload if they are unavailable. All witness commands are inside the existing bounded probe or supervised worker, with no network, host configuration change or lock replacement. Option semantics are documented by [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/#syntax); Python descriptor locking is documented by [fcntl.flock](https://docs.python.org/3.14/library/fcntl.html#fcntl.flock). These sources establish API semantics, not live qualification.

The six-GiB available-memory and ten-GiB disk gates, fixed probe/compile/runtime cgroups, deadlines, supervision, exact owned-name cleanup, unrelated-container preservation, ABI/license/privacy checks, full archive journey and all ten controls retain their previous requirements.

## Reproduction and evidence

Evidence is in `research/evidence/vanguard-linux38-docker-correction1-tjs1882-2026-10-24/`.

- The reviewer's original counterexample reproduces on the original candidate. Its real daemon-fixture lock is busy while its disjoint controller-fixture lock is admitted; mocked matching boot/provenance/cgroup observations pass the old resource boundary.
- The new private-lock regression fails on the original provider with `CalledProcessError not raised`. It passes on the correction through the same `resources()` boundary. Real files, stat calls and flocks implement the namespace model; Docker observations are mocked.
- All eleven existing source/process tests and six new topology tests pass. Subcases exercise correct mounts, a busy different daemon lock, wrong/absent/stale source/output mounts, symlinks, inode replacement, nested lock lifetime, cleanup while locked, and matching inode with released lock. A positive control reaches the fixture payload. Refused cases do not reach it.
- The actual staged runtime entry point produces the verified archive/output/harness mount arguments. Its real generated shell prelude runs against fixture files; correct mounts reach a marker and a wrong output refuses. The fixture stops before extraction or any native program. Docker operations and runtime image observations are mocked.
- The unchanged supervisor passes real normal-exit, deadline and cancellation fixtures. Owned descendants are reaped and an unrelated process survives. All fixture processes are reaped.
- All 19 staged helper bindings pass zero-fuzz, zero-offset patching, and the staged Python files parse. All 36 frozen Git bindings/carriers, 16 current local helper hashes, six pre-existing file hashes and original candidate evidence pass preservation. Canonical lock inode remains `657237`; the primary checkout was not touched.

Reproduce in a fresh output directory:

```sh
python3 -B vanguard/stage-linux38-docker.py --out build/linux38-correction-review
LINUX38_TEST_KIT=build/linux38-correction-review python3 -B vanguard/test-linux38-docker.py
LINUX38_TEST_KIT=build/linux38-correction-review python3 -B vanguard/test-linux38-topology.py
python3 -B research/evidence/vanguard-linux38-docker-tjs1882-2026-10-24/supervision-fixtures.py --kit build/linux38-correction-review --out build/linux38-correction-process
```

These are source/process results. No real Docker image pull, container launch, native compilation or Meownero journey ran. Actual daemon/controller topology, pinned-image utility availability and resource enforcement remain for fresh qualification after independent source clearance.

## Review and execution path

Reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` should inspect the exact corrected source, challenge the new prelude and worker integration, and return findings or scoped source clearance by comment. Product source is read only for the reviewer. Return the same issue to writer `92a7b4f2-787b-4cbb-954e-46831397ab09` as `todo`; do not close the release or enter the final artifact stage for this review.

This uses the first of two allowed correction rounds. One correction round remains. The single full attempt and one recovery for a distinct diagnosed cause are untouched. Changed source requires renewed independent review. After clearance, the writer owns fresh headroom, exact public-image fetch if needed, live topology/cgroup qualification and the complete finite controller. No new hardware or owner decision is needed.

Four of seven earlier scoped native acceptances, both Windows holds, ARM13 BUILT_UNTESTED, native Windows INSUFFICIENT_EVIDENCE, historical findings, owner approval, [release handoff revision 6](/TJS/issues/TJS-1882#document-release-handoff) and [the TJS-2504 stop](/TJS/issues/TJS-2504) remain intact. ARM13 archive SHA256 remains `fff26ea94928d2756cbf4b4b59bd2277a685e980d482cf389c8be405617ae15d`. This correction adds no platform acceptance, integration, deployment, paid spend, publication or group-delivery claim.

Needs TJ: None.
