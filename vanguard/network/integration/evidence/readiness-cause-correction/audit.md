Readiness cause audit — lead decision f287cb4f / bounded_readiness_decision

Baseline: exact 530205f7ee9ce949d191d3f70794a19cdf9e65ff. Pinned upstream
files were compared with their exact Git objects; see hypothesis-source-bindings.json.
No native process, Docker operation, capacity/admission check or original lock open ran.

| Hypothesis | Source and connected observation | Disposition |
| --- | --- | --- |
| Paired epee digest challenges | contrib/epee/src/http_auth.cpp:98,168,706–744 fixes realm monero-rpc, MD5 then MD5-sess and qop=auth. The local loopback fixture emits both separate WWW-Authenticate fields in that order and verifies the actual urllib Authorization digest, realm, nonce, URI, qop, nc and cnonce. Python 3.12.3 and 3.15.2 both authenticate and reject missing/wrong credentials. | Not reproduced. Keep the existing Digest handler and authenticated healthy-read controls. Fixture nonce/credentials and RPC body are disposable. This does not test the native epee HTTP server. |
| Restricted snapshot fields | src/rpc/core_rpc_server.cpp:300–347 supplies status, height, top_block_hash and wide_cumulative_difficulty even with restricted=true. :1577–1610 supplies pool hashes and stats, allowing only nonsensitive transactions under restriction. src/rpc/core_rpc_server_commands_defs.h:1698–1717 maps tx_hashes; :1760–1815 initializes txs_total=0 and serializes it within pool_stats. contrib/epee/include/serialization/keyvalue_serialization_overloads.h:88–100 deliberately omits empty containers. | Existing hashes.get('tx_hashes',[]) is required and correct. Source controls accept omitted empty hashes, reject each missing required field, wrong status/hash/height and nonempty hashes/stats. No payload predicate is relaxed. Actual previous RPC replies remain unobserved. |
| Genesis/height convention | src/cryptonote_core/blockchain.cpp:377–389 initializes an empty database with configured genesis. core_rpc_server.cpp:307–309 increments the top block index to chain height. profile.json:53–57, profile_contract.py:20 and evidence/native-genesis-attempt01/recipe1.json:14–18 agree on nonce424001 and exact hash885cb43cf51086063f15c94d2fb7f327e34c447de53c9c6291b1a86d6510dab6. | Genesis-only chain height is1. Retain the exact hash and height assertion. Recipe evidence is reused with its original attribution; no new native genesis computation or accepted running-state claim. |
| First-start initialization exceeds30s | The prior run4d5138f5 redacted-runtime-inspection.json records Core initialized/RPC started once, no initialization/bind failure and the outer READINESS_RPC TimeoutError. Published attachment4eb91777 (SHA256 d8f09beea6ca1eafb1c681321bc7a85613f32f109c8bd597ded7387bf61a1673) confirms runtime CLI1/container1, but contains no per-daemon LMDB/Core/RPC timestamps. Its local archive hash was reverified. Private staging was already deleted. | Inconclusive: no measured evidence warrants a larger timeout. Keep30s and the existing570+30s driver/runtime bounds. No private/raw log, wallet console, login, password or seed file was reopened. |

The Python3.12.3 primary implementation reads the first digest challenge and implements
MD5 qop=auth with nonce count/cnonce. See
[CPython v3.12.3 urllib.request](https://github.com/python/cpython/blob/v3.12.3/Lib/urllib/request.py#L1006-L1087)
and [official urllib documentation](https://docs.python.org/3/library/urllib.request.html#urllib.request.HTTPDigestAuthHandler).
The independent MD5 computation in the actual local HTTP fixture verifies this rather
than assuming support for the unsupported MD5-sess alternative.

Changed behavior and export boundary

Only RPC.call(), wait() and snapshot() in the frozen driver change. The actual
RPC methods, URLs, Digest manager, request bodies, retries, timeout, genesis/pool
predicates and raw401 auth controls stay the same. RPC.call preserves its original
RuntimeError class for HTTP failures and chains the original HTTPError privately.
Available HTTP response/error status is numeric. Snapshot annotates the operation
whose call, required field or fixed guard failed. wait retains the last retryable
exception and total attempt count, then raises the same readiness TimeoutError
with that exception as its private cause. A transient failure can still recover.
No cause was established by these hypotheses, so there is no speculative client
or daemon behavior fix.

integration/runtime_diagnostics.py extends its existing three-key closed schema
with one optional readiness object of exactly six keys: operation, exception_class,
http_status, require_label, key_field, attempts. Operations and exception/guard/field
names come only from fixed tables. Unknown names map to fixed OTHER tokens; status
is an integer100–599 or0 when unobserved; attempts is integer1–1000000 (booleans
refused). Unknown keys, bodies, text, credentials and invalid ranges refuse export.
The observer's frozen line anchors move by the exact25-line source delta. The
existing controller validator copies only a valid object into receipt.json. No new
public evidence filename or private retention/deletion policy is introduced.
Only the existing private0600 failure-traceback can contain the complete exception
chain. The unchanged controller enforces its existing bound on the diagnostic file.

Connected controls and fidelity

357 full guarded source tests pass,0 failures/errors/skips,62.318s, including78
direct controller checks. ResourceWarning is an error. Tests connect actual driver
snapshot/wait -> final TimeoutError -> actual main observer -> private traceback,
and separately validate actual controller receipt collection. HTTP transport/errors,
JSON error replies/malformed JSON and available200/503 statuses have closed causes.
Each required snapshot key and unchanged chain/pool guard is checked. Tests retain
transient recovery, current cause/attempt count, reject unknown fields/ranges and
exclude dummy PRIVATE_SECRET strings from public codes. The exact530205f7 wait
fails the identical cause-preservation control: no cause chain or readiness object.
Its expected known-bad observation remains in the passing connected test, not a
native diagnosis. Docker/native/clock/admission effects in the suite are fixtures;
the paired-challenge test instead uses a real disposable loopback HTTP server and
the actual client on both Python versions. This is source qualification only.

The reused guarded launcher denies the original heavy lock by exact path and
66306/657237 device/inode before builtins/io/os opens and before flock. Final
metadata is identical and zero protected touches occurred. Every fixture lock is
disposable. The baseline353 checks are not claimed as an independent new reviewer
result; the writer's new357 count is this run's observed suite. Previous native
failure remains ATTEMPTED_FAIL and is not reclassified by source controls.
