#!/usr/bin/python3
"""Apply Monet's small notification policy to the matching Plasma source tree.

Unexpected upstream structure fails the build instead of silently dropping a fix.
The native applet identity and C++ implementation stay unchanged.
"""
from pathlib import Path
import shutil
import sys


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"Expected one supported notification hook in {path.name}: {old!r}")
    path.write_text(text.replace(old, new))


def apply(source):
    applet = source / "applets/notifications"
    globals_qml = applet / "global/Globals.qml"
    replace_once(globals_qml, "    property NotificationManager.Notifications popupNotificationsModel:",
        "    property MonetNotificationPolicy monetPolicy: MonetNotificationPolicy {\n"
        "        notificationSettings: globals.notificationSettings\n    }\n\n"
        "    property NotificationManager.Notifications popupNotificationsModel:")
    replace_once(globals_qml,
        "onCloseClicked: globals.popupNotificationsModel.close(globals.popupNotificationsModel.index(index, 0))",
        "onCloseClicked: {\n"
        "                    if (globals.monetPolicy.keepPopup(popup.type, popup.urgency, popup.isTransient)) {\n"
        "                        model.expired = true;\n"
        "                    } else {\n"
        "                        globals.popupNotificationsModel.close(globals.popupNotificationsModel.index(index, 0));\n"
        "                    }\n                }")
    replace_once(globals_qml, "                closable: popup.closable",
        "                closable: popup.closable\n"
        "                closeButtonToolTip: globals.monetPolicy.keepPopup(popup.type, popup.urgency, popup.isTransient)\n"
        "                    ? globals.monetPolicy.dismissLabel : \"\"")
    interface = applet / "components/ModelInterface.qml"
    if "property string closeButtonToolTip" not in interface.read_text():
        replace_once(interface, "    property bool closable", "    property bool closable\n    property string closeButtonToolTip")
    # HeadingButtons already reads this optional label in Plasma 6.7.
    if "headingButtons.modelInterface.closeButtonToolTip" not in (applet / "components/HeadingButtons.qml").read_text():
        raise ValueError("Unsupported notification close-button interface")
    replace_once(applet / "CMakeLists.txt", "    main.qml\n", "    main.qml\n    MonetNotificationPolicy.qml\n")
    shutil.copy2(Path(__file__).with_name("MonetNotificationPolicy.qml"), applet)


if __name__ == "__main__":
    apply(Path(sys.argv[1]))
