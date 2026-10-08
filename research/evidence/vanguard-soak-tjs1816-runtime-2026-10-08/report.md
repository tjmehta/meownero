# build-mac startup failure and stale process identity

TJS-1816 remains BLOCKED. The authorized existing-profile startup was attempted
once and failed before Docker became available. There were zero heavy builds,
native trials, payments or recovery events. The requested test outcome is incomplete.

## Authorization and attempted action

The answered interaction `96c16832-aaee-45d0-bbe5-1c6abdd6dc87` resolves the
earlier startup-scope question. It authorizes routine startup of the installed
Colima runtime with its saved settings, followed by the frozen test protocol.
It specifies one startup and preserving other workloads. It does not authorize
installation, recreation, settings changes or shared-runtime repair.

Before startup, the writer read the saved default profile, startup help, existing
instance metadata, Docker contexts and active-work process list. The profile
has 4 CPUs, 6 GiB memory, a 100 GiB data disk, ARM64, the VZ driver, Docker,
Kubernetes disabled, and no custom provisioning scripts. `autoActivate` and
`sshConfig` are enabled. The current Docker context was already Colima and the
host SSH configuration already included Colima's generated configuration.
Existing default Lima provisioning is runtime-managed; no custom scripts or
global settings were added by the writer.

The writer executed this exact command at 2026-10-08 15:23:35.500 UTC:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 \
  build-mac 'colima start default --save-config=false'
```

The command returned exit 1 after 2.031 seconds. Its stdout reports failure
to inspect the existing instance because `ha.sock` refuses the host-agent
connection. Stderr reports failure starting the VM. Raw argv, UTC start,
duration, stdout, stderr and exit are in the
[runtime package](evidence/vanguard-soak-tjs1816-runtime-2026-10-08/startup-command.json).
No retry, force-stop, manual metadata removal or process signal was issued.

The saved profile SHA256 is unchanged before and after the attempt:
`953069eb536626c5b04906c9122d3f35d54e4d3091c50f5bc4adf7cc7f627697`.
The runtime-generated `lima.yaml` modification time changed during startup;
this report does not claim that every runtime-generated file remained unchanged.

## Actual blocker

Strict-host-key SSH still reaches build-mac, macOS 26.5.1 / Darwin 25.5.0 ARM64,
18 CPUs, 128 GiB host RAM and about 101 GiB available host disk. These host
figures do not prove memory or disk available within an operational Docker VM.
Colima is version 0.10.3 and Lima is version 2.2.0. All four installed Docker
endpoints failed the baseline API checks. After the startup attempt, Colima
reports `Broken`, `colima status` says it is not running, and the Colima Docker
socket remains absent. Existing container inventory cannot be read.

Both existing `ha.pid` and `vz.pid` contain `75180`. The files date from
September 16. Live `ps` binds that PID to an iOS simulator `deviceaccessd`
process started October 8 at 02:22:27 local time. The exact Colima instance
inspection also returns `hostAgentPID=75180` and `driverPID=75180`.
The corrected bounded `lsof -n -a -U <exact-ha.sock>` probe has no matches and
exit 1. The active-work probes show no Colima/Lima VM or native build/test.

Force-stop would risk the unrelated simulator process. This is an inference
from the live PID binding and the pinned
[Lima 2.2.0 force-stop implementation](https://raw.githubusercontent.com/lima-vm/lima/v2.2.0/pkg/instance/stop.go),
which signals positive recorded driver and host-agent PIDs. No such stop was
executed. Generic newer recovery documentation cannot establish the behavior
of the installed version.

The local documented `ghc` helper delegates to repository navigation and an
editor launch. Its source is included with a digest in `references.json`.
The supported native transport used here is strict-host-key SSH to build-mac;
this is an existing-runtime state blocker, not an inaccessible-machine claim.

## Preservation and cleanup

The owned local branch remains based on accepted commit
`72e572bd2c6725eb59d5598852d782185e225504`, with the prior preparation commit
`e10dcbe0f93efab52de8ca046c42fcd9a79ad5ed`. Existing `vanguard/` source and
accepted gates have no diff from the accepted base. Both dirty primary
checkouts were inspected read-only and preserved. No remote staging checkout,
image, container, network, wallet, native process or heavy-work lock was created.
Nothing task-owned requires container/process cleanup. The failed startup did
not produce a running runtime to stop. Historical PID/socket files were left
intact, and PID 75180 was observed alive after diagnosis.

One diagnostic used `lsof -U` without `-a`, which selected unrelated Unix
sockets. That output is retained privately in this run directory. The public
package clearly marks the omitted rows, records the original output hash and
includes the corrected exact-path probe. No wallet secrets exist in this run.

Reproduce read-only diagnosis into a fresh output path:

```sh
python3 -B research/evidence/vanguard-soak-tjs1816-runtime-2026-10-08/collect-runtime.py \
  --out /tmp/tjs1816-runtime-new
cd research/evidence/vanguard-soak-tjs1816-runtime-2026-10-08
sha256sum -c MANIFEST.sha256
```

The collector never starts, stops or repairs the runtime. Do not replay the
recorded startup attempt without resolving the current stale-state blocker.

## Protocol result matrix

| Requirement | Result | Observation |
| --- | --- | --- |
| Exact accepted base and owned isolated local checkout | PASS | Accepted ancestor retained; no unrelated changes touched. |
| Protocol frozen and published before execution | PASS | Revision 1 from prior run remains unchanged and published. |
| Supported build-mac transport with host-key checking | PASS | Fresh SSH command/exit receipts. |
| Saved-profile and workload inspection before startup | PASS | Profile, context, instance metadata, help and process baseline saved. |
| Authorized unchanged-settings runtime startup | FAIL | One attempt exited 1; existing host-agent socket refused connection. |
| Reachable Docker API, container inventory and VM capacity | FAIL | Runtime remains unavailable; operational inventory/capacity NOT_RUN. |
| Source, image, toolchain and native binary provenance | NOT_RUN | Engine unavailable; no owned native build staged. |
| Two independent trials, each at least 1,800 measured seconds | NOT_RUN | Zero trials launched. |
| 32 exactly-once confirmed payments per trial across both nodes | NOT_RUN | Zero native payments. |
| Persistent daemon and wallet restart | NOT_RUN | No native children. |
| Queued disconnect/reconnect | NOT_RUN | No native bridge. |
| Partition/rejoin and main-chain reorg | NOT_RUN | No fresh test chain. |
| Wallet restore and later confirmed spend | NOT_RUN | No test wallets. |
| Invalid/conflicting rejection followed by healthy payment | NOT_RUN | No native RPC history. |
| Exact tx/block/destination/amount binding; no duplicate credit/spend | NOT_RUN | No new payment evidence. |
| Process identities, resource trend, final peaks, child exits and OOM counters | NOT_RUN | No owned native process generations or trial cgroups. |
| New verifier baseline and adversarial refusals | NOT_RUN | Soak runner/verifier implementation remains outstanding. |
| Existing load/P2P/backlog gates preserved | PASS | Their source is unchanged; new native/regression runs NOT_RUN. |
| Complete executable package and exact-candidate independent review | NOT_RUN | Runtime diagnosis package only. |
| Parent integration and next-step readiness | NOT_RUN | Requires native trials, independent acceptance and parent verification. |

## Unblock owner and continuation

Studio lead `38e398e0-4ce9-4c35-91f5-90d48ac757fc` owns the smallest missing
action: supply a reachable authorized build-mac Docker endpoint, or coordinate
an exact non-signaling stale-metadata recovery and unchanged-profile retry.
One concrete candidate is reversible quarantine of only verified stale
`ha.pid`, `vz.pid` and `ha.sock`, after fresh no-VM/process-ownership checks,
preserving disks and settings. That shared-runtime repair was not executed.

Pending interaction `7c366606-1c35-48c5-ad8b-f41e462627de` is addressed to the
studio lead and wakes this writer on resolution. The writer retains task-only
implementation and native-test ownership. After runtime resolution, implement
the soak runner/verifier, execute both fresh bounded trials, correct safe
in-scope failures and freeze the actual candidate and evidence. Then activate
one independent review stage for reviewer
`ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`. Parent integration and WhatsApp group
delivery remain downstream of independent acceptance. No acceptance or
next-step readiness is claimed here.

Needs TJ: None. The runtime repair is routed to the studio lead/parent.

Observed learning: stale runtime PID files can name unrelated live simulator
processes. Socket connection failure plus a live numeric PID does not prove
runtime ownership. Inspect process identity before any shared-runtime signal.
