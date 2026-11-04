# Wallet setup and prompt audit

Run `2eb5b450-3335-4de6-b553-1a536277890e`, 2026-11-04. Base
`b17746e67e2512f1348ea05fb90f6955950d08b6`. Lead decision interaction
`7c011923-32e9-49c2-8abc-1af68a51b5ed`, report `8a735166`.
One implementation pass, one correction pass available, at most 60 minutes from
first edit at 18:39:53 UTC. This is source evidence; no native attempt is authorized.

All upstream paths below are relative to pinned Monero
`e151643c5269c83bf24a83b2548e2493876026b2`. The fixture checks the inspected
files against their exact Git objects. Candidate paths below are relative to
`vanguard/network/`. Every option in both actual wallet argv lists and their
shared config is listed. Only `cli.conf` is a wallet option config; the private
password and automatically generated RPC login files are credential inputs.

| Entry | Candidate file:line | Pinned registration/behavior | Verdict |
| --- | --- | --- | --- |
| Shared `daemon-login=<private daemon login>` | profile-integration.py:486 | wallet2.cpp:264,1339; both mains call wallet2::init_options | OK; credential bytes/handling unchanged |
| Shared `rpc-ssl=disabled` at base | profile-integration.py:486 (base475) | wallet2.cpp:265,1340 registers `daemon-ssl`; simplewallet.cpp:10325-10353 does not register rpc_args; wallet_args.cpp:167 rejects unknown config keys before log setup at190 | MISMATCH fixed to `daemon-ssl=disabled` |
| Shared `daemon-ssl=disabled` after correction | profile-integration.py:486 | wallet2.cpp:265,1340,354-381; accepted disabled value | OK for CLI and RPC daemon client |
| CLI executable `monero-wallet-cli` | profile-integration.py:410 | src/simplewallet/CMakeLists.txt OUTPUT_NAME; simplewallet.cpp:10314 main | OK |
| CLI `--testnet` | profile-integration.py:410 | wallet2.cpp:272,1347; simplewallet.cpp:3918-3925 | OK |
| CLI `--config-file <root/cli.conf>` | profile-integration.py:410 | wallet_args.cpp:112,132,160-167 | OK |
| CLI `--password-file <root/password>` | profile-integration.py:411 | wallet_args.cpp:79-81; wallet2.cpp:262,1337,521-548 removes trailing line breaks | OK |
| CLI `--daemon-address 127.0.0.1:<port>` | profile-integration.py:411 | wallet2.cpp:256,1331 | OK |
| CLI `--log-file <root/cli.log>` | profile-integration.py:412 | wallet_args.cpp:111,127,185-190 | OK; private path |
| Create `--generate-new-wallet <root/wallet>` | profile-integration.py:413 | simplewallet.cpp:160,10329,4393-4407 | OK; fresh controlled path |
| Create `--mnemonic-language English` | profile-integration.py:413 | simplewallet.cpp:167,10336,4722-4738 selects supplied language from language list | OK; no language answer needed |
| Reopen `--wallet-file <root/wallet>` | profile-integration.py:413 | wallet_args.cpp:75-77; simplewallet.cpp:10327,4500ff | OK; existing stopped bundle |
| RPC executable `monero-wallet-rpc` | profile-integration.py:466 | src/wallet/CMakeLists.txt OUTPUT_NAME; wallet_rpc_server.cpp:5190 main | OK |
| RPC `--testnet` | profile-integration.py:466 | wallet2.cpp:272,1347; wallet_rpc_server.cpp:5012-5019 | OK |
| RPC `--config-file <root/cli.conf>` | profile-integration.py:466 | wallet_args.cpp:112,132,160-167; wallet_rpc_server.cpp:5202 | OK; both shared keys registered |
| RPC `--wallet-file <root/wallet>` | profile-integration.py:467 | wallet_args.cpp:75-77; wallet_rpc_server.cpp:5195,5207,5068 | OK |
| RPC `--password-file <root/password>` | profile-integration.py:467 | wallet2.cpp:262,1337,521-548; wallet_rpc_server.cpp:5068 | OK |
| RPC `--daemon-address 127.0.0.1:<port>` | profile-integration.py:468 | wallet2.cpp:256,1331 | OK |
| RPC `--rpc-bind-ip 127.0.0.1` | profile-integration.py:468 | rpc_args.cpp:92,117; wallet_rpc_server.cpp:5206 | OK; loopback unchanged |
| RPC `--rpc-bind-port <port>` | profile-integration.py:469 | wallet_rpc_server.cpp:144,5203 | OK |
| RPC `--rpc-ssl disabled` | profile-integration.py:469 | rpc_args.cpp:101,126,77; wallet_rpc_server.cpp:5206 | OK; explicit server option retained |
| RPC `--restricted-rpc` | profile-integration.py:469 | wallet_rpc_server.cpp:146,341,5205 | OK; all 17 denial predicates unchanged |
| RPC `--log-file <cwd/native.log>` | profile-integration.py:470 | wallet_args.cpp:111,127,185-190 | OK; private path |

The programmatic source check also confirms both mains' registrations rather
than accepting a descriptor string without its registration. The disposable CLI
models the audited option subset and refuses any other key before log setup.
It is a fixture, not Boost's parser or a compiled native CLI.

| Prompt/answer/command | Candidate file:line | Pinned source | Verdict |
| --- | --- | --- | --- |
| English command text | profile-integration.py:38 (LC_ALL=C) | simplewallet.cpp tr() strings in C locale | OK |
| `[wallet <six Base58 chars>]: ` | profile-integration.py:418 | simplewallet.cpp:9068-9080 uses address.substr(0,6), wallet text and `]: ` | OK |
| Optional `(no daemon)` / `(out of sync)` | profile-integration.py:418 | simplewallet.cpp:9074-9077 | OK |
| ANSI stripping and CR normalization | profile-integration.py:436 | prompt text above; console color/terminal wrappers | OK; fixture exercises fragmented tokens |
| Startup wallet prompt; no password answer expected at load | profile-integration.py:446 | wallet2.cpp:532-545 password-file bypasses password prompt; simplewallet.cpp:4722-4738 supplied language | OK; runtime remains unproven |
| `Wallet password: ` | profile-integration.py:438 | simplewallet.cpp:324,4677-4691; common/password.cpp:183 appends colon/space | OK |
| Answer same private password once per expect | profile-integration.py:439-440 | simplewallet.cpp:2612,4677-4694 calls get_and_verify_password for setter | OK; credential handling unchanged |
| Repeated Wallet password | profile-integration.py:439 | invalid password can cause a retry; controller must not retry secrets | OK; original require unchanged |
| Unknown `Enter password...: ` / `Confirm password: ` | profile-integration.py:441 | simplewallet.cpp:5567-5571; common/password.cpp:188 | OK; refused, no answer |
| Unknown confirmation `[y/N]: ` | profile-integration.py:441 (base430) | simplewallet.cpp:279-285 input_line appends ` [y/N]` then `: ` | MISMATCH fixed: refusal regex now includes colon/space; no answer |
| Legacy `[Y/n]: ` refusal | profile-integration.py:441 | no selected-path emitter identified; retained defensive rejection | OK; no answer |
| `set refresh-from-block-height 0` | profile-integration.py:447 | simplewallet.cpp:3711 dispatch;2610-2624 parses height, verifies password, sets height and rewrites keys | OK |
| `set` | profile-integration.py:447,451 | simplewallet.cpp:3641 prints `refresh-from-block-height = ` followed by stored height | OK; existing height-zero assertion unchanged |
| `address new` | profile-integration.py:447 | simplewallet.cpp:3168,9344-9357 creates subaddress, no confirmation/password for this path | OK |
| `refresh 0` | profile-integration.py:447 | simplewallet.cpp:3102,5749-5764 parses start height then refresh_main;5644ff | OK; selected genesis-only zero-funding path; unexpected password still refused |
| `save` | profile-integration.py:447 | simplewallet.cpp:3180,5090-5110 stores wallet and prints Wallet data saved | OK; no confirmation expected |
| `exit` and wait for zero status | profile-integration.py:453-455 | contrib/epee/include/console_handler.h:407; simplewallet.cpp:10415-10420 run/deinit,5057-5087 close/store | OK; existing exit/PID assertions unchanged |
| EOF / Linux PTY EIO | profile-integration.py:424-434 | PTY slave close is a read termination; process status obtained by wait | Added bounded reap and exception note containing status + expected prompt label; main's unchanged private traceback writer persists it |

Two mismatches were fixed; none requires assertion or contract changes. The
fixture uses pinned strings for creation, password, setter/query, address,
refresh, save, exit and confirmation refusal. It tests actual controller PTY
handling, including split prompts, reopen, EOF/EIO and early command exit.

Private diagnostic notes travel only to the existing `failure-traceback` writer.
The actual-main fixture verifies its 0600 mode and the unchanged closed public
three-key OSError diagnostic without status, label or transcript. No actual
wallet console, seed, password, login or private native file was opened.

`runtime_diagnostics.py` receives only an eleven-line offset adjustment for its
existing main/wallet tables and cutoff. Public vocabulary/schema are unchanged.
The source tests protect every existing require call, commands, password write,
and all driver bytes outside cli() plus the single config token. The freezer,
runner, build.sh, native inputs and compiled build identity remain byte-identical.

Platform source review comes first. Security follows only if Platform identifies
a changed authentication, credential, isolation or export surface. A separate
fresh exact 900s runtime-only reuse grant is still required, bound to the accepted
commit, runner, inputs and packet plus the published retained root/digest. All old
grants remain consumed. Formal Core47234b59/count2 and later formal Security are
unchanged. Historical native ATTEMPTED_FAIL with nine of sixteen functional rows
PASS; this source round adds no native results. launch_ready=false;public_launch=false.

Needs TJ: None.
