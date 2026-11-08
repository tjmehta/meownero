# Privacy consultation response, 2026-10-20 UTC

Execution update, October 20 13:08 UTC: the platform rebind was obtained and its
single finite grant is now consumed. The corrected core/helper target passed
twice on approved checkout `a1558795663e5999785a5586bf6c755c7826071a`;
see [the native result](policy-result.md). Native projection, unlock/maturity,
peer/wallet and final-review requirements below remain open. The original
consultation/pre-execution account below retains its historical timestamp.

The independent [Privacy/Cryptography ruling](<private-tracker>/TJS/issues/TJS-2504#comment-92c3db8f-40a3-483e-99f1-4975701a59c8)
confirms the inherited v18 nonzero-unlock restriction and the foreign-selector
projection correction. The [Core response](projection-correction.md) already
implements that correction in `2417930cc649f24e1ba4b175a95f4ede28e6c42d`.
Both scoped source consultations are complete. Native checks and full-candidate
acceptance remain open; public launch stays disabled.

Privacy reviewed `ebb953530ecfc3bf712e9cb08e042cf11b7f272c`, overlay SHA256
`0f971c34e3401f2faf85fa98862f7f28698af3b5ee28765c17657f8bee5eb044`.
The corrected overlay SHA256 is
`32c40224dcd618995ef4d846cab411a85783314da79a803ed16074241780312c`.
Its [correction receipt](evidence/projection-correction/correction.json) records
that only `src/cryptonote_core/blockchain.cpp` differs between those overlays.
This documentation update changes neither overlay nor its runner, native target,
profile, genesis, source lock or crypto pins. The platform grant must still name
the exact approved checkout/artifact before execution; matching implementation
inputs alone provide no authority.

## Preserved rules and evidence limits

At upstream `e151643c5269c83bf24a83b2548e2493876026b2`, ordinary transactions
with nonzero unlock are rejected from v17 before proof processing. Dedicated
TESTNET uses v18 from height one. Preserve that rule through pool, supplement,
main-chain and alternative-chain paths, including their verified-fork caches.
Keep the separate coinbase requirement of exact height+60, including genesis
unlock60. No epoch, timestamp conversion, persisted lock bucket, proof rule or
consensus ban is added.

Privacy's verifier SHA256
`3b3b30d582589b7488837a101bcdf91a02b71f7544a1d6a5029221a5f20ee780`
was independently checked against local working bytes and the pinned Git object
for `src/cryptonote_core/tx_verification_utils.cpp`. Fourteen existing policy
source/runner checks passed again, including patch reconstruction, inherited
unlock/coinbase checks, foreign projection and known-bad projection/median
controls. These checks do not execute C++, wallet, LMDB or peers.

## Native acceptance still required

Privacy's requirements supplement [Core's native matrix](core-review/lock-consultation.md).
Every row below remains NOT_RUN for the corrected full candidate.

| Boundary | Required observation |
| --- | --- |
| Ordinary unlock | Otherwise valid funded unlock0 succeeds. Values1,499999999,500000000,current timestamp and UINT64_MAX reach the explicit nonzero-unlock guard and fail. A malformed-proof rejection is insufficient. Retain Core's additional timestamp-anchor cases. |
| Admission and cache | Direct supplement, kept-by-block, alternative-chain and stale pre-fork pool/cache paths refuse nonzero unlock before outputs persist. Valid PoW/root controls isolate the guard; rejected inputs leave roots and DB unchanged. |
| Maturity and coinbase | Positive controls and before/at/after wallet count L+1. At bounded creation index b, ordinary L=b+9 and coinbase L=b+59. Preserve exact coinbase lock, reward, point/torsion and proof checks. |
| Wallet | Online/offline fork selection, restore/rescan and input selection agree on dedicated v18@1, zero-unlock construction, custom-unlock refusal and path/spendability data. RPC restriction alone is insufficient. |
| Persistence and isolation | Two peers agree across restart/catch-up, detach/replay and rebuild on block hashes, roots/layers, unified IDs, locked/custom-lock tables and membership paths. Refuse foreign genesis/profile/DB/checkpoint/bootstrap material. Then prove receive/payment/restore/later spend. |
| Projection | Native heights59/60/61, monotone/equal/reordered/skewed windows, outliers, rounding and future-time rejection; compare foreign v1/v2/v18 with upstream. Preserve the below60 wall-clock fallback and in-place median sorting before maximum selection. |

The maturity argument is bounded to b+60<500000000. It does not establish
unbounded-lifetime assurance or FCMP timestamp spendability. The dedicated
mature-window projection is min(median+2745,max+90); foreign projection retains
upstream120, including v1. Projection arithmetic is separate from spendability.

## Next capability and owner

The existing [platform rebind request](<private-tracker>/TJS/issues/TJS-2504#comment-e7783dc0-d0d2-4b10-816c-d45e04b67ab5)
still awaits a response. The old unused grant binds the prior overlay and is
refused before output creation. P2P/Mining owns obtaining the exact corrected
artifact binding, then fresh original-inode/resource/collision admission, the
same one finite helper/template attempt and cleanup receipts. This consultation
adds no workload to that grant. No native runner, staging, container, listener,
wallet, host reservation or current resource admission was created for this wake.

After that narrow attempt, broader native peer/wallet evidence still requires
appropriate platform admission and independent Core/Security stages, followed by
accepted-only lead integration. Needs TJ: None.
