# Clean fifteen-patch verification — September 12, 2026

**PASS: two clean historical-control builds reproduce in the same immutable
builder image.** This verifies the fifteen-patch **0.9 MEOW/120 s** source. It
is not evidence for selected 9/90 or fallback 12/120 binaries.

The resumed runner completed with exit **0**, and its final comparison passed.
Both raw source/build trees remain at
`/tmp/meow-swarm-network-20260912-run/reproduction/{first,second}`. No clean15
build container remained at collection. New evidence is confined to
[evidence/clean15-2026-09-12](evidence/clean15-2026-09-12/summary.json); the prior
pending-build reports and evidence remain unchanged.

## Independently checked provenance

The [collector](../spikes/network-benchmark/clean15-provenance.py) re-hashed the
actual files rather than trusting the success line. It verified all seven receipt
files byte-for-byte across builds: `BUILDER_IMAGE_ID`, `packages.txt`, `SHA256SUMS`,
`SOURCE_REVISIONS`, `SUBMODULES`, `INPUT_SHA256SUMS`, and `VERSIONS`.

| Item | Verified value |
|---|---|
| Applied source HEAD | `7410c04bab0e304112710d63c3225c110bd8b4de` |
| Source tree | `4db958cb96d72943c5c2433bd5f4a8f730037148` |
| Upstream | `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5` |
| Immutable builder | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Package manifest SHA-256 | `769dbcd72bac1dd528f5bd1833da29e0b788fdc50d9dee23791148ef6e6cd8d9` |
| Frozen input manifest SHA-256 | `6f74c265453e138cea3b3936542ef410ff3f0396ae561a8aa9a9f3eae7c3518e` |
| Compiler / CMake | GCC 13.3.0, Ubuntu `13.3.0-6ubuntu2~24.04.1`; CMake 3.28.3 |
| Executable version | `Monero 'Fluorine Fermi' (v0.18.5.1-7410c04ba)` |

All files listed by the frozen manifest still match. Each build's input receipt
contains exactly `upstream.lock` and fifteen patch files and matches those frozen
bytes. Live HEAD/tree, tracked cleanliness and six recursive submodule revisions
match the receipts. The 4,320 tracked file hashes agree across trees. Each tree
also has a new 2,228-file build inventory for subsequent preservation checks;
those inventories are collection-time hashes, not signed build attestations.

Actual daemon/CLI/RPC hashes agree with the receipts and across builds:

| Executable | SHA-256 in both clean builds |
|---|---|
| `monerod` | `63282e3c9705a55dfec3671f63d8485c9b07c8d8ad846ccbbe7bdb553b967cbe` |
| `monero-wallet-cli` | `15e55ac632b7800cc7dc7015920354205096fc9d90af1596f320c32c24f77956` |
| `monero-wallet-rpc` | `bc13d9d382a4ac69ef66f28ab433d945611a1a945ff4712c6c3167445aa835e4` |

Both test executables independently hash identically as well:
`unit_tests`: `862fe597c024ab7656f9e301e192c3aa6b1e5428555278688051fb0bd29d1e46`;
`meow_difficulty_floor_tests`:
`0b714b017f6b6c0ff80e20c6fabc717d71c45d87046a483c30277ed565631817`.
The collector reran executable/compiler/CMake version commands and queried the
immutable image's installed packages; they match the recorded versions/packages.

## Retained build and test receipts

[First build/test log](evidence/clean15-2026-09-12/first/build-and-tests.log) and
[second build/test log](evidence/clean15-2026-09-12/second/build-and-tests.log) each
record:

- **24/24** consensus/protocol tests selected by
  `meow_*:cryptonote_protocol_handler.race_condition`.
- **10/10** DAA/core tests at production floor one, and **10/10** in the separately
  compiled 150M-floor executable. These overlap the first selection; they are
  not 44 distinct tests.
- Successful disabled-update/DNS-blocklist-authority checks, working local bans,
  and disabled donation checks on all three networks using disposable unfunded
  wallets.

The complete compiler logs, CMake logs/caches and all receipts are retained for
both runs. The [combined log](evidence/clean15-2026-09-12/reproduction.log) and
[exit receipt](evidence/clean15-2026-09-12/reproduction.exit) record completion
around **23:27:29 UTC on September 12**, following the 22:30:45 UTC restart.
This collection verifies their recorded test outcomes; it does not claim another
full native unit-suite execution.

The frozen guard used the shared heavy lock, one compiler job, 4 GiB memory/no
swap and two CPUs. First/second preflights recorded respectively 10,570,704 and
11,442,460 KiB available RAM, with more than 5 GiB free disk. Ccache was disabled.
Compilation and authority/version containers explicitly disabled networking;
the frozen difficulty-test wrapper used Docker's default network mode. No
outbound workload is asserted for it, and blanket network isolation is not
claimed for every historical child container.

Independent collection ran in that immutable image with source/build and frozen
inputs mounted read-only, network disabled, 512 MiB/no swap, one CPU, and Git
optional locks disabled. To collect into another empty output directory:

```bash
# Mount the complete original run at /run-input:ro, this harness at /harness:ro,
# and an empty evidence directory at /out in the capped immutable image.
git config --global --add safe.directory '*'
python3 /harness/clean15-provenance.py --run-root /run-input --output /out
```

## Limits and selected-profile follow-on

This is same-image, same-host source reproducibility, not independent apt/compiler
reconstruction, cross-host reproduction, absence of bugs, launch readiness or
selected issuance validation. Executables remain in the preserved local raw
build trees; the committed artifacts are provenance and logs.

Selected builds use disposable copies of the verified first tree, apply the
coordinator's monetary overlay followed by its approved common fixture patch,
and verify `fixture-source-lock.json` against the original reward fixture first.
The approved fixture SHA-256 is
`360acc9ea7bd014225aa20ad93bee19c5f5444d126b36f93ffed0f913030f0e7`.
That subsequent incremental experiment is separately described under
[network benchmark](../spikes/network-benchmark/README.md). It does not change
this clean15 result, the production patch series, or the frozen historical input.
