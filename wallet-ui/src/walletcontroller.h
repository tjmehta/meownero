#pragma once

// The one typed controller between QML and the wallet engine. It owns exact
// atomic amounts, the session identity, prepared payments, consent, async
// replies and every state transition in the experience contract. QML only
// reads display values and calls the actions below; it never sees RPC
// methods, credentials, recovery words (unless revealed) or raw integers to
// do arithmetic on.

#include "ledger.h"
#include "simulatedbackend.h"

#include <QLocale>
#include <QObject>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>

class ActivityModel;

class WalletController : public QObject
{
    Q_OBJECT
    // Navigation and presentation
    Q_PROPERTY(QString route READ route NOTIFY changed)
    Q_PROPERTY(bool onboarding READ onboarding NOTIFY changed)
    Q_PROPERTY(bool simulated READ simulated CONSTANT)
    Q_PROPERTY(bool reducedMotion READ reducedMotion NOTIFY reducedMotionChanged)
    Q_PROPERTY(bool exactDigits READ exactDigits NOTIFY changed)
    Q_PROPERTY(QString toastText READ toastText NOTIFY toastChanged)
    // Network identity (from the node's reported network, never chosen)
    Q_PROPERTY(QString networkKey READ networkKey NOTIFY changed)
    Q_PROPERTY(QString networkName READ networkName NOTIFY changed)
    Q_PROPERTY(QString networkTitle READ networkTitle NOTIFY changed)
    Q_PROPERTY(QString networkSay READ networkSay NOTIFY changed)
    Q_PROPERTY(QString networkProse READ networkProse NOTIFY changed)
    // Node and engine
    Q_PROPERTY(QString nodeState READ nodeState NOTIFY changed)
    Q_PROPERTY(QVariantMap node READ node NOTIFY changed)
    Q_PROPERTY(QVariantMap condition READ condition NOTIFY changed)
    Q_PROPERTY(QVariantMap reorg READ reorg NOTIFY changed)
    Q_PROPERTY(bool canTransact READ canTransact NOTIFY changed)
    Q_PROPERTY(QString nodePick READ nodePick NOTIFY changed)
    Q_PROPERTY(bool consentOpen READ consentOpen NOTIFY changed)
    Q_PROPERTY(QString consentToken READ consentToken NOTIFY changed)
    Q_PROPERTY(QString remoteExposure READ remoteExposure CONSTANT)
    // Balances and activity
    Q_PROPERTY(QVariantMap balance READ balance NOTIFY changed)
    Q_PROPERTY(ActivityModel *activity READ activity CONSTANT)
    Q_PROPERTY(ActivityModel *recentActivity READ recentActivity CONSTANT)
    Q_PROPERTY(int pendingCount READ pendingCount NOTIFY changed)
    Q_PROPERTY(QString walletName READ walletName NOTIFY changed)
    Q_PROPERTY(QString receiveAddress READ receiveAddress NOTIFY changed)
    Q_PROPERTY(QVariantList kitWallets READ kitWallets NOTIFY changed)
    Q_PROPERTY(int createdBlock READ createdBlock NOTIFY changed)
    Q_PROPERTY(int tip READ tip NOTIFY changed)
    // Send
    Q_PROPERTY(QVariantMap send READ send NOTIFY changed)
    Q_PROPERTY(QVariantMap review READ review NOTIFY changed)
    Q_PROPERTY(QVariantMap sendResult READ sendResult NOTIFY changed)
    // First run, recovery words, restore, lock
    Q_PROPERTY(QVariantMap onb READ onb NOTIFY changed)
    Q_PROPERTY(QStringList displayedWords READ displayedWords NOTIFY changed)
    Q_PROPERTY(QStringList restoreWords READ restoreWords NOTIFY changed)
    Q_PROPERTY(QString seedDialog READ seedDialog NOTIFY changed)
    Q_PROPERTY(QString seedError READ seedError NOTIFY changed)
    Q_PROPERTY(QString passwordHint READ passwordHint NOTIFY changed)
    // Reviewer fixtures (separate window)
    Q_PROPERTY(QVariantMap fixtures READ fixtures NOTIFY changed)

public:
    explicit WalletController(SimulatedBackend *backend, QObject *parent = nullptr);
    ~WalletController() override;

    void setLocale(const QLocale &locale) { m_locale = locale; emit changed(); }
    void startAt(const QString &route, ledger::Story story);

    QString route() const { return m_route; }
    bool onboarding() const;
    bool simulated() const { return true; }
    bool reducedMotion() const;
    bool exactDigits() const { return m_exact; }
    QString toastText() const { return m_toast; }

    QString networkKey() const { return m_testnet ? QStringLiteral("testnet") : QStringLiteral("regtest"); }
    QString networkName() const;
    QString networkTitle() const;
    QString networkSay() const;
    QString networkProse() const;

    QString nodeState() const { return m_nodeState; }
    QVariantMap node() const;
    QVariantMap condition() const;
    QVariantMap reorg() const;
    bool canTransact() const;
    QString nodePick() const { return m_nodePick; }
    bool consentOpen() const { return !m_consentToken.isEmpty(); }
    QString consentToken() const { return m_consentToken; }
    static QString remoteExposure();

    QVariantMap balance() const;
    ActivityModel *activity() const { return m_activity; }
    ActivityModel *recentActivity() const { return m_recent; }
    int pendingCount() const { return m_ledger.pendingCount(); }
    QString walletName() const { return m_walletName; }
    QString receiveAddress() const;
    QVariantList kitWallets() const;
    int createdBlock() const { return m_ledger.created; }
    int tip() const { return m_ledger.tip; }

    QVariantMap send() const;
    QVariantMap review() const;
    QVariantMap sendResult() const;

    QVariantMap onb() const;
    QStringList displayedWords() const;
    QStringList restoreWords() const { return m_restoreWords; }
    QString seedDialog() const { return m_seedDialog; }
    QString seedError() const { return m_seedError; }
    QString passwordHint() const;

    QVariantMap fixtures() const;

    // Display helpers (pure formatting of controller-owned values)
    QVariantMap amountView(quint64 magnitude, bool negative, bool exact, bool sign) const;
    QString amountText(quint64 magnitude, bool exact = true) const;
    QString rowSubtitle(const ledger::Tx &tx) const;
    const ledger::Ledger &ledgerState() const { return m_ledger; }

    // ---- Actions ----
    Q_INVOKABLE void navigate(const QString &route);
    Q_INVOKABLE void toggleExact();
    Q_INVOKABLE void copyAddress();
    Q_INVOKABLE void copyTransactionId(const QString &rowId);
    Q_INVOKABLE QVariantMap detail(const QString &rowId) const;

    Q_INVOKABLE void setSendField(const QString &field, const QString &value);
    Q_INVOKABLE void pickKitWallet(const QString &key);
    Q_INVOKABLE void useMax();
    Q_INVOKABLE void requestReview();
    Q_INVOKABLE void cancelReview();
    Q_INVOKABLE bool confirmSend(const QString &reviewToken);
    Q_INVOKABLE void sendAnother();
    Q_INVOKABLE void reconcile(const QString &rowId);
    Q_INVOKABLE void mineTestCoins();
    Q_INVOKABLE void retryNode();
    Q_INVOKABLE void dismissReorg();

    Q_INVOKABLE void pickNode(const QString &choice);
    Q_INVOKABLE void applyNodePick();
    Q_INVOKABLE bool confirmRemoteNode(const QString &token);
    Q_INVOKABLE void keepCurrentNode();
    Q_INVOKABLE void dismissConsent();

    Q_INVOKABLE void submitCreateDetails(const QString &name, const QString &password, const QString &repeat);
    Q_INVOKABLE void revealWords();
    Q_INVOKABLE void setAcknowledged(bool ack);
    Q_INVOKABLE QStringList quizOptions(int position) const;
    Q_INVOKABLE void pickQuizWord(int position, const QString &word);
    Q_INVOKABLE void openNewWallet();
    Q_INVOKABLE void setRestoreWord(int index, const QString &text);
    Q_INVOKABLE void submitRestoreWords();
    Q_INVOKABLE void submitRestoreDetails(const QString &height, const QString &name, const QString &password);
    Q_INVOKABLE void openRestoredWallet();
    Q_INVOKABLE void unlock(const QString &password);
    Q_INVOKABLE void lock();
    Q_INVOKABLE void requestSeed();
    Q_INVOKABLE void submitSeedPassword(const QString &password);
    Q_INVOKABLE void hideRecoveryWords();
    Q_INVOKABLE void startOver();
    Q_INVOKABLE QString diagnostics() const;

    // Reviewer fixtures: labelled simulation controls, not app features.
    Q_INVOKABLE void fixtureSetNetwork(const QString &key);
    Q_INVOKABLE void fixtureSetNodeState(const QString &state);
    Q_INVOKABLE void fixtureSetStory(const QString &story);
    Q_INVOKABLE void fixtureSetSendOutcome(const QString &outcome);
    Q_INVOKABLE void fixtureSetUnknownResolves(const QString &resolves);
    Q_INVOKABLE void fixtureAddBlocks(int count);
    Q_INVOKABLE void fixtureReorg();
    Q_INVOKABLE void fixtureFillSend(const QString &kind);
    Q_INVOKABLE void fixtureFillRestore(const QString &kind);

    // Counters for evidence: late replies dropped, stale confirmations refused.
    int staleRepliesDropped() const { return m_staleDropped; }
    int staleActionsRefused() const { return m_staleRefused; }
    quint64 sessionEpoch() const { return m_epoch; }
    SimulatedBackend *backend() const { return m_backend; }

signals:
    void changed();
    void reducedMotionChanged();
    void toastChanged();
    void announce(const QString &message);
    void focusHeading();
    void focusField(const QString &name);
    void reviewReady();
    void reviewClosed();
    void consentRequested();
    void reconciled(const QString &rowId);
    void seedRequested();
    void consentClosed();
    void seedClosed();

private:
    struct Prepared {
        QString token;
        quint64 epoch = 0;
        quint64 formRevision = 0;
        QString recipient;
        quint64 amount = 0;
        quint64 fee = 0;
        QString note;
        QString preparedRef;
        QString txid;
    };
    struct Attempt {
        quint64 id = 0;
        quint64 walletGeneration = 0;
        Prepared prepared;
        quint64 changeBack = 0;
    };

    void invalidateSession(const QString &why);
    bool refuseWalletChange();
    void setNode(const QString &state, bool announceIt = true);
    void setToast(const QString &text);
    void say(const QString &text);
    void refreshModels();
    bool validateSend();
    void loadWallet(ledger::Story story, const QString &name);
    QString chipAccessible() const;
    QString addressFor(const QString &key) const;
    QString kitLabelFor(const QString &address) const;
    QString pausedUntil() const;
    QString pausedNeeds() const;
    void onPrepared(quint64 requestId, const QString &ref, quint64 fee, const QString &txid);
    void onRelayFinished(quint64 attemptId, SimulatedBackend::SendOutcome outcome, const QString &reason);
    void onChecked(quint64 requestId, const QString &txid, bool found);
    void onBlocks(quint64 requestId, int count);
    void onReconnected(quint64 requestId);
    void onScan(quint64 requestId, int percent);

    SimulatedBackend *m_backend;
    ActivityModel *m_activity;
    ActivityModel *m_recent;
    QLocale m_locale;

    QString m_route = QStringLiteral("welcome");
    bool m_exact = false;
    QString m_toast;
    int m_toastSerial = 0;

    bool m_testnet = false;
    QString m_nodeState = QStringLiteral("synced");
    QString m_nodePick; // "", "local" or "remote": a pick changes nothing until Connect
    QString m_consentToken;
    quint64 m_consentEpoch = 0;
    int m_nodePct = 62;
    int m_scanPct = 48;
    qint64 m_lastSyncedMs = 0;
    quint64 m_reconnectRequest = 0;

    ledger::Ledger m_ledger;
    QString m_walletName = QStringLiteral("Test wallet");
    QByteArray m_passwordDigest;
    quint64 m_walletGeneration = 0;
    bool m_fixtureWallet = false;
    std::optional<std::pair<int, int>> m_reorg; // height, count

    // Session identity: bumped by lock, wallet, node and network changes.
    quint64 m_epoch = 1;
    quint64 m_nextId = 1;

    QString m_sendStep = QStringLiteral("form"); // form|preparing|submitting|result
    QString m_sendTo, m_sendAmount, m_sendNote;
    QString m_toError, m_amountError;
    quint64 m_formRevision = 0;
    quint64 m_prepRequest = 0;
    quint64 m_prepEpoch = 0;
    quint64 m_prepFormRevision = 0;
    std::optional<Prepared> m_prepared;
    std::optional<Attempt> m_attempt;
    QString m_resultKind; // sent|refused|unknown
    QString m_resultRowId;
    QString m_resultReason;
    quint64 m_resultAmount = 0;
    quint64 m_resultFee = 0;
    quint64 m_resultChange = 0;
    QString m_resultTo;
    QString m_resultTxid;
    quint64 m_checkRequest = 0;
    QString m_checkRowId;
    quint64 m_checkEpoch = 0;
    quint64 m_mineRequest = 0;

    // Onboarding
    QString m_onbName = QStringLiteral("Test wallet");
    QVariantMap m_onbErrors;
    bool m_wordsRevealed = false;
    bool m_ack = false;
    QMap<int, QString> m_picks, m_wrong;
    QStringList m_restoreWords;
    QList<int> m_badWords;
    QString m_restoreHeight;
    quint64 m_scanRequest = 0;
    int m_restoreScan = 0;
    QString m_unlockError;
    QString m_seedDialog = QStringLiteral("none"); // none|password|words
    QString m_seedError;
    QByteArray m_pendingDigest;
    bool m_hasWallet = false;
    bool m_locked = false;
    quint64 m_mineGeneration = 0;
    QString m_cleanTo;
    quint64 m_parsedAmount = 0;

    int m_staleDropped = 0;
    int m_staleRefused = 0;
};
