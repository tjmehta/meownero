# Resumed privacy implementation — 2026-09-12

TJ authorized this local continuation after the earlier track closure. The
coordinator root's `research/decision-2026-09-12-issuance.md` and latest handoffs
were read first: selected issuance is **9 MEOW/90 seconds**, with **12/120** only
as the gated fallback. This work changes no issuance consumers or production
patches. The reused binary remains the historical fifteen-patch control; these
results do not establish selected-profile integration.

## Implemented boundary

[`privacy-wallet-rpc.py`](../chain/privacy-wallet-rpc.py) now accepts paired
`--restricted-wallet` and `--password-file` arguments. It opens the existing
wallet through upstream `--wallet-file --password-file --restricted-rpc`, while
retaining the loopback authenticated RPC listener, global local SOCKS proxy,
untrusted daemon, pinned HTTPS/onion startup policy and private state/log paths.
It refuses missing files, missing companion options, nonregular files, and
wallet/cache, `.keys` or password files not owned by the current user or readable
only by that user. Validation happens before creating launcher state or executing
the wallet. The password contents never enter launcher arguments or evidence.

This is an opt-in native controller restriction for an already provisioned
wallet. The existing default administrative mode is preserved. Upstream refuses
wallet creation and opening through restricted RPC, so simply forwarding
`--restricted-rpc` alongside the old `--wallet-dir` would leave the application
without a usable loaded wallet. No new RPC proxy, application service, address
parser, dependencies or upstream patches were introduced.

Example, with locally supplied reviewed paths and an out-of-band certificate pin:

```sh
python3 chain/privacy-wallet-rpc.py \
  --binary /absolute/path/to/verified/monero-wallet-rpc \
  --state-dir /absolute/path/to/private/rpc-state \
  --rpc-port 19100 --proxy 127.0.0.1:9050 \
  --daemon https://127.0.0.1:18081 \
  --daemon-fingerprint YOUR_OUT_OF_BAND_64_HEX_CERTIFICATE_SHA256 \
  --restricted-wallet /absolute/path/to/private/existing-wallet \
  --password-file /absolute/path/to/private/password-file
```

Provisioning and syncing a wallet remain operator responsibilities. Native
restricted mode denies manual refresh/auto-refresh configuration and wallet
management RPCs; upstream startup/background behavior still applies. Do not run
a second process against an already open wallet. This mode does not turn a
spend-capable wallet into a watch-only wallet or erase its keys.

## Actual-binary checks

The [sanitized result](evidence/resume-privacy-2026-09-12/result.json) and
[stdout receipt](evidence/resume-privacy-2026-09-12/harness.stdout.log) record the
complete final run, including all earlier controls: **52/52 passed in 45.665
seconds**, with a measured container memory peak of **42,483,712 bytes**
(40.5 MiB). Python AST, shell syntax, launcher help and local report links also
pass. Checks include:

- An existing disposable wallet opens in a fresh restricted process. Its balance
  and native address remain readable; unauthenticated RPC still returns 401 and
  the random login file retains private permissions.
- Authenticated daemon/TLS/trust changes and daemon/proxy replacement return
  upstream restricted error `-7`. Create/open wallet, transfer to an alias and
  mnemonic export also return `-7`; these probes emit no DNS queries. A subsequent
  spend-proof query still reaches the original pinned daemon through SOCKS, with
  zero direct or redirect-observer connections.
- A native address validates with `allow_openalias=false`; an alias is invalid
  with zero DNS queries. With `allow_openalias=true`, restricted mode still emits
  **10 controlled DNS queries** despite `--no-dns`. The resolver is isolated
  loopback TCP and never forwards externally.
- A valid serialized public genesis transaction returned for the all-zero
  requested transaction ID reaches the actual transaction-hash mismatch guard.
  Truncating that valid hex reaches the transaction decoding guard. Neither
  returns a spend proof.
- Valid JSON containing a roughly 2 MiB invalid transaction hex field or a
  roughly 2 MiB unknown padding field returns an error and leaves the wallet
  callable with zero balance. The recorded response sizes are 2,097,193 and
  2,097,207 bytes. A string instead of the transaction array reaches the count
  guard. A short HTTP body with a larger declared Content-Length fails transport.
- Missing option pairs/files, exposed wallet/cache/keys/password permissions and
  a FIFO password file fail before state creation. The FIFO case terminates
  without attempting a blocking read. Existing configuration, dead-proxy,
  post-success proxy refusal, TLS-pin mismatch and redirect controls still pass.

The hostile responses exercise `get_spend_proof` on an empty disposable wallet.
The original malformed/truncated JSON cases can reach semantic guards after
partial decoding; **strict JSON parsing is not established**. Large responses
were consumed before semantic rejection: **no response-size limit was added or
proven**. The [machine-readable interpretation](evidence/resume-privacy-2026-09-12/response-boundary-interpretation.json)
explicitly distinguishes these errors from a size ceiling. The HTTP client's `handle_target_data` appends received pieces to its
body buffer. The two bounded oversized probes do not establish resistance to
unbounded, compressed, slow, deeply nested or sustained denial-of-service input.

## Scope that remains outside this launcher

Authenticated restricted RPC is still sensitive. Address/balance queries,
OpenAlias validation and some proof-generation methods remain callable; it is
not an arbitrary-application sandbox, a complete read-only API or a process-wide
DNS boundary. The demonstrated controller gap is closed only when the operator
selects `--restricted-wallet`. Administrative mode still accepts `set_daemon`
trust/TLS changes, as the retained positive control demonstrates.

Daemon hostnames still travel intact to the tested SOCKS4a proxy; this change
does not require numeric daemon addresses or block OpenAlias in every
address-taking RPC. A future controlling application must enforce literal
native-address input and its permitted method set before making stronger claims.
There is no existing product application layer here to retrofit. Same-user file
replacement, mutable binaries, malicious local proxies and other process egress
are outside the launcher boundary. File checks assume a trusted local user and
private containing directories; they are not a race-proof file sandbox.

No Tor/I2P network, circuit separation, timing correlation, daemon P2P relay,
synchronization anonymity, funded transfer/decoy selection, eclipse/reorg
resilience, FCMP workload or selected-issuance binary was tested. TLS pinning
authenticates a node; it does not make its data true. No blanket anonymity or
comprehensive malicious-node-resilience claim is made.

## Reproduction and preservation

```sh
bash chain/privacy-test.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meow-resume-privacy-your-new-run
```

The runner refuses output reuse and uses the existing immutable builder with
network disabled, one CPU, 512 MiB memory/no swap, dropped capabilities and
read-only source/harness mounts. No compiler was run and the shared heavy lock
was not acquired, leaving network reproduction priority intact. The selected
policy's heavy-work 5 GiB preflight remains applicable to future heavy builds.

The evidence includes binary/source revision and input hashes. The reusable
source locations checked are `wallet_rpc_server.cpp` (restricted checks,
OpenAlias and wallet startup), `wallet2.cpp` (transaction count/decode/hash
checks), `cryptonote_config.h` (public genesis fixture) and
`contrib/epee/include/net/http_client.h` (response accumulation).

Final scratch output is `/tmp/meow-resume-privacy-20260912-b`; the first successful
run at `...-a` is also preserved. Both contain disposable secrets and must not be
published wholesale. Only aggregate counts/errors, revisions and hashes were
copied into the new evidence directory. Existing raw privacy evidence,
production patches, real keys, verified source/binaries, frozen clean15 inputs
and historical seed evidence were not edited. Shared docs and issuance aggregate
consumer work remain with the coordinator. No push, publication, outreach,
spend, host-service changes or additional agents occurred.
