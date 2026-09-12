# Resumed mining checkpoint — September 12, 2026

**Selected-family source adaptation passes; stock P2Pool remains incompatible.**
This is a local engineering checkpoint for selected **9 MEOW/90 s**, with gated
**12 MEOW/120 s** fallback. Both target 3,153,600 MEOW/year before penalties.
Neither profile passes network/FCMP/release gates through this work. There is no
working pool, daemon integration or demonstrated payout.

TJ's resumed implementation authorization supersedes the earlier closed track.
The decision and latest handoffs were read from coordinator root
`<repo>/research/`; this worktree predates that
selected-policy update. The coordinator's `spikes/selected-issuance` overlays
were consumed read-only. Production patches, frozen clean15 inputs, historical
mining evidence, daemon sources and real keys were not modified. No agents,
services, external messages, push, publication or spending were involved.

## What is implemented and executed

[Runner](../spikes/p2pool/run-selected.sh),
[generator/tests](../spikes/p2pool/selected_probe.py),
[isolated gate](../spikes/p2pool/selected_gate.inc), and
[additional source pins](../spikes/p2pool/selected-source-lock.json).
The P2Pool pin remains `9bac5bdd6c5a729a2c3824430c2aeb6049faa8e4`.

- Compile actual pinned `get_base_reward`, changing only its declining formula
  to the selected overlay's flat constant. Tally values from zero through u64
  saturation no longer affect subsidy. Genesis mining requests are refused by
  the surrounding gate; the primitive itself is not a genesis constructor.
- Compile unchanged `SideChain::network_major_version` against the hash-pinned
  actual Meownero fork table: version 1 at height 0, version 16 from height 1.
  No fabricated fork table or version override is used.
- Compile unchanged P2Pool weight-penalty routine and its native `umul128` /
  `udiv128` helpers. The wrapper applies the pinned v16 weight floor, refuses
  medians at or above 2^32 and excessive weights, then checks fee-addition
  overflow. Its median-domain refusal is an explicit local adapter restriction,
  not a new daemon consensus rule. Fees remain unpenalized in tested quotes.
- Compile the actual `Wallet::decode` body with regular mainnet prefix 120 and
  subaddress prefix 123 substituted. The surrounding gate accepts only regular
  mainnet addresses. Its 95-character format works for mainnet's one-byte
  prefixes; this does not implement testnet/stagenet varint prefixes. The
  decoder's checksum and point-decompression checks execute using pinned
  P2Pool Keccak routines and actual linked upstream crypto-ops C files.
- Remove only the decoder's **non-enforcing informational FCMP torsion warning**
  from this source slice. It is not replaced with a fake successful crypto
  implementation. This omission makes **no FCMP/torsion compatibility claim**.
  Curve membership does not establish subgroup or intended-proof readiness.
- Compare supplied genesis and experimental profile/sharechain identity before
  accepting an address or quoting a reward. The genesis constant is tied to
  the hash-verified historical mainnet RPC receipt; both overlays leave genesis
  parameters unchanged. No new selected daemon genesis was fetched. The
  profile digest binds that genesis, reward, spacing, prefix, weight floor,
  configuration, overlay and fork-table hashes in a probe-only domain.

These identity comparisons are an executable local boundary, **not a real
RPC/peer authentication or serialized share validation test**. A caller supplies
the observed identity strings. The two selected profiles share the preserved
chain genesis and address namespace, so genesis/address alone cannot distinguish
issuance policy. Their experimental share IDs differ and cross-profile attempts
are rejected. These IDs are not P2Pool's RandomX-derived consensus identifiers,
not integrated into share hashing/discovery, and not a selected launch identity.

Generated source and adaptation diffs are retained for
[selected](evidence/resume-mining-2026-09-12/selected-9-90/adaptation.diff) and
[fallback](evidence/resume-mining-2026-09-12/fallback-12-120/adaptation.diff).
The fork lookup body is unchanged; its linked table changes from pinned Monero
to pinned Meownero. Small class/state declarations and a memcpy load adapter
replace infrastructure dependencies. No reward or cryptographic result is
stubbed. C++ source slices use UBSan with recovery disabled; linked crypto-ops
C objects are compiled normally and are not claimed to be sanitizer-audited.

## Verification and evidence

[Complete summary](evidence/resume-mining-2026-09-12/summary.json),
[run log](evidence/resume-mining-2026-09-12/run.log),
[preservation/syntax checks](evidence/resume-mining-2026-09-12/checks.json).

| Executed checks | Result |
|---|---|
| 9/90 independent integer-oracle grid | 2,520/2,520 |
| 12/120 independent integer-oracle grid | 2,520/2,520 |
| Identity, address, fork, fee/domain controls | 31/31 per profile |
| Recompiled historical stock reward/fork controls | 7/7 |
| Stock address decode, valid Monero / refused Meownero | 2/2 |
| Stock reward/fork mismatches at selected tally boundaries | 6/6 per profile |
| Actual stock parser minimum-reward guard, extracted alone | 5/5 per profile |
| Deliberately wrong source digests refused | P2Pool, daemon, overlays |
| Overlay reverse application restores exact original bytes | Both profiles |

The oracle grid varies five heights, seven tallies, four medians, nine weights
and two fee amounts. It includes saturated tally, 1.125/1.5/1.875-median weights,
near-zero subsidy, zero subsidy and excessive-weight refusal. At a 1.5-median
weight, subsidy is 6.75 or 9 MEOW; selected supply saturation does not stop it.
First unpenalized saturating blocks are 2,049,639 and 1,537,229 respectively.
This is reward continuity, not verification of aggregate consumers.

Controls reject absent/wrong genesis, absent/cross-profile share ID, all three
stock default/mini/nano IDs, Monero/testnet/stagenet/subaddress/integrated payout
addresses, invalid alphabet, truncated strings, a bad checksum, checksum-valid
invalid points, genesis mining, wrong fork versions, unsupported median domain
and fee overflow. Positive controls include the existing public Meownero fixture,
maximum representable fee-inclusive amounts and the valid stock Monero address
constructed from the same public keys. No private keys are used.

Raw vector inputs and results are stored as deterministic gzip files; control
labels, generated translation units and profile manifests are alongside them.
The summary's vector/result hashes apply to **decompressed** bytes. The final
[evidence manifest](evidence/resume-mining-2026-09-12/manifest.json) hashes stored
artifacts and authored harness files. Authored files pass whitespace checks;
raw generated upstream source and unified-diff context retain their original
whitespace. All consumed pinned sources and overlays
were rechecked after testing. No full production suite was rerun for this spike.

## Payout boundaries

The pinned source still needs integration across template construction,
serialization, share validation, output derivation and actual wallet receipt.
This checkpoint does not adapt `split_reward`, build PPLNS windows or demonstrate
low-hashrate share discovery, credited shares, paid outputs, maturity or recovery.

- A single full selected reward takes **7 varint bytes**, versus **6** for the
  historical 0.9 reward. Both fit the pinned per-output maximum `(1<<56)-1`.
  This is amount-encoding arithmetic, not executed coinbase/output construction.
  Actual split amounts may have other sizes; all output-size accounting paths
  still need integration tests.
- The actual isolated stock parser guard rejects total reward below 0.6 MEOW.
  The selected penalty function can legitimately quote below that, including
  zero subsidy at twice median weight. Stock documents this as a transaction
  selection/share policy. Replacing that guard with 9 or 12 would additionally
  reject every fee-free penalized selected reward. No replacement share minimum
  is silently chosen here; the new quote gate does not claim share acceptance.
- One unpenalized 9/90 block mismatches stock's roughly 35.18 initial reward;
  12/120 mismatches too. At saturated tally stock returns 0.6, while the adapted
  profiles continue 9 or 12. Stock's height-1 fork lookup still returns version 1.
  RPC field compatibility alone fixes none of these differences.
- Mainchain timing assumptions elsewhere in P2Pool, share difficulty, stale
  policy, peer discovery, consensus-ID derivation, FCMP/merge-mining paths and
  payout fairness remain open. No pool settings, hashrate guarantee, economic
  security claim or purchasing-power assumption is supplied.

## Reproduction and resources

```sh
bash spikes/p2pool/run-selected.sh \
  /tmp/meow-swarm-mining-p2pool-source \
  /tmp/meownero-wallet-verified-source-20260912 \
  <repo>/spikes/selected-issuance \
  /tmp/meownero-mining-selected-NEW_EMPTY_DIRECTORY
```

Final successful run: `/tmp/meownero-mining-selected-20260912-final`, exit 0.
Builder remains immutable image
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`,
GCC 13.3. Inputs/root filesystem read-only, no network, no exposed ports, one
compiler job, 512 MiB memory, no swap, half a CPU and low CPU shares. Observed
cgroup memory peak was 78,647,296 bytes (about 75 MiB).

An initial lock-taking attempt yielded exit 75 before compilation. The runner
then used TJ's explicit <=512 MiB lightweight exception, also confirmed by the
coordinator, leaving the existing heavy lock with network reproduction. No heavy
work or resource-gate bypass was performed. A full pool build would still require
the shared heavy lock, network priority, >=5 GiB available preflight, one compiler
job and the <=4 GiB/2 CPU limits. No host service was changed to free resources.
