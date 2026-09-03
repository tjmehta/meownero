# E2 — Mandatory privacy: mechanism

**Exploration:** Which mechanism enforces "no transparent transactions, ever" (hard requirement §1.1 #3) without material security risk? · **Status:** Rev 3 — incident record built, dPoW-sunset finding added, observer-visibility analysis completed, mempool-DoS analysis plan drafted · **Date:** 2026-09-03 (rev 2 earlier same day pinned the Pirate code path and fee semantics; rev 1: 2026-08-22)

## 1. Verdict (DRAFT, strengthened)

Three mechanisms, in descending order of precedent strength. **(a) Monero-inherent** (Candidate M): mandatory by construction since 2014 — zero delta, strongest precedent. **(b) Pirate-style Sapling-only** (Candidate Z on the Sapling pool): production-enforced since 2018; the enforcing consensus code is pinned (§2a) — a real consensus rule, simpler than expected, with the "coinbase first spend must shield" property *emergent* from a single vout predicate rather than a separate rule. **(c) Ironwood-only rule** (Candidate Z on the current-generation pool): no live production precedent as of this revision — but **Pirate itself activates an Ironwood halo2 pool on its mandatory-private mainnet on 2026-10-03** (§2c), which if it holds becomes the first production precedent for exactly this mechanism class. Implementation evidence today, zero maturity evidence; watch it, do not lean on it.

Two findings materially reframe the Z-mechanism analysis:

1. **Fee and coinbase visibility are solved problems, in our favor (§3a).** On a fully shielded Zcash-lineage chain the fee is public per transaction by construction (it *is* the sum of the plaintext `valueBalance` fields), and shielded coinbase is publicly decryptable by consensus rule (ZIP-213 zero-ovk rule) with post-NU6 exact balance equality. A mandatory-shielded Meownero keeps per-block supply auditability and the PLAN.md §9.8 no-premine proof *without* Pirate's transparent-coinbase carve-out — the rule can be simpler and stricter than Pirate's.
2. **Pirate's precedent is stronger as a mechanism and weaker as a security story (§2b).** No chain-level incident found in 8 years of enforcement — but its reorg resistance always leaned on Komodo dPoW, and **Komodo sunset notary dPoW in January 2026**, replacing it with developer-key auto-checkpointing. Pirate now runs its own reduced 6-signature notary scheme whose anchoring target post-sunset is unverified. PLAN.md §4.3's "borrowed security with strings" caveat is confirmed with interest: the strings got pulled. The *mandatory-privacy* precedent transfers to us; the *security* posture never did and now visibly doesn't.

**PLAN.md impact (amendment queue; PLAN.md is not edited without TJ/the whitepaper author):** (i) §5 E2's Z-mechanism should be restated post-NU6.3 as Ironwood-only vs. Sapling-only (rev 2 finding, stands); (ii) §4.3's Pirate paragraph should note the January 2026 dPoW sunset — the dependency it warned about has already degraded to dev-key checkpointing upstream; (iii) the Z-mechanism needs no transparent-coinbase exception — ZIP-213 shielded coinbase preserves supply auditability via the zero-ovk rule (post-NU6.3 pools: Sapling and/or Ironwood; Orchard coinbase prohibited); (iv) §9.8's supply-tally/no-premine page is fully realizable on either candidate; (v) new watch item: Pirate's Ironwood activation 2026-10-03 as the first potential production precedent for an Ironwood-scoped mandatory-shielded rule.

## 2. Production precedents & maturity evidence

- **Monero:** every transaction private by construction since 2014; ~12 years securing a top-tier coin. `[VERIFIED-PRIMARY]` (uncontroversial; getmonero.org)
- **Pirate Chain (ARRR), 2018–present:** Komodo-derived private assetchain; mandatory-shielded enforced at consensus since launch (code in §2a). Official documents match the code: Whitepaper v3 (2022-03-01) §5 — "The initial coinbase reward to the miner of a block is transparent for supply audibility. From that point on, all Peer-to-Peer transactions of the Pirate Chain network are required to be shielded"; EXCEPTIONS box — "The first transaction of a coinbase reward is required to be sent to a shielded address. DPOW transactions are required to be transparent." `[VERIFIED-PRIMARY]` — both PDFs fetched and read 2026-09-03; the explicit first-spend sentence appears only in Whitepaper v3, not The Pirate Code v2.0.
- **Shielded coinbase:** ZIP-213 — coinbase MUST NOT contain JoinSplit or Spend descriptions; MAY contain Sapling and/or Orchard outputs from NU5, **Sapling and/or Ironwood post-NU6.3 (Orchard-pool components prohibited)**; transparent coinbase also still permitted upstream. **All shielded coinbase outputs MUST be recoverable with 32 zero bytes as the outgoing viewing key — coinbase addresses and amounts are publicly decryptable by consensus rule.** `[VERIFIED-PRIMARY]` — zips.z.cash/zip-0213 (re-read 2026-09-03)
- **Ironwood-only enforcement:** not yet live on any chain found in this pass; Pirate's scheduled activation (§2c) is the first concrete implementation evidence located. `[VERIFIED-PRIMARY for Pirate schedule; negative result elsewhere]`

### 2a. Pirate's enforcing code path (pinned; rev 2, retained)

Repo that runs mainnet: **github.com/PirateNetwork/pirate**, `master`; latest signed release v6.0.4-b9b8b4c (2026-09-01) matches master HEAD `b9b8b4cf`, so the cited code is the released mainnet code. `[VERIFIED-PRIMARY]` — files fetched at that commit and read directly 2026-09-03.

- **Parameterization:** `ASSETCHAINS_PRIVATE` global set from `-ac_private`; Pirate hardcodes `SoftSetArg("-ac_private","1")` in its chain defaults (`src/komodo_utils.cpp:1058-1062`), so the daemon is private-only out of the box. Upstream Komodo refuses `-ac_private` for chains other than PIRATE/ZOMBIE (`KomodoPlatform/komodo src/komodo_utils.cpp:1611-1623`).
- **Enforcement site:** `CheckTransactionWithoutProofVerification` in `src/main.cpp`, reached via `CheckTransaction()` from both mempool acceptance and per-transaction block validation (`CheckBlock`) — a consensus rule, not wallet policy. Three checks at commit `b9b8b4c`:
  1. `main.cpp:1697-1713` — any **non-coinbase transparent vout with `nValue > 0`** to a non-notary address (`komodo_isnotaryvout()`, `src/komodo_notary.cpp:102-123`: CRYPTO777 address or the season's elected notary addresses) flags the tx invalid.
  2. `main.cpp:1740-1752` — flagged tx with Sapling spends → rejected `bad-txns-acprivate-chain` ("no sapling -> taddr"), except a narrow season>5 P2SH redeem-script-reveal carve-out for the notary pattern.
  3. `main.cpp:1869-1876` — catch-all: flagged tx rejected unless it is a legacy pure Sprout→taddr migration with zero transparent vins (a pre-Sapling-deadline allowance, dead today).
- **Design insight for our Z-mechanism:** transparent *vins* are permitted (that is how coinbase rewards get spent); "first spend of coinbase must shield" is **emergent** — a spend of a transparent coinbase output cannot create any transparent output, so it must shield everything. One vout predicate at a single validation choke point delivers the whole property. Our rule on Zebra would be simpler still (empty transparent bundles for non-coinbase txs + ZIP-213 shielded coinbase; no notary or Sprout exceptions) — but this is a **design** precedent only; zcashd-era Komodo C++ transfers nothing as code to Zebra.

### 2b. Incident record, 2018–2026 (Pirate + Komodo substrate)

- **No chain-level attack found on ARRR:** no documented 51%/reorg double-spend, inflation event, or attack-triggered emergency fork 2018–2026. Searched: Pirate/Komodo blogs, GitHub releases and security-advisory APIs (both return empty — neither project publishes GitHub advisories), news, forums. `[OPEN as absence-of-evidence]` — Pirate incident comms live partly on Medium/Discord; record as "none found," not "none happened."
- **CVE-2019-7167 (Sprout counterfeiting) applied to early Pirate.** Pirate launched 2018-08-29 on Sprout z-addresses (same BCTV14 parameters as Zcash/Komodo); remediation was the ecosystem-wide forced Sapling migration with Sprout disabled after 2019-02-15, making Pirate "the first Sapling-only chain." No evidence of actual counterfeiting on ARRR. `[SECONDARY→PRIMARY]` — Pirate's own Medium/blog posts; zfnd.org and ECC posts for the underlying CVE; Komodo's advisory URL confirmed but 403s automated fetchers. Consequence: the "mandatory-private since 2018" record includes ~6 months on later-known-unsound Sprout crypto — the *enforcement mechanism* never failed; the underlying proving system did. Feeds E1's "years in production is a weak soundness proxy" finding.
- **dPoW status change (material):** Komodo v0.9.2 "Draco Typhon" (published 2025-12-20; mandatory) **replaced 64-notary dPoW with "auto-checkpointing"** — checkpoints broadcast by a developer node, signed by a master key held by "the project's most trusted developers," activating KMD height 4,771,595 (~2026-01-05). `[VERIFIED-PRIMARY]` — github.com/KomodoPlatform/komodo/releases/tag/v0.9.2 (read 2026-09-03). Pirate v6.0.0 (Aug 2026) still ships active notary machinery — `requiredSigs` fixed at **6** from height 4,141,650 (~2026-09-19) — but **what Pirate notarizes to after the KMD sunset is unverified.** `[VERIFIED-PRIMARY for the release notes; OPEN for the anchoring target]`
- **Inherited-C++-bug hygiene, cautionary:** the Bitcoin-Core-lineage ConnectBlock use-after-free (CVE-2024-52911 class) was fixed by zcashd v6.12.5 and Komodo v0.9.2-2 (June 2026; also nSPV P2P declared remotely memory-unsafe); **no evidence Pirate shipped the same fix** in v6.0.0–v6.0.4 release notes. `[OPEN]` — a live illustration of PLAN.md §9's upstream-shock risk and why the 72h security-merge SLA matters for any fork, including us. (The 2019 Agama wallet npm supply-chain attack is a further inherited-stack warning — wallet-layer only, no consensus impact, but exactly the §9.4 threat class.)

### 2c. Pirate Ironwood pool (precedent-in-motion, not yet evidence)

Pirate v6.0.0 introduces an **Ironwood shielded pool** (halo2 over Pallas, evolved from an Orchard integration; `orchard =0.15.4` + halo2 crates pinned from PirateNetwork forks) while retaining the same private-chain checks; mainnet activation **2026-10-03 19:00 UTC**, timestamp-derived. `[VERIFIED-PRIMARY]` — release-notes-6.0.0.md (read 2026-09-03). If it activates and holds, Pirate becomes the first *mandatory-private* chain running a halo2 pool — a genuine (if young and zcashd-lineage) production precedent for mechanism (c). Whether Pirate's pinned halo2 forks include the June 2026 gadget fix is unstated in release notes (timing strongly suggests yes). `[OPEN — re-check after 2026-10-03]`

## 3. Consensus/crypto delta

- **Candidate M:** zero.
- **Candidate Z:** consensus rule requiring (i) empty transparent input/output bundles for all non-coinbase transactions, (ii) coinbase paid directly to shielded outputs per ZIP-213 (no Pirate-style transparent-coinbase exception needed; supply auditability preserved by the zero-ovk rule), (iii) removal/disabling of transparent mempool acceptance, RPC, and address surface. Pool-scoping decision from E1 (Ironwood-only vs. Sapling-only) sets which bundles must be non-empty; post-NU6.3 coinbase pools are Sapling and/or Ironwood only. No new cryptography — a new *rule*, unprecedented today if Ironwood-scoped (watch §2c), precedented by analogy if Sapling-scoped.

### 3a. What a passive observer sees on an all-shielded chain (answered)

All `[VERIFIED-PRIMARY]` — Zcash protocol spec (protocol.pdf §3.4 transactions/treestates, §4.13 Sapling balance, §4.14 Orchard/Ironwood balance, §7.1 encoding + coinbase rules; current version includes Ironwood-era language), ZIP 225, ZIP 317, ZIP 213 (read 2026-09-03):

- **The fee is public per transaction, by construction.** With no transparent bundle, the transparent value pool's remaining value — which the spec defines as the miner fee and requires to be nonnegative — equals `valueBalanceSapling + valueBalanceOrchard`, both plaintext int64 fields. Positive balancing value moves value out of a shielded pool; consistency with the hidden note commitments is enforced by the binding signatures. Fees cannot be hidden without redesigning the balance mechanism (which §2.1 forbids). Consequence for messaging and the explorer: amounts, addresses, and linkages are hidden; fees and fee totals are not.
- **Structure leaks:** bundle counts are plaintext — Sapling leaks spend and output counts *separately*; Orchard/Ironwood actions merge spend+output so only the action count leaks, and reference wallets pad to ≥2 actions (`DEFAULT_MIN_ACTIONS` in the orchard crate builder) — **a wallet convention, not a consensus rule**. Also visible: `nExpiryHeight`, anchors (an upper bound on witness/note age), lock_time, flags, fixed-size ciphertexts, nullifiers, commitments, proofs, signatures. Padding/uniformity policy is a wallet-track design item, not consensus.
- **ZIP-317 fees on an all-shielded chain:** `conventional_fee = 5000 · max(2, logical_actions)` zatoshis with `logical_actions = max(nSpendsSapling, nOutputsSapling) + nActionsOrchard` (transparent/Sprout terms zero). Deliberately computable from public data, so it adds no new leak; a nonstandard fee is itself a fingerprint — another argument for wallet-side uniformity defaults.
- **Shielded coinbase is effectively transparent:** valueBalance goes negative by exactly subsidy+fees (post-NU6: total output value MUST equal total input value), coinbase MUST NOT have Spend descriptions, and all shielded coinbase outputs MUST decrypt under the all-zero outgoing viewing key — miner addresses and amounts are readable by anyone. Supply tally (`emission = height × 1 MEOW`) and per-block payout verification work fully on an all-shielded chain; it also means **miner payouts are the one permanently public flow** — disclose that honestly in mining docs.

## 4. Security assumptions introduced (Z mechanism)

- The rule must not disturb value-balance accounting across pools, turnstile logic (load-bearing upstream for Orchard→Ironwood migration), or fee semantics. Fee semantics are now understood (§3a — fees ride the same valueBalance fields whether or not transparent bundles exist; the rule constrains bundle presence, not balance arithmetic); the turnstile/pool-accounting interaction remains to verify against Zebra's actual validation code. `[OPEN — narrowed]`
- **All-shielded mempool DoS economics:** every transaction carries heavy proof verification; upstream Zcash was designed assuming a cheap transparent majority. Needs adversarial analysis per §4a, not assumption. `[OPEN — Stage 2]`
- If Sapling-scoped: assumption that a Sapling-only chain's proving/parameter inheritance is acceptable (see E1 open task; ZIP 219 signals upstream intent to restrict Sapling).

### 4a. All-shielded mempool DoS analysis plan (Stage 2 input)

Question to answer with measurements, not vibes: *can an attacker exhaust node CPU/memory more cheaply than the fee market punishes them, when every transaction requires proof verification?*

1. **Cost baseline:** benchmark single-tx validation on commodity hardware — Sapling Groth16 spend/output verify, Orchard/Ironwood halo2 action verify (batched and unbatched), signature checks — per tx and per byte, on Zebra. Compare against a transparent-tx baseline to quantify the "no cheap majority" delta.
2. **Admission-policy map:** enumerate Zebra's existing mempool defenses (verify-before-accept ordering, per-peer rate limits, eviction, orphan/expiry handling; ZIP-401 mempool limiting) and identify which assume transparent-dominant traffic.
3. **Adversarial scenarios:** (a) valid-proof spam at minimum ZIP-317 fee — $/hour to saturate a node's verify capacity; (b) *invalid*-proof spam — what gets verified before ban/score, and can a peer force repeated expensive failures; (c) re-validation amplification on reorgs and mempool churn; (d) block-verification worst case — a full block of max-action txs vs. the 120s block target (interacts with E3's block-time sanity check).
4. **Prior art to mine:** Zcash's 2022 Sapling spam incident and the ZIP-317 response; Pirate v6.0.0's DoS hardening set (mempool bounds, rate limiting, MAX_INV_SZ 50,000→5,000, consensus/mempool proof-uniqueness enforcement — production evidence that an all-shielded mempool needs exactly this defense class); Monero's dynamic-block-size + fee floor as the M-side comparison.
5. **Output:** a go/no-go note against the Z mechanism's kill criterion ("perturbs audited invariants in ways review cannot bound") plus recommended admission parameters. Benchmarks are Stage 2 spike work (throwaway, `spikes/`, feasibility-only per PLAN.md §2.3).

## 5. Audit burden

Unchanged in scope: the rule plus every path whose invariants it touches — value balance, coinbase handling, mempool policy, RPC surface — plus the wallet's shielded-only operation (interacts with E1's Zallet-alpha finding). §3a narrows the unknowns (fee/coinbase semantics are spec-anchored); §4a defines the mempool-DoS review deliverable. On Candidate M: zero incremental burden for this requirement.

## 6. Kill criteria (unchanged from PLAN.md §5 E2)

For the Z mechanism only: unbounded patch surface, or indication the rule perturbs audited invariants in ways review cannot bound. The *product requirement* is never dropped — only the risky mechanism is.

## 7. Safest fallback

Candidate M, where the property is inherent.

## 8. Open verification tasks

- [x] Pin Pirate whitepaper v3 + Pirate Code v2 PDFs and locate the enforcing `ac_private` consensus code in current Pirate source. *(rev 2, 2026-09-03 — §2a.)*
- [x] Complete the Komodo/Pirate incident audit. *(rev 3, 2026-09-03 — §2b: no chain-level ARRR incident found (absence-of-evidence caveat recorded); Sprout CVE applied 2018–19 and was remediated by forced migration; Komodo dPoW sunset Jan 2026 is the material finding; Agama and v0.9.2-2 memory-safety fixes recorded as inherited-stack warnings.)*
- [x] Confirm fee visibility and value-balance semantics for a 100%-shielded chain. *(rev 2/3, 2026-09-03 — §3a: fee public by construction; shielded coinbase publicly decryptable via zero-ovk with post-NU6 exact balance; structure counts leak, padding is wallet convention.)*
- [x] Draft the all-shielded mempool DoS analysis plan. *(rev 3, 2026-09-03 — §4a; benchmarks remain Stage 2.)*
- [ ] Decide pool scoping jointly with E1 (Ironwood-only vs. Sapling-only) — blocked on the group's crypto-maturity-bar answer (open-questions #3).
- [ ] Re-check Pirate's Ironwood activation after 2026-10-03 — clean activation? do their halo2 pins include the June 2026 gadget fix? (§2c) — before treating it as production precedent.
- [ ] Verify what Pirate notarizes to post-KMD-dPoW-sunset, and whether Pirate shipped the ConnectBlock UAF fix (§2b) — context for how much of Pirate's clean record is mechanism vs. borrowed security vs. luck.
- [ ] Verify the turnstile/pool-accounting interaction of an empty-transparent-bundle rule against Zebra's actual validation code (Stage 2, with the control prototype).

## 9. Sources

Primary (read on dates noted):

- Zcash protocol specification: https://zips.z.cash/protocol/protocol.pdf — §3.4 (transactions/treestates, fee definition), §4.13/§4.14 (Sapling and Orchard/Ironwood balance), §7.1 (encoding; coinbase balance rules) (2026-09-03)
- ZIP-213 shielded coinbase: https://zips.z.cash/zip-0213 (2026-09-03) · ZIP-225 v5 tx format: https://zips.z.cash/zip-0225 · ZIP-317 proportional fees: https://zips.z.cash/zip-0317 (2026-09-03)
- Pirate whitepaper v3: https://piratechain.com/wp-content/uploads/Pirate_Chain_White_Paper_v3.pdf (SHA-256 `08e068b6155e2764d49a6a94bf17041b57d9211741f6e1f61bf186d7aeee3e23`) · Pirate Code v2: https://piratechain.com/wp-content/uploads/The_Pirate_Code_V2.0.pdf (both 2026-09-03; site 403s non-browser user agents)
- Pirate private-chain initialization: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/src/komodo_utils.cpp#L1058-L1062
- Pirate consensus enforcement: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/src/main.cpp#L1697-L1876
- Pirate notary exception: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/src/komodo_notary.cpp#L102-L130
- Pirate v6.0.0 release notes (Ironwood, notary requiredSigs, DoS hardening): https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/doc/release-notes/release-notes-6.0.0.md (2026-09-03)
- Komodo v0.9.2 "Draco Typhon" (dPoW → auto-checkpointing): https://github.com/KomodoPlatform/komodo/releases/tag/v0.9.2 (published 2025-12-20; read 2026-09-03) · Komodo v0.9.2-2 (ConnectBlock UAF & memory-safety fixes): https://github.com/KomodoPlatform/komodo/releases/tag/v0.9.2-2 (2026-06-25)
- CVE-2019-7167: https://zfnd.org/concerning-the-sprout-vulnerability-cve-2019-7167/ · https://electriccoin.co/blog/zcash-counterfeiting-vulnerability-successfully-remediated/
- Agama supply-chain post-mortem: https://blog.npmjs.org/post/185397814280/plot-to-steal-cryptocurrency-foiled-by-the-npm.html
- Orchard builder padding convention: https://github.com/zcash/orchard/blob/main/src/builder.rs (`DEFAULT_MIN_ACTIONS`)
- getmonero.org design documentation

Secondary: Pirate Medium posts (Sapling migration, 2019) · securityaffairs.com (Komodo affected by CVE-2019-7167) · decker.im Draco Typhon writeup · komodoplatform.com advisory URLs (403 to fetchers; titles confirmed via search) · bitcoincore.org CVE-2024-52911 disclosure (context for the inherited UAF class)
