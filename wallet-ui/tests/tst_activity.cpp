#include "activitymodel.h"
#include "amount.h"
#include "walletcontroller.h"
#include <QAbstractItemModelTester>
#include <QPersistentModelIndex>
#include <QSignalSpy>
#include <QTest>

class TstActivity : public QObject
{
    Q_OBJECT
private slots:
    void fixtureRowsAndExactDigits()
    {
        SimulatedBackend backend;
        WalletController w(&backend);
        w.setLocale(QLocale(QLocale::English, QLocale::UnitedStates));
        w.startAt(QStringLiteral("overview"), ledger::Story::Normal);
        auto *model = w.activity();
        QAbstractItemModelTester tester(model, QAbstractItemModelTester::FailureReportingMode::QtTest);
        QCOMPARE(model->count(), 4);
        const QStringList ids{"s1", "r2", "r1", "m1"};
        const QStringList subtitles{"To Test wallet B · Lunch test", "Sender not shown", "From Jonas's test wallet", "Blocks 1,205–1,274"};
        for (int i = 0; i < 4; ++i) {
            QCOMPARE(model->data(model->index(i), ActivityModel::RowIdRole).toString(), ids[i]);
            QCOMPARE(model->data(model->index(i), ActivityModel::SubtitleRole).toString(), subtitles[i]);
            QCOMPARE(w.recentActivity()->data(w.recentActivity()->index(i), ActivityModel::RowIdRole).toString(), ids[i]);
        }
        const QPersistentModelIndex tiny(model->index(1));
        QCOMPARE(model->data(tiny, ActivityModel::AmountTextRole).toString(), QStringLiteral("+0.000000000001"));
        const auto accessible = model->data(tiny, ActivityModel::AmountAccessibleRole);
        QSignalSpy reset(model, &QAbstractItemModel::modelReset);
        QSignalSpy changed(model, &QAbstractItemModel::dataChanged);
        w.toggleExact();
        QCOMPARE(reset.count(), 0);
        QVERIFY(tiny.isValid());
        QCOMPARE(model->data(tiny, ActivityModel::RowIdRole).toString(), QStringLiteral("r2"));
        QCOMPARE(model->data(tiny, ActivityModel::AmountAccessibleRole), accessible);
        QVERIFY(changed.count() > 0);
        for (const auto &signal : changed) {
            const auto roles = qvariant_cast<QList<int>>(signal.at(2));
            QVERIFY(!roles.contains(ActivityModel::RowIdRole));
            QVERIFY(!roles.contains(ActivityModel::StatusTextRole));
            QVERIFY(!roles.contains(ActivityModel::SubtitleRole));
        }
    }

    void populatedHistoryMatchesIndependentFormattingAndStableOrder()
    {
        SimulatedBackend backend;
        WalletController w(&backend);
        const QLocale locale(QLocale::German, QLocale::Germany);
        w.setLocale(locale);
        w.startAt(QStringLiteral("overview"), ledger::Story::Empty);
        // The object is mutable; this test-only fixture uses its existing ledger
        // access rather than adding a history injection API to the application.
        auto &l = const_cast<ledger::Ledger &>(w.ledgerState());
        for (int i = 0; i < 1000; ++i) {
            ledger::Tx t;
            t.id = QString::number(i);
            t.type = i % 3 == 0 ? ledger::TxType::Out : ledger::TxType::In;
            t.amount = 1234567890123ULL + i;
            t.height = i % 7 == 0 ? std::optional<int>() : std::optional<int>(1200 + i % 100);
            t.status = i % 17 == 0 ? ledger::TxStatus::Failed : i % 19 == 0 ? ledger::TxStatus::Unknown : ledger::TxStatus::Normal;
            l.txs.append(t);
        }
        w.toggleExact();
        auto *m = w.activity();
        QAbstractItemModelTester tester(m, QAbstractItemModelTester::FailureReportingMode::QtTest);
        QList<int> expected;
        // Explicit oracle: unconfirmed, then descending heights; insertion order
        // within ties, including failed/unknown records.
        for (int i = 0; i < 1000; ++i) if (i % 7 == 0) expected.append(i);
        for (int h = 1299; h >= 1200; --h)
            for (int i = 0; i < 1000; ++i)
                if (i % 7 != 0 && 1200 + i % 100 == h) expected.append(i);
        QCOMPARE(m->count(), 1000);
        QCOMPARE(w.recentActivity()->count(), 4);
        for (bool exact : {true, false}) {
            if (!exact) w.toggleExact();
            for (int row = 0; row < 1000; ++row) {
                const auto &t = l.txs[expected[row]];
                const auto idx = m->index(row);
                const bool out = t.type == ledger::TxType::Out;
                const auto f = amount::format(t.amount, out, exact, true, locale);
                const auto full = amount::format(t.amount, out, true, true, locale);
                QCOMPARE(m->data(idx, ActivityModel::RowIdRole).toString(), t.id);
                QCOMPARE(m->data(idx, ActivityModel::AmountTextRole).toString(), f.textWithoutEllipsis());
                QCOMPARE(m->data(idx, ActivityModel::MoreDigitsRole).toBool(), f.moreDigits);
                QCOMPARE(m->data(idx, ActivityModel::AmountAccessibleRole).toString(), full.text() + QStringLiteral(" MEOW"));
                QCOMPARE(m->data(idx, ActivityModel::StatusTextRole).toString(), ledger::statusText(l, t));
                if (row < 4) QCOMPARE(w.recentActivity()->data(w.recentActivity()->index(row), ActivityModel::RowIdRole).toString(), t.id);
            }
        }
    }

    void statusRefreshKeepsRowsAndReorderRebuildsCorrectly()
    {
        SimulatedBackend backend;
        WalletController w(&backend);
        w.startAt(QStringLiteral("overview"), ledger::Story::Normal);
        auto *m = w.activity();
        const QPersistentModelIndex outgoing(m->index(0));
        QSignalSpy resets(m, &QAbstractItemModel::modelReset);
        w.fixtureAddBlocks(1); // normal pending payment confirms at the new tip
        QCOMPARE(resets.count(), 0);
        QVERIFY(outgoing.isValid());
        QCOMPARE(m->data(outgoing, ActivityModel::StatusTextRole).toString(), QStringLiteral("1 of 10 confirmations"));
        w.fixtureSetStory(QStringLiteral("empty"));
        QCOMPARE(m->count(), 0);
        QVERIFY(!outgoing.isValid());
        w.fixtureSetStory(QStringLiteral("normal"));
        QCOMPARE(m->count(), 4);
        QCOMPARE(m->data(m->index(0), ActivityModel::RowIdRole).toString(), QStringLiteral("s1"));
    }
};

QTEST_MAIN(TstActivity)
#include "tst_activity.moc"
