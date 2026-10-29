// More Settings' QWidget modules, drawn by the user's existing Qt style.
// Keep their minimum layout sizes inside KDE's scrolling module host. In
// particular, plasma-nm's KCMForm sets a 100px minimum that would otherwise
// override the much wider minimum of its children, clipping even at scroll end.
#include <QApplication>
#include <QFormLayout>
#include <QProxyStyle>
#include <QScrollArea>
#include <QScrollBar>
#include <QSettings>
#include <QStandardPaths>
#include <QStyleFactory>
#include <QStylePlugin>
#include <QTabWidget>
#include <QWheelEvent>
#include "backgrounddrag.h"

class SettingsStyle : public QProxyStyle {
public:
    explicit SettingsStyle(QStyle *base) : QProxyStyle(base), backgroundDrag(this) {}

    int styleHint(StyleHint hint, const QStyleOption *option = nullptr,
                  const QWidget *widget = nullptr, QStyleHintReturn *data = nullptr) const override
    {
        if (hint == SH_FormLayoutWrapPolicy)
            return QFormLayout::WrapLongRows;
        return QProxyStyle::styleHint(hint, option, widget, data);
    }

    void polish(QApplication *app) override
    {
        QProxyStyle::polish(app);
        app->installEventFilter(this);
        app->installEventFilter(&backgroundDrag);
    }

    void unpolish(QApplication *app) override
    {
        app->removeEventFilter(this);
        app->removeEventFilter(&backgroundDrag);
        QProxyStyle::unpolish(app);
    }

    void polish(QWidget *widget) override
    {
        QProxyStyle::polish(widget);
        if (auto tabs = qobject_cast<QTabWidget *>(widget)) {
            widget->setProperty("_monetOriginalTabScroll", tabs->usesScrollButtons());
            tabs->setUsesScrollButtons(true);
        }
        // An explicit minimum overrides Qt's layout-derived minimum in a
        // QScrollArea. Let the layout maintain it as pages/fields are added.
        // Leave intentionally fixed-size widgets and module-owned constraints alone.
        if (widget->layout() && widget->minimumWidth() > 0
            && widget->maximumWidth() == QWIDGETSIZE_MAX
            && widget->layout()->sizeConstraint() == QLayout::SetDefaultConstraint) {
            for (auto parent = widget->parentWidget(); parent; parent = parent->parentWidget()) {
                if (qobject_cast<QScrollArea *>(parent)) {
                    widget->setProperty("_monetLayoutMinimum", true);
                    widget->setProperty("_monetOriginalMinimum", widget->minimumSize());
                    widget->layout()->setSizeConstraint(QLayout::SetMinimumSize);
                    break;
                }
            }
        }
        if (auto bar = qobject_cast<QScrollBar *>(widget)) {
            widget->setProperty("_monetOriginalFocus", int(bar->focusPolicy()));
            bar->setFocusPolicy(Qt::StrongFocus);
        }
    }

    void unpolish(QWidget *widget) override
    {
        if (auto tabs = qobject_cast<QTabWidget *>(widget); tabs && widget->property("_monetOriginalTabScroll").isValid()) {
            tabs->setUsesScrollButtons(widget->property("_monetOriginalTabScroll").toBool());
            widget->setProperty("_monetOriginalTabScroll", QVariant());
        }
        if (widget->property("_monetLayoutMinimum").toBool() && widget->layout()) {
            widget->layout()->setSizeConstraint(QLayout::SetDefaultConstraint);
            widget->setMinimumSize(widget->property("_monetOriginalMinimum").toSize());
            widget->setProperty("_monetLayoutMinimum", QVariant());
        }
        if (widget->property("_monetOriginalFocus").isValid()) {
            widget->setFocusPolicy(Qt::FocusPolicy(widget->property("_monetOriginalFocus").toInt()));
            widget->setProperty("_monetOriginalFocus", QVariant());
        }
        QProxyStyle::unpolish(widget);
    }

    QSize sizeFromContents(ContentsType type, const QStyleOption *option, const QSize &size,
                           const QWidget *widget = nullptr) const override
    {
        auto result = QProxyStyle::sizeFromContents(type, option, size, widget);
        if (type == CT_TabWidget && northTabs(widget))
            result.rheight() += tabGap;
        return result;
    }

    QRect subElementRect(SubElement element, const QStyleOption *option,
                         const QWidget *widget = nullptr) const override
    {
        auto rect = QProxyStyle::subElementRect(element, option, widget);
        if (northTabs(widget)) {
            if (element == SE_TabWidgetTabBar)
                rect.translate(0, 8);
            else if (element == SE_TabWidgetTabPane || element == SE_TabWidgetTabContents)
                rect.adjust(0, tabGap, 0, 0);
        }
        return rect;
    }

protected:
    bool eventFilter(QObject *object, QEvent *event) override
    {
        // Shift+wheel pans a wide module from anywhere on its form, including
        // spin boxes and combo boxes, without changing the setting under the pointer.
        if (event->type() == QEvent::Wheel) {
            auto wheel = static_cast<QWheelEvent *>(event);
            if (wheel->modifiers() == Qt::ShiftModifier) {
                for (auto widget = qobject_cast<QWidget *>(object); widget; widget = widget->parentWidget()) {
                    if (auto area = qobject_cast<QScrollArea *>(widget)) {
                        auto bar = area->horizontalScrollBar();
                        if (bar->maximum() > bar->minimum()) {
                            const auto pixels = wheel->pixelDelta();
                            const auto angle = wheel->angleDelta();
                            const int delta = !pixels.isNull() ? (pixels.x() ? pixels.x() : pixels.y())
                                : (angle.x() ? angle.x() : angle.y()) * bar->singleStep() / 40;
                            bar->setValue(bar->value() - delta);
                            wheel->accept();
                            return true;
                        }
                    }
                }
            }
        }
        return QProxyStyle::eventFilter(object, event);
    }

private:
    BackgroundDrag backgroundDrag;
    static constexpr int tabGap = 16;
    static bool northTabs(const QWidget *widget)
    {
        auto tabs = qobject_cast<const QTabWidget *>(widget);
        return tabs && tabs->tabPosition() == QTabWidget::North;
    }
};

class SettingsStylePlugin : public QStylePlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QStyleFactoryInterface" FILE "monetsettings.json")
public:
    QStyle *create(const QString &key) override
    {
        if (key.compare("MonetSettings", Qt::CaseInsensitive) != 0)
            return nullptr;
        const auto path = QStandardPaths::locate(QStandardPaths::GenericConfigLocation, "kdeglobals");
        QSettings settings(path, QSettings::IniFormat);
        auto name = settings.value("KDE/widgetStyle", "kvantum").toString();
        if (name.compare("MonetSettings", Qt::CaseInsensitive) == 0)
            name = "kvantum";
        auto base = QStyleFactory::create(name);
        return new SettingsStyle(base ? base : QStyleFactory::create("Fusion"));
    }
};

#include "monetsettings.moc"
