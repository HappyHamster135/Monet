// Blank native surfaces can move a window. Interactive descendants keep their
// gestures, including selection in an otherwise empty editor or item view.
#pragma once
#include <QAbstractButton>
#include <QAbstractScrollArea>
#include <QAbstractSlider>
#include <QAbstractSpinBox>
#include <QApplication>
#include <QComboBox>
#include <QGroupBox>
#include <QLabel>
#include <QLineEdit>
#include <QMouseEvent>
#include <QPointer>
#include <QScrollArea>
#include <QTabBar>
#include <QToolBar>
#include <QWindow>

class BackgroundDrag : public QObject {
public:
    using QObject::QObject;

    static bool eligible(QWidget *widget, QPoint position)
    {
        if (!widget || !widget->isEnabled() || widget->window()->isFullScreen())
            return false;
        for (auto item = widget; item; item = item->parentWidget()) {
            if (qobject_cast<QAbstractButton *>(item) || qobject_cast<QAbstractSlider *>(item)
                || qobject_cast<QAbstractSpinBox *>(item) || qobject_cast<QLineEdit *>(item)
                || qobject_cast<QComboBox *>(item)
                || (qobject_cast<QAbstractScrollArea *>(item) && !qobject_cast<QScrollArea *>(item)))
                return false;
            if (auto label = qobject_cast<QLabel *>(item); label
                && label->textInteractionFlags() != Qt::NoTextInteraction)
                return false;
            if (auto group = qobject_cast<QGroupBox *>(item); group && group->isCheckable())
                return false;
        }
        if (auto tabs = qobject_cast<QTabBar *>(widget))
            return tabs->tabAt(position) < 0;
        if (auto bar = qobject_cast<QToolBar *>(widget))
            return !bar->actionAt(position);
        return widget->metaObject() == &QWidget::staticMetaObject
            || widget->metaObject() == &QFrame::staticMetaObject
            || qobject_cast<QLabel *>(widget) || qobject_cast<QGroupBox *>(widget)
            || (widget->layout() && widget->focusPolicy() == Qt::NoFocus);
    }

protected:
    virtual bool startMove(QWindow *window) { return window && window->startSystemMove(); }

    bool eventFilter(QObject *object, QEvent *event) override
    {
        if (event->type() == QEvent::MouseButtonPress) {
            candidate.clear();
            auto mouse = static_cast<QMouseEvent *>(event);
            auto widget = qobject_cast<QWidget *>(object);
            if (mouse->button() == Qt::LeftButton && mouse->modifiers() == Qt::NoModifier
                && mouse->source() == Qt::MouseEventNotSynthesized
                && eligible(widget, mouse->position().toPoint())) {
                candidate = widget;
                origin = mouse->globalPosition();
                return true;
            }
        } else if (event->type() == QEvent::MouseMove && candidate) {
            auto mouse = static_cast<QMouseEvent *>(event);
            if (!(mouse->buttons() & Qt::LeftButton) || mouse->modifiers() != Qt::NoModifier) {
                candidate.clear();
            } else if ((mouse->globalPosition() - origin).manhattanLength() >= QApplication::startDragDistance()) {
                auto window = candidate->window()->windowHandle();
                candidate.clear();
                return startMove(window);
            }
        } else if (event->type() == QEvent::MouseButtonRelease
                   || event->type() == QEvent::MouseButtonDblClick
                   || event->type() == QEvent::WindowDeactivate) {
            candidate.clear();
        }
        return false;
    }

private:
    QPointer<QWidget> candidate;
    QPointF origin;
};
