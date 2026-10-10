#pragma once

// Exact MEOW amounts. Every value is an integer count of atomic units
// (12 decimal places). Nothing here touches floating point.
//
// TJ's presentation rule (docs/milestones.md:95): display may simplify, but
// payment input is never rounded and a nonzero amount is never shown as zero.

#include <QChar>
#include <QLocale>
#include <QString>
#include <QtGlobal>

namespace amount {

inline constexpr int kDecimals = 12;
inline constexpr quint64 kAtomicPerCoin = 1'000'000'000'000ULL;
// Compact display hides digits only at or above 0.0001 MEOW.
inline constexpr quint64 kCompactThreshold = 100'000'000ULL;

struct ParseResult {
    bool ok = false;
    quint64 atomic = 0;
    QString message; // set when !ok
};

// Parses user input exactly. Accepts ASCII digits and the given decimal
// separator only. Grouping marks, spaces and the other decimal mark are
// refused, so "0,5" can never become 5. More than 12 decimals is refused,
// never rounded. Port of the prototype's parseAmount + PARSER_CASES.
ParseResult parse(const QString &raw, const QLocale &locale);

struct Formatted {
    QString sign;      // "", "+" or "−" (U+2212)
    QString integer;   // grouped with the locale's group separator
    QString fraction;  // without trailing zeros; empty for whole amounts
    bool moreDigits = false; // compact view hid nonzero digits: show "…"
    QChar decimalPoint = QLatin1Char('.');

    QString text() const; // sign + integer + fraction + "…"
    QString textWithoutEllipsis() const;
};

// exact: every nonzero digit. Compact: at most four decimals, truncated
// (never rounded), and only for amounts of at least 0.0001 MEOW.
Formatted format(quint64 magnitude, bool negative, bool exact, bool showSign,
                 const QLocale &locale);

// Digits and decimal point only, no grouping: what the Max action writes
// back into the amount field so parse() accepts it unchanged.
QString plain(quint64 atomic, QChar decimalPoint);

} // namespace amount
