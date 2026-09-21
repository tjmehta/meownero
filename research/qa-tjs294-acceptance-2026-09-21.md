# TJS-294 — QA acceptance of testnet v0 M4 cold backup/restore and payout-wallet restart (TJS-287, 3bc39cb + 93fe9d4)

QA/Release (agent `0b42215e-c278-424b-b68b-7b731047a093`), 2026-09-21. Independent acceptance
of the TJS-287 milestone (operator recovery: cold whole-directory backup and restore of a node
data directory, and a payout wallet closed and reopened across a plain daemon restart and across
the restored daemon) against the exact candidate: recipe extension `3bc39cb` and witness commit
`93fe9d4` on `m1/september-7-verification`. Read-only on every candidate file; no fix applied.
Unlike TJS-278, QA **did execute the packaged journey itself** in a fresh container (§4), because
the shared heavy lock was free, no Meownero worker was live, and the recipe holds the lock for
under a minute. **Agent acceptance, not an external audit; no launch, mainnet, release or FCMP
authority.** Lineage findings route to the wallet specialist on TJS-287.

## 1. Candidate binding (verified on disk before any other work)

| Input | Value | Check |
|---|---|---|
| Repo HEAD | `93fe9d410a689029a3bca1e2c22cccd001443ec3` on `m1/september-7-verification` | equals the issue's `93fe9d4`; `chain/testnet-v0` unchanged between `3bc39cb` and HEAD; worktree clean for every candidate file |
| Report `research/testnet-v0-recover-tjs287-2026-09-21.md` | `4a3582e9f285862faaf101193843ec0e12fafb53712aca9572fb988537ba607b` | committed in `93fe9d4` |
| Evidence `research/evidence/testnet-v0-recover-tjs287-2026-09-21/MANIFEST.sha256` | 119 entries, `26745e83…d94` | `sha256sum -c`: **119 OK** (`manifest-check.txt`) |
| `recover/EVIDENCE.sha256` | 32 entries | **32 OK** in the evidence dir and in `build/testnet-v0-recover-tjs287-run02`; all 33 public files byte-equal between the two (`evidence-check-*.txt`, `evidence-vs-workdir.txt`) |
| `recover/INPUTS.sha256` against the repo | 48 entries | **48 OK** (`inputs-check.txt`); the four new recipe files hash-equal their `3bc39cb` blobs; the accepted TJS-229 manifest `1e3b8a78…` is inside |
| `refusals/MANIFEST.sha256`, `run01-history-order-refused/EVIDENCE.sha256` | 56 / 25 entries | **56 OK / 25 OK** |
| `monerod` / `monero-wallet-rpc` | `b79cb49d…4a2c1` / `5782abee…3a921a` | equal to `launch.py` / `recover.py` pins and `BINARY.sha256`; same bytes as TJS-44/TJS-129/TJS-224/TJS-230 |
| Builder image | `sha256:10a15deb…1c3e` | `launch.py`, both `container-command.json`, `docker image inspect` equal |
| `verify.stdout.json` in the evidence dir | `PASS_RECEIPT_RECONCILIATION` | byte-for-byte equal to QA's own run of `verify-recover.py` on the evidence dir |

Evidence for this acceptance: `research/evidence/qa-tjs294-2026-09-21/` (`MANIFEST.sha256` at
its root; the read-only checks regenerate with `bash research/evidence/qa-tjs294-2026-09-21/collect.sh`
from the repo root; the fresh journey is the documented `recover.py` command in §4).

## 2. Verdict

**PASS — bound to `93fe9d4`.** The M4 claims hold on the retained TJS-287 receipts, are corroborated
by the daemon logs read directly, and reproduce on an independent execution of the same recipe by a
second operator in a new container:

- a node restored from a cold whole-directory backup opens at the backup tip (daemon log
  `last block: 5`), keeps the backup tip header, and rejoins peer 0's tip, header set and
  cumulative work through P2P alone (blocks 6–7 fetched with `NOTIFY_REQUEST_GET_OBJECTS`);
- the payout wallet reopened after a plain restart and after the restored daemon shows the same
  address match, balance, unlocked balance, incoming history and (empty) outgoing history as before,
  with every history txid equal to the canonical header's `miner_tx_hash`.

Scope accepted: finite seven-block empty chain, two loopback peers, native RandomX/DAA, one
disposable wallet RPC, one isolated container. Nothing here is a hot-backup, corrupted-restore,
cross-host, cross-version, CLI-restore, spend-after-restore, pool-restart, 90-second-cadence,
public-testnet or mainnet claim.

## 3. Independent re-derivation (`rederive.py`, 54/54 OK on run02 and on the fresh run)

QA-authored, reads only the public receipts and the three peer 1 stdout logs; does not import the
candidate. Amounts in atomic units (1 MEOW = 10^12).

| Claim | Re-derived from receipts (run02) | Source |
|---|---|---|
| Identical header sets | full dict equality of both peers' 8 headers; `prev_hash` linked 0…7; genesis `20ce111b…` reward 0 v1; every mined block v16, 9 MEOW, 0 txes, not orphan | `headers.json` |
| Cumulative work | difficulties 1,1,1,5,25,127,647,2499; running sum equals `cumulative_difficulty` and `wide_cumulative_difficulty` at every height; total 3,306 = `0xcea` on both peers' `get_info` and in `result.peers` | `headers.json`, `rpc-final.json`, `result.json` |
| Emission | 7 × 9 MEOW = 63,000,000,000,000 = Σ header reward = `emission_amount` on both peers; fees 0; `alt_blocks_count` 0, pool 0, `tx_count` 0, target 90 | `rpc-final.json` |
| Native PoW signature | 7 distinct nonces; `peer0.log` has exactly one `Found block <hash> at height h for difficulty d` per header with equal hash and difficulty; `peer1.log` has no `Found block` | `headers.json`, `peer0.log`, `peer1.log` |
| Payout wallet W | one `block` entry per height 1…5, each txid = `headers[h].miner_tx_hash`, amount 9 MEOW; balance 45,000,000,000,000, unlocked 0 (top < 60); no outgoing/pending/pool/failed; `address_matches` on all three snapshots | `wallet-restart.json`, `headers.json` |
| Wallet across plain restart | `wallet_after == wallet_before`; scanned height 6 → 6 | `wallet-restart.json` |
| Wallet across cold restore | `wallet_after_cold_restore == wallet_before`; scanned height 8 (blocks 6–7 paid to the public fixture, not W) | `wallet-restart.json`, `mining-command.json` |
| Plain restart | exit 0; shutdown tip == payout tip; first readback height 6, top hash `a2ce81d1…`; receipt `stored_tip_at_open` 5; 0 blocks missed; state after == before | `wallet-restart.json` |
| Cold backup | taken from the cleanly stopped restarted peer at tip 5; manifest = `lmdb/data.mdb` 180,224 B, `lmdb/lock.mdb` 8,192 B, `28180/p2pstate.bin` 62 B; archive 204,800 B, sha `072e5352…` = `result.backup_archive_sha256`, under `data/`; directory absent after destroy; restored manifest equal | `cold-restore.json`, `result.json` |
| Offline mining | tip 7 − 5 = 2 = `blocks_missed` = `phases.offline_blocks`; offline tip `6d159c35…` and work `0xcea` on the final chain | `cold-restore.json`, `headers.json` |
| Restore and rejoin | `stored_tip_at_open` 5 = backup height; first readback height 6 with `top_block_hash` = backup tip hash; `state_after_rejoin` == both peers' final state; rejoin 0.613 s = `caught_up − restarted`; timeline backed_up < restored ≤ restarted < caught_up; loopback-only connections; `sync_info.height` 8 | `cold-restore.json` |
| Delivery | peer 1 received only read RPC + `sync_info`; peer 0 write RPC exactly `start_mining` ×2 and `stop_mining` ×2; five owned commands; `peer1-restart` and `peer1-restore` byte-equal to `peer1`; mainnet mode inside the container, loopback binds, exclusive peering; wallet RPC bound to peer 1 with no secret on the command line | `rpc-methods.json`, `process-commands.json` |
| Container | five exits 0; 4 GiB, no swap, 2 CPU, no OOM; 45.0 s; `container.exit` 0, `launcher.exit` 0 | `resources.json` |
| Daemon logs (read directly) | `peer1.stdout.log` / `peer1-restart.stdout.log` / `peer1-restore.stdout.log` open at 0 / 5 / 5; `peer1.log` (shared across the three lives) has three DB opens and three `Deinitializing core`, both offline block hashes appear after the third open, `REORGANIZE` 0, `alternative` 0 | `daemon-log-crosscheck.txt` |

Block timestamps: block 1 at +0, blocks 2–5 at +22 s (RandomX dataset initialisation precedes the
first hash), 6 at +29, 7 at +30; block 1 ≥ peer 0's `start_time`, tip ≤ `adjusted_time` on both
peers, and the restored peer 1's `start_time` is after the tip block, as it must be.

## 4. Operator steps exercised by QA, including a fresh execution

| Step | Result |
|---|---|
| `python3 -B chain/testnet-v0/recover.py --work <fresh> --check-only` | `PASS: accepted recipe manifest, profile, binary, wallet and baseline inputs verified`, exit 0 |
| `python3 -B chain/testnet-v0/test-recover-refusals.py --work build/testnet-v0-recover-qa294-refusals-01` | `PASS: 13 admission refusals and accepted-input control; no nodes started` |
| **`python3 -B chain/testnet-v0/recover.py --work build/testnet-v0-recover-qa294-01`** | lock free, no live worker (`lock-probe.txt`); container `meow-tjs287-2557630`, 45.5 s wall, exit 0/0, five owned exits 0, container removed; `journey-qa294-01.run.txt` |
| `python3 -B chain/testnet-v0/verify-recover.py build/testnet-v0-recover-qa294-01` | `PASS_RECEIPT_RECONCILIATION` (`verify-qa294-01.txt`) |
| `sha256sum -c` on the fresh run's `INPUTS.sha256` / `EVIDENCE.sha256` | 48 OK (pins identical to run02) / 32 OK |
| `rederive.py` on the fresh run | 54/54 OK (`rederive-qa294-01.txt`) |
| Candidate verifier on `run01-history-order-refused` | exit 1 `FAIL: launcher exit` (`verify-run01-negative.txt`) |
| Faithful copy of the 32 public receipts, re-signed | verifier exit 0 |
| Edit without re-signing | `FAIL: changed receipt: wallet-restart.json` |
| Eight one-field tampers, each re-signed (`tamper-refusal.txt`) | `wallet_after_cold_restore` +1 → `payout wallet state differs after a reopen`; `restored_manifest_equal=false` → `destroy and restore witness`; restore `stored_tip_at_open=4` → `restored database opened at the backup tip`; peer 1 tip hash altered → `two identical header sets`; `submit_block` added to peer 1 → `peer1 received a block-injecting or mining RPC`; restore command altered → `restarts must reuse the exact peer1 command`; W history txid altered → `wallet history txid is not the canonical coinbase hash`; one offline block → `blocks mined while destroyed` |

Fresh run versus run02 (`fresh-vs-run02.txt`): same phases, scope, delivery text, process commands,
genesis and profile readback; container command identical except `--name` and the work mount; all
seven mined hashes differ; difficulties 1,1,1,5,26,138,729,2890 (total `0xecf`); rejoin 0.715 s;
backup again three files of 180,224 / 8,192 / 62 bytes in a 204,800-byte archive; wallet heights
6 / 6 / 8; peak memory 2,786,811,904 B; 44.9 s container wall. The fresh run's 33 public files are
retained in `qa294-01/` under this evidence directory; its `data/` (node databases, backup archive,
wallet files) stays in `build/` and is not archived. A base58 grep over both runs' public receipts
finds only the public fixture address `M9Lds8…`; the `seed` hits are RandomX seed-hash and
`pruning_seed` log lines, not wallet material.

## 5. Findings (route to the wallet specialist on TJS-287; none blocks this acceptance)

- **F1 — pinned input still untracked at `93fe9d4` (lineage, repeat of TJS-278 F1).**
  `docs/testnet-v0-freeze-tjs223-2026-09-20.md` is pinned through the accepted TJS-229 manifest
  `1e3b8a78…` (`inputs-git-lineage.txt`) but untracked at HEAD, so a clean checkout of `93fe9d4`
  fails `recover.py` admission with `accepted recipe input differs`. The bytes on this host match
  the pin, so the evidence is bound; a second operator on a clean clone needs the file committed
  or shipped with the package. Previously routed on TJS-230 (comment `803a79fa`); still open.
- **F2 — receipt count in the report.** The report says "34 public receipts pass
  `EVIDENCE.sha256`"; the manifest has 32 entries and the directory 33 files including the
  manifest. Cosmetic.
- **F3 — "no other line changed" between run01 and run02 is not verifiable from retained
  evidence.** Run01's `INPUTS.sha256` pins pre-fix `recover.py` and `verify-recover.py` by hash
  only; the pre-fix files are not retained and not in git. The accepted candidate is `3bc39cb`
  regardless; noted so nobody cites run01 as evidence about the fix's extent.
- **F4 — verifier hardening (optional).** `verify-recover.py` checks the restored peer's first
  readback height range but not that `first_rpc_info_after_restore.top_block_hash` equals
  `tip_at_backup.hash` (the runner checks it live via a header lookup). QA's `rederive.py` checks
  it from the receipts and it holds on both runs. One-line addition if the verifier is revised.
- **F5 — observation.** `peer1.log` carries two `net.http … simple_http_connection_handler`
  ERROR lines per wallet session start and `peer0.log` has `COMMAND_HANDSHAKE invoke failed`
  WARNING lines while peer 1 is down. Both are expected for a wallet connecting to its daemon
  and a peer whose only neighbour is stopped; not defects.
- **F6 — scope note.** The freeze row "Restart node, pool and wallet without lost funds or
  changed tip" also names the pool; TJS-287 covers node and wallet only, so the pool half of that
  row stays open behind F4. The TJS-287 report's "milestone check 4" is the M4 label, not the
  fourth freeze row (which is cross-node payment, accepted on TJS-278).

## 6. Open gates not covered by this candidate

- Hot or partial backups, `mdb_copy`, corrupted or truncated restores, restore onto another host
  or across binary versions.
- CLI wallet restore, wallet file copied to another host, spend after restore, pool payouts and
  pool restart (F6).
- Reorg with transactions (freeze row 6), FCMP, external audit, 90-second steady-state cadence,
  public testnet and mainnet.
- Lineage per F1 until the freeze document is committed.

## 7. What this run did and did not do

QA ran one fresh `recover.py` journey in its own container (`meow-tjs287-2557630`), holding the
shared heavy lock for about 46 s while no other Meownero worker was live, and released it; the
container was removed by the recipe's own cleanup and none remains. No TJS-287 container, daemon
or work directory was reused; `build/testnet-v0-recover-tjs287-run02` was read only. No candidate
file, manifest or Paperclip document of another role was modified. No push, no mainnet, no public
testnet; no seed or key left the container or entered a receipt.
