# Linux38 Docker candidate 1, correction round 2

The fresh live qualification of independently cleared correction `b3629f3c7991679576880154169a376f2c5c576b` stopped before the full controller. Its admission container exited 2 with `sh: 3: cannot open /canonical-heavy-lock: Permission denied`. This report preserves that failed result. It does not claim live topology, mount, cgroup, native-build or archive-journey acceptance.

The canonical lock is owned by UID/GID 1000, mode 0600, device/inode `66306:657237`. The admission probe used the base image's default root user with `--cap-drop=ALL`, so it could not open the task user's lock. It failed before the contention, mount and resource transcript. The exact owned probe was removed with identity verification, exit 2 and no OOM; all 52 pre-existing container IDs remain. No full controller attempt or distinct recovery was consumed.

## Bounded correction

The only provider behavior change adds `--user <task UID>:<task GID>` to admission-container creation. This follows the existing compilation and runtime workers, which already pass the same numeric identity. Preparation retains its existing root/package-installation behavior and existing capability contract. No worker script or patch changes. The lock's owner, permissions, inode and bytes are unchanged; every admission capability remains dropped. Source staging selects new correction-2 inputs and rebinds the two changed helpers, provider and staging script. The other 17 staged helper hashes and the correction-1 patch are unchanged.

Docker documents the default root identity and numeric UID:GID override in [container user settings](https://docs.docker.com/engine/containers/run/#user). Its [capability table](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities) describes discretionary-access overrides. These explain the diagnosed failure and selected setting; they do not prove corrected live execution.

## Observed work and checks

- Initial read-only headroom was 5,040,660,480 available bytes, below six GiB. After source/clearance verification and staging, a new check under the canonical lock measured 6,725,017,600 bytes. Both output and Docker disk reserves exceeded ten GiB. No workload was admitted from the low snapshot.
- Fetched the exact public Ubuntu22 digest `ubuntu@sha256:08ea48a03a3e78ebc7cd526e6a275053223aadd88bfc09cc49b06d5281525fde` through a private anonymous Docker client on the existing local Unix endpoint, within the 180-second bound. Its amd64 image is `sha256:e8df6c74f650ad385efe2e20103eca9b0ad50690fb3c63d49fa00762412bbf55`. No global client, daemon or host configuration changed.
- The actual cleared provider admitted the bound Ubuntu24/x64 controller and daemon identity. Its single small live probe then encountered the permission failure above. `flock` was found, but lock contention and subsequent witnesses did not execute. Read-only capability flags are not cgroup enforcement proof. No corrected-source live container was launched.
- Added task-identity and no-added-capability assertions to the existing failed-probe/create-response-loss test. It fails on the cleared old provider in all three cases because `--user` is absent. All eleven admission/controller tests and six real-shell/flock topology tests pass with this correction. Docker observations in these tests are mocked. These are regression and source/process results, not a corrected Docker pass.
- Fresh zero-fuzz/zero-offset staging verifies all 19 helper hashes and Python parsing. The 36 frozen Git bindings/carriers, 16 local frozen helpers, six pre-existing file hashes and all earlier evidence are preserved. The owned live probe is absent; original container IDs and canonical lock inode/mode remain. The primary checkout was not touched. The unchanged supervisor's earlier real normal/deadline/cancellation evidence remains historical; it was not rerun in this correction.

Evidence is in `research/evidence/vanguard-linux38-docker-correction2-tjs1882-2026-10-24/`. It contains the original live failure, owned cleanup, before-pull headroom/fetch receipt, failing old-source regression, passing corrected source tests, source export and preservation checks. Raw machine/daemon identity, provenance JSON, anonymous client and private logs remain outside the packet. Safe receipts retain hashes and exact task-owned probe identity.

Reproduction from the correction commit:

```sh
python3 -B vanguard/stage-linux38-docker.py --out build/linux38-correction2-review
LINUX38_TEST_KIT=build/linux38-correction2-review python3 -B vanguard/test-linux38-docker.py
LINUX38_TEST_KIT=build/linux38-correction2-review python3 -B vanguard/test-linux38-topology.py
```

## Review and continuation

This is the second and final allowed source correction round. Zero correction rounds remain. One full finite-controller attempt and one distinct diagnosed recovery remain unconsumed. Independent reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` must inspect this exact new source before another live probe, then return the same issue to writer `92a7b4f2-787b-4cbb-954e-46831397ab09` as `todo`. The final artifact stage stays dormant; do not close the release for preliminary source clearance.

After clearance, the same writer must freshly rebind qualification evidence and check headroom, run the real topology/lock/mount/pinned-base/cgroup probe, then run the complete finite controller and exact-archive journey only if qualification succeeds. The cached public base is no admission or reservation. Any further source defect must respect the exhausted correction budget and record its precise cause and smallest remedy.

Four of seven prior scoped native acceptances, both Windows holds, ARM13 BUILT_UNTESTED, native Windows INSUFFICIENT_EVIDENCE, owner approval, historical findings, release-handoff revision 6 and the TJS-2504 stop remain intact. ARM13 archive SHA256 remains `fff26ea94928d2756cbf4b4b59bd2277a685e980d482cf389c8be405617ae15d`. No Meownero compilation/journey, new platform acceptance, integration, deployment, paid spend, publication or group delivery is claimed. Needs TJ: None.
