# Current private operator / seed recipe addendum for F1

This updates the funding, wallet recovery and capacity parts of `../operators.md`
for the finite lead-approved F1 milestone. That preserved preparation recipe and
its placeholders do not become a persistent launch command. Public launch and
launch_ready remain false. Persistent seed/operator assignments are still unknown;
no public listener, new host, paid capacity or package-writer change is authorized.

Use one dedicated profile per data directory. Never open a foreign, upstream,
historical, or unmanifested data directory with these binaries. Nonempty native
DB startup does not compare genesis; the accepted launcher manifest is an
ownership/history guard, not an independent native foreign-chain attestation.
Missing or changed manifest/profile/overlay/binaries/file inventory refuses before
launch. Preserve prior roots; never erase a database to turn a failure into PASS.

The prior zero-funding run on b6f54326 passed all16 functional rows, accepted by
lead as the early integration premise. Its nine-JSON archive is df4b39c2,
SHA25657180d6b62ff38ab8feedff832a4ca68bb620c2894c7f1f00331fb007dd609a2.
This is prior writer execution, not F1 or full independent acceptance. All earlier
grants are consumed. Reuse only the externally published retained authority3eedebc0,
root from run401698da/native-profile-attempt, manifest SHA2561b2815e21fb4c41ccd269e73f3eca3f905c872900e69d5a6d1c24537406275d6.
A locally recomputed manifest does not supply that authority.

Before execution, authenticate Platform→Core→Security source acceptances in order,
then the fresh exact grant and its at-least48h validity. Platform must confirm the
4.2h heavy-lock window has no other scheduled workload. Keep the original heavy
lock, both admissions, shared-capacity floors and one-attempt consumption. On
first-admission refusal, use at most3 separate wakes at least2h apart and at most
one existing monitor under the grant; do not poll or perform an early probe.
Output creation consumes the attempt permanently, even after a crash.

The reviewed candidate must run in a clean exact checkout. Preserve the seven
unowned caches in the managed worktree; use the established temporary exact
checkout route only inside the separately granted attempt. No source preparation
or build is part of this runtime-only reuse grant.

The eventual command below is a template, not execution authorization. The fresh
grant supplies the exact identifiers, hashes and fresh output. Its parent is an
owned mode0700 run directory; the controller log is private0600. Invoke setsid and
return from foreground waits within60s. Save the returned PID/start identity and
inspect only the exact controller receipt after it exits. A session ending must
not kill the detached attempt.

```sh
umask 077
setsid python3 -B vanguard/network/run-profile.py \
  --workload funded-two-peer-journey --inputs vanguard/network/integration/inputs.json \
  --grant-comment "$FRESH_EXACT_PLATFORM_GRANT" --artifact-sha256 "$EXACT_PACKET_SHA256" \
  --reuse-build "$PUBLISHED_RETAINED_ROOT" --out "$FRESH_OWNED_ATTEMPT_ROOT" \
  > "$OWNED_RUN_DIR/f1-controller.private.log" 2>&1 < /dev/null &
```

A/B start fresh. Only A mines through native startup flags, one thread in existing
RandomX light mode. Both peers use only each other's explicit loopback endpoints
in a network-none container. RPC stays loopback and authenticated. Signer wallets
are private full-key contexts with generated per-process login files; they are
never offered as observer services. Do not disable authentication or put a wallet
password, mnemonic, login or key in argv, public evidence or model context.

The driver creates disposable wallets using the accepted native one-shot CLI
setter/store/separate getter. For funded recovery it stops/stores/releases B,
queries its private mnemonic only inside the signer controller, restores in a
new owned root with explicit restore_height0, refreshes and matches the received
output and key image. It then stores/exits, verifies height0 with the unchanged
CLI getter, and reopens the restored signer. The later transfer must consume that
exact received key image and be confirmed on both peers. A balance match alone
cannot pass. The operator never opens seed, raw transcript, console, password or
login files. No simultaneous owner opens the same wallet file.

F1 stops on a mismatch, overshot target, N80 or deadline. Do not restart the
attempt, alter timestamps/difficulty, add funding, extend the cap, or reuse its
grant. On failure, retain only the exact owned staging for authorized same-run
local inspection. Follow the accepted redaction procedure: select traceback/log
cause locally, and inspect only the existing private redacted CLI skeleton for
CLI text (maximum2KiB verbatim in a cause comment). Never open raw wallet console,
seed/password/login files into model context. Do not add public filenames.

After confirming exact CID/label/anchored-name absence, remove the exact owned
staging in the same run. Report a failed deletion as failed and retain its root;
do not claim cleanup. Export only the eight closed row JSON files plus receipt
(and the existing tenth pre-runtime build diagnostic only when eligible; F1 has
no build phase). Withdraw nodes by stopping their owned process identities;
never signal an unrelated PID or change networking. The full two-seed/client
recovery topology, corruption controls, signed release and activation remain
subsequent separately reviewed work.
