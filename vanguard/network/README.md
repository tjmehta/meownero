# Vanguard private network checkpoint

Start with [the source-bound launch sheet](launch-sheet.md) and
[operator preparation](operators.md). The current [profile](profile.json) is
`protocol-proposal`, not a usable network. Cryptography has accepted the
v1@0/v18@1/cutoff0 and explicit native one-zero-output genesis construction
directions for bounded implementation. Exact genesis bytes, admission, maturity
roots and the final native candidate remain unverified.

`python3 -B vanguard/network/network.py validate` checks an exact profile copy.
`check-source` verifies listed native source/pin bindings.
`identity-overlay` writes a TESTNET identity-only proposal patch to fresh scratch.
`genesis-inputs` exports the native public-input recipe and reversible TESTNET
activation/height-zero validation patch. They are prepared source, uncompiled
and unexecuted. See [native preparation](native/README.md) for the build-slot gate
and required native checks. This is still missing selected-policy integration.
`prepare` validates an assigned loopback primary/recovery topology and writes
private proposal configs. Port aliases and superseded v17 profile bindings are
refused. `readiness` exits3. There is no launch command.

These tools use only Python's standard library and Git. They do not modify the
upstream source, package/build/CI files, lockfiles, wallets or running services.
Tests require a task-owned private scratch directory; the actual pinned source
is needed for the full source/patch checks. Fifteen tooling tests pass; raw
current results live in [evidence/consultation-applied](evidence/consultation-applied).
The source lock and historical accepted trials retain their original meaning.
