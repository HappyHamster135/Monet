// SPDX-License-Identifier: GPL-3.0-or-later
#include <plugin.h>
#include <workspace.h>
#include <window.h>
#include <input.h>
#include <keyboard_input.h>
#include <xkb.h>
#include <core/inputdevice.h>
#include <wayland_server.h>
#include <wayland/display.h>
#include <wayland/seat.h>
#include <KGlobalAccel>
#include <KLocalizedString>
#include <QAction>
#include <QProcess>
#include <QSet>
#include <QPointer>
#include <QTimer>
#include <main.h>
#include <inputmethod.h>
#include <wayland/surface.h>
#include <wayland/textinput_v2.h>
#include <wayland/textinput_v3.h>
#include <xkbcommon/xkbcommon.h>

using namespace KWin;

class PlainPaste final : public Plugin
{
    Q_OBJECT
public:
    PlainPaste()
    {
        auto *action = new QAction(i18nd("monet", "Paste as plain text"), this);
        action->setObjectName(QStringLiteral("Monet Paste as Plain Text"));
        action->setAutoRepeat(false);
        KGlobalAccel::setGlobalShortcut(action, QKeySequence(Qt::META | Qt::CTRL | Qt::Key_V));
        connect(action, &QAction::triggered, this, &PlainPaste::paste);
        connect(&helper, &QProcess::finished, this, &PlainPaste::finish);
        deliveryTimer.setSingleShot(true);
        connect(&deliveryTimer, &QTimer::timeout, this, &PlainPaste::resumeQueue);
    }

private:
    static Window *focusedWindow()
    {
        auto *server = waylandServer();
        auto *w = workspace()->activeWindow();
        if (!server || server->isScreenLocked() || !w || w->isDeleted() || w->isLockScreen()
            || !(w->isNormalWindow() || w->isDialog()) || !w->surface()
            || server->seat()->focusedKeyboardSurface() != w->surface()) {
            return nullptr;
        }
        return w;
    }

    static bool canCommit(Window *window)
    {
        auto *seat = waylandServer()->seat();
        return kwinApp()->inputMethod() && seat->focusedTextInputSurface() == window->surface()
            && (seat->textInputV2()->isEnabled() || seat->textInputV3()->isEnabled());
    }

    static void sendPasteKey(bool matchStyle)
    {
        auto *server = waylandServer();
        auto *seat = server->seat();
        if (!seat->selection() || !seat->keyboard()) {
            return;
        }
        auto *xkb = input()->keyboard()->xkb();
        const auto key = xkb->keycodeFromKeysym(XKB_KEY_v);
        if (!key || !xkb->keymap()) {
            return;
        }
        const auto ctrl = xkb_keymap_mod_get_index(xkb->keymap(), XKB_MOD_NAME_CTRL);
        const auto shift = xkb_keymap_mod_get_index(xkb->keymap(), XKB_MOD_NAME_SHIFT);
        if (ctrl >= 32 || shift >= 32) {
            return;
        }
        seat->notifyKeyboardModifiers((1u << ctrl) | (matchStyle ? 1u << shift : 0),
                                     0, 0, xkb->currentLayout());
        seat->notifyKeyboardKey(key->keyCode, KeyboardKeyState::Pressed, server->display()->nextSerial());
        seat->notifyKeyboardKey(key->keyCode, KeyboardKeyState::Released, server->display()->nextSerial());
        xkb->forwardModifiers();
    }

    void paste()
    {
        auto *window = focusedWindow();
        if (!window) {
            return;
        }
        // Browsers implement this command in the editor, including web page
        // paste events, undo, and the sandboxed content process. Konsole handles
        // multiline confirmation and bracketed paste through its own shortcut.
        static const QSet<QString> native = {
            QStringLiteral("zen"), QStringLiteral("app.zen_browser.zen"),
            QStringLiteral("firefox"), QStringLiteral("org.mozilla.firefox"),
            QStringLiteral("chromium"), QStringLiteral("org.chromium.chromium"),
            QStringLiteral("google-chrome"), QStringLiteral("com.google.chrome"),
            QStringLiteral("brave-browser"), QStringLiteral("com.brave.browser"),
            QStringLiteral("microsoft-edge"), QStringLiteral("com.microsoft.edge"),
            QStringLiteral("konsole"), QStringLiteral("org.kde.konsole"),
        };
        const auto desktopId = window->desktopFileName().toLower();
        if (native.contains(desktopId) || native.contains(window->resourceClass().toLower())) {
            sendPasteKey(true);
            return;
        }

        if (delivery || helper.state() != QProcess::NotRunning) {
            if (queued != window) {
                queued = window;
                waiting = 0;
            }
            ++waiting;
            return;
        }
        if (window->pid() <= 0) {
            return;
        }
        target = window;
        watch = std::make_unique<QObject>();
        auto *seat = waylandServer()->seat();
        initialSelection = seat->selection();
        const bool commit = canCommit(window);
        auto cancel = [this] {
            if (target && target == queued) {
                waiting = 0;
                queued.clear();
            }
            target.clear();
            helper.closeWriteChannel();
        };
        connect(seat, &SeatInterface::focusedKeyboardSurfaceAboutToChange, watch.get(), cancel);
        connect(seat, &SeatInterface::selectionChanged, watch.get(), cancel);
        if (commit) {
            connect(seat, &SeatInterface::focusedTextInputSurfaceChanged, watch.get(), cancel);
            connect(seat->textInputV2(), &TextInputV2Interface::enabledChanged, watch.get(), cancel);
            connect(seat->textInputV3(), &TextInputV3Interface::enabledChanged, watch.get(), cancel);
            connect(seat->textInputV2(), &TextInputV2Interface::surroundingTextChanged, watch.get(), cancel);
            connect(seat->textInputV3(), &TextInputV3Interface::surroundingTextChanged, watch.get(), cancel);
        }
        helper.start(QStringLiteral("/usr/libexec/monet-utilities"), {
            QStringLiteral("paste-plain"), QString::number(window->pid()),
            commit ? QStringLiteral("commit") : QStringLiteral("edit")
        });
    }

    void awaitDelivery()
    {
        // Keyboard and input-method events reach the app asynchronously. Wait
        // for its updated editor state before snapshotting the next selection.
        // Some clients do not use text-input or acknowledge an empty paste.
        delivery = std::make_unique<QObject>();
        deliveryTimer.start(350);
        auto *seat = waylandServer()->seat();
        auto acknowledged = [this] { deliveryTimer.start(0); };
        if (canCommit(target)) {
            connect(seat->textInputV2(), &TextInputV2Interface::surroundingTextChanged, delivery.get(), acknowledged);
            connect(seat->textInputV3(), &TextInputV3Interface::surroundingTextChanged, delivery.get(), acknowledged);
        }
        auto moved = [this] {
            waiting = 0;
            queued.clear();
            deliveryTimer.start(0);
        };
        connect(seat, &SeatInterface::focusedKeyboardSurfaceAboutToChange, delivery.get(), moved);
        connect(seat, &SeatInterface::selectionChanged, delivery.get(), moved);
    }

    void finish(int result, QProcess::ExitStatus status)
    {
        const auto bytes = helper.readAllStandardOutput();
        watch.reset();
        if (status == QProcess::NormalExit && target && target == focusedWindow()
            && initialSelection == waylandServer()->seat()->selection()) {
            // The helper only requests a native paste after checking the
            // destination's editable control and the clipboard formats.
            if (result == 23) {
                awaitDelivery();
                sendPasteKey(false);
                return;
            } else if (result == 24 && !bytes.isEmpty() && bytes.size() <= 3500 && canCommit(target)) {
                awaitDelivery();
                kwinApp()->inputMethod()->sendText(QString::fromUtf8(bytes));
                return;
            }
        }
        resumeQueue();
    }

    void resumeQueue()
    {
        delivery.reset();
        target.clear();
        if (waiting && queued && queued == focusedWindow()) {
            --waiting;
            paste();
        } else {
            waiting = 0;
            queued.clear();
        }
    }

    QPointer<Window> target, queued;
    int waiting = 0;
    AbstractDataSource *initialSelection = nullptr; // Identity only; owned by the seat.
    std::unique_ptr<QObject> watch, delivery;
    QTimer deliveryTimer;
    QProcess helper;
};

class PlainPasteFactory final : public PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "plainpaste.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<Plugin> create() const override { return std::make_unique<PlainPaste>(); }
};

#include "plainpaste.moc"
