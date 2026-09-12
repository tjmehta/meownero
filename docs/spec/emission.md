# Emission specification v2 — selected policy, engineering-gated profiles

**Selected by TJ, 2026-09-12:** fixed perpetual issuance, zero premine, no
halvings, cap or sunset, no developer or transfer tax, no artificial burns;
fees to miners. High early dilution is accepted for simple fair launch and
ongoing open distribution. [Decision and evidence](../../research/decision-2026-09-12-issuance.md).
PLAN.md §2 and §8 remain governing gates; this is not launch approval.

## Parameters and implementation status

| Profile | MEOW/block | Target seconds | Atomic subsidy (12 dp) | MEOW/365 days before penalties | Status |
|---|---:|---:|---:|---:|---|
| Selected target | 9 | 90 | 9,000,000,000,000 | 3,153,600 | Reversible source overlay; validation/relay/stale/reorg gates including intended crypto open |
| Selected fallback | 12 | 120 | 12,000,000,000,000 | 3,153,600 | Use if 90 s fails; same integration/review gates |
| Historical implementation control | 0.9 | 120 | 900,000,000,000 | 236,520 | Preserved fifteen-patch source and frozen reproduction |
| Historical benchmark control | 0.675 | 90 | 675,000,000,000 | 236,520 | Preserve original experiments and readiness evidence |

Genesis subsidy stays zero; the coinbase contains one zero-amount output.
Atomic precision remains inherited `COIN = 10^12`; no precision change is
implied. Subsidies are independent of cumulative issuance and do not halve.
Inherited block-weight penalties can reduce subsidy; actual block arrivals
change calendar issuance. Fees accrue to miners in addition to subsidy.
No premine or front-loaded substitute is permitted merely to lower later
percentage growth. No cap at 135 or 150 years is selected.

## Verification and integration boundary

[Isolated overlays and runner](../../spikes/selected-issuance/README.md) change
only the reward constant, target V2 spacing and an obsolete whole-minute
assertion in the flat reward function. No overlay is in `chain/patches` or used
by the queued historical reproduction. The existing genesis construction and
validation, penalties, fees and precision remain unchanged source inputs.

For **each selected profile**, 3,024 compiled extracted-source cases verify:

- Full subsidy across versions 1–16 and cumulative-tally probes through `UINT64_MAX`.
- Weight-floor behavior, exact integer penalties, zero reward at twice the
  median, rejection above twice the median.
- Both main-chain and alternate-chain tally expressions at either side of
  saturation; neither wraps and the reward continues at the saturated tally.

The oracle uses Python arbitrary-precision arithmetic; the compiled path uses
actual pinned `mul128`/`div128_64` code. Source drift is refused; reverse-applying
each overlay restores its copied inputs byte for byte. These are extracted
function tests, not a fresh full unit-suite, node, genesis or wallet run.
Historical reward tests and successful seed-recovery evidence remain intact.

Full selected binaries, updated profile-specific unit fixtures, fees/coinbase
aggregation, wallet/RPC amounts, difficulty/timeouts and loaded adversarial
network tests remain required. Match **both** issuance and capacity per second:
`capacity_90 = 3/4 * capacity_120`, with comparable proof mix and topology.
A workload budget does not enforce dynamic consensus capacity; the overlays
retain inherited limits and alone are not a matched-capacity benchmark.
Intended FCMP workloads must run faithfully before claiming those gates pass.

## Supply arithmetic and tally horizon

Before penalties, `S(t) = 3,153,600*t` at target spacing, with zero initial
supply. Next-year supply growth is `1/t`, independent of coin denomination.

| Year | Issued that year (MEOW) | Cumulative (MEOW) | Growth during year |
|---|---:|---:|---:|
| 1 | 3,153,600 | 3,153,600 | Undefined from zero |
| 2 | 3,153,600 | 6,307,200 | 100% |
| 3 | 3,153,600 | 9,460,800 | 50% |
| 11 | 3,153,600 | 34,689,600 | 10% |
| 51 | 3,153,600 | 160,833,600 | 2% |

At retained 12 dp the u64 internal generated-coins tally first saturates at
unpenalized reward block **2,049,639** for 9/90, or **1,537,229** for 12/120:
about **5.85 years** in either case. This is an internal tally limit, not a
supply cap. The historical 0.9/120 control's roughly 78-year horizon must not
be quoted for the selected family. Full integration must review every aggregate
amount, supply-reporting and fee consumer across this much earlier boundary;
a successful reward primitive does not establish whole-system readiness.
The mathematical cumulative totals above are not representable in that u64
atomic-unit tally after saturation. Lower precision has not been selected.

## Evidence and presentation constraints

No direct causal evidence establishes zero adoption penalty for flat issuance
from genesis. Mature Monero tail after declining issuance is a different
history. Ongoing nominal miner rewards do not guarantee purchasing power,
hashpower or security; supply growth is not a mechanically equal price decline.
No “fixed supply,” “initial deflation,” “early low inflation,” adoption-neutral
or guaranteed-security claims. [Primary receipts and denominator limits](../../research/swarm-facts-and-choices-2026-09-12.md).

Wallet presentation may simplify display independently of consensus precision,
but must never silently round payment inputs or show a nonzero balance as zero.
Ticker, identities, checkpoint trust, second signer and audit budget remain
outside this monetary decision. All artifacts stay local.
