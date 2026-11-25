// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "input_event_spy.h"
#include <QLocalSocket>
#include <chrono>
#include <optional>

namespace KWin
{
class ScreenCastSource;

class RecordingClicks : public InputEventSpy
{
public:
    RecordingClicks(ScreenCastSource *source, qint64 recorder);
    ~RecordingClicks() override;
    void frame(std::chrono::nanoseconds pts);
    void pause();
    void pointerButton(PointerButtonEvent *event) override;

private:
    void observe();
    void stop();
    ScreenCastSource *m_source;
    QLocalSocket m_editor;
    std::optional<std::chrono::nanoseconds> m_first;
    bool m_streaming = false;
    bool m_authenticated = false;
    bool m_observing = false;
    bool m_announced = false;
};
}
