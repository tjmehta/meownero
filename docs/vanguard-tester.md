# Try a local Vanguard payment and recovery

This kit lets an operator watch disposable funds move between two native nodes,
restore the receiving wallet, and spend its recovered funds. Everything happens
inside a network-disabled container. These coins have no value. Use no personal
wallet, seed or credentials.

The current implementation runs the pinned upstream FCMP++ and CARROT code in an
accelerated, fixed-difficulty regtest. It does **not** apply Meownero's selected
9 MEOW / 90-second policy. The historical [testnet-v0 journey](../chain/testnet-v0/journey.md)
tests that separate policy lineage and takes about three hours. Choose this kit
for a short current-crypto first-use check. Choose the historical journey only
when that older policy witness is the subject of the test.

## Supported setup

Only `build-mac-colima-arm64` is supported: build-mac, Darwin 25.5.0, arm64, Docker client
29.2.1 / Linux ARM64 server 29.5.2, existing `colima` context at
`unix://~/.colima/default/docker.sock`. The local image, toolchain,
upstream/submodule/Cargo.lock pins and native binary hashes are in
[tester-profile.json](../vanguard/tester-profile.json) and
[source-lock.json](../vanguard/source-lock.json).

The verified cache is `~/Developer/tjs1816-5a24c6b6/build01`. Preflight
checks its original accepted preparation receipt, exact source revisions and
clean tracked sources, installed rustc/cargo hashes, and native ELF ARM64 daemon
and wallet bytes. Runtime versions are checked again during the cached inspection
stage. The cache is mounted read-only. There is no compilation, pull or installer.
This is assisted setup on a verified machine, not a clean-machine installer.
Other Macs, Linux, x86 emulation and Windows remain unsupported.

You need an idle existing Docker runtime, its existing shared heavy-work lock,
two VM CPUs, at least 5 GiB available VM memory, and 5 GiB available host disk.
An absent prerequisite produces `FAIL_TESTER` and exit 1. Keep the diagnostic and
ask the operator to resolve that specific prerequisite within their authority.
The kit does not start Colima, change its settings, stop other containers, pull
an image, install tools or repair a cache.

## Run on build-mac

From a clean committed candidate, an agent/operator can create a small package:

```sh
python3 -B vanguard/tester.py package --out /existing/owned/parent/kit01
```

Copy only that owned package to a fresh directory on build-mac using the existing
SSH route. The package contains named code/docs and `tester-inputs.json`, which
binds every file to the candidate commit. It includes no executables or secrets.
Run from its root, using fresh output names under an existing owned parent:

```sh
python3 -B vanguard/tester.py preflight
python3 -B vanguard/tester.py run --out ~/Developer/tjs1870-owned/journey01
python3 -B vanguard/tester.py export ~/Developer/tjs1870-owned/journey01 \
  --out ~/Developer/tjs1870-owned/public01 \
  --archive ~/Developer/tjs1870-owned/public01.tar.gz
```

Preflight is read-only, including a nonblocking test of the existing lock inode.
Run rechecks idle Docker after taking that lock and keeps it across both gates.
It first inspects cached native binaries, then runs the unchanged native P2P
scenario once and the unchanged funded restore scenario once. Each scenario has
a 1,100-second container deadline, a bounded host wait, 2 CPUs, 4 GiB RAM,
256 PIDs, no capabilities and no outside network. Its private Unix socket uses
the accepted container tmpfs approach because Colima shared folders cannot chmod
that socket. The workload has a 2,500-second
host workload budget, enforced by a timer as well as bounded subprocess waits.
Every invocation uses fresh random container names and a cidfile inside its fresh
output. Before cleanup, the actual ID, pinned image and invocation label must
match. A stopped-container name collision refuses the run and preserves that
container. Cleanup uses the proven ID and independently bounds stop, inspection,
removal and the final ID listing. A timeout in one step still attempts the later
steps and records the error; any cleanup error fails the run. An unavailable
ownership proof leaves the container untouched and records cleanup as unknown.
Exact-container cleanup has separate bounded waits after a deadline or signal.
Typical measured timing belongs in the rehearsal report; no
30-minute soak or Railway run is part of this invocation.

The restore gate confirms a 5-unit payment to a new receiver, restores its
25-word disposable seed in memory, rescans, checks reorg rollback, and confirms
a later 2-unit spend. It also checks orphan-spend and key-image replay refusals.
The P2P gate includes native relay, malformed-frame refusals and healthy relay
after reconnect. Exact native process hashes, RPC observations, transaction and
block hashes, wallet output identities, process exits, memory/OOM counters and
owned container removal are saved. Wallet creation and seed RPC are excluded
from observations. Transaction secret keys and private pending-transaction
metadata are excluded even when a wallet could return them. The cache and package
are rehashed after the workload. Every private output remains mode 0700 and unshared.

On success, run exits 0 and `result.json` says `PASS_NATIVE_JOURNEY`. On failure,
it exits nonzero, keeps the failed attempt and attempts removal only by its proven
owned container ID.
Never rerun into that output or delete another operator's output. Failed or
incomplete output cannot be exported as a passing journey. Private wallet,
chain and ring databases remain in the owned directory for diagnosis until its
owner chooses exact-path deletion. No wallet or chain data is copied to the cache.

## Verify and share the receipt

Copy only `public01.tar.gz` or its explicit public file set back to the reviewer.
From the full repository at the exact candidate, verify the exported directory:

```sh
python3 -B vanguard/tester.py verify /owned/public01
python3 -B vanguard/test-tester-refusals.py --public /owned/public01 --work /owned/controls01
```

On the same idle supported build-mac setup, the reviewer also runs the native cleanup
controls from the package root:

```sh
python3 -B vanguard/test-tester-cleanup.py --work ~/Developer/tjs1870-owned/cleanup-controls01
```

These create their own stopped fixtures and short cached-inspection containers.
They check collision preservation, refusal of a foreign invocation label, and
removal after injected stop/inspection transport timeouts. Each operation has a
deadline and uses the shared lock. No daemon or wallet scenario runs in these
fault controls. Failed control outputs stay private; only `controls.json` is a
shareable summary. The script removes only the exact IDs it created.

The ARM adapter checks fixed independently accepted ARM binaries and then calls
the existing P2P and restore reconcilers. Their historical x86 CLI pins and all
scenario assertions remain unchanged. The legacy receipt field `build` records
a cached inspection stage, explicitly labeled `build_mode`; it is not a new build.

Only named JSON receipts, native observations, counters and captured Levin
refusal frames are exported. Daemon parser logs are projected to recognized
parser markers only, with the original raw digest recorded. Free-form logs and
all unlisted files are excluded. JSON passes the pinned
[public field/type schema](../vanguard/tester-public-schema.json), including
nested objects, arrays and JSON encoded inside native RPC responses. Unknown
fields are refused before any shareable export is created. Wallet notes are
excluded at capture. The schema is frozen from source-pinned writer and
independent reviewer receipts; it never learns fields from the input being
exported. New legitimate upstream fields require an explicit schema review.
Symlinks, hard links, nonregular files, changed manifests, secret-bearing JSON
and renamed database content are refused. Never
archive the original output recursively. Even these public receipts link
disposable local transaction/output identities; they are evidence for this test,
not an anonymity claim.

An independent reviewer must reproduce the documented `preflight`, `run` and
`export` invocation with fresh owned paths and inspect the exact candidate.
Screenshots and a writer summary do not satisfy that requirement. See the
[current evidence and acceptance index](../research/current-evidence.md).

## What this does not establish

The RPC clients explicitly trust their local throwaway daemons. A local operator
can observe wallet RPC and associate amounts, addresses, output identities and
relay origin. The loopback/AF_UNIX bridge has no outside observer here; it gives
no evidence about public IP exposure, remote-node honesty, Tor/I2P, DNS/OpenAlias
or a hostile Internet peer. A seed restores on-chain funds and spend capability,
not local notes or all metadata. Secrets remain with the disposable local run.

Portability, selected-policy 9/90 integration of this current crypto lineage,
public-testnet readiness, sustained capacity and production cryptographic/security
assurance remain open. Agent review is not an external audit. The accepted
52-case restricted-controller checkpoint remains a separate completed result.
