#!/usr/bin/python3
"""Make native Ark batch extraction return its actual KJob outcome."""
from pathlib import Path
import sys

root = Path(sys.argv[1])


def patch(name, before, after):
    path = root / name
    source = path.read_text()
    if after in source:
        return
    if source.count(before) != 1:
        raise SystemExit('Ark source changed: ' + name)
    path.write_text(source.replace(before, after))


patch('app/main.cpp', '#include <QApplication>', '#include <QApplication>\n#include <QTimer>')
patch('app/main.cpp',
      'QObject::connect(batchJob, &KJob::result, &application, &QCoreApplication::quit, Qt::QueuedConnection);',
      '''QObject::connect(batchJob, &KJob::result, &application, [&application](KJob *job) {
                // Read before KJob's automatic deletion, then queue only the
                // value. The native error/password dialogs have already run.
                const int code = job->error() == KJob::KilledJobError ? 130 : (job->error() ? 1 : 0);
                QTimer::singleShot(0, &application, [code]() { QCoreApplication::exit(code); });
            });''')
patch('app/batchextract.cpp',
      '        m_failedFiles.append(url.fileName());',
      '        m_failedFiles.append(url.fileName());\n        setError(KJob::UserDefinedError);')

patch('plugins/libarchive/libarchiveplugin.cpp', '#include "libarchiveplugin.h"',
      '#include "libarchiveplugin.h"\n#include "rpmheader.h"')
patch('plugins/libarchive/libarchiveplugin.cpp',
      '    qCDebug(ARK_LOG) << "Listing archive contents";',
      '''    qCDebug(ARK_LOG) << "Listing archive contents";

    // RPM already carries a complete file index in its header. Listing via
    // libarchive otherwise decompresses the entire sequential cpio payload.
    const auto rpmEntries = MonetRpm::read(filename());
    if (QThread::currentThread()->isInterruptionRequested()) return false;
    if (rpmEntries.has_value()) {
        m_cachedArchiveEntryCount = 0;
        m_extractedFilesSize = 0;
        m_numberOfEntries = 0;
        for (const auto &item : *rpmEntries) {
            if (QThread::currentThread()->isInterruptionRequested()) return false;
            auto aentry = archive_entry_new();
            archive_entry_copy_pathname_w(aentry, item.path.toStdWString().c_str());
            archive_entry_copy_uname(aentry, item.owner.toUtf8().constData());
            archive_entry_copy_gname(aentry, item.group.toUtf8().constData());
            archive_entry_set_size(aentry, item.size);
            archive_entry_set_mode(aentry, item.mode);
            archive_entry_set_mtime(aentry, item.time, 0);
            if (!item.link.isEmpty()) archive_entry_copy_symlink(aentry, item.link.toUtf8().constData());
            if (!m_emitNoEntries) emitEntryFromArchiveEntry(aentry);
            archive_entry_free(aentry);
            m_cachedArchiveEntryCount++;
            m_extractedFilesSize += item.size;
        }
        Q_EMIT progress(1.0);
        return true;
    }''')
(root / 'plugins/libarchive/rpmheader.h').write_bytes(Path(__file__).with_name('rpmheader.h').read_bytes())
