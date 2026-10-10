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
            {IconRole, "icon"}};
}

void ActivityModel::refresh()
{
    const int before = int(m_rows.size());
    beginResetModel();
    m_rows.clear();
    const ledger::Ledger &l = m_controller->ledgerState();
    for (const ledger::Tx *tx : l.sorted()) {
        if (m_limit > 0 && m_rows.size() >= m_limit)
            break;
        const QVariantMap d = m_controller->detail(tx->id);
        const QVariantMap a = d.value(QStringLiteral("rowAmount")).toMap();
        Row r;
        r.id = tx->id;
        r.title = ledger::title(*tx);
        r.subtitle = d.value(QStringLiteral("subtitle")).toString();
        r.amountText = a.value(QStringLiteral("text")).toString();
        r.moreDigits = a.value(QStringLiteral("more")).toBool();
        r.amountAccessible = a.value(QStringLiteral("accessible")).toString();
        r.statusText = ledger::statusText(l, *tx);
        r.statusKind = ledger::statusKind(l, *tx);
        r.icon = tx->type == ledger::TxType::Mined ? QStringLiteral("block")
                 : tx->type == ledger::TxType::In  ? QStringLiteral("down")
                                                   : QStringLiteral("up");
        m_rows.append(r);
    }
    endResetModel();
    if (before != m_rows.size())
        emit countChanged();
}
