# TJS-297 — Testnet v0 M5: freeze-document lineage (F1) and F4 pool restart on the launch recipe

Wallet & transport privacy role (agent `fa593b6f-985b-4373-828c-48c27f575077`), 2026-09-21.
Branch `m1/september-7-verification`, starting HEAD `915bb41` (TJS-294 acceptance). Single writer,
no push, no mainnet, no public testnet, no key custody. **Agent-reviewed work, not an external audit;
no launch, release, F4-closure or 90-second-cadence authority.** Evidence directories:
`research/evidence/testnet-v0-lineage-tjs297-2026-09-21/` (F1/F2/F3 receipts, `MANIFEST.sha256` at
its root) and `research/evidence/testnet-v0-pool-restart-tjs297-2026-09-21/` (F4 witness, committed
at `aeb85d5`). The lineage proof below binds to `aeb85d5`; this report and the lineage receipts are
the commit after it, which touches `research/` only. QA/Release re-runs the proof at that hash with
`bash research/evidence/testnet-v0-lineage-tjs297-2026-09-21/lineage-check.sh <hash> <new dir>`.

## 1. Commits in this slice

| Commit | Content | Byte binding |
|---|---|---|
| `5c7af1f` | Tracks `docs/testnet-v0-freeze-tjs223-2026-09-20.md` and `chain/test-network-payment.py` | `46fb2b35…cfec` and `ebac3a52…35f5`, equal to every pin (TJS-229 manifest, M3 attempt-03 `INPUTS.sha256`) |
| `46f74c6` | Tracks `spikes/p2pool/full-source-lock.json` and `spikes/p2pool/meownero-local.patch` | `62354e65…7c3c` and `0b28c5d9…dede6`, equal to the freeze document's exact-baseline table and the TJS-224 binding |
| `46f373a` | Recipe extension: `chain/testnet-v0/pool-restart.py`, `verify-pool-restart.py`, `test-pool-restart-refusals.py`, `pool-restart-journey.md` | committed **before** the first execution so every run's `INPUTS.sha256` resolves to git blobs (see §5, F3) |
| `aeb85d5` | `research/evidence/testnet-v0-pool-restart-tjs297-2026-09-21/` (run01 receipts, refusals, tamper controls, verifier output) | `MANIFEST.sha256` 97 entries |

No accepted recipe file, evidence file, manifest or Paperclip document of another role was modified.
`chain/testnet-v0/README.md` is itself an accepted pinned input and is unchanged; the pool journey is
documented in `pool-restart-journey.md` as the sync and recover extensions were. The other untracked
`spikes/p2pool` harness files belong to the F4 writer and stay untracked.

## 2. F1 — lineage proof from a fresh worktree (`at-aeb85d5/`)

`lineage-check.sh` adds a detached `git worktree` at the commit, confirms it has zero dirty or untracked
entries (`worktree.txt`), then runs `sha256sum -c` on every `INPUTS.sha256`, `MANIFEST.sha256`,
`EVIDENCE.sha256` and `BINARY.sha256` below the M1–M5 and QA evidence directories, `INPUTS` from the
worktree root and the others from their own directory, and checks with `git ls-files --error-unmatch`
that every path pinned by an `INPUTS.sha256` is tracked. It removes the worktree afterwards. Per-manifest
output is in `manifests.tsv` and one `.log` per manifest.

**Result on the two findings QA raised:** zero untracked pinned inputs (`untracked-pins.txt` is empty,
where TJS-278/TJS-294 had listed the freeze document), and every accepted-run manifest verifies from the
clean checkout:

| Milestone | Manifest | Fresh-worktree result |
|---|---|---|
| M1 launch (TJS-229) | `launch/INPUTS.sha256` 43, `launch/EVIDENCE.sha256` 26, `launch/BINARY.sha256` 1, `MANIFEST.sha256` 83, `refusals/MANIFEST.sha256` 52 | all OK |
| M2 sync (TJS-242) | `sync/INPUTS.sha256` 48, `sync/EVIDENCE.sha256` 36, `sync/BINARY.sha256` 1, `MANIFEST.sha256` 124, `refusals/MANIFEST.sha256` 52, `run01-per-ip-refused/EVIDENCE.sha256` 28 and `BINARY.sha256` 1 | all OK |
| M3 payment (TJS-230) | `attempt-03/INPUTS.sha256` 48, `attempt-03/BINARY.sha256` 2, `MANIFEST.sha256` 49, `attempt-01`/`attempt-02` `BINARY.sha256` 2+2, `attempt-01/EVIDENCE.sha256` 6 | all OK |
| M4 recover (TJS-287) | `recover/INPUTS.sha256` 48, `recover/EVIDENCE.sha256` 32, `recover/BINARY.sha256` 2, `MANIFEST.sha256` 119, `refusals/MANIFEST.sha256` 56, `run01-history-order-refused/EVIDENCE.sha256` 25 and `BINARY.sha256` 2 | all OK |
| M5 pool restart (this slice) | `pool-restart/INPUTS.sha256` 50, `pool-restart/EVIDENCE.sha256` 32, `pool-restart/BINARY.sha256` 2, `MANIFEST.sha256` 97, `refusals/MANIFEST.sha256` 56 | all OK |
| QA TJS-278 / TJS-294 | `MANIFEST.sha256` 17 / 60, `qa294-01/INPUTS.sha256` 48, `qa294-01/EVIDENCE.sha256` 32, `qa294-01/BINARY.sha256` 2 | all OK |

`BINARY.sha256` lines are absolute paths into this host's `build/` tree, so they prove the binaries on
this host, not that a clean clone contains them; the recipes take `--binary`/`--pool` for another copy of
the same bytes, as before.

The script's overall verdict is **FAIL** because two classes of manifest cannot verify from any
checkout, and it is right to say so rather than to exclude them:

1. **Refused-attempt `INPUTS.sha256` pinning superseded recipe bytes** (the F3 class, §5): sync
   `run01-per-ip-refused` (3 lines), payment `attempt-01` and `attempt-02` (2 lines each), recover
   `run01-history-order-refused` (2 lines). Every other line of those four manifests is OK.
2. **M3 `attempt-03/EVIDENCE.sha256`, 19 OK and 6 missing**: `peer0.conf`, `peer0.log`,
   `peer0.stdout.log`, `peer1.conf`, `peer1.log`, `peer1.stdout.log`. The TJS-230 report states that
   the large daemon logs stay in the build directory; they are 26.5 MB together, still present in
   `build/testnet-v0-payment-tjs230-03`, and still hash-equal to the manifest
   (`m3-attempt-03-build-only-receipts.txt`, 6 OK). They are not added to the repository here.

Neither class involves an untracked *input*; both are receipts of runs that were either refused or
accepted with the exception already documented. The accepted M1–M5 lineage is reproducible from a clean
checkout of `aeb85d5` plus the two pinned binaries.

## 3. F4 — pool restart witness (`testnet-v0-pool-restart-tjs297-2026-09-21/`)

The pinned image has a pool component runnable in isolation, so this slice did not stop at F1. The
TJS-187 candidate `p2pool` (`bbc3240607bf40bd3db7e13f011ccf9eda431dddd751918a3ebf4e3aaf129fad`, rebuilt
byte-identically in TJS-224 from `full-source-lock.json` and `meownero-local.patch`) executes in the
accepted builder image `sha256:10a15deb…1c3e` with every shared library resolved. `pool-restart.py`
admits it only with that hash and only when the two pinned source inputs are hash-equal, alongside the
unchanged TJS-229 admission (accepted recipe manifest `1e3b8a78…`, profile, daemon binary, 43 inputs).

Journey (run01, container `meow-tjs297-*`, 41.3 s container wall, container and launcher exit 0, all
four owned processes exit 0, peak memory 3,342,471,168 B under the 4 GiB cap, no OOM, container removed):

| Seam | Witness | Receipt |
|---|---|---|
| Chain before the pool | peer 0 mines 4 blocks natively; peer 1 converges via P2P | `headers.json`, `run.log` |
| Attach at the common tip | pool starts on peer 1 (light mode, no miner, no cache, no DNS, loopback listeners, JSON data API); first stratum job 1.31 s after start has `height` 5 and the 32-byte previous id in its hashing blob equals tip 4's hash; `network/stats` reports the same hash, height and difficulty; `totalBlocksFound` 0 | `pool-restart.json: attach` |
| Follow live blocks | peer 0 mines 2 more (tip 6) while the pool runs; the pool reaches them only through peer 1's ZMQ feed and RPC; a fresh login shows job height 7 on tip 6's hash | `pool-restart.json: live` |
| Stop, mine on, restart | SIGTERM → pool exit 0 at tip 6; peer 0 mines 2 blocks with the pool down (tip 8, both peers converged); pool restarts with the byte-identical command on the same data directory; first job 1.20 s after restart has height 9 on tip 8's hash; API agrees; `blocks_missed` 2 | `pool-restart.json: resumed`, `process-commands.json` |
| Delivery | peer 1 received only read RPC from the runner; peer 0's write RPC was exactly `start_mining` ×3 and `stop_mining` ×3; peer 0 logs eight `Found block` lines, peer 1 none; `pool.log` has no `BLOCK FOUND` and no `submit_block`; the only base58 address in any receipt is the public fixture | `rpc-methods.json`, `peer0.log`, `pool.log`, `address-privacy-grep.txt` |
| Commands | peer 0 runs the exact recipe v1 command; peer 1 differs only in `--no-zmq` → `--zmq-rpc-bind-ip 127.0.0.1 --zmq-rpc-bind-port 28182 --zmq-pub tcp://127.0.0.1:28183`; the verifier compares both token for token | `process-commands.json` |

Difficulties 1,1,1,5,26,138,666,3010,13846; emission 8 × 9 MEOW; fees 0; identical header sets on both
peers. `verify-pool-restart.py` → `PASS_RECEIPT_RECONCILIATION` (`verify.stdout.json`); `INPUTS.sha256`
50 OK; `EVIDENCE.sha256` 32 OK; `test-pool-restart-refusals.py` → 13 refusals (ten profile fields, stale
directory, wrong daemon binary, wrong pool binary) plus the accepted-input control (`refusals/`).
Negative controls on re-signed copies (`tamper-refusal.json`): faithful copy passes; job height −1 and
job previous id set to the pre-restart tip → `resumed: job is not on the common tip`; API tip left at the
pre-restart tip → `resumed: pool API tip`; `totalBlocksFound` 1 → `resumed: pool found blocks`; pool exit
1 → `pool stopped cleanly at the live tip`; `blocks_missed` 0 → `blocks mined while the pool was down`;
restart command with one extra flag → `restart must reuse the exact pool command`; `--start-mining` added
→ `pool must not mine…`; `submit_block` counted on peer 1 → `peer1 received a block-injecting or mining
RPC`; peer 1 back on `--no-zmq` → `daemons must run the exact recipe commands`; edited without re-signing
→ refused at the manifest.

**Scope of the claim.** The pool process restarts against a running two-peer chain and resumes serving
work at the tip both daemons share, with no miner connected and no sidechain peer. This is the pool half
of the freeze row "restart node, pool and wallet without lost funds or changed tip" as an operator-recovery
check. It is not share acceptance, PPLNS accounting, a pool payout, a restart with a populated sidechain
cache, a pool reorg, a restart under load, F4 closure, or any 90-second-cadence, public-testnet or mainnet
claim; those remain with TJS-187/TJS-224 and the freeze document's open gates. The recipe profile keeps
`pool_enabled: false` for the daemon launch; the pool is a separately pinned component attached to peer 1
and the journey document says so.

## 4. F2 — receipt count (`f2-receipt-count.txt`)

The TJS-287 report line "34 public receipts pass `EVIDENCE.sha256`" is a miscount. `recover/EVIDENCE.sha256`
has 32 entries; the evidence directory and `build/testnet-v0-recover-tjs287-run02` each hold 33 public files
including the manifest itself. The accepted evidence is unchanged; the correct statement is **32 receipts +
the manifest**. The TJS-287 report is left as accepted history; this report supersedes that one line.

## 5. F3 — what is derivable about run01 → run02 (`refused-attempt-pins.txt`)

The claim "no other line changed" between TJS-287 run01 and run02 is **not derivable** from retained
evidence, and the same holds for the sync and payment refused attempts. `refused-attempt-pins.txt`
re-derives, for each refused attempt against its accepted run: the set of differing `INPUTS.sha256` lines
(recover run01: exactly `recover.py` and `verify-recover.py`, 2 of 48; payment attempt-01/02: `payment.py`
and `payment-journey.md`, 2 of 48; sync run01: `sync.py`, `verify-sync.py`, `sync-journey.md`, 3 of 48),
and, for every superseded pin, a search over all 1,354 blobs in the object store (reachable and
unreachable, `git cat-file --batch-all-objects`) plus a bounded search of `build/`, scratch and run
directories: **none of the seven pre-fix byte strings exists anywhere**. What can be said is therefore:
"between run01 and run02 exactly these recipe files changed, by hash", and the refused attempts' own
receipts show why each was refused. Nothing more precise can be cited, and the TJS-287 line should be read
that way. The accepted candidates (`1887fa6`, `86226ae`, `3bc39cb`) are unaffected.

Durable fix applied in this slice: the pool recipe was committed (`46f373a`) before its first execution,
so any future refused run's `INPUTS.sha256` pins resolve to git blobs and a line-level diff is derivable.
This is the convention to follow for further extensions: commit the recipe, then run.

## 6. Handoff to QA/Release

Candidate for acceptance: recipe `46f373a`, witness `aeb85d5`, lineage proof and this report in the
commit after `aeb85d5` on `m1/september-7-verification` (hash in the Paperclip comment). Suggested checks:
`lineage-check.sh` at the report commit (expect the same 40-manifest table with only the eight
documented FAIL lines); `sha256sum -c` on the two new `MANIFEST.sha256` files; `verify-pool-restart.py`
on `pool-restart/`; and, if the heavy lock is free and no worker is live, a fresh
`python3 -B chain/testnet-v0/pool-restart.py --work build/<new>` (about one minute, holds the lock for
that long) followed by the verifier.

## 7. What this run did and did not do

One fresh `pool-restart.py` journey in its own container, holding the shared heavy lock for about 45 s
while no other Meownero worker was live (lock probe and `pgrep` before launch); the container was removed
by the recipe's own cleanup. No M2–M4 daemon, container or work directory was reused or modified;
`build/testnet-v0-payment-tjs230-03` and `build/testnet-v0-recover-tjs287-run02` were read only. One
temporary worktree was added and removed. No push, no mainnet, no public testnet; no seed or key exists in
this journey and none entered a receipt.
