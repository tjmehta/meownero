# Selected monetary direction and local evidence handoff — September 12, 2026

Later local engineering: [restarted checkpoint](handoff-2026-09-12-restarted.md).
The policy decision below remains current; subsequent test/build state is there.

## Decision and authorization

TJ's latest explicit delegated choice supersedes the preceding recommendation:
**fixed perpetual issuance, zero premine, no halvings/cap/sunset, no developer
or transfer tax, no artificial burns; fees to miners.** Target **9 MEOW/~90 s**,
conditional on validation, relay, stale-block and reorg testing including the
intended cryptography. If 90 s fails choose **12 MEOW/120 s**. Both target
**3,153,600 MEOW per 365 days before penalties**. High early dilution is accepted
for simple fair launch and ongoing open distribution. Do not replace this with
premine or front-loaded emission merely to lower later percentage growth.

The 0.9/120 and 0.675/90 families remain explicitly **historical controls**,
each 236,520 MEOW/year. Preserve their code, evidence, completed seed recovery
and frozen clean reproduction. The fifteen-patch source still represents that
control. Selected policy does not imply selected binaries already exist.

This authorizes reversible local parameter engineering and reviewable commits.
It does not authorize launch, publication, push, spending, real-user experiments
or outside outreach. No identities, ticker, checkpoint trust, second signer,
audit budget, architecture or cryptography readiness gates are silently chosen.

## Evidence versus values

[Primary receipts and limitations](swarm-facts-and-choices-2026-09-12.md) retain
Coincards dollar-volume shares, CoinGate distinct order/asset-share denominators,
and Monero's tail-emission rationale. Merchant usage establishes neither causal
zero adoption penalty nor guaranteed security. Mature tail is not flat-from-zero
launch evidence; USDC backing/redemption differs from miner issuance.

At target spacing before penalties, `S(t)=3,153,600*t` from zero; next-year
growth is `1/t`. Year 2 adds 100%, year 11 adds 10%, year 51 adds 2%. Increasing
coin units changes neither percentages nor guarantees real miner income.
Supply growth is not a mechanically equal price decline. Matched flat issuance
and a 135/150-year cutoff have equal pre-cutoff flow, but expectations could
change present demand. TJ chose no cutoff as a values decision. No direct causal
evidence of zero adoption penalty was identified or implied by this choice.

## Distribution to the existing swarm

Both the evidence update and the superseding selected-policy update were sent
through `herdr agent prompt` to the five existing sessions. All five explicitly
acknowledged the **selected** direction, not only submission receipt:

| Worker / pane | Acknowledgment and consequence |
|---|---|
| network / wB:p1 | 9/90 selected, 12/120 fallback; match issuance and capacity/time including dynamic effects. Report/readiness checker retain historical parameters. |
| privacy / wC:p1 | Prior branding-only acknowledgment superseded; observer-specific limits preserved; no conflicting monetary claim. |
| mining / wD:p1 | Historical compatibility matrix does not test selected parameters; incentives depend on purchasing power/costs. |
| rust / wE:p1 | Earlier recommendation-only status superseded; 120-second parity report remains historical evidence. |
| demo / wF:p1 | Selected perpetual/no-cap and early dilution disclosure; old payment accounting preserved; no adoption/security guarantee. |

[Captured acknowledgment excerpts](evidence/swarm-2026-09-12/issuance/worker-acknowledgments.json).
Workers performed read-only review and did not rerun or reopen their closed
tracks. Coordinator updated shared decision/spec/handoff and clarifying labels;
all worker code and the network worktree used by the queued build stay intact.

## Verified reversible local checkpoint

[Runner and two mutually exclusive overlays](../spikes/selected-issuance/README.md)
apply only to disposable copies of hash-verified current15 source. They set the
selected reward/time constants and remove the obsolete whole-minute assertion
from the flat reward function. `chain/patches` and the frozen inputs are untouched.

[Compiled results](evidence/swarm-2026-09-12/issuance/summary.json): **3,024 cases
per profile**, 6,048 total, pass against an independent Python integer oracle.
Actual reward/weight functions, integer helpers and both main/alt tally
expressions are source-pinned. Coverage includes versions 1–16, weight floors,
penalty fractions, excessive-weight refusal, saturation boundaries and continued
reward at maximum tally. Source drift refusal and byte-exact reverse application
pass. Immutable Ubuntu/GCC 13 builder, one CPU, 512 MiB/no-swap container, no
network; source mounted read-only and shared build lock respected.

At retained 12 dp the first unpenalized saturating reward block becomes
2,049,639 (9/90) or 1,537,229 (12/120), approximately **5.85 years**. This is
an internal u64 tally limit, not a cap. The historical roughly 78-year figure
does not describe selected issuance. The reward primitive continues correctly;
full aggregate amount/RPC/wallet/fee/reporting consumers remain to be verified.

[Preservation and final checks](evidence/swarm-2026-09-12/issuance/preservation-checks.json):
frozen manifest and all listed input hashes pass; all five worker worktrees
remain clean; protected production/demo/seed paths are unchanged. Shell/Python
syntax and local Markdown links pass.

## Open gates and preserved build

- Full selected daemon/wallet binaries and profile-specific unit fixtures have
  not been built or reproduced. Genesis and seed-recovery source/evidence are
  preserved, not newly verified under the selected family.
- Selected fee, coinbase, aggregate-supply/reporting, wallet/RPC, difficulty and
  timeout integration remains open, particularly around earlier tally saturation.
- No capacity rule was chosen by these overlays. Match `capacity_90 = 3/4 *
  capacity_120` in controlled network trials and measure dynamic medians/limits;
  equal offered budgets alone do not prove enforced capacity equality.
- Actual intended FCMP blocks, loaded validation/propagation, stale/reorg and
  difficulty recovery remain required. Extracted primitives or simulated crypto
  costs cannot stand in for full integration. Fallback is conditional, not an
  automatic gate pass. P2Pool selected-family compatibility is untested.
- The existing clean15 waiter at `/tmp/meow-swarm-network-20260912-run` remains
  alive, awaiting the 5 GiB host-memory preflight. Its log continued advancing;
  available RAM ranged around 1.0–1.7 GiB during this checkpoint. No duplicate
  build, resource-policy bypass, service change or frozen-input edit occurred.
  See the [prior handoff](handoff-2026-09-12-swarm.md#preserved-clean-fifteen-reproduction-waiter)
  for exact input identities and collection commands.

The next work is bounded selected-profile integration and intended-workload
readiness, preserving the queued historical reproduction. This checkpoint does
not promote either profile past existing release or independent-review gates.
