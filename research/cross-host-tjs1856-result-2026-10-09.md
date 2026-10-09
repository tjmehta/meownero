# TJS-1856 finite native cross-host result

**Writer result: PASS native payment, sync and persisted recovery witness. Independent acceptance: NOT_RUN.** Four distinct FCMP++ type7/CARROT payments were confirmed once on both build-mac and Railway in native attempt03. The remote daemon reopened the exact height73 tip while build-mac was paused, then reconnected and confirmed payment4 at height74. Provider and owned runtime/image cleanup passed. This is a valueless regtest witness; production security, cryptographic soundness and public-trial readiness remain unestablished.

Accepted base remains `c6620342328f313e1e9bdfb79570d5245e669090`. Actual native execution candidate is `f003ad05cdf6cef31151f7d099ef9946b6fee15d`. The subsequent preparation-checker commit `f15d1ce` changes only the offline checker. Live driver/supervisor/host-wrapper bytes match the execution pins in `native-attempt03/host-receipt.json` and the uploaded-file manifest. All commits remain on the assigned isolated branch; nothing was pushed, merged or published to a public registry.

| Requirement | Result | Raw evidence / limits |
|---|---|---|
| Native host identity and process hashes | PASS | build-mac ARM daemon/wallets, native Railway x86_64 daemon; live executable hashes and command lines recorded |
| Actual TCP handshake and matching genesis | PASS | `native-attempt03/public/result.json`: genesis, runtime_network, transport; RPC connection observations on both peers |
| Four distinct intended-crypto payments | PASS | Native decoded type7 signatures and CARROT outputs; full serialized transaction equality, fees and disjoint input key images |
| Once-only pool, block and recipient binding | PASS | 279 raw RPC rows; construction destination/amount, both pools, identical main-chain block and one recipient output per transaction |
| Persisted remote restart before rejoining | PASS | build-mac SIGSTOP; new remote PID/start_ticks; `reopened_info` matches saved height73 hash/difficulty before build-mac SIGCONT |
| Healthy payment after recovery | PASS | Fourth payment, final height74 hash, matching healthy connections and empty pools |
| Recipient balance | PASS | Exactly4 outputs, 4,100,000,000,000 atomic units (4.10); accepted local gates unchanged |
| Finite workload and timing | PASS | 74 blocks in successful attempt; 23.606s after funding; native host 49.064s; 220 total generated blocks across all3 native attempts, within amended270 cap |
| Resources, exits, OOM | PASS | Remote peak391,778,304B below measured999,997,440B cap; local peak534,970,368B; all daemon/wallet/generation exits0; OOM/oom_kill0 |
| Remote non-mining design and authenticated controls | PASS | Mining/wallets only on build-mac; public RPC denied unauthenticated; authenticated mining/submission rejected; allowlisted read RPC positive checks |
| Service/deployment/proxy/domain/volume cleanup | PASS | Runtime secret deleted; deployment stopped; TCP proxy/domain removed; exact service deleted; final authenticated project status has zero services/volumes |
| Owned process/container/image cleanup | PASS | All task containers absent on DEV/build-mac; three exact owned images removed; shared Colima preserved; private wallet attempts remain0700 on build-mac |
| Remaining free credit immediately before execution | UNCONFIRMED | Parent handoff observed $5.00 at05:00:18Z; project credential lacks billing usage access. No new account/billing/payment/upgrade mutation performed |
| Project credential revocation | PARENT_ACTION | Parent owns secured project token and revokes it after this cleanup handoff |
| Existing independent reviewer acceptance | NOT_RUN | Reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` must independently accept exact candidate/raw artifacts. Initial run ownership has expired; document write returned409 |
| Production soundness / public-trial readiness | NOT_RUN | Neither is established or claimed by this finite witness |

The payments used6 distinct input key images. The report's tables are writer verification; the separate existing reviewer supplies independent acceptance.

| Payment | Amount | Transaction hash | Height | Construction-to-confirmation seconds |
|---|---:|---|---:|---:|
| 1 | 1.01 | `2728b153afe5263550f399f6f252be27037e7e1871a37add60608894286403b5` | 71 | 6.528 |
| 2 | 1.02 | `6495119c25bb694630392facf1e44c91b2ccdba870356a64f9af4b20a2efca0f` | 72 | 4.621 |
| 3 | 1.03 | `50bf76722aba2eb5a2687650f39792146124f7f8918fdec74b567f14fd2252aa` | 73 | 4.398 |
| 4 | 1.04 | `83114c09f48bf23d07a2f292cfed579ada50bea2aaa2e91f67c28a894ba55479` | 74 | 3.468 |

The saved/reopened height73 block is `7bfea75c863080934bf573be257415f39762e80b001e4e2e9dc0ead0a7725b34` (wide cumulative difficulty0x4a). Final height74 block is `36f1504463858d427b45baa1218f9f3310c171f7102ce7dfc96c7ae8566127be` (0x4b). Full block hashes, previous hashes, serialized transactions, fees and destination/amount/output bindings are in the raw result and referenced RPC rows. The independent writer readback is `writer-raw-readback.json`; no wallet seed, key, wallet database or chain database was copied from private attempts.

**Pins and provenance.** Upstream `e151643c5269c83bf24a83b2548e2493876026b2`, full submodules/monero-oxide/crypto-bigint pins in `vanguard/source-lock.json` and host receipt; Cargo.lock SHA256 `6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239`. Native ARM daemon SHA256 `b4becc6efbdc922f0fac93a0730de6f9397c1637a60b95630140e9ace677b920`, wallet RPC `9ab761894ace8a84e3563619ba978e4d8a2c86ee07d7d38e5a5c8c364c4c450b`. Native Railway x86 daemon SHA256 `a1c98d4fcf69402e4850467984bb39a5c76bb244fe23ed7766110f7f20c386b0` (29,872,616bytes). Actual successful deployed image is `sha256:94e46fd391453a5c083bb120efe73927d29216b101d7594bf43e49f6895bd80e`, deployment `1eeab1b4-7ab3-41ec-a870-a8a21706ea00`. Historical local package-image identities are preparation observations, not substitutes for this provider digest.

Railway project `f46a08ef-dcba-431b-8fb0-a3b2c0dd721e`, regtest environment `4e5d9d89-594e-464c-a9de-b854ec33e30a`, handed-off service `884ba31d-a288-4f69-9dbb-9e1332501d87` is now deleted. Parent comments `06276ddb-ceda-42b3-96f4-811e162ea928` and `8f4986a9-ab3b-421c-9582-9b3465a4ec1c` were read; adoption recorded in `1bf4172e-0570-45b1-89f3-4ffda666be1f`. Supported task-only CLI5.64.1 SHA256 `47869b61196e463670bbe870f2c8c5053a09ddbe5dffc0833396c2355857d747` used the protected project-token file through environment only. The conflicting account0.5GB/service1GB UI observations remain recorded; acceptance used the actual cgroup memory.max999,997,440B. Remote CPU usage counters and local2CPU/4GiB Docker caps are recorded; the remote2CPU limit is parent UI provenance, not a separately read cpu.max observation.

The remote exposes native P2P19080 through the generated TCP proxy and authenticated HTTPS control8080. Daemon RPC stays loopback. Wallets and generateblocks stayed on build-mac. Both peers disabled public discovery and used only the selected exclusive destination; provider restart policy NEVER was verified before funding. Runtime supervisor lifetime1800s and operator cleanup deadline were frozen before startup. Provider runtime disk measurement at final shutdown was422,595B (logical file sizes); local native disk files remain private.

**Preserved failures and corrections.** Native attempt01 confirmed3 payments, then failed because the supervisor treated a BUSY/empty header as reopened state; all exits0/OOM0. Native attempt02 confirmed3 payments, then failed with restart HTTP503. Pinned source inspection established `core_rpc_server::on_get_last_block_header` calls CHECK_CORE_READY, which waits for P2P synchronization. Pausing the only counterpart therefore prevents this API's readiness. Revision5 used `on_get_info`, which reads `m_core.get_blockchain_top` without that gate; stored height/top_block_hash/wide cumulative difficulty were checked before resuming the counterpart. This corrects the proof method without changing daemon consensus code. The explicitly recorded protocol amendment allowed one final attempt03 and increased the self-imposed total cap from180 to270 blocks before execution; actual total was220. There was no further native retry.

| Preserved attempt | Outcome |
|---|---|
| x86 initial build | FAIL timeout124 after3520.96s; emulated peak2,888,134,656B/OOM0; same cache resumed, no duplicate build |
| x86 daemon-only resume | PASS225.885s; emulated peak2,117,910,528B/OOM0; all emulated build containers removed |
| Provider01 | FAIL native P2P/control PORT collision; no funding |
| Provider02 | FAIL coordinator treated INITIALIZING/deploymentStopped as terminal; no funding |
| Provider03 | FAIL confirmed bind collision, bounded native error tail preserved; no funding |
| Provider04 | FAIL strict anonymous denial status mismatch; healthy native peer, no funding |
| Provider05 | FAIL read imageDigest before provider metadata populated; no funding |
| Provider06 / native01 | FAIL recovery check after3 confirmed payments; all raw evidence preserved in `native/` |
| Provider07 | FAIL exact403 assertion when forbidden request returned404; no native trial |
| Provider08 | FAIL authenticated read returned edge404 Application not found; no native trial |
| Provider09 / native02 | FAIL P2P-dependent reopened-header gate after3 confirmed payments |
| Provider10 / native03 | PASS full four-payment/sync/persisted-recovery native witness |

All provider attempts have cleanup receipts. The coordinator logs denied statuses/bodies and rechecks authorized state/get_info before funding. Read-only requests retry edge HTTP404/502/503 for at most30s, recording each response; restart and stop commands are issued once. Earlier preparation smokes asserted header equality without a readiness/nonempty requirement and do not prove a loaded genesis header; their raw results remain historical. The final offline ARM preparation check uses get_info statusOK/nonempty stored hash and matching height, verifies auth/mining refusals and restart identity, and passed with no network at PORT19080. Actual WAN genesis acceptance comes from the native handshake evidence.

**Cleanup and reproducibility.** `final-cleanup/final-empty-project.stdout`, `final-cleanup/final-cleanup.json`, and `final-cleanup/dev-owned-containers.json` prove resource removal. Private disposable wallets/daemon databases remain under task-owned build-mac trial directories with mode0700; no live task process remains. Exact image tags tjs1856-builder:amd64, tjs1856-peer:amd64 and tjs1856-peer02:amd64 were removed without global pruning. Shared ARM build/cache and Colima are preserved. An accidental initial global Rust1.93 install during preparation was copied to task staging and uninstalled; no remaining global installation is claimed.

Review offline from the exact branch/worktree, the public archive or attached patch. Hashes cover each public evidence file in `SHA256SUMS.json`; source hashes are also bound by each native host receipt and upload manifest. `reproduction/` saves the exact bounded coordinator, native input pins and Dockerfile; credentials are deliberately excluded. The native host wrapper accepts its runtime secret on protected SSH stdin and launches the pinned ARM image with source read-only. A fresh private service, new runtime secret and fresh task-owned attempt directory are necessary for any authorized future reproduction; the cleaned-up endpoints are not live.

Commands for review: `git diff --check c6620342328f313e1e9bdfb79570d5245e669090 HEAD`; read `native-attempt03/public/result.json`, `rpc.jsonl`, `control.jsonl`, host receipt, final counters and provider deployment metadata; verify `SHA256SUMS.json`; compare the native executable/file hashes with the receipts and source lock. Do not run an old deployment script against the now-deleted service or reopen private wallets during review. Independent review should challenge the stored-tip proof, raw transaction/block/recipient binding, attempt history, cleanup, secret exclusions and limits; it must not replace missing production gates with this result.

**Delivery state.** Paperclip document update returned409 Issue run ownership conflict: checkoutRunId/executionRunId are null while actorRunId is the ended initial run. No blind document-write retry or duplicate checkout was attempted. The exact review-stage payload and evidence will be handed to the studio lead for a sanctioned ownership restoration or stage activation if the same guard rejects final disposition. The writer cannot claim the reviewer has started or accepted without a successful persisted path.

Changed: task-only authenticated supervisor, bounded native cross-host driver/host wrapper, private package tooling, preparation checker, protocol and raw evidence. Verified: native four-payment/sync/persisted recovery; once-only bindings; resource limits and cleanup. Unconfirmed/next: independent acceptance, parent-owned credential revocation and current remaining free credit. Needs TJ: none. Parent integrates only the exact independently accepted candidate and delivers the result to the originally authorized group.
