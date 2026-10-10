"""Minimal org.freedesktop.portal.Settings for an isolated D-Bus session.

Qt 6.12's GNOME theme reads the reduced-motion preference through this portal
(org.gnome.desktop.interface enable-animations, org.freedesktop.appearance
reduced-motion). Running it on a private session bus lets the harness flip the
"system" preference without touching the user's live desktop settings.
Toggle with SIGUSR1; the current value is written to the path in argv[1].
"""
import signal
import sys

from gi.repository import Gio, GLib

XML = """
<node>
  <interface name="org.freedesktop.portal.Settings">
    <method name="ReadAll"><arg type="as" name="namespaces" direction="in"/><arg type="a{sa{sv}}" name="value" direction="out"/></method>
    <method name="Read"><arg type="s" name="namespace" direction="in"/><arg type="s" name="key" direction="in"/><arg type="v" name="value" direction="out"/></method>
    <method name="ReadOne"><arg type="s" name="namespace" direction="in"/><arg type="s" name="key" direction="in"/><arg type="v" name="value" direction="out"/></method>
    <signal name="SettingChanged"><arg type="s" name="namespace"/><arg type="s" name="key"/><arg type="v" name="value"/></signal>
    <property name="version" type="u" access="read"/>
  </interface>
</node>
"""
state = {"reduced": False}
status_path = sys.argv[1]


def values():
    return {
        "org.gnome.desktop.interface": {"enable-animations": GLib.Variant("b", not state["reduced"]),
                                        "color-scheme": GLib.Variant("s", "default")},
        "org.freedesktop.appearance": {"reduced-motion": GLib.Variant("u", 1 if state["reduced"] else 0),
                                       "color-scheme": GLib.Variant("u", 0)},
    }


def write_status():
    with open(status_path, "w") as f:
        f.write("reduced=%d\n" % state["reduced"])


def on_call(conn, sender, path, iface, method, params, inv):
    v = values()
    if method == "ReadAll":
        wanted = params.unpack()[0]
        out = {ns: kv for ns, kv in v.items() if not wanted or ns in wanted}
        inv.return_value(GLib.Variant("(a{sa{sv}})", (out,)))
        return
    ns, key = params.unpack()
    if ns in v and key in v[ns]:
        val = v[ns][key]
        inv.return_value(GLib.Variant("(v)", (GLib.Variant("v", val) if method == "Read" else val,)))
    else:
        inv.return_dbus_error("org.freedesktop.portal.Error.NotFound", "Requested setting not found")


def on_get(conn, sender, path, iface, prop):
    return GLib.Variant("u", 2)


conn = None


def toggle(*_):
    state["reduced"] = not state["reduced"]
    write_status()
    for ns, key in (("org.gnome.desktop.interface", "enable-animations"), ("org.freedesktop.appearance", "reduced-motion")):
        conn.emit_signal(None, "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings", "SettingChanged",
                         GLib.Variant("(ssv)", (ns, key, values()[ns][key])))
    return True


def on_bus(c, name):
    global conn
    conn = c
    node = Gio.DBusNodeInfo.new_for_xml(XML)
    c.register_object("/org/freedesktop/portal/desktop", node.interfaces[0], on_call, on_get, None)


write_status()
Gio.bus_own_name(Gio.BusType.SESSION, "org.freedesktop.portal.Desktop", Gio.BusNameOwnerFlags.NONE, on_bus, None, None)
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, toggle)
GLib.MainLoop().run()
