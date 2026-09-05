#!/usr/bin/env python3
"""Candidate Z control: apply the Meownero delta to a pristine Zebra v6.3.0 tree (d1fd7ad).

Feasibility only, never security (PLAN.md §2.3). Exact-string replacements that fail loudly on
upstream drift; the script doubles as the touched-surface inventory.  Run: python3 apply.py <zebra-dir>

Deltas exercised (the actual risky ones, PLAN.md §5 E2/E3):
  1. emission: constant 0.9 coin/block replaces the halving schedule; genesis pays 0
  2. MAX_MONEY raised (perpetual issuance exceeds Zcash's 21M cap after ~89 years at 120 s)
  3. mandatory privacy: non-coinbase transactions may carry no transparent inputs or outputs;
     coinbase transparent outputs must be zero-value (shielded coinbase per ZIP-213)
  4. block spacing 120 s (working value)
Identity (name/magic/genesis) is NOT changed here: the control runs on Zebra's Regtest network,
whose bundled genesis block lets it boot without a genesis generator. Genesis/magic/prefix
generation is a measured M1 task, not a control-prototype input.
"""
import sys, pathlib

root = pathlib.Path(sys.argv[1])
touched = []

def edit(rel, pairs):
    p = root / rel
    s = p.read_text()
    for old, new in pairs:
        assert s.count(old) == 1, f"{rel}: anchor not unique/missing: {old[:70]!r}"
        s = s.replace(old, new)
    p.write_text(s)
    touched.append(rel)

def append(rel, text):
    p = root / rel
    p.write_text(p.read_text() + text)
    touched.append(rel)

# ---------------------------------------------------------------- 1. emission
edit("zebra-chain/src/parameters/network/subsidy/constants.rs", [
    ("pub(crate) const MAX_BLOCK_SUBSIDY: u64 = ((25 * COIN) / 2) as u64;",
     "pub(crate) const MAX_BLOCK_SUBSIDY: u64 = ((25 * COIN) / 2) as u64;\n\n"
     "/// Meownero: perpetual flat block subsidy, 0.9 coin per block at 8 decimal places\n"
     "/// (PLAN.md rev 4 §8.1). Genesis pays 0 (§8.2).\n"
     "pub const MEOW_BLOCK_SUBSIDY: u64 = ((9 * COIN) / 10) as u64;"),
])
edit("zebra-chain/src/parameters/network/subsidy.rs", [
    ("""pub fn block_subsidy(height: Height, net: &Network) -> Result<Amount<NonNegative>, SubsidyError> {
    let Some(halving_div) = halving_divisor(height, net) else {
        return Ok(Amount::zero());
    };
""",
     """pub fn block_subsidy(height: Height, net: &Network) -> Result<Amount<NonNegative>, SubsidyError> {
    // Meownero: perpetual flat subsidy, independent of height, halving, slow start and network.
    // The upstream schedule below is unreachable and kept only to keep the diff reviewable.
    if height == Height(0) {
        return Ok(Amount::zero());
    }
    #[allow(unreachable_code)]
    return Ok(Amount::try_from(constants::MEOW_BLOCK_SUBSIDY)?);

    let Some(halving_div) = halving_divisor(height, net) else {
        return Ok(Amount::zero());
    };
"""),
])
append("zebra-chain/src/parameters/network/subsidy.rs", r'''

/// Meownero emission invariants (control prototype). See spikes/candidate-z/README.md.
#[cfg(test)]
mod meow_tests {
    use super::*;
    use crate::amount::MAX_MONEY;

    const R: u64 = constants::MEOW_BLOCK_SUBSIDY;

    #[test]
    fn constant_is_0_9_coin() {
        assert_eq!(R, 90_000_000);
        assert_eq!(R, (9 * crate::amount::COIN as u64) / 10);
    }

    #[test]
    fn subsidy_is_flat_on_every_network_and_height() {
        for net in Network::iter() {
            assert_eq!(block_subsidy(Height(0), &net).unwrap(), Amount::zero());
            for h in [1u32, 2, 100, 262_800, 10 * 262_800, 1_000_000_000, Height::MAX.0] {
                assert_eq!(
                    block_subsidy(Height(h), &net).unwrap(),
                    Amount::<NonNegative>::try_from(R).unwrap(),
                    "height {h}"
                );
            }
        }
    }

    #[test]
    fn supply_is_height_times_reward_and_fits_max_money() {
        // supply(h) = h * R; the cap must hold for every representable height
        let max_h = Height::MAX.0 as u64; // 2^31 - 1
        let supply_at_max = max_h * R;
        assert!(supply_at_max <= MAX_MONEY as u64, "MAX_MONEY too small for perpetual issuance");
        // years to exceed Zcash's original 21M cap at 120 s blocks: informational, asserted for the record
        let blocks_per_year = (365 * 24 * 3600) / 120;
        let zcash_cap_blocks = (21_000_000u64 * crate::amount::COIN as u64) / R;
        assert_eq!(zcash_cap_blocks / blocks_per_year, 88); // ~88.8 years
    }

    #[test]
    fn no_funding_streams_on_regtest_control() {
        let net = Network::new_regtest(Default::default());
        for h in [1u32, 2, 1000] {
            assert!(funding_stream_values(Height(h), &net, block_subsidy(Height(h), &net).unwrap())
                .unwrap()
                .is_empty());
        }
    }
}
''')

# ---------------------------------------------------------------- 2. MAX_MONEY
edit("zebra-chain/src/amount.rs", [
    ("pub const MAX_MONEY: i64 = 21_000_000 * COIN;",
     "// Meownero: perpetual issuance has no cap; the type bound is raised to the largest value that\n"
     "// keeps every Amount arithmetic path inside i64 (9.2e18 < i64::MAX). Zcash's 21M cap would be\n"
     "// crossed after ~88 years at 0.9/120 s, at which point every value-pool check would fail.\n"
     "pub const MAX_MONEY: i64 = 92_000_000_000 * COIN;"),
])

# ---------------------------------------------------------------- 3. mandatory privacy
edit("zebra-consensus/src/error.rs", [
    ('''    #[error("must have at least one output: transparent, shielded output, or joinsplit")]
    NoOutputs,
''',
     '''    #[error("must have at least one output: transparent, shielded output, or joinsplit")]
    NoOutputs,

    #[error("Meownero: transparent value is forbidden (mandatory privacy); only zero-value coinbase transparent outputs are allowed")]
    TransparentValueForbidden,
'''),
    ('''            | NoInputs
            | NoOutputs
            | BadBalance''',
     '''            | NoInputs
            | NoOutputs
            | TransparentValueForbidden
            | BadBalance'''),
])
edit("zebra-consensus/src/transaction/check.rs", [
    ('''/// Checks that the transaction has enough orchard flags.
///
/// # Consensus
///
/// For `Transaction::V5` only:''',
     '''/// Meownero mandatory privacy (PLAN.md §1.1 #3; E2 §3 rule, stricter than Pirate's):
///
/// * a non-coinbase transaction MUST have no transparent inputs and no transparent outputs;
/// * a coinbase transaction MUST NOT have a transparent output with non-zero value
///   (miner subsidy and fees are paid to a shielded receiver, ZIP-213).
///
/// Together with ZIP-213 shielded coinbase this leaves no transparent value on the chain at all,
/// so the transparent pool balance is identically zero and no transparent escape hatch exists.
pub fn mandatory_shielded(tx: &Transaction) -> Result<(), TransactionError> {
    if tx.is_coinbase() {
        if tx.outputs().iter().any(|o| o.value != Amount::<zebra_chain::amount::NonNegative>::zero()) {
            return Err(TransactionError::TransparentValueForbidden);
        }
        return Ok(());
    }
    if !tx.inputs().is_empty() || !tx.outputs().is_empty() {
        return Err(TransactionError::TransparentValueForbidden);
    }
    Ok(())
}

/// Checks that the transaction has enough orchard flags.
///
/// # Consensus
///
/// For `Transaction::V5` only:'''),
])
edit("zebra-consensus/src/transaction.rs", [
    ('''    check::has_inputs_and_outputs(tx)?;
    check::has_enough_orchard_flags(tx)?;
    // NU6.3 / Ironwood flag rules (no-ops for pre-v6 transactions).''',
     '''    check::has_inputs_and_outputs(tx)?;
    // Meownero: no transparent value outside zero-value coinbase outputs (mandatory privacy).
    check::mandatory_shielded(tx)?;
    check::has_enough_orchard_flags(tx)?;
    // NU6.3 / Ironwood flag rules (no-ops for pre-v6 transactions).'''),
])
append("zebra-consensus/src/transaction/tests.rs", r'''

/// Meownero mandatory-privacy rule (control prototype).
mod meow_mandatory_shielded {
    use super::*;

    /// The rule, restated independently of the implementation, over every transaction in the
    /// upstream mainnet/testnet block vectors: coinbase => all transparent outputs zero-valued;
    /// otherwise => no transparent inputs and no transparent outputs.
    #[test]
    fn matches_spec_on_all_vector_transactions() {
        let _init_guard = zebra_test::init();
        let (mut rejected, mut accepted, mut shielded_only) = (0usize, 0usize, 0usize);
        for net in Network::iter() {
            for tx in transactions_from_blocks(net.block_iter()) {
                let expected_ok = if tx.is_coinbase() {
                    tx.outputs().iter().all(|o| o.value == Amount::<NonNegative>::zero())
                } else {
                    tx.inputs().is_empty() && tx.outputs().is_empty()
                };
                let got = check::mandatory_shielded(&tx);
                match (expected_ok, got) {
                    (true, Ok(())) => {
                        accepted += 1;
                        if !tx.is_coinbase() {
                            shielded_only += 1;
                        }
                    }
                    (false, Err(TransactionError::TransparentValueForbidden)) => rejected += 1,
                    (e, g) => panic!("spec/impl disagree: expected_ok={e} got={g:?} tx={tx:?}"),
                }
            }
        }
        // Zcash vectors are full of transparent value: the rule must bite, and at least one
        // fully shielded non-coinbase transaction must pass so the accept path is exercised.
        assert!(rejected > 0, "no transaction was rejected");
        assert!(shielded_only > 0, "no shielded-only transaction was accepted");
        assert!(accepted > 0);
    }

    /// Every Zcash-vector coinbase pays transparent value, so every one is rejected: the control
    /// chain can only be mined with a shielded miner address (ZIP-213).
    #[test]
    fn transparent_coinbase_is_rejected() {
        for net in Network::iter() {
            let cb = transactions_from_blocks(net.block_iter())
                .find(|tx| tx.is_coinbase() && tx.outputs().iter().any(|o| o.value != Amount::<NonNegative>::zero()))
                .expect("a transparent coinbase in the vectors");
            assert!(matches!(
                check::mandatory_shielded(&cb),
                Err(TransactionError::TransparentValueForbidden)
            ));
        }
    }
}
''')

# ---------------------------------------------------------------- 4. block spacing (working value)
edit("zebra-chain/src/parameters/network_upgrade.rs", [
    ("pub const POST_BLOSSOM_POW_TARGET_SPACING: u32 = 75;",
     "// Meownero: 120 s working block time (PLAN.md §8.1; pending Stage 2 benchmarks).\n"
     "pub const POST_BLOSSOM_POW_TARGET_SPACING: u32 = 120;"),
])

print("touched:")
for t in touched:
    print("  ", t)
