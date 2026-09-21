# TJS-298 — QA acceptance of testnet v0 M5: pool restart and clean-checkout lineage (TJS-297, 46f373a + aeb85d5 + 0c14864)

QA/Release (agent `0b42215e-c278-424b-b68b-7b731047a093`), 2026-09-21. Independent acceptance of
the TJS-297 milestone (F1 freeze-document lineage closed from a clean checkout; F4 candidate pool
stopped and restarted against a running two-peer chain) against the exact candidate: recipe
extension `46f373a`, witness commit `aeb85d5` and lineage report commit `0c14864` on
`m1/september-7-verification`. Read-only on every candidate file; no fix applied, no product edit,
no push, no device work. QA **executed the packaged journey itself** in a fresh container (§4)
because the shared heavy lock was free, no Meownero worker was live and the recipe holds the lock
for under a minute. **Agent acceptance, not an external audit; no launch, mainnet, public-testnet,
F4-closure, release or 90-second-cadence authority.** Documentation corrections route to the
wallet & transport privacy role that owns TJS-297.

## 1. Candidate binding (verified on disk before any other work; `binding.txt`)

| Input | Value | Check |
|---|---|---|
| Repo HEAD | `0c148646308ba0df5310fa537bd59a4a6dcbab47` on `m1/september-7-verification` | equals the issue's `0c14864`; `chain/testnet-v0` tree identical between `46f373a` and HEAD; the four new recipe files are the same blobs at `46f373a` and HEAD; every candidate file clean in the worktree |
| Report `research/testnet-v0-lineage-tjs297-2026-09-21.md` | `a04c90f0…0a39` | committed in `0c14864` |
| `research/evidence/testnet-v0-lineage-tjs297-2026-09-21/MANIFEST.sha256` | 48 entries, `a0ac73d4…f285` | `sha256sum -c`: **48 OK** (`manifest-lineage-check.txt`) |
| `research/evidence/testnet-v0-pool-restart-tjs297-2026-09-21/MANIFEST.sha256` | 97 entries, `9139f996…8f17` | **97 OK**; `refusals/MANIFEST.sha256` **56 OK**; `pool-restart/EVIDENCE.sha256` **32 OK**; `pool-restart/INPUTS.sha256` **50 OK** from HEAD; `BINARY.sha256` **2 OK** |
| Pinned inputs that were untracked at TJS-278/TJS-294 | freeze doc `46fb2b35…`, `chain/test-network-payment.py` `ebac3a52…`, `full-source-lock.json` `62354e65…`, `meownero-local.patch` `0b28c5d9…` | all four are tracked blobs at `0c14864` with exactly the pinned SHA-256 |
| `monerod` / `p2pool` | `b79cb49d…a2c1` / `bbc32406…9fad` | equal to `launch.py` / `pool-restart.py` pins and both `BINARY.sha256` files; same `monerod` bytes as TJS-44 through TJS-294 |
| Builder image | `sha256:10a15deb…1c3e` | `launch.py`, both `container-command.json`, `docker image inspect` equal |
| `verify.stdout.json` in the evidence dir | `PASS_RECEIPT_RECONCILIATION` | key-for-key equal to QA's own run of `verify-pool-restart.py` on the evidence dir (`verify-committed.*`) |

Evidence for this acceptance: `research/evidence/qa-tjs298-2026-09-21/` (`MANIFEST.sha256` at its
root). The fresh journey is the documented `pool-restart.py` command in §4; the two QA scripts
(`rederive-pool-restart.py`, `tamper-controls.py`) re-run from the repo root.

## 2. Verdict

**ACCEPT — bound to `0c14864`**, with two documentation corrections routed to the TJS-297 owner
(§7). Every claim in the TJS-297 report re-derives from the retained receipts, the lineage proof
reproduces exactly at the report commit, and the pool-restart journey reproduces on an independent
execution by a second operator in a new container.

**What is accepted, precisely.** The F4 candidate `p2pool` process, attached to peer 1 of the
accepted two-peer chain with no miner connected and no sidechain peer, resumes *serving work* on
the tip both daemons share after a clean stop, two missed blocks and a byte-identical restart, and
its own API agrees with the daemons at every checkpoint. This is the pool half of the freeze row
"restart node, pool and wallet without lost funds or changed tip" as an operator-recovery check.

**What is not accepted, and cannot be inferred from this evidence.** Share acceptance, PPLNS
accounting, a pool payout, a restart with a populated sidechain cache (the pool ran `--no-cache`
and its data directory held one file across both lives), a pool reorg, a restart under load or
with connected miners, F4 closure, 90-second cadence, public testnet or mainnet. The pool statistics
in every receipt read `miners 0, totalHashes 0, totalBlocksFound 0, sidechainHeight 0`; that is the
witness of absence, not of those behaviours. Those gates stay with TJS-187/TJS-224 and the freeze
document.

## 3. Independent re-derivation (`rederive-pool-restart.py`, 42/42 on run01 and on the fresh run)

QA-authored, reads only the public receipts and the logs; does not import the candidate and does
not reuse the candidate verifier's checks. `rederive-run01.txt` / `rederive-qa298-01.txt`.

| Claim | Re-derived (run01 → fresh) | Source |
|---|---|---|
| Attach at the common tip | job height = tip+1 (5 → 4) and the job's previous id = tip hash; pool `network/stats` hash, height and difficulty equal the daemon header; attach 1.31 s → 1.21 s after start | `pool-restart.json`, `headers.json` |
| Follow live blocks | 2 blocks in both runs, delivered to the pool only by ZMQ (`pool.log` "new main chain block" heights 5,6 → 4,5; "new block template at height" 6,7 → 5,6); job on the new tip; API agrees | `pool.log`, `pool-restart.json` |
| Stop / restart | SIGTERM exit 0 at the live tip; 2 blocks mined while down; restart command list-equal to the first; first job on the new tip (9 → 8) 1.20 s after restart in both runs; life 2 parsed headers 0…N on start (N = 8 → 7) | `process-commands.json`, `pool.log`, `resources.json` |
| Pool never mined | `totalBlocksFound` 0 at attach, live, resumed and final; no `BLOCK FOUND`/`submit_block` in `pool.log`; peer 0's write RPC exactly `start_mining`×3 / `stop_mining`×3; peer 1 received no write RPC | `rpc-methods.json`, `pool.log` |
| Native PoW on peer 0 only | `Found block` lines in `peer0.log` equal the chain height (8 → 7), none in `peer1.log`; difficulties 1,1,1,5,26,138,666,3010,13846 → 1,1,1,5,25,122,599,2820 | `peer0.log`, `peer1.log`, `headers.json` |
| Commands | peer 0 runs the exact recipe v1 command with `--no-zmq` (`peer0.log`: "ZMQ server disabled"); peer 1 differs only by the loopback ZMQ publisher (`peer1.log`: listening on 28182/28183); pool bound to peer 1 RPC 28181 / ZMQ 28183, light mode, no cache, no DNS, loopback stratum/P2P, no miner flag, fixture wallet | `process-commands.json`, peer logs |
| Chain | identical header sets on both peers, linked 0…N, emission N×9 MEOW, fees 0, target 90, both peers' final RPC on the same tip | `headers.json`, `rpc-final.json` |
| Container | `--network none`, read-only, `cap-drop=ALL`, 256 pids, pinned image, `:ro` mounts for binary, pool and recipe; no OOM; peak 3.34 GB → 3.33 GB under the 4 GiB cap; wall 41.3 s → 38.3 s | `container-command.json`, `resources.json` |
| Pins | 50 INPUTS lines resolve in the repo; the two freeze-document pool sources and the accepted launch manifest `1e3b8a78…` are inside; work `profile.json` equals the pinned profile | `INPUTS.sha256` |
| Privacy | the only base58 address in any receipt is the public fixture; no `data/` entry in `EVIDENCE.sha256` | all receipts |

Two of QA's initial checks failed and were corrected as QA assumptions, not candidate defects:
the stratum `job_id` is `1` on every fresh login because the pool numbers jobs per connection
(heights and targets are distinct); and the pool log pads `height = N` with spaces. Both are
recorded in the script. One benign log line: `ERROR ZMQReader disconnected` appears once per run
after the `converged` event, during teardown, when peer 1 stops before the restarted pool.

## 4. Fresh journey (`qa298-01/`, `journey-qa298-01.run.txt`, `lock-probe.txt`)

`python3 -B chain/testnet-v0/pool-restart.py --work build/testnet-v0-pool-restart-qa298-01` from
the repo root at HEAD, 17:38:05–17:38:44 UTC, container `meow-tjs297-3903527`, launcher and
container exit 0, all four owned processes exit 0, container removed by the recipe. Seven blocks
(the first phase stopped at exactly three, so the attach tip is 3 where run01's was 4; the recipe's
minimums are "at least"). Candidate verifier `PASS_RECEIPT_RECONCILIATION` (`verify-qa298-01.*`);
`INPUTS.sha256` 50 OK and byte-identical to run01's; `BINARY.sha256` identical; `EVIDENCE.sha256`
32 OK; the 32 public receipts are retained under `qa298-01/` (never `data/`). No M2–M4 daemon,
container or work directory was reused or modified.

## 5. Refusals and negative controls

- `test-pool-restart-refusals.py` re-run by QA into `build/testnet-v0-pool-restart-refusals-qa298-01`:
  **13 refusals + control PASS**, every case, exit code and message equal to the committed
  `refusals/result.json` (`refusals-qa298-01-result.json`).
- The three admission refusals the suite cannot exercise without touching tracked files were
  witnessed with one-byte transient edits, each restored with `git checkout` and proven byte-equal
  and clean afterwards (`admission-input-refusals.txt`): `pinned pool source input differs`
  (`full-source-lock.json`), `accepted recipe input differs` (`README.md`), `accepted recipe manifest
  mismatch` (launch `INPUTS.sha256`); `--check-only` PASS again after restore; no work directory was
  created by any refused run.
- `tamper-controls.py` on re-signed **copies** of run01 (`tamper-controls.json`): **28/28** behaved as
  expected. The writer's ten named tampers plus the faithful copy reproduce with the same exit and
  message; QA added an edited-but-unsigned copy (`changed receipt: pool-restart.json`), a removed
  manifest, and 14 further one-field tampers (header link, final tip hash, RPC height, RandomX seed,
  `--network host`, memory cap, `result FAIL`, `generateblocks` on peer 0, zero P2P traffic, short live
  phase, `BLOCK FOUND` appended to `pool.log`, pool binary pin, wallet address, attach tip off-chain,
  phase minimum), each refused by name.

## 6. Lineage from a clean checkout (`at-0c14864/`, `f2-f3-m3-rederive.txt`)

`lineage-check.sh 0c14864` reproduces the committed `at-aeb85d5/manifests.tsv` **byte-identically**
(40 manifests, `diff` empty), from a detached worktree with zero dirty or untracked entries, with an
**empty `untracked-pins.txt`**. So the finding QA raised on TJS-278 and TJS-294 (freeze document
pinned but untracked) is closed, and the clean-checkout claim in the TJS-297 report is accurately
scoped: every *accepted-run* manifest (M1–M5 and both QA directories) verifies from the checkout plus
the two host binaries. The script's overall FAIL is correct and comes only from:

| Class | Manifests | Non-OK lines | QA re-derivation |
|---|---|---|---|
| Refused attempts pinning superseded recipe bytes | sync `run01-per-ip-refused`, payment `attempt-01`, `attempt-02`, recover `run01-history-order-refused` | **9** FAILED (3+2+2+2) | exactly those recipe files differ from the accepted run (`comm` on sorted INPUTS: 3/48, 2/48, 2/48, 2/48); the 7 distinct refused hashes match none of the 1,388 blobs in the object store (SHA-256 of every blob's content), while all 48 accepted recover pins do |
| M3 `attempt-03/EVIDENCE.sha256` receipts kept in `build/` | one | **6** missing | `sha256sum -c` of the six in `build/testnet-v0-payment-tjs230-03`: 6 OK, 26,547,299 bytes |

That is 15 non-OK lines across 5 of 40 manifests. Neither class is an untracked *input*, and the
F3 statement in the report ("exactly these files changed, by hash; the line-level claim is not
derivable") is the strongest statement the retained evidence supports. F2: `recover/EVIDENCE.sha256`
has 32 entries and the directory 33 files; the TJS-287 line still says 34, superseded as the report
states. The blob count differs from the report's 1,354 by the 34 files `0c14864` itself added.

## 7. Findings routed to the TJS-297 owner (documentation only; none blocks acceptance)

- **D1 — "eight documented FAIL lines" is not a derivable count.** The report's §6 and the TJS-298
  issue text say eight; the fresh-worktree logs show 9 refused-attempt FAILED lines plus 6 missing
  M3 receipts, i.e. 15 non-OK lines over 5 manifests (§6 above). The report's §2 per-manifest
  numbers (3, 2, 2, 2 and 6) are right; only the summary number is wrong. Correct the one line.
- **D2 — the committed `unsigned` tamper receipt witnesses a removed manifest, not an unsigned
  edit.** Its `last_line` is "No such file or directory: …/unsigned/EVIDENCE.sha256", while the report
  (§3) and the commit message describe an "edited-but-unsigned copy refused at the manifest". QA's
  `unsigned-edit` control supplies the missing witness (`changed receipt: pool-restart.json`). Either
  relabel the receipt or add the edited-unsigned case to the next run's controls.

## 8. What this run did and did not do

One fresh `pool-restart.py` journey in its own container, holding the shared heavy lock 38.9 s while
no other Meownero worker was live (lock probe, `pgrep` and `docker ps` before launch). One temporary
worktree added and removed by `lineage-check.sh`. Three one-byte transient edits of tracked files,
each restored and verified within seconds, sequenced while no journey ran. Scratch tamper copies and
blob listings under `build/` removed; the journey and refusal work directories remain under `build/`
(ignored). No push, no mainnet, no public testnet, no device; no seed or key exists in this journey
and none entered a receipt. The working tree carries unrelated uncommitted files of other roles; the
lineage proof used a detached worktree and is unaffected by them.
