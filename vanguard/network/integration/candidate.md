# Source candidate and current boundary

Latest source delta: [control-storage.md](control-storage.md) records the operator handback and the v2 storage fit/refusal contract. The proposed 1/11/2/1 GiB split remains unqualified. Helper/server/lifecycle/inner integration stops at absent concrete authority/interfaces; bootstrap is null and native execution remains NOT_RUN. Earlier source-pass and single-filesystem descriptions below retain historical attribution and are superseded for storage by that contract.

The latest [October 27 lead decision](/TJS/issues/TJS-2504#comment-c78e1c2c-262f-41fb-9f1e-6e3ef52ca45d) supersedes the earlier source-work stop. This candidate adds `profile_outer.py`, `run-outer.py`, outer failure-path tests and four null capability bindings. Read [capability-checklist.md](capability-checklist.md) for kept guarantees, replaceable mechanisms, actual source behavior and precise missing host facilities. The outer lifecycle is implemented; its privileged/delegated manager adapter, hard storage boundary, immutable image and private admission channel remain unbound. This is not a runnable contained host launcher. Native acceptance remains NOT_RUN. The source-only budget is one implementation and one correction pass; no runtime or grant request is authorized here.

This implements the bounded source-only continuation authorized in TJS-2504 comment `cf81ba5e-fcb5-44fe-ae6b-5537f57484bd`. P2P/Mining remains the writer. Native execution, building, source/Cargo build staging, resource admission/reservation, containers and launch are unauthorized in this continuation. `cb95cc036000a70bc688deeba6bff1b384b27eb3` and its executed helper evidence are preserved unchanged. Grant `0ae5446a-0da7-4f75-9604-50b4e7b090c8` remains consumed.

Revision2 reconciles Platform's source findings in comment `ca2ad2ac-d448-44fe-b228-c151c53fbcfe`. The [outer contract](outer-contract.md) is authoritative for the handoff/resource proposal and its unresolved interfaces. The inner now accepts inherited original-lock and existing CONSUMED-ledger descriptors plus a private sealed context; immutable grant v2 excludes runtime facts. It never consumes again or unlocks. Its resource/cleanup rows remain NOT_RUN until an independent outer completion. `platform_bootstrap_sha256` remains null and the source implementation table is empty. Both null and manually populated hashes refuse before grant/resource/native operations. The shared-socket second-admission observer has been removed; its qualified outer replacement is also unavailable and refuses.

This is a source candidate with a concrete named prerequisite. It supplies no qualified outer adapter, manager unit/delegation, offline image archive, fixed filesystem or runtime grant. Exact source hashes do not make this grant-ready. Platform must qualify the new source against an already authorized supported interface for those capabilities, including FD survival and independent recovery/accounting. P2P/Mining remains the same writer and owns the exact source adapter after qualification. No install or reconfiguration is authorized.
The source driver has not been exercised against native binaries. Exact prompts, native daemon startup on the corrected overlay, native frame acceptance and save/reopen behavior remain unmeasured. Source checks settle request field coverage and guard ordering, not native behavior. The successful source-only tests use disposable files and modeled process/counter values. They never touch the original heavy lock or inspect current capacity. No slice PASS is claimed.

## Inputs and commands

`inputs.json` contains SHA256 bindings for candidate files, 32 unchanged repository inputs, 63 distinct pinned upstream paths, including the portable-storage and request/prompt interfaces, RandomX configuration, all ten changed overlay files, the offline Cargo registry/git trees and mounted Rust toolchain tree. Whole-tree digests cover sorted relative paths, file modes, content digests and internal symlink targets, with file counts. The canonical profile remains `56a25f173448b3caa34ae9bb29761f5d467376df4470902fd89824ddc11fe4e8`; overlay remains `32c40224dcd618995ef4d846cab411a85783314da79a803ed16074241780312c`. Filesystem source pin and Git-object equality checks execute without exporting source. No upstream file or consensus implementation changes in this candidate.

Allowed source checks:

```sh
python3 -B vanguard/network/freeze-profile.py --check
python3 -B -m unittest discover -s vanguard/network -p test_profile.py -v
python3 -B -m unittest discover -s vanguard/network -p test_handoff.py -v
python3 -B -m unittest discover -s vanguard/network -p test_outer.py -v
python3 -B vanguard/network/run-outer.py --check
python3 -B vanguard/network/test_network.py --source <pinned-source> --scratch <owned-source-test-scratch> --evidence <network-source-evidence>
python3 -B vanguard/network/test_policy.py --source <pinned-source> --scratch <owned-source-test-scratch> --evidence <fresh-policy-source-evidence>
python3 -B vanguard/network/test_admission.py --scratch <owned-source-test-scratch>
```

`freeze-profile.py --freeze` writes only the local source/input manifest. It never builds or stages upstream/Cargo bytes. Generated source evidence is excluded from the self-binding list. Candidate Git commit and published archive SHA256 are bound separately by the publication receipt and later grant to avoid a self-referential digest.

Future commands, NOT_RUN:

```sh
python3 -B vanguard/network/run-profile.py \
  --inputs vanguard/network/integration/inputs.json \
  --grant-comment <new-authenticated-exact-Platform-comment> \
  --artifact-sha256 <published-candidate-archive-sha256> \
  --context-fd <sealed-private-context-fd> \
  --lock-fd <inherited-original-open-description-fd> \
  --ledger-fd <existing-readonly-CONSUMED-receipt-fd>
```

After the missing Platform interface and implementation are supplied, its exact invocation must enclose this command. The immutable grant authorizes frozen inputs; the outer-created private descriptor context carries observed runtime identities and the existing consumption. Proposed exit3 means refusal, exit124 means deadline, exit1 means failure. Inner exit0 means only PENDING_OUTER_COMPLETION. It establishes no resource/cleanup/native acceptance or launch readiness. Every consumed failure stays consumed with no retry.
The literal future build commands are in `build.sh`: configure Release/ARCH default with tests and Trezor off, manual submodules; build only `daemon simplewallet wallet_rpc_server --parallel 1`. Their native output names are `monerod`, `monero-wallet-cli`, `monero-wallet-rpc`. No fourth helper, funding target, configure fallback, package install, dependency fetch or image pull. Check rustc against the lock, hash all three ELF binaries, inspect NEEDED entries with readelf and retain the RPC translation-unit object/log binding. No ldd execution. Successful build dispatches the same exact container to `python3 -B /out/harness/profile-integration.py` under a 600s timeout. An incomplete build skips native startup.

## Native observation contract

Every proposed output starts with row-level `NOT_RUN` in `inputs.json`. `profile_contract.py` defines required rows and prevents a blanket PASS when any included control is missing, unavailable, failed or skipped. The only possible complete-slice label is `PASS_COMPLETE_BINARIES_GENESIS_PEER_WALLET_BOUNDARY_ONLY`. It would still retain all exclusions below and would not close the full launch task.

| Output | Required witnesses, proposed only |
| --- | --- |
| build.json | Three new binary hashes/ELF dependencies, RPC object/log binding; original source/profile/overlay/toolchain/cache inputs |
| peer.json | Real bidirectional native handshake through the existing bounded Levin framing pattern, captured-frame hashes, equal count1/genesis hash/cumulative work, empty allowed pool reads; daemon get_version hard_forks and hard_fork_info(version18) |
| wallet.json | CLI generation, explicit height setter, save/exit and sequential native getter0 after reopening; pre-provisioned subaddress; standard/integrated/subaddress same-profile parsing and integrated split roundtrip; native foreign-prefix positive any-net fixture and refusal with any_net_type=false/allow_openalias=false |
| auth.json | Each missing/wrong/old-auth request bracketed by an authenticated allowed read against the same process; loaded restricted wallet's 17 schema-valid requests return HTTP200/error-7; fresh process generates distinct login |
| isolation.json | Separate UUID and chain-request native log guard witnesses, healthy matching controls before/after and identical accepted state; launcher-only adverse manifests/copies; bounded counterpart-absent socket census with no external connection, source-bound exclusive-peer policy |
| reopen.json | Owned PID plus start ticks, normal TERM/save/exit, listener absence and open-file-owner release; sequential native reopening of saved bundles; stopped-state cold copies into fresh owned roots; daemon counterpart stopped during retained and restored-root probes |
| resources.json | Shared parent limits/accounting, deadlines, hard disk envelope/free-disk abort and no OOM, conditional on the missing Platform implementation |
| cleanup.json | Exact owned CID/process absence, owned staging removal and original-inode lock release, including independent outer cleanup after controller death |

Wrong UUID changes only the native portable-storage UUID field in an actual captured handshake. It requires `WRONG NETWORK AGENT CONNECTED!` from a new private log interval. Same-UUID wrong genesis first completes the healthy handshake, then sends command2006 with `block_ids` as one 32-byte POD blob and `prune=false`. Its all-zero last hash must produce both native `genesis block mismatch:` and protocol `Failed to handle NOTIFY_REQUEST_CHAIN.` witnesses from the isolated log interval. Healthy matching requests use the dedicated genesis and require response2007 before and after the negative. Serialized requests have frozen digests in `inputs.json`; raw frames stay private. Timeout, disconnect or an unknown handshake tip cannot establish the chain guard. No upstream/historical chain execution is claimed.

The CLI dialogue recognizes the pinned English wallet prompt and exact `Wallet password: ` prompt. It issues `set refresh-from-block-height 0`, `set`, `address new`, `refresh 0`, `save`, `exit`; reopens with `--wallet-file` and requires `set` to show0. Config/password/stdout/CLI seed display remain private. Unknown prompts abort, without speculative input. Each prompt has at most25s and lifecycle TERM20/KILL5 fits the global deadline. Forced kill can clean up but cannot pass persistence. Wallet files never have overlapping writers. A saved manifest binds the controller's known creation provenance, exact file membership and hashes after stop; it cannot authenticate arbitrary foreign LMDB contents.

Restricted denial methods are transfer, transfer_split, sweep_all, sweep_single, sign, sign_transfer, query_key, set_daemon, store, stop_wallet, close_wallet, create_address, create_account, create_wallet, open_wallet, restore_deterministic_wallet and refresh. Every required serialized request field is checked against the pinned native request map. The source checker verifies each method's early restricted guard precedes request-field use. Transaction/unsigned-set/key-image fixtures are only guard-first schema controls. They claim no valid spend/proof construction or consensus refusal. Restore uses a bound public upstream test fixture inside the private controller, never the new wallet's recovery material. Nothing is imported because the restricted guard must return first. An unexpected non-denial aborts the attempt. get_tx_key and proof methods have no denial claim; full keys and every credential remain controller-private.

Restricted get_info connection counts, peer sizes and start time are masked and never used as peer/process witnesses. Native frames and `/proc` PID/start ticks supply those observations. No mining route, full-pool route, privileged submit route, transaction construction, PoW or funding is invoked. The daemon's fork metadata does not establish offline wallet fork agreement.

Explicit native exclusions remain NOT_RUN: foreign-DB identity refusal, TESTNET checkpoint rejection, offline-wallet fork agreement, deterministic seed restore/funded rescan and every non-genesis/full-matrix control. `remaining-matrix.md` preserves all twelve final-candidate rows. Zero premine, 9/90, v18@1, inherited nonzero-unlock proof/maturity guards, h+60 coinbase, projection semantics, roots/reorg/cache invariants and genuine receive/payment/restore/later spend remain mandatory. The 71-block minimum and 80+6/14400s funding proposals gain no authority here.

## Whole-attempt resource proposal and missing prerequisite

See [outer-contract.md](outer-contract.md) for the exact revision2 proposal, all six Platform findings, descriptor/ledger ordering, fixed-disk/offline-image inputs, manager recovery and final receipt requirements. It supersedes revision1's unreachable independent-open/flock/ledger draft, metadata watchdog and premature inner cleanup PASS. Rootful cgroupfs requires an authorized Platform interface; rootless/systemd is not assumed compatible. The proposed common parent keeps2CPU/4GiB/no-swap/256PIDs, with work3840MiB/224PIDs and recovery256MiB/32PIDs. OOM grouping applies to work; recovery must survive work-subtree termination. Its actual manager support and accounting remain unavailable.

Keep original device66306/inode657237,5GiB memory/20GiB backing admission, fixed filesystem<=15GiB,4GiB free-disk abort, two admissions, one compiler job and4500=3600+600+300s. Load1/5/15<=6.0 remains a proposal. The canonical2026-10-20T13:34:05Z snapshot remains dated evidence,605,360,128 bytes below the memory floor. No capacity feasibility or current admission is established. All setup, image import, build, runtime, export, private cleanup and daemon/helper shutdown must be counted. No parent-wide kill is claimed to preserve an exporter in that parent.

The source lifecycle and checklist are ready for one exact Platform qualification. The remaining adapter/host-capability work stops at the named independent keeper/recovery/observer and hard storage prerequisite. Rootful/loop/ext4 are replaceable proposal choices, as detailed in the checklist; the existing inner still enforces its frozen mechanism until a separately reviewed delta changes it. No runtime grant is requested against this incomplete adapter. No Core or Privacy consultation is repeated. Preserve their authorship and all full-candidate acceptance requirements. The latest lead decision places any exact runtime grant after the existing independent Core and Security reviews.

## Source references and independent gates

Source behavior is checked against Git `e151643c5269c83bf24a83b2548e2493876026b2`, using the paths and hashes in `inputs.json`. Existing implementations reused are `network.py`/`policy.py` overlay, `run-genesis.py` admission/collision vocabulary and `daemon-p2p.py`'s bounded native Levin framing. Native restricted-wallet schemas, prompts, daemon flags and three CMake target/output mappings are verified from the pinned local source, not inferred from current upstream releases.

Official resource references read for this proposal are [kernel cgroup-v2 hierarchy/controllers](https://docs.kernel.org/admin-guide/cgroup-v2.html), [systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html), [Docker create controls](https://docs.docker.com/reference/cli/docker/container/create/) and [Docker daemon configuration](https://docs.docker.com/reference/cli/dockerd/). The hierarchy proposal follows the kernel's ancestor-enforced limits. Documentation establishes the interfaces; it does not establish this host's version, permissions, cgroup topology, fixed-filesystem support, rootless compatibility or capacity. Those runtime facts remain NOT_RUN and belong to Platform's exact prerequisite. No package/service/host reconfiguration is authorized by this source artifact.

Preserve Core stage `bab7a7aa-fe78-4cc9-8822-2b3d1e9b35de`, decision `52c7a4e3-be38-4338-bd39-2da99c28b85d`, changes-requested count1, subsequent independent Security, exact native acceptance and lead accepted-only integration. No merge, operator assignment, public endpoint, account/provider/deployed-runtime change or launch. Needs TJ: None.
