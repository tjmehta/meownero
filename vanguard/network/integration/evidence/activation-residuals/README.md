# Activation residuals: implementation and verification

Historical round-1 receipt for `5ee8ac7`; Security requested corrections F1/F2
in revision `66c79827`. The [correction receipt](../activation-residuals-correction/README.md)
supersedes its witness coverage and shared-backstop claims. Raw round-1 logs
and rendered rules below remain historical. The mutation script now exercises
the correction and writes into that separate evidence directory.

Writer: P2P & Mining Systems (`3730ad68-e373-4c8a-84df-2e11327b86a5`),
run `ee6866ce-7fe0-4de8-bd97-fab4c8943fa1`, 2026-11-11.
Base: `fe479217fb8fd712caaae1da3a47ebad9640b2f2`.
The exact candidate commit is recorded in the issue's implementation-report.
State: source verified and nft check verified; independent Security acceptance
is separate. This is an agent implementation receipt, not an external audit.

Authority: [assigned scope](/TJS/issues/TJS-4398), following the accepted
[previous hardening](/TJS/issues/TJS-4393). The run prompt was read in full;
`run-identity.json` records the 339-line prompt digest and current native identity.

## Changed contract and item coverage

| Item | Before → after; entry point and invariant | Verification |
| --- | --- | --- |
| 1: live dial witness | **Extends** `operator_contract` and **adds** the read-only `activation_witness` CLI. The rehearsal's default `seed_log_witness` and driver rows retain their original behavior. The live mode checks the running argv against the existing plan, including `--out-peers 0`, and alerts on any of the five upstream seed addresses outside static seed-list initialization, or connections_maker peer-selection/fallback messages. Generic non-upstream failed-connect and ping-back lines are tolerated. Missing seed-pass evidence is UNVERIFIED. | `ActivationWitness` tests all five upstream addresses against connect/failure/handshake messages; bad out-peer values; maker messages; INFO/DEBUG list initialization; housekeeping/ping-backs; missing evidence; CLI reads and exit codes 0/2/3. The runbook points activation monitoring to this new command. Five in-memory faults cover missing gates and false positives. |
| 2: real nft validation | Both variants are rendered with `eth0`, `192.0.2.10`, rate 30/minute and burst 10, then checked with the installed nft 1.0.9 and its exact libraries in a scratch image. This **adds evidence**, not host configuration. | `private.nft`, `operator-tls.nft`, `nft-image-inputs.json`, build log and `nft-checks.json`. Both `nft -c -f /rule.nft` commands exit 0 with empty stdout/stderr. Containers use `--network none --cap-drop ALL --cap-add NET_ADMIN`, a read-only rule-file mount, no host network and no apply command. Kernel: 6.8.0-146-generic. |
| 3: meter capacity | **Extends** the existing canonical template with `size 65535`, then a shared global new-packet backstop at 120/minute, burst 60, before accept. Both RPC variants retain their interface/address/port restrictions. A full meter can no longer bypass every rate bound. | The parser verifies exact size, source key, timeout, both rate expressions, port sets, drop verdicts and ordering. Six mutants remove/change size, change the key, remove the backstop, accept instead of drop, or place the backstop after accept; all are detected. Real nft checks cover both final templates. |
| 4: monitor overflow | **Extends** `outside_monitor.check_status` to map `math.isfinite` integer-conversion overflow to the existing Unverified input outcome instead of a traceback. Finite and NaN/infinity behavior is retained. | Positive and negative `10**400` regressions check direct validation and real CLI JSON/exit 3 with only pin/follower transports substituted. Removing the overflow handler is detected. Existing finite/nonfinite and monitor journey checks remain. |
| 5: executable identity (optional) | The path suffix validator is retained. The runbook now documents why identity belongs to managed binary custody: `run-operator.py:554-562` calls `run-profile.binary_copy`, which checks the expected SHA-256 and stable metadata; `Operator.daemon_argv` selects the staged `d.BIN/'monerod'`. The shape check and new witness are not executable attestation. | Source inspection of the unchanged staging/copy/launch path. This rationale applies to that managed launcher. An arbitrary caller or compromised seed process cannot acquire trusted identity merely by ending its argv in `/monerod`; activation must preserve verified-binary custody. |
| 6: stale evidence hash | Refreshes only the README entry in the previous evidence directory's `MANIFEST.sha256`. Historical README and logs are not rewritten. | All 20 previous manifest entries pass `sha256sum -c MANIFEST.sha256`. |

No feature is removed. Existing launcher, seal, backup, recovery, rollback,
outside-monitor pin/tip/peer checks and rehearsal verdicts stay in place. The
new activation command is an additive runbook consumer, not a change to the
granted rehearsal driver. No runtime plan or input changes require another
native seed run. `chain/`, `vanguard/network/operators.md`, `run-operator.py`,
`operator_driver.py` and `inputs.json` match the base byte for byte; the source
summary records frozen-path verification.

## Verification

From the task worktree root:

```sh
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --focus
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --mutations
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --full
```

Final full gate: **547 tests, zero failures/errors/skips, exit 0,
219.153 seconds**. The result and tested source hashes are in
`source-summary.json`.
The full gate discovers the network tests and all four integration modules;
`ResourceWarning` is an error and skips are not a pass. The inherited guard
refuses the original heavy lock by path/device/inode before open or flock and
refuses Docker/native launches by the source suites. Its summary must show an
empty original-lock touch list and unchanged original-lock metadata.

`mutations.json` and the paired gzip-compressed control/mutant logs preserve all 12 final
faults. Every control passes and every mutant fails; on-disk source bytes are
unchanged by mutation. Gzip preserves raw unittest output bytes (including its
trailing whitespace); decompression was checked byte for byte before removing
the plain copies. Fault sensitivity is not a native vulnerability
reproduction. The first focused run (62 tests) and first full run predate the
additional DEBUG-list regression; the final full gate includes that regression.
The additional run tests this discovered log-initialization case, not a retry
of an unexplained failure.

For nft, the exact executed argument arrays, both outputs, exits, rule hashes,
image ID, version and kernel are in `nft-checks.json`. `nft-image-inputs.json`
records the scratch Dockerfile, build command, source executable/library paths
and hashes. The image needed no package install, image pull or network. The
temporary image, containers and owned build context were removed afterward;
see `cleanup.json`. No host nft ruleset was read, replaced or applied.

## Source premises and limits

`fork-source.json` binds the inspected fork at
`e151643c5269c83bf24a83b2548e2493876026b2`, with file digests and line references:
`net_node.inl:836-842` (upstream seeds), `1529-1541` (out-peer gate), `1495-1505`
(shared INFO connect failure), `1651,1911,2066` (maker messages), `1941,1977`
(DEBUG seed-list loading), `2507-2562` (ping-back), and `3052-3090` (housekeeping).
These source premises, the actual checked argv and the complete current-launch
log jointly support the activation sample. INFO logs alone do not identify
every non-upstream caller. Upstream IP use by an otherwise tolerated path also
alerts conservatively. A missing launch prefix is UNVERIFIED, including a
restart whose retained white list causes no seed pass. Operators must retain
the seed-pass evidence or investigate that outcome, not suppress it.

The global backstop bounds admission when source-meter insertion fails. Traffic
below its bucket can still pass. A hostile source can exhaust the shared global
bucket; this is bounded fallback, not availability or per-source fairness under
exhaustion. `ct state new` includes retransmissions. No full-set traffic test or
live enforcement is claimed. `nft -c` proves validity on the recorded tool/kernel,
not on a future chosen host; validate its final substituted file there.

Primary references inspected for the template and check semantics:

- [nftables meters](https://wiki.nftables.org/wiki-nftables/index.php/Meters)
  documents per-source state, timeouts and rate/burst expressions.
- [Netfilter nft manual](https://netfilter.org/projects/nftables/manpage.html)
  documents token buckets, `over`, and check mode without applying changes.
  Local installed `nft(8)` and the real 1.0.9 checks qualify the used syntax.

## Unconfirmed / next

Security (`f2908de7-2099-425c-97a7-69cc70cc887e`) reviews the exact candidate
through the existing native review stage, with one correction round per review.
The Meownero lead owns later integration and authorized public replay after
acceptance. No public activation, external push or native seed run occurred.
No host firewall, DNS, uid, router or rented-host configuration changed. `launch_ready` and
`public_launch` remain false. Live outside-vantage behavior remains unmeasured.

Needs TJ: None.
