# TJS-1003 independent exact-commit QA — native Vanguard daemon P2P

**Verdict: accept the bounded fixed-difficulty regtest witness at code commit
`6ba799b909d005be57232e4566ee3617a63574ac`.** Two cleanly rebuilt,
offline trials satisfy the four requested TJS-991 gaps. This verdict covers
two `monerod` processes in one network-disabled namespace, not a public
network, loaded performance, security audit, or release readiness. TJS-751,
TJS-953, TJS-958 and TJS-959 remain closed.

## Exact candidate and independent reproduction

- Code: `6ba799b909d005be57232e4566ee3617a63574ac`; writer evidence:
  `918d50cf1c59d76fa77e5648d8c48acab82c189e`; upstream FCMP++:
  `e151643c5269c83bf24a83b2548e2493876026b2`.
- Writer bundle: `research/evidence/vanguard-daemon-p2p-tjs996-2026-09-29/`
  at the evidence commit. Its `MANIFEST.sha256` digest is
  `afedfb9d82162d954ecdbc556dd7c02394bdb678d29cadea6e09f9290a760942`.
  All 43 manifest entries passed `sha256sum -c`; its verifier printed
  `PASS_DAEMON_P2P_RECEIPT_RECONCILIATION`.
- A clean detached checkout at the full code SHA used a private copy of the
  pinned upstream tree and offline Cargo cache. The copied tree excluded the
  writer's compiled `build/` and test injections; `git status --short` in it
  was empty. No writer source or evidence was edited. The fresh configure and
  `make -j1 daemon wallet_rpc_server` ran in the pinned image
  `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`
  with `--pull=never --network=none`, two CPUs, 4 GiB memory/swap, and the
  offline Rust cache. The clean build exited 0, peaked at 3,528,261,632 bytes,
  and recorded zero OOM events. The actual command and logs are in
  [rebuild/](evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/rebuild/).
- Rebuilt `monerod`: SHA-256
  `5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509`
  (29,872,608 bytes). Rebuilt `monero-wallet-rpc`: SHA-256
  `cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2`
  (33,545,392 bytes). Both exactly match the writer's receipt.
- The unchanged code-commit runner made two fresh trials. Build, run 1 and
  run 2 exited 0 (5.34, 32.05 and 29.94 seconds). The independent bundle is
  [native/](evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/native/); its
  `MANIFEST.sha256` digest is
  `41799ea1314daf620357f5a2dd30884e0534ee0f094bfbce019d518ded861aed`.
  Both the writer verifier and the separate
  [QA oracle](qa_vanguard_daemon_p2p_tjs1003.py) pass this bundle and the
  writer bundle. The QA oracle checks the exact pooled state that the writer
  verifier omits. The outer QA evidence manifest has SHA-256
  `126f1485071a1b8a5e9252c3ef58efe7a06e66b98de1ed052c6281a200ccbe3b`
  and all 59 entries pass `sha256sum -c`.

## Requested conditions

| Condition | Independent observation |
| --- | --- |
| Real daemons and native P2P | `process_started` records distinct `monerod` PIDs and LMDB directories; native peer counts are nonzero. Raw Levin frames carry `2002` FCMP++ transaction notifications, `2008` block notifications containing the header, and `2006/2007` chain exchange in both directions. The wallet RPC reports RingCT type 7. The two RPC block headers agree after native delivery. This is not the TJS-990 custom `H/T/S/B/Q` protocol. |
| Duplicates and malformed parsed inputs | Captured `2002` and `2008` frames were replayed, then same-size malformed transaction, header and block bodies were injected. After transaction inputs, tips and pools match earlier records and key-image status is pooled on both nodes; after block inputs, the full state matches a pre-input snapshot. Daemon 1 logs one transaction and two block parse rejections in each trial. Five bridge connections, unchanged daemon PIDs, zero daemon exit codes and a later native block relay show recovery after parse errors and reconnects. |
| Partition and rollback | Node B removed two blocks through local regtest RPC and mined a three-block competing branch while the bridge was partitioned. After reconnect, both tips converged at height 73, the old tip was orphaned, each key image changed from confirmed `1` to pooled `2`, and the same transaction appeared in both pools. A subsequent block converged at height 74. |
| Reconciliation and containment | The writer and fresh bundles pass `PASS_DAEMON_P2P_RECEIPT_RECONCILIATION` and `sha256sum -c`. During fresh run 1, independent `docker inspect` showed `NetworkMode=none`, no port bindings or IP; `docker exec` showed only `lo`, no route, six loopback-only listeners, and `ENETUNREACH` for reserved address `192.0.2.1`. The runner's two run-local containment files also show only loopback listeners and no routes. |

Fresh run 1 and run 2 both show confirmed key images `[1,1]`, rolled-back
key images `[2,2]`, and the run's exact transaction hash in both pools. Both
have five bridge connections; bridge byte counts are 47,628 in each run.
Run-local memory peaks are 804,282,368 and 757,874,688 bytes, with zero OOM
events. Exact txids, states and frame hashes are in `native/run*/public/` and
the [QA outputs](evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/checks/).

## Commands and negative control

The detached checkout was created with
`git worktree add --detach <run-scratch>/exact 6ba799b909d005be57232e4566ee3617a63574ac`.
The copied upstream and Cargo cache were prepared under that checkout's
`build/vanguard-src/`. The actual clean Docker configure/build command is
preserved in `rebuild/command.sh`. These commands exited 0:

```sh
python3 -B <exact>/vanguard/run-daemon-p2p.py --src <exact>/build/vanguard-src --out <exact>/build/tjs1003-qa-native --runs 2
python3 -B <exact>/vanguard/verify-daemon-p2p.py research/evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/native
python3 -B research/qa_vanguard_daemon_p2p_tjs1003.py research/evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/native
(cd research/evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/native && sha256sum --status -c MANIFEST.sha256)
```

An adversarial copy of the writer bundle was made outside the repository:
both `result.json` and rollback event were changed to key-image `[0,0]` and
empty pools in both trials, then the two affected manifest hashes were
updated. `sha256sum --status -c` exited 0 and the writer verifier exited 0
with `PASS_DAEMON_P2P_RECEIPT_RECONCILIATION`; the independent QA oracle
exited 1 at its exact `[2,2]`/pool assertion. The mutation and command
outputs are documented in
[negative-control.md](evidence/vanguard-daemon-p2p-tjs1003-2026-09-29/checks/negative-control.md).

## Source-located findings and limits

1. **Nonblocking receipt-verifier defect.** At candidate
   `vanguard/verify-daemon-p2p.py:69-70`, any rollback status other than `1`
   passes, and neither pool is required to contain the transaction. At
   `vanguard/daemon-p2p.py:433-435`, the runner has the same weak rollback
   condition. The negative control proves that a false unspent/empty-pool
   receipt passes the writer verifier after hashes are updated. For future
   reuse, require `[2,2]`, the exact txid in both pools, and equality between
   rollback event and result. The unmodified writer and fresh receipts meet
   these conditions under the independent QA oracle, so this defect does not
   overturn this exact-run verdict.
2. **Nonblocking duplicate-transaction baseline gap.** At
   `vanguard/daemon-p2p.py:378-381`, the snapshot used to assert duplicate
   transaction invariance is taken after injecting the duplicate. A change
   before that snapshot could go unnoticed. The archived and fresh receipts'
   prior `fcmp_transaction_relayed` pools and funded tip match their post-input
   state, and the QA oracle checks that match. A future runner should take the
   complete tip/pool/key-image snapshot before injection.

This uses fixed-difficulty regtest and one network namespace. The competing
branch is created with local `pop_blocks` rather than natural mining, and the
test does not exercise a root-changing FCMP proof after the split. There is
no inference here about public-network behavior, performance, security, or
launch readiness. **Observed behavior:** the exact clean binary hashes and
two independently reproduced native daemon receipts match the claimed bounded
state transitions; the writer verifier's rollback assertion needs tightening.
