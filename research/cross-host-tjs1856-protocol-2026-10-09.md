# Finite native Railway and build-mac protocol

Revision 1, prepared 2026-10-09 before any cross-host native trial. Starting
candidate is `c6620342328f313e1e9bdfb79570d5245e669090`. This is one accelerated,
valueless FCMP++/CARROT regtest witness. Accepted local tests and launch gates
remain unchanged. Source pins are those in `vanguard/source-lock.json`.

## Hosts and pins

build-mac is Darwin ARM64, macOS 26.5.1. Strict host-key SSH and its existing Colima
Docker context are the only native execution route. Docker 29.5.2 reports an
aarch64 Ubuntu 24.04.4 VM, 4 CPUs and 6,197,448,704 bytes total memory. Native
work holds `/tmp/meownero-swarm-20260912-heavy.lock` without waiting or stealing.
Require at least 5 GiB available VM memory and disk before a 4 GiB local cap.

The compatible ARM build is read-only at
`~/Developer/tjs1816-5a24c6b6/build01`. Its actual daemon SHA256 is
`b4becc6efbdc922f0fac93a0730de6f9397c1637a60b95630140e9ace677b920`,
27,832,112 bytes; wallet RPC is
`9ab761894ace8a84e3563619ba978e4d8a2c86ee07d7d38e5a5c8c364c4c450b`,
31,426,016 bytes. Builder ID is
`sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b`.
Recheck source/submodule HEADs, clean tracked sources, Cargo.lock and build
receipt before reuse. These hashes do not certify x86 binaries.

Upstream is `e151643c5269c83bf24a83b2548e2493876026b2`; Cargo.lock SHA256 is
`6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239`.
The full submodule, monero-oxide and crypto-bigint pins accompany the public
run input manifest. Rust version remains 1.93.0. If x86 is required, reuse
verified compatible cached objects in task-owned staging and build on build-mac
with its existing x86 emulation. Record emulated preparation separately from
native Railway execution. No global toolchain or runtime configuration changes.

Railway project is `f46a08ef-dcba-431b-8fb0-a3b2c0dd721e`, workspace
`2b820311-d9b2-4a11-acca-fe0ab337dc38`, regtest environment
`4e5d9d89-594e-464c-a9de-b854ec33e30a`. The reported account limit is 2 vCPU
and 0.5 GB RAM per service, with a 30-day/$5 free-credit limit. Before deployment
record the parent's exact service/auth handoff, available credit, provider
limit, runtime architecture, uploaded file hashes and built/deployed image
identity. No limit or free-credit PASS follows from generic documentation.

## Transport and exposure

Railway runs one validating daemon and a standard-library authenticated control
supervisor. It never hosts a wallet or generates blocks. RPC binds to loopback.
Its public native TCP proxy targets P2P port 19080. Only an HTTPS control domain
exposes port 8080, with a random secret in a provider runtime variable. Every
control route requires authentication. Control RPC has an explicit read-only
allowlist, excluding mining, submission and wallet methods. No browser cookie,
wallet seed, key, wallet file or chain database enters the upload package.

build-mac's single daemon and two disposable wallets run in one owned, capped
container with ordinary bridge networking, no published ports and only
loopback RPC/wallet listeners. Its sole exclusive P2P destination is the
Railway proxy. Railway's outgoing exclusive destination is an unused loopback
port, preventing public discovery. Both use regtest, fixed difficulty 1,
disabled DNS checkpoints, disabled update checks, no IGD and no ZMQ. Confirm
actual connection endpoints, network ID/chain genesis and process command lines.
This is native Levin traffic across actual hosts, not the accepted Unix bridge.

Railway documents [native TCP forwarding](https://docs.railway.com/networking/tcp-proxy)
and [Dockerfile source deployment](https://docs.railway.com/builds/dockerfiles).
Deployment uses supported [CLI authentication](https://docs.railway.com/cli).
The actual service and deployed observations determine acceptance.

## Bounded trial

Use a fresh private directory for every attempt. Start local and remote peers,
record live executable identities and require native handshake and common
genesis/tip. On build-mac create sender and recipient wallets, fund the sender with
70 blocks, synchronize both peers and require mature disposable inputs. Begin
the measured window only after funding and empty pools agree. Allow at most
90 generated blocks total, 4 workload payments and 900 measured seconds.

Confirm three sequential distinct FCMP++ type-7 payments to the recipient,
using different amounts and disjoint input key images. For each preserve the
wallet destination/amount request, full serialized transaction, fee, admission,
both native decoded transactions and main-chain blocks, and one matching
recipient output. Require identical byte/hash/height/block binding and exactly
one credit. Refresh the sender after admission to reserve its inputs. Mine
only on build-mac and wait for both peers before the next payment.

Then gracefully restart only the Railway daemon within its supervisor,
retaining its chain directory. Bind the pre/post generation identity, saved
chain tip and disk state, exit code and native reconnect. Confirm the fourth
distinct payment after recovery. Recheck all four payments, empty pools,
recipient balances, both healthy peers and matched final tips. Preserve every
failed or partial attempt without upgrading its result.

Sample local/remote cgroup memory, OOM and CPU counters, daemon RSS and disk
through shutdown, at least every 10 seconds during the measured trial. Record
actual construction, transport and confirmation times. Verify the remote peer
against its actual service memory limit; local ARM/x86 emulation is preparation
evidence only. Record local and remote process exits and final measurements.

## Deadlines, cleanup and acceptance

The remote supervisor enforces a 1,800-second lifetime from startup. Provider
restart policy must be NEVER, so expiry cannot cycle indefinitely. The measured
trial has a 900-second deadline after funding, 180-second phase deadlines and
a 1,500-second whole native-run deadline. An operator cleanup deadline must be
recorded in the frozen run inputs before service startup. Always stop/remove
the Railway deployment, TCP proxy, HTTPS domain and any task volume after
capture, including failure paths. Leave the empty private project and shared
Colima running. Remove exact owned local containers/processes and task images;
preserve raw public evidence and private failed attempts safely.

Publish PASS/FAIL/NOT_RUN per requirement, raw hashes and reproduction commands.
Once a candidate and raw evidence exist, activate one native review stage for
`ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`. The writer cannot supply independent
acceptance. Parent integration and group outcome follow acceptance of the exact
candidate. This witness does not establish cryptographic soundness, production
security, selected-policy capacity or public-trial readiness.
