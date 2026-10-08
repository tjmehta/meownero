# Longer Vanguard tests: build-mac runtime blocker

Historical preflight, superseded by the [completed writer results](vanguard-soak-tjs1816-results-2026-10-08.md). The observations below describe the earlier blocked attempt.

TJS-1816 was incomplete at this preflight. No heavy build, native payment trial, recovery event or
new verifier baseline ran. Writer disposition is BLOCKED on an unavailable
contained Docker runtime on build-mac. The accepted work is not reopened.

## Changed

The harness supplied a clean isolated task branch at the exact accepted base
`72e572bd2c6725eb59d5598852d782185e225504`. This branch adds the
[revision-1 test protocol](vanguard-soak-tjs1816-protocol-2026-10-08.md) and
[raw read-only preflight evidence](evidence/vanguard-soak-tjs1816-access-2026-10-08/raw/commands.json).
The protocol is also published in the issue's `test-protocol` document, revision
`6a5a318e-d821-49b7-98b5-f2f6485ad0e4`, before native execution. The added
collector reproduces only read-only access checks. It is not a soak runner.

No existing Vanguard source, lock, verifier, refusal suite or accepted receipt
was changed. No remote staging checkout, container, daemon or wallet was created.
Both dirty primary checkouts, existing processes and caches were preserved.

## Verified

On 2026-10-08 at about 15:13 UTC, SSH with `BatchMode=yes`,
`StrictHostKeyChecking=yes` and `ConnectTimeout=10` reached hostname `build-mac`.
It returned macOS 26.5.1, Darwin 25.5.0, ARM64, 18 CPUs and
137,438,953,472 bytes of RAM. `vm_stat` recorded 631,438 free 16,384-byte pages,
about 9.64 GiB. Disk availability was 105,823,796 KiB, about 100.92 GiB. These
host figures do not establish resources available inside a Docker VM.

Docker client 29.2.1 is installed. The default context is Colima. Every installed
endpoint checked failed to connect:

| Probe | Observed result |
| --- | --- |
| `colima status` | Exit 1, `colima is not running`. |
| `docker --context colima version` | Exit 1, `~/.colima/default/docker.sock` missing. |
| `docker --context desktop-linux version` | Exit 1, cannot connect to `~/.docker/run/docker.sock`. |
| `docker --context default version` | Exit 1, cannot connect to `/var/run/docker.sock`. |
| `docker --host unix://~/.colima/docker.sock version` | Exit 1, cannot connect to the legacy socket. |

The process probe found Docker's privileged vmnet helper and a Dockerman CI
listener, but no matching Docker engine/VM, Colima, compiler, Vanguard or Monero
process. The helper alone is not a running Docker engine. An earlier
`openclaw nodes status --json` returned no connected build-mac execution node. The
documented native SSH route worked independently of that node list; this is
not a machine-inaccessible or SSH-credential blocker.

The remote primary is dirty at
`17bb881c2470add06129ac69aa72fae89a8d52b3`, has no `vanguard` directory, and
contains older network-build caches. Its visible Rust toolchain directory is
`1.95.0-aarch64-apple-darwin`. Neither that directory nor older caches proves a
compatible pinned Linux toolchain or FCMP++ executable. Image/cache provenance,
Docker VM capacity and new executable identity remain unverified because the
engine is unavailable. No old ARM or x86 binary was relabeled as this candidate.

Raw commands, UTC timestamps, durations, stdout, stderr and each exit are saved
under `research/evidence/vanguard-soak-tjs1816-access-2026-10-08/raw`. The raw
manifest was checked successfully. No disposable wallet secrets exist in this
run because no wallets were started. Source syntax and whitespace checks apply
only to the preparation artifact, not to native behavior.

Reproduce these access checks into a new directory:

```sh
python3 -B research/evidence/vanguard-soak-tjs1816-access-2026-10-08/collect-preflight.py \
  --out "$PAPERCLIP_RUN_SCRATCH_DIR/tjs1816-preflight-new"
sha256sum -c research/evidence/vanguard-soak-tjs1816-access-2026-10-08/MANIFEST.sha256
```

The outer manifest uses paths relative to the repository root. The raw manifest
uses paths relative to its own directory. The collector refuses an existing
output path and performs no runtime start, configuration change or native test.

## Protocol result rows

| Requirement | Writer result | Evidence or missing check |
| --- | --- | --- |
| Exact accepted base and owned isolated local checkout | PASS | Harness branch and Git HEAD inspected. |
| Concrete protocol published before execution | PASS | Protocol file and Paperclip revision above. |
| Supported build-mac transport with host-key checking | PASS | Raw `host` probe. |
| Running contained Docker runtime precondition | FAIL | Five stopped/unreachable runtime probes above. |
| Image, source, toolchain and native build provenance on build-mac | NOT_RUN | No engine; no task-owned source/build has been prepared. |
| Two independent trials, each at least 1,800 measured seconds | NOT_RUN | No native trial launched. |
| At least 32 exactly-once confirmed payments per trial, repeated cohorts on both nodes | NOT_RUN | No native payment submitted. |
| Persistent daemon and wallet restart | NOT_RUN | No owned daemon or wallet started. |
| Queued disconnect/reconnect | NOT_RUN | No contained P2P bridge started. |
| Partition/rejoin and main-chain reorg | NOT_RUN | No test chain created. |
| Wallet restore and later confirmed spend | NOT_RUN | No disposable wallets created. |
| Malformed/invalid and conflicting-spend rejection followed by healthy payment | NOT_RUN | No native rejection or positive control exercised. |
| Exact transaction/block/destination/amount binding, empty queues and no duplicate credit/spend | NOT_RUN | No new native RPC history. |
| Live process/executable receipts, resource trend, final peaks, child exits and OOM counters | NOT_RUN | No owned native children or trial cgroup. |
| New verifier passing live baseline and adversarial refusals | NOT_RUN | New soak implementation and verifier remain to be written. |
| Existing load/P2P/backlog gates preserved | PASS | Existing Vanguard files untouched. Their native/refusal reruns are NOT_RUN. |
| Complete executable test package and independent exact-candidate review | NOT_RUN | Preparation artifact only; no candidate for acceptance. |
| Accepted-candidate parent integration and next-step readiness | NOT_RUN | Requires native results, independent acceptance and parent verification. |

## Unconfirmed and next

The assignment says to reuse existing Docker and excludes global
runtime/settings changes. Starting a stopped shared engine changes runtime
state; I did not infer an exception. This is a task-scope stop, not an automatic
approval rejection or a failed product test.

Unblock owner is the studio lead, agent
`38e398e0-4ce9-4c35-91f5-90d48ac757fc`, coordinating with the parent OpenClaw
capacity/transport preflight. The smallest unblock is either a reachable
already-running authorized build-mac Docker endpoint, or a resolved authorization
for starting the existing installed runtime with its current settings. No
global install, host restart or network-policy change is needed by this request.
The lead was notified on the current issue while it was open. Any runtime start
must establish VM resources, compatible image/cache pins and ownership before
building; current host availability alone is insufficient.

After that resolution, the writer owns task-only staging, runner/verifier
implementation, both measured trials, safe corrections and reruns. The existing
reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` owns one independent review
stage once the exact native candidate and hashed evidence exist. Review was not
activated for this incomplete preparation. The parent owns integration and group
delivery after independent acceptance. This report does not claim readiness for
the next cross-host step or production security/capacity/WAN assurance.

Learning delta, observed behavior: a missing build-mac entry in the gateway node list
does not imply lost SSH access. On this run SSH worked and the actual blocker
was the stopped Docker runtime. Keep those failures separate during continuation.

Needs TJ: None. The runtime-scope decision is routed through the studio lead.
