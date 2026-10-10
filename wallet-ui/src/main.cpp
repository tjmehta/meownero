#include "simulatedbackend.h"
#include "walletcontroller.h"
#include "activitymodel.h"

#include <QCommandLineParser>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("Meownero Wallet"));
    QGuiApplication::setOrganizationName(QStringLiteral("Meownero"));
    QGuiApplication::setApplicationVersion(QStringLiteral("0.1.0-simulated"));
    QGuiApplication::setDesktopFileName(QStringLiteral("meownero-wallet"));

    QCommandLineParser cli;
    cli.setApplicationDescription(QStringLiteral("Meownero Wallet with a simulated backend. No wallet, node or network is connected."));
    cli.addHelpOption();
    QCommandLineOption start(QStringLiteral("start"), QStringLiteral("First screen: welcome, unlock or overview."), QStringLiteral("route"), QStringLiteral("welcome"));
    QCommandLineOption story(QStringLiteral("story"), QStringLiteral("Fixture wallet history: normal, empty, dust or large."), QStringLiteral("story"), QStringLiteral("normal"));
    QCommandLineOption fixtures(QStringLiteral("reviewer-fixtures"), QStringLiteral("Open the separate reviewer fixtures window."));
    cli.addOptions({start, story, fixtures});
    cli.process(app);

    // Standard Qt Quick Controls with the accepted styling: Basic is the
    // customisable style; colours and shapes come from Theme.qml.
    QQuickStyle::setStyle(QStringLiteral("Basic"));

    SimulatedBackend backend;
    WalletController wallet(&backend);
    const QString s = cli.value(story);
    wallet.startAt(cli.value(start), s == QStringLiteral("empty") ? ledger::Story::Empty
                                     : s == QStringLiteral("dust")  ? ledger::Story::Dust
                                     : s == QStringLiteral("large") ? ledger::Story::Large
                                                                    : ledger::Story::Normal);

    // Recovery words are hidden whenever the app leaves the foreground.
    QObject::connect(&app, &QGuiApplication::applicationStateChanged, &wallet, [&wallet](Qt::ApplicationState st) {
        if (st != Qt::ApplicationActive)
            wallet.hideRecoveryWords();
    });

    qmlRegisterUncreatableType<ActivityModel>("Meownero.Core", 1, 0, "ActivityModel", QStringLiteral("display model"));
    qmlRegisterSingletonInstance("Meownero.Core", 1, 0, "Wallet", &wallet);

    QQmlApplicationEngine engine;
    // Only bundled, compiled-in QML is loaded; no network access is configured.
    engine.setInitialProperties({{QStringLiteral("showFixtures"), cli.isSet(fixtures)}});
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app, [] { QCoreApplication::exit(1); },
                     Qt::QueuedConnection);
    engine.loadFromModule("Meownero", "Main");
    return app.exec();
}
