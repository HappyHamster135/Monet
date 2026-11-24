// SPDX-License-Identifier: GPL-3.0-or-later
#include <plugin.h>
#include <input.h>
#include <input_event.h>
#include <inputmethod.h>
#include <effect/effecthandler.h>
#include <keyboard_input.h>
#include <main.h>
#include <window.h>
#include <workspace.h>
#include <xkb.h>
#include <core/inputdevice.h>
#include <wayland_server.h>
#include <wayland/display.h>
#include <wayland/seat.h>
#include <wayland/inputmethod_v1.h>
#include <wayland/surface.h>
#include <KLocalizedString>
#include <KService>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QFileInfo>
#include <QKeySequence>
#include <QPointer>
#include <QSet>
#include <QSettings>
#include <QTimer>
#include <xkbcommon/xkbcommon.h>

using namespace KWin;

enum class Confirmation { Hold, Twice, Modifier };
enum class Scope { All, Selected, Except };

static QString appName(QString value)
{
    value = QFileInfo(value).fileName().toLower();
    if (value.endsWith(QLatin1String(".desktop"))) {
        value.chop(8);
    }
    return value;
}

struct Rule
{
    bool enabled;
    Confirmation mode;
    Scope scope;
    int holdMs;
    int doubleMs;
    Qt::KeyboardModifier extra;
    bool feedback;
    QSet<QString> apps;

    static Rule read(QSettings &settings, const QString &group)
    {
        settings.beginGroup(group);
        Rule r{};
        r.enabled = settings.value("enabled", false).toBool();
        const auto mode = settings.value("mode").toString();
        r.mode = mode == "twice" ? Confirmation::Twice : mode == "modifier" ? Confirmation::Modifier : Confirmation::Hold;
        const auto scope = settings.value("scope").toString();
        r.scope = scope == "selected" ? Scope::Selected : scope == "except" ? Scope::Except : Scope::All;
        const auto mod = settings.value("modifier").toString();
        r.extra = mod == "alt" ? Qt::AltModifier : mod == "meta" ? Qt::MetaModifier : Qt::ShiftModifier;
        r.holdMs = qBound(250, settings.value("holdMs", 800).toInt(), 2000);
        r.doubleMs = qBound(200, settings.value("doubleMs", 600).toInt(), 1500);
        r.feedback = settings.value("feedback", true).toBool();
        const auto ids = settings.value("apps").toStringList();
        for (const auto &id : ids) {
            r.apps.insert(appName(id));
            if (r.enabled && r.scope != Scope::All) {
                if (auto service = KService::serviceByStorageId(id)) {
                    r.apps.insert(appName(service->property<QString>("StartupWMClass")));
                }
            }
        }
        r.apps.remove(QString());
        settings.endGroup();
        return r;
    }

    bool includes(Window *w) const
    {
        if (scope == Scope::All) {
            return true;
        }
        const bool listed = apps.contains(appName(w->desktopFileName())) || apps.contains(appName(w->resourceClass()));
        return listed == (scope == Scope::Selected);
    }
};

class QuitGuard final : public Plugin, public InputEventFilter
{
    Q_OBJECT
public:
    QuitGuard()
        : InputEventFilter(InputFilterOrder::InputMethod)
    {
        if (!waylandServer()) {
            return;
        }
        hold.setSingleShot(true);
        hold.setTimerType(Qt::PreciseTimer);
        connect(&hold, &QTimer::timeout, this, [this] {
            if (target && target == focused() && input()->keyboardModifiers() == Qt::ControlModifier) {
                sendCommand(scan, false);
            }
            reset();
        });
        connect(waylandServer()->seat(), &SeatInterface::focusedKeyboardSurfaceAboutToChange, this, &QuitGuard::reset);
        connect(waylandServer(), &WaylandServer::lockStateChanged, this, &QuitGuard::reset);
        connect(input(), &InputRedirection::keyboardModifiersChanged, this, [this](Qt::KeyboardModifiers mods) {
            if (hold.isActive() && mods != Qt::ControlModifier) {
                reset();
            }
        });
        connect(input(), &InputRedirection::deviceRemoved, this, [this] {
            reset();
            swallowed.clear();
            updateFilter();
        });
        QDBusConnection::sessionBus().connect({}, "/org/monet/QuitProtection", "org.monet.QuitProtection",
                                              "Changed", this, SLOT(reload()));
        reload();
    }

private Q_SLOTS:
    void reload()
    {
        QSettings settings("Monet", "QuitProtection");
        settings.sync();
        quit = Rule::read(settings, "quit");
        close = Rule::read(settings, "close");
        reset();
        updateFilter();
    }

private:
    void updateFilter()
    {
        const bool needed = quit.enabled || close.enabled || !swallowed.isEmpty();
        if (needed != installed) {
            installed = needed;
            if (needed) {
                input()->installInputEventFilter(this);
            } else {
                input()->uninstallInputEventFilter(this);
            }
        }
    }

    static Window *focused()
    {
        auto *server = waylandServer();
        auto *w = workspace()->activeWindow();
        if (!w || w->isDeleted() || !w->surface() || !(w->isNormalWindow() || w->isDialog())
            || w->isLockScreen() || server->isScreenLocked() || server->isKeyboardShortcutsInhibited()
            || workspace()->globalShortcutsDisabled() || server->seat()->focusedKeyboardSurface() != w->surface()
            || input()->isSelectingWindow() || (effects && effects->hasKeyboardGrab())) {
            return nullptr;
        }
        return w;
    }

    // Deliver the confirmed physical Q or W once. The application handles its
    // own tabs, unsaved documents, and quit dialogs.
    static void sendCommand(quint32 code, bool stripModifier)
    {
        auto *server = waylandServer();
        auto *seat = server->seat();
        auto *xkb = input()->keyboard()->xkb();
        if (!seat->keyboard() || !xkb->keymap()) {
            return;
        }
        auto *im = kwinApp()->inputMethod();
        auto *grab = im ? im->keyboardGrab() : nullptr;
        if (im && !grab) {
            im->commitPendingText();
        }
        if (stripModifier) {
            const auto ctrl = xkb_keymap_mod_get_index(xkb->keymap(), XKB_MOD_NAME_CTRL);
            if (ctrl >= 32) {
                return;
            }
            if (grab) {
                grab->sendModifiers(server->display()->nextSerial(), 1u << ctrl, 0, 0, xkb->currentLayout());
            } else {
                seat->notifyKeyboardModifiers(1u << ctrl, 0, 0, xkb->currentLayout());
            }
        }
        for (auto state : {KeyboardKeyState::Pressed, KeyboardKeyState::Released}) {
            const auto serial = server->display()->nextSerial();
            if (grab) {
                grab->sendKey(serial, seat->timestamp().count(), code, state);
            } else {
                seat->notifyKeyboardKey(code, state, serial);
            }
        }
        if (stripModifier) {
            if (grab) {
                im->forwardModifiers(InputMethod::Force);
            } else {
                xkb->forwardModifiers();
            }
        }
    }

    static void hint(const Rule &rule, Qt::Key key)
    {
        if (!rule.feedback) {
            return;
        }
        Qt::KeyboardModifiers mods = Qt::ControlModifier;
        if (rule.mode == Confirmation::Modifier) {
            mods |= rule.extra;
        }
        auto keys = QKeySequence(QKeyCombination(mods, key)).toString(QKeySequence::NativeText);
        QString message;
        if (rule.mode == Confirmation::Hold) {
            message = i18nd("monet", "Hold %1 to confirm", keys);
        } else if (rule.mode == Confirmation::Twice) {
            message = i18nd("monet", "Press %1 again to confirm", keys);
        } else {
            message = i18nd("monet", "Press %1 to confirm", keys);
        }
        auto osd = QDBusMessage::createMethodCall("org.kde.plasmashell", "/org/kde/osdService",
                                                   "org.kde.osdService", "showText");
        osd << QStringLiteral("input-keyboard") << message;
        QDBusConnection::sessionBus().asyncCall(osd);
    }

    void reset()
    {
        hold.stop();
        target.clear();
        pending = Qt::Key_unknown;
    }

    bool keyboardKey(KeyboardKeyEvent *e) override
    {
        const quint32 code = e->nativeScanCode;
        if (e->state == KeyboardKeyState::Released) {
            if (!swallowed.remove(code)) {
                return false;
            }
            if (hold.isActive() && scan == code) {
                reset();
            }
            updateFilter();
            return true;
        }
        if (e->state == KeyboardKeyState::Repeated) {
            return swallowed.contains(code);
        }
        // A release inside a compositor grab may never reach this filter.
        swallowed.remove(code);
        if (!quit.enabled && !close.enabled) {
            updateFilter();
            return false;
        }
        if (e->key != Qt::Key_Q && e->key != Qt::Key_W) {
            if (target && e->key != Qt::Key_Control) {
                reset();
            }
            return false;
        }
        const Rule &rule = e->key == Qt::Key_Q ? quit : close;
        const auto mods = e->modifiers;
        const bool extra = rule.mode == Confirmation::Modifier && mods == (Qt::ControlModifier | rule.extra);
        auto *w = rule.enabled && (extra || mods == Qt::ControlModifier) ? focused() : nullptr;
        if (!w || !rule.includes(w)) {
            reset();
            return false;
        }
        swallowed.insert(code);
        input()->keyboard()->addFilteredKey(code);
        const bool twice = rule.mode == Confirmation::Twice && w == target && e->key == pending
            && e->timestamp >= first && e->timestamp - first <= std::chrono::milliseconds(rule.doubleMs);
        reset();
        if (twice || extra) {
            sendCommand(code, extra);
        } else {
            if (rule.mode != Confirmation::Modifier) {
                target = w;
                scan = code;
                pending = e->key;
                first = e->timestamp;
                if (rule.mode == Confirmation::Hold) {
                    hold.start(rule.holdMs);
                }
            }
            hint(rule, e->key);
        }
        return true;
    }

    Rule quit{}, close{};
    bool installed = false;
    QSet<quint32> swallowed;
    QTimer hold;
    QPointer<Window> target;
    Qt::Key pending = Qt::Key_unknown;
    quint32 scan = 0;
    std::chrono::microseconds first{};
};

class QuitGuardFactory final : public PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "quitguard.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<Plugin> create() const override { return std::make_unique<QuitGuard>(); }
};
#include "quitguard.moc"
