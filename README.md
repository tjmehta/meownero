# Meownero

Meme-worthy, privacy-mandatory cryptocurrency project inspired by Monero's mission and cat-grade branding.

This repository contains local implementation and verification work, research,
and the project website. The provisional node implementation is a reviewed patch
series against pinned Monero sources; the architecture decision remains proposed
and launch gates remain open. See [PLAN.md](PLAN.md), the
[milestone checklist](docs/milestones.md), and [node build instructions](chain/README.md).

Start resumed work with the [September 13 recovery index](research/recovery-index-2026-09-13.md).
It identifies recovered sessions, active workstreams, completed checkpoints and
remaining failures. Historical test results are not launch-readiness claims.

Source discussions are under `research/`; original assets are under `assets/`.

## Run testnet v0 end to end

One command reproduces the whole isolated testnet v0 witness on one machine:
the accepted milestone recipes for launch, payment, late-peer sync, cold
backup/restore and pool restart run in order, each in its own container on its
own fresh two-peer chain from the same genesis, with one input manifest and one
evidence manifest for the run. It needs Docker, the pinned builder image, the
accepted daemon, wallet RPC and candidate pool executables under `build/`, a
free shared heavy-work lock and at least 5 GiB available RAM and disk.

```sh
python3 -B chain/testnet-v0/journey.py --work build/testnet-v0-journey-01
python3 -B chain/testnet-v0/verify-journey.py build/testnet-v0-journey-01
sha256sum -c build/testnet-v0-journey-01/INPUTS.sha256
```

Expect about 2 h 52 min of wall time, almost all of it the payment step's 124
natively mined blocks at about 90 s each, a container peak of about 3.3 GiB
under the 4 GiB cap, and about 30 MB of public receipts plus node databases
under each step's `data` directory. The run passed when the journey exits 0,
`build/testnet-v0-journey-01/result.json` says `PASS`, and the verifier prints
`PASS_JOURNEY_RECEIPT_RECONCILIATION` after re-running each milestone's own
verifier and the cross-step checks. `steps.json` and `<step>.exit` show where a
failed or blocked run stopped; keep that directory and rerun with a new path.
Details, refusals and limits: [journey](chain/testnet-v0/journey.md). This is
an isolated local witness, not a public testnet or a mainnet readiness claim.
