#pragma once

// The simulated wallet's history and the balances derived from it, the way
// get_balance reports total and unlocked amounts. Port of the prototype's
// story()/balances()/txStatus() rules. Amounts are atomic units.

#include <QList>
#include <QString>
#include <optional>

namespace ledger {

// Blocks before coins can be spent: pinned upstream cryptonote_config.h:43,48
// (TJS-1994 #3). Never expressed as clock time.
inline constexpr int kUnlockMined = 60;
inline constexpr int kUnlockIn = 10;
inline constexpr int kUnlockOut = 10;
// Example network fee of a prepared transaction (0.00006152); fees vary.
inline constexpr quint64 kFee = 61'520'000ULL;
// Upstream regtest block reward, not Meownero's planned 9 MEOW / 90 s.
inline constexpr quint64 kReward = 17'592'186'044'415ULL;

enum class TxType { In, Out, Mined };
enum class TxStatus { Normal, Unknown, Failed };

struct Tx {
    QString id;
    TxType type = TxType::In;
    quint64 amount = 0;
    quint64 fee = 0;
    quint64 change = 0;
    std::optional<int> height; // none: not in a block yet
    int firstHeight = 0;       // mined groups
    int blocks = 0;            // mined groups
    QString to;                // outgoing: kit wallet key ("b", "c") or a literal address
    QString txid;
    QString note;              // local only, never sent or restored
    TxStatus status = TxStatus::Normal;
    quint64 attemptId = 0;     // outgoing: the submission attempt that created it
};

struct Balances {
    quint64 total = 0;
    quint64 locked = 0;
    quint64 unlocked = 0;
    std::optional<int> nextUnlock; // blocks until more becomes spendable
};

enum class Story { Empty, Normal, Dust, Large };

struct Ledger {
    int tip = 0;
    int created = 0;
    QList<Tx> txs;

    int confirmations(const Tx &tx) const;
    Balances balances() const;
    const Tx *find(const QString &id) const;
    Tx *find(const QString &id);
    bool hasUnknownSubmission() const;
    int pendingCount() const;
    QList<const Tx *> sorted() const; // newest first, unconfirmed on top
};

Ledger story(Story kind);

// Display text for a transaction row/detail. Network-independent wording.
QString statusText(const Ledger &l, const Tx &tx);
QString statusKind(const Ledger &l, const Tx &tx); // failed|unknown|pending|done
QString title(const Tx &tx);

} // namespace ledger
