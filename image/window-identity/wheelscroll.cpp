// SPDX-License-Identifier: GPL-3.0-or-later
#include "mouseexceptions.h"
#include <plugin.h>
#include <input.h>
#include <input_event.h>
#include <keyboard_input.h>
#include <pointer_input.h>
#include <core/inputdevice.h>
#include <effect/effecthandler.h>
#include <wayland_server.h>
#include <wayland/seat.h>
#include <wayland/pointer.h>
#include <wayland/clientconnection.h>
#include <wayland-server-core.h>
#include <wayland-server-protocol.h>
#include <wayland/surface.h>
#include <window.h>
#include <xkb.h>
#include <xkbcommon/xkbcommon.h>
#include <QDBusConnection>
#include <QElapsedTimer>
#include <QPointer>
#include <QSettings>
#include <QTimer>
#include <climits>
#include <cstring>

using namespace KWin;

namespace {
// Positions are measured in high-resolution wheel units (120 per detent).
struct Glide
{
    qint64 distance = 0;
    qint64 sent = 0;
    qint64 start = 0;
    bool inverted = false;

    void add(qint64 delta, qint64 now, bool direction)
    {
        const qint64 left = distance - sent;
        distance = delta + ((left > 0) == (delta > 0) ? left : 0);
        sent = 0;
        start = now;
        inverted = direction;
    }

    qint64 advance(qint64 now, int duration, int quantum)
    {
        // Use elapsed time so a busy frame catches up without adding more timers.
        const double t = qBound(0., double(now - start + 12) / duration, 1.);
        const double tail = 1. - t;
        // X11 valuators represent fractions of a detent. Eighths of a
        // detent are exact in their binary representation. Flush any smaller
        // remainder on the final frame for high-resolution devices.
        const qint64 position = t == 1. ? distance : qRound64(distance * (1. - tail * tail * tail)) / quantum * quantum;
        const qint64 delta = position - sent;
        sent = position;
        return delta;
    }
};

// Older Wayland clients accumulate v120 down to whole wheel clicks in KWin.
bool supportsHighResolutionWheel(SurfaceInterface *surface)
{
    bool supported = false;
    wl_client_for_each_resource(surface->client()->client(), [](wl_resource *resource, void *result) {
        if (std::strcmp(wl_resource_get_class(resource), "wl_pointer") == 0) {
            *static_cast<bool *>(result) = wl_resource_get_version(resource) >= WL_POINTER_AXIS_VALUE120_SINCE_VERSION;
            return WL_ITERATOR_STOP;
        }
        return WL_ITERATOR_CONTINUE;
    }, &supported);
    return supported;
}

enum class Profile { System, Linear, Smooth };
}

class WheelScroll final : public Plugin, public InputEventFilter
{
    Q_OBJECT
public:
    WheelScroll()
        : InputEventFilter(InputFilterOrder::GlobalShortcut)
    {
        if (!waylandServer()) {
            return;
        }
        clock.start();
        frame.setTimerType(Qt::PreciseTimer);
        frame.setInterval(16);
        connect(&frame, &QTimer::timeout, this, &WheelScroll::animate);
        connect(input(), &InputRedirection::keyboardModifiersChanged, this, &WheelScroll::stop);
        connect(input(), &InputRedirection::pointerButtonStateChanged, this, &WheelScroll::stop);
        connect(input(), &InputRedirection::deviceRemoved, this, [this](InputDevice *removed) {
            if (device == removed) stop();
        });
        connect(waylandServer(), &WaylandServer::lockStateChanged, this, &WheelScroll::stop);
        QDBusConnection::sessionBus().connect({}, "/org/monet/WheelScrolling", "org.monet.WheelScrolling",
                                              "Changed", this, SLOT(reload()));
        QDBusConnection::sessionBus().connect({}, "/org/monet/MouseEnhancements", "org.monet.MouseEnhancements",
                                              "Changed", this, SLOT(reload()));
        reload();
    }

private Q_SLOTS:
    void reload()
    {
        QSettings s("Monet", "WheelScrolling");
        s.sync();
        exceptions.reload();
        const auto mode = s.value("profile").toString();
        profile = mode == "smooth" ? Profile::Smooth : mode == "linear" ? Profile::Linear : Profile::System;
        const auto key = s.value("sideways").toString();
        if (key == "shift") sideways = Qt::ShiftModifier;
        else if (key == "alt") sideways = Qt::AltModifier;
        else if (key == "ctrl") sideways = Qt::ControlModifier;
        else if (key == "meta") sideways = Qt::MetaModifier;
        else sideways = Qt::NoModifier;
        distancePercent = qBound(50, s.value("distance", 100).toInt(), 250);
        duration = qBound(60, s.value("duration", 160).toInt(), 400);
        stop();
        const bool enabled = profile != Profile::System || sideways != Qt::NoModifier;
        if (enabled != installed) {
            installed = enabled;
            if (enabled) input()->installInputEventFilter(this);
            else input()->uninstallInputEventFilter(this);
        }
    }

private:
    MouseExceptions exceptions;

    SurfaceInterface *destination() const
    {
        auto *server = waylandServer();
        auto *p = input()->pointer();
        auto *w = p->focus();
        auto *seat = server->seat();
        if (!w || w != p->hover() || w->isDeleted() || !(w->isNormalWindow() || w->isDialog())
            || w->isInteractiveMove() || w->isInteractiveResize() || p->decoration() || p->isConstrained() || p->areButtonsPressed()
            || !seat->pointer() || seat->isDrag() || server->isScreenLocked() || input()->isSelectingWindow() || exceptions.matches(w)
            || (effects && effects->isMouseInterception()) || server->isKeyboardShortcutsInhibited()) {
            return nullptr;
        }
        return seat->pointer()->focusedSurface();
    }

    void stop()
    {
        if (!target && !frame.isActive() && !focusChanged) {
            return;
        }
        frame.stop();
        horizontal = vertical = {};
        QObject::disconnect(focusChanged);
        focusChanged = {};
        device.clear();
        target.clear();
        xRemainder = yRemainder = 0;
    }

    // A modifier is already meaningful to many applications (e.g. Ctrl zoom).
    // Scope the modifier change to this wheel frame and its receiving client.
    void send(Qt::Orientation axis, double delta, int units, PointerAxisSource source, bool inverted)
    {
        auto *seat = waylandServer()->seat();
        auto *keyboardSurface = seat->focusedKeyboardSurface();
        auto *xkb = input()->keyboard()->xkb();
        const bool mask = remapped && keyboardSurface && target && keyboardSurface->client() == target->client();
        if (mask && xkb->keymap()) {
            const char *name = sideways == Qt::ShiftModifier ? XKB_MOD_NAME_SHIFT :
                sideways == Qt::AltModifier ? XKB_MOD_NAME_ALT :
                sideways == Qt::MetaModifier ? XKB_MOD_NAME_LOGO : XKB_MOD_NAME_CTRL;
            const auto index = xkb_keymap_mod_get_index(xkb->keymap(), name);
            const quint32 keep = index < 32 ? ~(quint32(1) << index) : ~quint32(0);
            const auto state = xkb->modifierState();
            seat->notifyKeyboardModifiers(state.depressed & keep, state.latched & keep, state.locked & keep, xkb->currentLayout());
        }
        seat->notifyPointerAxis(axis, delta, units, source, inverted);
        seat->notifyPointerFrame();
        if (mask) xkb->forwardModifiers();
    }

    void sendUnits(Qt::Orientation axis, qint64 units, bool inverted)
    {
        if (!units) return;
        // XWayland converts scroll valuators to wheel clicks for older X11 apps.
        const bool x11 = target->client() == waylandServer()->xWaylandConnection();
        const int value = int(qBound(qint64(-INT_MAX), units, qint64(INT_MAX)));
        // With older clients, carrying v120 suppresses intermediate frames
        // and may also generate a second, discrete scroll for the final frame.
        const double perDetent = x11 || !highResolution ? 15.0 : 40.0;
        send(axis, value * perDetent / 120., x11 || highResolution ? value : 0,
             x11 ? PointerAxisSource::Wheel : PointerAxisSource::Continuous, inverted);
    }

    void animate()
    {
        if (!target || target != destination() || (input()->globalPointer() - origin).manhattanLength() > 24) {
            stop();
            return;
        }
        const auto now = clock.elapsed();
        // Wayland events use the monotonic input clock. A monotonic interval
        // since the physical event also works for a nested compositor.
        auto *seat = waylandServer()->seat();
        seat->setTimestamp(std::max(std::chrono::duration_cast<std::chrono::microseconds>(seat->timestamp()),
                                    inputTime + std::chrono::milliseconds(now - received)));
        const int quantum = target->client() == waylandServer()->xWaylandConnection() ? 15 : 1;
        sendUnits(Qt::Horizontal, horizontal.advance(now, duration, quantum), horizontal.inverted);
        sendUnits(Qt::Vertical, vertical.advance(now, duration, quantum), vertical.inverted);
        if (horizontal.distance == horizontal.sent && vertical.distance == vertical.sent) frame.stop();
    }

    bool pointerAxis(PointerAxisEvent *event) override
    {
        const bool wheel = event->source == PointerAxisSource::Wheel || event->source == PointerAxisSource::WheelTilt
            || (event->source == PointerAxisSource::Unknown && event->deltaV120 != 0);
        const bool turn = sideways != Qt::NoModifier && event->modifiers == sideways && event->orientation == Qt::Vertical;
        auto *surface = wheel && !event->autoscroll && !(event->device && event->device->isTouchpad())
            && (event->modifiers == Qt::NoModifier || turn) ? destination() : nullptr;
        if (!surface || (!turn && profile == Profile::System) || !event->delta) {
            if (target) stop();
            return false;
        }

        if (surface != target || device != event->device || turn != remapped || (event->position - origin).manhattanLength() > 24) {
            stop();
            target = surface;
            highResolution = supportsHighResolutionWheel(surface);
            device = event->device;
            focusChanged = connect(waylandServer()->seat()->pointer(), &PointerInterface::focusedSurfaceChanged,
                                   this, &WheelScroll::stop);
        }
        origin = event->position;
        remapped = turn;
        const auto axis = turn ? Qt::Horizontal : event->orientation;
        inputTime = event->timestamp;
        received = clock.elapsed();
        waylandServer()->seat()->setTimestamp(inputTime);
        if (profile == Profile::System) {
            send(axis, event->delta, event->deltaV120, event->source, event->inverted);
            return true;
        }

        // Carry fractions from high-resolution wheels across input reports.
        int &remainder = axis == Qt::Horizontal ? xRemainder : yRemainder;
        const qint64 raw = event->deltaV120 ? event->deltaV120 : qRound64(event->delta * 8.);
        const qint64 scaled = raw * distancePercent + remainder;
        const qint64 units = scaled / 100;
        remainder = int(scaled % 100);
        if (!units) return true;
        if (profile == Profile::Linear) {
            sendUnits(axis, units, event->inverted);
        } else {
            Glide &glide = axis == Qt::Horizontal ? horizontal : vertical;
            glide.add(units, received, event->inverted);
            if (!frame.isActive()) {
                frame.start();
                animate();
            }
        }
        return true;
    }

    Profile profile = Profile::System;
    Qt::KeyboardModifier sideways = Qt::NoModifier;
    bool installed = false, remapped = false, highResolution = false;
    int distancePercent = 100, duration = 160, xRemainder = 0, yRemainder = 0;
    QTimer frame;
    QElapsedTimer clock;
    qint64 received = 0;
    std::chrono::microseconds inputTime{};
    QPointF origin;
    Glide horizontal, vertical;
    QPointer<InputDevice> device;
    QPointer<SurfaceInterface> target;
    QMetaObject::Connection focusChanged;
};

class WheelFactory final : public PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "wheelscroll.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<Plugin> create() const override { return std::make_unique<WheelScroll>(); }
};
#include "wheelscroll.moc"
