# Native genesis prerequisite

The [Cryptography ruling](<private-tracker>/TJS/issues/TJS-2504#comment-3b6c0197-43f9-4c30-a90c-399f82fc0b57)
accepts implementation of the proposed construction and v18 activation. It does
not accept exact genesis bytes or the final candidate. The helper was built
from exported pinned source and passed twice, with byte-identical recipe outputs.
See [the result](../native-result.md). The combined TESTNET admission overlay
now passes the bounded real-core genesis witness; its stored root is immature
and unavailable. See [the admission result](../admission-result.md).

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

The `genesis-inputs` patch omits the genesis blob and selected9/90 implementation.
`network.py admission-overlay` now adds the bound native-derived bytes and
dedicated identity to those prerequisite changes. Both commands only write
fresh scratch outputs. Neither produces the completed selected-policy overlay.

The platform owner's [local-slot reply](<private-tracker>/TJS/issues/TJS-2504#comment-2d70177d-b7a7-4ef6-8079-242320bdcb1f)
permits one bounded local attempt after fresh admission. It covers the local
default Docker daemon only; the native package task's separate ARM guest remains
outside this slot. The existing source and builder are read-only inputs; never
reconfigure or copy generated files into that source, its cache or another
writer's worktree.

That helper attempt is complete. The subsequent
[platform grant](<private-tracker>/TJS/issues/TJS-2504#comment-15414082-2a53-4872-8d19-b87f302f0bae)
allowed one new local admission attempt after fresh nonblocking admission. That
attempt is now complete; no grant or host reservation remains. Task-owned
source/build/Cargo staging and stopped databases were archived as needed and
removed. Commands below document the executed one-shot recipe, not current
authority to rerun it. A future attempt needs fresh coordination and staging.

`../run-admission.py` implements that separate window. It verifies every original
archive member in the task-owned export, refuses unexpected source paths,
checks the copied Cargo inputs and prior helper binary, records hashes of reused
objects, and applies only the committed three-file admission overlay. It reuses
the task-owned incremental build; it is not a clean rebuild. Shared source/cache
and package paths are never writable mounts. It keeps the same host lock through
exact-container removal and records load, memory, disk, process/container
collisions, limits, toolchains and complete failures. Failed admission creates
no container and does not wait for capacity.

```sh
python3 -B vanguard/network/run-admission.py --out "$TASK_PRIVATE_SCRATCH/admission-attempt-new"
```

`admission.cpp` initializes actual TESTNET with null test options, offline/DNS
disabled/fast-sync disabled and no fixed difficulty. It checks height, genesis
bytes/hash, zero generated coins, stored output/commitment/origin/unlock data,
scheduled tree metadata and next-block v18 state, then reopens and compares a
second independent fresh database. A zero-layer immature root is explicitly
unavailable, never an accepted mature root. This is database agreement, not
two-peer networking. Separate fresh negative cases exercise the native public
`reset_and_set_genesis_block` API after ordinary initialization; they do not
claim alternate-config initialization. Each case has a 45-second limit. Raw
logs and exits survive every failure. Selected 9/90 policy, maturity/funding,
two-peer continuity, wallet and operator acceptance remain separate requirements.

`../run-genesis.py` implements this grant. It opens the existing host lock
without creation/truncation, checks the platform-recorded device/inode and takes
it nonblocking. Under that lock it checks native processes/containers and at
least5GiB available memory/disk, exports the pinned Git and five submodule
objects, copies Cargo registry/Git inputs without hardlinks or credentials,
verifies the two Rust checkout pins and checks the toolchain. It never uses the
shared source's dirty test CMake or cached build objects.

```sh
python3 -B vanguard/network/run-genesis.py --out "$TASK_PRIVATE_SCRATCH/native-attempt-new"
```

The output must be a fresh leaf below an owned private parent outside a Git
checkout. The runner uses the explicitly granted local input paths. It records
source archive/cache/helper digests, toolchains, actual commands, raw configure/
build/helper logs, recipe repetition and container state/cleanup. Source pins
are rechecked after the attempt. One task-named container gets the exact granted
caps, network-none/no ports and read-only toolchain. Host supervision reserves
the last20 of900 seconds for cleanup. Only its returned container ID/cidfile is
used for cleanup, under the same host lock. Lock contention refuses before
Docker creation. There is no automatic retry; any resource, dependency or time
failure must retain diagnostics and return to the platform owner for the next
bounded action. A successful helper is still not TESTNET admission.

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
above. The runner stages this exact command sequence using the platform's
confirmed inputs. Record
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
