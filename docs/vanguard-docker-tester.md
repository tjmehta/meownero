# Disposable Docker tester

This candidate builds the pinned FCMP++/CARROT daemon, wallet RPC and wallet CLI
for a local valueless payment and recovery test. Native Linux x64 is the first
target. Run these commands in a Linux x64 shell with a local Docker daemon,
cgroup v2 and support for the legacy Docker builder. Windows/Mac Docker hosts
and ARM images are untested. This candidate's independent acceptance is pending.
Do not use real funds, keys or an existing wallet.

Get an exact independently cleared source archive through the existing
authenticated artifact route. Verify its published SHA256 before extracting it.
The website download is pending parent publication. No public image or signed
private download URL is advertised here.

From the extracted repository, with Python 3.11 or later and Docker installed,
reserve at least 10 GiB on both the output and Docker data filesystems:

```sh
python3 vanguard/docker/build.py --out /absolute/existing/parent/build-attempt-01
```

Use a new output name for every attempt. The builder freezes an allowlist of recipe files, notices and documentation,
hashes the copied bytes and checks them before every build phase. Both image
stages use that copied Dockerfile. It fetches public sources and dependencies into a
new image, verifies the upstream commit, all five submodules, Cargo.lock, Rust
1.93.0 and dependency archive/recipe checksums, then compiles offline in its own
2 CPU, 3 GiB memory and swap, 256 PID container with a one-hour deadline.
Package/license assertions remain mandatory. It retains build.json and exact
logs, removes owned containers and records the final image ID under
`images.runtime`. Failed attempts remain available for diagnosis. Cleanup queries have bounded
recovery, check each resource independently and always finalize the receipt and
close the workload lock. Failed identity checks leave the resource untouched
and record unresolved cleanup. Build images are retained for review.

Both builder and runtime use the same digest-pinned Ubuntu 24.04 base and the
fixed 20261009T000000Z APT snapshot. The exact package inventory is shipped in
`/opt/docker-build.json`. Inputs are pinned for rebuilding, but identical image
bytes have not been demonstrated. Compile timestamps and layer metadata can
vary. The APT mechanism is documented by the
[Ubuntu Snapshot Service](https://snapshot.ubuntu.com/).

Run the exact image ID from build.json:

```sh
python3 vanguard/docker/run.py --image sha256:THE_RECORDED_IMAGE_ID --out /absolute/existing/parent/journey-01
```

The launcher uses your nonroot UID, no external network or published ports, a
read-only image, 2 CPU, 2 GiB memory with no swap, 256 PIDs, no capabilities and
no new privileges. Wallets, seeds, logs and chain state live in a disposable
tmpfs. Only result.json and the container ownership/cleanup receipt reach the
fresh output directory. Share result.json only.

The builder requires a local Unix Docker socket and matching client/container
kernel boot IDs. Remote daemons and separate Docker VMs are refused. Before
source fetching and compilation, a small owned container measures actual
Docker-host available memory and free space on the Docker data filesystem; it
requires five and ten GiB respectively. Only the small digest-pinned base image
is pulled before this host witness. The probe has no network, a read-only root,
64 MiB memory with no swap, 16 PIDs and an exact read-only Docker-data mount.
It reports only capacity scalars and a boot-ID hash, then removes itself.

The native five-GiB host memory/disk admission remains unchanged. This separate
contained route checks five GiB available on the actual Docker host/VM and the
output filesystem, then checks at least 1.5 GiB available within its enforced
two-GiB cgroup. It also requires writable private tmpfs space. It refuses an
unlimited, overcommitted or incorrectly configured container. The contained
policy is separate from the historical host-specific kit.

The journey mines disposable funds, receives 5, sends two CARROT/type-7 payments,
restores the recipient, spends 2 later and exercises the native CLI. Success
requires `PASS_NATIVE_JOURNEY` and owned cleanup. Its deadline is 1200 seconds.
Ctrl-C or SIGTERM asks the exact owned container to stop and allows 90 seconds
for child cleanup. The launcher recovers interrupted creation by its exact UUID name and verifies
the ID, image and invocation label before stopping or removal. It writes the
terminal receipt even when a cleanup query fails. No other container is stopped.

For acceptance, retain a fresh passing journey, a five-second deadline attempt
with `--deadline-seconds 5`, and a live interruption attempt with
`--interrupt-after 1`, each under a new output. Refusal fixtures do not replace
these real native executions. Independent review and authenticated website
publication are still required. The original seven-target release remains open;
the three previously accepted downloads keep their existing decisions.

Parent SOURCE HOLD from receipt `675d81524fbde416a7194e2cdf57846548b8e64b3e805709dfaff5f601268d40`
remains pending independent review of these source corrections. Attempt03 was
stopped diagnostically through its original owner cleanup before image
assembly. No corrected build, journey or distribution is accepted. Parent
owns those gates; new native CI publication remains paused.
