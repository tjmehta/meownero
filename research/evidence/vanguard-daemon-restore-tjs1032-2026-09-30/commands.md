# TJS-1032 command and exit ledger

All reproduction commands ran from a separate detached checkout at
`40be047b6ed89745c94d22b3a36537b138bc91ee`. Its path during this run was
`<agent-scratch>`.
The checkout's `build/` directory was private to this run. Commands below
completed with exit 0 unless explicitly marked as an expected rejection.

| Command | Result |
| --- | --- |
| `git worktree add --detach <qa-checkout> 40be047b6ed89745c94d22b3a36537b138bc91ee` | 0; detached at exact evidence commit |
| `sha256sum MANIFEST.sha256` in committed TJS-1010 bundle | 0; `24b4ecdb2bac9f4b4114e1745632ce1dcb89217c917684c7a735b618a8f1ac2a` |
| `sha256sum -c MANIFEST.sha256` in committed TJS-1010 bundle | 0; all 33 entries OK |
| `python3 -B vanguard/verify-daemon-restore.py research/evidence/vanguard-daemon-restore-tjs1010-2026-09-29` | 0; `PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION` |
| `mkdir -p build/vanguard-src && cp -a --reflink=auto <TJS-990-worktree>/build/vanguard-src/. build/vanguard-src/ && rm -rf build/vanguard-src/monero-fcmp/build/vanguard && mkdir -p build/vanguard-src/monero-fcmp/build/vanguard` | Tool rejected before execution because it contained `rm -rf`; no filesystem mutation |
| `rsync -a --exclude '/monero-fcmp/build/vanguard/' <TJS-990-worktree>/build/vanguard-src/ build/vanguard-src/` | 0; copied pinned prepared source and offline Cargo cache, excluded the prior build directory |
| `git -C build/vanguard-src/monero-fcmp rev-parse HEAD` | 0; `e151643c5269c83bf24a83b2548e2493876026b2` |
| `sha256sum build/vanguard-src/monero-fcmp/src/fcmp_pp/fcmp_pp_rust/Cargo.lock` | 0; `6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239` |
| `git -C build/vanguard-src/monero-fcmp diff --name-only HEAD` | 0; only the established `tests/CMakeLists.txt` harness injection |
| `git diff --exit-code 9057e7bc220b5b690e978b69f3dcb583402807ce 40be047b6ed89745c94d22b3a36537b138bc91ee -- vanguard` | 0; no code changes in evidence commit |
| Network-disabled CMake command below | 0; `configure.log` ends in `Configuring done` and `Generating done` |
| `python3 -B vanguard/run-daemon-p2p.py --scenario restore --src build/vanguard-src --out build/tjs1032/exact01 --runs 2` | 0; source build 1433.239 s, run1 66.857 s, run2 70.661 s; writer verifier PASS |
| `sha256sum build/vanguard-src/monero-fcmp/build/vanguard/bin/monerod build/vanguard-src/monero-fcmp/build/vanguard/bin/monero-wallet-rpc` | 0; hashes in report and `bundle/receipt.json` |
| `sha256sum -c MANIFEST.sha256` in copied QA restore bundle | 0; all 33 entries OK |
| `python3 -B vanguard/verify-daemon-restore.py research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/bundle` | 0; `PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION` |
| `python3 -B research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/compare.py <writer-bundle> <qa-bundle> research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/comparison.json` | 0; `PASS_TJS1032_FOUR_RUN_SEMANTIC_COMPARISON` |
| `python3 -B research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/tamper.py <writer-bundle> research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/tamper-results.json` | 0; `PASS_TJS1032_TAMPER_CONTROLS_AND_VERIFIER_GAPS` |
| `python3 -B vanguard/test-daemon-p2p-refusals.py` | 0; `PASS_DAEMON_P2P_HASH_CONSISTENT_REFUSAL` on committed P2P evidence |
| `python3 -B vanguard/run-daemon-p2p.py --scenario p2p --src build/vanguard-src --out build/tjs1032/p2p-step0 --runs 1` | 0; `PASS_DAEMON_P2P_RECEIPT_RECONCILIATION` |
| `sha256sum -c MANIFEST.sha256` in copied QA P2P bundle | 0; all 25 entries OK |
| `python3 -B vanguard/verify-daemon-p2p.py research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/p2p-step0` | 0; `PASS_DAEMON_P2P_RECEIPT_RECONCILIATION` |
| `python3 -B vanguard/test-daemon-p2p-refusals.py research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/p2p-step0` | 0; `PASS_DAEMON_P2P_HASH_CONSISTENT_REFUSAL` |

The exact `docker run` argument arrays for the source build, both restore trials,
and the extra P2P trial are in `bundle/receipt.json` and `p2p-step0/receipt.json`.
Each uses `--pull=never --network=none --cap-drop=ALL
--security-opt=no-new-privileges --cpus=2 --memory=4g --memory-swap=4g
--pids-limit=256 --ulimit core=0`; all stages exited 0. The source build was
clean because the copied `build/vanguard` directory was excluded before CMake.

## Exact CMake command

The following was run from the detached checkout, with its current directory as
`$PWD`, before the runner:

```sh
docker run --rm --pull=never --network=none --cap-drop=ALL --security-opt=no-new-privileges --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 --ulimit core=0 -u "$(id -u):$(id -g)" -v "$PWD/build/vanguard-src/monero-fcmp:/src" -v "$PWD/build/vanguard-src/cargo-home:/cargo-home" -v "$HOME/.rustup/toolchains/stable-x86_64-unknown-linux-gnu:/opt/rust:ro" -e CARGO_HOME=/cargo-home -e CARGO_NET_OFFLINE=true -e PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin -w /src/build/vanguard sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e bash -euc 'cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON ../.. > /src/build/vanguard/qa-cmake.log 2>&1'
```

## Intentional verifier failures and false passes

`tamper.py` runs four exact mutations against a temporary copy of the committed
bundle. The first two are the required refusal controls. The latter two expose
coverage gaps. `tamper-results.json` records each verifier exit and final error.

| Mutation | Verifier result |
| --- | --- |
| Rehash manifest after changing `receipt.json` exact-commit source hash | exit 1, `exact-commit source mismatch` (expected refusal) |
| Add a byte to `run1/public/result.json`, leave manifest unchanged | exit 1, `manifest mismatch` (expected refusal) |
| Rehash manifest after replacing `receipt.json` `binary.monerod.sha256` with zeros | exit 0, PASS (unexpected acceptance) |
| Rehash manifest after changing one daemon's confirmed tip in result and matching event | exit 0, PASS (unexpected acceptance) |

The two nonzero exits above are successful negative tests. No command failed
unexpectedly.
