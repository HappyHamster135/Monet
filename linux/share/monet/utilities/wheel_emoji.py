"""A browsable emoji picker on the wheel's existing desktop surface."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from actions import tr
from notch_pages import EmojiPage
from notch_settings_style import apply_style, symbol


class WheelEmoji(QFrame):
    def __init__(self, wheel, host):
        super().__init__(wheel)
        self.setObjectName('settingsPage')
        layout=QVBoxLayout(self);layout.setContentsMargins(16,12,16,12);layout.setSpacing(8)
        header=QHBoxLayout();header.setSpacing(10)
        self.back=QPushButton();self.back.setIcon(symbol('go-previous','#edf4f1'))
        self.back.setAutoDefault(False)
        self.back.setAccessibleName(tr('Back to radial menu'));self.back.setFixedSize(34,34)
        self.back.clicked.connect(wheel.close_picker);header.addWidget(self.back)
        title=QLabel(tr('Emoji'));title.setProperty('sectionTitle',True);header.addWidget(title,1)
        self.close=QPushButton('×');self.close.setAccessibleName(tr('Close emoji picker'))
        self.close.setAutoDefault(False)
        self.close.setFixedSize(34,34);self.close.clicked.connect(wheel.hide);header.addWidget(self.close)
        layout.addLayout(header)
        self.page=EmojiPage(host);self.page.layout_box.setContentsMargins(0,0,0,0)
        self.page.layout_box.setSpacing(8);layout.addWidget(self.page,1)
        apply_style(self,dark=True)
        self.back.setStyleSheet('padding:0;border:0;background:transparent;')
        self.close.setStyleSheet('padding:0;border:0;background:transparent;font-size:22px;')
        self.page.grid.setStyleSheet('QListWidget {background:#252a30;border:0;border-radius:12px;padding:4px;}')
        self.page.caption.setStyleSheet('font-size:11px;color:#aeb9b8;')

    def focus_search(self):
        self.page.search.setFocus(Qt.ShortcutFocusReason)
