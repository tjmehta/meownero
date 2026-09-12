# Selected issuance: aggregate reporting checkpoint

The earlier [decision](decision-2026-09-12-issuance.md) left selected-family
aggregate consumers open. This checkpoint tests one bounded part of that work:
the exact pinned core coinbase aggregation method and RPC/CLI amount formatting.
Production sources, fifteen patches and historical evidence remain unchanged.

## What was exercised

`spikes/selected-issuance/verify-reporting.py` extracts literal hash-verified
`core::get_coinbase_tx_sum`, `store_128`, `hex`, `insert_money_decimal_point`
and the u128 `print_money` overload. Synthetic storage supplies block ranges
and transactions; the decimal default is supplied as the retained 12 places.
The wide-string conversion matches the daemon CLI caller. The supplied reward
values represent the two selected overlays; the overlays and daemon are not
built by this test.

Forty cases cover zero count, genesis-only and first payment, both selected
rewards, ranges before/across/after the generated-tally saturation height,
partial subsidy, nonzero fees and independent aggregate-fee overflow. Python
integers supply the expected totals, low/high RPC words, wide hexadecimal and
fixed-decimal display. A deliberately wrong source digest is rejected.

Both the direct probe and the final wrapper run passed all 40 cases. The latter
uses the preserved immutable GCC 13 image, network disabled, read-only source,
one CPU, 512 MiB memory/no swap. This lightweight cap permits running alongside
the priority clean15 build without acquiring its long-held compiler lock.

## Result and consumer requirement

The core sum remains accurate above u64 because it accumulates into u128. The
RPC wide field and daemon CLI retain that value; `emission_amount` alone is the
low word and wraps as a representation. Consumers must parse the hexadecimal
`wide_emission_amount`, or reconstruct `(emission_amount_top64 << 64) +
emission_amount`. The same applies to fee fields. This is existing upstream
behavior, not a production fix introduced here.

Synthetic storage does not establish database traversal, consensus acceptance
of the extreme-fee fixture, actual RPC JSON serialization, wallet balance or
spending correctness, or full selected-profile compatibility. The internal
generated tally remains saturating and is not an exact post-boundary supply
counter. No launch gate is marked passed.

## Reproduction and receipts

```sh
bash spikes/selected-issuance/run-reporting.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-reporting-new-run
```

Durable [summary and source hashes](evidence/resume-2026-09-12/reporting/reporting-summary.json),
[generated compiled source](evidence/resume-2026-09-12/reporting/reporting-probe.cpp)
and [run log](evidence/resume-2026-09-12/reporting/run.log). The compiler reports
one unused parameter warning in the unmodified extracted upstream lambda.
