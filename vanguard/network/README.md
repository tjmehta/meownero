# Vanguard private network checkpoint

Start with [the source-bound launch sheet](launch-sheet.md) and
[operator preparation](operators.md). The current [profile](profile.json) is
`protocol-proposal`, not a usable network. Genesis and native proof are unresolved.
The updated proposal uses Core's conditional v1@0/v18@1 direction with a
version-one cutoff of 0. Cryptography has not accepted a genesis construction.

`python3 -B vanguard/network/network.py validate` checks an exact profile copy.
`check-source` verifies listed native source/pin bindings.
`identity-overlay` writes a TESTNET identity-only proposal patch to fresh scratch.
`prepare` validates an assigned loopback primary/recovery topology and writes
private proposal configs. Port aliases and superseded v17 profile bindings are
refused. `readiness` exits3. There is no launch command.

These tools use only Python's standard library and Git. They do not modify the
upstream source, package/build/CI files, lockfiles, wallets or running services.
Tests require a task-owned private scratch directory; the actual pinned source
is needed for the full source/patch checks. Raw scoped results live in [evidence](evidence).
The source lock and historical accepted trials retain their original meaning.
