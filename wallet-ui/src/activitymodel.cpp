#include "activitymodel.h"

#include "walletcontroller.h"

ActivityModel::ActivityModel(const WalletController *controller, int limit, QObject *parent)
    : QAbstractListModel(parent), m_controller(controller), m_limit(limit)
{
}

int ActivityModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : int(m_rows.size());
}

QVariant ActivityModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_rows.size())
        return {};
    const Row &r = m_rows.at(index.row());
    switch (role) {
    case RowIdRole: return r.id;
    case TitleRole: return r.title;
    case SubtitleRole: return r.subtitle;
    case AmountTextRole: return r.amountText;
    case MoreDigitsRole: return r.moreDigits;
    case AmountAccessibleRole: return r.amountAccessible;
    case StatusTextRole: return r.statusText;
    case StatusKindRole: return r.statusKind;
    case IconRole: return r.icon;
    }
    return {};
}

QHash<int, QByteArray> ActivityModel::roleNames() const
{
    return {{RowIdRole, "rowId"},           {TitleRole, "title"},
            {SubtitleRole, "subtitle"},     {AmountTextRole, "amountText"},
            {MoreDigitsRole, "moreDigits"}, {AmountAccessibleRole, "amountAccessible"},
            {StatusTextRole, "statusText"}, {StatusKindRole, "statusKind"},
            {IconRole, "iconKey"}};
}

void ActivityModel::refresh(const QList<const ledger::Tx *> &sorted)
{
    const int before = int(m_rows.size());
    QList<Row> rows;
    rows.reserve(m_limit > 0 ? qMin(qsizetype(m_limit), sorted.size()) : sorted.size());
    const ledger::Ledger &l = m_controller->ledgerState();
    for (const ledger::Tx *tx : sorted) {
        if (m_limit > 0 && rows.size() >= m_limit)
            break;
        const QVariantMap a = m_controller->amountView(tx->amount, tx->type == ledger::TxType::Out,
                                                     m_controller->exactDigits(), true);
        Row r;
        r.id = tx->id;
        r.title = ledger::title(*tx);
        r.subtitle = m_controller->rowSubtitle(*tx);
        r.amountText = a.value(QStringLiteral("text")).toString();
        r.moreDigits = a.value(QStringLiteral("more")).toBool();
        r.amountAccessible = a.value(QStringLiteral("accessible")).toString();
        r.statusText = ledger::statusText(l, *tx);
        r.statusKind = ledger::statusKind(l, *tx);
        r.icon = tx->type == ledger::TxType::Mined ? QStringLiteral("block")
                 : tx->type == ledger::TxType::In  ? QStringLiteral("down")
                                                   : QStringLiteral("up");
        rows.append(r);
    }
    bool sameIds = rows.size() == m_rows.size();
    for (int i = 0; sameIds && i < rows.size(); ++i)
        sameIds = rows[i].id == m_rows[i].id;
    if (!sameIds) {
        beginResetModel();
        m_rows = std::move(rows);
        endResetModel();
    } else {
        // Keep row objects and persistent indexes alive for focus and dialogs.
        // Only changed roles are notified; unchanged refreshes do no QML work.
        for (int i = 0; i < rows.size(); ++i) {
            const Row &a = m_rows[i], &b = rows[i];
            QList<int> roles;
            if (a.title != b.title) roles.append(TitleRole);
            if (a.subtitle != b.subtitle) roles.append(SubtitleRole);
            if (a.amountText != b.amountText) roles.append(AmountTextRole);
            if (a.moreDigits != b.moreDigits) roles.append(MoreDigitsRole);
            if (a.amountAccessible != b.amountAccessible) roles.append(AmountAccessibleRole);
            if (a.statusText != b.statusText) roles.append(StatusTextRole);
            if (a.statusKind != b.statusKind) roles.append(StatusKindRole);
            if (a.icon != b.icon) roles.append(IconRole);
            m_rows[i] = std::move(rows[i]);
            if (!roles.isEmpty()) emit dataChanged(index(i), index(i), roles);
        }
    }
    if (before != m_rows.size())
        emit countChanged();
}
