# Threat model v1 (provisional — Candidate M lineage)

Extends PLAN.md §9.1 for the provisional architecture. Living document; every row names a control that exists, a test that exercises it, or an explicit gap. **Status legend:** ✅ control exists and is tested here · ⚠️ control exists upstream, not yet exercised by us · ❌ gap.

## Assets

Consensus integrity (no inflation, no invalid blocks accepted); user privacy (sender/receiver/amount); availability (block production, relay, node uptime); supply auditability (`supply(h) = h × 0.9`); operator keys (release signing, seed nodes); launch fairness (no insider advantage).

## Threats

| # | Threat | Vector | Control | Status |
|---|---|---|---|---|
| T1 | Inflation via subsidy rule | wrong constant, genesis over-pay, tally overflow | `get_block_reward` constant; height-0 rule on both paths; saturation semantics | ✅ `meow_emission.*`; devnet supply check |
| T2 | Inflation via proof soundness | RingCT/BP+/CLSAG soundness bug (cf. Zcash CVE-2026-54496 class; Monero 2017 key-image class) | inherited audited code; §2.3 gadget-layer controls adapted to `ringct`/`crypto`; key-image subgroup check | ⚠️ review not yet performed by us |
| T3 | Privacy escape hatch | any transparent transaction type; amount leaks | none exists on the lineage; RingCT mandatory from HF 6/13; view tags leak nothing on-chain | ✅ inherent; ❌ no Meownero-specific test yet (add: reject pre-RingCT tx types after height 16) |
| T4 | Consensus split / launch-window peering | hard-fork table shape; handshake `top_version` check at activation boundaries | single-jump table `{v1@0, v16@1}` (no boundary above v6); `meow_hardforks.single_jump_table`; devnet sync of 3 nodes | ✅ table pinned by test; ⚠️ devnet re-run with the new table pending |
| T5 | Deep reorg / 51% | young-chain hashrate; no checkpoints by design | confirmation guidance; monitoring; open-questions #6 (bounded finality) | ❌ policy undecided (human); ⚠️ no chain monitor yet |
| T6 | Difficulty manipulation | timestamp attacks, negative solvetimes, launch-window whiplash (E5 incident record) | inherited Monero DAA (720/15/60, 2 h FTL, PR #2887); launch floor undecided | ❌ launch floor + whiplash simulation (M1/M2) |
| T7 | Malformed blocks/txs | oversize, bad decomposition, invalid RCT types, bad unlock times | inherited validation; penalty math | ⚠️ inherited tests; add Meownero adversarial vectors (M2) |
| T8 | DoS / resource exhaustion | RPC without limits (CVE-2025-26819 fixed in 0.18.4.x), P2P floods, RandomX verification cost | inherited fixes in 0.18.5.1; `--restricted-rpc`; ban logic | ⚠️ verify version includes fixes; `ban.subnet` test failed in container (attribute) |
| T9 | Eclipse / bootstrap | no seeds shipped: node trusts whatever peers it is given | explicit seed policy (PLAN §9.5, human); anchor connections; Dandelion++ | ❌ seed policy undecided; ⚠️ docs must warn |
| T10 | Network-layer deanonymization | IP linkage of tx origin | Dandelion++ inherited; Tor/I2P relay inherited | ⚠️ not exercised on devnet |
| T11 | Remote-node wallet leaks | malicious remote node (2025 advisory, unpatched upstream) | operator guidance: run own node | ❌ document in operator docs |
| T12 | Supply-chain compromise | dependency drift, container image drift, unpinned upstream | pinned tag + submodule hashes; Docker builder from pinned Ubuntu; reproducible build (M1) | ⚠️ pins recorded; ❌ reproducibility not yet verified by two builds |
| T13 | Key compromise | release signing, donation multisig | PLAN §9.5 | ❌ human gate (who holds keys) |
| T14 | Launch unfairness | insta-mine at difficulty 1, secret pre-testing | launch floor; parameters public T−4 weeks; fairness report | ❌ floor undecided; procedure documented in PLAN §8.3 |
| T15 | Upstream shock | critical upstream vuln post-fork; FCMP++ rewrite | 72 h security-merge SLA; rebase-clean patch series | ⚠️ patch series format (M1) |
| T16 | Wallet recovery failure | seed restore, rescan | inherited `monero-wallet-cli` restore | ⚠️ exercise on devnet (M2) |
| T17 | Brand-claim liability | "no trace", "deflationary" | PLAN §8.1 forbidden claims; §9.2 counsel | ❌ counsel (human) |

## Trust boundaries

- **Consensus code** (Monero v0.18.5.1 + delta): trusted after review; every delta line enumerated in `docs/security/code-map.md`.
- **Build environment**: Ubuntu 24.04 container with distro packages — trusted at the distro level; reproducibility pending.
- **Peers**: untrusted; no seeds shipped.
- **RPC clients**: untrusted unless `--restricted-rpc` off is deliberate.

## Explicit non-goals for v1

Bitcoin interop (E4), merge-mining (E6), hardware wallets, light wallets, mobile.
