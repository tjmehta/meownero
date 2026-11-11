# Security notes N1–N6: implementation and source evidence

Writer: P2P & Mining Systems (`3730ad68-e373-4c8a-84df-2e11327b86a5`), run
`d8848c2a-2f59-4604-a509-a52e861b8644`, 2026-11-11.
Base: `def24f0c9fa9b1a928db718e87ae0f17eb91c301`. The exact candidate commit
and branch are recorded in the issue's implementation-report document. This
directory is committed with that single candidate; `source-summary.json` binds
the tested source bytes. State: source verified, pending independent Security
acceptance; no activation or native execution.

Authority: [assigned scope](/TJS/issues/TJS-4393), closing the six notes in
[Security's original verdict](/TJS/issues/TJS-4238#document-security-review),
revision `22ba9c1a-74a8-467b-9bb5-cffe86cf8909`.

## Changed contract and note coverage

The baseline-to-candidate change extends the existing operator package. It adds
only a text-template RPC selector, stricter validation, runbook corrections and
regressions. No new native/runtime mechanism, service or dependency is added.

| Note | Change and affected entry point | Verification |
| --- | --- | --- |
| N1 | `operator_contract.check_public_seed` now requires the option's presence and the exact value `--check-updates disabled`. The existing driver already supplies it. | `PublicSeedShape.test_updates_must_be_explicitly_disabled`: omission, `notify`, `download` refuse; `disabled` passes. Reverting both presence and value checks causes three failures. |
| N2 | The canonical `OBJECT_CLASSES['port-rule']['rule']` template uses input policy drop and an IPv4 source-keyed new-connection meter before an explicit interface/address/port allow-list. `port_rule()` defaults to 48080 only; `port_rule('operator-tls')` adds 48081 to the meter and allow-list. The removal command is unchanged. | `PublicSeedShape.test_port_rule_parses_to_only_planned_ports_with_per_source_limits` parses the table, both chains, rule order, meter key, rate/burst and both port sets. No nft command is invoked. |
| N3 | `topology-operators.md` explains outbound TCP ping-backs to an inbound peer's own IP/advertised P2P port, outside `--out-peers`. The template explicitly chooses output policy accept. It also corrects the overbroad claim that the public shape never contacts third-party hosts. | Source review against the original verdict's pinned `e151643c` facts (`net_node.inl:2507,2735–2740`); the N2 parser checks output policy accept. Rehearsal clients hide their ports, so zero dial lines never proved this path. |
| N4 | Activation checklist item 1 distinguishes uid file/process authority from network reach. It says every local uid can reach host-loopback private RPC when the seed shares the host network namespace, and recommends a separate seed network namespace and authenticated operator tunnel. | Runbook source review; the template is explicitly scoped to the dedicated seed namespace. No uid or namespace is created here. |
| N5 | `outside_monitor.follower_info` supplies `ProxyHandler({})` alongside the existing Digest handler. `check_status` requires a finite numeric `unix`. | `OutsideMonitor.test_follower_ignores_environment_http_proxy` uses real local follower/proxy sockets with `http_proxy` set and no bypass; a default-opener control proves the proxy is active. `test_nonfinite_status_timestamp_is_unverified_even_when_tips_agree` checks NaN/±infinity, UNVERIFIED evaluation and finite integer/float controls. Each removed control is detected. |
| N6 | Runtime controls are unchanged. Regressions protect `run-operator.read_relayed` and `Operator.open_public`. | `OperatorManager.test_relay_refuses_symlink_to_valid_owner_only_file` accepts the 0600 target but refuses its symlink. `test_public_reopen_refuses_reused_pin_before_publishing` accepts first/rotated pins and refuses reuse without advancing the launch counter or publishing. Both removed-control mutations fail. Launch/listener transports are substituted; publication uses real files. |

The only existing runtime callers affected are the operator driver's public
seed validation and outside-monitor sampling. The driver, runner and inputs
stay unchanged, so the assigned contract requires no new native grant/run.
Failure behavior gets stricter (PolicyRefusal or UNVERIFIED). Seal, backup,
rollback, pin distribution and recovery behavior are preserved. There is no
runtime plan drift beyond these six assigned notes.

Verification also exposed a pre-existing socket leak in
`test_exposure.PinnedClient.test_closed_session_never_retries_digest_in_plaintext`:
its `rpc.session()` probe opened a real TLS socket without closing it. The test
now uses `contextlib.closing`; its assertions and runtime source are unchanged.
This bounded fixture cleanup makes the source gate free of that resource warning.

## Verification

Run from the task worktree root with Python 3.15.2 and standard-library tools:

```sh
python3 -B vanguard/network/integration/evidence/security-notes-n1-n6/guarded-source-tests.py --focus
python3 -B vanguard/network/integration/evidence/security-notes-n1-n6/guarded-source-tests.py --mutations
python3 -B vanguard/network/integration/evidence/security-notes-n1-n6/guarded-source-tests.py --full
```

- Focused operator suite: **56 tests, zero failures/errors/skips**, exit 0,
  60.301 seconds including setup. See `focused-source-tests.log`.
- Full source suite: **540 tests, zero failures/errors/skips, exit 0, 232.380 seconds including setup; no resource warning**. See `full-source-tests.log` and
  `source-summary.json` for the exact counts and wall time.
- Each guarded command checks the original lock by path and device/inode before
  open/flock. Lock metadata remains unchanged and original-lock touch lists are
  empty. The copied guard also refuses real Docker/native executable spawns;
  the source suites use substituted native effects and isolated fixtures.
- `ResourceWarning` is treated as an error. No skipped test counts as pass.
- The first full run's unclosed-socket warning is retained in
  `full-source-tests-before-fixture-cleanup.log`; the final full run includes
  the fixture cleanup above. No assertion was removed or weakened.
- An initial inherited filename-discovery command found zero tests because
  `integration/` is a namespace directory. `focused-empty-discovery.log` is
  retained as invalid evidence. The corrected wrapper explicitly loads
  `integration.test_operator` for focus, and all four integration test modules
  alongside root discovery for full. It asserts nonempty discovery.
- Source-scope and whitespace checks pass. `chain/`,
  `vanguard/network/operators.md`, `run-operator.py`,
  `integration/operator_driver.py` and `integration/inputs.json` match the base.

Mutation results (`mutations.json`, `mutation-run.log`, and paired logs):

| Removed control | Passing control tests | Mutant outcome |
| --- | --- | --- |
| N1: required presence and disabled-only update value | 1 | 3 failures |
| N5: empty proxy handler | 1 | 1 failure |
| N5: finite timestamp predicate | 1 | 1 failure, 2 errors (±infinity reach the stale-status Alert instead of Unverified) |
| N6: O_NOFOLLOW in read_relayed | 1 | 1 failure |
| N6: changed-pin requirement in open_public | 1 | 1 failure |

Mutations replace only functions in memory, with exact single-match checks and
restored attributes. On-disk source hashes are identical before/after. These
faults prove test sensitivity; they are not native vulnerability reproductions.

## Primary API references

- Python documents an empty proxy mapping as disabling autodetected proxies;
  this supplies the bypass in `follower_info`:
  [ProxyHandler](https://docs.python.org/3.15/library/urllib.request.html#urllib.request.ProxyHandler).
- `math.isfinite` rejects infinity and NaN:
  [isfinite](https://docs.python.org/3.15/library/math.html#math.isfinite).
- The nftables project's source-keyed meter and timeout examples ground the
  review-only template:
  [Meters](https://wiki.nftables.org/wiki-nftables/index.php/Meters).

## Unconfirmed / next

Security (`f2908de7`) reviews the exact candidate via this issue's configured
native review stage, with one correction round. After acceptance, the Meownero
lead integrates with `--no-ff` and replays to the public repository.

No new native, second-uid, second-host, public-host or outside-vantage evidence
is claimed. The nft source parser is deliberately limited to this template;
kernel compatibility, substituted-rule validation and live enforcement remain
unmeasured until authorized activation work. No firewall, uid, router, DNS,
rented-host or port change, public push, merge or launch occurred.
`launch_ready` and `public_launch` remain false.

Needs TJ: None.
