#include "ledger.h"

#include "amount.h"

#include <QLocale>
#include <algorithm>

namespace ledger {
namespace {

// "12.5" -> atomic units. Fixture helper only; never used on user input.
quint64 at(const char *s)
{
    return amount::parse(QString::fromLatin1(s), QLocale(QLocale::English, QLocale::UnitedStates)).atomic;
}

// Mock transaction ids: random hex that matches no real transaction.
const char *const kTxid[] = {
    "f344d362f2142dc292936b4ebbc4c45eff81243af547f57af43b7abe103f693e",
    "75a57f39b00bf9d2cd414edcedf48836c58f13daf23024cef1c1398f42036e54",
    "772fca6666d1c111260261bdc4bc52dd9443bd8fba94d49d2a364fbf7a3b936d",
};

// Recipients are stored as kit-wallet keys; the controller resolves them per network.
const QString kWalletB = QStringLiteral("b");

} // namespace

int Ledger::confirmations(const Tx &tx) const
{
    return tx.height ? tip - *tx.height + 1 : 0;
}

Balances Ledger::balances() const
{
    // Accumulate wide so a pathological fixture cannot wrap.
    __int128 total = 0, locked = 0;
    std::optional<int> next;
    auto note = [&next](int need) { next = next ? std::min(*next, need) : need; };
    for (const Tx &tx : txs) {
        if (tx.status == TxStatus::Failed)
            continue;
        if (tx.type == TxType::Out) {
            total -= __int128(tx.amount) + tx.fee;
            const int need = kUnlockOut - confirmations(tx);
            if (tx.status == TxStatus::Unknown || need > 0) {
                locked += tx.change;
                if (need > 0)
                    note(need);
            }
        } else if (tx.type == TxType::Mined) {
            total += tx.amount;
            // Each block's reward unlocks 60 blocks after that block.
            for (int k = 0; k < tx.blocks; ++k) {
                const int need = kUnlockMined - (tip - (tx.firstHeight + k) + 1);
                if (need > 0) {
                    locked += tx.amount / quint64(tx.blocks);
                    note(need);
                }
            }
        } else {
            total += tx.amount;
            const int need = kUnlockIn - confirmations(tx);
            if (need > 0) {
                locked += tx.amount;
                note(need);
            }
        }
    }
    Balances b;
    b.total = total > 0 ? quint64(total) : 0;
    b.locked = locked > 0 ? quint64(std::min(locked, total > 0 ? total : 0)) : 0;
    b.unlocked = b.total - b.locked;
    b.nextUnlock = next;
    return b;
}

const Tx *Ledger::find(const QString &id) const
{
    for (const Tx &tx : txs)
        if (tx.id == id)
            return &tx;
    return nullptr;
}

Tx *Ledger::find(const QString &id)
{
    for (Tx &tx : txs)
        if (tx.id == id)
            return &tx;
    return nullptr;
}

bool Ledger::hasUnknownSubmission() const
{
    return std::any_of(txs.begin(), txs.end(), [](const Tx &t) { return t.status == TxStatus::Unknown; });
}

int Ledger::pendingCount() const
{
    return int(std::count_if(txs.begin(), txs.end(),
                             [](const Tx &t) { return !t.height && t.status != TxStatus::Failed; }));
}

QList<const Tx *> Ledger::sorted() const
{
    QList<const Tx *> out;
    for (const Tx &tx : txs)
        out.append(&tx);
    std::stable_sort(out.begin(), out.end(), [](const Tx *a, const Tx *b) {
        return a->height.value_or(1'000'000'000) > b->height.value_or(1'000'000'000);
    });
    return out;
}

Ledger story(Story kind)
{
    Ledger l;
    l.tip = 1340;
    switch (kind) {
    case Story::Empty:
        l.created = 1336;
        break;
    case Story::Dust:
        l.created = 1300;
        l.txs = {{QStringLiteral("d1"), TxType::In, 1, 0, 0, 1302, 0, 0, {}, QString::fromLatin1(kTxid[2]), {}}};
        break;
    case Story::Large:
        l.created = 1200;
        l.txs = {
            {QStringLiteral("l1"), TxType::In, at("3153600.123456789012"), 0, 0, 1250, 0, 0, {},
             QString::fromLatin1(kTxid[0]), QStringLiteral("Layout check: a large balance")},
            {QStringLiteral("l2"), TxType::Out, at("1234567.000000000001"), kFee, at("8.5"), 1330, 0, 0,
             kWalletB, QString::fromLatin1(kTxid[1]), {}},
        };
        break;
    case Story::Normal:
        l.created = 1203;
        l.txs = {
            {QStringLiteral("m1"), TxType::Mined, kReward * 70, 0, 0, 1274, 1205, 70, {}, {}, {}},
            {QStringLiteral("r1"), TxType::In, at("5"), 0, 0, 1290, 0, 0, {}, QString::fromLatin1(kTxid[0]),
             QStringLiteral("From Jonas's test wallet")},
            {QStringLiteral("s1"), TxType::Out, at("2.5"), kFee, kReward - at("2.5") - kFee, std::nullopt, 0, 0,
             kWalletB, QString::fromLatin1(kTxid[1]), QStringLiteral("Lunch test")},
            {QStringLiteral("r2"), TxType::In, 1, 0, 0, 1338, 0, 0, {}, QString::fromLatin1(kTxid[2]), {}},
        };
        break;
    }
    return l;
}

QString statusText(const Ledger &l, const Tx &tx)
{
    if (tx.status == TxStatus::Failed)
        return QStringLiteral("Not sent");
    if (tx.status == TxStatus::Unknown)
        return QStringLiteral("Status unknown");
    if (!tx.height)
        return QStringLiteral("Waiting to confirm");
    const int c = l.confirmations(tx);
    const int need = tx.type == TxType::Mined ? 0 : (tx.type == TxType::In ? kUnlockIn : kUnlockOut);
    if (need && c < need)
        return QStringLiteral("%1 of %2 confirmations").arg(c).arg(need);
    if (tx.type == TxType::Out)
        return QStringLiteral("Confirmed");
    return QStringLiteral("%1 confirmations").arg(QLocale(QLocale::English, QLocale::UnitedStates).toString(c));
}

QString statusKind(const Ledger &l, const Tx &tx)
{
    if (tx.status == TxStatus::Failed)
        return QStringLiteral("failed");
    if (tx.status == TxStatus::Unknown)
        return QStringLiteral("unknown");
    if (!tx.height)
        return QStringLiteral("pending");
    const int need = tx.type == TxType::Mined ? 0 : (tx.type == TxType::In ? kUnlockIn : kUnlockOut);
    return need && l.confirmations(tx) < need ? QStringLiteral("pending") : QStringLiteral("done");
}

QString title(const Tx &tx)
{
    if (tx.type == TxType::Mined)
        return tx.blocks == 1 ? QStringLiteral("Mined 1 test block") : QStringLiteral("Mined %1 test blocks").arg(tx.blocks);
    if (tx.type == TxType::In)
        return QStringLiteral("Received");
    if (tx.status == TxStatus::Unknown)
        return QStringLiteral("Submission status unknown");
    if (tx.status == TxStatus::Failed)
        return QStringLiteral("Payment not sent");
    return QStringLiteral("Sent");
}

} // namespace ledger
