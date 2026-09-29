# Independent TJS-991 exact-commit QA — Vanguard socket witness

**Disposition: changes needed for the requested daemon-transport gate.** The
TJS-990 socket harness is reproducible as bounded engineering evidence. It is
not a two-`monerod` transport test and does not establish daemon P2P behavior.
This review leaves TJS-751, TJS-953, TJS-958, and TJS-959 closed. It makes no
security, external-audit, public-network, or release-readiness claim.

## Candidate and method

- Writer handoff commit: `2bd853b` (`Record bounded Vanguard socket transport
  receipts`). Frozen code commit and independently checked out revision:
  `687b4b0e99cfbb1710c015fac86d950e20ac1ff2`. Upstream FCMP++ source:
  `e151643c5269c83bf24a83b2548e2493876026b2`.
- Writer's committed manifest SHA-256:
  `4e679926a049beb94d836c1f614a643d780f88718c1c9a9dba8af4d945d4b491`.
  Its archived bundle passed `verify-sync-process.py` and `sha256sum -c` from
  the clean checkout.
- Independent clean detached worktree at the full code SHA, with a private
  copy of the pinned upstream scratch tree and offline Cargo cache. Neither
  the writer worktree nor its source files were modified. Docker used the
  pinned image `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`,
  `--pull=never`, and `--network=none`.

## Reproduction

The following commands returned zero unless noted. The first run's full
receipt is in `research/evidence/vanguard-socket-tjs991-2026-09-29/exact-687b4b0/`.
Paths under `build/` were disposable in the clean checkout. To re-run the
author verifier, use a checkout with `687b4b0` in its ancestry, because that
verifier requires this relation.

```sh
git worktree add --detach /tmp/tjs991-qa-6769d055 687b4b0e99cfbb1710c015fac86d950e20ac1ff2
# Copy the previously pinned, prepared upstream tree and Cargo cache into
# /tmp/tjs991-qa-6769d055/build/vanguard-src without changing the writer copy.
cd /tmp/tjs991-qa-6769d055
python3 -B vanguard/run-sync-process.py --out build/tjs991-qa-exact-687b4b0
python3 -B vanguard/verify-sync-process.py build/tjs991-qa-exact-687b4b0
cd build/tjs991-qa-exact-687b4b0 && sha256sum --status -c MANIFEST.sha256
```

The runner printed `PASS_VANGUARD_SYNC_PROCESS two_runs=2`; both verifier and
manifest commands passed. The rebuilt binary SHA-256 was
`622250d1b2626d4606c1f514ec1cf34e6f8fe72a80c8ee8102a1ad5abb6ad8e9`,
identical to the writer's receipt. The independent manifest SHA-256 is
`3b8a629b5d1997b1e488b26cd19d05d208c5dd515cbcbfb29d92736455888665`.
Each run has 516 passing checks and the same check-stream SHA-256,
`ec0892cd23a9e4909c4f710cae03acdb3dd5cf962e3050c03f6cc1e9a16c5f9c`.
Process receipts show distinct source/peer PIDs (run 1: 8/9; run 2: 7/8).
An initial `sha256sum -c build/tjs991-qa-exact-687b4b0/MANIFEST.sha256`
from the checkout root failed because the manifest's paths are relative to its
own directory. Running it from that directory passed. This was an invocation
error, not a candidate failure.

| Requested condition | Observation | Scope |
| --- | --- | --- |
| Header, transaction, block delivery | The peer parses and echoes canonical headers, checks them against subsequent blocks, and passes serialized transactions/blocks to the pinned core. Out-of-order block 137 is refused before 136. | Harness commands over a Unix stream, not daemon P2P messages. |
| Reconnect and replay | Same peer PID after reconnect; replaying the tip leaves both recorded states equal. Oversized and truncated frames each close the connection, then a new connection succeeds. | No autonomous peer scheduling or backlog sync. |
| Reorg and key-image rollback | At depth 142 both cores report spend in chain and key image spent; the competing depth-144 branch reports neither; reverse depth-145 branch restores both. Stale-root supplement and pool paths are rejected on both cores. | Synthetic, valueless FAKECHAIN fixture. |
| Duplicate/malformed input | A duplicate tip is replayed without changing state; oversized and truncated frames are rejected. | No malformed parsed header, transaction, block, or duplicate transaction was injected. |
| Outside network reachability | A third exact-binary run exited zero with 516 checks. Live `docker inspect` reported `NetworkMode=none`, no port bindings or IP; `/proc/net/tcp`, `tcp6`, and `route` had zero entries beyond headers. | Proves this container's network namespace and TCP state during the probe. The Unix socket resides on a host bind mount and was not tested against other same-UID host processes. |

The third run's Docker command, live inspection, exit code, and raw check stream
are in `research/evidence/vanguard-socket-tjs991-2026-09-29/containment-probe/`.
All three runs used the exact rebuilt binary; the third run did not rebuild it.

## Findings and acceptance conditions

1. **Blocking scope mismatch — no daemon transport.** The test starts two
   `cryptonote::core` objects inside a parent/child harness
   (`vanguard/sync/process_tests.cpp:221,450-474`) and communicates using its
   custom `H`, `T`, `S`, `B`, and `Q` frames (`:242-311`). TJS-990's own
   `research/vanguard-socket-tjs990-2026-09-29.md` explicitly excludes
   `monerod`, P2P handshake, peer discovery, request scheduling, gossip, and
   transaction relay policy. The requested two-node daemon-transport gate is
   therefore unverified. Acceptance needs two actual isolated daemon processes
   exchanging headers, blocks, and transactions through the candidate daemon
   transport, with reconnect/replay, rollback, and containment receipts tied to
   their exact commit.
2. **Adversarial parsed inputs are unverified; the harness peer exits on them.**
   The witness injects only over-limit and short frames plus a repeated valid
   tip (`process_tests.cpp:546-555`). A malformed header throws at `:273-275`;
   the worker's catch at `:314-323` recovers only `bad socket frame` and
   `short socket frame`, rethrowing other parse errors to the outer worker exit.
   This is a source-level counterexample to general malformed-message recovery,
   not a claimed runtime exploit in `monerod`. Acceptance needs explicit bad
   header/transaction/block and duplicate transaction/block inputs against the
   actual target transport, followed by unchanged state and a healthy exchange
   on the same or a new connection as the daemon contract requires.

The bounded socket witness itself passed. These findings do not reopen the
previously accepted pipe-based two-process core gate or any earlier accepted
task. **Observed behavior:** clean exact-source rebuild reproduced the binary
and check-stream hashes; live containment inspection found no TCP listener or
route in the network-disabled probe.
