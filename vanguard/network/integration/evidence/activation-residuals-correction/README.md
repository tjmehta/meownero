# TJS-4398: Security correction round

**Changed**

Writer: P2P & Mining Systems `3730ad68-e373-4c8a-84df-2e11327b86a5`,
run `73ec5ffb-943b-4310-8c22-cb7abfe5d24c`, 2026-11-11.
Correction to candidate `5ee8ac7d12e17f1baac6baaabd097b1e017eee8b`,
on accepted base `fe479217fb8fd712caaae1da3a47ebad9640b2f2`.
The exact new candidate is recorded in the issue's implementation report.
This implements both blocking findings in [Security revision 66c79827](/TJS/issues/TJS-4398#document-security-review).
Items 2, 4, 5 and 6 remain accepted from that review; their prior evidence is
preserved. No independent acceptance of this correction is claimed.

| Finding / original item | Change and observable contract | Checks |
| --- | --- | --- |
| F1 / item 1 | The read-only CLI binds the supplied native log to the running `--log-file`, requires numeric logging 1–4, derives the current process-start upper bound from procfs, and selects the unique current startup banner. Only its suffix is sampled. The seed-pass count stays diagnostic; a retained-white-list restart can reach OK without it. Old seed passes cannot establish current coverage. | Source tests for restart, old-only and multi-launch logs, WARNING/category overrides, INFO/DEBUG initialization, upstream and maker activity, housekeeping and ping-backs; CLI exit 0/2/3. Four added witness mutants detect seed-pass dependency, missing logging gate, old-banner acceptance and missing launch slicing. |
| F2 / item 3 | A named dynamic IPv4 set retains the 65,535 capacity and 1-minute idle timeout. `update @seed_sources` meters by source. Only `ip saddr != @seed_sources` reaches the shared fallback, before accept. Tracked sources never spend shared tokens; insertion failure still has a bound. | Parser pins declaration, source key, timeout, rates, ports, conditions and order. Two added backstop mutants detect unconditional or reversed shared limiting. Both variants and plan maxima pass real nft checks. Functional loopback probes include rejected-design and full-set negative controls. |

Runbook: `integration/topology-operators.md` explains the file to pass,
coverage derivation, logging visibility, restart behavior and recovery on
UNVERIFIED. Existing rehearsal rows are unchanged. All 80 tracked frozen paths
match the accepted base, including `chain/`, `network/operators.md`, runner,
driver and every tracked `inputs.json` (`frozen-paths.json`). No grant for a
native seed rerun was needed or requested: launcher, driver and inputs did not
change. One correction round; no delegation or native daemon work.

**Verified**

Run from the task worktree root:

```sh
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --focus
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --mutations
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --full
python3 -B vanguard/network/integration/evidence/activation-residuals-correction/nft-checks.py
python3 -B vanguard/network/integration/evidence/activation-residuals-correction/cli-check.py
```

- Focus: 66 tests, no failures/errors/skips, exit 0. Final full suite: **550 tests,
  no failures/errors/skips, exit 0, 223.019 seconds**. The receipt and tested
  hashes are in `source-summary.json`; raw output is `full.log.gz`.
  ResourceWarning is an error. Original heavy-lock metadata remains unchanged,
  with no original-lock touches. Source-suite native/Docker launches are refused.
- All **18** in-memory mutants are detected, with clean controls and unchanged
  on-disk source bytes. `mutations.json` and paired gzip logs preserve evidence.
  The first harness attempt had a SyntaxError because the old call-site fault
  no longer matched the assigned expression. That run is preserved; correcting
  the in-memory mutation target produced the clean control/detected-mutant run.
- **nft 1.0.9**, kernel 6.8.0-146-generic: `private`, `operator-tls` and both
  plan-maximum renders pass `nft -c -f` (exit 0, empty output). Invalid size
  `banana` fails (exit 1). `nft-checks.json` records exact argv, outputs and hashes.
  The scratch container uses `--network none --cap-drop ALL --cap-add NET_ADMIN`,
  0.5 CPU, 128 MiB and 64 PIDs; tools/libraries and evidence are mounted read-only.
  Nothing reads or changes host rules. The owned image and context were removed.
- Functional loopback traffic in that disposable namespace: 12 sources each get
  10 of 15 attempts; a fresh source gets **5/5**. At plan maximum, one source gets
  60/70 and the fresh source **5/5**. An unconditional-backstop control yields
  only **1/5** for the fresh source, so the probe detects F2. A deliberately small
  size-4 set admits **61/80** from the fifth source, bounded by the fallback;
  removing its backstop admits **80/80**, proving the insertion-failure control.
  This is a reduced-capacity witness, not a 65,535-source capacity stress test.
  `functional-check-output.json` holds exact commands and raw results. Its probe
  adapts `func_lib.py` from Security attachment `3120ac7d` (hash in run identity).
- The unmocked CLI runs **13 cases**, including first launch, restart without a
  seed pass, old-only log, accumulated launches, old/current upstream dials,
  benign dials, missing header, wrong file, three WARNING overrides and dead PID.
  It uses a short-lived sleeping C stand-in with the checked argv, actual procfs,
  real log files and real CLI subprocesses. It is **not a native seed run**.
  All asserted exit codes pass; `cli-check-output.json` preserves results.
- Prior accepted monitor-overflow behavior remains untouched and its mutant is
  included. The previous security-notes manifest still verifies. Round-1 raw
  evidence is retained; only its README supersession note, executable mutation
  script and associated manifest hashes are updated.

Source premises are pinned in `source-premises.json` at fork `e151643c`:
`daemon/main.cpp:274–298` establishes the banner after logging setup and before
node startup; `mlog.cpp:49,96–121` establishes file format and numeric logging;
easylogging's location formatter supplies the source path. Procfs starttime is
field 22 in clock ticks ([Linux proc_pid_stat(5)](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html));
`CLOCK_BOOTTIME` includes suspended time ([Linux clock_gettime(2)](https://man7.org/linux/man-pages/man2/clock_gettime.2.html)).
The timestamp selection and conservative upper-tick bound are this writer's
inference from those interfaces. The named-set update/timeout pattern follows
[Netfilter's meter documentation](https://wiki.nftables.org/wiki-nftables/index.php/Meters);
check mode is documented in the [nft manual](https://netfilter.org/projects/nftables/manpage.html).
Actual nft 1.0.9 execution above qualifies the specific syntax used here.

**Unconfirmed/next**

Security re-reviews the exact candidate through the existing native stage.
The Meownero lead owns later integration and authorized public replay. No merge
or external push occurred; agent review is not an external audit.

The log binding assumes default timestamp format, the daemon's timezone, stable
wall time since launch, and managed single-writer log custody. It fails closed
for missing/ambiguous banners, startup within its start clock tick, unreadable
inputs, nonnumeric/category-override logging, or process/clock changes during
sampling. A clock step before the sample is not reconstructed; investigate it
and recover launch evidence. This witness does not attest executable bytes,
prove arbitrary-egress absence or replace the outside monitor. Retained binary
hash custody still belongs to the unchanged managed launcher.

Tracked-source fairness is preserved; untracked sources share a bounded fallback
and can consume each other's budget when the set is full. SYN retransmissions
consume packet tokens. No public-host enforcement, native populated-white-list
restart or outside-vantage observation was run. Revalidate the final substituted
rule on the chosen host. No host firewall/router/DNS/uid/rented-host change or
activation occurred. `launch_ready` and `public_launch` stay false.

Needs TJ: None.
