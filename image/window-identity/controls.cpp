// SPDX-License-Identifier: GPL-3.0-or-later
#include "controls.h"
#include <input.h>
#include <pointer_input.h>
#include <window.h>
#include <workspace.h>
#include <qpa/qwindowsysteminterface.h>
#include <cmath>

bool WindowControls::beginMove(QObject *target, const QPointF &press, QWindow *bar)
{
    auto window = qobject_cast<KWin::Window *>(target);
    if (!bar || !bar->isVisible() || bar->title() != QStringLiteral("Monet title bar")
            || !window || !KWin::workspace()->windows().contains(window) || window->isDeleted()
            || !(window->isNormalWindow() || window->isDialog() || window->isUtility()) || window->isMinimized() || window->isFullScreen()
            || !window->isMovableAcrossScreens() || (window->isInteractiveMove() || window->isInteractiveResize())
            || !(KWin::input()->pointer()->buttons() & Qt::LeftButton)
            || !std::isfinite(press.x()) || !std::isfinite(press.y())) {
        return false;
    }
    // Unlike slotWindowMove (a keyboard action), this retains the pointer's
    // position and the original press offset. KWin owns snapping and release.
    window->performMousePressCommand(KWin::Options::MouseActivateRaiseAndMove, press);
    if (window->isInteractiveMove()) {
        window->updateInteractiveMoveResize(KWin::input()->pointer()->pos(), Qt::NoModifier);
        // KWin consumes the physical release during its move. Finish the old
        // Qt press too, or QQuickWindow drops the next press as a duplicate.
        const auto pos = KWin::input()->pointer()->pos();
        QWindowSystemInterface::handleMouseEvent(bar, pos - bar->position(), pos,
            KWin::input()->pointer()->buttons() & ~Qt::LeftButton, Qt::LeftButton, QEvent::MouseButtonRelease, Qt::NoModifier);
    }
    return window->isInteractiveMove();
}
