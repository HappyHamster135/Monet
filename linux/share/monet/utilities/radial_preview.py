"""An editable wheel with stable slots and a readable center label."""
import math
from PySide6.QtCore import Qt, QSize, QRectF, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget
from actions import tr
from radial_actions import entry, normalize
from notch_settings_style import symbol


class RadialPreview(QWidget):
    selected = Signal(int)

    def __init__(self):
        super().__init__(); self.index = 0; self.keys = [''] * 8; self.records = [{}] * 8; self.buttons = []
        self.setFixedHeight(320); self.setMinimumWidth(0)
        self.caption = QLabel(self); self.caption.setWordWrap(True); self.caption.setAlignment(Qt.AlignCenter)
        self.caption.setStyleSheet('color:#f2f3f4;background:transparent;font-size:12px;')
        self.caption.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        for index in range(8):
            button = QPushButton(self); button.setProperty('radialSlot', True)
            button.setCheckable(True); button.setIconSize(QSize(23,23))
            button.clicked.connect(lambda checked=False,index=index:self.choose(index)); self.buttons.append(button)
        self.update_slots(self.records)

    def choose(self, index):
        self.index = index; self.update_slots(self.records); self.selected.emit(index)

    def update_slots(self, records):
        self.records = [normalize(value) for value in records]; self.keys = [value.get('action','') for value in self.records]
        for index,(button,value) in enumerate(zip(self.buttons,self.records)):
            item = entry(value)
            button.setIcon(symbol(item.icon_name or 'list-add', '#eef4f1'))
            button.setText(''); button.setChecked(index == self.index)
            button.setAccessibleName(tr('Slot {number}: {name}').format(number=index+1,name=item.title))
        item = entry(self.records[self.index])
        self.caption.setText(tr('Slot {number}').format(number=self.index+1)+'\n'+item.title)
        self.update()

    def paintEvent(self, event):
        paint = QPainter(self); paint.setRenderHint(QPainter.Antialiasing)
        paint.setPen(Qt.NoPen); paint.setBrush(QColor('#1b1e23'))
        paint.drawRoundedRect(QRectF(self.rect()),14,14)
        from radial_art import RingGeometry, paint_ring
        radius = min(140, (self.width()-16)/2); cx = self.width()/2; cy = self.height()/2
        geometry=RingGeometry(QRectF(cx-radius-8,cy-radius-8,2*radius+16,2*radius+16))
        paint_ring(paint,geometry,self.index)
        paint.setPen(QColor('#8c9b9f'))
        font=paint.font();font.setPixelSize(10);paint.setFont(font)
        for index in range(8):
            angle=index*math.pi/4-math.pi/2
            x=cx+math.cos(angle)*(radius-12);y=cy+math.sin(angle)*(radius-12)
            paint.drawText(QRectF(x-8,y-7,16,14),Qt.AlignCenter,str(index+1))
        paint.end()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        size=44;radius=min(98,max(60,(self.width()-74)/2));cy=self.height()/2
        for index,button in enumerate(self.buttons):
            angle=index*math.pi/4-math.pi/2
            button.setGeometry(round(self.width()/2+math.cos(angle)*radius-size/2),round(cy+math.sin(angle)*radius-size/2),size,size)
        self.caption.setGeometry(round(self.width()/2-45),round(cy-41),90,82)
