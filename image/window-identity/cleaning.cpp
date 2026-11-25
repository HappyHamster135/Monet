// SPDX-License-Identifier: GPL-3.0-or-later
#include <plugin.h>
#include <core/inputdevice.h>
#include <core/session.h>
#include <main.h>
#include <xkb.h>
#include <xkbcommon/xkbcommon.h>
#include <input.h>
#include <input_event.h>
#include <keyboard_input.h>
#include <pointer_input.h>
#include <wayland/seat.h>
#include <wayland_server.h>
#include <KLocalizedString>
#include <QApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusMessage>
#include <QDBusServiceWatcher>
#include <QDeadlineTimer>
#include <QElapsedTimer>
#include <QFrame>
#include <QHBoxLayout>
#include <QLabel>
#include <QPointer>
#include <QPushButton>
#include <QScreen>
#include <QStyle>
#include <QTimer>
#include <QVBoxLayout>
#include <map>
#include <memory>

namespace KWin
{
// An internal compositor window stays above fullscreen apps and on all desktops.
// Workspace input never reaches clients while this card is showing.
class CleaningCard : public QFrame
{
public:
    CleaningCard(QScreen *screen, bool dark)
        : QFrame(nullptr, Qt::ToolTip | Qt::FramelessWindowHint | Qt::WindowDoesNotAcceptFocus)
        , blackout(dark)
    {
        setObjectName(QStringLiteral("monetCleaningCard"));
        setWindowTitle(i18nd("monet", "Cleaning mode"));
        setAttribute(Qt::WA_ShowWithoutActivating);
        setAttribute(Qt::WA_TranslucentBackground, !blackout);
        if (blackout) {
            QPalette colors = palette();
            colors.setColor(QPalette::Window, Qt::black);
            setPalette(colors);
            setAutoFillBackground(true);
        }
        setStyleSheet(QStringLiteral(
            "QFrame#panel {background:#292925; border:1px solid #686a60; border-radius:14px;}"
            "QLabel {color:#f4f3ec; background:transparent;}"
            "QPushButton {color:white; background:#30685b; border:1px solid #729b8c; border-radius:12px; padding:6px 12px;}"
            "QPushButton[pointed=true] {background:#3a7969;}"
            "QPushButton:pressed {background:#20483e;}"));
        auto outer = new QVBoxLayout(this);
        outer->setContentsMargins(0, 0, 0, 0);
        auto panel = new QFrame(this);
        panel->setObjectName(QStringLiteral("panel"));
        outer->addWidget(panel, 0, blackout ? Qt::AlignCenter : Qt::Alignment());
        auto layout = new QVBoxLayout(panel);
        layout->setContentsMargins(15, 10, 15, 12);
        auto row = new QHBoxLayout;
        auto heading = new QLabel(windowTitle(), panel);
        QFont font = heading->font();
        font.setBold(true);
        heading->setFont(font);
        row->addWidget(heading);
        row->addStretch();
        finish = new QPushButton(i18nd("monet", "Finish cleaning"), panel);
        finish->setFocusPolicy(Qt::NoFocus);
        row->addWidget(finish);
        layout->addLayout(row);
        remaining = new QLabel(panel);
        layout->addWidget(remaining);
        instruction = new QLabel(i18nd("monet", "Press Esc five times to finish early."), panel);
        instruction->setWordWrap(true);
        layout->addWidget(instruction);
        setScreen(screen);
        connect(screen, &QScreen::geometryChanged, this, [this, screen] { position(screen); });
    }

    void refresh(int seconds, int count)
    {
        remaining->setText(i18nd("monet", "Cleaning ends in %1 s", seconds));
        instruction->setText(count ? i18nd("monet", "Esc presses: %1 of 5", count)
                                   : i18nd("monet", "Press Esc five times to finish early."));
    }

    void position(QScreen *screen)
    {
        const QRect area = screen->geometry();
        if (blackout) {
            setGeometry(area);
            return;
        }
        setFixedWidth(qMin(area.width(), qMax(280, layout()->minimumSize().width())));
        adjustSize();
        move(qMax(area.left(), area.right() - width() - 15), area.top() + 16);
    }

    bool buttonAt(const QPointF &point) const
    {
        return finish->rect().contains(finish->mapFromGlobal(point.toPoint()));
    }

    void point(bool over)
    {
        finish->setProperty("pointed", over);
        finish->style()->unpolish(finish);
        finish->style()->polish(finish);
        finish->update();
    }
    QPushButton *finish;
private:
    const bool blackout;
    QLabel *remaining;
    QLabel *instruction;
};

class Cleaning : public Plugin, public InputEventFilter, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.Cleaning")
public:
    Cleaning()
        : InputEventFilter(InputFilterOrder::ScreenEdge)
        , owner(QStringLiteral("org.monet.Utilities"), QDBusConnection::sessionBus(),
                QDBusServiceWatcher::WatchForUnregistration)
    {
        auto bus = QDBusConnection::sessionBus();
        bus.registerObject(QStringLiteral("/org/monet/Cleaning"), this, QDBusConnection::ExportScriptableSlots);
        timer.setSingleShot(true);
        timer.setTimerType(Qt::PreciseTimer);
        connect(&timer, &QTimer::timeout, this, &Cleaning::tick);
        connect(&owner, &QDBusServiceWatcher::serviceUnregistered, this, [this] { end(); });
        connect(waylandServer(), &WaylandServer::lockStateChanged, this, [this] {
            if (waylandServer()->isScreenLocked()) end();
        });
        if (auto session = kwinApp()->session()) {
            connect(session, &Session::activeChanged, this, [this](bool current) {
                if (!current) end();
            });
        }
        connect(qGuiApp, &QGuiApplication::screenAdded, this, [this](QScreen *screen) {
            if (active) addCard(screen);
        });
        connect(qGuiApp, &QGuiApplication::screenRemoved, this, [this](QScreen *screen) {
            cards.erase(screen);
            if (cards.empty()) end();
        });
        connect(input(), &InputRedirection::deviceRemoved, this, [this](InputDevice *device) {
            heldButtons.remove(device);
            const auto keys = input()->keyboard()->pressedKeys();
            heldKeys.removeIf([&keys](uint32_t key) { return !keys.contains(key); });
            if (clickDevice == device) cancelClick();
            updateFilter();
        });
    }

    ~Cleaning() override
    {
        QDBusConnection::sessionBus().unregisterObject(QStringLiteral("/org/monet/Cleaning"));
        if (installed) input()->uninstallInputEventFilter(this);
    }

public Q_SLOTS:
    Q_SCRIPTABLE bool Begin(int seconds, bool dark)
    {
        auto bus = QDBusConnection::sessionBus();
        if (!calledFromDBus() || bus.interface()->serviceOwner(QStringLiteral("org.monet.Utilities")).value() != message().service()
            || (seconds != 30 && seconds != 60 && seconds != 120) || active || qGuiApp->screens().isEmpty()
            || waylandServer()->isScreenLocked() || waylandServer()->seat()->isDrag()
            || waylandServer()->seat()->isTouchSequence() || input()->pointer()->areButtonsPressed() || input()->isSelectingWindow()) {
            return false;
        }
        // Let keys held before activation finish normally; a button may have
        // activated the dialog on key-down. Their releases must not count.
        beforeKeys = input()->keyboard()->pressedKeys();
        auto *xkb = input()->keyboard()->xkb();
        if (auto *state = xkb->state()) {
            keymap.reset(xkb_keymap_ref(xkb_state_get_keymap(state)));
            locked = xkb_state_serialize_mods(state, XKB_STATE_MODS_LOCKED);
            latched = xkb_state_serialize_mods(state, XKB_STATE_MODS_LATCHED);
            layoutIndex = xkb->currentLayout();
        }
        blackout = dark;
        active = true;
        deadline = QDeadlineTimer(seconds * 1000, Qt::PreciseTimer);
        presses = 0;
        escapeDown = false;
        lastSecond = -1;
        for (auto screen : qGuiApp->screens()) addCard(screen);
        updateFilter();
        tick();
        return true;
    }

private:
    void addCard(QScreen *screen)
    {
        if (cards.count(screen)) return;
        auto card = std::make_unique<CleaningCard>(screen, blackout);
        card->refresh((deadline.remainingTime() + 999) / 1000, presses);
        card->position(screen);
        connect(card->finish, &QPushButton::clicked, this, [this] { end(); }, Qt::QueuedConnection);
        card->show();
        cards.emplace(screen, std::move(card));
    }

    void updateFilter()
    {
        const bool needed = active || !heldKeys.isEmpty() || !heldButtons.isEmpty() || !touches.isEmpty();
        if (needed == installed) return;
        installed = needed;
        if (needed) input()->installInputEventFilter(this);
        else input()->uninstallInputEventFilter(this);
    }

    void tick()
    {
        if (deadline.hasExpired()) {
            end();
            return;
        }
        if (presses && sequence.elapsed() >= 6000) presses = 0;
        const int left = deadline.remainingTime();
        const int second = (left + 999) / 1000;
        if (lastSecond != second || lastPresses != presses) {
            lastPresses = presses;
            lastSecond = second;
            for (auto &[screen, card] : cards) card->refresh(second, presses);
        }
        int next = left - (second - 1) * 1000;
        if (presses) next = qMin(next, int(6000 - sequence.elapsed()));
        timer.start(qMax(1, next));
    }

    void cancelClick()
    {
        if (pressedCard) pressedCard->finish->setDown(false);
        pressedCard.clear();
        clickDevice = nullptr;
    }

    void end()
    {
        if (!active) return;
        active = false;
        timer.stop();
        beforeKeys.clear();
        cancelClick();
        touchButton.clear();
        cards.clear();
        auto *xkb = input()->keyboard()->xkb();
        auto *state = xkb->state();
        if (keymap && state && xkb_state_get_keymap(state) == keymap.get()
            && (locked != xkb_state_serialize_mods(state, XKB_STATE_MODS_LOCKED)
                || latched != xkb_state_serialize_mods(state, XKB_STATE_MODS_LATCHED)
                || layoutIndex != xkb->currentLayout())) {
            // Retain physically depressed modifiers while undoing lock-key and
            // layout changes made while wiping the keyboard.
            xkb->updateModifiers(xkb_state_serialize_mods(state, XKB_STATE_MODS_DEPRESSED),
                                 latched, locked, layoutIndex);
        }
        keymap.reset();
        updateFilter();
    }

    CleaningCard *buttonAt(const QPointF &point) const
    {
        for (const auto &[screen, card] : cards)
            if (card->buttonAt(point)) return card.get();
        return nullptr;
    }

    bool keyboardKey(KeyboardKeyEvent *event) override
    {
        const auto key = event->nativeScanCode;
        if (beforeKeys.contains(key)) {
            if (event->state == KeyboardKeyState::Released) beforeKeys.removeAll(key);
            return event->state != KeyboardKeyState::Released;
        }
        if (!active) {
            if (!heldKeys.contains(key)) return false;
            if (event->state != KeyboardKeyState::Repeated) heldKeys.remove(key);
            updateFilter();
            return event->state != KeyboardKeyState::Pressed;
        }
        if (event->state == KeyboardKeyState::Repeated) return true;
        if (event->state == KeyboardKeyState::Pressed) {
            heldKeys.insert(key);
            input()->keyboard()->addFilteredKey(key);
            if (event->key == Qt::Key_Escape && event->modifiers == Qt::NoModifier && heldKeys.size() == 1) {
                escapeDown = true;
            } else {
                presses = 0;
                escapeDown = false;
            }
        } else {
            heldKeys.remove(key);
            if (event->key == Qt::Key_Escape && escapeDown) {
                escapeDown = false;
                if (presses && sequence.elapsed() > 6000) presses = 0;
                sequence.restart();
                if (++presses == 5) {
                    end();
                    return true;
                }
            }
        }
        tick();
        return true;
    }

    bool pointerButton(PointerButtonEvent *event) override
    {
        const bool down = event->state == PointerButtonState::Pressed;
        const bool wasHeld = heldButtons.value(event->device).contains(event->nativeButton);
        if (!down || !active) {
            auto it = heldButtons.find(event->device);
            if (it != heldButtons.end()) {
                it->remove(event->nativeButton);
                if (it->isEmpty()) heldButtons.erase(it);
            }
        }
        if (!active) {
            updateFilter();
            return !down && wasHeld;
        }
        if (down) heldButtons[event->device].insert(event->nativeButton);
        if (event->button == Qt::LeftButton) {
            if (down) {
                cancelClick();
                pressedCard = buttonAt(event->position);
                clickDevice = event->device;
                if (pressedCard) pressedCard->finish->setDown(true);
            } else if (clickDevice == event->device) {
                const bool finish = pressedCard && pressedCard == buttonAt(event->position);
                cancelClick();
                if (finish) end();
            }
        }
        return true;
    }

    bool touchDown(TouchDownEvent *event) override
    {
        touches.remove(event->id);
        if (!active) { updateFilter(); return false; }
        touches.insert(event->id);
        touchButton = touches.size() == 1 ? buttonAt(event->pos) : nullptr;
        return true;
    }
    bool touchMotion(TouchMotionEvent *event) override
    {
        if (touchButton && touchButton != buttonAt(event->pos)) touchButton.clear();
        return active || touches.contains(event->id);
    }
    bool touchUp(TouchUpEvent *event) override
    {
        const bool held = touches.remove(event->id);
        const bool finish = active && held && touchButton && touches.isEmpty();
        touchButton.clear();
        if (finish) end();
        updateFilter();
        return active || held;
    }
    bool touchCancel() override
    {
        const bool held = !touches.isEmpty();
        touches.clear();
        touchButton.clear();
        updateFilter();
        return active || held;
    }
    bool touchFrame() override { return active; }
    bool pointerMotion(PointerMotionEvent *event) override
    {
        if (!active) return false;
        auto card = buttonAt(event->position);
        if (hoveredCard != card) {
            if (hoveredCard) hoveredCard->point(false);
            if (card) card->point(true);
            hoveredCard = card;
            if (pressedCard) pressedCard->finish->setDown(pressedCard == card);
        }
        return true;
    }
    bool pointerAxis(PointerAxisEvent *) override { return active; }
    bool pointerFrame() override { return active; }
    bool pinchGestureBegin(PointerPinchGestureBeginEvent *) override { return active; }
    bool pinchGestureUpdate(PointerPinchGestureUpdateEvent *) override { return active; }
    bool pinchGestureEnd(PointerPinchGestureEndEvent *) override { return active; }
    bool pinchGestureCancelled(PointerPinchGestureCancelEvent *) override { return active; }
    bool swipeGestureBegin(PointerSwipeGestureBeginEvent *) override { return active; }
    bool swipeGestureUpdate(PointerSwipeGestureUpdateEvent *) override { return active; }
    bool swipeGestureEnd(PointerSwipeGestureEndEvent *) override { return active; }
    bool swipeGestureCancelled(PointerSwipeGestureCancelEvent *) override { return active; }
    bool holdGestureBegin(PointerHoldGestureBeginEvent *) override { return active; }
    bool holdGestureEnd(PointerHoldGestureEndEvent *) override { return active; }
    bool holdGestureCancelled(PointerHoldGestureCancelEvent *) override { return active; }
    bool tabletToolProximityEvent(TabletToolProximityEvent *) override { return active; }
    bool tabletToolAxisEvent(TabletToolAxisEvent *) override { return active; }
    bool tabletToolTipEvent(TabletToolTipEvent *) override { return active; }
    bool tabletToolButtonEvent(TabletToolButtonEvent *) override { return active; }
    bool tabletPadButtonEvent(TabletPadButtonEvent *) override { return active; }
    bool tabletPadRingEvent(TabletPadRingEvent *) override { return active; }
    bool tabletPadStripEvent(TabletPadStripEvent *) override { return active; }
    QDBusServiceWatcher owner;
    QDeadlineTimer deadline;
    QElapsedTimer sequence;
    QTimer timer;
    std::map<QScreen *, std::unique_ptr<CleaningCard>> cards;
    QPointer<CleaningCard> hoveredCard;
    QPointer<CleaningCard> pressedCard;
    QPointer<CleaningCard> touchButton;
    InputDevice *clickDevice = nullptr;
    QList<uint32_t> beforeKeys;
    QSet<uint32_t> heldKeys;
    QHash<InputDevice *, QSet<uint32_t>> heldButtons;
    QSet<int> touches;
    std::unique_ptr<xkb_keymap, decltype(&xkb_keymap_unref)> keymap{nullptr, xkb_keymap_unref};
    xkb_mod_mask_t locked = 0;
    xkb_mod_mask_t latched = 0;
    xkb_layout_index_t layoutIndex = 0;
    int lastSecond = -1;
    int lastPresses = 0;
    int presses = 0;
    bool active = false;
    bool installed = false;
    bool blackout = false;
    bool escapeDown = false;
};

class CleaningFactory : public PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "cleaning.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<Plugin> create() const override
    {
        if (!waylandServer() || !input()) return {};
        return std::make_unique<Cleaning>();
    }
};
}
#include "cleaning.moc"
