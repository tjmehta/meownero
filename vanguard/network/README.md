# Vanguard private network checkpoint

Start with [the source-bound launch sheet](launch-sheet.md) and
[operator preparation](operators.md). The current [profile](profile.json) is
`protocol-proposal`, not a usable network. Cryptography has accepted the
v1@0/v18@1/cutoff0 and explicit native one-zero-output genesis construction
directions for bounded implementation. The native helper now reproduces exact
genesis bytes/hashes and unchanged helper rejection controls. TESTNET admission,
maturity roots and final candidate acceptance remain unverified. See
[the bounded native result](native-result.md).

`python3 -B vanguard/network/network.py validate` checks an exact profile copy.
`check-source` verifies listed native source/pin bindings.
`identity-overlay` writes a TESTNET identity-only proposal patch to fresh scratch.
`genesis-inputs` exports the native public-input recipe and reversible TESTNET
activation/height-zero validation patch. `admission-overlay` combines that patch,
the dedicated identity and the bound native-derived genesis in fresh scratch.
This combined overlay is uncompiled/unadmitted and lacks selected-policy
integration. See [native preparation](native/README.md) for the next slot gate
and required native checks.
`prepare` validates an assigned loopback primary/recovery topology and writes
private proposal configs. Port aliases and superseded v17 profile bindings are
refused. `readiness` exits3. There is no launch command.

Preparation uses Python's standard library and Git. The bounded native runner
also uses the existing local Docker builder. Shared upstream source,
package/build/CI paths, lockfiles, wallets and services remain unchanged.
Tests require a task-owned private scratch directory; the actual pinned source
is needed for the full source/patch checks. Seventeen tooling tests pass; current
results live in [evidence/native-genesis-attempt01](evidence/native-genesis-attempt01).
The source lock and historical accepted trials retain their original meaning.
