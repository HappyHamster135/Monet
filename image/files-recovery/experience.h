// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QApplication>
#include <QEvent>
#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLineEdit>
#include <QAbstractButton>
#include <QEnterEvent>
#include <QHoverEvent>
#include <QMouseEvent>
#include <QPointer>
#include <QScopedValueRollback>
#include <QTabBar>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTextEdit>
#include <QTimer>
#include <QVBoxLayout>
#include <KIO/RenameDialog>
#include <KLocalizedString>
#include <functional>

// One lightweight filter per Files process. Never stat or decode a file here.
class MonetFilesExperience final : public QObject {
public:
    MonetFilesExperience(QObject *parent, std::function<void()> preview)
        : QObject(parent), m_preview(std::move(preview)) { qApp->installEventFilter(this); }

    static void improveConflict(KIO::RenameDialog *dialog)
    {
        if (dialog->property("monetKeepBoth").toBool()) return;
        // Resume-only conflicts deliberately don't allow a rename.
        const auto rename = dialog->findChildren<QPushButton *>();
        bool renameAllowed = false;
        for (auto button : rename)
            if (button->text() == i18nd("kio6", "Suggest New &Name")) renameAllowed = true;
        if (!renameAllowed) return;
        auto layout = qobject_cast<QVBoxLayout *>(dialog->layout());
        if (!layout) return;
        dialog->setProperty("monetKeepBoth", true);
        auto row = new QHBoxLayout;
        row->addStretch();
        auto both = new QPushButton(i18nd("monet", "Keep both"), dialog);
        both->setObjectName(QStringLiteral("monetKeepBoth"));
        both->setToolTip(i18nd("monet", "Keep the existing file and give the incoming file an unused name."));
        row->addWidget(both);
        layout->addLayout(row);
        QObject::connect(both, &QPushButton::clicked, dialog, [dialog] {
            // KIO chooses an unused name and rechecks collisions in its CopyJob.
            dialog->suggestNewNamePressed();
            dialog->renamePressed();
        });
        both->setDefault(true);
    }

protected:
    bool eventFilter(QObject *object, QEvent *event) override
    {
        if (!m_forwardingClose && tabCloseEvent(object, event)) return true;
        if (event->type() == QEvent::Show) {
            if (auto conflict = qobject_cast<KIO::RenameDialog *>(object)) improveConflict(conflict);
        }
        if (event->type() != QEvent::KeyPress || object != QApplication::focusWidget()) return false;
        auto key = static_cast<QKeyEvent *>(event);
        if (key->key() != Qt::Key_Space || key->modifiers() != Qt::NoModifier || key->isAutoRepeat()) return false;
        auto focus = QApplication::focusWidget();
        if (qobject_cast<QLineEdit *>(focus) || qobject_cast<QTextEdit *>(focus) || qobject_cast<QPlainTextEdit *>(focus)) return false;
        for (auto parent = focus; parent; parent = parent->parentWidget()) {
            if (parent->inherits("DolphinView")) {
                m_preview();
                key->accept();
                return true;
            }
        }
        return false;
    }
private:
    // Expand input around the existing close widget, rather than replacing
    // its style, icon, geometry or native hover/press animation.
    static QAbstractButton *closeAt(QTabBar *bar, const QPoint &point)
    {
        const int index = bar->tabAt(point);
        if (index < 0 || !bar->tabsClosable()) return nullptr;
        for (auto side : {QTabBar::LeftSide, QTabBar::RightSide}) {
            auto button = qobject_cast<QAbstractButton *>(bar->tabButton(index, side));
            if (!button || !button->inherits("CloseButton") || !button->isVisible() || !button->isEnabled()) continue;
            const QRect original(button->mapTo(bar, QPoint()), button->size());
            const int size = qMax(32, qMax(original.width(), original.height()) + 16);
            const QRect target(original.center() - QPoint(size / 2, size / 2), QSize(size, size));
            if (target.intersected(bar->tabRect(index)).contains(point)) return button;
        }
        return nullptr;
    }

    void closeHover(QAbstractButton *button)
    {
        if (m_closeHover == button) return;
        QScopedValueRollback<bool> guard(m_forwardingClose, true);
        if (m_closeHover) {
            auto old = m_closeHover;
            old->setAttribute(Qt::WA_UnderMouse, false);
            QEvent leave(QEvent::Leave); QApplication::sendEvent(old, &leave);
            QHoverEvent hover(QEvent::HoverLeave, QPointF(-1, -1), old->mapToGlobal(QPoint(-1, -1)), QPointF(old->rect().center()));
            QApplication::sendEvent(old, &hover); old->update();
        }
        m_closeHover = button;
        if (button) {
            const QPointF local(button->rect().center());
            button->setAttribute(Qt::WA_UnderMouse, true);
            QEnterEvent enter(local, button->mapTo(button->window(), local.toPoint()), button->mapToGlobal(local.toPoint()));
            QApplication::sendEvent(button, &enter);
            QHoverEvent hover(QEvent::HoverEnter, local, button->mapToGlobal(local.toPoint()), QPointF(-1, -1));
            QApplication::sendEvent(button, &hover); button->update();
        }
    }

    bool tabCloseEvent(QObject *object, QEvent *event)
    {
        const auto type = event->type();
        if (type != QEvent::MouseMove && type != QEvent::MouseButtonPress
            && type != QEvent::MouseButtonDblClick && type != QEvent::MouseButtonRelease
            && type != QEvent::Leave) return false;
        auto widget = qobject_cast<QWidget *>(object);
        if (!widget) return false;
        auto parent = widget;
        while (parent && !qobject_cast<QTabBar *>(parent)) parent = parent->parentWidget();
        auto bar = qobject_cast<QTabBar *>(parent);
        if (type == QEvent::Leave) {
            if (widget == m_closeBar) closeHover(nullptr);
            return false;
        }
        auto mouse = static_cast<QMouseEvent *>(event);
        const auto point = bar ? bar->mapFrom(widget, mouse->position().toPoint()) : QPoint();
        auto button = bar ? closeAt(bar, point) : nullptr;
        if (bar || m_closeHover) { closeHover(button); m_closeBar = bar; }
        if (type == QEvent::MouseButtonRelease && m_closePressed) {
            if (mouse->button() != Qt::LeftButton) return false;
        } else if (type == QEvent::MouseMove && m_closePressed) {
            // Moving away cancels a press, exactly as on the original button.
        } else if ((type == QEvent::MouseButtonPress || type == QEvent::MouseButtonDblClick)
                   && mouse->button() == Qt::LeftButton && button && widget != button) {
            m_closePressed = button;
        } else return false;
        if (!m_closePressed) return false;
        auto receiver = m_closePressed;
        const QPointF local = button == receiver ? QPointF(receiver->rect().center()) : QPointF(-1, -1);
        QScopedValueRollback<bool> guard(m_forwardingClose, true);
        QMouseEvent forwarded(type, local, receiver->mapToGlobal(local.toPoint()),
                              mouse->button(), mouse->buttons(), mouse->modifiers(), mouse->pointingDevice());
        if (type == QEvent::MouseButtonRelease) m_closePressed.clear();
        QApplication::sendEvent(receiver, &forwarded);
        event->accept();
        return true;
    }

    bool m_forwardingClose = false;
    QPointer<QAbstractButton> m_closeHover;
    QPointer<QAbstractButton> m_closePressed;
    QPointer<QTabBar> m_closeBar;
    std::function<void()> m_preview;
};
