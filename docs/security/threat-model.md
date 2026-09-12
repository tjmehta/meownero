# Threat model v1 (provisional — Candidate M lineage)

Extends PLAN.md §9.1 for the provisional architecture. Living document; every row names a control that exists, a test that exercises it, or an explicit gap. **Status legend:** ✅ control exists and is tested here · ⚠️ control exists upstream, not yet exercised by us · ❌ gap.

## Assets

Consensus integrity (no inflation, no invalid blocks accepted); user privacy (sender/receiver/amount); availability (block production, relay, node uptime); supply auditability (`supply(h) = h × 0.9`); operator keys (release signing, seed nodes); launch fairness (no insider advantage).

## Threats

| # | Threat | Vector | Control | Status |
|---|---|---|---|---|
| T1 | Inflation via subsidy rule | wrong constant, genesis over-pay, tally overflow | `get_block_reward` constant; height-0 rule on both paths; saturation semantics | ✅ `meow_emission.*`; devnet supply check |
| T2 | Inflation via proof soundness | RingCT/BP+/CLSAG soundness bug (cf. Zcash CVE-2026-54496 class; Monero 2017 key-image class) | inherited audited code; §2.3 gadget-layer controls adapted to `ringct`/`crypto`; key-image subgroup check | ⚠️ review not yet performed by us |
| T3 | Privacy escape hatch | any transparent transaction type; amount leaks | none exists on the lineage; RingCT mandatory from HF 6/13; view tags leak nothing on-chain | ✅ inherent; ❌ no Meownero-specific test yet (add: reject pre-RingCT tx types from height 1) |
| T4 | Consensus split / launch-window peering | hard-fork table shape; handshake `top_version` check at activation boundaries | single-jump table `{v1@0, v16@1}` (no boundary above v6); `meow_hardforks.single_jump_table`; devnet sync of 3 nodes | ✅ 2026-09-06 table test, 18 upstream HF tests, and real-block devnet: identical tips at h2,841; ✅ 2026-09-07 synthetic protocol regression passes with v16-aware test-only output encoding (patch 0007); production validation unchanged |
| T5 | Deep reorg / 51% | young-chain hashrate; no checkpoints by design | confirmation guidance; monitoring; open-questions #6 (bounded finality) | ✅ local depth-3 low-work reorg/restart tests; ❌ final policy undecided (human); ⚠️ high-work/long-alt/P2P partition cases and monitor remain open |
| T6 | Difficulty manipulation | timestamp attacks, negative solvetimes, launch-window whiplash (E5 incident record) | inherited Monero DAA (720/15/60, 2 h FTL, PR #2887); simulation in `docs/spec/difficulty.md`; patch 0006 adds a computed-result floor (currently 1) | ✅ 10/10 checks at each floor 1/150M, including main/alt sampling and rollback boundaries (2026-09-12); ⚠️ native-DAA launch models show timestamp-driven issuance distortion; actual attack replay, lifetime and calibrated launch value remain open |
| T7 | Malformed blocks/txs | oversize, bad decomposition, invalid RCT types, bad unlock times | inherited validation; penalty math | ✅ five actual malformed/version/timestamp/coinbase rejection cases with positive control (2026-09-12); ⚠️ malformed transactions/proofs, size/weight and unlock-time adversarial cases remain open |
| T8 | DoS / resource exhaustion | RPC without limits (CVE-2025-26819 fixed in 0.18.4.x), P2P floods, RandomX verification cost | inherited fixes in 0.18.5.1; `--restricted-rpc`; ban logic | ⚠️ verify version includes fixes; `ban.subnet` test failed in container (attribute) |
| T9 | Eclipse / bootstrap | no seeds shipped: node trusts whatever peers it is given | explicit seed policy (PLAN §9.5, human); anchor connections; Dandelion++ | ❌ seed policy undecided; ⚠️ docs must warn |
| T10 | Network-layer deanonymization | IP linkage of tx origin | Dandelion++ inherited; Tor/I2P relay inherited | ⚠️ not exercised on devnet |
| T11 | Remote-node wallet leaks | malicious remote node (2025 advisory, unpatched upstream) | operator guidance: run own node | ❌ document in operator docs |
| T12 | Supply-chain compromise | dependency drift, container image drift, unpinned upstream | pinned upstream tag + submodule hashes; Ubuntu 24.04 Docker recipe | ✅ fresh six-patch build verified 2026-09-06; 2026-09-07 base digest pinned, immutable builder/package records and fresh cache-disabled comparison implemented; ✅ both thirteen-patch clean builds/tests pass and all three binary hashes match (2026-09-12) (same-host fixed-image source reproducibility; provenance in `chain/README.md`); ❌ apt versions/snapshots and independent toolchain reconstruction remain open |
| T13 | Key compromise | release signing, donation multisig | PLAN §9.5 | ❌ human gate (who holds keys) |
| T14 | Launch unfairness | insta-mine at difficulty 1, secret pre-testing | launch floor; parameters public T−4 weeks; fairness report | ❌ floor undecided; procedure documented in PLAN §8.3 |
| T15 | Upstream shock | critical upstream vuln post-fork; FCMP++ rewrite | 72 h security-merge SLA; rebase-clean patch series | ⚠️ patch series format (M1) |
| T16 | Wallet recovery failure | seed restore, rescan | wallet2 regeneration/rescan; sparse-fork version lookup fixed by patch 0014 | ✅ isolated wallet-RPC seed restore matches address, 130 coinbase entries, exact balances and reopen; ⚠️ private-payment/outgoing metadata and interactive CLI recovery remain untested |
| T17 | Brand-claim liability | "no trace", "deflationary" | PLAN §8.1 forbidden claims; §9.2 counsel | ❌ counsel (human) |

### Inherited opt-in authority follow-up (2026-09-07)

Patch 0010 removes the remaining inherited update/download endpoints at the shared helper, disables DNS-blocklist lookup even when explicitly requested, and disables CLI donations without a replacement recipient. Actual update RPC modes fail closed; local host bans still work; the blocklist option warns; offline donation checks pass on all three networks. Shared update unit tests pass; the wallet-manager API caller is reviewed but not separately runtime-tested. This closes these specific inherited authority routes, not release signing/key custody or general DNS privacy review. See the regenerated ten-patch `code-map.md` and the dated verification record.

## Trust boundaries

- **Consensus code** (Monero v0.18.5.1 + delta): trusted after review; every delta line enumerated in `docs/security/code-map.md`.
- **Build environment**: Ubuntu 24.04 container with distro packages — trusted at the distro level; same-host fixed-image source reproducibility verified for patches 0001–0013; clean fifteen-patch reproduction and independent toolchain reconstruction pending.
- **Peers**: untrusted; no seeds shipped.
- **RPC clients**: untrusted unless `--restricted-rpc` off is deliberate.

## Explicit non-goals for v1

Bitcoin interop (E4), merge-mining (E6), hardware wallets, light wallets, mobile.

Latest evidence and limits: [foundation verification](../../research/verification-2026-09-12-m1.md), [initial M2 adversarial/native-DAA report](../../research/verification-2026-09-12-m2.md). These results do not close the independent audit or human launch gates.
