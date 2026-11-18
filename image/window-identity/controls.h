// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QPointF>
#include <QWindow>

// In-process only: the title script hands its held press to the compositor.
class WindowControls : public QObject
{
    Q_OBJECT
public:
    explicit WindowControls(QObject *parent = nullptr) : QObject(parent) {}
    Q_INVOKABLE bool beginMove(QObject *target, const QPointF &press, QWindow *bar);
};
