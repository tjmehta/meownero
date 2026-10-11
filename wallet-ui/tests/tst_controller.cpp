#include "amount.h"
#include "walletcontroller.h"

#include <QSignalSpy>
#include <QTest>

// State checks for the shared controller: exact prepared payments bound to
// the session, stale replies and actions, unknown submissions, consent,
// recovery-word lifetime and the diagnostics allowlist.
class TstController : public QObject
{
    Q_OBJECT
    SimulatedBackend *backend = nullptr;
    WalletController *w = nullptr;

    QString kitB() { return w->kitWallets().at(0).toMap().value(QStringLiteral("short")).toString(); }

    void openReview(const QString &amountText = QStringLiteral("2.5"))
    {
        w->navigate(QStringLiteral("send"));
        w->pickKitWallet(QStringLiteral("b"));
        w->setSendField(QStringLiteral("amount"), amountText);
        QSignalSpy ready(w, &WalletController::reviewReady);
        w->requestReview();
        QCOMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("preparing"));
        QVERIFY(ready.wait(1000));
        QVERIFY(w->review().value(QStringLiteral("open")).toBool());
    }
    QString token() { return w->review().value(QStringLiteral("token")).toString(); }
    int outgoingAttemptRows()
    {
        int n = 0;
        for (const ledger::Tx &t : w->ledgerState().txs)
            if (t.type == ledger::TxType::Out && t.attemptId != 0)
                ++n;
        return n;
    }

private slots:
    void init()
    {
        backend = new SimulatedBackend(this);
        backend->prepareDelayMs = 20;
        backend->relayDelayMs = 30;
        backend->checkDelayMs = 20;
        backend->mineDelayMs = 10;
        backend->reconnectDelayMs = 10;
        backend->scanTickMs = 5;
        w = new WalletController(backend, this);
        w->setLocale(QLocale(QLocale::English, QLocale::UnitedStates));
        w->startAt(QStringLiteral("overview"), ledger::Story::Normal);
    }
    void cleanup()
    {
        delete w;
        delete backend;
    }

    void reviewShowsExactPreparedValuesAndSameTransactionIsRelayed()
    {
        openReview();
        const QVariantMap r = w->review();
        QCOMPARE(r.value(QStringLiteral("amount")).toString(), QStringLiteral("2.5 MEOW"));
        QCOMPARE(r.value(QStringLiteral("fee")).toString(), QStringLiteral("0.00006152 MEOW"));
        QCOMPARE(r.value(QStringLiteral("total")).toString(), QStringLiteral("2.50006152 MEOW"));
        QVERIFY(r.value(QStringLiteral("to")).toString().startsWith(QStringLiteral("48oicA")));
        QSignalSpy said(w, &WalletController::announce);
        QVERIFY(w->confirmSend(token()));
        QCOMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("submitting"));
        QTRY_COMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("result"));
        QCOMPARE(w->sendResult().value(QStringLiteral("kind")).toString(), QStringLiteral("sent"));
        QCOMPARE(backend->relayedRefs(), backend->preparedRefs()); // reviewed == relayed, never rebuilt
        QVERIFY(said.last().first().toString().startsWith(QStringLiteral("Sent.")));
        // Confirm cannot be replayed with the consumed token.
        QVERIFY(!w->confirmSend(QStringLiteral("review-1")));
    }

    void editingInvalidatesReview()
    {
        openReview();
        const QString old = token();
        w->setSendField(QStringLiteral("amount"), QStringLiteral("2.6"));
        QVERIFY(!w->review().value(QStringLiteral("open")).toBool());
        QVERIFY(!w->confirmSend(old));
        QCOMPARE(w->staleActionsRefused(), 1);
        QVERIFY(backend->relayedRefs().isEmpty());
    }

    void leavingSendWhilePreparingDropsTheLateReply()
    {
        w->navigate(QStringLiteral("send"));
        w->pickKitWallet(QStringLiteral("b"));
        w->setSendField(QStringLiteral("amount"), QStringLiteral("1"));
        QSignalSpy ready(w, &WalletController::reviewReady);
        w->requestReview();
        w->navigate(QStringLiteral("overview"));
        QTest::qWait(80);
        QCOMPARE(ready.count(), 0);
        QCOMPARE(w->staleRepliesDropped(), 1);
        w->navigate(QStringLiteral("send"));
        QCOMPARE(w->send().value(QStringLiteral("amount")).toString(), QStringLiteral("1")); // form keeps what was typed
        QCOMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("form"));
    }

    void lockAndNodeChangesInvalidatePreparedPayment()
    {
        openReview();
        QString t = token();
        const quint64 epoch = w->sessionEpoch();
        w->lock();
        QVERIFY(w->sessionEpoch() > epoch);
        QVERIFY(!w->confirmSend(t));
        w->unlock(QStringLiteral("simulated"));
        openReview();
        t = token();
        w->fixtureSetNodeState(QStringLiteral("offline"));
        QVERIFY(!w->confirmSend(t));
        QVERIFY(backend->relayedRefs().isEmpty());
        // Shell routes stay out of reach while locked.
        w->lock();
        w->navigate(QStringLiteral("overview"));
        QCOMPARE(w->route(), QStringLiteral("unlock"));
        w->unlock(QStringLiteral("wrong"));
        QCOMPARE(w->route(), QStringLiteral("unlock"));
        QVERIFY(!w->onb().value(QStringLiteral("unlockError")).toString().isEmpty());
    }

    void lateReplyAfterLockCannotReopenReview()
    {
        w->navigate(QStringLiteral("send"));
        w->pickKitWallet(QStringLiteral("b"));
        w->setSendField(QStringLiteral("amount"), QStringLiteral("1"));
        QSignalSpy ready(w, &WalletController::reviewReady);
        w->requestReview();
        w->lock();
        w->unlock(QStringLiteral("simulated"));
        w->navigate(QStringLiteral("send"));
        QTest::qWait(80);
        QCOMPARE(ready.count(), 0);
        QVERIFY(!w->review().value(QStringLiteral("open")).toBool());
    }

    void submissionUnderWayFinishesAfterLeavingSend()
    {
        openReview();
        QVERIFY(w->confirmSend(token()));
        w->navigate(QStringLiteral("activity"));
        QSignalSpy focus(w, &WalletController::focusHeading);
        QTRY_COMPARE(w->sendResult().value(QStringLiteral("kind")).toString(), QStringLiteral("sent"));
        QCOMPARE(focus.count(), 0); // outcome announced without moving focus
        QCOMPARE(w->route(), QStringLiteral("activity"));
    }

    void droppedSubmissionStaysUnknownUntilEvidence()
    {
        w->fixtureSetSendOutcome(QStringLiteral("drops"));
        w->fixtureSetUnknownResolves(QStringLiteral("notsent"));
        const quint64 before = w->ledgerState().balances().total;
        openReview(QStringLiteral("1.25"));
        QVERIFY(w->confirmSend(token()));
        QTRY_COMPARE(w->sendResult().value(QStringLiteral("kind")).toString(), QStringLiteral("unknown"));
        const QString row = w->sendResult().value(QStringLiteral("rowId")).toString();
        QVERIFY(w->ledgerState().hasUnknownSubmission());
        // Blocks another payment, never retries.
        w->sendAnother();
        QVERIFY(!w->send().value(QStringLiteral("canReview")).toBool());
        w->pickKitWallet(QStringLiteral("b"));
        w->setSendField(QStringLiteral("amount"), QStringLiteral("1"));
        w->requestReview();
        QCOMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("form"));
        QCOMPARE(backend->relayedRefs().size(), 1);
        // A new block without it proves nothing.
        w->fixtureAddBlocks(1);
        QVERIFY(w->detail(row).value(QStringLiteral("unknown")).toBool());
        // Only the node's absence proof resolves it to not sent, coins returned.
        w->reconcile(row);
        QTRY_VERIFY(w->detail(row).value(QStringLiteral("failed")).toBool());
        QCOMPARE(w->ledgerState().balances().total, before);
        QVERIFY(w->send().value(QStringLiteral("canReview")).toBool());
    }

    void unknownSubmissionFoundInBlockResolvesToWaiting()
    {
        w->fixtureSetSendOutcome(QStringLiteral("drops"));
        openReview(QStringLiteral("1"));
        QVERIFY(w->confirmSend(token()));
        QTRY_COMPARE(w->sendResult().value(QStringLiteral("kind")).toString(), QStringLiteral("unknown"));
        const QString row = w->sendResult().value(QStringLiteral("rowId")).toString();
        QSignalSpy said(w, &WalletController::announce);
        w->fixtureAddBlocks(1);
        QCOMPARE(w->detail(row).value(QStringLiteral("unknown")).toBool(), false);
        QVERIFY(said.last().first().toString().contains(QStringLiteral("so your node received it")));
    }

    void refusedSubmissionChangesNothing()
    {
        w->fixtureSetSendOutcome(QStringLiteral("refused"));
        const int rows = w->ledgerState().txs.size();
        const quint64 before = w->ledgerState().balances().unlocked;
        openReview();
        QVERIFY(w->confirmSend(token()));
        QTRY_COMPARE(w->sendResult().value(QStringLiteral("kind")).toString(), QStringLiteral("refused"));
        QCOMPARE(w->ledgerState().txs.size(), rows);
        QCOMPARE(w->ledgerState().balances().unlocked, before);
    }

    void remoteConsentIsBoundToSessionAndNetwork()
    {
        // Regtest never offers someone else's node.
        w->pickNode(QStringLiteral("remote"));
        QCOMPARE(w->nodePick(), QString());
        w->fixtureSetNetwork(QStringLiteral("testnet"));
        w->navigate(QStringLiteral("node"));
        w->pickNode(QStringLiteral("remote"));
        QCOMPARE(w->nodeState(), QStringLiteral("synced")); // a pick changes nothing
        QSignalSpy asked(w, &WalletController::consentRequested);
        w->applyNodePick();
        QCOMPARE(asked.count(), 1);
        QCOMPARE(w->nodeState(), QStringLiteral("synced")); // opening the dialog changes nothing
        const QString t = w->consentToken();
        // Escape closes the dialog only: nothing connects and the pick stays.
        w->dismissConsent();
        QCOMPARE(w->nodeState(), QStringLiteral("synced"));
        QCOMPARE(w->nodePick(), QStringLiteral("remote"));
        QVERIFY(!w->confirmRemoteNode(t));
        w->applyNodePick();
        const QString tKeep = w->consentToken();
        // Keep current node clears the pick and changes nothing.
        w->keepCurrentNode();
        QVERIFY(!w->confirmRemoteNode(tKeep));
        QCOMPARE(w->nodeState(), QStringLiteral("synced"));
        QVERIFY(!w->confirmRemoteNode(t));
        // Network change while the dialog is open: stale consent is refused.
        w->pickNode(QStringLiteral("remote"));
        w->applyNodePick();
        const QString t2 = w->consentToken();
        w->fixtureSetNetwork(QStringLiteral("regtest"));
        QVERIFY(!w->consentOpen());
        QVERIFY(!w->confirmRemoteNode(t2));
        QCOMPARE(w->nodeState(), QStringLiteral("synced"));
        // Valid consent connects, and is announced.
        w->fixtureSetNetwork(QStringLiteral("testnet"));
        w->pickNode(QStringLiteral("remote"));
        w->applyNodePick();
        QSignalSpy said(w, &WalletController::announce);
        QVERIFY(w->confirmRemoteNode(w->consentToken()));
        QCOMPARE(w->nodeState(), QStringLiteral("remote"));
        QVERIFY(said.last().first().toString().contains(QStringLiteral("someone else's node")));
        // Back to own node: one Connect, no dialog.
        w->pickNode(QStringLiteral("local"));
        w->applyNodePick();
        QCOMPARE(w->nodeState(), QStringLiteral("synced"));
    }

    void addressRules()
    {
        w->navigate(QStringLiteral("send"));
        auto toErrorFor = [this](const QString &kind) {
            w->fixtureFillSend(kind);
            return w->send().value(QStringLiteral("toError")).toString() + w->send().value(QStringLiteral("amountError")).toString();
        };
        QVERIFY(toErrorFor(QStringLiteral("typo")).contains(QStringLiteral("test wallets in your Meownero test kit")));
        QVERIFY(toErrorFor(QStringLiteral("mainnet")).contains(QStringLiteral("mainnet address")));
        QVERIFY(toErrorFor(QStringLiteral("wrongnet")).contains(QStringLiteral("Meownero testnet address")));
        QVERIFY(toErrorFor(QStringLiteral("short")).contains(QStringLiteral("incomplete")));
        QVERIFY(toErrorFor(QStringLiteral("13dp")).contains(QStringLiteral("This amount has 13")));
        QVERIFY(toErrorFor(QStringLiteral("locked")).contains(QStringLiteral("spendable now")));
        QVERIFY(toErrorFor(QStringLiteral("valid")).isEmpty());
    }

    void dustAndLargeBalances()
    {
        w->fixtureSetStory(QStringLiteral("dust"));
        QVariantMap b = w->balance();
        QCOMPARE(b.value(QStringLiteral("spendable")).toMap().value(QStringLiteral("text")).toString(), QStringLiteral("0.000000000001"));
        QVERIFY(b.value(QStringLiteral("belowFee")).toBool());
        QVERIFY(!w->send().value(QStringLiteral("canReview")).toBool());
        QVERIFY(w->send().value(QStringLiteral("disabledReason")).toString().contains(QStringLiteral("smaller than a network fee")));
        w->fixtureSetStory(QStringLiteral("large"));
        b = w->balance();
        const QVariantMap s = b.value(QStringLiteral("spendable")).toMap();
        QVERIFY(s.value(QStringLiteral("more")).toBool());
        QVERIFY(!s.value(QStringLiteral("text")).toString().contains(QStringLiteral("…")));
        w->toggleExact();
        QCOMPARE(w->balance().value(QStringLiteral("spendable")).toMap().value(QStringLiteral("more")).toBool(), false);
    }

    void recoveryWordsHideOnLeaveLockAndBackground()
    {
        w->startOver();
        QCOMPARE(w->route(), QStringLiteral("welcome"));
        w->navigate(QStringLiteral("create-1"));
        w->submitCreateDetails(QStringLiteral("Second"), QStringLiteral("passw0rd!"), QStringLiteral("passw0rd!"));
        QCOMPARE(w->route(), QStringLiteral("create-2"));
        QCOMPARE(w->displayedWords().first(), QStringLiteral("•••••"));
        w->setAcknowledged(true);
        QVERIFY(!w->onb().value(QStringLiteral("ack")).toBool()); // not before reveal
        w->revealWords();
        QCOMPARE(w->displayedWords().at(19), QStringLiteral("verification"));
        w->navigate(QStringLiteral("create-1"));
        QCOMPARE(w->displayedWords().first(), QStringLiteral("•••••"));
        w->navigate(QStringLiteral("create-2"));
        w->revealWords();
        w->hideRecoveryWords(); // app deactivated
        QCOMPARE(w->displayedWords().first(), QStringLiteral("•••••"));
        w->revealWords();
        w->setAcknowledged(true);
        w->navigate(QStringLiteral("create-3"));
        QSignalSpy said(w, &WalletController::announce);
        w->pickQuizWord(4, QStringLiteral("tabby")); // a wrong pick is marked and announced
        QVERIFY(w->onb().value(QStringLiteral("wrong")).toMap().contains(QStringLiteral("4")));
        QCOMPARE(said.last().first().toString(), QStringLiteral("That isn't word 4. Check your paper."));
        const QStringList sample = {QStringLiteral("lantern"), QStringLiteral("marble"), QStringLiteral("meadow")};
        w->pickQuizWord(4, sample.at(0));
        w->pickQuizWord(13, sample.at(1));
        w->pickQuizWord(22, sample.at(2));
        w->navigate(QStringLiteral("create-4"));
        QCOMPARE(w->route(), QStringLiteral("create-4"));
        w->openNewWallet();
        QCOMPARE(w->route(), QStringLiteral("overview"));
        QCOMPARE(w->walletName(), QStringLiteral("Second"));
        // Re-reveal needs the wallet password.
        w->navigate(QStringLiteral("wallet"));
        w->requestSeed();
        w->submitSeedPassword(QStringLiteral("simulated"));
        QCOMPARE(w->seedDialog(), QStringLiteral("password"));
        w->submitSeedPassword(QStringLiteral("passw0rd!"));
        QCOMPARE(w->seedDialog(), QStringLiteral("words"));
        QCOMPARE(w->displayedWords().at(8), QStringLiteral("laboratory"));
        w->lock();
        QCOMPARE(w->seedDialog(), QStringLiteral("none"));
        QCOMPARE(w->displayedWords().first(), QStringLiteral("•••••"));
    }

    void restoreValidationAndPaste()
    {
        w->startOver();
        w->navigate(QStringLiteral("restore-1"));
        w->setRestoreWord(0, QStringLiteral("whisker saucer velvet"));
        QCOMPARE(w->restoreWords().at(2), QStringLiteral("velvet"));
        w->submitRestoreWords();
        QVERIFY(w->onb().value(QStringLiteral("errors")).toMap().value(QStringLiteral("words")).toString().contains(QStringLiteral("You've entered 3")));
        w->fixtureFillRestore(QStringLiteral("badword"));
        QVERIFY(w->onb().value(QStringLiteral("errors")).toMap().value(QStringLiteral("words")).toString().contains(QStringLiteral("“mittens” (word 7)")));
        w->fixtureFillRestore(QStringLiteral("checksum"));
        QVERIFY(w->onb().value(QStringLiteral("errors")).toMap().value(QStringLiteral("words")).toString().contains(QStringLiteral("don't add up")));
        w->fixtureFillRestore(QStringLiteral("sample"));
        w->submitRestoreWords();
        QCOMPARE(w->route(), QStringLiteral("restore-2"));
        w->submitRestoreDetails(QStringLiteral("99999"), QStringLiteral("Restored"), QStringLiteral("correct horse"));
        QVERIFY(w->onb().value(QStringLiteral("errors")).toMap().value(QStringLiteral("height")).toString().contains(QStringLiteral("in the future")));
        w->submitRestoreDetails(QStringLiteral("1,203"), QStringLiteral("Test wallet"), QStringLiteral("correct horse"));
        QVERIFY(w->onb().value(QStringLiteral("errors")).toMap().value(QStringLiteral("name")).toString().contains(QStringLiteral("already exists")));
        w->submitRestoreDetails(QStringLiteral("1,203"), QStringLiteral("Restored"), QStringLiteral("correct horse"));
        QCOMPARE(w->route(), QStringLiteral("restore-3"));
        QVERIFY(w->restoreWords().join(QString()).isEmpty()); // typed words are not kept
        QTRY_COMPARE(w->onb().value(QStringLiteral("scan")).toInt(), 100);
        w->openRestoredWallet();
        QCOMPARE(w->route(), QStringLiteral("overview"));
        QCOMPARE(w->createdBlock(), 1203);
    }

    void diagnosticsUseAnAllowlist()
    {
        openReview();
        w->confirmSend(token());
        QTRY_COMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("result"));
        w->navigate(QStringLiteral("wallet"));
        w->requestSeed();
        w->submitSeedPassword(QStringLiteral("simulated"));
        const QString d = w->diagnostics();
        for (const QString &secret : {QStringLiteral("whisker"), QStringLiteral("verification"), QStringLiteral("simulated\n"),
                                      QStringLiteral("4AKvVK"), QStringLiteral("48oicA"), QStringLiteral("f344d362"),
                                      QStringLiteral("Lunch test"), QStringLiteral("2.5")})
            QVERIFY2(!d.contains(secret), qPrintable(secret));
        QVERIFY(d.contains(QStringLiteral("network=regtest")));
    }

    void nodeStatesNamePartAtFaultAndAreAnnounced()
    {
        QSignalSpy said(w, &WalletController::announce);
        w->fixtureSetNodeState(QStringLiteral("engine-down"));
        QCOMPARE(said.last().first().toString(), QStringLiteral("Connection: Wallet engine stopped. Sending paused"));
        QVERIFY(w->send().value(QStringLiteral("disabledReason")).toString().contains(QStringLiteral("wallet engine")));
        w->retryNode();
        QCOMPARE(said.last().first().toString().left(22), QStringLiteral("Connection: Connecting"));
        QTRY_COMPARE(w->nodeState(), QStringLiteral("synced"));
        w->fixtureSetNodeState(QStringLiteral("wrong-net"));
        QCOMPARE(w->node().value(QStringLiteral("height")).toString(), QStringLiteral("—"));
        QVERIFY(w->send().value(QStringLiteral("disabledReason")).toString().contains(QStringLiteral("your node")));
    }

    // Security review TJS-2018 finding 1 (probe p1b): lock while submitting, then try
    // "Use a different wallet" and a restore. The wallet change waits; the relayed
    // payment is recorded against its own wallet; sending works afterwards.
    void walletChangeWaitsForSubmissionInFlight()
    {
        backend->relayDelayMs = 300;
        openReview();
        QVERIFY(w->confirmSend(token()));
        w->lock();
        QSignalSpy said(w, &WalletController::announce);
        w->navigate(QStringLiteral("welcome")); // unlock page: "Use a different wallet"
        QCOMPARE(w->route(), QStringLiteral("unlock"));
        QVERIFY(said.last().first().toString().contains(QStringLiteral("still being submitted")));
        w->fixtureFillRestore(QStringLiteral("sample"));
        QCOMPARE(w->route(), QStringLiteral("unlock"));
        QTRY_COMPARE(outgoingAttemptRows(), 1); // the relayed payment has a row
        QCOMPARE(backend->relayedRefs().size(), 1);
        w->navigate(QStringLiteral("welcome")); // now allowed
        QCOMPARE(w->route(), QStringLiteral("welcome"));
        w->navigate(QStringLiteral("unlock"));
        w->unlock(QStringLiteral("simulated"));
        openReview(QStringLiteral("1"));
        QVERIFY(w->confirmSend(token())); // sending is not wedged
        QTRY_COMPARE(backend->relayedRefs().size(), 2);
    }

    // Finding 1 via the reviewer fixture (probe p1c).
    void fixtureStoryChangeWaitsForSubmission()
    {
        backend->relayDelayMs = 200;
        openReview();
        QVERIFY(w->confirmSend(token()));
        const int rows = w->ledgerState().txs.size();
        w->fixtureSetStory(QStringLiteral("normal"));
        QTRY_COMPARE(w->ledgerState().txs.size(), rows + 1); // history was not replaced; the send landed
        w->sendAnother();
        openReview(QStringLiteral("1"));
        QVERIFY(w->confirmSend(token()));
    }

    // A matched relay reply never leaves the attempt set, even for another wallet generation.
    void noDroppedReplyLeavesAttemptSet()
    {
        backend->relayDelayMs = 100;
        openReview();
        QVERIFY(w->confirmSend(token()));
        QTRY_COMPARE(w->send().value(QStringLiteral("step")).toString(), QStringLiteral("result"));
        w->navigate(QStringLiteral("wallet"));
        w->startOver();
        QCOMPARE(w->route(), QStringLiteral("welcome"));
    }

    // Review risk R1 (probes p2a, p2b): node-check evidence is bound to the session that asked.
    void nodeCheckReplyDroppedAfterNodeLossOrLock()
    {
        w->fixtureSetSendOutcome(QStringLiteral("drops"));
        w->fixtureSetUnknownResolves(QStringLiteral("notsent"));
        backend->checkDelayMs = 150;
        openReview(QStringLiteral("1"));
        QVERIFY(w->confirmSend(token()));
        QTRY_COMPARE(w->sendResult().value(QStringLiteral("kind")).toString(), QStringLiteral("unknown"));
        const QString row = w->sendResult().value(QStringLiteral("rowId")).toString();
        w->reconcile(row);
        w->fixtureSetNodeState(QStringLiteral("offline"));
        QTest::qWait(300);
        QVERIFY(w->detail(row).value(QStringLiteral("unknown")).toBool());
        w->fixtureSetNodeState(QStringLiteral("synced"));
        w->reconcile(row); // not blocked by the dropped check
        w->lock();
        QTest::qWait(300);
        QVERIFY(w->detail(row).value(QStringLiteral("unknown")).toBool());
        w->unlock(QStringLiteral("simulated"));
        w->reconcile(row);
        QTRY_VERIFY(w->detail(row).value(QStringLiteral("failed")).toBool());
    }
};

QTEST_MAIN(TstController)
#include "tst_controller.moc"
