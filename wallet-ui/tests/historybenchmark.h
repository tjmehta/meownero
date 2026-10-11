#pragma once

// This header is compiled only into the disposable, instrumented source copies
// prepared by prepare-history-benchmark.py. It is absent from normal builds.
#include "activitymodel.h"
#include "walletcontroller.h"
#include "bench_counters.h"
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQuickWindow>
#include <QTimer>
#include <cstdio>
#include <sys/resource.h>

class HistoryBenchmark : public QObject
{
    Q_OBJECT
public:
    explicit HistoryBenchmark(WalletController *wallet) : w(wallet) {}
    Q_INVOKABLE void created() { ++creates; ++live; }
    Q_INVOKABLE void destroyed() { ++destroys; --live; }

    void fixture(int count, const QString &page)
    {
        n = count;
        route = page;
        w->setLocale(QLocale(QLocale::English, QLocale::UnitedStates));
        w->startAt(QStringLiteral("overview"), ledger::Story::Normal);
        if (count != 4) {
            const auto original = w->m_ledger.txs;
            w->m_ledger.txs.clear();
            for (int i = 0; i < count; ++i) {
                auto tx = original[i % original.size()];
                tx.id = QStringLiteral("history-%1").arg(i);
                tx.txid = QStringLiteral("%1").arg(i + 1, 64, 16, QLatin1Char('0'));
                if (tx.height) tx.height = 1000 + i % 300;
                w->m_ledger.txs.append(tx);
            }
        }
        w->navigate(page);
        connect(w->activity(), &QAbstractItemModel::modelReset, this, [this] { ++resets; });
        connect(w->recentActivity(), &QAbstractItemModel::modelReset, this, [this] { ++resets; });
        connect(w->activity(), &QAbstractItemModel::dataChanged, this, [this] { ++changes; });
        connect(w->recentActivity(), &QAbstractItemModel::dataChanged, this, [this] { ++changes; });
        reset();
        operation = QStringLiteral("model");
        start();
        w->refreshModels();
        syncNs = timer.nsecsElapsed();
        syncCpu = cpu() - cpuStart;
        output(syncNs);
    }

    void attach(QQuickWindow *window)
    {
        win = window;
        connect(win, &QQuickWindow::frameSwapped, this, [this] {
            if (!measuring) return;
            measuring = false;
            const auto ns = timer.nsecsElapsed();
            QTimer::singleShot(0, this, [this, ns] {
                output(ns);
                if (operation == QStringLiteral("refresh"))
                    QTimer::singleShot(300, this, [this] { run(QStringLiteral("toggle")); });
                else QCoreApplication::quit();
            });
        }, Qt::DirectConnection);
        QTimer::singleShot(600, this, [this] { run(QStringLiteral("refresh")); });
    }
private:
    static qint64 cpu()
    {
        rusage r{}; getrusage(RUSAGE_SELF, &r);
        return (r.ru_utime.tv_sec + r.ru_stime.tv_sec) * 1000000LL
            + r.ru_utime.tv_usec + r.ru_stime.tv_usec;
    }
    void reset()
    {
        creates = destroys = resets = changes = 0;
        benchFindComparisons = benchDetailCalls = benchSortCalls = 0;
    }
    void start() { cpuStart = cpu(); timer.start(); }
    void run(const QString &op)
    {
        reset(); operation = op; start();
        if (op == QStringLiteral("toggle")) w->toggleExact();
        else { w->refreshModels(); emit w->changed(); }
        syncNs = timer.nsecsElapsed(); syncCpu = cpu() - cpuStart;
        measuring = true;
        win->update();
    }
    void output(qint64 frameNs)
    {
        rusage r{}; getrusage(RUSAGE_SELF, &r);
        QJsonObject o{{"n", n}, {"page", route}, {"operation", operation},
            {"sync_ms", syncNs / 1e6}, {"frame_ms", frameNs / 1e6},
            {"sync_cpu_ms", syncCpu / 1e3}, {"frame_cpu_ms", (cpu() - cpuStart) / 1e3},
            {"peak_rss_kib", double(r.ru_maxrss)}, {"model_resets", resets},
            {"data_changes", changes}, {"delegate_creates", creates},
            {"delegate_destroys", destroys}, {"live_delegates", live},
            {"find_comparisons", double(benchFindComparisons)},
            {"detail_calls", double(benchDetailCalls)}, {"sort_calls", double(benchSortCalls)}};
        puts(QJsonDocument(o).toJson(QJsonDocument::Compact).constData()); fflush(stdout);
    }
    WalletController *w;
    QQuickWindow *win = nullptr;
    int n = 0, creates = 0, destroys = 0, live = 0, resets = 0, changes = 0;
    QString route, operation;
    bool measuring = false;
    QElapsedTimer timer;
    qint64 syncNs = 0, cpuStart = 0, syncCpu = 0;
};
