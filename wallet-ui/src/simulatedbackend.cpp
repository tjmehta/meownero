#include "simulatedbackend.h"

#include <QTimer>

namespace {
// Mock ids for submitted payments: random hex, no real transaction.
const char *const kSubmittedTxid[] = {
    "109b2de17f8e5346cf33add2c8e8f6978247deec6581c2a162a4e8fe2c2b0c71",
    "418375dbda2a7a6e7b2da9fa23abc3b5176c1109bdd2214b69b288d593546d8b",
    "9e9ce957111e2f300943bddf59f7db5716ad632c2b43ebb09da4006c68acdd3c",
};
constexpr quint64 kPreparedFee = 61'520'000ULL; // same example fee as the ledger
} // namespace

SimulatedBackend::SimulatedBackend(QObject *parent) : QObject(parent) {}

void SimulatedBackend::prepareTransfer(quint64 requestId, const QString &recipient, quint64 atomic)
{
    Q_UNUSED(recipient);
    Q_UNUSED(atomic);
    const int n = m_prepareCounter++;
    const QString ref = QStringLiteral("sim-prepared-%1").arg(n);
    const QString txid = QString::fromLatin1(kSubmittedTxid[n % 3]);
    QTimer::singleShot(prepareDelayMs, this, [this, requestId, ref, txid] {
        m_unrelayed.insert(ref);
        m_issuedOrder.append(ref);
        emit transferPrepared(requestId, ref, kPreparedFee, txid);
    });
}

void SimulatedBackend::relayPrepared(quint64 attemptId, const QString &preparedRef)
{
    const SendOutcome outcome = nextSendOutcome;
    QTimer::singleShot(relayDelayMs, this, [this, attemptId, preparedRef, outcome] {
        if (!m_unrelayed.remove(preparedRef)) {
            // Never rebuild: an unknown or already-used reference is refused.
            emit relayFinished(attemptId, SendOutcome::Refused,
                               QStringLiteral("this prepared payment is not known to the wallet engine"));
            return;
        }
        m_relayed.append(preparedRef);
        emit relayFinished(attemptId, outcome,
                           outcome == SendOutcome::Refused
                               ? QStringLiteral("double spend: one of the coins was already spent")
                               : QString());
    });
}

void SimulatedBackend::checkSubmission(quint64 requestId, const QString &txid)
{
    const bool found = unknownResolves == UnknownResolves::ReachedNode;
    QTimer::singleShot(checkDelayMs, this, [this, requestId, txid, found] {
        emit submissionChecked(requestId, txid, found);
    });
}

void SimulatedBackend::generateBlocks(quint64 requestId, int count)
{
    QTimer::singleShot(mineDelayMs, this, [this, requestId, count] { emit blocksGenerated(requestId, count); });
}

void SimulatedBackend::reconnect(quint64 requestId)
{
    QTimer::singleShot(reconnectDelayMs, this, [this, requestId] { emit reconnected(requestId); });
}

void SimulatedBackend::scanRestore(quint64 requestId)
{
    auto *timer = new QTimer(this);
    timer->setInterval(scanTickMs);
    auto pct = std::make_shared<int>(0);
    connect(timer, &QTimer::timeout, this, [this, timer, pct, requestId] {
        *pct = std::min(100, *pct + 7);
        emit scanProgress(requestId, *pct);
        if (*pct >= 100)
            timer->deleteLater();
    });
    timer->start();
}
