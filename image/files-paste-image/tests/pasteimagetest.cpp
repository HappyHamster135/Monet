// SPDX-License-Identifier: GPL-3.0-or-later
#include <KFileItemActions>
#include <KFileItemListProperties>
#include <KPluginMetaData>

#include <QApplication>
#include <QBuffer>
#include <QClipboard>
#include <QDialog>
#include <QFile>
#include <QLineEdit>
#include <QMenu>
#include <QMimeData>
#include <QTemporaryDir>
#include <QTest>
#include <QTimer>

class PasteImageTest : public QObject
{
    Q_OBJECT

    static QAction *imageAction(QMenu &menu)
    {
        for (auto action : menu.actions()) {
            if (action->text() == QStringLiteral("Paste Image as PNG…")) {
                return action;
            }
        }
        return nullptr;
    }

private Q_SLOTS:
    void mixedClipboard()
    {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        QWidget window;
        KFileItemActions fileActions;
        fileActions.setParentWidget(&window);
        fileActions.setItemListProperties(KFileItemListProperties({KFileItem(QUrl::fromLocalFile(dir.path()))}));

        QStringList excluded;
        const auto plugins = KPluginMetaData::findPlugins(QStringLiteral("kf6/kfileitemaction"));
        for (const auto &plugin : plugins) {
            if (plugin.name() != QStringLiteral("Paste Image as PNG")) {
                excluded.append(plugin.pluginId());
            }
        }
        auto clipboard = QApplication::clipboard();
        clipboard->setText(QStringLiteral("Caption"));
        QMenu textMenu;
        fileActions.addActionsTo(&textMenu, KFileItemActions::MenuActionSource::Plugins, {}, excluded);
        QVERIFY(!imageAction(textMenu));

        QImage image(3, 2, QImage::Format_RGBA8888);
        image.fill(QColor(60, 100, 200, 125));
        QBuffer encoded;
        QVERIFY(encoded.open(QIODevice::WriteOnly));
        QVERIFY(image.save(&encoded, "PNG"));
        auto mime = new QMimeData;
        mime->setText(QStringLiteral("Caption"));
        mime->setData(QStringLiteral("image/png"), encoded.data());
        clipboard->setMimeData(mime);

        QMenu imageMenu;
        fileActions.addActionsTo(&imageMenu, KFileItemActions::MenuActionSource::Plugins, {}, excluded);
        auto action = imageAction(imageMenu);
        QVERIFY(action);

        bool sawFilename = false;
        QTimer acceptDialog;
        connect(&acceptDialog, &QTimer::timeout, this, [&] {
            auto dialog = qobject_cast<QDialog *>(QApplication::activeModalWidget());
            if (dialog && dialog->findChild<QLineEdit *>()) {
                acceptDialog.stop();
                sawFilename = dialog->findChild<QLineEdit *>()->text() == QStringLiteral("Pasted image.png");
                clipboard->setText(QStringLiteral("New selection"));
                dialog->accept();
            }
        });
        acceptDialog.start(10);
        action->trigger();
        QFile saved(dir.filePath(QStringLiteral("Pasted image.png")));
        QTRY_VERIFY_WITH_TIMEOUT(saved.size() > 0, 8000);
        QVERIFY(sawFilename);
        QVERIFY(saved.open(QIODevice::ReadOnly));
        QCOMPARE(saved.readAll(), encoded.data());
        QCOMPARE(clipboard->text(), QStringLiteral("New selection"));
    }
};

QTEST_MAIN(PasteImageTest)
#include "pasteimagetest.moc"
