# Owned Ubuntu22 admission for Linux38 and ARM39

This candidate implements the local admission/provenance change requested in
studio comment `c06c9dcb` and the TJS-1245 owned-hardware routing record. It needs
ec85048c's scoped source review by comment before environment qualification and
native execution. It does not accept a release or consume a release-stage decision.

The original Linux38/ARM39 payloads, workflow carriers and input carriers remain
frozen at `3071ff1276aae8cb96ef13619b3fcbb11a6adb8d`. Separate
`local-38-inputs.json` and `local-39-inputs.json` in the adjacent
`evidence/vanguard-local-runner-tjs1882-2026-10-19/` directory change only the
controller source binding and add an origin record. All source, Rust, dependency,
image, ABI, target and resource pins retain their frozen values. These are local
execution inputs, not GitHub publication packets.

## Change and affected callers

`vanguard/run-portable-linux-ci.py` adds optional `--local-provenance` and
`--local-provenance-sha256` arguments. Hosted execution still requires its real
GitHub runner identity. Local execution requires an actual native Ubuntu 22.04
VM, glibc 2.35, Python >=3.13, a matching physical architecture attested in the
qualification evidence, and exact VM machine-id, boot-id and Docker identities.
It refuses GITHUB_/RUNNER_ variables, Docker overrides, a remote socket,
containerized controllers, another running workload, and a non-task daemon name.
Both normal task names and Lima's `lima-` hostname prefix are supported.

The same full controller calls the same supervisor for fetch, prepare, build,
package and runtime. It forwards the provenance binding into every supervised
phase, which checks it again. Workers, fetch, resources, package diagnostics,
receipt filtering and supervisor bytes are unchanged. There is no local wrapper
or new dependency. Existing frozen hosted workflows are not republished.

Admission still requires >=6 GiB available RAM and ten GiB output/Docker disk
reserve before compilation and at each phase. Compilation remains 2 CPUs,
4 GiB RAM/total swap, 3600 seconds; the controller retains its finite 115-minute
budget. Runtime remains 2 CPUs, 2 GiB/no extra swap, 256 PIDs, offline, read-only,
and without capabilities. Original exact-container cleanup, owned-process
supervision, shared lock, ABI/privacy/notice checks and ten controls remain.

Public receipts identify `OWNED_NATIVE_UBUNTU22_VM`, retain hashes of the
qualification, machine, boot and daemon identity, and omit GitHub run/SHA fields
and raw daemon/VM identifiers. The qualification digest links external operator
evidence; it does not independently prove that evidence true. Reviewer and
operator must inspect the actual host/VM evidence before execution and acceptance.

## Qualification and next execution

After scoped source clearance, the writer first qualifies a separately owned
native aarch64 Ubuntu22 VM on build-mac. Installed Lima 2.2.0 includes a pinned
Ubuntu22 aarch64 image:

`https://cloud-images.ubuntu.com/releases/jammy/release-20260705/ubuntu-22.04-server-cloudimg-arm64.img`

SHA256: `9c2ddc65079f9a285ca7c9efabdee6d58ff7dd2b08a130114426d2020506db7a`.

Use a task-specific VM name and bounded disk/RAM/CPU allocation after checking
fresh host headroom. The installed template's unpinned fallback images and
generic Docker template's curl-to-shell installer are not qualified inputs.
Record the exact VM configuration/image, host arm64 identity, virtualization
mode, guest OS/kernel/architecture, CPU AES/PMULL/SHA1/SHA2 features, Python and
Docker toolchain origins/versions, idle daemon and resource gates. Rootful Docker
must be inside this VM with its own `/var/lib/docker` and local default socket.
Keep existing Colima configuration/workloads intact. There is no qualified
new VM or toolchain yet; in particular, Ubuntu22's default Python is insufficient.
Record and checksum any guest-only preparation before claiming qualification.

Make a private provenance JSON from those actual observations, with exactly
these fields (angle-bracket values are documentation placeholders):

```json
{
  "schema": "meownero-owned-native-linux-runner/1",
  "issue": "TJS-1882",
  "target": "linux-aarch64",
  "environment": "tjs1882-arm39-<owned-id>",
  "physical_host_architecture": "arm64",
  "machine_id_sha256": "<SHA256 of /etc/machine-id bytes>",
  "boot_id_sha256": "<SHA256 of /proc/sys/kernel/random/boot_id bytes>",
  "docker_id": "<actual docker info ID>",
  "docker_name": "<actual task VM Docker name>",
  "qualification_evidence_sha256": "<SHA256 of retained qualification evidence>"
}
```

Run the complete controller inside that VM with the separately named local
inputs, their SHA256, the provenance path/SHA256 and a new owned output. Do not
set hosted variables or call `--phase` directly. A VM reboot or daemon identity
change requires fresh qualification/binding. Copy only the exact allowlisted
source inputs; keep source and compilation offline after the fetch phase.

Acceptance still requires native daemon/CLI/RPC and archive hashes, manifest,
actual ELF/import/glibc-floor <=2.35 audit, clean extract and preflight, receive
5, two type-7 CARROT payments, restored address/balance/output/key-image equality,
later spend/receipt 2, restored CLI use, all ten controls, and owned cleanup.
Independent review must bind the resulting exact archive and evidence.
Ubuntu22 does not establish Debian12/Fedora/RHEL/Arch/openSUSE acceptance.
Linux38 follows on dev only when an isolated native x86_64 Ubuntu22 environment
and host headroom qualify; its shared Ubuntu24 daemon cannot run this command.
Fetch retained captures before disposing of the exact owned VM and scratch.

## Checks and current limits

Seven admission tests cover both architectures and adversarial identity, OS,
libc, Python, container, environment and daemon cases. A real subprocess on dev
refuses Ubuntu24 for both full-controller and direct-phase invocations before
output creation. An admitted-controller fixture verifies provenance propagation
into the supervisor, truthful local receipt fields and lock cleanup; its mocked
supervisor stops before any source fetch or build. The 81 existing linker inventory, privacy and package-failure
cases pass. Both local input sets validate all 16 helper bindings. All 36 frozen
bindings are preserved. Actual small owned-process normal/deadline fixtures
prove supervisor reaping while preserving an unrelated process. These are source
and supervision checks, not native Meownero build/journey evidence. The first
deadline observer caught the wrong expected exception type; its terminal cleanup
receipt is retained and excluded, and a corrected observer passed separately.

Fresh read-only checks found native dev x86_64 Ubuntu24 with shared production
Docker workloads, and build-mac Darwin arm64 with 128 GiB physical RAM, approximately
676 GiB free disk and native Virtualization.framework support. Existing Colima
remains a 6 GiB Ubuntu24 guest with about 5.34 GiB available and no running
containers. No new VM, build or CI dispatch started.

No active Actions runs were returned for this repository. Current included
minutes/storage remain **unconfirmed**: installed GitHub credentials lack the
`user` scope and billing queries return HTTP404. This is not fresh evidence of
quota exhaustion or spend authority. Keep i68635's existing parent-owned route,
packet `03d24579` and spending-limit asks separate. ARM12's terminal build failure
on `sys/mman.h`, historical 3/7 native acceptance, and published Docker acceptance
remain intact. The full seven-target release remains open.

## Primary references

- Installed controller, frozen inputs, builder and check scripts at this
  candidate; the frozen controller is retained in git at `3071ff12`.
- [Docker context inspection](https://docs.docker.com/reference/cli/docker/context/inspect/)
  defines the actual endpoint inspection used by admission.
- [Docker info JSON](https://docs.docker.com/reference/cli/docker/system/info/#format-the-output---format)
  supplies daemon identity, architecture, OS and data-root observations.
- [Lima templates](https://lima-vm.io/docs/templates/) and the installed 2.2.0
  Ubuntu22 image template provide a possible owned VM route; no image was fetched.
- GitHub's authenticated billing responses specifically report missing `user`
  scope. No token refresh, authentication change or capacity claim was made.

Needs TJ: None new. Next owner is ec85048c for scoped source review, then writer
92a7b4f2 for qualification and actual ARM39/Linux38 execution.
