# Native genesis prerequisite

The [Cryptography ruling](<private-tracker>/TJS/issues/TJS-2504#comment-3b6c0197-43f9-4c30-a90c-399f82fc0b57)
accepts implementation of the proposed construction and v18 activation. It does
not accept absent genesis bytes or the final candidate. The code here is
**prepared, uncompiled and unexecuted**. There is no native result yet.

`genesis.cpp` uses the pinned native crypto and transaction/block serializers.
Its recovery inputs are the public canonical little-endian scalars 1,2,3 for
spend, view and transaction keys. Native derivation at output index0 produces
the sole zero-valued `txout_to_key`. These inputs are valueless public fixtures,
not private wallets or release signing keys. The transaction is explicitly v2,
RCTNull, input height0 and unlock60. General amount decomposition stays unchanged.

It checks the native amount-zero map entry and coinbase commitment equal G
(`58` followed by31 `66` bytes), native output/commitment collection and unchanged
torsion rejection. Adverse controls exercise identity, small-order, malformed
and a validly encoded historical torsion-bearing point in both output and
commitment positions. They are helper checks, not block admission. Native
legacy leaf conversion records O/I/C; it does not establish a scheduled or
persisted tree root. Native genesis construction records the actual nonce,
full block/transaction bytes and hashes with exact parse/serialize roundtrips.

Prepare source and the reversible prerequisite patch without starting anything:

```sh
python3 -B vanguard/network/network.py genesis-inputs \
  --source "$PINNED_UPSTREAM_SOURCE" --out "$TASK_PRIVATE_SCRATCH/genesis-inputs-new"
```

This exports `native/CMakeLists.txt`, `native/genesis.cpp`,
`activation-genesis-admission.patch` and a source/profile-bound receipt. It
refuses foreign source or an existing output directory. The patch changes only
the TESTNET fork table/cutoff and TESTNET height-zero reward validation. Its
shape check continues through the existing exact-coinbase and torsion code;
there is no early success or FAKECHAIN exception. The first rewarded block is
height1, even though its previous generated-coins balance is also zero.

The patch deliberately omits the still-unproduced genesis blob and selected
9/90 implementation. It must not be treated as a completed network overlay.

Before compilation, obtain the platform owner's idle-slot reply to
[the resource request](<private-tracker>/TJS/issues/TJS-2504#comment-80fd656e-4d6b-4547-a8d5-3ebd8b41f5d3).
That owner is currently active on the native package task. No build slot has
been confirmed. The existing source and builder are read-only inputs; never
reconfigure or copy generated files into that source, its cache or another
writer's worktree. No build has run here, including syntax-only compilation.

After slot assignment, use one private task-owned clean source staging tree and
the existing contained builder/offline dependencies. Add this target directory
to that private tree after its ordinary tests. In the admitted container only:

```sh
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release \
  -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF \
  -D MANUAL_SUBMODULES=ON
cmake --build /src/build/network --target vanguard_network_genesis --parallel 1
/src/build/network/tests/vanguard-network/vanguard_network_genesis \
  > /out/recipe.json 2> /out/recipe.stderr.log
```

The private test-directory name must be `tests/vanguard-network` for the path
above. The builder/staging driver still needs the platform's confirmed input
paths and provenance; this command sequence is unexecuted preparation. Record
the clean source/submodule trees, added test CMake line, helper and patch
digests, toolchains, native executable hashes, complete stdout/stderr and exit.
Do not present cached object reuse as a full clean build. Use the shared
nonblocking heavy lock, >=5GiB memory/disk admission, network-none, no published
ports, 2CPUs/4GiB/no swap/256PIDs, one compile job and a900s attempt deadline.
Retain a failed attempt before changing anything. Clean only exact owned
containers/staging build output after retaining diagnostics.

On successful helper execution, compare two recipe outputs byte-for-byte and
bind them to the exact source/build inputs. The result is only
`PASS_NATIVE_RECIPE_HELPERS_ONLY`. Do not update the profile to accepted or
launchable from that result. Next integrate the exact native-derived bytes into
the isolated TESTNET configuration, exercise real fresh LMDB admission without
FAKECHAIN/test-options, and capture zero generated coins, persisted commitment,
scheduled maturity/root state and explicit negative genesis variants. Then
complete the selected-policy differential vectors and full native two-peer,
wallet/payment/restore/later-spend and adverse consensus checks described in
the launch sheet. No public activation or independent acceptance follows from
this prerequisite.
