# Gated selected-issuance source overlays

TJ selected 9 MEOW/90 s, conditional on intended-crypto validation/relay/stale/
reorg testing; fallback 12 MEOW/120 s preserves 3,153,600 MEOW per 365 days
before penalties. [Decision](../../research/decision-2026-09-12-issuance.md).
The current fifteen-patch 0.9/120 build and 0.675/90 experiments remain
historical controls. These two mutually exclusive overlays are **not** added
to the production patch series or frozen reproduction inputs.

Run against the preserved current15 source and a new empty output directory:

```sh
bash spikes/selected-issuance/run.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-selected-issuance-new-run
```

Uses the existing immutable GCC 13 builder, no network, read-only source,
512 MiB memory/no swap, one CPU and the shared priority compiler lock.
No source download or host installation. Source hashes are checked before
applying each overlay **only to disposable copies**. The check compiles literal
reward/minimum-weight functions and both main/alt tally expressions, linked
to pinned upstream integer arithmetic. A Python big-integer oracle tests
3,024 cases per profile, including excess-weight refusal and saturation edges.
Source mismatch is refused and reverse application must restore exact bytes.

The only logic removal is the reward function's inherited whole-minute
assertion: the old minute-based emission calculation has already been removed
by the flat-subsidy patch. Config-only 90 s would otherwise fail to compile.
The selected target sets V2 to 90; inherited V1 remains 60 for the historical
fork model (v1 genesis, v16 from height 1). No penalty, genesis, fee, capacity,
precision or difficulty-floor rules change here. Source searches found display
minute conversions and a half-window timestamp conversion, which remain in
full integration review scope.

Output `summary.json` reports `launch_ready: false` unconditionally. The probe
is not a whole daemon build, integrated consensus/FCMP test, seed-recovery rerun
or matched-capacity network benchmark. Current source full-reward floors remain
unchanged, so capacity/time is **not matched** by applying these overlays alone.
The separate [September 13 recovery build](../../research/recovery-network-2026-09-13.md)
passes all 1,237 native tests and bounded empty-block P2P checks for each of
9/90 and 12/120. Fee/wallet/aggregate consumers still
require integration work before promotion. U64
generated-coins saturation moves to about 5.85 years;
primitive reward continuity passes but full-system reporting/aggregation does
not thereby become verified. No precision change or safety-gate relaxation.

[Recorded local result](../../research/evidence/swarm-2026-09-12/issuance/summary.json).

## Aggregate reporting across tally saturation

```sh
bash spikes/selected-issuance/run-reporting.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-reporting-new-run
```

This separate 512 MiB probe compiles the literal pinned core coinbase-sum method,
RPC `store_128`, hexadecimal encoder and wide money formatter. Synthetic block
storage and transactions supply both rewards, genesis, ranges crossing the u64
boundary, partial rewards and fees. Forty cases compare exact totals, RPC low/high
words, wide hexadecimal strings and 12-decimal CLI formatting against Python
integers. The legacy `emission_amount` alone is only the low 64 bits; consumers
must use `wide_emission_amount` or combine it with `emission_amount_top64`.

This checks aggregation/formatting arithmetic with synthetic storage. It does
not exercise database traversal, JSON serialization, the full RPC handler,
wallet balances/spending, fee validation or selected daemon binaries. The
fee-overflow fixture tests aggregate formatting, not consensus acceptance of
extreme fees. Historical sources and production patches stay unchanged.

## Native emission fixtures for selected builds

`selected-unit-fixtures.patch` is a separate test-only overlay, applied after
either economic overlay to a disposable source copy. It changes only
`tests/unit_tests/block_reward.cpp`; `fixture-source-lock.json` pins that file's
original bytes. Production `chain/patches` and historical fixtures stay intact.

The fixture asserts independent expected reward/spacing pairs, annual issuance
and saturation heights. Ten-year arithmetic uses the installed Boost u128 type
because selected issuance exceeds the internal u64 tally in about 5.85 years;
the test separately checks mathematical issuance and saturated tally behavior.
It retains supply/version independence, exact penalty fractions and positive
perpetual rewards. It does not change precision, fees or capacity policy.

```sh
bash spikes/selected-issuance/run-fixtures.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-selected-fixtures-new-run
```

The smoke test compiles the complete patched fixture with native headers/gtest
and literal extracted reward functions. Seven tests pass for each selected
profile; historical 0.9/120 fails pair, annual-supply and horizon assertions as
the negative control. Both overlays reverse to identical source bytes. Native
headers exceeded the 512 MiB lightweight cap, so this runner uses the existing
heavy guard: 5 GiB available-memory/disk preflight, shared compiler lock,
4 GiB/no swap container and one CPU. It reports fixture arithmetic only;
full daemon/wallet/unit integration is a separate build step.

`selected-gamma-fixture.patch` supplies the additional output-selection fixture
correction used by the full build runner. It converts block ages using the actual
target and keeps the original 36,000,000-second history horizon for both profiles.
One million draws reduce sampling error; the original 1.3–1.4-day median bounds
are unchanged. `gamma-fixture-source-lock.json` pins the upstream inputs. The
[recovery report](../../research/recovery-network-2026-09-13.md) records the
negative controls and repeated probe results that support this fixture change.
