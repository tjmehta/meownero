#!/usr/bin/python3
"""Real XTest/AT-SPI checks using the accepted isolated native journey helpers."""
import importlib.util
import json
import os
import pathlib
import sys

repo = pathlib.Path(__file__).resolve().parents[2]
path = repo / "research/evidence/native-wallet-tjs2018-2026-10-10/harness/journey.py"
spec = importlib.util.spec_from_file_location("accepted_journey", path)
j = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)
app = None
try:
    app = j.App("--start", "overview", "--reviewer-fixtures")
    j.key("ctrl+2", wait=0.6)
    names = [i["name"] for i in app.nodes() if i["role"] == "push button" and i["name"].startswith("Sent, ")]
    j.check("H1 outgoing row has full accessible amount and status", len(names) == 1 and "2.5 MEOW" in names[0] and "Waiting to confirm" in names[0], json.dumps(names))
    name = names[0]
    j.check("H2 keyboard reaches a payment row", app.tab_to(name))
    j.key("Return")
    j.check("H3 keyboard opens details", "Sent" in app.dialogs())
    app.press_fixture("Add 1 block")
    j.pump(0.5)
    j.key("Escape")
    focus = app.focused()[1]
    j.check("H4 status refresh preserves named row opener focus", focus["role"] == "push button" and focus["name"].startswith("Sent, ") and "1 of 10 confirmations" in focus["name"], json.dumps(focus))
    j.shot("h04-row-focus-after-status-refresh")
    j.check("H5 pointer opens the same payment", j.press_by_pointer(app, focus["name"]))
    j.pump(0.4)
    status = [n.get_name() for n in app.raw() if j.in_dialog(n, "Sent") and n.get_name().startswith("Status:")]
    j.check("H6 pointer detail has same title and status", "Sent" in app.dialogs() and "Status: 1 of 10 confirmations" in status, json.dumps(status))
    j.key("Escape")
    j.check("H7 keyboard reaches digit toggle", app.tab_to("Show every digit", back=True))
    j.key("space")
    focus = app.focused()[1]
    j.check("H8 digit toggle keeps its focus and pressed state", focus["name"] == "Show every digit" and focus["checked"], json.dumps(focus))
    j.check("H9 Activity keeps four named rows after toggle", len([i for i in app.nodes() if i["role"] == "push button" and any(i["name"].startswith(p) for p in ["Sent, ", "Received, ", "Mined "])]) == 4)
    j.shot("h09-activity-exact")
    j.key("ctrl+1")
    balance = next(i["name"] for i in app.nodes() if i["name"].startswith("Spendable now:") and i["role"] == "push button")
    j.check("H10 keyboard reaches Overview balance", app.tab_to(balance))
    j.key("space")
    focus = app.focused()[1]
    j.check("H11 balance toggle keeps accessible focus", focus["name"].startswith("Spendable now:") and focus["role"] == "push button", json.dumps(focus))
except Exception as exc:
    j.check("history focus journey raised", False, repr(exc))
finally:
    if app:
        pathlib.Path(j.OUT, "raw/history-focus-app.log").write_text(app.quit())
    pathlib.Path(j.OUT, "raw/history-focus-results.json").write_text(json.dumps(j.RESULTS, indent=2))
sys.exit(1 if any(not r["pass"] for r in j.RESULTS) else 0)
