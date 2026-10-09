# Run a disposable Vanguard payment

This candidate contains the pinned FCMP++/CARROT daemon, wallet CLI and wallet-RPC
programs. It runs a local accelerated regtest with valueless coins. It has no
shared group network or faucet and does not apply the historical 9/90 policy.
Use only disposable wallets. Keep personal seeds, wallets and coins elsewhere.

Read the adjacent release manifest and `release.json` before running. The
archive freezes its initial `BUILT_UNTESTED` status. The adjacent release
manifest records subsequent native journeys and independent review against its
exact SHA256.
An archive's existence does not establish support for your distribution.
The final review report must bind the archive's SHA256 and tested environment.

## Requirements

Use the operating system and architecture named in `release.json`, Python 3.8
or later on Linux/Mac, two CPU cores, five GiB available memory and five GiB free disk.
Windows requires CPython 3.13 or later, which protects the private output directory
with user/admin access. Use 64-bit CPython for x64 and ARM64 programs, and Windows
10 version 1709 or later. Native Windows
journeys and download approval remain untested until recorded against exact bytes.
Linux ELF packages require the stated glibc version. Native macOS Mach-O
packages require the stated macOS version and matching CPU. Read the ABI,
dependency and signing fields in that same manifest. The Mac candidate has an
ad hoc linker signature or is unsigned, as recorded in its manifest. It is not
Developer ID signed or notarized; download
approval by macOS remains a separate check. Windows, WSL and containers are
separate targets. This package does not install anything or invoke Docker.

Check the downloaded archive against the adjacent `SHA256SUMS`, extract it to
a new directory, and open a terminal in the extracted package. Run:

```sh
./launch.sh preflight
./launch.sh run --out ../my-disposable-journey
```

On Windows, open Command Prompt in the extracted package and run:

```bat
launch.cmd preflight
launch.cmd run --out ..\my-disposable-journey
```

Windows x86 programs can run on an x64 Windows host through WOW64; the receipt
records that environment. ARM64 Windows archives require ARM64 hardware.
For an Intel Mac archive on an Apple Silicon Mac with Rosetta already installed,
add `--translated-macos-x86_64` to each command. Its receipt is marked
`ROSETTA_TRANSLATED_MACOS_X86_64` and `PASS_TRANSLATED_JOURNEY`; it does not
certify an Intel CPU. No starter installs Rosetta or changes system settings.

The output name must be new. Keep output outside the package. The entrypoint
checks every packaged file, source pins, native binary format and architecture,
then starts programs only on loopback. It refuses a busy tester lock or existing
output. The daemon uses offline regtest, fixed difficulty and one worker. An
attempt has a twenty-minute deadline. It stops only its own child processes,
keeps diagnostics, and never deletes another run's output. Windows children
start suspended and enter a private Job Object before execution; its deadline,
memory limit and final cleanup apply only to that job and its descendants.

The run generates seventy blocks to obtain disposable sender funds. It sends
five units to a new receiver, confirms the native FCMP++/CARROT transaction,
restores that receiver from its disposable seed in memory, compares output and
key-image identities, then spends two recovered units back to the sender and
checks receipt of that exact transaction. Confirmation blocks take seconds.
`PASS_NATIVE_JOURNEY` requires all steps and owned-process cleanup to pass.

`private/` holds disposable wallet and chain databases and native logs. Keep it
unshared, including after a failed attempt. Share only the fixed `result.json`
receipt. It contains program/manifest hashes and public test transaction hashes,
amounts and cleanup status. The entrypoint never exports a directory or prints
the recovery seed. Save failed outputs for diagnosis; choose a new output name
for each correction. Delete only an exact disposable output you own when done.

## Explore the native CLI

`bin/monerod --help`, `bin/monero-wallet-cli --help` and
`bin/monero-wallet-rpc --help` describe the actual shipped programs.
Windows program names end in `.exe` and their bundled DLLs sit beside them in `bin/`.
The automated journey exits its daemons and wallets when finished. To inspect the resulting
wallet manually, on Linux first set `export LD_LIBRARY_PATH="$PWD/lib"` in this
terminal to use the bundled libraries. The native Mac package uses system
frameworks and bundles its other dependencies statically. Start the daemon with the same `private/chain` directory and
the regtest/offline options used in `tester.py`. Open
`private/restored/restored` with the wallet CLI, `--allow-mismatched-daemon-version`
`--shared-ringdb-dir` pointing at that run's `private/ringdb`, and the local
daemon's RPC address. Use `refresh`, `balance`, `incoming_transfers`
and `show_transfers`. The disposable wallet has an empty password.

For another manual payment, create a disposable CLI wallet against that same
daemon, use `address` for its receive address, and transfer from the restored
wallet. Confirm by calling the daemon's `generateblocks` RPC with your sender
address, then refresh the receiving wallet. For recovery, create another
disposable wallet with `--restore-deterministic-wallet`, the receiver's
twenty-five-word seed and restore height zero. Enter the seed locally at the
prompt and keep it out of shell history. Refresh and check its balance before
making a subsequent transfer. The daemon help/RPC contract at the exact source
pin governs these commands. No public node is provided by this candidate.

The automated journey establishes a local payment and recovery witness only.
It does not establish public-network privacy, selected-policy integration,
production cryptographic assurance, or support for an untested OS/ABI.
