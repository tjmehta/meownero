Lead decision, TJ may reverse: stop chasing the interactive prompt and switch the wallet CLI steps to pinned native one-shot command mode.

**What the skeleton shows.** The producer got through the mining question (answered no), "Refresh done, blocks received: 0", the account listing and "Background refresh thread started". After that it printed no prompt within 25 s. At pinned e151643c:
- `simple_wallet::run()` (simplewallet.cpp:9082-9093) starts the idle/auto-refresh thread, then enters `run_handling(get_prompt)`.
- `get_prompt()` (9068-9080) calls `check_connection()` and `is_synced()`, which take `m_daemon_rpc_mutex` (wallet2.cpp:6667) with a 200 s default timeout (wallet2.h:769). That mutex is shared with the refresh thread that just started.

So producer-side blocking before the first prompt is a plausible explanation, not a proven one. This is the third failure at the same gate. Under the second-attempt rule the shared premise was that the interactive readline main loop is a dependable control surface, so I am removing that dependency instead of tuning it.

**The supported alternative is already in pinned source.**
- With positional commands, `main` calls `w.init(vm)` then `process_command(command)`, `stop()` and `deinit()`, and never calls `run()` (simplewallet.cpp:10380-10387).
- `skip_check_backround_mining` skips the mining question (4537-4539).
- `deinit()` → `close_wallet()` stores the wallet (4671-4676, 5224).

No readline main loop, no idle refresh thread and no startup prompt are involved.

**Scope.** You, from clean 200955e7, in `vanguard/network/` only. One implementation pass and one correction pass, at most 60 minutes from the first edit. The frozen-driver exception covers only `cli()`/`expect()` and their direct tests and anchors.
1. Run each existing command as its own one-shot native invocation, sequentially, with the same argv base (`--testnet --config-file --password-file --daemon-address --log-file`, plus `--generate-new-wallet … --mnemonic-language English` on the first call and `--wallet-file` afterwards):
   1. `set refresh-from-block-height 0` at creation
   2. `address new`
   3. `refresh 0`
   4. `save`
   5. then, in a fresh process, `set`

   Require `refresh-from-block-height = 0` from that fresh-process readback. Do the same for the reopen path.
2. Each invocation must exit 0. Verify the PID is gone, the listener is absent and the wallet file is released before the next one starts. The only interactive input allowed is the existing exact `Wallet password: ` answer, bounded per invocation. Any `[y/N]`, `[Y/n]`, confirm, unknown, repeated or extra prompt still refuses. Remove the now-unreachable startup-prompt and mining-answer paths. Keep the redacted skeleton on failure.
3. The commands, password and credential handling, rows, assertions, normalizer, redactor, export codes and schema are unchanged, as are the wallet-RPC, denial and rotation paths.
4. **Controls.**
   - A PTY fixture CLI implementing the pinned one-shot semantics passes.
   - Known-bad 200955e7 times out against a fixture that never prints the interactive prompt.
   - A nonzero exit, an extra prompt or a missing readback fails.
   - The existing redactor, daemon, auth and rotation controls stay green.
   - Cite the pinned line numbers above in the audit.

**Review.** Platform first, then Security (the PTY and password handling flow changed). Core consultation is not needed, because the same native setter, store and separate-reopen getter that Core endorsed are used. Formal Core still reviews the final candidate. Findings under the per-round bounds are yours to fix. The same finding failing twice comes back to me.

**Then.** One fresh 900 s `--reuse-build` grant on the published retained authority (root from 3eedebc0, digest 1b2815e2…), with all existing conditions. If a wallet step fails natively again, post the skeleton plus the step and exit code, and return to me. No blind patch. d00daf5a and all earlier grants stay consumed.

Core decision 47234b59 (count 2) is unchanged. Native ATTEMPTED_FAIL with 9 of 16 functional rows PASS; launch_ready=false; public_launch=false. Needs TJ: None.
