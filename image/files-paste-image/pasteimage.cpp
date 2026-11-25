// SPDX-License-Identifier: GPL-3.0-or-later
#include <KAbstractFileItemActionPlugin>
#include <KFileItemListProperties>
#include <KIO/PasteJob>
#include <KJobUiDelegate>
#include <KJobWidgets>
#include <KLocalizedString>
#include <KMessageBox>
#include <KPluginFactory>

#include <QAction>
#include <QApplication>
#include <QBuffer>
#include <QClipboard>
#include <QFutureWatcher>
#include <QImageReader>
#include <QMenu>
#include <QMimeData>
#include <QPointer>
#include <QTimer>
#include <QtConcurrentRun>

namespace
{
// Asking for the formats does not fetch the clipboard image while the menu opens.
QString encodedFormat(const QMimeData *mime)
{
    if (mime->hasFormat(QStringLiteral("image/png"))) {
        return QStringLiteral("image/png");
    }
    const auto formats = mime->formats();
    for (const QString &format : formats) {
        if (format.startsWith(QLatin1String("image/"))) {
            static const auto readable = QImageReader::supportedMimeTypes();
            if (readable.contains(format.toLatin1())) {
                return format;
            }
        }
    }
    return {};
}

QByteArray asPng(const QByteArray &bytes, QImage image)
{
    if (!bytes.isEmpty()) {
        QBuffer input;
        input.setData(bytes);
        input.open(QIODevice::ReadOnly);
        QImageReader reader(&input);
        reader.setAutoTransform(true);
        const QByteArray format = reader.format();
        image = reader.read();
        if (!image.isNull() && format == "png") {
            return bytes;
        }
    }
    QBuffer output;
    if (!image.isNull() && output.open(QIODevice::WriteOnly) && image.save(&output, "PNG")) {
        return output.data();
    }
    return {};
}

void pasteImage(const QUrl &folder, QWidget *window)
{
    QPointer<const QMimeData> source = QApplication::clipboard()->mimeData();
    // Snapshot on activation. The owner can change while the filename dialog is open.
    const QString format = source ? encodedFormat(source) : QString();
    QByteArray bytes;
    QImage image;
    if (!format.isEmpty()) {
        bytes = source->data(format);
    }
    if (bytes.isEmpty() && source && source->hasImage()) {
        image = qvariant_cast<QImage>(source->imageData());
    }
    if (bytes.isEmpty() && image.isNull()) {
        KMessageBox::information(window, i18nd("monet", "Copy an image, then choose Paste Image as PNG again."));
        return;
    }

    auto watcher = new QFutureWatcher<QByteArray>(window);
    QObject::connect(watcher, &QFutureWatcher<QByteArray>::finished, watcher, [watcher, folder, window] {
        const QByteArray png = watcher->result();
        watcher->deleteLater();
        if (png.isEmpty()) {
            KMessageBox::error(window, i18nd("monet", "Files could not read the copied image."));
            return;
        }

        // A single-format payload uses KIO's normal naming, conflict and undo flow.
        // Keep the snapshot alive for the entire asynchronous paste job.
        auto payload = new QMimeData;
        payload->setData(QStringLiteral("image/png"), png);
        payload->setData(QStringLiteral("application/x-kde-suggestedfilename"), i18nd("monet", "Pasted image").toUtf8());
        auto job = KIO::paste(payload, folder);
        payload->setParent(job);
        KJobWidgets::setWindow(job, window);
        if (job->uiDelegate()) {
            job->uiDelegate()->setAutoErrorHandlingEnabled(true);
        }
    });
    watcher->setFuture(QtConcurrent::run(asPng, bytes, image));
}
}

class PasteImageAction : public KAbstractFileItemActionPlugin
{
    Q_OBJECT
public:
    explicit PasteImageAction(QObject *parent)
        : KAbstractFileItemActionPlugin(parent)
    {
    }

    QList<QAction *> actions(const KFileItemListProperties &props, QWidget *parentWidget) override
    {
        const auto urls = props.urlList();
        if (!parentWidget || urls.size() != 1 || !props.isDirectory() || !props.supportsWriting()) {
            return {};
        }
        const QMimeData *mime = QApplication::clipboard()->mimeData();
        if (!mime || (!mime->hasImage() && encodedFormat(mime).isEmpty())) {
            return {};
        }

        auto action = new QAction(QIcon::fromTheme(QStringLiteral("insert-image")), i18nd("monet", "Paste Image as PNG…"), parentWidget);
        QWidget *window = parentWidget->window();
        connect(action, &QAction::triggered, window, [folder = urls.first(), window] { pasteImage(folder, window); });
        // KIO assembles the menu after this call. Release each action with its menu.
        QTimer::singleShot(0, action, [action] {
            for (QObject *host : action->associatedObjects()) {
                if (auto menu = qobject_cast<QMenu *>(host)) {
                    action->setParent(menu);
                    break;
                }
            }
        });
        return {action};
    }
};

K_PLUGIN_CLASS_WITH_JSON(PasteImageAction, "pasteimage.json")
#include "pasteimage.moc"
