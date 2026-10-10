#include "amount.h"

#include <QTest>

// PARSER_CASES from docs/design/gui-wallet/prototype.html (accepted revision 5),
// ported verbatim for the en-US decimal point. -1 means refused with a message.
class TstAmount : public QObject
{
    Q_OBJECT
    const QLocale us{QLocale::English, QLocale::UnitedStates};
    const QLocale de{QLocale::German, QLocale::Germany};

private slots:
    void parserCases_data()
    {
        QTest::addColumn<QString>("input");
        QTest::addColumn<qint64>("want");
        const struct { const char *in; qint64 want; } cases[] = {
            {"2.5", 2500000000000}, {".5", 500000000000}, {"5.", 5000000000000}, {"0.000000000001", 1},
            {"3153600.123456789012", 3153600123456789012},
            {"0.0000000000015", -1}, {"1.0000000000000", -1}, {"0,5", -1}, {"2,5", -1}, {"1.000,5", -1},
            {"1,000", -1}, {"1 000", -1}, {"1_0", -1}, {"1e3", -1}, {"-1", -1}, {"2.5.1", -1}, {"0", -1}, {"", -1},
        };
        for (const auto &c : cases)
            QTest::newRow(c.in[0] ? c.in : "<empty>") << QString::fromUtf8(c.in) << c.want;
    }
    void parserCases()
    {
        QFETCH(QString, input);
        QFETCH(qint64, want);
        const amount::ParseResult r = amount::parse(input, us);
        if (want < 0) {
            QVERIFY2(!r.ok, qPrintable(input));
            QVERIFY(!r.message.isEmpty());
        } else {
            QVERIFY2(r.ok, qPrintable(r.message));
            QCOMPARE(r.atomic, quint64(want));
        }
    }

    void refusalMessages()
    {
        QVERIFY(amount::parse(QStringLiteral("0.0000000000015"), us).message.contains(QStringLiteral("This amount has 13")));
        QVERIFY(amount::parse(QStringLiteral("0,5"), us).message.startsWith(QStringLiteral("Use only digits and “.”")));
        QCOMPARE(amount::parse(QStringLiteral("0"), us).message, QStringLiteral("Enter an amount above zero."));
        QCOMPARE(amount::parse(QStringLiteral("   "), us).message, QStringLiteral("Enter an amount."));
    }

    void otherSpaceAndGroupingCharactersRefused()
    {
        for (QChar c : {QChar(0x00A0), QChar(0x202F), QChar(0x2009), QChar(0x2019), QChar(u'\''), QChar(u'\t')})
            QVERIFY(!amount::parse(QStringLiteral("1") + c + QStringLiteral("000"), us).ok);
        // Non-ASCII digits are not digits here.
        QVERIFY(!amount::parse(QString::fromUtf8("١٢"), us).ok);
    }

    void localeDecimalComma()
    {
        // The system locale's decimal separator is accepted; the other mark is refused.
        auto r = amount::parse(QStringLiteral("0,5"), de);
        QVERIFY(r.ok);
        QCOMPARE(r.atomic, quint64(500000000000));
        QVERIFY(!amount::parse(QStringLiteral("0.5"), de).ok);
        QVERIFY(!amount::parse(QStringLiteral("1.000,5"), de).ok);
        QVERIFY(!amount::parse(QStringLiteral("1 000,5"), de).ok);
        QCOMPARE(amount::parse(QStringLiteral("0,0000000000001"), de).ok, false);
        QCOMPARE(amount::parse(QStringLiteral("3153600,123456789012"), de).atomic, quint64(3153600123456789012ULL));
    }

    void overflowRefusedNotWrapped()
    {
        QVERIFY(!amount::parse(QStringLiteral("18446744073709551616"), us).ok);
        QVERIFY(!amount::parse(QStringLiteral("18446744.073709551616"), us).ok);
        auto max = amount::parse(QStringLiteral("18446744.073709551615"), us);
        QVERIFY(max.ok);
        QCOMPARE(max.atomic, std::numeric_limits<quint64>::max());
    }

    void formatNeverShowsNonzeroAsZero()
    {
        QCOMPARE(amount::format(1, false, false, false, us).text(), QStringLiteral("0.000000000001"));
        QCOMPARE(amount::format(99'999'999, false, false, false, us).text(), QStringLiteral("0.000099999999"));
        QCOMPARE(amount::format(0, false, false, false, us).text(), QStringLiteral("0"));
    }

    void formatCompactTruncatesWithEllipsis()
    {
        const quint64 big = 3153600123456789012ULL;
        auto f = amount::format(big, false, false, false, us);
        QCOMPARE(f.text(), QStringLiteral("3,153,600.1234…"));
        QVERIFY(f.moreDigits);
        QCOMPARE(amount::format(big, false, true, false, us).text(), QStringLiteral("3,153,600.123456789012"));
        // Truncated, not rounded: .99999 stays .9999…
        QCOMPARE(amount::format(1'999'990'000'000ULL, false, false, false, us).text(), QStringLiteral("1.9999…"));
        // Exactly four decimals: nothing hidden.
        QCOMPARE(amount::format(2'500'000'000'000ULL, false, false, false, us).text(), QStringLiteral("2.5"));
    }

    void formatSignsAndLocale()
    {
        QCOMPARE(amount::format(2'500'000'000'000ULL, true, true, true, us).text(), QStringLiteral("−2.5"));
        QCOMPARE(amount::format(1, false, true, true, us).text(), QStringLiteral("+0.000000000001"));
        QCOMPARE(amount::format(1'234'500'000'000'000ULL, false, true, false, de).text(), QStringLiteral("1.234,5"));
    }

    void plainRoundTrips()
    {
        for (quint64 v : {quint64(1), quint64(2'500'000'000'000ULL), quint64(3153600123456789012ULL)}) {
            QCOMPARE(amount::parse(amount::plain(v, QLatin1Char('.')), us).atomic, v);
            QCOMPARE(amount::parse(amount::plain(v, QLatin1Char(',')), de).atomic, v);
        }
    }
};

QTEST_GUILESS_MAIN(TstAmount)
#include "tst_amount.moc"
