# Factual corrections and retained choices — 2026-09-12

This is the coordinator's source check of the latest research, separate from
policy adoption. TJ subsequently selected the monetary direction in the
[decision record](decision-2026-09-12-issuance.md); evidence limitations and
readiness gates remain unchanged.

## Source-backed facts

- [Monero PR 11283](https://github.com/monero-project/monero/pull/11283) remained
  open and unmerged in the GitHub API check on September 12. Its proposed change
  concerns keeping peers that relay invalid blocks with valid PoW, anticipating
  propagation before expensive validation finishes. It motivates measuring FCMP
  validation and propagation; it is not itself FCMP integration or an adopted
  Meownero relay policy. Checked head: `a58e7b0227d9a29fb3a20068f019b1b6a561b17e`.
- The FCMP [tower-cycle/hash-growth PR 10361](https://github.com/monero-project/monero/pull/10361)
  and [curve-tree builder PR 10724](https://github.com/monero-project/monero/pull/10724)
  were also open and unmerged. Checked heads were respectively
  `3d3ed652469b0ce1852f47e8ded55b97bae60cc2` and
  `6fdb42b56b7fd0d78d1e6fa659eb73bb249d53b9`. These statuses are dated observations,
  not a complete integrated cryptography readiness assessment.
- The [Cuprate 0.1.0-preview release](https://github.com/Cuprate/cuprate/releases/tag/cuprated-0.1.0-preview)
  describes a beta preview with initial wallet support and explicitly discloses
  that the downloadable CI binaries are not reproducible. The API records its
  publication as August 1, 2026; the August 4 social announcement is a different
  event. Source-built module parity tests do not certify a full Meownero node.
- The [Monero optimization results](https://www.getmonero.org/2025/08/27/fcmp%2B%2B-contest-final.html)
  report improvements in divisor construction and a separate curve library.
  The reported over-95% divisor improvement, 22% weighted CPU speedup and 39%
  weighted WASM-cycle improvement have different scopes. None is a measured
  whole-chain speedup. The rules explicitly call for bounded code/API changes
  and concrete architectures/toolchains for constant-time requirements.
- The supplied X counts are September 12 attention snapshots with different
  exposure durations. They are not independently audited people, conversion,
  or evidence that economics, privacy claims or a brand direction cause adoption.
  No social analytics or address/IP tracking was introduced here.

## Arithmetic and explicitly selected policy

These are exact unpenalized target-spacing calculations for 365-day years,
excluding zero-reward genesis. Actual block arrival times and weight penalties
can change calendar issuance.

| Pair | MEOW/second | MEOW/year | 135 years | 150 years | Status |
|---|---:|---:|---:|---:|---|
| 120 s / 0.9 | 0.0075 | 236,520 | 31,930,200 | 35,478,000 | Historical implementation control |
| 90 s / 0.675 | 0.0075 | 236,520 | 31,930,200 | 35,478,000 | Historical benchmark control |
| 90 s / 9 | 0.1 | 3,153,600 | 425,736,000 | 473,040,000 | Selected target, engineering-gated |
| 120 s / 12 | 0.1 | 3,153,600 | 425,736,000 | 473,040,000 | Selected fallback if 90 s fails |

The selected family is 13⅓ times the historical control issuance rate at the same
unit definition. Compare 9/90 with 12/120, separately from the old matched pair. The 135/150-year columns
are cumulative arithmetic, not implemented caps. A cap with the same subsidy
until cutoff has the same near-term issuance and then removes subsidy; future expectations can affect present demand even before cutoff. TJ selected
perpetual issuance with no cutoff; the columns are not caps.

Holding block capacity constant while reducing spacing from 120 to 90 seconds
raises nominal capacity per second by one third. A controlled comparison needs
`capacity_90 = 3/4 × capacity_120`, alongside matched issuance, proof/workload mix
and topology. Inherited dynamic block-weight medians and minimums mean an offered
load budget is not automatically an enforced consensus limit. Per-block overhead
and confirmation time still differ; equal confirmation counts do not establish
equal security.

## Choices retained for people

Selected monetary policy is recorded separately from source findings. Historical
120 s / 0.9 build inputs, floor 1, provisional Monero lineage and cryptography
readiness gates remain preserved.
No architecture sign-off, founder-identity, ticker, checkpoint-trust, second-signer
or audit-budget decision is inferred from this work. Pool decentralization cannot
supply missing hashpower, and a fresh genesis cannot inherit Monero's historical
anonymity set. Atomic swaps remain after core quality. All engineering and review
artifacts remain local; no publication, prize commitment or outreach follows from
this note.

## Adoption receipts and their limits (TJ update)

- [Coincards June 2024](https://x.com/CoinCards/status/1809702144288882870): XMR 34.4%, BTC on-chain 25.96%, Lightning 2.08%, DOGE 2.09% of **dollar volume**, not people or transaction counts. Retained as TJ's verified primary receipt; this coordinator's X fetch returned 403. Actual use alongside capped alternatives does not establish zero adoption penalty from uncapped issuance.
- [CoinGate H1 2026](https://coingate.com/blog/post/crypto-payments-data-report-h1-2026): 782,403 completed orders total; USDC 22.1% and BTC 21.0% of on-chain asset payments. Page fetched by the coordinator. These denominators differ; do not multiply total orders by asset shares blindly. Dollar backing/redemption is not miner issuance.
- [Monero tail rationale](https://www.getmonero.org/resources/moneropedia/tail-emission.html): permanent subsidy supports miner incentives and dynamic capacity. Page fetched by the coordinator. Mature tail following a declining schedule is not a direct test of flat issuance from zero, and nominal rewards guarantee neither purchasing power nor sufficient security.

No direct causal evidence of zero adoption penalty was identified. For zero
initial supply, unpenalized target-time `S(t) = A*t`; next-year growth is `1/t`:
year 2 doubles supply, year 11 adds 10%, year 51 adds 2%. More nominal units do
not change these percentages. Supply growth is not a mechanically equal price
decline. TJ accepts the early dilution as a values choice, not an adoption result.

Arithmetic correction to PLAN §8.1’s historical illustration: with 236,520
MEOW/year, a hypothetical genesis balance needed for 3% growth during year 2
is `236520/0.03 - 236520 = 7,647,480`; for 2% it is 11,589,480. The earlier
figures omitted year-1 issuance. Such a premine remains explicitly rejected.
