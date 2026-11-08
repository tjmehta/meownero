# Native policy helper and template result

At 2026-10-20 13:08 UTC, the single approved corrected-candidate attempt finished
with `PASS_NATIVE_POLICY_HELPERS_AND_TEMPLATE_ONLY`. Two invocations with distinct
fresh TESTNET data roots produced byte-identical JSON. This advances the native
policy prerequisite; the shared-network candidate remains blocked and non-public.

## Exact execution binding

The executed clean checkout was `a1558795663e5999785a5586bf6c755c7826071a`, with
implementation `2417930cc649f24e1ba4b175a95f4ede28e6c42d`. The authenticated
[platform rebind](<private-tracker>/TJS/issues/TJS-2504#comment-0ae5446a-0da7-4f75-9604-50b4e7b090c8)
authorized this one finite attempt. Its original author, timestamp and body are
retained in [grant.json](evidence/native-policy-attempt01/grant.json).

| Binding | SHA256 or revision |
| --- | --- |
| Upstream | `e151643c5269c83bf24a83b2548e2493876026b2` |
| Canonical profile | `56a25f173448b3caa34ae9bb29761f5d467376df4470902fd89824ddc11fe4e8` |
| Ten-file overlay | `32c40224dcd618995ef4d846cab411a85783314da79a803ed16074241780312c` |
| Source lock | `f70160e8b7de56bfaed50ed6d29155ea0fcb41789f0c2cfcd15019085c82d001` |
| Executed runner | `640ab1c99f537201c34b69cda5852c126e92725b8ad6d4f8942119e7b9ce8587` |
| Native policy source | `a9919e59720261debd5b4519b22944190773fd11721d123d41e22bcee295da3e` |
| Executable | `2ec35d3debd8d51fa82d68e9bc301f97f128d5181f0b2768e7f519cabd53940f` |
| Each native JSON output | `d17081c14440119ff09fe035dc5b087bf173c2674ab765d1bdba07a638e5affc` |

All eleven frozen candidate inputs matched both approved and implementation Git
objects before execution. All 38 bound upstream inputs matched their working
bytes and pinned Git objects before and after the attempt. Fresh upstream and
submodule archives were exported, the exact overlay applied, and offline Cargo
inputs copied into owned staging. No prior build objects were reused. The
[driver receipt](evidence/native-policy-attempt01/receipt.json) retains archive,
cache, toolchain, applied-source and binary bindings. Exact executed inputs are
under its sibling `executed/` directory. An independent post-build check matched
all ten applied source hashes and the executable digest before cleanup.

## Observed invariant map

Counts below apply to **each** of the two native invocations.

| Requirement | Native observation | Limit |
| --- | --- | --- |
| Selected reward/target and foreign behavior | 13,608 vectors pass for MAINNET, TESTNET, STAGENET and FAKECHAIN, versions 1–18, reward penalties, overweight refusal and supply boundaries; target is 90 for dedicated TESTNET and inherited 60/120 for foreign selectors | Helper execution; no long-lived issuance or difficulty/capacity trial |
| Address separation | 39 checks pass: dedicated standard/integrated/subaddress roundtrips, bilateral foreign-selector refusal and upstream TESTNET/historical prefix rejection | No native P2P, bootstrap, wallet-file or database-profile refusal |
| Coinbase construction | 24 height-one CARROT constructions pass across zero/positive/saturated accounting, fees and penalty weights; explicit zero-reward genesis construction and genesis-fee refusal also pass | No non-genesis block admission, mining, maturity or funded spend |
| Genuine chain selection and template | Actual TESTNET core with null test options reports target 90/v18 and produces a height-one 9-MEOW template | No daemon RPC/P2P listener, wallet or cross-node transaction |
| Positive reset control | `reset_and_set_genesis_block` accepts the already admitted genesis at the same API boundary | Historical adverse reset cases were not rerun on this candidate |
| Repeatability | Separate fresh roots yield identical native summaries | Independent fresh databases are not peer persistence/recovery proof |

The exact outputs are [policy01.json](evidence/native-policy-attempt01/policy01.json)
and [policy02.json](evidence/native-policy-attempt01/policy02.json); both native
stderr logs are empty. Complete configure/build logs are retained. Only the
`vanguard_network_policy` target was built. In particular, the overlay's changed
RPC server source was not compiled by this target. Native adjusted-time window
and foreign-selector differential cases remain unexecuted.

## Resource admission and cleanup

The independent read-only preflight at 12:54:24 UTC observed 7,034,884,096
available memory bytes, 1,114,392,207,360 free disk bytes and load averages
3.501/3.268/3.103 on 12 logical CPUs. No matching native processes or containers
were found. The original regular lock file, device 66306/inode 657237, uid 1000,
mode 0600, was acquired nonblockingly and released immediately after that check.

The frozen driver reacquired that original lock and repeated admission before
staging and before container creation: available memory was 7,858,208,768 and
7,654,895,616 bytes respectively, with disk above 5 GiB and no matching native
collision. Supervisor load/memory samples cover the attempt. Actual Docker
containment matched network-none/no ports, 2 CPUs, 4 GiB memory/no swap, 256 PIDs,
one compile job, all capabilities dropped, no-new-privileges and no core dumps.
The pinned builder was used locally with no pull and the Rust toolchain read-only.

The driver finished in 829.2 seconds within the 900-second total grant and its
880-second execution limit. Container exit was 0, peak cgroup memory was
1,715,228,672 bytes, all OOM counters were zero, and the exact container was
removed under the original lock. Independent cleanup verification confirmed its
absence, reacquired/released the same original inode and rechecked all 38 source
bindings. Only owned source/build/Cargo exports, six source archives and the two
stopped data roots were removed. No unrelated workloads were stopped.

The executable and two stopped valueless genesis databases were archived before
removal; archive SHA256 is
`0c967feb803aec1060582f930981e8f9e954130f72ec95153cf88d0a1b8e329c`.
This archive is retained in the issue attachment, not committed as build output.
The [cleanup receipt](evidence/native-policy-attempt01/cleanup-verification.json)
records the exact paths. No native staging, container, host reservation, scheduled
retry, daemon listener, wallet or signing material remains.

## Grant consumption and next capability

Grant `0ae5446a-0da7-4f75-9604-50b4e7b090c8` is consumed. After preserving the
executed runner, the only implementation change adds that UUID to its existing
consumed-grant refusal list. The existing adverse test now includes it; all 14
source/runner checks pass, including refusal before output creation. Source and
documentation whitespace checks pass. Raw generated CMake/toolchain output and
verbatim patch context retain their original whitespace; their full diff-check
diagnostic is preserved in `whitespace-checks.json`. This Python guard change
does not alter the native target, overlay, profile or crypto pins.
The frozen native receipt identifies the pre-guard runner exactly; no second
native invocation was made or authorized.

The next missing capability is a separately agreed full-profile native workload,
not another helper run. P2P/Mining owns freezing the complete daemon/wallet
harness and realistic funding/difficulty/capacity bounds, then obtaining a new
exact platform grant before any heavy build or runtime. Existing capacity is the
proposal; no new infrastructure or endpoint is requested. Fresh original-inode,
memory/disk/load/collision admission and exact owned cleanup remain mandatory.
The consumed helper grant cannot authorize projection, unlock/maturity, native
peer/bootstrap, wallet, persistence/recovery or payment work.

The [remaining integration contract](remaining-integration.md) names the required
daemon/CLI/wallet profile integration and genuine cross-node receive/payment/
restore/subsequent-spend journey. Core/Privacy source consultations are complete;
their full native matrix, independent Core/Security stages and accepted-only
lead integration remain open. No own-branch merge or public activation occurred.
Public launch stays disabled. Needs TJ: None.
