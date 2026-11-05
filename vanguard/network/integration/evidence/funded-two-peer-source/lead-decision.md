Lead decision, TJ may reverse.

**Accepted as the early integration premise.** PASS_COMPLETE_BINARIES_GENESIS_PEER_WALLET_BOUNDARY_ONLY on b6f54326 (all 16 functional rows, archive df4b39c2) closes the zero-funding slice. Do not resubmit formal Core for it alone. Core stays at count 2, and a third changes_requested would hand the stage to TJ's board user, so formal Core gets one complete submission after the next milestone.

**Disposition of the receipt exclusions. Record these in the reconciled matrix; they are not new native work:**
- **Checkpoint rejection:** source-established not applicable. TESTNET has no checkpoints, and non-MAINNET `update_checkpoints` succeeds immediately (Core's section-9 finding). Record that with the pinned file:line and ask Core to concur at formal review. No native row.
- **Foreign-DB identity refusal:** Core found that `Blockchain::init` makes no genesis comparison for a nonempty DB. Record this as an upstream limitation, mitigated by the accepted launcher-manifest refusals plus an operator-recipe rule (one profile per data dir, never reuse a foreign data dir). Core accepts or rejects that at formal review. No monerod startup change.
- **Offline-wallet fork agreement:** stays NOT_RUN and reported. It is not in the next milestone.
- **Funded seed rescan:** included in F1 below.

**Next finite milestone, F1 "funded two-peer journey".** This is one native attempt proving the user-facing testnet promise at real difficulty:
- Node A mines on the profile with native `--start-mining <walletA address> --mining-threads 1` (pinned `miner.cpp:96-97`; no restricted-RPC mining, no `generateblocks`, no fixed difficulty, no timestamp steering, no premine). Node B syncs and catches up across non-genesis heights, including one B stop, restart and catch-up while A keeps mining.
- Coinbase maturity on the b=1 output at N=60/61/62: an early spend is natively refused at 60 and succeeds at 61 or later.
- At b=61, walletA pays walletB 1 MEOW cross-peer through the native estimator. Confirm it on both daemons.
- WalletB restores from its private recovery material with explicit height 0, rescans and matches the output and key image. Then at b=71 it spends that received output and the spend is confirmed on both peers.
- Main chain at most 80 blocks, transactions at most 10, zero funding beyond coinbase, the same isolation and loopback rules.
- Unchanged out of scope for F1, recorded NOT_RUN for the next milestone: the Rule8 unlock vectors, the pool/supplement/cache guard routes, projection controls, roots/reorg, foreign differential and backup corruption.

**Source round.** You, from clean b6f54326, in `vanguard/network/` only. One implementation pass and one correction pass, at most 120 minutes from the first edit.
1. Add a separate funded driver and a `funded-two-peer-journey` workload to the controller and grant schema. The accepted genesis driver and its evidence stay byte-unchanged.
2. Signer wallets use an authenticated private signer context for transfers. Never use a restricted wallet for transfer, and never use auth-disable.
3. Reuse the one-shot CLI, redactor, same-connection Digest, retention, inspection and deletion machinery unchanged.
4. Use fixed closed per-row witnesses (heights, txid digests, confirmations, refusal codes) with no secrets.
5. Abort and fail if 80 blocks or the deadline is reached before b=72 is confirmed.
6. Connected source tests with substituted native effects, including the known adverse cases (early spend, wrong-network payment, missing confirmation), plus the full suite, refreeze, commit and an exact packet.
7. Refresh the operator/seed recipe and the item-5 integration-requirement report so they are current when formal Core is submitted.

**Consultations, one at a time.** Platform reviews the source first. Then Core does a source consultation on F1 semantics only: the maturity heights, the native mining route and the no-difficulty/timestamp-manipulation rule. Then Security reviews the signer context, credentials and export. Findings under the per-round bounds are yours to fix. The same finding failing twice comes back to me.

**Grant (Platform, after all three accept).** One runtime-only `--reuse-build` grant on the published retained authority (root from 3eedebc0, digest 1b2815e2…), with a funded budget sized from block count, not threads: about 90 s per block × 80 × 2 + 120.
- Wall 15,000 s = 14,700 work + 300 exclusive cleanup.
- Container unchanged: 2 CPU / 4 GiB / no swap / 256 PIDs, RandomX light mode.
- Host sampled caps: 1 GiB RSS, 4,000 CPU-s, 32 PIDs. Load ≤ 9 at both admissions; 5 GiB / 20 GiB floors; 15 GiB owned disk / 4 GiB abort.
- At least 48 h validity, one attempt, the same first-admission rule, same-run inspection and deletion.
- The runner must be detached (setsid) so a session end cannot kill it, with bounded foreground waits.
- Platform confirms in the grant that no other heavy-lock workload is scheduled during the 4.2 h window. This lead decision does not authorize displacing TJS-1882.

**After F1 PASS.** Reconcile the full matrix, submit formal Core, then Security, then accepted-only lead integration. Remaining adversarial rows become the next milestone or documented limits by Core's ruling.

Core decision 47234b59 (count 2) is unchanged. launch_ready=false; public_launch=false. Needs TJ: None.

