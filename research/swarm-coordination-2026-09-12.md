# Local parallel engineering — 2026-09-12

**Subsequent update:** all five existing workers acknowledged TJ’s selected 9/90 direction, gated 12/120 fallback and adoption-evidence limits. [Decision and distribution receipts](decision-2026-09-12-issuance.md). Recommendation-only language below records the earlier checkpoint, not current policy.

TJ explicitly requested focused Codex/Herdr sessions implementing the latest
research. The coordinator read the complete external research note
`<private-notes-path>`
and the [verified handoff](handoff-2026-09-12-resumed.md). This work starts from
`39070e8`, which includes `81b3182`; closed evidence is preserved.

## Ownership and verification

| Session / pane | Branch (all prefixed `swarm/20260912-`) | Owned paths | Deliverable and stop condition |
|---|---|---|---|
| `meow-network` / `wB:p1` | `network` | `chain/build.sh`, `chain/test-reproducibility.sh`, new `chain/network-*` / `chain/test-network-*`, `spikes/network-benchmark/` | Two clean current-series builds with hashes; actual P2P/adversarial measurements; matched issuance/capacity harness; explicit FCMP integration boundary |
| `meow-privacy` / `wC:p1` | `privacy` | new `chain/privacy-*`, `wallet/metadata/` | Distinct RPC/relay/sync observer map; tested fail-closed controls and malicious-node/leak cases; state untested observers |
| `meow-mining` / `wD:p1` | `mining` | `spikes/p2pool/` | Source-pinned isolated PoC, or executable compatibility probes identifying the exact adaptation boundary |
| `meow-rust` / `wE:p1` | `rust` | `spikes/cuprate/` | Source-built bounded module differential tests, source/corpus/toolchain provenance and parity/readiness limits |
| `meow-demo` / `wF:p1` | `demo` | `demos/private-payment/`, `docs/brand/swarm-2026-09-12/` | Actual disposable private-payment demo and recovery where feasible; scoped optimization materials and referenced storyboard directions |

Each worker owns `research/swarm-<track>-2026-09-12.md` and its directory under
`research/evidence/swarm-2026-09-12/`. Worktrees live at
`/tmp/meownero-swarm-20260912-<track>`. Workers commit explicit owned paths; the
coordinator reviews and integrates commits and owns shared CI, milestone,
specification and handoff changes. No further delegation is needed.

At startup the host had 12 logical CPUs, approximately 5.8 GiB available RAM,
nearly full swap and 39 GiB free disk. Heavy operations serialize with
`flock /tmp/meownero-swarm-20260912-heavy.lock`, one compiler job and at most
4 GiB container memory / two CPUs; large builds require at least 5 GiB available
before starting. The network reproduction has priority. Lightweight research
continues independently; other simultaneous test workloads are limited to
512 MiB each or use the same lock. No existing services are stopped and no host
packages, runtime configuration or caches are changed. The original reproduction
trees and verified source tree are read-only inputs.

## Integration acceptance

- Inspect actual changed behavior and callers, not only the worker summary.
- Preserve all fifteen production patches and the verified seed recovery unless
  a separately reviewed change is necessary. A test candidate is not a production
  economics change.
- Require reproducible commands, source identities, meaningful negative controls
  and evidence identifying what was measured. A skipped integration is an open
  item, not a passing full-system result.
- Match issuance per second and capacity per second for the 90/120 comparison;
  distinguish configured workload budgets from enforced consensus limits. Record
  cache state, hardware, toolchain, topology and proof type. Simulated FCMP costs
  cannot substitute for integrated FCMP blocks.
- Inspect evidence for disposable secrets and unneeded identifying data before
  committing it. No account, telemetry or address/IP acquisition funnel.
- Separate source-backed factual corrections from normative choices. Component
  audit, language choice, pool architecture and social reach do not establish
  integrated security or adoption.

All future changes remain local. No pushes, public release, mainnet launch,
spending, external messages, real keys or OpenClaw/runtime changes are authorized.
Fair launch, zero premine, the working perpetual policy and readiness gates stay
unchanged. The 9 MEOW / 90 s branding candidate and 135/150-year cap discussions
do not authorize consensus changes. Founder identity, ticker, checkpoint trust,
second signer and audit funding remain human decisions.

## Integration result

All five workers finished reviewable commits and stopped repository writes.
The coordinator reviewed the changed flows, source/corpus boundaries, negative
controls, evidence and visual assets, then integrated the owned commits locally:

| Track | Worker commit | Integrated commit | Result |
|---|---|---|---|
| Rust | `03f455f` | `8b3fc83` | 1,870 parity cases; three separately expected arithmetic mismatches |
| Mining | `64f4e58` | `3b4c448` | Exact P2Pool routines and real RPC/ZMQ/coinbase controls establish incompatibility |
| Demo | `f004bdd` | `c9ddfb3` | Private payment/recovery; 321 hash vectors; baseline and visual materials |
| Privacy | `17a948d` | `48f224b` | 29 cases; startup proxy failure closes; OpenAlias/RPC-controller limits explicit |
| Network | `174b723` | `924f367` | Actual P2P depth-3 partition/rejoin; clean15 memory blocker; FCMP readiness inventory |

Coordinator integration corrected one Shellcheck literal-brace warning in the
build source-tree receipt command. The frozen waiter retains the worker's
semantically equivalent original spelling; its inputs/worktree are unchanged.
Shared CI now lints the new runners and watches their paths; their local
fixture-specific runtime suites are not represented as remote-CI passes.
Operator/threat guidance removes blanket no-DNS and unsupported stale-advisory
claims and links the observed limits. Full production tests were not repeated:
production patches/binaries are unchanged, and all prior evidence is preserved.

See the [final handoff](handoff-2026-09-12-swarm.md) for combined checks, exact
build-waiter state and remaining work. Sessions/worktrees remain available for
inspection. No project remote/push, host-service changes or unrelated edits.
