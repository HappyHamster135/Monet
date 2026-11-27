"""Quiet grouped settings, consistent symbols and Monet accent colors."""
from pathlib import Path
from functools import lru_cache
import re
from PySide6.QtCore import Qt, QStandardPaths, QRectF
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPixmap


def heading_font(size):
    font = QFont(QApplication.font())
    font.setPixelSize(size); font.setWeight(QFont.DemiBold)
    return font


@lru_cache(maxsize=1)
def glyphs():
    relative='plasma/plasmoids/org.monet.notch/contents/ui/IslandSymbols.js'
    candidates=[Path(__file__).resolve().parents[2]/relative,
                Path(QStandardPaths.locate(QStandardPaths.GenericDataLocation,relative))]
    source=next((path.read_text() for path in candidates if path.is_file()),'')
    paths=dict(re.findall(r"^    (\w+): '([^']+)'",source,re.M))
    aliases=dict(re.findall(r"'([^']+)':'([^']+)'",source))
    aliases.update({'spectacle':'camera','edit-clear':'clipboard','camera-photo':'camera','media-record':'record','face-smile':'emoji','media-playback-stop':'stop',
                    'preferences-desktop':'display','user-desktop':'window','utilities-system-monitor':'activity',
                    'input-keyboard':'keyboard','audio-input-microphone':'mic','audio-headphones':'headphones',
                    'audio-card':'headphones','audio-volume-low':'volume','go-home':'home','view-grid':'grid',
                    'view-more':'wheel','format-text-uppercase':'text','accessories-text-editor':'note',
                    'system-search':'search','system-lock-screen':'lock','rating':'star','emblem-favorite':'heart',
                    'weather-clear':'sun','list-remove':'minus','object-select-symbolic':'check',
                    'color-picker':'pipette','input-mouse':'mouse','view-history':'timer','internet-web-browser':'globe',
                    'mail-message-new':'mail','input-gaming':'game','preferences-system':'link',
                    'edit-select-text':'scan','media-optical':'compress','preferences-desktop-theme':'sun',
                    'preferences-desktop-wallpaper':'image','input-touchpad':'touchpad',
                    'preferences-system-windows':'window','application-exit':'close',
                    'preferences-desktop-keyboard':'shield','preferences-desktop-notification':'bell',
                    'preferences-system-bluetooth':'bluetooth','network-wired':'network','computer':'usb',
                    'system-run':'activity','text-x-script':'terminal'})
    paths.update(stop='M5 5h14v14H5Z',home='m3 10 9-8 9 8M5 8v13h5v-7h4v7h5V8',
                 star='m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z',
                 heart='M12 21 3 12C-3 4 8-1 12 7c4-8 15-3 9 5Z',minus='M4 12h16',check='m4 12 5 5L20 6',
                 globe='M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c-6 5-6 13 0 18 6-5 6-13 0-18Z',
                 mail='M2 5h20v14H2Zm0 0 10 8L22 5',
                 game='M7 6h10c3 0 4 4 5 10 0 4-3 4-6 0H8c-3 4-6 4-6 0 1-6 2-10 5-10ZM7 9v5m-2-2h4m7-1h.1m3 2h.1')
    return paths,aliases


def symbol(icon, color=None):
    return cached_symbol(icon,color or QApplication.palette().color(QPalette.Text).name())


@lru_cache(maxsize=256)
def cached_symbol(icon, color):
    paths,aliases=glyphs();path=paths.get(aliases.get(icon,icon))
    if not path:return QIcon.fromTheme(icon+'-symbolic',QIcon.fromTheme(icon))
    from PySide6.QtSvg import QSvgRenderer
    svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="'+path+
         '" fill="none" stroke="'+QColor(color).name()+'" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    pixmap=QPixmap(64,64);pixmap.fill(Qt.transparent);pixmap.setDevicePixelRatio(2)
    painter=QPainter(pixmap);QSvgRenderer(svg.encode()).render(painter,QRectF(0,0,32,32));painter.end()
    return QIcon(pixmap)


def badge(icon, category):
    pixmap=QPixmap(40,40);pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap);painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen);painter.setBrush(QColor('#294b43'));painter.drawRoundedRect(pixmap.rect(),11,11)
    painter.drawPixmap(9,9,symbol(icon,'#8ad1bd').pixmap(22,22));painter.end()
    return pixmap


def apply_style(window, dark=None):
    if dark is None:dark = QApplication.palette().color(QPalette.Window).lightness() < 128
    ink, dim, paper, sidebar, wash, line, accent = (
        ('#f0f1f2','#a6a9ad','#1e1f22','#25262a','#292b30','#3b3e43','#438f7d') if dark else
        ('#25292c','#6a7073','#f7f7f5','#eeefec','#ffffff','#dadeda','#357f72'))
    palette = QPalette(QApplication.palette())
    for role,color in ((QPalette.Window,paper),(QPalette.WindowText,ink),(QPalette.Text,ink),
                       (QPalette.Base,paper),(QPalette.Button,wash),(QPalette.ButtonText,ink),
                       (QPalette.Highlight,accent),(QPalette.PlaceholderText,dim)):
        palette.setColor(role,QColor(color))
    window.setPalette(palette)
    chevron=Path(__file__).with_name('settings-chevron.svg').as_posix()
    window.setStyleSheet(f'''
        QMainWindow {{background:{sidebar}; color:{ink};}}
        QDialog {{background:{paper}; color:{ink};}}
        QWidget#settingsSidebar {{background:transparent;}}
        QFrame#settingsPaper {{background:{paper}; border:0; border-radius:14px;}}
        QLabel {{color:{ink}; background:transparent;}}
        QLabel[muted="true"] {{color:{dim};}}
        QLabel#settingsBrand {{font-size:10px; font-weight:600; letter-spacing:3px; padding-bottom:5px;}}
        QListWidget#settingsNavigation {{border:0; background:transparent; color:{ink}; outline:0;}}
        QListWidget#settingsNavigation::item {{padding:7px 10px; border-radius:9px; border:1px solid transparent;}}
        QListWidget#settingsNavigation::item:selected {{background:{'#29483f' if dark else '#d8ebe3'}; color:{ink}; border-color:transparent;}}
        QListWidget#settingsNavigation::item:hover:!selected {{background:{wash};}}
        QLineEdit#settingsSearch {{background:{paper}; border:1px solid {line}; border-radius:12px; padding:9px 10px; color:{ink};}}
        QLineEdit#settingsSearch:focus {{border-color:{accent};}}
        QScrollArea#settingsScroll, QScrollArea#settingsScroll > QWidget > QWidget {{background:transparent; border:0;}}
        QWidget#settingsPage {{background:transparent; color:{ink};}}
        QDialog#settingsPage {{background:{paper}; color:{ink};}}
        QFrame#settingsCard {{background:{wash}; border:0; border-radius:18px;}}
        QScrollBar:vertical {{background:transparent; width:7px; margin:0;}}
        QScrollBar::handle:vertical {{background:{line}; min-height:28px; border-radius:3px;}}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:transparent;}}
        QWidget#settingsPage QLineEdit, QWidget#settingsPage QPlainTextEdit,
        QWidget#settingsPage QTextEdit, QWidget#settingsPage QComboBox,
        QWidget#settingsPage QSpinBox, QWidget#settingsPage QDoubleSpinBox {{
            background:{paper}; color:{ink}; border:1px solid {line}; border-radius:10px; padding:7px;
            selection-background-color:{accent};}}
        QWidget#settingsPage QPushButton {{background:{wash}; color:{ink}; border:1px solid {line}; border-radius:11px; padding:9px 13px;}}
        QWidget#settingsPage QPushButton:hover {{border-color:{accent};}}
        QWidget#settingsPage QPushButton:focus {{border:2px solid {accent}; padding:8px 12px;}}
        QWidget#settingsPage QPushButton[routeCard="true"] {{text-align:left; background:{wash}; border:1px solid transparent; border-radius:14px; padding:0;}}
        QWidget#settingsPage QPushButton[routeCard="true"]:hover, QWidget#settingsPage QPushButton[routeCard="true"]:focus {{border-color:{accent}; background:{paper};}}
        QWidget#settingsPage QPushButton[radialSlot="true"] {{padding:2px; border:1px solid #4a5358; border-radius:12px; background:#30363d;}}
        QWidget#settingsPage QPushButton[radialSlot="true"]:checked {{border:2px solid #7dcab4; background:#36594f;}}
        QWidget#settingsPage QPushButton[primary="true"] {{background:{accent}; color:white; border-color:{accent};}}
        QWidget#settingsPage QPushButton:disabled {{color:{dim};}}
        QWidget#settingsPage QPushButton[choice="true"] {{padding:8px 10px; text-align:left;}}
        QWidget#settingsPage QPushButton[choice="true"]:checked {{border:1px solid {accent}; background:{sidebar}; color:{accent};}}
        QWidget#settingsPage QPushButton[iconChoice="true"] {{padding:4px; border-radius:9px;}}
        QWidget#settingsPage QPushButton[iconChoice="true"]:checked {{border:2px solid {accent}; background:{sidebar};}}
        QWidget#settingsPage QPushButton[danger="true"] {{color:#e66e72;}}
        QWidget#settingsPage QListWidget#radialActions::item:selected {{background:{accent}; color:white; border-radius:7px;}}
        QWidget#settingsPage QListWidget#radialActions::item:hover:!selected {{background:{wash};}}
        QLabel[sectionTitle="true"] {{font-weight:600; font-size:15px;}}
        QWidget#settingsPage QCheckBox {{color:{ink}; spacing:12px; padding:8px 0;}}
        QWidget#settingsPage QComboBox {{padding-right:24px; min-height:22px;}}
        QWidget#settingsPage QComboBox::drop-down {{border:0; width:26px;}}
        QWidget#settingsPage QComboBox::down-arrow {{image:url("{chevron}");width:12px;height:8px;}}
        QWidget#settingsPage QSpinBox, QWidget#settingsPage QDoubleSpinBox {{padding-right:28px; min-height:22px;}}
        QWidget#settingsPage QSlider::groove:horizontal {{height:5px; background:{line}; border-radius:2px;}}
        QWidget#settingsPage QSlider::sub-page:horizontal {{background:{accent}; border-radius:2px;}}
        QWidget#settingsPage QSlider::handle:horizontal {{width:18px; margin:-7px 0; border-radius:9px; background:{ink};}}
        QWidget#settingsPage QTreeView, QWidget#settingsPage QListWidget {{background:{paper}; color:{ink}; border:1px solid {line}; border-radius:12px;}}
        QWidget#settingsPage QTreeView::item, QWidget#settingsPage QListWidget::item {{padding:7px;}}
        QWidget#settingsPage QTreeView::item:selected {{background:{'#29483f' if dark else '#d8ebe3'};color:{ink};}}
        QWidget#settingsPage QHeaderView::section {{background:{wash};color:{dim};border:0;border-bottom:1px solid {line};padding:12px 8px;}}
        QWidget#settingsPage QGroupBox {{background:{wash}; border:0; border-radius:14px; margin-top:16px; padding:18px 12px 12px; color:{ink};}}
        QWidget#settingsPage QGroupBox::title {{subcontrol-origin:margin; left:12px;}}
        QWidget#settingsPage QTabWidget::pane {{border:0;background:transparent;}}
        QWidget#settingsPage QTabBar::tab {{background:{wash};color:{dim};border:0;border-radius:8px;padding:9px 14px;margin:0 3px 10px 0;}}
        QWidget#settingsPage QTabBar::tab:selected {{background:{'#29483f' if dark else '#d8ebe3'};color:{ink};}}
        QStatusBar {{background:transparent; color:{dim};}}
    ''')
