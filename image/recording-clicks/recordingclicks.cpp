// SPDX-License-Identifier: GPL-2.0-or-later
#include "recordingclicks.h"
#include "core/inputdevice.h"
#include "cursor.h"
#include "input.h"
#include "input_event.h"
#include "screencastsource.h"
#include "wayland_server.h"
#include <QFile>
#include <sys/socket.h>
#include <unistd.h>

namespace KWin
{
static qint64 parentOf(qint64 pid)
{
    QFile status(QStringLiteral("/proc/%1/status").arg(pid));
    if (status.open(QIODevice::ReadOnly)) {
        for (const auto &line : status.readAll().split('\n')) {
            if (line.startsWith("PPid:")) {
                return line.mid(5).trimmed().toLongLong();
            }
        }
    }
    return -1;
}

RecordingClicks::RecordingClicks(ScreenCastSource *source, qint64 recorder)
    : m_source(source)
{
    // Spectacle's parent is the editor that launched this specific take.
    QObject::connect(&m_editor, &QLocalSocket::connected, &m_editor, [this, recorder] {
        ucred peer{};
        socklen_t length = sizeof(peer);
        if (getsockopt(m_editor.socketDescriptor(), SOL_SOCKET, SO_PEERCRED, &peer, &length) != 0
            || peer.uid != getuid() || peer.pid != parentOf(recorder)) {
            m_editor.abort();
            return;
        }
        m_authenticated = true;
        observe();
    });
    QObject::connect(&m_editor, &QLocalSocket::disconnected, &m_editor, [this] {
        m_authenticated = false;
        stop();
    });
    m_editor.setSocketOptions(QLocalSocket::AbstractNamespaceOption);
    m_editor.connectToServer(QStringLiteral("monet-recording-clicks-%1-%2").arg(getuid()).arg(recorder), QIODevice::WriteOnly);
}

RecordingClicks::~RecordingClicks()
{
    QObject::disconnect(&m_editor, nullptr, &m_editor, nullptr);
    stop();
}

void RecordingClicks::observe()
{
    if (!m_authenticated || !m_streaming || m_observing) {
        return;
    }
    if (!m_announced) {
        m_editor.write("ready\n");
        m_announced = true;
    }
    input()->installInputEventSpy(this);
    m_observing = true;
}

void RecordingClicks::stop()
{
    if (m_observing) {
        input()->uninstallInputEventSpy(this);
        m_observing = false;
    }
}

void RecordingClicks::pause()
{
    m_streaming = false;
    stop();
}

void RecordingClicks::frame(std::chrono::nanoseconds pts)
{
    if (!m_streaming) {
        if (!m_first) {
            m_first = pts;
        }
        m_streaming = true;
        observe();
    }
}

void RecordingClicks::pointerButton(PointerButtonEvent *event)
{
    if (event->state != PointerButtonState::Pressed || event->button != Qt::LeftButton
        || waylandServer()->isScreenLocked() || !m_source->includesCursor(Cursors::self()->currentCursor())) {
        return;
    }
    const auto size = m_source->textureSize();
    if (size.isEmpty() || m_editor.bytesToWrite() >= 65536) {
        return;
    }
    const auto local = m_source->mapFromGlobal(event->position) * m_source->devicePixelRatio();
    const auto x = local.x() / size.width();
    const auto y = local.y() / size.height();
    // Same monotonic presentation clock as KWin's PipeWire video headers.
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch() - *m_first).count();
    if (ms >= 0 && x >= 0 && x < 1 && y >= 0 && y < 1) {
        m_editor.write(QByteArray::number(ms) + ' ' + QByteArray::number(x) + ' ' + QByteArray::number(y) + '\n');
    }
}
}
