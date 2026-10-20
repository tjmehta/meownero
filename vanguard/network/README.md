# Vanguard private network checkpoint

Start with [the source-bound launch sheet](launch-sheet.md) and
[operator preparation](operators.md). The current [profile](profile.json) is
`protocol-proposal`, not a usable network. Cryptography has accepted the
v1@0/v18@1/cutoff0 and explicit native one-zero-output genesis construction
directions for bounded implementation. The native helper now reproduces exact
genesis bytes/hashes and unchanged helper rejection controls. Genuine TESTNET
genesis admission, zero accounting, stored commitment, v18 next-block state,
reopen and second-database agreement now pass. Mature roots, full network behavior
and final candidate acceptance remain open. See [the admission result](admission-result.md)
and [the earlier helper result](native-result.md).

The [current-lineage 9/90 preparation](selected-policy.md) adds a separate frozen
ten-file policy overlay and an executable bounded native test runner. The
[Core consultation response](projection-correction.md) restricts adjusted-time
projection changes to dedicated TESTNET and retains inherited v18 unlock rules.
Fourteen source/admission-guard checks pass; the overlay has not been compiled or
run. The profile digest and accepted genesis evidence stay unchanged. The unused
platform grant binds the prior artifact and needs an explicit update before
executing the corrected candidate. Native peer/wallet proof and independent
acceptance remain open.

`python3 -B vanguard/network/network.py validate` checks an exact profile copy.
`check-source` verifies listed native source/pin bindings.
`identity-overlay` writes a TESTNET identity-only proposal patch to fresh scratch.
`genesis-inputs` exports the native public-input recipe and reversible TESTNET
activation/height-zero validation patch. `admission-overlay` combines that patch,
the dedicated identity and the bound native-derived genesis in fresh scratch.
This combined overlay passed the bounded genesis admission witness and still
lacks selected-policy integration. See [native preparation](native/README.md)
for the consumed slot and remaining native checks.
`prepare` validates an assigned loopback primary/recovery topology and writes
private proposal configs. Port aliases and superseded v17 profile bindings are
refused. `readiness` exits3. There is no launch command.

Preparation uses Python's standard library and Git. The bounded native runner
also uses the existing local Docker builder. Shared upstream source,
package/build/CI paths, lockfiles, wallets and services remain unchanged.
Tests require a task-owned private scratch directory; the actual pinned source
is needed for the full source/patch checks. Seventeen tooling and six provenance
checks pass; current results live in
[evidence/native-admission-attempt01](evidence/native-admission-attempt01).
The source lock and historical accepted trials retain their original meaning.
