# Initial adversarial and matched-issuance evidence — 2026-09-12

Local engineering resumed after TJ completed the private snapshot publication.
Future changes remain local. This is a bounded M2 checkpoint, **not M2 completion,
an audit, a timing selection or a launch-difficulty decision**.

## Actual daemon reorganization and rejection tests

Run `bash chain/test-reorg.sh <built-source> <new-output-directory> [mode]`.
Both modes passed with the existing thirteen-patch daemon:

| Mode | Common chain | Difficulty | Result |
|---|---|---|---|
| `regtest` | 65 blocks | explicit fixed difficulty 1 | [PASS](evidence/2026-09-12/m2/reorg-regtest.json) |
| `mainnet-window` | 738 blocks | native DAA, shipped floor 1, **no fixed override** | [PASS](evidence/2026-09-12/m2/reorg-mainnet-window.json) |

Two daemon processes run inside `--network none`; no ports are published. The
harness explicitly delivers blocks through RPC, withholding them while building
competing histories. It checks that a shorter branch and an equal-work branch do
not replace the incumbent, then that a greater-work branch replaces three blocks.
Both nodes agree on tip, cumulative work and exact subsidy accounting afterward.
Restarting the receiving daemon preserves the selected chain and work.

Five mutations are rejected without changing tip/work: malformed blob, obsolete
block version, timestamp beyond the two-hour bound, timestamp below the median,
and coinbase reward inflated by one atomic unit. The unchanged template is then
accepted as a positive control. Errors and assertion results are in the JSON links.

The mainnet-mode run uses historical headers at exact 120-second intervals,
asserting that every template's native difficulty remains one. Every block still
passes the daemon's actual PoW and consensus checks. It crosses the 720/735 sampling
boundaries but does **not** stress high-difficulty mining, changing work, full
alternative-only windows, transactions, P2P partition recovery or propagation.
No private keys are loaded; mining uses an existing test-fixture public address.

## Matched-issuance native-DAA scenarios

Run `bash chain/benchmark-difficulty.sh <patched-source> <new-output-directory>`.
The runner compiles the actual `src/cryptonote_basic/difficulty.cpp` into a narrow
C interface and invokes it from Python. It does not substitute a Python DAA port.
Actual source hashes and immutable builder identity are recorded in
[source provenance](evidence/2026-09-12/m2/daa-source-sha256s.txt) and
[image identity](evidence/2026-09-12/m2/BUILDER_IMAGE_ID).

**720 runs passed**: 20 seeds × 6 scenarios × 3 floor policies × 2 approved
pairings. Every pairing is asserted to issue exactly **236,520 MEOW per 365 days
at target spacing**, in atomic integer arithmetic. Hashed-work arrivals are
exponential; rates are integrated across phase changes, zero hashrate produces
no blocks, and a block beyond the 24-hour horizon is not counted. Genesis adds
work one but zero issuance and is excluded from DAA samples. The last 735 samples
are passed to native code, which retains its first 720. Timestamp validation in
the model accepts equality with the last-60 median and preserves the two-hour
future bound.

The hashrate is **assumed 5 MH/s**, not measured or guaranteed. Each candidate uses
the same random seeds. Scenario definitions are in the script; timestamp attackers
operate **from genesis**, unlike the older simulator's warmed-up attack trials.
Floor alternatives are **model-only**, `H × target / 4` either permanently or for
blocks 1–720. Production floor and lifetime are unchanged.

Shipped-floor-one results (mean first-day issuance over 20 seeds):

| Scenario | 90 s / 0.675 | 120 s / 0.9 | Paired difference, 90 minus 120; approximate 95% CI for the mean |
|---|---:|---:|---:|
| Steady | 654.953 | 656.775 | −1.823 [−8.209, 4.564] |
| 10 kH/s first hour, then 5 MH/s | 864.270 | 883.215 | −18.945 [−25.424, −12.466] |
| Tenfold hashrate from hours 6–8 | 583.706 | 629.010 | −45.304 [−53.292, −37.315] |
| Zero hashrate hours 6–8, 1% hours 8–16, then recovery | 632.644 | 618.750 | 13.894 [2.517, 25.271] |
| 20% of producers timestamp at future bound | 1,905.120 | 1,895.265 | 9.855 [−18.636, 38.346] |
| 50% of producers timestamp at future bound | 601.324 | 743.670 | −142.346 [−195.179, −89.513] |

Units are MEOW; the target-day expectation is 648. These are first-day transient
results, not guaranteed calendar emission or long-run inflation. Confidence
intervals use paired seed differences and Student-t with 19 degrees of freedom;
they describe sampling uncertainty in this model, **not model validity**. Twenty
seeds are not enough to characterize rare-event tails. Full per-seed hourly counts,
longest gaps, all floor alternatives and summaries are in
[raw benchmark data](evidence/2026-09-12/m2/daa-scenarios.json).

## Implications and limits

- Steady-state timing preference is not established: the steady first-day paired
  interval includes zero. Different transient responses do not establish that
  either candidate is safer or more adoptable.
- **Launch timestamp risk remains open.** The 20% future-stamp launch scenario
  produces roughly three target-days of issuance inside the first modeled day.
  The 50% case has large stalls and seed variance. This is a native-DAA model
  finding, not a demonstrated exploit against a live network. Replay under real
  miners, competing branches and realistic clocks before assigning severity or
  choosing a mitigation. The earlier warmed-up-model “no easy win” statement
  must not be read as covering this launch scenario.
- Floor alternatives do not authorize a constant or lifetime change. A bounded
  floor still bounds blocks, not wall-clock duration; neither guarantees liveness
  when mining disappears. The model's assumed hashrate is not calibration evidence.
- **Propagation, proof-validation cost, block capacity, transaction load, orphan
  rates and network reorg performance are not benchmarked here.** This checkpoint
  covers actual fixed/low-work daemon rejection and reorg behavior plus simulated
  difficulty/issuance transients. The full matched-issuance network comparison,
  sustained uptime and adversarial privacy/transaction suite remain M2 work.

Historical `spikes/candidate-m/difficulty_sim.py` results remain historical: that
port includes genesis in its samples, uses median + 1 and counts the final
out-of-horizon draw. This native harness corrects those model details and uses
different attack timing; numerical comparisons must state those differences.
