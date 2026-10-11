#!/usr/bin/env python3
"""Overlay the same local instrumentation on a disposable wallet-ui source copy."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
harness = pathlib.Path(__file__).resolve().parent
for name in ("historybenchmark.h",):
    (root / "tests" / name).write_bytes((harness / name).read_bytes())
(root / "src/bench_counters.h").write_text("#pragma once\n#include <QtGlobal>\ninline quint64 benchFindComparisons = 0, benchDetailCalls = 0, benchSortCalls = 0;\n")

def edit(path, before, after):
    p = root / path
    s = p.read_text()
    if before not in s:
        raise RuntimeError(f"Missing instrumentation anchor: {path}: {before}")
    p.write_text(s.replace(before, after))

edit("src/walletcontroller.h", "private:\n", "friend class HistoryBenchmark;\nprivate:\n")
edit("src/ledger.cpp", '#include "ledger.h"', '#include "ledger.h"\n#include "bench_counters.h"')
edit("src/ledger.cpp", "if (tx.id == id)", "if ((++benchFindComparisons, tx.id == id))")
edit("src/ledger.cpp", "QList<const Tx *> Ledger::sorted() const\n{", "QList<const Tx *> Ledger::sorted() const\n{\n    ++benchSortCalls;")
edit("src/walletcontroller.cpp", '#include "walletcontroller.h"', '#include "walletcontroller.h"\n#include "bench_counters.h"')
edit("src/walletcontroller.cpp", "QVariantMap WalletController::detail(const QString &rowId) const\n{", "QVariantMap WalletController::detail(const QString &rowId) const\n{\n    ++benchDetailCalls;")
edit("src/main.cpp", '#include "activitymodel.h"', '#include "activitymodel.h"\n#include "../tests/historybenchmark.h"')
edit("src/main.cpp", "cli.addOptions({start, story, fixtures});", 'QCommandLineOption benchmark("benchmark", "Synthetic history count", "count");\n    QCommandLineOption page("benchmark-page", "Benchmark page", "page", "overview");\n    cli.addOptions({start, story, fixtures, benchmark, page});')
edit("src/main.cpp", "qmlRegisterUncreatableType<ActivityModel>", 'HistoryBenchmark probe(&wallet);\n    if (!cli.isSet(benchmark)) return 2;\n    probe.fixture(cli.value(benchmark).toInt(), cli.value(page));\n    qmlRegisterSingletonInstance("Meownero.Core", 1, 0, "HistoryProbe", &probe);\n\n    qmlRegisterUncreatableType<ActivityModel>')
edit("src/main.cpp", "return app.exec();", 'if (engine.rootObjects().isEmpty()) return 1;\n    probe.attach(qobject_cast<QQuickWindow *>(engine.rootObjects().first()));\n    return app.exec();')
edit("qml/ActivityList.qml", "id: row", "id: row\n                Component.onCompleted: HistoryProbe.created()\n                Component.onDestruction: HistoryProbe.destroyed()")
edit("CMakeLists.txt", "qt_add_executable(meownero-wallet src/main.cpp)", "qt_add_executable(meownero-wallet src/main.cpp tests/historybenchmark.h)")
