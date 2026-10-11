#include "walletcontroller.h"

#include "activitymodel.h"
#include "amount.h"

#include <QAccessibilityHints>
#include <QClipboard>
#include <QCryptographicHash>
#include <QDateTime>
#include <QGuiApplication>
#include <QRegularExpression>
#include <QStyleHints>
#include <QSysInfo>

using ledger::Tx;
using ledger::TxStatus;
using ledger::TxType;

namespace {

// Prototype fixtures: random strings that cannot pass an address checksum.
struct NetAddresses { const char *self, *b, *c; };
constexpr NetAddresses kRegtest{
    "4AKvVKKRpe4mjeLmYeXnU9cRrRZUjLfDhSVtuQfQHpFYrqP5iU1qr1Vtqbok9AiXZUjg1J9A5mZvmF1tJ23XPi4ztMgYjFd",
    "48oicAQMJAXY7wNJ9dYYiBLJkTJKaRFfqJFHFUcmWMgmjQr5sBRJQAdA2biBSFRipb6Kw6KMA7oKhVqQphBgRXM2phFLM9q",
    "47ugjvRPLkivpYA4zNXnTqsaGmvJJVxJ1f6kKP6URWgb4FN5dRr3xvr7m92dX9QDScsCpBHjutJHs3uQzvBgdJ6BVDQaMye"};
constexpr NetAddresses kTestnet{
    "T6hgrwLVHjyRjAL4adoGeJCJPuYhjZa88mucsPBGxyNuKDz6gpCEiZyEMjbf5nDc9ZxRQ28DwsnvoaTR3iwh9zNmNgn8dMy",
    "T6SVHS1pGKv8qeXfx2SEXYZvefFRwcaRLHBVHUevMRF9imt5ysHSmySD4booyZDaZmUC3DVmUPa9sgjt8gT63oT4LJe3yt8",
    "T6t18dykQuQqNpfYaVkXxtbogKztJNFVoJrMMNXBUwU4L3jX9f1gS4gxPfWSruD4XyB85sjCdLxEcjHearTC1PYPBXV7YGV"};
constexpr const char *kMainnet =
    "M5eJESRaFp7bC6q3PaoiE6XeSdVX4QZzrqENaK5RLBSmwa65RyPcvEz7UgQL3hZy9tgCLCUNT2jqneExhgC9WYWCdP6Z1KS";
constexpr int kChainTip = 1340;

// Sample words for layout only. "tabby" is not one of the first 24, so the
// check word can never match: this list cannot be a valid recovery phrase.
const QStringList &sampleWords()
{
    static const QStringList w = {
        QStringLiteral("whisker"), QStringLiteral("saucer"),   QStringLiteral("velvet"),
        QStringLiteral("lantern"), QStringLiteral("pebble"),   QStringLiteral("orchard"),
        QStringLiteral("mitten"),  QStringLiteral("harbor"),   QStringLiteral("laboratory"),
        QStringLiteral("tundra"),  QStringLiteral("ember"),    QStringLiteral("quilt"),
        QStringLiteral("marble"),  QStringLiteral("fennel"),   QStringLiteral("cobalt"),
        QStringLiteral("sparrow"), QStringLiteral("thistle"),  QStringLiteral("juniper"),
        QStringLiteral("wicker"),  QStringLiteral("verification"), QStringLiteral("copper"),
        QStringLiteral("meadow"),  QStringLiteral("ripple"),   QStringLiteral("sable"),
        QStringLiteral("tabby")};
    return w;
}

bool isKnownWord(const QString &w)
{
    static const QStringList extra = {
        QStringLiteral("acorn"),  QStringLiteral("biscuit"), QStringLiteral("canyon"), QStringLiteral("dapple"),
        QStringLiteral("falcon"), QStringLiteral("gravel"),  QStringLiteral("hollow"), QStringLiteral("island"),
        QStringLiteral("kettle"), QStringLiteral("lilac"),   QStringLiteral("mosaic"), QStringLiteral("nectar"),
        QStringLiteral("oyster"), QStringLiteral("parcel"),  QStringLiteral("quarry"), QStringLiteral("raven"),
        QStringLiteral("saddle"), QStringLiteral("timber"),  QStringLiteral("umber"),  QStringLiteral("violet"),
        QStringLiteral("walnut"), QStringLiteral("yonder"),  QStringLiteral("zephyr")};
    return sampleWords().contains(w) || extra.contains(w);
}

constexpr int kQuiz[] = {4, 13, 22}; // 1-based positions
const QString kVeiled = QStringLiteral("•••••");

QByteArray digestOf(const QString &password)
{
    // The simulated wallet keeps a digest, never the password itself.
    return QCryptographicHash::hash(QByteArrayLiteral("meownero-simulated:") + password.toUtf8(),
                                    QCryptographicHash::Sha256);
}

const QStringList kOnboardingRoutes = {
    QStringLiteral("welcome"),   QStringLiteral("create-1"),  QStringLiteral("create-2"),
    QStringLiteral("create-3"),  QStringLiteral("create-4"),  QStringLiteral("restore-1"),
    QStringLiteral("restore-2"), QStringLiteral("restore-3"), QStringLiteral("unlock")};
const QStringList kShellRoutes = {QStringLiteral("overview"), QStringLiteral("activity"),
                                  QStringLiteral("send"),     QStringLiteral("receive"),
                                  QStringLiteral("node"),     QStringLiteral("wallet")};
const QStringList kNodeStates = {
    QStringLiteral("synced"),  QStringLiteral("remote"),    QStringLiteral("connecting"),
    QStringLiteral("node-sync"), QStringLiteral("scanning"), QStringLiteral("offline"),
    QStringLiteral("wrong-net"), QStringLiteral("engine-down"), QStringLiteral("auth-failed"),
    QStringLiteral("node-old")};

QString shortAddress(const QString &a) { return a.left(6) + QStringLiteral("…") + a.right(6); }

} // namespace

WalletController::WalletController(SimulatedBackend *backend, QObject *parent)
    : QObject(parent), m_backend(backend), m_activity(new ActivityModel(this, 0, this)),
      m_recent(new ActivityModel(this, 4, this)), m_locale(QLocale::system())
{
    m_ledger = ledger::story(ledger::Story::Empty);
    m_ledger.txs.clear();
    m_restoreWords = QStringList(25, QString());
    connect(m_backend, &SimulatedBackend::transferPrepared, this, &WalletController::onPrepared);
    connect(m_backend, &SimulatedBackend::relayFinished, this, &WalletController::onRelayFinished);
    connect(m_backend, &SimulatedBackend::submissionChecked, this, &WalletController::onChecked);
    connect(m_backend, &SimulatedBackend::blocksGenerated, this, &WalletController::onBlocks);
    connect(m_backend, &SimulatedBackend::reconnected, this, &WalletController::onReconnected);
    connect(m_backend, &SimulatedBackend::scanProgress, this, &WalletController::onScan);
    if (auto *hints = QGuiApplication::styleHints() ? QGuiApplication::styleHints()->accessibility() : nullptr)
        connect(hints, &QAccessibilityHints::motionPreferenceChanged, this, &WalletController::reducedMotionChanged);
}

WalletController::~WalletController() = default;

void WalletController::startAt(const QString &route, ledger::Story story)
{
    if (kShellRoutes.contains(route) || route == QStringLiteral("unlock")) {
        loadWallet(story, QStringLiteral("Test wallet"));
        m_passwordDigest = digestOf(QStringLiteral("simulated"));
        m_fixtureWallet = true;
        m_locked = route == QStringLiteral("unlock");
        m_route = route;
    } else {
        m_route = kOnboardingRoutes.contains(route) ? route : QStringLiteral("welcome");
    }
    emit changed();
}

bool WalletController::onboarding() const { return kOnboardingRoutes.contains(m_route); }

bool WalletController::reducedMotion() const
{
    const auto *hints = QGuiApplication::styleHints() ? QGuiApplication::styleHints()->accessibility() : nullptr;
    return hints && hints->motionPreference() == Qt::MotionPreference::ReducedMotion;
}

// ---------------------------------------------------------------- network

QString WalletController::networkName() const
{
    return m_testnet ? QStringLiteral("Meownero testnet") : QStringLiteral("Local regtest");
}
QString WalletController::networkTitle() const
{
    return m_testnet ? QStringLiteral("Meownero testnet (preview)") : QStringLiteral("Local regtest");
}
QString WalletController::networkSay() const
{
    return m_testnet ? QStringLiteral("Design preview of a future shared test network. It is not live, and its "
                                      "values are placeholders.")
                     : QStringLiteral("An isolated, accelerated FCMP++/CARROT test chain. Coins have no value.");
}
QString WalletController::networkProse() const
{
    return m_testnet ? QStringLiteral("Meownero testnet") : QStringLiteral("local regtest");
}

QString WalletController::addressFor(const QString &key) const
{
    const NetAddresses &n = m_testnet ? kTestnet : kRegtest;
    if (key == QStringLiteral("self"))
        return QString::fromLatin1(n.self);
    if (key == QStringLiteral("b"))
        return QString::fromLatin1(n.b);
    if (key == QStringLiteral("c"))
        return QString::fromLatin1(n.c);
    return key;
}

QString WalletController::kitLabelFor(const QString &key) const
{
    if (key == QStringLiteral("b"))
        return QStringLiteral("Test wallet B");
    if (key == QStringLiteral("c"))
        return QStringLiteral("Test wallet C");
    return {};
}

QString WalletController::receiveAddress() const { return addressFor(QStringLiteral("self")); }

QVariantList WalletController::kitWallets() const
{
    QVariantList out;
    for (const QString &k : {QStringLiteral("b"), QStringLiteral("c")}) {
        const QString a = addressFor(k);
        out.append(QVariantMap{{QStringLiteral("key"), k},
                               {QStringLiteral("label"), kitLabelFor(k)},
                               {QStringLiteral("short"), shortAddress(a)},
                               {QStringLiteral("selected"), m_sendTo.trimmed() == a}});
    }
    return out;
}

// ---------------------------------------------------------------- node

bool WalletController::canTransact() const
{
    return m_nodeState == QStringLiteral("synced") || m_nodeState == QStringLiteral("remote");
}

QString WalletController::pausedUntil() const
{
    return (m_nodeState == QStringLiteral("engine-down") || m_nodeState == QStringLiteral("auth-failed"))
               ? QStringLiteral("the wallet engine is running again")
               : QStringLiteral("your node is connected and synced");
}

QString WalletController::pausedNeeds() const
{
    return (m_nodeState == QStringLiteral("engine-down") || m_nodeState == QStringLiteral("auth-failed"))
               ? QStringLiteral("the wallet engine running")
               : QStringLiteral("your node connected and synced");
}

QVariantMap WalletController::node() const
{
    const QString s = m_nodeState;
    const bool remote = s == QStringLiteral("remote");
    const bool unloaded = s == QStringLiteral("offline") || s == QStringLiteral("wrong-net") || s == QStringLiteral("node-old");
    const QString nodeAddr = m_testnet ? QStringLiteral("127.0.0.1:29081") : QStringLiteral("127.0.0.1:18081");
    const QString tip = m_locale.toString(m_ledger.tip);

    QString chipTitle, chipSub, chipKind = QStringLiteral("bad");
    if (s == QStringLiteral("synced")) { chipTitle = QStringLiteral("Synced"); chipSub = QStringLiteral("Block %1").arg(tip); chipKind = QStringLiteral("ok"); }
    else if (remote) { chipTitle = QStringLiteral("Synced"); chipSub = QStringLiteral("Using someone else's node"); chipKind = QStringLiteral("warn"); }
    else if (s == QStringLiteral("connecting")) { chipTitle = QStringLiteral("Connecting…"); chipSub = nodeAddr; chipKind = QStringLiteral("spin"); }
    else if (s == QStringLiteral("node-sync")) { chipTitle = QStringLiteral("Node catching up"); chipSub = QStringLiteral("%1% of blocks").arg(m_nodePct); chipKind = QStringLiteral("spin"); }
    else if (s == QStringLiteral("scanning")) { chipTitle = QStringLiteral("Scanning for payments"); chipSub = QStringLiteral("%1% scanned").arg(m_scanPct); chipKind = QStringLiteral("spin"); }
    else if (s == QStringLiteral("offline")) { chipTitle = QStringLiteral("Node unreachable"); chipSub = QStringLiteral("Sending paused"); }
    else if (s == QStringLiteral("wrong-net")) { chipTitle = QStringLiteral("Wrong network"); chipSub = QStringLiteral("Nothing loaded from this node"); }
    else if (s == QStringLiteral("engine-down")) { chipTitle = QStringLiteral("Wallet engine stopped"); chipSub = QStringLiteral("Sending paused"); }
    else if (s == QStringLiteral("auth-failed")) { chipTitle = QStringLiteral("Engine refused this app"); chipSub = QStringLiteral("Sending paused"); }
    else { chipTitle = QStringLiteral("Incompatible node"); chipSub = QStringLiteral("Nothing loaded from this node"); }

    static const QMap<QString, QString> status = {
        {QStringLiteral("synced"), QStringLiteral("Connected and synced")},
        {QStringLiteral("remote"), QStringLiteral("Connected and synced")},
        {QStringLiteral("connecting"), QStringLiteral("Connecting…")},
        {QStringLiteral("node-sync"), QStringLiteral("Node catching up")},
        {QStringLiteral("scanning"), QStringLiteral("Scanning for payments")},
        {QStringLiteral("offline"), QStringLiteral("Can't reach this node")},
        {QStringLiteral("wrong-net"), QStringLiteral("Wrong network")},
        {QStringLiteral("engine-down"), QStringLiteral("Wallet engine stopped")},
        {QStringLiteral("auth-failed"), QStringLiteral("Wallet engine refused this app's credentials")},
        {QStringLiteral("node-old"), QStringLiteral("Incompatible node version")}};

    QString height = unloaded ? QStringLiteral("—")
                     : s == QStringLiteral("node-sync")
                         ? QStringLiteral("%1 of %2").arg(m_locale.toString(m_ledger.tip * m_nodePct / 100), tip)
                         : tip;
    QString scanned = s == QStringLiteral("scanning") ? m_locale.toString(m_ledger.tip * m_scanPct / 100)
                      : (s == QStringLiteral("synced") || remote) ? tip
                      : (s == QStringLiteral("engine-down") || s == QStringLiteral("auth-failed"))
                          ? QStringLiteral("Waiting for the wallet engine")
                          : QStringLiteral("Waiting for node");
    return {
        {QStringLiteral("status"), status.value(s)},
        {QStringLiteral("address"), remote ? QStringLiteral("node.example-test.org:29081") : nodeAddr},
        {QStringLiteral("addressNote"), remote ? QStringLiteral("someone else's node")
                                               : (m_testnet ? QStringLiteral("Your Meownero testnet node")
                                                            : QStringLiteral("Your node in the Meownero test kit (Docker)"))},
        {QStringLiteral("networkWrong"), s == QStringLiteral("wrong-net")},
        {QStringLiteral("networkText"), s == QStringLiteral("wrong-net")
                                            ? QStringLiteral("%1 · this wallet needs the %2")
                                                  .arg(m_testnet ? QStringLiteral("Local regtest") : QStringLiteral("Meownero testnet"), networkProse())
                                            : networkTitle()},
        {QStringLiteral("height"), height},
        {QStringLiteral("scanned"), scanned},
        {QStringLiteral("peers"), unloaded ? QStringLiteral("—") : (m_testnet ? QStringLiteral("8") : QStringLiteral("1"))},
        {QStringLiteral("peersNote"), (!unloaded && !m_testnet) ? QStringLiteral("a local regtest may have none") : QString()},
        {QStringLiteral("trust"), remote ? QStringLiteral("Untrusted, by your choice")
                                         : QStringLiteral("Trusted, because you chose your own node")},
        {QStringLiteral("remote"), remote},
        {QStringLiteral("remoteAllowed"), m_testnet},
        {QStringLiteral("ownNodeNote"), m_testnet ? QStringLiteral("Recommended: your wallet's requests stay on this computer. Payments you send are still relayed to the network.")
                                                  : QStringLiteral("The Meownero test kit's node at %1").arg(nodeAddr)},
        {QStringLiteral("chipTitle"), chipTitle},
        {QStringLiteral("chipSub"), chipSub},
        {QStringLiteral("chipKind"), chipKind},
        {QStringLiteral("chipAccessible"), chipAccessible()},
        {QStringLiteral("pausedUntil"), pausedUntil()},
        {QStringLiteral("pausedNeeds"), pausedNeeds()},
    };
}

QString WalletController::chipAccessible() const
{
    // Rebuilt from node() pieces without recursion.
    const QString s = m_nodeState;
    QString t, sub;
    if (s == QStringLiteral("synced")) { t = QStringLiteral("Synced"); sub = QStringLiteral("Block %1").arg(m_locale.toString(m_ledger.tip)); }
    else if (s == QStringLiteral("remote")) { t = QStringLiteral("Synced"); sub = QStringLiteral("Using someone else's node"); }
    else if (s == QStringLiteral("connecting")) { t = QStringLiteral("Connecting"); sub = m_testnet ? QStringLiteral("127.0.0.1:29081") : QStringLiteral("127.0.0.1:18081"); }
    else if (s == QStringLiteral("node-sync")) { t = QStringLiteral("Node catching up"); sub = QStringLiteral("%1% of blocks").arg(m_nodePct); }
    else if (s == QStringLiteral("scanning")) { t = QStringLiteral("Scanning for payments"); sub = QStringLiteral("%1% scanned").arg(m_scanPct); }
    else if (s == QStringLiteral("offline")) { t = QStringLiteral("Node unreachable"); sub = QStringLiteral("Sending paused"); }
    else if (s == QStringLiteral("wrong-net")) { t = QStringLiteral("Wrong network"); sub = QStringLiteral("Nothing loaded from this node"); }
    else if (s == QStringLiteral("engine-down")) { t = QStringLiteral("Wallet engine stopped"); sub = QStringLiteral("Sending paused"); }
    else if (s == QStringLiteral("auth-failed")) { t = QStringLiteral("Engine refused this app"); sub = QStringLiteral("Sending paused"); }
    else { t = QStringLiteral("Incompatible node"); sub = QStringLiteral("Nothing loaded from this node"); }
    return QStringLiteral("Connection: %1. %2").arg(t, sub);
}

QVariantMap WalletController::condition() const
{
    const QString s = m_nodeState;
    const QString nodeAddr = m_testnet ? QStringLiteral("127.0.0.1:29081") : QStringLiteral("127.0.0.1:18081");
    auto banner = [](const QString &tone, const QString &title, const QString &body, const QString &action = {},
                     const QString &actionLabel = {}, const QString &second = {}, const QString &secondLabel = {},
                     int progress = -1) {
        return QVariantMap{{QStringLiteral("visible"), true},        {QStringLiteral("tone"), tone},
                           {QStringLiteral("title"), title},         {QStringLiteral("body"), body},
                           {QStringLiteral("action"), action},       {QStringLiteral("actionLabel"), actionLabel},
                           {QStringLiteral("secondary"), second},    {QStringLiteral("secondaryLabel"), secondLabel},
                           {QStringLiteral("progress"), progress}};
    };
    if (s == QStringLiteral("connecting"))
        return banner(QStringLiteral("info"), QStringLiteral("Connecting to your node at %1…").arg(nodeAddr),
                      QStringLiteral("Balances below are from the last time this wallet was open."));
    if (s == QStringLiteral("node-sync"))
        return banner(QStringLiteral("net"), QStringLiteral("Your node is catching up with the network."),
                      QStringLiteral("Recent payments may be missing until it finishes (%1%). Sending waits until then.").arg(m_nodePct),
                      {}, {}, {}, {}, m_nodePct);
    if (s == QStringLiteral("scanning"))
        return banner(QStringLiteral("net"), QStringLiteral("Scanning blocks for your payments."),
                      QStringLiteral("Block %1 of %2. Balances may still go up.")
                          .arg(m_locale.toString(m_ledger.tip * m_scanPct / 100), m_locale.toString(m_ledger.tip)),
                      {}, {}, {}, {}, m_scanPct);
    if (s == QStringLiteral("offline"))
        return banner(QStringLiteral("bad"), QStringLiteral("Can't reach your node at %1.").arg(nodeAddr),
                      QStringLiteral("Showing balances from when the wallet last synced. Sending is paused until the node is back. "
                                     "If you use the Meownero test kit, check that it is running."),
                      QStringLiteral("retry"), QStringLiteral("Try again"), QStringLiteral("node"), QStringLiteral("Node settings"));
    if (s == QStringLiteral("wrong-net"))
        return banner(QStringLiteral("bad"), QStringLiteral("That node is on a different network."),
                      QStringLiteral("It reports the %1, but this wallet belongs to the %2. Nothing was loaded from it. "
                                     "Connect to a %3 node or open a different wallet.")
                          .arg(m_testnet ? QStringLiteral("local regtest") : QStringLiteral("Meownero testnet"), networkProse(),
                               networkKey()),
                      QStringLiteral("node"), QStringLiteral("Choose another node"));
    if (s == QStringLiteral("engine-down"))
        return banner(QStringLiteral("bad"), QStringLiteral("The wallet engine stopped."),
                      QStringLiteral("Your wallet file and recovery words are safe. Balances are from the last sync, and "
                                     "sending is paused until the engine is running again."),
                      QStringLiteral("retry"), QStringLiteral("Restart wallet engine"));
    if (s == QStringLiteral("auth-failed"))
        return banner(QStringLiteral("bad"), QStringLiteral("The wallet engine didn't accept this app's credentials."),
                      QStringLiteral("Nothing was sent or changed. Restarting the engine lets the app create fresh private credentials."),
                      QStringLiteral("retry"), QStringLiteral("Restart wallet engine"));
    if (s == QStringLiteral("node-old"))
        return banner(QStringLiteral("bad"), QStringLiteral("This node runs an incompatible version."),
                      QStringLiteral("It may follow different rules, so nothing was loaded from it. Update the Meownero test "
                                     "kit, or connect to another node."),
                      QStringLiteral("node"), QStringLiteral("Node settings"));
    return {{QStringLiteral("visible"), false}};
}

QVariantMap WalletController::reorg() const
{
    if (!m_reorg)
        return {{QStringLiteral("visible"), false}};
    const auto [height, count] = *m_reorg;
    return {{QStringLiteral("visible"), true},
            {QStringLiteral("title"), QStringLiteral("The chain reorganized at block %1.").arg(m_locale.toString(height))},
            {QStringLiteral("body"), QStringLiteral("%1 payment%2 went back to pending, and your balance was updated. This "
                                                    "can happen on any proof-of-work chain; nothing needs to be done unless "
                                                    "a payment stays pending.")
                                         .arg(count)
                                         .arg(count == 1 ? QString() : QStringLiteral("s"))}};
}

QString WalletController::remoteExposure()
{
    // Approved wording (TJS-1994 #11), shown in full before connecting and while connected.
    return QStringLiteral("An untrusted node can observe your connection and request activity and link submitted "
                          "transactions to that connection. Untrusted mode does not hide this metadata.");
}

// ---------------------------------------------------------------- amounts

QVariantMap WalletController::amountView(quint64 magnitude, bool negative, bool exact, bool sign) const
{
    const amount::Formatted f = amount::format(magnitude, negative, exact, sign, m_locale);
    const amount::Formatted full = amount::format(magnitude, negative, true, sign, m_locale);
    return {{QStringLiteral("text"), f.textWithoutEllipsis()},
            {QStringLiteral("more"), f.moreDigits},
            {QStringLiteral("exact"), full.text()},
            {QStringLiteral("accessible"), full.text() + QStringLiteral(" MEOW")}};
}

QString WalletController::amountText(quint64 magnitude, bool exact) const
{
    return amount::format(magnitude, false, exact, false, m_locale).text() + QStringLiteral(" MEOW");
}

QVariantMap WalletController::balance() const
{
    const ledger::Balances b = m_ledger.balances();
    const bool stale = !canTransact() && m_nodeState != QStringLiteral("scanning") && m_nodeState != QStringLiteral("node-sync");
    QString lastSynced;
    if (stale && m_lastSyncedMs > 0) {
        const qint64 mins = (QDateTime::currentMSecsSinceEpoch() - m_lastSyncedMs) / 60000;
        lastSynced = mins < 1 ? QStringLiteral("Last synced less than a minute ago")
                              : QStringLiteral("Last synced %1 minute%2 ago").arg(mins).arg(mins == 1 ? QString() : QStringLiteral("s"));
    }
    const QString next = b.nextUnlock ? QStringLiteral("%1 block%2").arg(*b.nextUnlock).arg(*b.nextUnlock == 1 ? QString() : QStringLiteral("s")) : QString();
    QString nothingSpendable;
    if (b.unlocked <= ledger::kFee) {
        if (b.unlocked > 0)
            nothingSpendable = QStringLiteral("Your spendable balance is smaller than a network fee, so it can't be sent yet.");
        else if (b.locked > 0)
            nothingSpendable = QStringLiteral("Nothing is spendable yet. %1 is still unlocking%2.")
                                   .arg(amountText(b.locked), next.isEmpty() ? QString() : QStringLiteral("; more is ready in ") + next);
        else
            nothingSpendable = QStringLiteral("This wallet has no test coins to send yet.");
    }
    return {
        {QStringLiteral("spendable"), amountView(b.unlocked, false, m_exact, false)},
        {QStringLiteral("unlocking"), amountView(b.locked, false, m_exact, false)},
        {QStringLiteral("total"), amountView(b.total, false, m_exact, false)},
        {QStringLiteral("spendableExact"), amountText(b.unlocked)},
        {QStringLiteral("hasLocked"), b.locked > 0},
        {QStringLiteral("nextUnlock"), next},
        {QStringLiteral("belowFee"), b.unlocked > 0 && b.unlocked <= ledger::kFee},
        {QStringLiteral("canSend"), b.unlocked > ledger::kFee},
        {QStringLiteral("nothingSpendable"), nothingSpendable},
        {QStringLiteral("lastSynced"), lastSynced},
        {QStringLiteral("accessibleName"),
         QStringLiteral("Spendable now: %1 MEOW, test coins. Show every digit")
             .arg(amount::format(b.unlocked, false, true, false, m_locale).text())},
    };
}

// ---------------------------------------------------------------- navigation

void WalletController::navigate(const QString &route)
{
    const bool shell = kShellRoutes.contains(route);
    if (!shell && !kOnboardingRoutes.contains(route))
        return;
    // A locked or absent wallet keeps every wallet page out of reach, including by shortcut.
    if (shell && (!m_hasWallet || m_locked))
        return;
    // Leaving for another wallet (welcome, create, restore) waits for a submission in flight.
    if (!shell && route != QStringLiteral("unlock") && !onboarding() && refuseWalletChange())
        return;
    if (!shell && route != QStringLiteral("unlock") && m_route == QStringLiteral("unlock") && refuseWalletChange())
        return;
    if (m_route == QStringLiteral("create-2") && route != QStringLiteral("create-2"))
        m_wordsRevealed = false;
    if (route == QStringLiteral("create-3") && !m_ack)
        return;
    if (route == QStringLiteral("create-4")) {
        for (int p : kQuiz)
            if (m_picks.value(p) != sampleWords().at(p - 1))
                return;
    }
    // A payment being prepared is discarded on leaving; the form keeps what was typed (re-check N2).
    if (route != QStringLiteral("send") && m_sendStep == QStringLiteral("preparing")) {
        m_prepRequest = 0;
        m_sendStep = QStringLiteral("form");
    }
    if (route != QStringLiteral("send") && m_prepared) {
        m_prepared.reset();
        emit reviewClosed();
    }
    if (route == QStringLiteral("send") && m_sendStep == QStringLiteral("result"))
        sendAnother();
    if (!route.startsWith(QStringLiteral("restore-")))
        m_restoreWords = QStringList(25, QString()), m_badWords.clear();
    if (m_seedDialog != QStringLiteral("none"))
        hideRecoveryWords();
    if (!m_consentToken.isEmpty()) {
        m_consentToken.clear();
        emit consentClosed();
    }
    m_nodePick.clear();
    m_onbErrors.clear();
    m_unlockError.clear();
    m_route = route;
    emit changed();
    emit focusHeading();
}

void WalletController::toggleExact()
{
    m_exact = !m_exact;
    refreshModels();
    emit changed();
}

void WalletController::setToast(const QString &text)
{
    m_toast = text;
    ++m_toastSerial;
    emit toastChanged();
}

void WalletController::say(const QString &text) { emit announce(text); }

void WalletController::refreshModels()
{
    const auto sorted = m_ledger.sorted();
    m_activity->refresh(sorted);
    m_recent->refresh(sorted);
}

void WalletController::copyAddress()
{
    QClipboard *cb = QGuiApplication::clipboard();
    const QString a = receiveAddress();
    QString msg = QStringLiteral("Couldn't copy. Select the text and copy it yourself.");
    if (cb) {
        cb->setText(a);
        if (cb->text() == a)
            msg = QStringLiteral("Copied");
    }
    setToast(msg);
    say(msg);
}

void WalletController::copyTransactionId(const QString &rowId)
{
    const Tx *tx = m_ledger.find(rowId);
    QClipboard *cb = QGuiApplication::clipboard();
    QString msg = QStringLiteral("Couldn't copy. Select the text and copy it yourself.");
    if (tx && !tx->txid.isEmpty() && cb) {
        cb->setText(tx->txid);
        if (cb->text() == tx->txid)
            msg = QStringLiteral("Copied");
    }
    setToast(msg);
    say(msg);
}

QString WalletController::rowSubtitle(const Tx &tx) const
{
    const QString kit = kitLabelFor(tx.to);
    const QString notePart = tx.note.isEmpty() ? QString() : QStringLiteral(" · ") + tx.note;
    if (tx.type == TxType::Out && tx.status != TxStatus::Unknown && !kit.isEmpty())
        return QStringLiteral("To ") + kit + notePart;
    if (tx.type == TxType::Mined)
        return QStringLiteral("Blocks %1–%2").arg(m_locale.toString(tx.firstHeight), m_locale.toString(tx.firstHeight + tx.blocks - 1));
    if (tx.type == TxType::In)
        return tx.note.isEmpty() ? QStringLiteral("Sender not shown") : tx.note;
    return QStringLiteral("To ") + shortAddress(addressFor(tx.to)) + notePart;
}

QVariantMap WalletController::detail(const QString &rowId) const
{
    const Tx *tx = m_ledger.find(rowId);
    if (!tx)
        return {};
    const bool out = tx->type == TxType::Out;

    QString block = !tx->height ? QStringLiteral("Not in a block yet")
                    : tx->type == TxType::Mined
                        ? QStringLiteral("%1–%2").arg(m_locale.toString(tx->firstHeight), m_locale.toString(tx->firstHeight + tx->blocks - 1))
                        : m_locale.toString(*tx->height);
    return {
        {QStringLiteral("rowId"), tx->id},
        {QStringLiteral("title"), ledger::title(*tx)},
        {QStringLiteral("subtitle"), rowSubtitle(*tx)},
        {QStringLiteral("rowAmount"), amountView(tx->amount, out, m_exact, true)},
        {QStringLiteral("amount"), amountView(tx->amount, out, true, true)},
        {QStringLiteral("isOut"), out},
        {QStringLiteral("isIn"), tx->type == TxType::In},
        {QStringLiteral("fee"), out ? amountText(tx->fee) : QString()},
        {QStringLiteral("to"), out ? addressFor(tx->to) : QString()},
        {QStringLiteral("status"), ledger::statusText(m_ledger, *tx)},
        {QStringLiteral("statusKind"), ledger::statusKind(m_ledger, *tx)},
        {QStringLiteral("block"), block},
        {QStringLiteral("txid"), tx->txid},
        {QStringLiteral("note"), tx->note},
        {QStringLiteral("failed"), tx->status == TxStatus::Failed},
        {QStringLiteral("unknown"), tx->status == TxStatus::Unknown},
        {QStringLiteral("checking"), m_checkRequest != 0 && m_checkRowId == tx->id},
    };
}

// ---------------------------------------------------------------- send

QVariantMap WalletController::send() const
{
    const ledger::Balances b = m_ledger.balances();
    const Tx *unknown = nullptr;
    for (const Tx &t : m_ledger.txs)
        if (t.status == TxStatus::Unknown)
            unknown = &t;
    const bool belowFee = b.unlocked <= ledger::kFee;
    QString reason;
    if (!canTransact())
        reason = QStringLiteral("Sending is paused until %1.").arg(pausedUntil());
    else if (belowFee)
        reason = balance().value(QStringLiteral("nothingSpendable")).toString();
    return {
        {QStringLiteral("step"), m_sendStep},
        {QStringLiteral("to"), m_sendTo},
        {QStringLiteral("amount"), m_sendAmount},
        {QStringLiteral("note"), m_sendNote},
        {QStringLiteral("toError"), m_toError},
        {QStringLiteral("amountError"), m_amountError},
        {QStringLiteral("canReview"), canTransact() && !unknown && !belowFee},
        {QStringLiteral("disabledReason"), reason},
        {QStringLiteral("hasUnknown"), unknown != nullptr},
        {QStringLiteral("unknownRowId"), unknown ? unknown->id : QString()},
        {QStringLiteral("spendableHint"), amountText(b.unlocked)},
        {QStringLiteral("decimalPoint"), m_locale.decimalPoint()},
        {QStringLiteral("toHint"), m_testnet ? QStringLiteral("Testnet addresses start with T. Paste rather than type.")
                                             : QStringLiteral("Only wallets in your Meownero test kit can be paid on the local regtest.")},
        {QStringLiteral("placeholder"), QStringLiteral("Paste a %1 address").arg(networkName().toLower())},
    };
}

QVariantMap WalletController::review() const
{
    if (!m_prepared)
        return {{QStringLiteral("open"), false}};
    const Prepared &p = *m_prepared;
    return {{QStringLiteral("open"), true},
            {QStringLiteral("token"), p.token},
            {QStringLiteral("amount"), amountText(p.amount)},
            {QStringLiteral("fee"), amountText(p.fee)},
            {QStringLiteral("total"), amountText(p.amount + p.fee)},
            {QStringLiteral("to"), p.recipient},
            {QStringLiteral("network"), networkTitle() + QStringLiteral(" · test coins")},
            {QStringLiteral("note"), p.note},
            {QStringLiteral("confirmLabel"), QStringLiteral("Send ") + amountText(p.amount)}};
}

QVariantMap WalletController::sendResult() const
{
    return {{QStringLiteral("kind"), m_resultKind},
            {QStringLiteral("amount"), amountText(m_resultAmount)},
            {QStringLiteral("fee"), amountText(m_resultFee)},
            {QStringLiteral("change"), m_resultChange > 0 ? amountText(m_resultChange) : QString()},
            {QStringLiteral("to"), m_resultTo},
            {QStringLiteral("txid"), m_resultTxid},
            {QStringLiteral("reason"), m_resultReason},
            {QStringLiteral("rowId"), m_resultRowId}};
}

void WalletController::setSendField(const QString &field, const QString &value)
{
    if (field == QStringLiteral("to")) {
        if (m_sendTo == value) return;
        m_sendTo = value;
        m_toError.clear();
    } else if (field == QStringLiteral("amount")) {
        if (m_sendAmount == value) return;
        m_sendAmount = value;
        m_amountError.clear();
    } else if (field == QStringLiteral("note")) {
        if (m_sendNote == value) return;
        m_sendNote = value.left(80);
    } else {
        return;
    }
    ++m_formRevision; // anything prepared from the old form is now stale
    if (m_prepared) {
        m_prepared.reset();
        emit reviewClosed();
    }
    if (m_sendStep == QStringLiteral("preparing")) {
        m_prepRequest = 0;
        m_sendStep = QStringLiteral("form");
    }
    emit changed();
}

void WalletController::pickKitWallet(const QString &key)
{
    if (m_testnet || (key != QStringLiteral("b") && key != QStringLiteral("c")))
        return;
    setSendField(QStringLiteral("to"), addressFor(key));
}

void WalletController::useMax()
{
    const ledger::Balances b = m_ledger.balances();
    if (b.unlocked > ledger::kFee) {
        const QChar dp = m_locale.decimalPoint().isEmpty() ? QLatin1Char('.') : m_locale.decimalPoint().at(0);
        setSendField(QStringLiteral("amount"), amount::plain(b.unlocked - ledger::kFee, dp));
        m_amountError.clear();
    } else {
        m_amountError = QStringLiteral("Your spendable balance can't cover the network fee, so there's nothing to send yet.");
    }
    emit changed();
}

bool WalletController::validateSend()
{
    const ledger::Balances b = m_ledger.balances();
    QString to = m_sendTo.trimmed();
    to.remove(QRegularExpression(QStringLiteral("\\s+")));
    m_toError.clear();
    m_amountError.clear();
    const QChar prefix = m_testnet ? QLatin1Char('T') : QLatin1Char('4');
    const QStringList known = {addressFor(QStringLiteral("self")), addressFor(QStringLiteral("b")), addressFor(QStringLiteral("c"))};
    static const QRegularExpression nonBase58(QStringLiteral("[^1-9A-HJ-NP-Za-km-z]"));
    if (to.isEmpty())
        m_toError = QStringLiteral("Enter the address you're paying.");
    else if (nonBase58.match(to).hasMatch())
        m_toError = QStringLiteral("Addresses don't contain 0, O, I or l, spaces or punctuation. Check for a typo.");
    else if (to.size() != 95 && to.size() != 106)
        m_toError = QStringLiteral("This address is incomplete: it has %1 characters, and a full one has 95.").arg(to.size());
    else if (to.at(0) == QLatin1Char('M'))
        m_toError = QStringLiteral("That's a Meownero mainnet address. This wallet only sends test coins on the %1. Mainnet doesn't exist yet.").arg(networkProse());
    else if (to.at(0) != prefix)
        m_toError = m_testnet ? QStringLiteral("That isn't a Meownero testnet address. It may be a local regtest or Monero address.")
                    : to.at(0) == QLatin1Char('T')
                        ? QStringLiteral("That's a Meownero testnet address. This wallet is on the local regtest, so it can't pay it.")
                        : QStringLiteral("That isn't one of the test wallets in your Meownero test kit. On the local regtest you can only pay those wallets.");
    else if (!m_testnet && !known.contains(to))
        m_toError = QStringLiteral("That isn't one of the test wallets in your Meownero test kit. On the local regtest you can only pay those wallets. If you meant one of them, pick it above.");
    else if (!known.contains(to))
        m_toError = QStringLiteral("This address has a typo somewhere: its checksum doesn't match. Copy it again from the person you're paying.");
    else if (to == known.at(0))
        m_toError = QStringLiteral("That's this wallet's own address.");

    const amount::ParseResult p = amount::parse(m_sendAmount, m_locale);
    if (!p.ok)
        m_amountError = p.message;
    else if (p.atomic > b.total || b.total - p.atomic < ledger::kFee)
        m_amountError = QStringLiteral("That's more than this wallet holds. Including the fee, the most you can send is %1.")
                            .arg(amountText(b.unlocked > ledger::kFee ? b.unlocked - ledger::kFee : 0));
    else if (p.atomic > b.unlocked || b.unlocked - p.atomic < ledger::kFee)
        m_amountError = QStringLiteral("Only %1 is spendable now. %2 is still unlocking%3.")
                            .arg(amountText(b.unlocked), amountText(b.locked),
                                 b.nextUnlock ? QStringLiteral("; more is ready in %1 block%2").arg(*b.nextUnlock).arg(*b.nextUnlock == 1 ? QString() : QStringLiteral("s")) : QString());
    m_cleanTo = to;
    m_parsedAmount = p.ok ? p.atomic : 0;
    return m_toError.isEmpty() && m_amountError.isEmpty();
}

void WalletController::requestReview()
{
    if (m_route != QStringLiteral("send") || m_sendStep != QStringLiteral("form") || m_prepared)
        return;
    if (!send().value(QStringLiteral("canReview")).toBool())
        return;
    if (!validateSend()) {
        emit changed();
        emit focusField(!m_toError.isEmpty() ? QStringLiteral("to") : QStringLiteral("amount"));
        return;
    }
    m_prepRequest = m_nextId++;
    m_prepEpoch = m_epoch;
    m_prepFormRevision = m_formRevision;
    m_sendStep = QStringLiteral("preparing");
    emit changed();
    emit focusHeading();
    say(QStringLiteral("Preparing the payment."));
    m_backend->prepareTransfer(m_prepRequest, m_cleanTo, m_parsedAmount);
}

void WalletController::onPrepared(quint64 requestId, const QString &ref, quint64 fee, const QString &txid)
{
    // Late replies cannot reopen a review: the request, session, form and page must all still match.
    if (requestId == 0 || requestId != m_prepRequest || m_prepEpoch != m_epoch || m_prepFormRevision != m_formRevision
        || m_route != QStringLiteral("send") || m_sendStep != QStringLiteral("preparing")) {
        ++m_staleDropped;
        return;
    }
    m_prepRequest = 0;
    Prepared p;
    p.token = QStringLiteral("review-%1").arg(m_nextId++);
    p.epoch = m_epoch;
    p.formRevision = m_formRevision;
    p.recipient = m_cleanTo;
    p.amount = m_parsedAmount;
    p.fee = fee;
    p.note = m_sendNote;
    p.preparedRef = ref;
    p.txid = txid;
    m_prepared = p;
    m_sendStep = QStringLiteral("form");
    emit changed();
    emit reviewReady();
}

void WalletController::cancelReview()
{
    if (!m_prepared)
        return;
    m_prepared.reset(); // Edit discards the prepared transaction; it is prepared again next time
    emit changed();
}

bool WalletController::confirmSend(const QString &reviewToken)
{
    const ledger::Balances b = m_ledger.balances();
    const bool valid = m_prepared && !reviewToken.isEmpty() && reviewToken == m_prepared->token
                       && m_prepared->epoch == m_epoch && m_prepared->formRevision == m_formRevision
                       && m_route == QStringLiteral("send") && canTransact() && !m_ledger.hasUnknownSubmission()
                       && !m_attempt && m_prepared->amount <= b.unlocked && b.unlocked - m_prepared->amount >= m_prepared->fee;
    if (!valid) {
        ++m_staleRefused;
        const bool had = m_prepared.has_value();
        m_prepared.reset();
        if (m_sendStep != QStringLiteral("result") && m_sendStep != QStringLiteral("submitting"))
            m_sendStep = QStringLiteral("form");
        emit changed();
        emit reviewClosed();
        say(had || !reviewToken.isEmpty()
                ? QStringLiteral("This review is out of date, so nothing was sent. Review the payment again.")
                : QStringLiteral("Nothing to send. Review the payment first."));
        return false;
    }
    Attempt a;
    a.id = m_nextId++;
    a.walletGeneration = m_walletGeneration;
    a.prepared = *m_prepared;
    // Inputs are whole outputs; whatever they hold beyond amount + fee comes back as change.
    const quint64 spend = a.prepared.amount + a.prepared.fee;
    const quint64 k = (spend + ledger::kReward - 1) / ledger::kReward;
    const quint64 room = b.unlocked - spend;
    a.changeBack = room > 0 ? std::min(k * ledger::kReward - spend, room) : 0;
    m_attempt = a;
    m_prepared.reset();
    m_sendStep = QStringLiteral("submitting");
    emit changed();
    emit focusHeading();
    say(QStringLiteral("Submitting the payment to your node."));
    m_backend->relayPrepared(a.id, a.prepared.preparedRef);
    return true;
}

void WalletController::onRelayFinished(quint64 attemptId, SimulatedBackend::SendOutcome outcome, const QString &reason)
{
    if (!m_attempt || m_attempt->id != attemptId) {
        ++m_staleDropped;
        return;
    }
    if (m_attempt->walletGeneration != m_walletGeneration) {
        // Unreachable while wallet changes are refused during a submission; never leave it set.
        m_attempt.reset();
        ++m_staleDropped;
        emit changed();
        return;
    }
    // A submission already under way keeps its identity and finishes even if the user left Send.
    const Attempt a = *m_attempt;
    m_attempt.reset();
    m_resultAmount = a.prepared.amount;
    m_resultFee = a.prepared.fee;
    m_resultTo = a.prepared.recipient;
    m_resultTxid = a.prepared.txid;
    m_resultReason = reason;
    m_resultChange = 0;
    m_resultRowId.clear();
    QString msg;
    if (outcome == SimulatedBackend::SendOutcome::Refused) {
        m_resultKind = QStringLiteral("refused");
        msg = QStringLiteral("Payment not sent. Your node refused it, and your balance hasn't changed.");
    } else {
        Tx tx;
        tx.id = QStringLiteral("s%1").arg(a.id);
        tx.type = TxType::Out;
        tx.amount = a.prepared.amount;
        tx.fee = a.prepared.fee;
        tx.change = a.changeBack;
        QString key = a.prepared.recipient;
        for (const QString &k : {QStringLiteral("b"), QStringLiteral("c")})
            if (addressFor(k) == key)
                key = k;
        tx.to = key;
        tx.txid = a.prepared.txid;
        tx.note = a.prepared.note;
        tx.attemptId = a.id;
        tx.status = outcome == SimulatedBackend::SendOutcome::ConnectionDrops ? TxStatus::Unknown : TxStatus::Normal;
        m_ledger.txs.append(tx);
        m_resultRowId = tx.id;
        m_resultChange = tx.change;
        if (tx.status == TxStatus::Unknown) {
            m_resultKind = QStringLiteral("unknown");
            msg = QStringLiteral("Submission status unknown. Check this payment before trying again.");
        } else {
            m_resultKind = QStringLiteral("sent");
            msg = QStringLiteral("Sent. Submitted to your node and waiting to confirm.");
        }
    }
    m_sendStep = QStringLiteral("result");
    refreshModels();
    emit changed();
    if (m_route == QStringLiteral("send"))
        emit focusHeading();
    say(msg);
}

void WalletController::sendAnother()
{
    m_sendStep = QStringLiteral("form");
    m_sendTo.clear();
    m_sendAmount.clear();
    m_sendNote.clear();
    m_toError.clear();
    m_amountError.clear();
    m_resultKind.clear();
    ++m_formRevision;
    emit changed();
}

void WalletController::reconcile(const QString &rowId)
{
    const Tx *tx = m_ledger.find(rowId);
    if (!tx || tx->status != TxStatus::Unknown || m_checkRequest != 0)
        return;
    if (!canTransact()) {
        say(QStringLiteral("Checking needs %1.").arg(pausedNeeds()));
        return;
    }
    m_checkRequest = m_nextId++;
    m_checkEpoch = m_epoch;
    m_checkRowId = rowId;
    emit changed();
    say(QStringLiteral("Checking with your node."));
    m_backend->checkSubmission(m_checkRequest, tx->txid);
}

void WalletController::onChecked(quint64 requestId, const QString &txid, bool found)
{
    Tx *tx = m_ledger.find(m_checkRowId);
    // Evidence counts only for the session that asked: lock, node or wallet changes drop it.
    if (requestId == 0 || requestId != m_checkRequest || m_checkEpoch != m_epoch || !tx
        || tx->status != TxStatus::Unknown || tx->txid != txid) {
        ++m_staleDropped;
        return;
    }
    const QString rowId = m_checkRowId;
    m_checkRequest = 0;
    m_checkRowId.clear();
    // Leaves "unknown" only on evidence: found by the node, or proven absent by the node.
    tx->status = found ? TxStatus::Normal : TxStatus::Failed;
    const QString msg = found ? QStringLiteral("Your node has this payment. It's waiting to confirm.")
                              : QStringLiteral("Not sent: your node never received this payment, and the coins are back in your balance.");
    refreshModels();
    emit changed();
    emit reconciled(rowId);
    setToast(msg);
    say(msg);
}

void WalletController::mineTestCoins()
{
    if (m_testnet || !canTransact() || m_mineRequest != 0 || !m_hasWallet || m_locked)
        return;
    m_mineRequest = m_nextId++;
    m_mineGeneration = m_walletGeneration;
    m_backend->generateBlocks(m_mineRequest, 10);
}

void WalletController::onBlocks(quint64 requestId, int count)
{
    if (requestId == 0 || requestId != m_mineRequest || m_mineGeneration != m_walletGeneration) {
        ++m_staleDropped;
        return;
    }
    m_mineRequest = 0;
    const int first = m_ledger.tip + 1;
    Tx found;
    bool resolved = false;
    for (Tx &t : m_ledger.txs) {
        if (t.height || t.status == TxStatus::Failed)
            continue;
        if (t.status == TxStatus::Unknown) {
            if (m_backend->unknownResolves != SimulatedBackend::UnknownResolves::ReachedNode)
                continue; // a block without it proves nothing
            t.status = TxStatus::Normal;
            resolved = true;
            found = t;
        }
        t.height = first;
    }
    Tx mined;
    mined.id = QStringLiteral("m%1").arg(first);
    mined.type = TxType::Mined;
    mined.blocks = count;
    mined.amount = ledger::kReward * quint64(count);
    mined.firstHeight = first;
    mined.height = first + count - 1;
    m_ledger.txs.append(mined);
    m_ledger.tip += count;
    m_reorg.reset();
    refreshModels();
    emit changed();
    setToast(QStringLiteral("Mined %1 test blocks").arg(count));
    say(QStringLiteral("Mined %1 test blocks").arg(count));
    if (resolved)
        say(QStringLiteral("The payment whose status was unknown is in block %1, so your node received it. It's confirming now.").arg(m_locale.toString(first)));
}

void WalletController::retryNode()
{
    if (canTransact() || m_nodeState == QStringLiteral("connecting"))
        return;
    setNode(QStringLiteral("connecting"));
    m_reconnectRequest = m_nextId++;
    m_backend->reconnect(m_reconnectRequest);
}

void WalletController::onReconnected(quint64 requestId)
{
    if (requestId == 0 || requestId != m_reconnectRequest || m_nodeState != QStringLiteral("connecting")) {
        ++m_staleDropped;
        return;
    }
    m_reconnectRequest = 0;
    setNode(QStringLiteral("synced"));
}

void WalletController::dismissReorg()
{
    m_reorg.reset();
    emit changed();
}

void WalletController::setNode(const QString &state, bool announceIt)
{
    if (!kNodeStates.contains(state))
        return;
    const bool wasTransacting = canTransact();
    if (wasTransacting)
        m_lastSyncedMs = QDateTime::currentMSecsSinceEpoch();
    const bool changedState = state != m_nodeState;
    m_nodeState = state;
    if (wasTransacting && !canTransact())
        invalidateSession(QStringLiteral("node unavailable"));
    if (state != QStringLiteral("connecting"))
        m_reconnectRequest = 0;
    m_nodePick.clear();
    emit changed();
    if (announceIt && changedState)
        say(chipAccessible());
}

// ---------------------------------------------------------------- node choice

void WalletController::pickNode(const QString &choice)
{
    if (choice == QStringLiteral("remote") && !m_testnet)
        return; // someone else's node is never offered on the local regtest
    if (choice != QStringLiteral("local") && choice != QStringLiteral("remote"))
        return;
    m_nodePick = choice; // a pick changes nothing until an explicit Connect
    emit changed();
}

void WalletController::applyNodePick()
{
    const QString current = m_nodeState == QStringLiteral("remote") ? QStringLiteral("remote") : QStringLiteral("local");
    if (m_nodePick.isEmpty() || m_nodePick == current)
        return;
    if (m_nodePick == QStringLiteral("remote")) {
        if (!m_testnet)
            return;
        m_consentToken = QStringLiteral("consent-%1").arg(m_nextId++);
        m_consentEpoch = m_epoch;
        emit changed();
        emit consentRequested();
        return;
    }
    // Back to your own node: one Connect, no dialog.
    invalidateSession(QStringLiteral("node change"));
    m_nodeState = QStringLiteral("connecting");
    setNode(QStringLiteral("synced"));
}

bool WalletController::confirmRemoteNode(const QString &token)
{
    const bool valid = !token.isEmpty() && token == m_consentToken && m_consentEpoch == m_epoch && m_testnet
                       && m_nodePick == QStringLiteral("remote");
    const bool hadDialog = !m_consentToken.isEmpty();
    m_consentToken.clear();
    if (!valid) {
        ++m_staleRefused;
        m_nodePick.clear();
        emit changed();
        emit consentClosed();
        if (hadDialog || !token.isEmpty())
            say(QStringLiteral("That confirmation is out of date, so nothing changed. Your current node was kept."));
        return false;
    }
    emit consentClosed();
    invalidateSession(QStringLiteral("node change"));
    setNode(QStringLiteral("remote"));
    return true;
}

void WalletController::keepCurrentNode()
{
    const bool had = !m_consentToken.isEmpty() || !m_nodePick.isEmpty();
    m_consentToken.clear();
    m_nodePick.clear();
    if (had) {
        emit changed();
        emit consentClosed();
    }
}

void WalletController::dismissConsent()
{
    // Escape or clicking outside: the dialog closes, nothing connects, the pick stays.
    if (m_consentToken.isEmpty())
        return;
    m_consentToken.clear();
    emit changed();
}

// ---------------------------------------------------------------- session

void WalletController::invalidateSession(const QString &why)
{
    Q_UNUSED(why);
    ++m_epoch;
    m_prepRequest = 0;
    m_checkRequest = 0; // an outstanding node check no longer applies; Check with node can run again
    m_checkRowId.clear();
    if (m_sendStep == QStringLiteral("preparing"))
        m_sendStep = QStringLiteral("form");
    if (m_prepared) {
        m_prepared.reset();
        emit reviewClosed();
    }
    if (!m_consentToken.isEmpty()) {
        m_consentToken.clear();
        emit consentClosed();
    }
    m_nodePick.clear();
    hideRecoveryWords();
}

void WalletController::loadWallet(ledger::Story story, const QString &name)
{
    m_ledger = ledger::story(story);
    m_walletName = name;
    ++m_walletGeneration;
    m_hasWallet = true;
    m_locked = false;
    m_reorg.reset();
    m_checkRequest = 0;
    m_mineRequest = 0;
    invalidateSession(QStringLiteral("wallet change"));
    sendAnother();
    refreshModels();
}

void WalletController::lock()
{
    if (!m_hasWallet || m_locked)
        return;
    invalidateSession(QStringLiteral("lock"));
    m_locked = true;
    m_unlockError.clear();
    m_onbErrors.clear();
    m_route = QStringLiteral("unlock");
    emit changed();
    emit focusHeading();
    say(QStringLiteral("Wallet locked."));
}

void WalletController::unlock(const QString &password)
{
    if (password.isEmpty())
        m_unlockError = QStringLiteral("Enter your password.");
    else if (!m_hasWallet && password != QStringLiteral("simulated"))
        m_unlockError = QStringLiteral("That password doesn't open this wallet file. Passwords are case-sensitive.");
    else if (m_hasWallet && digestOf(password) != m_passwordDigest)
        m_unlockError = QStringLiteral("That password doesn't open this wallet file. Passwords are case-sensitive.");
    else {
        if (!m_hasWallet) {
            // First run "Open a wallet file": the simulated fixture wallet.
            loadWallet(ledger::Story::Normal, QStringLiteral("Test wallet"));
            m_passwordDigest = digestOf(password);
            m_fixtureWallet = true;
        }
        m_locked = false;
        m_unlockError.clear();
        invalidateSession(QStringLiteral("unlock"));
        navigate(QStringLiteral("overview"));
        return;
    }
    emit changed();
    emit focusField(QStringLiteral("unlock"));
    say(m_unlockError);
}

bool WalletController::refuseWalletChange()
{
    // A submission keeps its attempt identity and finishes against its own wallet.
    if (!m_attempt)
        return false;
    say(QStringLiteral("A payment is still being submitted. Wait for it to finish before switching wallets."));
    return true;
}

void WalletController::startOver()
{
    if (refuseWalletChange())
        return;
    invalidateSession(QStringLiteral("wallet change"));
    m_locked = true; // the current wallet file stays on this computer, closed
    m_onbName = QStringLiteral("Test wallet");
    m_route.clear();
    navigate(QStringLiteral("welcome"));
}

QString WalletController::passwordHint() const
{
    if (!m_hasWallet || m_fixtureWallet)
        return QStringLiteral("Simulated wallet file. Its fixture password is “simulated”.");
    return QStringLiteral("Simulated wallet: use the password you chose for it.");
}

// ---------------------------------------------------------------- recovery words

QStringList WalletController::displayedWords() const
{
    const bool show = (m_route == QStringLiteral("create-2") && m_wordsRevealed) || m_seedDialog == QStringLiteral("words");
    return show ? sampleWords() : QStringList(25, kVeiled);
}

void WalletController::revealWords()
{
    if (m_route != QStringLiteral("create-2"))
        return;
    m_wordsRevealed = true;
    emit changed();
}

void WalletController::setAcknowledged(bool ack)
{
    m_ack = ack && m_wordsRevealed;
    emit changed();
}

void WalletController::hideRecoveryWords()
{
    const bool wasOpen = m_seedDialog != QStringLiteral("none");
    const bool was = m_wordsRevealed || wasOpen;
    m_wordsRevealed = false;
    m_seedDialog = QStringLiteral("none");
    m_seedError.clear();
    if (wasOpen)
        emit seedClosed();
    if (was)
        emit changed();
}

void WalletController::requestSeed()
{
    if (!m_hasWallet || m_locked || m_route != QStringLiteral("wallet"))
        return;
    m_seedDialog = QStringLiteral("password");
    m_seedError.clear();
    emit changed();
    emit seedRequested();
}

void WalletController::submitSeedPassword(const QString &password)
{
    if (m_seedDialog != QStringLiteral("password") || m_locked)
        return;
    // The RPC returns the mnemonic without checking a password, so the app checks it first.
    if (password.isEmpty())
        m_seedError = QStringLiteral("Enter your password.");
    else if (digestOf(password) != m_passwordDigest)
        m_seedError = QStringLiteral("That password doesn't open this wallet.");
    else {
        m_seedError.clear();
        m_seedDialog = QStringLiteral("words");
        emit changed();
        emit seedRequested();
        return;
    }
    emit changed();
    emit focusField(QStringLiteral("seed-password"));
    say(m_seedError);
}

// ---------------------------------------------------------------- create and restore

QVariantMap WalletController::onb() const
{
    QVariantMap picks, wrong;
    for (auto it = m_picks.begin(); it != m_picks.end(); ++it)
        picks.insert(QString::number(it.key()), it.value());
    for (auto it = m_wrong.begin(); it != m_wrong.end(); ++it)
        wrong.insert(QString::number(it.key()), it.value());
    bool quizOk = true;
    for (int p : kQuiz)
        quizOk = quizOk && m_picks.value(p) == sampleWords().at(p - 1);
    QVariantList bad;
    for (int i : m_badWords)
        bad.append(i);
    const int tip = m_hasWallet ? m_ledger.tip : kChainTip;
    const int from = m_restoreHeight.toInt();
    return {
        {QStringLiteral("name"), m_onbName},
        {QStringLiteral("errors"), m_onbErrors},
        {QStringLiteral("revealed"), m_wordsRevealed},
        {QStringLiteral("ack"), m_ack},
        {QStringLiteral("picks"), picks},
        {QStringLiteral("wrong"), wrong},
        {QStringLiteral("quiz"), QVariantList{4, 13, 22}},
        {QStringLiteral("quizOk"), quizOk},
        {QStringLiteral("createdAt"), m_locale.toString(kChainTip - 4)},
        {QStringLiteral("chainTip"), m_locale.toString(tip)},
        {QStringLiteral("badWords"), bad},
        {QStringLiteral("scan"), m_restoreScan},
        {QStringLiteral("scanBlock"), m_locale.toString(from + (kChainTip - from) * m_restoreScan / 100)},
        {QStringLiteral("unlockError"), m_unlockError},
        {QStringLiteral("hasWallet"), m_hasWallet},
        {QStringLiteral("restoredSummary"),
         QStringLiteral("Found 4 payments. Spendable balance %1.")
             .arg(amountText(ledger::story(ledger::Story::Normal).balances().unlocked, false))},
    };
}

void WalletController::submitCreateDetails(const QString &name, const QString &password, const QString &repeat)
{
    m_onbErrors.clear();
    m_onbName = name;
    QString first;
    if (name.trimmed().isEmpty())
        m_onbErrors.insert(QStringLiteral("name"), QStringLiteral("Give the wallet a name."));
    else if (m_hasWallet && name.trimmed() == m_walletName)
        m_onbErrors.insert(QStringLiteral("name"), QStringLiteral("A wallet named “%1” already exists on this computer. Choose another name; nothing was overwritten.").arg(name.trimmed()));
    if (password.size() < 8)
        m_onbErrors.insert(QStringLiteral("pw"), QStringLiteral("Use at least 8 characters."));
    else if (password != repeat)
        m_onbErrors.insert(QStringLiteral("pw2"), QStringLiteral("The passwords don't match."));
    for (const QString &k : {QStringLiteral("name"), QStringLiteral("pw"), QStringLiteral("pw2")})
        if (first.isEmpty() && m_onbErrors.contains(k))
            first = k;
    if (!first.isEmpty()) {
        emit changed();
        emit focusField(first);
        say(m_onbErrors.value(first).toString());
        return;
    }
    m_pendingDigest = digestOf(password);
    m_ack = false;
    m_picks.clear();
    m_wrong.clear();
    navigate(QStringLiteral("create-2"));
}

QStringList WalletController::quizOptions(int p) const
{
    if (p < 1 || p > 25)
        return {};
    const QString right = sampleWords().at(p - 1);
    QStringList pool = sampleWords();
    pool.removeAll(right);
    QStringList all = {right, pool.at((p * 7) % pool.size()), pool.at((p * 11 + 3) % pool.size()),
                       pool.at((p * 5 + 9) % pool.size())};
    all.removeDuplicates();
    std::stable_sort(all.begin(), all.end(), [p](const QString &a, const QString &b) {
        return (a.at(1).unicode() * p) % 7 < (b.at(1).unicode() * p) % 7;
    });
    return all;
}

void WalletController::pickQuizWord(int p, const QString &w)
{
    if (m_route != QStringLiteral("create-3") || p < 1 || p > 25)
        return;
    if (w == sampleWords().at(p - 1)) {
        m_picks.insert(p, w);
        m_wrong.remove(p);
    } else {
        m_wrong.insert(p, w);
        m_picks.remove(p);
        say(QStringLiteral("That isn't word %1. Check your paper.").arg(p));
    }
    emit changed();
}

void WalletController::openNewWallet()
{
    if (m_route != QStringLiteral("create-4") || refuseWalletChange())
        return;
    loadWallet(ledger::Story::Empty, m_onbName.trimmed());
    m_ledger.created = m_ledger.tip - 4;
    m_passwordDigest = m_pendingDigest;
    m_pendingDigest.clear();
    m_fixtureWallet = false;
    navigate(QStringLiteral("overview"));
}

void WalletController::setRestoreWord(int index, const QString &text)
{
    if (index < 0 || index >= 25 || !m_route.startsWith(QStringLiteral("restore-")))
        return;
    static const QRegularExpression ws(QStringLiteral("\\s+"));
    const QStringList parts = text.trimmed().split(ws, Qt::SkipEmptyParts);
    if (parts.size() > 1) {
        // Pasting the whole phrase into one box fills the rest.
        for (int k = 0; k < parts.size() && index + k < 25; ++k)
            m_restoreWords[index + k] = parts.at(k).toLower();
        emit changed();
        return;
    }
    m_restoreWords[index] = text.trimmed().toLower();
}

void WalletController::submitRestoreWords()
{
    if (m_route != QStringLiteral("restore-1"))
        return;
    m_onbErrors.clear();
    m_badWords.clear();
    int filled = 0, firstEmpty = -1;
    for (int i = 0; i < 25; ++i) {
        const QString &w = m_restoreWords.at(i);
        if (w.isEmpty()) {
            if (firstEmpty < 0)
                firstEmpty = i;
        } else {
            ++filled;
            if (!isKnownWord(w))
                m_badWords.append(i);
        }
    }
    int focusIndex = 0;
    if (filled != 25) {
        m_onbErrors.insert(QStringLiteral("words"), QStringLiteral("Recovery phrases have 25 words. You've entered %1.").arg(filled));
        focusIndex = firstEmpty;
    } else if (!m_badWords.isEmpty()) {
        m_onbErrors.insert(QStringLiteral("words"), QStringLiteral("“%1” (word %2) isn't a recovery word. Check the spelling against your paper.")
                                                        .arg(m_restoreWords.at(m_badWords.first()))
                                                        .arg(m_badWords.first() + 1));
        focusIndex = m_badWords.first();
    } else if (m_restoreWords != sampleWords()) {
        m_onbErrors.insert(QStringLiteral("words"), QStringLiteral("These words don't add up. The last word is a check word, and it doesn't match the others, so one word is probably wrong or out of order."));
    } else {
        // Simulated: the sample words stand in for a phrase that passes the check.
        navigate(QStringLiteral("restore-2"));
        return;
    }
    emit changed();
    emit focusField(QStringLiteral("word:%1").arg(focusIndex));
    say(m_onbErrors.value(QStringLiteral("words")).toString());
}

void WalletController::submitRestoreDetails(const QString &height, const QString &name, const QString &password)
{
    if (m_route != QStringLiteral("restore-2"))
        return;
    m_onbErrors.clear();
    m_onbName = name;
    QString h = height;
    h.remove(QRegularExpression(QStringLiteral("[,\\s]")));
    static const QRegularExpression digits(QStringLiteral("^\\d+$"));
    const int tip = m_hasWallet ? m_ledger.tip : kChainTip;
    if (!h.isEmpty() && !digits.match(h).hasMatch())
        m_onbErrors.insert(QStringLiteral("height"), QStringLiteral("Enter a block number using digits only."));
    else if (!h.isEmpty() && (h.size() > 9 || h.toInt() > tip))
        m_onbErrors.insert(QStringLiteral("height"), QStringLiteral("Block %1 is in the future. This chain is at block %2.")
                                                         .arg(h.size() > 9 ? h : m_locale.toString(h.toInt()), m_locale.toString(tip)));
    if (name.trimmed().isEmpty())
        m_onbErrors.insert(QStringLiteral("name"), QStringLiteral("Give the wallet a name."));
    else if (m_hasWallet && name.trimmed() == m_walletName)
        m_onbErrors.insert(QStringLiteral("name"), QStringLiteral("A wallet named “%1” already exists on this computer. Choose another name; nothing was overwritten.").arg(name.trimmed()));
    if (password.size() < 8)
        m_onbErrors.insert(QStringLiteral("pw"), QStringLiteral("Use at least 8 characters."));
    QString first;
    for (const QString &k : {QStringLiteral("height"), QStringLiteral("name"), QStringLiteral("pw")})
        if (first.isEmpty() && m_onbErrors.contains(k))
            first = k;
    if (!first.isEmpty()) {
        emit changed();
        emit focusField(first);
        say(m_onbErrors.value(first).toString());
        return;
    }
    m_restoreHeight = h;
    m_pendingDigest = digestOf(password);
    m_restoreScan = 0;
    m_restoreWords = QStringList(25, QString()); // consumed by the restore call; not kept
    navigate(QStringLiteral("restore-3"));
    m_scanRequest = m_nextId++;
    m_backend->scanRestore(m_scanRequest);
}

void WalletController::onScan(quint64 requestId, int percent)
{
    if (requestId == 0 || requestId != m_scanRequest) {
        ++m_staleDropped;
        return;
    }
    m_restoreScan = percent;
    emit changed();
    if (percent >= 100) {
        m_scanRequest = 0;
        say(QStringLiteral("Wallet restored. ") + onb().value(QStringLiteral("restoredSummary")).toString());
    }
}

void WalletController::openRestoredWallet()
{
    if (m_route != QStringLiteral("restore-3") || m_restoreScan < 100 || refuseWalletChange())
        return;
    loadWallet(ledger::Story::Normal, m_onbName.trimmed());
    m_ledger.created = m_restoreHeight.toInt();
    m_passwordDigest = m_pendingDigest;
    m_pendingDigest.clear();
    m_fixtureWallet = false;
    navigate(QStringLiteral("overview"));
}

// ---------------------------------------------------------------- diagnostics

QString WalletController::diagnostics() const
{
    // Built from an allowlist of fields. Recovery words, passwords, addresses,
    // transaction ids, amounts and notes are never read here.
    QStringList lines;
    lines << QStringLiteral("app=meownero-wallet 0.1.0 (simulated backend)")
          << QStringLiteral("qt=%1").arg(QString::fromLatin1(qVersion()))
          << QStringLiteral("os=%1 %2").arg(QSysInfo::prettyProductName(), QSysInfo::currentCpuArchitecture())
          << QStringLiteral("network=%1").arg(networkKey())
          << QStringLiteral("reduced_motion=%1").arg(reducedMotion() ? 1 : 0)
          << QStringLiteral("node_state=%1").arg(m_nodeState)
          << QStringLiteral("chain_tip=%1").arg(m_ledger.tip)
          << QStringLiteral("wallet_loaded=%1 locked=%2").arg(m_hasWallet).arg(m_locked)
          << QStringLiteral("history_rows=%1 pending=%2 unknown_submissions=%3")
                 .arg(m_ledger.txs.size())
                 .arg(m_ledger.pendingCount())
                 .arg(m_ledger.hasUnknownSubmission() ? 1 : 0)
          << QStringLiteral("stale_replies_dropped=%1 stale_actions_refused=%2").arg(m_staleDropped).arg(m_staleRefused);
    return lines.join(QLatin1Char('\n'));
}

// ---------------------------------------------------------------- reviewer fixtures

QVariantMap WalletController::fixtures() const
{
    return {{QStringLiteral("network"), networkKey()},
            {QStringLiteral("node"), m_nodeState},
            {QStringLiteral("sendOutcome"), m_backend->nextSendOutcome == SimulatedBackend::SendOutcome::Accepted ? QStringLiteral("accepted")
                                            : m_backend->nextSendOutcome == SimulatedBackend::SendOutcome::Refused ? QStringLiteral("refused")
                                                                                                                  : QStringLiteral("drops")},
            {QStringLiteral("unknownResolves"), m_backend->unknownResolves == SimulatedBackend::UnknownResolves::ReachedNode
                                                    ? QStringLiteral("reached") : QStringLiteral("notsent")},
            {QStringLiteral("staleDropped"), m_staleDropped},
            {QStringLiteral("staleRefused"), m_staleRefused},
            {QStringLiteral("epoch"), QString::number(m_epoch)}};
}

void WalletController::fixtureSetNetwork(const QString &key)
{
    const bool testnet = key == QStringLiteral("testnet");
    if (testnet == m_testnet)
        return;
    m_testnet = testnet;
    invalidateSession(QStringLiteral("network change"));
    sendAnother();
    // The local regtest never uses someone else's node (D5).
    if (!m_testnet && m_nodeState == QStringLiteral("remote"))
        setNode(QStringLiteral("synced"));
    refreshModels();
    emit changed();
}

void WalletController::fixtureSetNodeState(const QString &state)
{
    if (state == QStringLiteral("remote") && !m_testnet)
        return;
    if ((state == QStringLiteral("remote")) != (m_nodeState == QStringLiteral("remote")))
        invalidateSession(QStringLiteral("node change"));
    setNode(state);
}

void WalletController::fixtureSetStory(const QString &story)
{
    if (!m_hasWallet || refuseWalletChange())
        return;
    const ledger::Story s = story == QStringLiteral("empty") ? ledger::Story::Empty
                            : story == QStringLiteral("dust")  ? ledger::Story::Dust
                            : story == QStringLiteral("large") ? ledger::Story::Large
                                                               : ledger::Story::Normal;
    const QString name = m_walletName;
    const QByteArray digest = m_passwordDigest;
    const bool locked = m_locked;
    loadWallet(s, name);
    m_passwordDigest = digest;
    m_locked = locked;
    emit changed();
}

void WalletController::fixtureSetSendOutcome(const QString &outcome)
{
    m_backend->nextSendOutcome = outcome == QStringLiteral("refused") ? SimulatedBackend::SendOutcome::Refused
                                 : outcome == QStringLiteral("drops") ? SimulatedBackend::SendOutcome::ConnectionDrops
                                                                       : SimulatedBackend::SendOutcome::Accepted;
    emit changed();
}

void WalletController::fixtureSetUnknownResolves(const QString &resolves)
{
    m_backend->unknownResolves = resolves == QStringLiteral("notsent") ? SimulatedBackend::UnknownResolves::NotSent
                                                                       : SimulatedBackend::UnknownResolves::ReachedNode;
    emit changed();
}

void WalletController::fixtureAddBlocks(int count)
{
    if (!m_hasWallet || count < 1)
        return;
    Tx found;
    bool resolved = false;
    for (Tx &t : m_ledger.txs) {
        if (t.height || t.status == TxStatus::Failed)
            continue;
        // An unknown payment leaves that state only on evidence (re-check N4).
        if (t.status == TxStatus::Unknown) {
            if (m_backend->unknownResolves != SimulatedBackend::UnknownResolves::ReachedNode)
                continue;
            t.status = TxStatus::Normal;
            resolved = true;
            found = t;
        }
        t.height = m_ledger.tip + 1;
    }
    m_ledger.tip += count;
    m_reorg.reset();
    refreshModels();
    emit changed();
    if (resolved)
        say(QStringLiteral("The payment whose status was unknown is in block %1, so your node received it. It's confirming now.")
                .arg(m_locale.toString(*m_ledger.find(found.id)->height)));
}

void WalletController::fixtureReorg()
{
    Tx *cand = nullptr;
    for (Tx &t : m_ledger.txs)
        if (t.height && t.type != TxType::Mined && (!cand || *t.height > *cand->height))
            cand = &t;
    if (!cand) {
        setToast(QStringLiteral("Nothing recent enough to reorganize"));
        return;
    }
    m_reorg = std::make_pair(*cand->height, 1);
    cand->height.reset();
    refreshModels();
    emit changed();
    say(reorg().value(QStringLiteral("title")).toString() + QStringLiteral(" Your balance was updated."));
}

void WalletController::fixtureFillSend(const QString &kind)
{
    if (!m_hasWallet || m_locked)
        return;
    if (m_route != QStringLiteral("send"))
        navigate(QStringLiteral("send"));
    sendAnother();
    const QString b = addressFor(QStringLiteral("b"));
    QString to = b, amt = QStringLiteral("2.5");
    if (kind == QStringLiteral("typo"))
        to = b.left(40) + QLatin1Char('Q') + b.mid(41);
    else if (kind == QStringLiteral("wrongnet"))
        to = QString::fromLatin1(m_testnet ? kRegtest.b : kTestnet.b);
    else if (kind == QStringLiteral("mainnet"))
        to = QString::fromLatin1(kMainnet);
    else if (kind == QStringLiteral("short"))
        to = b.left(70);
    else if (kind == QStringLiteral("13dp"))
        amt = QStringLiteral("0.0000000000015");
    else if (kind == QStringLiteral("locked")) {
        const ledger::Balances bal = m_ledger.balances();
        const QChar dp = m_locale.decimalPoint().isEmpty() ? QLatin1Char('.') : m_locale.decimalPoint().at(0);
        amt = amount::plain(bal.unlocked + (bal.locked > 0 ? bal.locked / 2 : amount::kAtomicPerCoin), dp);
    }
    if (m_locale.decimalPoint() != QStringLiteral(".") && amt.contains(QLatin1Char('.')) && kind != QStringLiteral("locked"))
        amt.replace(QLatin1Char('.'), m_locale.decimalPoint());
    m_sendTo = to;
    m_sendAmount = amt;
    ++m_formRevision;
    if (kind != QStringLiteral("valid"))
        validateSend();
    emit changed();
}

void WalletController::fixtureFillRestore(const QString &kind)
{
    if ((!m_route.startsWith(QStringLiteral("restore-")) && m_route != QStringLiteral("welcome")) || refuseWalletChange())
        return;
    if (m_route != QStringLiteral("restore-1")) {
        m_route = QStringLiteral("restore-1");
        emit changed();
    }
    QStringList w = sampleWords();
    if (kind == QStringLiteral("badword"))
        w[6] = QStringLiteral("mittens");
    else if (kind == QStringLiteral("checksum"))
        w.swapItemsAt(3, 4);
    else if (kind == QStringLiteral("count"))
        w[23] = QString(), w[24] = QString();
    m_restoreWords = w;
    emit changed();
    if (kind != QStringLiteral("sample"))
        submitRestoreWords();
}
