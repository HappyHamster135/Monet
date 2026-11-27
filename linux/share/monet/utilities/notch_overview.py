"""A focused first page of grouped routes and desktop shortcuts."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)
from actions import tr
from notch_shortcuts import ShortcutCard


def label(text, muted=False):
    result = QLabel(tr(text)); result.setWordWrap(True); result.setProperty('muted',muted)
    result.setTextFormat(Qt.PlainText); result.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
    return result


class RouteCard(QPushButton):
    def __init__(self, title, detail, callback):
        super().__init__(); self.setProperty('routeCard',True)
        self.setAccessibleName(tr(title)); self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        box = QVBoxLayout(self); box.setContentsMargins(16,13,16,13); box.setSpacing(5)
        heading = label(title+'  ›'); font=heading.font(); font.setBold(True); heading.setFont(font)
        for child in (heading,label(detail,True)):
            child.setAttribute(Qt.WA_TransparentForMouseEvents); box.addWidget(child)
        self.clicked.connect(callback)

    def sizeHint(self):return self.layout().sizeHint()
    def minimumSizeHint(self):return self.layout().minimumSize()
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self.layout().totalHeightForWidth(width)


class Overview(QWidget):
    def __init__(self, owner, bridge, navigate):
        super().__init__(); self.bridge=bridge; self.setProperty('settingsDesigned',True)
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0); box.setSpacing(16)
        self.grids=[];self.cards=[]
        groups=[('Notch', [('Shape & size','Resize and preview your notch.','layout'),
                           ('Pages & buttons','Choose pages and arrange shortcuts.','content'),
                           ('Activity','Choose the closed notch’s indicators.','activity'),
                           ('Behavior','Set opening, gestures and navigation.','behavior')]),
                ('Quick access', [('Radial menu','Choose slots, categories and actions.','radial'),
                                  ('Tools & favorites','Choose the tools you want to keep.','tools')])]
        for title,routes in groups:
            heading=label(title);heading.setProperty('sectionTitle',True);box.addWidget(heading)
            grid=QGridLayout();grid.setSpacing(10);box.addLayout(grid)
            cards=[RouteCard(title,detail,lambda key=key:navigate(key)) for title,detail,key in routes]
            self.cards.extend(cards);self.grids.append((grid,cards))
        title=label('Keyboard shortcuts');title.setProperty('sectionTitle',True);box.addWidget(title)
        self.shortcuts=[ShortcutCard(owner,key) for key in ('radial','toggle')]
        for shortcut in self.shortcuts:box.addWidget(shortcut)
        self.columns=0;self.reflow();box.addStretch()

    def reflow(self):
        columns=2 if self.width() >= 510 else 1
        if columns == self.columns:return
        self.columns=columns
        for grid,cards in self.grids:
            for card in cards:grid.removeWidget(card)
            for index,card in enumerate(cards):grid.addWidget(card,index//columns,index%columns)
            grid.setColumnStretch(0,1);grid.setColumnStretch(1,1 if columns==2 else 0)

    def resizeEvent(self,event):
        super().resizeEvent(event);self.reflow()

    def refresh(self):
        for shortcut in self.shortcuts:shortcut.refresh()
