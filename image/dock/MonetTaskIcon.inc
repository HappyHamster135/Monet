// Included by the native task manager's backend.cpp.
QIcon Backend::monetTaskIcon(const QString &appId, const QIcon &decoration) const
{
    if (QIcon::themeName() != QLatin1String("Monet")) {
        return decoration;
    }

    // KDE uses the window's own pixels when a portable app has no installed
    // launcher. Its window ID can still identify a painting in Monet's theme.
    static const QRegularExpression iconName(QStringLiteral(R"(^[\w+-][\w.+-]*$)"));
    for (const auto &name : {decoration.name(), appId, appId.toLower()}) {
        if (!iconName.match(name).hasMatch()) {
            continue;
        }
        const auto path = QStandardPaths::locate(QStandardPaths::GenericDataLocation,
                                                 QStringLiteral("icons/Monet/apps/scalable/") + name + QStringLiteral(".svg"));
        if (!path.isEmpty()) {
            return QIcon::fromTheme(name, QIcon(path));
        }
    }

    // Reuse the canvas and relief used by Monet's generated launcher icons.
    // Cache the result by the original QIcon so other task roles can update
    // without repainting or decoding the same window icon again.
    if (decoration.isNull()) {
        return decoration;
    }
    static QCache<qint64, QIcon> framedIcons(64);
    if (const auto *cached = framedIcons.object(decoration.cacheKey())) {
        return *cached;
    }
    const auto texture = [](const QString &name) {
        return QPixmap(QStandardPaths::locate(QStandardPaths::GenericDataLocation,
                                             QStringLiteral("monet/textures/") + name));
    };
    static const QPixmap canvas = texture(QStringLiteral("frame-canvas.png"));
    static const QPixmap relief = texture(QStringLiteral("frame-relief.png"));
    if (canvas.isNull() || relief.isNull()) {
        return decoration;
    }
    const auto image = decoration.pixmap(QSize(152, 152));
    if (image.isNull()) {
        return decoration;
    }

    QPixmap result(256, 256);
    result.fill(Qt::transparent);
    QPainter painter(&result);
    painter.setRenderHint(QPainter::SmoothPixmapTransform);
    painter.drawPixmap(result.rect(), canvas);
    const QSize dimensions = image.size().scaled(QSize(152, 152), Qt::KeepAspectRatio);
    const QRect iconRect(QPoint((256 - dimensions.width()) / 2, (256 - dimensions.height()) / 2), dimensions);
    painter.drawPixmap(iconRect, image);
    painter.drawPixmap(result.rect(), relief);
    painter.end();

    const QIcon icon(result);
    framedIcons.insert(decoration.cacheKey(), new QIcon(icon));
    return icon;
}
