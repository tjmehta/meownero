#include "amount.h"

#include <limits>

namespace amount {
namespace {

bool isAsciiDigit(QChar c) { return c >= QLatin1Char('0') && c <= QLatin1Char('9'); }

// Characters that people use to group digits or as the other decimal mark.
// Any of them makes the input ambiguous, so it is refused rather than stripped.
bool isRefusedSeparator(QChar c, QChar decimalPoint, QChar localeGroup)
{
    if (c == decimalPoint)
        return false;
    if (c.isSpace() || c == QLatin1Char(',') || c == QLatin1Char('.') || c == QLatin1Char('_')
        || c == QLatin1Char('\'') || c == QChar(0x2019) || c == QChar(0x00A0) || c == QChar(0x202F)
        || c == QChar(0x2009) || c == QChar(0x066B) || c == QChar(0x066C))
        return true;
    return c == localeGroup;
}

QString separatorMessage(QChar dp)
{
    if (dp == QLatin1Char('.'))
        return QStringLiteral("Use only digits and “.” for decimals, for example 1000.5. Commas, spaces "
                              "and other separators aren't accepted, so the amount can't be misread.");
    return QStringLiteral("Use only digits and “%1” for decimals, for example 1000%15. Points, spaces "
                          "and other separators aren't accepted, so the amount can't be misread.")
        .arg(dp);
}

QString shapeMessage(QChar dp)
{
    if (dp == QLatin1Char('.'))
        return QStringLiteral("Use digits and one decimal point, for example 2.5.");
    return QStringLiteral("Use digits and one decimal separator “%1”, for example 2%15.").arg(dp);
}

} // namespace

ParseResult parse(const QString &raw, const QLocale &locale)
{
    const QChar dp = locale.decimalPoint().isEmpty() ? QLatin1Char('.') : locale.decimalPoint().at(0);
    const QChar group = locale.groupSeparator().isEmpty() ? QChar() : locale.groupSeparator().at(0);
    const QString s = raw.trimmed();

    for (QChar c : s)
        if (isRefusedSeparator(c, dp, group))
            return {false, 0, separatorMessage(dp)};
    if (s.isEmpty())
        return {false, 0, QStringLiteral("Enter an amount.")};

    const qsizetype point = s.indexOf(dp);
    const QString intPart = point < 0 ? s : s.left(point);
    const QString fracPart = point < 0 ? QString() : s.mid(point + 1);
    bool shapeOk = (intPart.size() + fracPart.size()) > 0;
    for (QChar c : intPart)
        shapeOk = shapeOk && isAsciiDigit(c);
    for (QChar c : fracPart)
        shapeOk = shapeOk && isAsciiDigit(c);
    if (!shapeOk)
        return {false, 0, shapeMessage(dp)};

    if (fracPart.size() > kDecimals)
        return {false, 0,
                QStringLiteral("MEOW has 12 decimal places. This amount has %1. Remove the extra digits; "
                               "the wallet will not round it for you.")
                    .arg(fracPart.size())};

    // Exact integer arithmetic with overflow refusal (no wrap, no float).
    quint64 whole = 0;
    for (QChar c : intPart) {
        const quint64 d = quint64(c.unicode() - '0');
        if (whole > (std::numeric_limits<quint64>::max() - d) / 10)
            return {false, 0, QStringLiteral("That amount is larger than any balance this wallet can hold.")};
        whole = whole * 10 + d;
    }
    quint64 frac = 0;
    for (int i = 0; i < kDecimals; ++i)
        frac = frac * 10 + (i < fracPart.size() ? quint64(fracPart.at(i).unicode() - '0') : 0);
    if (whole > (std::numeric_limits<quint64>::max() - frac) / kAtomicPerCoin)
        return {false, 0, QStringLiteral("That amount is larger than any balance this wallet can hold.")};
    const quint64 atomic = whole * kAtomicPerCoin + frac;
    if (atomic == 0)
        return {false, 0, QStringLiteral("Enter an amount above zero.")};
    return {true, atomic, {}};
}

QString Formatted::textWithoutEllipsis() const
{
    return sign + integer + (fraction.isEmpty() ? QString() : QString(decimalPoint) + fraction);
}

QString Formatted::text() const
{
    return textWithoutEllipsis() + (moreDigits ? QStringLiteral("…") : QString());
}

Formatted format(quint64 magnitude, bool negative, bool exact, bool showSign, const QLocale &locale)
{
    Formatted f;
    f.decimalPoint = locale.decimalPoint().isEmpty() ? QLatin1Char('.') : locale.decimalPoint().at(0);
    QLocale grouping = locale;
    grouping.setNumberOptions(QLocale::DefaultNumberOptions);
    f.integer = grouping.toString(qulonglong(magnitude / kAtomicPerCoin));
    QString frac = QString::number(magnitude % kAtomicPerCoin).rightJustified(kDecimals, QLatin1Char('0'));
    while (frac.endsWith(QLatin1Char('0')))
        frac.chop(1); // trailing zeros carry no value; trimming them is lossless
    if (!exact && magnitude >= kCompactThreshold && frac.size() > 4) {
        f.moreDigits = true;
        frac.truncate(4);
    }
    f.fraction = frac;
    const bool neg = negative && magnitude != 0;
    f.sign = showSign ? (neg ? QStringLiteral("−") : QStringLiteral("+")) : (neg ? QStringLiteral("−") : QString());
    return f;
}

QString plain(quint64 atomic, QChar decimalPoint)
{
    QString frac = QString::number(atomic % kAtomicPerCoin).rightJustified(kDecimals, QLatin1Char('0'));
    while (frac.endsWith(QLatin1Char('0')))
        frac.chop(1);
    return QString::number(atomic / kAtomicPerCoin) + (frac.isEmpty() ? QString() : QString(decimalPoint) + frac);
}

} // namespace amount
