// SPDX-License-Identifier: GPL-3.0-or-later
#include "launcher.h"
#include "folderopener.h"
#include <QQmlExtensionPlugin>
#include <qqml.h>

class MonetLauncherPlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override {
        qmlRegisterType<Launcher>(uri, 1, 0, "Launcher");
        qmlRegisterType<FolderOpener>(uri, 1, 0, "FolderOpener");
    }
};
#include "plugin.moc"
