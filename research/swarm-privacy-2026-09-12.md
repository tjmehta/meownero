# Privacy worker — startup transport controls and observer evidence

2026-09-12. Bounded local deliverable for parent integration/review. Based on
`39070e8e3ab32a695d80c90b7c0ad74cf39fb581`, including `81b3182`. Decision record
and resumed handoff read completely; closed chain/recovery/reproduction evidence
was reused, not rerun. No consensus, policy, seed-script, CI or shared-plan edits.

**The launcher controls startup wallet-to-daemon connections. It is not a
process-wide anonymity sandbox.** The authenticated local RPC controller can
change TLS and trust settings. OpenAlias lookups can issue DNS outside SOCKS
despite `--no-dns`: the real binary produced 10 queries to a controlled local
resolver in this test. Application enforcement of literal addresses/OpenAlias
restrictions remains a parent follow-up. No production patch 0016 or custom RPC
proxy is included.

## Deliverable and measured outcome

- [Strict startup launcher](../chain/privacy-wallet-rpc.py): Python standard
  library, no dependencies, passes existing upstream options and replaces itself
  with the wallet process. Required numeric loopback SOCKS endpoint; onion HTTP
  or explicit HTTPS certificate pin; loopback authenticated wallet RPC;
  untrusted daemon; private state and bounded logs; no arbitrary extra options.
- [Reproducible runner](../chain/privacy-test.sh) and
  [observer harness](../chain/privacy-test.py): **29/29 cases, exit 0, 35.676 s**.
  One wallet at a time; immutable builder; network namespace with loopback only;
  no published ports; 512 MiB memory/swap cap, one CPU, dropped capabilities,
  read-only root/source/harness. Observed cgroup memory peak **33,312,768 bytes**.
  No build or heavy job was needed, so no heavy-lock work was performed.
- [Machine-readable results](evidence/swarm-2026-09-12/privacy/result.json),
  [console evidence](evidence/swarm-2026-09-12/privacy/harness.stdout.log),
  [source manifest](evidence/swarm-2026-09-12/privacy/source-manifest.json), and
  [harness hashes](evidence/swarm-2026-09-12/privacy/harness-manifest.json).

The real wallet RPC binary SHA-256 was
`3c6df7d56822641f1aca4c064a7d52d931cec566ee8ca480f114ff8147bae097`.
It was reused read-only from `/tmp/meownero-wallet-verified-source-20260912`:
applied HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, source tree
`4db958cb96d72943c5c2433bd5f4a8f730037148`. This inherits the resumed handoff's
incremental-build provenance; it is not new clean-build verification.

## Three distinct observer paths

Source paths/line numbers below refer to that applied source tree; manifest
hashes identify the bytes. Upstream links are fixed at
`4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, not moving `master`.

| Path | Actual code and controls | Observer and remaining disclosure |
| --- | --- | --- |
| Wallet → daemon RPC | `wallet2.cpp:3197` sends short chain history/start height to `/getblocks.bin`; `:7590` sends the serialized transaction to `/sendrawtransaction`. `src/net/http.cpp:40` installs the SOCKS connector; `socks_connect.cpp:60` passes hostnames to SOCKS without local resolution. `wallet2.cpp:1382` preserves a startup global proxy across `set_daemon`. | The daemon sees request timing, queried chain/transaction data and submitted transaction bytes. A proxy changes the observed network source, not the daemon's knowledge of its RPC session. An onion service authenticates its endpoint through Tor; pinned HTTPS authenticates the selected certificate. Neither makes the node's data truthful. |
| Daemon → transaction-relay peers | `p2p/net_node.inl:2277` selects an anonymity zone for locally originated transactions when configured. With no suitable anonymous outbound route, it does not choose the public zone. Transactions received through P2P take the public relay path. `--tx-proxy` configures these anonymity zones. | Relay peers and network observers see timing/volume and transaction propagation. Wallet RPC transport alone says nothing about the remote daemon's relay configuration. The existing no-route behavior is source-backed here, not a measured P2P/real-transaction result. |
| Daemon ↔ synchronization peers | `cryptonote_protocol_handler.inl:491` excludes chain sync in Tor/I2P address zones. `p2p/net_node.inl:883` separately supports daemon-wide `--proxy`, replacing the public-zone connector and disabling DNS seeds/blocklist unless proxy DNS leakage is explicitly allowed. | With only `--tx-proxy`, ordinary synchronization remains a separate public network path. Public-zone traffic carried through daemon `--proxy` is distinct from the Tor/I2P transaction zones. The synchronization peer still sees chain state and requests. This track does not test or launch that daemon configuration. |

Pinned primary sources: [wallet](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp),
[HTTP connector](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/net/http.cpp),
[SOCKS connection](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/net/socks_connect.cpp),
[P2P selection](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/p2p/net_node.inl),
[sync handler](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_protocol/cryptonote_protocol_handler.inl).

There is also an **application → wallet RPC control interface**, distinct from
the wallet's daemon RPC client. It can manage keys, transfers and daemon settings.
The launcher binds it to IPv4 loopback, leaves upstream Digest authentication
enabled, and puts upstream's random mode-0600 login file inside a user-owned
private directory. It is a trusted administrative interface, not safe to expose
to arbitrary applications or through a public onion service. See
`wallet_rpc_server.cpp:305–389,4694–4765` and
[`rpc_args.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/rpc/rpc_args.cpp)
(`rpc-use-ipv6` defaults false).

## Positive controls, refusal and malicious-response results

| Case | Measured result |
| --- | --- |
| Direct positive control | Actual binary without proxy reached the same TLS daemon observer: 1 direct TCP connection, 5 HTTP requests. |
| Dead startup proxy | Bound/non-listening SOCKS port; 4 failed proof requests including after authenticated `set_daemon`; **0 direct connections**. Nonempty per-daemon proxy override returned RPC error `-49`. |
| Working proxy | SOCKS4a request forwarded to the real destination with source `127.0.0.2`; 1 proxy connection, 1 daemon connection, 9 HTTP requests. Direct connections would have source `127.0.0.1`; **0** observed. The proxy allowlists test targets and never uses DNS. |
| Proxy starts refusing after success | SOCKS request observed; server returns refusal; wallet reports no connection; **0 direct connections**. A daemon reset closes the prior working connection before the test. |
| Incorrect certificate pin | 5 proxied TCP/TLS connection attempts, **0 HTTP requests** and **0 direct connections**. This is authentication evidence, not data-integrity evidence. |
| Missing / duplicate transaction | Mock `/gettransactions` returns zero/two entries. `get_spend_proof` rejects both at `wallet2.cpp:12588`. Wallet remains callable, balance remains zero. |
| Invalid transaction encoding | One entry contains invalid hex; rejected by `get_pruned_tx` at `wallet2.cpp:12596`. No proof returned; wallet remains callable. |
| Truncated malformed JSON | Request fails at the zero-transaction count check. This is **not** evidence of strict JSON parsing: partial decoding reached the semantic count guard. |
| HTTP redirect | Mock daemon returns 302 to a second loopback observer. Wallet reports failure; **0 redirect-target connections**, **0 direct connections**. |
| Hostname handling | `observer.invalid` arrives intact in the SOCKS request and reaches the allowlisted TLS backend. This establishes proxy-side daemon-name handling; it does not prove absence of every DNS path in the process. |
| Configuration refusal | 15 cases exit 2 before creating state or contacting any observer: empty/hostname/nonlocal/zero-port proxy, cleartext clearnet, absent/bad pin, URL credentials/path/whitespace, malformed onion, trusted/config/auth overrides and abbreviated option. |
| Planted config files | Working directory and container HOME, `.bitmonero`, `.meownero` contain candidate wallet config files attempting to remove proxy/auth and enable trust. Startup still requires authentication, rejects trusted-only mining before sending anything, and dead-proxy requests reach no daemon. |
| Runtime controller boundary | Authenticated `set_daemon` accepts `trusted=true` and TLS disabled. Test restores pinned TLS before subsequent requests. Startup policy is not immutable runtime authorization. |
| OpenAlias boundary | With `--no-dns` present, `validate_address(allow_openalias=false)` emits **0** DNS queries; enabling it emits **10** DNS queries to our TCP resolver, including `privacy-observer.example.com`. No external resolution occurs. |

The SOCKS request count includes ordinary initialization/connection checks where
applicable; it is not a count of user transactions. Errors and aggregate counts
are retained; request bodies, wallet addresses, RPC credentials, seed phrases,
wallet files and disposable TLS keys are not copied into tracked evidence.

## Factual corrections and compatibility boundaries

1. **`--no-dns` is not a complete guard.** It sets `m_use_dns` in
   `wallet2.h:1817`; the pinned wallet RPC OpenAlias helpers do not consult it.
   `wallet_rpc_server.cpp:4649` calls
   `cryptonote_basic_impl.cpp:287`, then `dns_utils.cpp:460`.
   Other address-taking paths also call the URL resolver (`wallet_rpc_server.cpp`
   `:1049,:2462,:3269,:3317`); only `validate_address` was exercised here.
   The probe uses the upstream `DNS_PUBLIC=tcp://127.0.0.1` override for that
   disposable process only, avoiding the resolver's public probe/fallback path
   (`dns_utils.cpp:251–313`). The launcher does not claim to control this path.
2. **Default config loading is explicit at this pin.**
   `wallet_args.cpp:115,144–182` adds `config-file` with no default and parses it
   only under `command_line::has_arg`. The RPC entry point calls this parser
   before server initialization (`wallet_rpc_server.cpp:5081`). The launcher
   accepts no config-file or extra-argument pass-through. Planted-file tests
   corroborate the source; this finding is not portable to arbitrary versions.
3. **The pinned anonymity document has stale specifics.** Its literal
   `--daemon-cert-file` option is absent from the actual wallet descriptors;
   those provide `--daemon-ssl-ca-certificates` and
   `--daemon-ssl-allowed-fingerprints`. Its claim that peer timed-sync sends
   current wall-clock time does not describe the present message structure:
   `p2p_protocol_defs.h:247–274` has payload/peerlist fields without `local_time`,
   and `net_node.inl:2187` clears exported `last_seen`. This does not establish
   freedom from timing or other fingerprints. No comparative Tor/I2P safety
   claim is adopted from the older prose.

Primary code: [wallet RPC](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet_rpc_server.cpp),
[argument parser](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet_args.cpp),
[DNS resolver](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/common/dns_utils.cpp),
[P2P definitions](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/p2p/p2p_protocol_defs.h).
The [pinned anonymity document](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/docs/ANONYMITY_NETWORKS.md)
was freshly fetched on September 12 and hash-matched against the read-only source.

## Normative implementation choices and trust assumptions

These are bounded launcher choices, not newly settled product/consensus policy:
require a local numeric IPv4 proxy; refuse cleartext clearnet and TLS verification
bypasses; require an out-of-band trusted certificate fingerprint for HTTPS;
default the daemon to untrusted; allow no arbitrary upstream arguments. For
onion HTTP, the launcher checks modern 56-character address syntax only; the
trusted Tor proxy must validate/authenticate the onion service. The onion mode
itself has not been exercised against Tor in this track. I2P, IPv6 daemon
addresses, SOCKS credentials and CA-management UI are not implemented here.

The binary, host, local proxy and authenticated controller must be trusted.
The launcher does not verify the binary hash at startup; users/integration must
select the reviewed artifact. It does not protect against same-user malware,
mutable executables, malicious local proxies or packet-level egress from other
features. State remains sensitive even with private permissions and bounded
logs. No account system or telemetry is added.

Tor cannot prevent an adversary observing both ends from correlating traffic
timing; circuit reuse also permits associations between streams. These limits
remain even when direct fallback is absent. No Tor service, circuit rotation or
public network was used in this experiment.
[Tor Project, limitations and remaining attacks](https://support.torproject.org/about-tor/security/attacks-on-onion-routing/)
(checked September 12).

## Reproduce and integration handoff

Run in this worktree with a new output directory (the runner refuses reuse):

```sh
bash chain/privacy-test.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meow-swarm-privacy-your-unique-run
```

It requires the already available immutable builder
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.
The `/home/ubuntu` mount is specific to that builder's existing UID-1000 HOME;
the harness asserts that match. No host HOME variable or host service is changed.
`bash -n`, Python parsing and launcher `--help` were also checked. Host Shellcheck
was unavailable; no package was installed. Early scratch runs fixed container
UID permissions, the test client's connection-scoped Digest handling, and the
mock HTTP server's keep-alive handling; none was an upstream wallet fix.

Example launcher interface, using placeholders that must be supplied locally:

```sh
python3 chain/privacy-wallet-rpc.py \
  --binary /absolute/path/to/verified/monero-wallet-rpc \
  --state-dir /absolute/path/to/private/state \
  --rpc-port 19100 --proxy 127.0.0.1:9050 \
  --daemon https://your-reviewed-node.example:18081 \
  --daemon-fingerprint YOUR_OUT_OF_BAND_64_HEX_CERTIFICATE_SHA256
```

Final raw scratch evidence: `/tmp/meow-swarm-privacy-run-20260912-e` (disposable
keys/certificates remain there; do not publish that whole directory). Earlier
unique scratch directories `...-a` through `...-d` are superseded. Tracked
sanitized evidence is under `research/evidence/swarm-2026-09-12/privacy/`.

**Remaining integration:** parent application must enforce address/OpenAlias and
RPC-controller policy before claiming a mandatory proxy privacy mode. A process
egress boundary would need separate design and testing. False but well-formed
node data, eclipsing, adversarial reorgs, large/slow responses, memory/CPU denial
of service, funded private-transfer/decoy selection, CLI integration, daemon
P2P relay fallback and daemon synchronization traffic are outside these tests.
The proof-response tests exercise existing rejection checks on an empty wallet;
they are not an audit or proof of comprehensive malicious-node resilience.
No new upstream source patch is warranted solely by these bounded results.
