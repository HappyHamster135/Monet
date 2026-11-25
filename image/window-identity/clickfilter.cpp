// SPDX-License-Identifier: GPL-3.0-or-later
#include "mouseexceptions.h"
#include <plugin.h>
#include <core/inputdevice.h>
#include <input.h>
#include <input_event.h>
#include <pointer_input.h>
#include <wayland_server.h>
#include <wayland/seat.h>
#include <window.h>
#include <workspace.h>
#include <QDBusConnection>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QSettings>
#include <algorithm>
#include <array>
#include <utility>
#include <linux/input-event-codes.h>

using namespace KWin;
using namespace std::chrono_literals;

namespace {
constexpr std::array buttons = {BTN_LEFT, BTN_RIGHT, BTN_MIDDLE};
constexpr std::array keys = {"primary", "secondary", "middle"};

bool isMouse(InputDevice *device)
{
    return device && device->isPointer() && !device->isTouchpad() && !device->isTouch()
        && !device->isTabletTool() && !device->isTabletPad();
}

QString modelKey(InputDevice *device)
{
    return QStringLiteral("%1:%2:%3").arg(device->vendor()).arg(device->product()).arg(device->name());
}

struct Button {
    bool forwardedDown = false;
    bool acceptedDown = false;
    bool discardedDown = false;
    bool armed = false;
    std::chrono::microseconds released{};
    QPointF position;
    Qt::KeyboardModifiers modifiers{};
    Qt::MouseButton logical{};
    QPointer<Window> window;
};
}

class ClickFilter final : public Plugin, public InputEventFilter
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.ExtraClicks1")
public:
    ClickFilter() : InputEventFilter(InputFilterOrder::ButtonRebind)
    {
        if (!waylandServer()) return;
        auto bus = QDBusConnection::sessionBus();
        bus.connect({}, "/org/monet/MouseEnhancements", "org.monet.MouseEnhancements", "Changed", this, SLOT(Reload()));
        bus.registerObject("/org/monet/ExtraClicks", this, QDBusConnection::ExportScriptableSlots | QDBusConnection::ExportScriptableSignals);
        connect(input(), &InputRedirection::deviceAdded, this, [this](InputDevice *d) {
            if (d->isPointer()) add(d);
            if (isMouse(d)) Q_EMIT ModelsChanged();
        });
        connect(input(), &InputRedirection::deviceRemoved, this, [this](InputDevice *d) {
            if (devices.remove(d)) updateDiscarded();
            if (isMouse(d)) Q_EMIT ModelsChanged();
        });
        connect(workspace(), &Workspace::windowActivated, this, [this](Window *active) {
            forgetClicks(active);
        });
        connect(waylandServer(), &WaylandServer::lockStateChanged, this, [this] { forgetClicks(); });
        Reload();
    }

public Q_SLOTS:
    Q_SCRIPTABLE QString Models() const
    {
        QJsonObject result;
        for (auto *d : input()->devices()) {
            if (isMouse(d)) result.insert(modelKey(d), d->name());
        }
        return QString::fromUtf8(QJsonDocument(result).toJson(QJsonDocument::Compact));
    }

    Q_SCRIPTABLE void Reload()
    {
        QSettings settings("Monet", "ExtraClicks");
        settings.sync();
        exceptions.reload();
        const bool enabled = settings.value("enabled", false).toBool();
        for (size_t i = 0; i < keys.size(); ++i)
            selected[i] = enabled && settings.value(keys[i], i == 0).toBool();
        interval = std::chrono::milliseconds(qBound(5, settings.value("interval", 25).toInt(), 100));
        model = settings.value("model").toString();
        forgetClicks();
        for (auto *d : input()->devices()) if (d->isPointer()) add(d);
        updateFilter();
    }

Q_SIGNALS:
    Q_SCRIPTABLE void ModelsChanged();

private:
    struct Mouse {
        bool enabled = false;
        std::array<Button, buttons.size()> buttonsState;
    };

    void add(InputDevice *d)
    {
        devices[d].enabled = isMouse(d) && (model.isEmpty() || model == modelKey(d));
    }

    void forgetClicks(Window *newFocus = nullptr)
    {
        for (auto &mouse : devices) {
            for (auto &b : mouse.buttonsState) {
                b.armed = false;
                if (!newFocus || b.window != newFocus) {
                    b.acceptedDown = false;
                    b.window.clear();
                }
                // A discarded press still owns its release across a settings
                // change or focus switch.
            }
        }
    }

    void updateFilter()
    {
        const bool wanted = std::ranges::any_of(selected, [](bool value) { return value; }) || (pendingMask | overlapMask) != Qt::NoButton;
        if (wanted == installed) return;
        installed = wanted;
        if (installed) input()->installInputEventFilter(this);
        else {
            input()->uninstallInputEventFilter(this);
            overlapMask = {};
            for (auto &mouse : devices)
                for (auto &b : mouse.buttonsState) b = {};
        }
    }

    void updateDiscarded()
    {
        Qt::MouseButtons forwarded;
        pendingMask = {};
        for (const auto &mouse : std::as_const(devices)) {
            for (const auto &b : mouse.buttonsState) {
                if (b.discardedDown) pendingMask |= b.logical;
                if (b.forwardedDown) forwarded |= b.logical;
            }
        }
        // Two independent pointing devices can hold the same logical button.
        // Keep the accepted drag visible until its own physical release.
        overlapMask = (overlapMask | pendingMask) & forwarded;
        if ((pendingMask | overlapMask) == Qt::NoButton && std::ranges::none_of(selected, [](bool value) { return value; }))
            QMetaObject::invokeMethod(this, &ClickFilter::updateFilter, Qt::QueuedConnection);
    }

    void correctButtons(Qt::MouseButtons &value) const
    {
        value = (value & ~pendingMask) | overlapMask;
    }

    bool forward(PointerButtonEvent *event, Button &b, bool pressed)
    {
        b.forwardedDown = pressed;
        b.logical = event->button;
        if ((pendingMask | overlapMask) & event->button) updateDiscarded();
        correctButtons(event->buttons);
        return false;
    }

    bool pointerButton(PointerButtonEvent *event) override
    {
        const auto match = std::ranges::find(buttons, event->nativeButton);
        if (match == buttons.end()) {
            correctButtons(event->buttons);
            return false;
        }
        const size_t i = match - buttons.begin();
        const bool pressed = event->state == PointerButtonState::Pressed;
        auto mouse = devices.find(event->device);
        // libinput merges overlapping holds into seat-wide edges. A release
        // from another physical device can finish the original mouse's press.
        if (!pressed && (mouse == devices.end() || (!mouse->buttonsState[i].forwardedDown && !mouse->buttonsState[i].discardedDown))
            && event->device && !event->device->sysPath().isEmpty()) {
            for (auto it = devices.begin(); it != devices.end(); ++it) {
                if ((it->buttonsState[i].discardedDown || it->buttonsState[i].forwardedDown) && !it.key()->sysPath().isEmpty()) {
                    it->buttonsState[i].acceptedDown = false;
                    mouse = it;
                    break;
                }
            }
        }
        if (mouse == devices.end()) {
            correctButtons(event->buttons);
            return false;
        }
        auto &b = mouse->buttonsState[i];
        if (b.discardedDown) {
            if (!pressed) { b.discardedDown = false; updateDiscarded(); }
            return true;
        }
        if (!selected[i] || !mouse->enabled) return forward(event, b, pressed);
        auto *target = input()->pointer()->hover();
        if (!target || waylandServer()->isScreenLocked() || waylandServer()->seat()->isDrag()
            || input()->isSelectingWindow() || exceptions.matches(target)) {
            b.armed = b.acceptedDown = false;
            return forward(event, b, pressed);
        }
        if (!pressed) {
            b.armed = b.acceptedDown && b.window == target && (event->position - b.position).manhattanLength() <= 3;
            b.acceptedDown = false;
            b.position = event->position;
            b.modifiers = event->modifiers;
            b.released = event->timestamp;
            return forward(event, b, false);
        }
        if (b.acceptedDown) return true; // Keep the eventual release for the original press.
        correctButtons(event->buttons);
        const auto elapsed = event->timestamp - b.released;
        const bool repeat = b.armed && target == workspace()->activeWindow() && elapsed >= 0us && elapsed < interval && b.window == target
            && (event->position - b.position).manhattanLength() <= 3 && event->modifiers == b.modifiers
            && !(event->buttons & ~event->button);
        if (repeat) {
            b.discardedDown = true;
            b.logical = event->button;
            updateDiscarded();
            return true;
        }
        b.armed = false;
        b.acceptedDown = true;
        b.position = event->position;
        b.window = target;
        return forward(event, b, true);
    }

    bool pointerMotion(PointerMotionEvent *event) override
    {
        // Wayland sends motion separately. Internal and decorated windows
        // also receive a Qt buttons mask; a discarded click must not drag.
        correctButtons(event->buttons);
        for (auto &mouse : devices) {
            for (auto &b : mouse.buttonsState) {
                if ((b.armed || b.acceptedDown) && (event->position - b.position).manhattanLength() > 3)
                    b.armed = b.acceptedDown = false;
            }
        }
        return false;
    }

    MouseExceptions exceptions;
    QHash<InputDevice *, Mouse> devices;
    std::array<bool, buttons.size()> selected{};
    QString model;
    std::chrono::milliseconds interval{25};
    Qt::MouseButtons pendingMask{};
    Qt::MouseButtons overlapMask{};
    bool installed = false;
};

class ClickFactory final : public PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "clickfilter.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<Plugin> create() const override { return std::make_unique<ClickFilter>(); }
};

#include "clickfilter.moc"
