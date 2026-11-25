#!/usr/bin/env python3
"""Attach markers to Spectacle's selected source and actual video timeline."""
from pathlib import Path
import shutil
import sys


def replace(path, before, after):
    data = path.read_text()
    if data.count(before) != 1:
        raise ValueError(f"Unsupported KWin source in {path.name}: {before!r}")
    path.write_text(data.replace(before, after))


def patch(source):
    folder = source / "src/plugins/screencast"
    manager = folder / "screencastmanager.cpp"
    header = folder / "screencaststream.h"
    stream = folder / "screencaststream.cpp"
    for name in ("recordingclicks.h", "recordingclicks.cpp"):
        shutil.copyfile(Path(__file__).with_name(name), folder / name)
    replace(manager, "    if (!stream->init()) {", """    const auto client = waylandStream->connection();
    if (client && client->executablePath() == QStringLiteral("/usr/bin/spectacle")) {
        stream->connectEditor(client->processId());
    }
    if (!stream->init()) {""")
    replace(header, "class ScreenCastSource;", "class ScreenCastSource;\nclass RecordingClicks;")
    replace(header, "    bool init();", "    void connectEditor(qint64 pid);\n    bool init();")
    replace(header, "    struct pw_stream *m_pwStream", "    std::unique_ptr<RecordingClicks> m_clicks;\n    struct pw_stream *m_pwStream")
    replace(stream, '#include "screencaststream.h"', '#include "screencaststream.h"\n#include "recordingclicks.h"')
    replace(stream, "void ScreenCastStream::close()", """void ScreenCastStream::connectEditor(qint64 pid)
{
    m_clicks = std::make_unique<RecordingClicks>(m_source.get(), pid);
}

void ScreenCastStream::close()""")
    replace(stream, "        m_source->pause();", "        if (m_clicks) {\n            m_clicks->pause();\n        }\n        m_source->pause();")
    replace(stream, "    m_source.reset();", "    m_clicks.reset();\n    m_source.reset();")
    replace(stream, "        spa_data->chunk->flags = SPA_CHUNK_FLAG_NONE;",
            "        if (m_clicks) {\n            m_clicks->frame(timestamp);\n        }\n        spa_data->chunk->flags = SPA_CHUNK_FLAG_NONE;")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
