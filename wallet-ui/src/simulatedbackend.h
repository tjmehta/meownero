#pragma once

// Deterministic, explicitly simulated wallet engine and node. It opens no
// socket, file or process. It stands where the authenticated loopback
// wallet RPC client will go, and exposes only the typed calls the controller
// needs (an allowlist by construction): there is no generic "call method".
//
// Every reply is asynchronous and carries the caller's request or attempt id,
// so the controller can drop late replies that no longer match its state.

#include <QObject>
#include <QSet>
#include <QString>

class SimulatedBackend : public QObject
{
    Q_OBJECT
public:
    enum class SendOutcome { Accepted, Refused, ConnectionDrops };
    Q_ENUM(SendOutcome)
    enum class UnknownResolves { ReachedNode, NotSent };
    Q_ENUM(UnknownResolves)

    explicit SimulatedBackend(QObject *parent = nullptr);

    // Scenario knobs, set only from reviewer fixtures and tests.
    SendOutcome nextSendOutcome = SendOutcome::Accepted;
    UnknownResolves unknownResolves = UnknownResolves::ReachedNode;
    int prepareDelayMs = 700;
    int relayDelayMs = 1400;
    int checkDelayMs = 800;
    int mineDelayMs = 400;
    int reconnectDelayMs = 1200;
    int scanTickMs = 160;

    // transfer {do_not_relay:true}: builds the exact transaction, sends nothing.
    void prepareTransfer(quint64 requestId, const QString &recipient, quint64 atomic);
    // wallet relay_tx of a previously prepared transaction, by its reference.
    void relayPrepared(quint64 attemptId, const QString &preparedRef);
    // Evidence for an unknown submission: in the pool/a block, or proven absent.
    void checkSubmission(quint64 requestId, const QString &txid);
    void generateBlocks(quint64 requestId, int count);
    void reconnect(quint64 requestId);
    void scanRestore(quint64 requestId);

    // For tests and evidence: what was actually relayed, in order.
    QStringList relayedRefs() const { return m_relayed; }
    QStringList preparedRefs() const { return m_issuedOrder; }

signals:
    void transferPrepared(quint64 requestId, const QString &preparedRef, quint64 fee, const QString &txid);
    void relayFinished(quint64 attemptId, SimulatedBackend::SendOutcome outcome, const QString &nodeReason);
    void submissionChecked(quint64 requestId, const QString &txid, bool foundByNode);
    void blocksGenerated(quint64 requestId, int count);
    void reconnected(quint64 requestId);
    void scanProgress(quint64 requestId, int percent);

private:
    QSet<QString> m_unrelayed;
    QStringList m_issuedOrder;
    QStringList m_relayed;
    int m_prepareCounter = 0;
};
