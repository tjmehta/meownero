#!/usr/bin/python3 -I
"""Author journey checks for the native wallet on an isolated X display.

Real keyboard input goes through XTest (xdotool) to the owned Xephyr display;
focus, names, tree contents, announcements and geometry are read over AT-SPI
on a private accessibility bus. Reviewer fixtures (the separate window) are
pressed through AT-SPI actions because they stage backend states, not journeys.

These are author checks. They do not replace independent journey QA or a
real screen-reader journey.

usage: journey.py <app-binary> <evidence-dir> <portal-status-file> <portal-pid>
"""
import json
import os
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib  # noqa: E402

APP, OUT, PORTAL_STATUS, PORTAL_PID = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
DISPLAY = os.environ["DISPLAY"]
RESULTS = []
ANNOUNCEMENTS = []
RECEIVE = "4AKvVKKRpe4mjeLmYeXnU9cRrRZUjLfDhSVtuQfQHpFYrqP5iU1qr1Vtqbok9AiXZUjg1J9A5mZvmF1tJ23XPi4ztMgYjFd"
EXPOSURE = ("An untrusted node can observe your connection and request activity and link submitted "
            "transactions to that connection. Untrusted mode does not hide this metadata.")
SAMPLE = ("whisker saucer velvet lantern pebble orchard mitten harbor laboratory tundra ember quilt marble "
          "fennel cobalt sparrow thistle juniper wicker verification copper meadow ripple sable tabby").split()


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ((" — " + detail) if detail else ""), flush=True)


def pump(seconds):
    ctx = GLib.MainContext.default()
    end = time.time() + seconds
    while time.time() < end:
        while ctx.iteration(False):
            pass
        time.sleep(0.02)


def on_event(event):
    data = event.any_data
    ANNOUNCEMENTS.append({"t": round(time.time(), 3), "type": event.type, "text": data if isinstance(data, str) else str(data)})


listener = Atspi.EventListener.new(on_event)
listener.register("object:announcement")


def xdo(*args):
    return subprocess.run(["xdotool", *args], capture_output=True, text=True).stdout.strip()


def key(*keys, wait=0.35):
    for k in keys:
        xdo("key", "--clearmodifiers", k)
        pump(wait)


def typ(text):
    xdo("type", "--delay", "18", text)
    pump(0.3)


def shot(name, geom="1500x800"):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", geom, "-i", DISPLAY,
                    "-frames:v", "1", os.path.join(OUT, "screens", name + ".png")])


def find_app():
    # Qt can register a second, empty application entry; use the one with windows.
    desktop = Atspi.get_desktop(0)
    best = None
    for i in range(desktop.get_child_count()):
        a = desktop.get_child_at_index(i)
        if a is not None and a.get_name() in ("meownero-wallet", "Meownero Wallet") and a.get_child_count() > 0:
            best = a
    return best


def walk(root):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        try:
            out.append(n)
            for i in range(n.get_child_count() - 1, -1, -1):
                stack.append(n.get_child_at_index(i))
        except GLib.Error:
            pass
    return out


def label_of(n):
    # Name from a labelled-by relation, which readers use when the name is empty.
    try:
        for r in n.get_relation_set():
            if r.get_relation_type() == Atspi.RelationType.LABELLED_BY and r.get_n_targets():
                return r.get_target(0).get_name() or ""
    except GLib.Error:
        pass
    return ""


def info(n):
    try:
        st = n.get_state_set()
        return {"role": n.get_role_name(), "name": n.get_name() or label_of(n), "showing": st.contains(Atspi.StateType.SHOWING), "description": n.get_description() or "",
                "focused": st.contains(Atspi.StateType.FOCUSED), "enabled": st.contains(Atspi.StateType.ENABLED),
                "checked": st.contains(Atspi.StateType.CHECKED) or st.contains(Atspi.StateType.PRESSED)}
    except GLib.Error:
        return {"role": "?", "name": "", "description": "", "focused": False, "enabled": False, "checked": False}


class App:
    def __init__(self, *args, size=None):
        env = dict(os.environ, QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1")
        self.t0 = time.time()
        self.proc = subprocess.Popen([APP, *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.win = ""
        for _ in range(100):
            self.win = xdo("search", "--name", "^Meownero Wallet —")
            if self.win:
                break
            time.sleep(0.05)
        self.mapped = time.time() - self.t0
        self.win = self.win.splitlines()[0] if self.win else ""
        pump(1.0)
        if size:
            xdo("windowsize", self.win, str(size[0]), str(size[1]))
            pump(0.5)
        xdo("windowmove", self.win, "0", "0")
        xdo("windowfocus", "--sync", self.win)
        pump(0.4)
        self.acc = None
        for _ in range(50):
            self.acc = find_app()
            if self.acc and self.main_frame() is not None:
                break
            pump(0.1)

    def nodes(self):
        return [info(n) for n in walk(self.acc)]

    def raw(self):
        return walk(self.acc)

    def main_frame(self):
        for i in range(self.acc.get_child_count()):
            f = self.acc.get_child_at_index(i)
            if f.get_name().startswith("Meownero Wallet —"):
                return f
        return None

    def fixtures(self):
        for i in range(self.acc.get_child_count()):
            f = self.acc.get_child_at_index(i)
            if f.get_name().startswith("Reviewer fixtures"):
                return f
        return None

    def focused(self):
        # Focus scopes up the chain also report FOCUSED; the focused control is the deepest one.
        found = (None, {"role": "", "name": "", "description": "", "checked": False, "enabled": False})
        for n in walk(self.main_frame()):
            i = info(n)
            if i["focused"]:
                found = (n, i)
        return found

    def dialogs(self):
        return [i["name"] for i in self.nodes() if i["role"] == "dialog" and i["showing"]]

    def names(self):
        return [i["name"] for i in self.nodes()]

    def press_fixture(self, name):
        for n in walk(self.fixtures()):
            if n.get_role_name() in ("push button", "toggle button") and n.get_name() == name:
                n.get_action_iface().do_action(0)
                pump(0.4)
                self.activate()
                return True
        return False

    def activate(self):
        # No window manager on the isolated display: focus the window, then click the
        # ribbon's static text (not a control) so Qt treats the main window as active.
        xdo("windowfocus", "--sync", self.win)
        xdo("mousemove", "--window", self.win, "420", "14", "click", "1")
        pump(0.3)

    def diagnostics(self):
        self.press_fixture("Refresh")
        for n in walk(self.fixtures()):
            if n.get_role_name() == "text":
                return Atspi.Text.get_text(n, 0, Atspi.Text.get_character_count(n))
        return ""

    def tab_to(self, name, limit=40, back=False):
        for _ in range(limit):
            _, i = self.focused()
            if i["name"] == name:
                return True
            key("shift+Tab" if back else "Tab", wait=0.15)
        return self.focused()[1]["name"] == name

    def quit(self):
        self.proc.terminate()
        try:
            out, _ = self.proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, _ = self.proc.communicate()
        return out


def ancestors(n):
    roles = []
    while n is not None:
        try:
            roles.append((n.get_role_name(), n.get_name()))
            n = n.get_parent()
        except GLib.Error:
            break
    return roles


def in_dialog(n, title):
    return any(r == "dialog" and nm == title for r, nm in ancestors(n))


def announced_since(t, text):
    return any(a["t"] >= t and text in a["text"] for a in ANNOUNCEMENTS)


# ---------------------------------------------------------------- journey A
def journey_create_backup_receive_restore():
    app = App("--start", "welcome", "--reviewer-fixtures")
    check("A0 app window mapped", bool(app.win), "%.3f s from launch" % app.mapped)
    names = app.names()
    check("A1 first run exposes no wallet pages", "Wallet sections" not in names and "Spendable now" not in " ".join(names))
    order = []
    for _ in range(5):
        key("Tab", wait=0.15)
        order.append(app.focused()[1]["name"])
    check("A2 Tab order on Welcome", order[:4] == ["What does this mean?", "Create a new wallet", "Restore from recovery words", "Open a wallet file"], json.dumps(order))
    app.tab_to("Create a new wallet")
    key("Return")
    _, f = app.focused()
    check("A3 navigation moves focus to the page heading", f["role"] == "heading" and f["name"] == "Name and protect this wallet", json.dumps(f))
    shot("a03-create-1")
    app.tab_to("Wallet name")
    key("ctrl+a")
    typ("Native QA")
    key("Tab")
    typ("passw0rd!")
    key("Tab")
    typ("different")
    t = time.time()
    key("Return", wait=0.6)
    _, f = app.focused()
    check("A4 mismatch error focuses the field and is linked", f["name"] == "Repeat password" and "don't match" in f["description"], json.dumps(f))
    check("A5 field error is announced", announced_since(t, "The passwords don't match."))
    shot("a05-create-1-error")
    key("ctrl+a")
    typ("passw0rd!")
    key("Return", wait=0.6)
    _, f = app.focused()
    check("A6 create-2 heading focused", f["name"] == "Write down your recovery words", json.dumps(f))
    names = app.names()
    check("A7 hidden recovery words are absent from the accessibility tree", not any(w in " ".join(names) for w in ("whisker", "verification")) and "Recovery words, hidden" in names)
    shot("a07-words-veiled")
    app.tab_to("Show words")
    key("Return", wait=0.6)
    names = app.names()
    check("A8 revealed words are exposed by position", "Word 1: whisker" in names and "Word 20: verification" in names)
    shot("a08-words-revealed")
    app.tab_to("Back")
    key("Return", wait=0.6)
    check("A9 leaving the words hides them again", not any("whisker" in n for n in app.names()))
    app.tab_to("Password")
    typ("passw0rd!")
    key("Tab")
    typ("passw0rd!")
    key("Return", wait=0.6)
    check("A10 words veiled again on return", "Recovery words, hidden" in app.names())
    app.tab_to("Show words")
    key("Return", wait=0.5)
    app.tab_to("I've written down all 25 words and the block number.")
    key("space")
    app.tab_to("Continue")
    key("Return", wait=0.6)
    _, f = app.focused()
    check("A11 word check heading focused", f["name"] == "Check your paper", json.dumps(f))
    # A wrong pick is marked and announced; then the right words.
    opts = [(i["role"], i["name"]) for i in app.nodes() if i["name"] in SAMPLE]
    print("DEBUG quiz options", opts)
    wrong = next(n for r, n in opts if n != "lantern")
    check("A11b quiz words are buttons, not check boxes", all(r in ("push button", "toggle button") for r, _ in opts), json.dumps(sorted(set(r for r, _ in opts))))
    app.tab_to(wrong)
    t = time.time()
    key("space", wait=0.5)
    check("A12 wrong word is announced", announced_since(t, "That isn't word 4. Check your paper."))
    shot("a12-quiz-wrong")
    for w in ("lantern", "marble", "meadow"):
        app.tab_to(w) or app.tab_to(w, back=True)
        key("space", wait=0.3)
    picked = app.focused()[1]
    check("A12b a picked word reports its pressed state", picked["name"] == "meadow" and picked["checked"], json.dumps(picked))
    app.tab_to("Finish")
    key("Return", wait=0.6)
    app.tab_to("Open wallet")
    key("Return", wait=0.8)
    _, f = app.focused()
    check("A13 new wallet opens on Overview heading", f["name"] == "Overview", json.dumps(f))
    names = app.names()
    check("A14 only the current page exists in the tree", "Overview" in names and "Your address" not in " ".join(names) and "Recovery words" not in names)
    shot("a14-overview-empty")
    key("ctrl+4", wait=0.6)
    _, f = app.focused()
    check("A15 Ctrl+4 reaches Receive heading", f["name"] == "Receive", json.dumps(f))
    check("A16 receive address is exposed exactly", RECEIVE in app.names())
    app.tab_to(RECEIVE)
    t = time.time()
    key("ctrl+c", wait=0.5)
    check("A17 copy shortcut on the focused address reports its result", announced_since(t, "Copied") or announced_since(t, "Couldn't copy"))
    shot("a17-receive")
    key("ctrl+6", wait=0.6)
    app.tab_to("Show recovery words")
    key("Return", wait=0.6)
    n, f = app.focused()
    check("A18 password dialog starts in its field", f["name"] == "Password" and in_dialog(n, "Enter your password"), json.dumps(f))
    typ("wrongpass")
    t = time.time()
    key("Return", wait=0.6)
    _, f = app.focused()
    check("A19 wrong password keeps words hidden and is announced", announced_since(t, "That password doesn't open this wallet.") and not any("whisker" in x for x in app.names()))
    typ("passw0rd!")
    key("Return", wait=0.8)
    names = app.names()
    check("A20 correct password reveals words in a named dialog", "Word 9: laboratory" in names)
    shot("a20-seed-dialog")
    key("Escape", wait=0.6)
    _, f = app.focused()
    check("A21 Escape hides words and returns focus to the opener", f["name"] == "Show recovery words" and not any("laboratory" in x for x in app.names()), json.dumps(f))
    key("ctrl+l", wait=0.6)
    _, f = app.focused()
    check("A22 Ctrl+L locks: unlock heading focused, no wallet pages", f["name"] == "Native QA is locked" and "Wallet sections" not in app.names(), json.dumps(f))
    key("ctrl+1", wait=0.5)
    check("A23 section shortcuts do nothing while locked", "Wallet sections" not in app.names())
    shot("a23-locked")
    app.tab_to("Password")
    typ("passw0rd!")
    key("Return", wait=0.8)
    check("A24 unlock returns to Overview", app.focused()[1]["name"] == "Overview")
    # Restore with typed sample words.
    key("ctrl+6", wait=0.6)
    app.tab_to("Create or restore another wallet")
    key("Return", wait=0.6)
    app.tab_to("Restore from recovery words")
    key("Return", wait=0.6)
    app.tab_to("Word 1")
    for i, w in enumerate(SAMPLE[:24]):
        typ(w)
        key("Tab", wait=0.05)
    t = time.time()
    app.tab_to("Continue")
    key("Return", wait=0.6)
    n, f = app.focused()
    check("A25 missing word: focus moves to the first empty box", f["name"] == "Word 25" and "25 words" in f["description"], json.dumps(f))
    check("A26 restore error announced", announced_since(t, "You've entered 24"))
    shot("a26-restore-missing")
    typ("tabby")
    key("Return", wait=0.6)
    _, f = app.focused()
    check("A27 restore-2 heading", f["name"] == "Where should the wallet start?", json.dumps(f))
    app.tab_to("Created at block (optional)")
    typ("99999")
    app.tab_to("Wallet name")
    key("ctrl+a")
    typ("Restored QA")
    key("Tab")
    typ("correct horse")
    t = time.time()
    key("Return", wait=0.6)
    _, f = app.focused()
    check("A28 future block refused and focused", f["name"] == "Created at block (optional)" and "in the future" in f["description"], json.dumps(f))
    key("ctrl+a")
    typ("1203")
    app.tab_to("New password for this computer")
    typ("correct horse")
    key("Return", wait=0.4)
    pump(3.0)
    names = app.names()
    check("A29 restore finishes with the scanned result", "Wallet restored" in names and any("Found 4 payments" in x for x in names))
    shot("a29-restored")
    app.tab_to("Open wallet")
    key("Return", wait=0.8)
    check("A30 restored wallet opens", app.focused()[1]["name"] == "Overview" and "Restored QA" in app.names())
    out = app.quit()
    with open(os.path.join(OUT, "raw", "journey-a-app.log"), "w") as f:
        f.write(out)


# ---------------------------------------------------------------- journey B
def fill_send(app, amount):
    app.tab_to("Test wallet B")
    key("space", wait=0.3)
    app.tab_to("Amount in MEOW")
    key("ctrl+a")
    typ(amount)


def journey_send_review_unknown_consent():
    app = App("--start", "overview", "--reviewer-fixtures")
    rm0 = app.diagnostics()
    check("B0 reduced motion off under the stub portal default", "reduced_motion=0" in rm0, rm0.replace("\n", "; "))
    key("ctrl+3", wait=0.6)
    check("B1 Ctrl+3 reaches Send heading", app.focused()[1]["name"] == "Send")
    fill_send(app, "0,5")
    key("Return", wait=0.5)
    _, f = app.focused()
    check("B2 comma refused with a message, focus on amount", f["name"] == "Amount in MEOW" and "Use only digits" in f["description"], json.dumps(f))
    key("ctrl+a")
    typ("0.0000000000015")
    key("Return", wait=0.5)
    _, f = app.focused()
    check("B3 13 decimals refused, never rounded", "This amount has 13" in f["description"], json.dumps(f))
    shot("b03-13dp")
    key("ctrl+a")
    typ("2.5")
    t = time.time()
    key("Return", wait=0.2)
    check("B4 preparing announced", announced_since(t, "Preparing the payment."))
    pump(1.0)
    n, f = app.focused()
    check("B5 review dialog opens on its confirm button", f["name"] == "Send 2.5 MEOW" and in_dialog(n, "Review payment"), json.dumps(f))
    check("B6 review shows exact prepared values", any("Total: 2.50006152 MEOW" in x for x in app.names()) and any("Network fee: 0.00006152 MEOW" in x for x in app.names()))
    shot("b06-review")
    trapped = True
    seen = []
    for _ in range(6):
        key("Tab", wait=0.15)
        n, f = app.focused()
        seen.append(f["name"])
        trapped = trapped and n is not None and in_dialog(n, "Review payment")
    check("B7 Tab stays inside the dialog", trapped, json.dumps(seen))
    key("Escape", wait=0.6)
    _, f = app.focused()
    check("B8 Escape discards review and restores focus", f["name"] == "Review payment" and "Review payment" not in app.dialogs(), json.dumps(f))
    # Stale review: node becomes unreachable while the review is open.
    key("Return", wait=1.2)
    app.press_fixture("Node unreachable")
    shot("b09-node-lost")
    dialogs = app.dialogs()
    check("B9 node loss closes the open review", "Review payment" not in dialogs, json.dumps(dialogs))
    app.press_fixture("Synced")
    diag = app.diagnostics()
    check("B10 no submission happened after the stale review", "history_rows=4" in diag, diag.replace("\n", "; "))
    # Leaving Send while preparing discards it; the form keeps what was typed.
    key("ctrl+3", wait=0.4)
    app.tab_to("Review payment")
    key("Return", wait=0.1)
    key("ctrl+1", wait=1.2)
    shot("b11-left-send")
    print("DEBUG b11 focused", app.focused()[1])
    dialogs = app.dialogs()
    check("B11 a late prepare reply cannot open review over another page", not dialogs and app.focused()[1]["name"] == "Overview", json.dumps(dialogs))
    key("ctrl+3", wait=0.5)
    amount = next((n for n in app.raw() if n.get_name() == "Amount in MEOW"), None)
    txt = Atspi.Text.get_text(amount, 0, Atspi.Text.get_character_count(amount)) if amount else ""
    check("B12 form keeps what was typed", txt == "2.5", txt)
    # Confirm the exact payment.
    app.tab_to("Review payment")
    key("Return", wait=1.2)
    t = time.time()
    key("Return", wait=0.3)
    check("B13 submitting announced", announced_since(t, "Submitting the payment to your node."))
    pump(1.8)
    _, f = app.focused()
    check("B14 Sent: heading focused and outcome announced", f["name"] == "Sent" and announced_since(t, "Sent. Submitted to your node"), json.dumps(f))
    check("B15 change explained on Sent", any("spendable dropped by more than you sent" in x for x in app.names()))
    shot("b15-sent")
    # Unknown submission.
    app.press_fixture("Connection drops")
    app.press_fixture("Not sent")
    app.tab_to("Send another")
    key("Return", wait=0.5)
    fill_send(app, "1.25")
    key("Return", wait=1.2)
    t = time.time()
    key("Return", wait=0.3)
    pump(1.8)
    _, f = app.focused()
    check("B16 dropped submission is 'Submission status unknown'", f["name"] == "Submission status unknown" and announced_since(t, "Submission status unknown."), json.dumps(f))
    shot("b16-unknown")
    key("ctrl+3", wait=0.6)
    rb = next((i for i in app.nodes() if i["name"] == "Review payment" and i["role"] == "push button"), None)
    check("B17 another payment is blocked while unknown", rb is not None and not rb["enabled"])
    app.press_fixture("Add 1 block")
    check("B18 a new block without it proves nothing", any("Status unknown" in x for x in app.names()) or "One payment's submission status is unknown." in app.names())
    app.tab_to("Check payment")
    key("Return", wait=0.6)
    n, f = app.focused()
    check("B19 detail dialog opens", in_dialog(n, "Submission status unknown"), json.dumps(f))
    shot("b19-unknown-detail")
    app.tab_to("Check with node")
    t = time.time()
    key("Return", wait=0.3)
    pump(1.2)
    check("B20 absence proof resolves to not sent, announced", announced_since(t, "Not sent: your node never received this payment"))
    rb = next((i for i in app.nodes() if i["name"] == "Review payment" and i["role"] == "push button"), None)
    check("B21 sending is available again", rb is not None and rb["enabled"])
    # Consent at the minimum window size on the testnet design preview.
    xdo("windowsize", app.win, "880", "600")
    pump(0.6)
    app.press_fixture("Testnet (design preview)")
    key("ctrl+5", wait=0.6)
    app.tab_to("My own node on this computer")
    key("Down", wait=0.4)
    _, f = app.focused()
    status = next((x for x in app.names() if x.startswith("Status: ")), "")
    check("B22 arrow key picks but changes nothing", f["name"] == "Someone else's node" and f["checked"] and status == "Status: Connected and synced", json.dumps(f) + " " + status)
    app.tab_to("Connect to someone else's node…")
    key("Return", wait=0.6)
    n, f = app.focused()
    check("B23 consent dialog starts on Keep current node, described by the exposure", f["name"] == "Keep current node" and f["description"] == EXPOSURE and in_dialog(n, "Connect to someone else's node?"), json.dumps(f))
    frame = app.main_frame().get_component_iface().get_extents(Atspi.CoordType.SCREEN)
    expl = next((m for m in app.raw() if m.get_name() == EXPOSURE and m.get_role_name() in ("label", "static", "text")), None)
    btn = next((m for m in app.raw() if m.get_name() == "Connect to someone else's node" and m.get_role_name() == "push button"), None)
    if expl and btn:
        e = expl.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        b = btn.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        inside = e.x >= frame.x and e.y >= frame.y and e.x + e.width <= frame.x + frame.width and e.y + e.height <= frame.y + frame.height
        check("B24 at 880x600 the whole explanation is inside the window, above Connect",
              inside and e.y + e.height <= b.y,
              "window %dx%d+%d+%d; explanation %dx%d+%d+%d; connect y=%d" % (frame.width, frame.height, frame.x, frame.y, e.width, e.height, e.x, e.y, b.y))
    else:
        print("DEBUG exposure nodes:", [(m.get_role_name(), m.get_name()[:30]) for m in app.raw() if "untrusted node" in (m.get_name() or "")])
        check("B24 at 880x600 the whole explanation is inside the window, above Connect", False, "nodes not found")
    shot("b24-consent-880x600", "880x600")
    key("Escape", wait=0.6)
    _, f = app.focused()
    status = next((x for x in app.names() if x.startswith("Status: ")), "")
    check("B25 Escape changes nothing and returns focus to Connect", f["name"] == "Connect to someone else's node…" and status == "Status: Connected and synced", json.dumps(f))
    key("Return", wait=0.6)
    app.press_fixture("Local regtest")
    dialogs = app.dialogs()
    status = next((x for x in app.names() if x.startswith("Status: ")), "")
    check("B26 network change closes stale consent and connects nothing", "Connect to someone else's node?" not in dialogs and status == "Status: Connected and synced", json.dumps(dialogs) + " " + status)
    app.press_fixture("Testnet (design preview)")
    key("ctrl+5", wait=0.5)
    app.tab_to("My own node on this computer")
    key("Down", wait=0.3)
    app.tab_to("Connect to someone else's node…")
    key("Return", wait=0.6)
    app.tab_to("Connect to someone else's node")
    t = time.time()
    key("Return", wait=0.6)
    status = next((x for x in app.names() if x.startswith("Trust: ")), "")
    check("B27 explicit consent connects and is announced", status == "Trust: Untrusted, by your choice" and announced_since(t, "Using someone else's node"), status)
    shot("b27-remote-connected", "880x600")
    # Reduced motion follows the portal preference.
    os.kill(PORTAL_PID, signal.SIGUSR1)
    pump(1.0)
    rm1 = app.diagnostics()
    check("B28 reduced motion follows the system preference change", "reduced_motion=1" in rm1, open(PORTAL_STATUS).read().strip() + "; " + rm1.replace("\n", "; "))
    os.kill(PORTAL_PID, signal.SIGUSR1)
    out = app.quit()
    with open(os.path.join(OUT, "raw", "journey-b-app.log"), "w") as f:
        f.write(out)


if __name__ == "__main__":
    only = os.environ.get("JOURNEY", "AB")
    for tag, fn in (("A", journey_create_backup_receive_restore), ("B", journey_send_review_unknown_consent)):
        if tag not in only:
            continue
        try:
            fn()
        except Exception as exc:  # keep partial results
            check(fn.__name__ + " raised", False, repr(exc))
    with open(os.path.join(OUT, "raw", "journey-results.json"), "w") as f:
        json.dump({"results": RESULTS, "announcements": ANNOUNCEMENTS}, f, indent=1)
    failed = [r for r in RESULTS if not r["pass"]]
    print("TOTAL %d checks, %d failed" % (len(RESULTS), len(failed)))
