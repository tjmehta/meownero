# Sequential native wallet commands

Authority: answered lead interaction e50340c0-206d-4c17-aff0-6575c72e24ac,
readline_startup_next_scope, lead8f050fb0/run0b8bd23b, resolved2026-11-04T22:49:36Z.
Report0c70efac-9fe6-4d2b-a6ce-6ab50b84a1f3. The assigned writer authenticated
this answer and adopted it by description-only PATCH. Baseline200955e76942d1f4971030505de74e0e047c7b75,
treef014378b70a97328cd2c1a2ebebab72f77825ffe. One implementation plus one correction
pass, <=3600s from the first edit recorded in implementation-budget.json.
Owned paths: vanguard/network/. No native operation is authorized by this packet.

## Observable outcome and limits

Remove reliance on the interactive readline main loop. Creation invokes, in order,
five separate processes: set refresh-from-block-height 0; address new; refresh 0;
save; set. Only the setter uses --generate-new-wallet and --mnemonic-language
English. Every later process uses --wallet-file. The existing reopen path already
contains only the getter, so it remains a fresh set process; it does not provision
another subaddress or change the saved wallet. The unchanged wallet_controls caller
repeats that reopen after wallet RPC stops. Both creation and reopen require the
existing exact height-zero readback assertion.

The same --testnet/config-file/password-file/daemon-address/log-file argv base and
password file handling remain. Each invocation has a new echo-disabled PTY and a
bounded25s read/exit loop under the existing outer runtime deadline. EOF or Linux
PTY EIO means the slave closed: reap the child, require exit0, require PID absent,
check the wallet-RPC listener at daemon_port+2 is absent, and run the existing
inode-based released(root) check before launching the next command. Failure of
any guard stops the sequence. All commands are positional argv; no command or
exit string is written to stdin. The sole stdin write is the existing exact
Wallet password: answer, at most once per invocation. Confirmation variants and
other password requests fail immediately; unrecognized input requests receive no
answer and hit the bounded timeout. Ordinary colon-bearing output can span PTY
reads without being mistaken for a prompt. Normalizer and redactor are byte-exact
with200955e7. Startup-wallet-prompt recognition and negative mining input are gone.

The existing failure cleanup reaps a live owned CLI, closes its PTY and retains
the private transcript; the unchanged _cli_skeleton boundary runs on every cli
exception. Private exception notes retain exit status and command label in the
existing expected_prompt field; no note enters the public diagnostic schema.
The observer's MAIN_STEPS/WALLET_STEPS and dependent test line move by-12 only.
All public codes, row witnesses, assertions outside the obsolete interactive
prompt guard, RPC/daemon/auth/denial/rotation paths remain unchanged. The old
CLI exited before expected prompt label remains in the closed code vocabulary.
The existing exit0, PID-absence, repeated-password and height assertions remain.

## Pinned source audit

All citations bind upstream e151643c5269c83bf24a83b2548e2493876026b2 Git objects,
not a newer upstream or private native output. The packet includes these sources.

| Contract | Pinned simplewallet.cpp source |
| --- | --- |
| Positional commands | arg_command:180, registration10337 and positional_options10352. main10376-10387: init -> process_command -> stop -> deinit for a nonempty command. The interactive run branch begins10388. |
| No mining question | 4537-4539: nonempty arg_command sets skip_check_backround_mining and skips the question. No mining answer is needed or sent. |
| Store at process exit | deinit4548-4554 calls close_wallet; close_wallet5057-5080 calls wallet deinit then m_wallet->store(). **Correction:** lead citations4671-4676/5224 point to language selection/untrusted-daemon handling in this exact Git object. The cited behavior is supported at4548-4554/5057-5080 instead. |
| Unchanged setter/readback | set_refresh_from_block_height uses native setter/rewrite; set getter3641 prints refresh-from-block-height = and native getter. Existing source-check bindings and Core-endorsed setter/store/reopen semantics stay. |
| Interactive premise removed | get_prompt9068-9080 calls check_connection/is_synced; run9082-9093 starts idle refresh before run_handling(get_prompt). wallet2.cpp6667 mutex/default wallet2.h769: plausible blocking, not the proven cause of prior failures. |

## Independent controls

The disposable Python executable uses actual PTYs and positional argv, persists
synthetic height/address state through a real locked fixture file, and records
command/PID/options without wallet secrets. It never reads retained native files.
Its one-shot path emits no interactive wallet prompt. Connected checks require
five different PIDs, the exact creation/open argv split, persisted height0 in a
fresh getter/reopen, and per-process exit/listener/release ordering. Guard failures
must prevent the next launch. Exact200955e7 times out on the same fixture's
prompt-free startup path. Nonzero exit, extra confirmation, missing fresh getter
readback, repeated/unknown password, mining questions, unknown prompts and altered
wallet prompts fail with reaping and a private skeleton. Readline-style control
bytes still exercise the unchanged normalizer. The redactor's dictionary/prefix,
control-boundary, secret, tail, atomic0600 and symlink controls remain green.

Only fixtures model native effects; these checks establish no wallet functional
PASS row. Native work requires Platform then Security source acceptance and a
separately fresh exact900s reuse grant on published retained authority. All old
grants includingd00daf5a stay consumed. Historical nativeATTEMPTED_FAIL9/16PASS,
seven wallet rows NOT_RUN. Full consensus/maturity/payment/persistence/recovery
matrix and independent acceptance remain unfinished. Core/count2, later formal
Security, assignment/holds/routing/monitor stay; no formal Core re-entry.
launch_ready=false; public_launch=false. Needs TJ: None.

## Qualification and correction accounting

Qualified 2026-11-04T23:07:44.107018+00:00, 540.22434s from first edit, within3600s.
One implementation and one correction pass used. Full398 Python3.15.2 checks
passed in77.751973s;119 direct Python3.12.3 checks passed in25.174202s;32 focused
wallet checks passed in5.206304s. No failures/errors/skips; ResourceWarning was
an error in full/direct suites. Original-lock guards blocked zero opens/flocks
and reported unchanged protected metadata. Native/Docker/admission effects were
substituted; no native binary, private native data or original lock was opened.

Initial focused31 had one unmoved observer-anchor mismatch (SETUP vsNODE1_START);
the initial full398 had one paired main AST anchor743 vs731. Both numeric
corrections and partial-colon handling are within the single correction pass.
Original failed logs are retained, followed by qualified passing logs.

A separate invariant import omitted -B and regenerated two stale unowned bytecode
caches. Historical Git source plus original header timestamps reconstructed the
exact saved pre-run SHA256 bytes for both; all seven final hashes equal baseline.
No unowned file was deleted or staged. Their modification times changed; this
packet does not claim untouched cache metadata. See bytecode-restoration.json.
All later Python invocations disable bytecode writes. This recovery changes no
source, test result, native assertion or public data.
