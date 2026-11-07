// SPDX-License-Identifier: GPL-3.0-or-later
#include "activity.h"
#include <QQmlExtensionPlugin>
#include <qqml.h>

class MonetActivityPlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override { qmlRegisterType<Activity>(uri, 1, 0, "Activity"); }
};
#include "plugin.moc"
