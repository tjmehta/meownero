#pragma once

// Display rows for Activity and Overview. Rows carry text only; amounts are
// already formatted by the controller's exact rules.

#include <QAbstractListModel>
#include "ledger.h"

class WalletController;

class ActivityModel : public QAbstractListModel
{
    Q_OBJECT
    Q_PROPERTY(int count READ count NOTIFY countChanged)
public:
    enum Role {
        RowIdRole = Qt::UserRole + 1,
        TitleRole,
        SubtitleRole,
        AmountTextRole,
        MoreDigitsRole,
        AmountAccessibleRole,
        StatusTextRole,
        StatusKindRole,
        IconRole,
    };

    ActivityModel(const WalletController *controller, int limit, QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;
    int count() const { return rowCount(); }

    void refresh(const QList<const ledger::Tx *> &sorted);

signals:
    void countChanged();

private:
    struct Row {
        QString id, title, subtitle, amountText, amountAccessible, statusText, statusKind, icon;
        bool moreDigits = false;
    };
    const WalletController *m_controller;
    int m_limit;
    QList<Row> m_rows;
};
