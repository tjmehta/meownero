# TJS-2504 source-bound shared-testnet checkpoint

2026-10-19. This is an implemented protocol proposal checkpoint, **not a
launchable candidate**. The first network-native claim is blocked on a
Core/Cryptography decision about genesis and activation. No daemon, wallet,
service or external endpoint was started for this checkpoint. Configuration
checks cannot establish native separation, consensus or recoverability.

## Bindings and selected direction

Repository base `0aafdbd2ed1accda8ddd0eccba1e49f1add0d0f0`, upstream
`e151643c5269c83bf24a83b2548e2493876026b2`. The original
[source lock](../source-lock.json) stays unchanged, SHA256
`f70160e8b7de56bfaed50ed6d29155ea0fcb41789f0c2cfcd15019085c82d001`.
It pins Cargo.lock
`6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239`,
Rust 1.93.0, monero-oxide `31c26d96eaadbba910ffe3613ad8b4cf9c598a93`,
crypto-bigint `78352771313f1e9b8e48abe5ce30d50d6bdd291d` and five
upstream submodules. [Source bindings](source-bindings.json) hash the thirteen
actual native files inspected. This is not an assertion that an entire source
tree, submodule worktree or binary is clean. The read-only local source has a
pre-existing `tests/CMakeLists.txt` injection, outside these thirteen paths.

[profile.json](profile.json) has canonical SHA256
`d3d9905bd3c1464f4940f49e0872dfa8e7510127ddf83b781d6c6743e0627168`.
Canonical means UTF-8 JSON with sorted keys, compact separators and no nonfinite
numbers, as implemented by `profile_hash` in [network.py](network.py). This
digest identifies bytes and decisions; it is not a signed release identity.

Use a dedicated native TESTNET configuration in an isolated source copy rather
than repurposing upstream FAKECHAIN. This keeps network selection shared by
daemon, wallet RPC and CLI and avoids FAKECHAIN's special database and validation
semantics. The existing packages need rebuilding/integrating for this profile.

| Item | Proposed value or explicit unresolved field |
| --- | --- |
| Namespace | `meownero-vanguard-shared-testnet-v1` |
| P2P UUID bytes | `e16d7839ed4d3ec8363d078df18fff6d`, first 16 SHA256 bytes of namespace plus `/network-id` |
| Standard/integrated/subaddress prefixes | 4240 / 4241 / 4242, distinct from upstream and historical Candidate M; native encoding/decoding is still NOT_RUN |
| P2P / daemon RPC / reserved disabled ZMQ / wallet RPC | 48080 / 48081 / 48082 / 48083 |
| Data root | A fresh private task directory, then namespace/node ID; native `--testnet` appends `testnet/lmdb` |
| Genesis | Zero reward/premine required. Proposed nonce start 424001. Transaction bytes and resulting native block hash are **null**, pending the decision below |
| Activation | Proposed v1 at height 0, v17 at height 1; not accepted or installed |
| Issuance | Selected perpetual 9 MEOW/90 s; gated 12/120 fallback unchanged. Twelve decimal atomic precision, fees to miners, no premine, tax, burn, halving, cap or sunset |
| Difficulty/capacity | Unresolved launch difficulty and matched-capacity intended-crypto gate. No fixed-difficulty override proposed for a shared network |
| Discovery | Explicit exclusive native P2P peers; no DNS, IP seed or daemon bootstrap-RPC fallback in the operator recipe |
| RPC | Loopback, authenticated and restricted. No wallet RPC on a seed. Preparation does not attest native runtime authentication |
| Operators/endpoints | Unassigned, represented by nulls in [operators.example.json](operators.example.json) |

The identity-only overlay changes TESTNET's prefixes, default ports, UUID and
genesis nonce. It leaves mainnet/stagenet, genesis transaction, monetary code,
fork tables, crypto and P2P trust code unchanged. It is intentionally insufficient
to launch this proposal. No source tree is modified by the tool.
[The generated patch](evidence/identity-only.patch) binds original config SHA256
`1b372c5a49b913928bc6c85793d0c4befce4ad45f596d6c7fd3b0ada9d8cdc18`
to proposed identity-only config SHA256
`5d94725389db05d076e2fafdba668fbea0f40e75f224e4a1bb7cfb7e131e78b2`.
The complete overlay receipt is [overlay.json](evidence/overlay.json).

## Decisive native premises

All paths below are in the pinned upstream, not the historical fifteen-patch
Monero lineage. The primary source is available at
[the exact upstream revision](https://github.com/seraphis-migration/monero/tree/e151643c5269c83bf24a83b2548e2493876026b2).
The local Git object and matching working-file hashes supplied the inspection
when the browser could not retrieve the pinned page.

| Native path | Observed consequence |
| --- | --- |
| `src/cryptonote_config.h:203-210,302-329,395` | FCMP++ and CARROT activate at v17. Upstream TESTNET has prefixes53/54/63, ports28080/1/2 and its own UUID. FAKECHAIN returns MAINNET's config |
| `src/hardforks/hardforks.cpp` | TESTNET ends at v16. MAINNET has mock v17 and v18 rows. A TESTNET flag alone cannot activate the intended crypto |
| `src/cryptonote_core/cryptonote_core.cpp:655-661` | Regtest picks the **last MAINNET table version**, which is mock v18 at this pin, at height1. The initial consultation's shorthand "accelerated v17" refers to the v17 crypto threshold, not the actual regtest fork version |
| `src/cryptonote_core/blockchain.cpp:1512-1541` | The code documents torsion in test genesis and skips the height-zero check only for FAKECHAIN. Early FCMP activation also checks outputs whose unlock time reaches that activation. Historical public genesis keys cannot be assumed valid for this proposal |
| `src/cryptonote_basic/cryptonote_basic_impl.cpp:84-97` | Current upstream still uses declining/tail emission and a whole-minute target assertion. Setting90 in config alone would fail compilation and would not implement flat9 issuance |
| `src/cryptonote_core/cryptonote_core.cpp:98-112,463-472,510` | Native selector appends its data suffix; FAKECHAIN can delete the old database unless keep-fakechain is set. TESTNET avoids that special reset route |
| `src/p2p/net_node.inl:833-890,1949,2008-2010,2683` | Upstream contains foreign seed lists. Exclusive peers suppress discovery and peerlist connections. Native handshake compares network IDs, but a same-ID/different-genesis adversary still needs a native chain test |
| `src/cryptonote_basic/cryptonote_basic_impl.cpp:131-191`; `src/wallet/wallet_rpc_server.cpp:727` | Native address encoding and parsing use the selected network config; both wallet and daemon must use the rebuilt profile |
| `src/rpc/rpc_args.cpp:226-245`; `src/wallet/wallet_rpc_server.cpp:330-390` | Daemon accepts RPC_LOGIN from its environment. Wallet RPC generates authentication when none is supplied unless disable-rpc-login is set. The generated proposal never disables authentication |

### Concrete owner decision

Core `781fc18f-d668-407b-8114-20094b3b18cc`, with Cryptography consultation
`637e65be-a666-4b41-b211-9fea5eef61da`, must approve or replace this proposal:

1. Construct a deterministic zero-reward genesis using existing upstream native
   transaction construction and serialization, with valid torsion-free outputs
   under the exact FCMP++ activation rules. Record full transaction bytes and
   native genesis hash. Do not reuse the historical keys without validation,
   introduce a new cryptographic construction, or extend FAKECHAIN exceptions.
2. Use v1 genesis then v17 at height1, deliberately selecting the intended
   FCMP++/CARROT rules instead of inheriting mock v18. Prove genesis admission,
   fork-boundary handshake, mature funding outputs and a valid type7 payment.
3. Integrate the settled selected reward/spacing into this lineage with the
   existing penalty, fee and generated-coins protections retained. The historical
   90-second overlay is a reference, not an applicable current source patch.
   Freeze difficulty and capacity only from the required engineering evidence.

This changes an assurance/consensus boundary and is outside an identity-only
configuration choice. No code in this checkpoint implements that decision.
The scoped consultation is on [TJS-2504](<private-tracker>/TJS/issues/TJS-2504#comment-a59d6e31-6116-420c-a369-37ba9cd8e141).
The smallest next action is that source-bound Core/Cryptography ruling on this
same issue, then the assigned writer can extend only its owned overlay paths.
No TJ decision, new account or purchased auditor is required.

## Requirements and independent acceptance map

| Requirement/invariant | Current check/evidence | Remaining acceptance |
| --- | --- | --- |
| Current lineage, original/changed source binding | 13 native paths, all submodule HEADs and Cargo.lock checked; scoped identity patch applies and reverses byte-for-byte | Full clean build and exact executable manifests for completed overlay |
| Dedicated network and address identity | Distinct proposed UUID/prefixes/ports; only TESTNET identity region changes | Real native wallet roundtrip and upstream/mainnet/old-profile address refusals |
| Genesis, activation, policy | Explicit null genesis/floor, proposed v17 activation, fixed settled policy; launch fails closed | Owner ruling, implementation and native consensus acceptance |
| Same/foreign/bootstrap network separation | Same-profile tooling succeeds; foreign selectors/profiles, profile hashes, foreign/default/public/DNS bootstrap endpoints and injected fields fail | Native positive handshake; wrong UUID and same-UUID/wrong-genesis refusal, foreign seed and upstream mainnet/regtest controls |
| Fresh data and restart isolation | Distinct prepared directories, no-overwrite sentinel and symlink controls pass; no LMDB created | Real persisted reopening while counterpart is stopped, then catch-up and recovery |
| Private authenticated restricted RPC | Proposed loopback/restricted settings, no auth-disable path; 0600 files/0700 directories checked | Runtime listeners, unauthenticated/forbidden-method refusals, secret-free logs and exits |
| Operator/seed recipe | [Executable preparation and runbook](operators.md), explicit primary/recovery mapping; unknown operators stay null | Capacity assignment, accepted runnable launcher, withdrawal and recovery witness |
| Finite resource use and cleanup | No native workload; all tests use run-owned scratch and clean successful fixtures | Shared-lock native test under original caps and captured cleanup, including failures |
| Native distribution and wallet payment | Exact remaining integration below | Same profile across daemon/CLI/wallet packages and genuine payment/restore/later spend |
| Independent acceptance/integration | Core/Security native review stages already configured on issue | Complete candidate independently accepted, then lead-only accepted integration receipt |

The eleven tooling tests cover multiple adverse variants and do not represent
eleven native network trials. [tooling-checks.json](evidence/tooling-checks.json)
contains CLI exit/output diagnostics. [source-check.json](evidence/source-check.json)
records the source scope. Early test-harness failure diagnostics are retained.

## Existing evidence retained without rerunning

[research/current-evidence.md](../../research/current-evidence.md) establishes
accepted TJS-1816,1856,1870 work. The four-payment cross-host native witness has
accepted candidate `be33beb62e5e97089dd2e204bce68da2cfd1478b` and integrated
merge `86393a36b11d2eb3d395bb63a96ea405a8059520`. It supplies the recovery method:
stop the counterpart, restart the retained peer, use get_info to attest the saved
height/hash/cumulative difficulty before reconnecting, then confirm subsequent
relay. get_last_block_header waits for synchronization and cannot prove that
independent reopening. Earlier failed attempts remain failures.

[Accepted receipt bindings](evidence/accepted-evidence-bindings.json) hash the
unchanged native result and host receipt read here. This run does not reauthenticate
live tips. Its new profile has **no native proof**. Neither that witness nor
historical Candidate M 9/90 data proves shared-network readiness.

## Exact remaining package and wallet integration

After the protocol decision, build daemon, CLI and wallet RPC from one complete
overlay and pinned dependencies; record original and changed source trees,
toolchains and binary hashes. Existing portable regtest packages cannot become
this network by adding a configuration file. The package owner must carry this
profile digest and the complete overlay/build manifest into the existing
package/launcher flow, select TESTNET consistently and refuse foreign/stale
data and profiles before starting. No package/build/CI helpers were edited here.

Then use two contained native peers on the final profile, a separately isolated
authenticated signer and a restricted observation endpoint. Run genuine cross-node
receive, payment confirmation, seed restore/rescan, and subsequent spend of the
restored received output. Match transaction bytes/hash, main-chain block/hash/height,
destination/amount, recipient output/key-image state and once-only credit across
both nodes. Capture the persistence, late catch-up, bootstrap recovery and adverse
profile controls in the same exact-profile evidence. A restricted wallet RPC
deliberately refuses signing methods; the private signer integration is still
required and cannot be replaced with an unrestricted shared service.

Public checksum custodian/key, final signed release manifests, anonymous native
downloads and public activation stay with the lead/native release workflow.
No signing material was created or read. No own-branch merge or public launch
is part of this checkpoint.
