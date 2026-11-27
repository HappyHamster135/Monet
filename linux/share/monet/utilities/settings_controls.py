"""Native accessible checkboxes drawn as Monet switches in preferences."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QProxyStyle, QStyle, QStyleFactory


class SwitchStyle(QProxyStyle):
    def __init__(self,parent):
        super().__init__(QStyleFactory.create('Fusion'));self.setParent(parent)

    def pixelMetric(self,metric,option=None,widget=None):
        if isinstance(widget,QCheckBox):
            if metric==QStyle.PM_IndicatorWidth:return 38
            if metric==QStyle.PM_IndicatorHeight:return 22
        return super().pixelMetric(metric,option,widget)

    def drawPrimitive(self,element,option,painter,widget=None):
        if element!=QStyle.PE_IndicatorCheckBox or not isinstance(widget,QCheckBox):
            return super().drawPrimitive(element,option,painter,widget)
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        if not option.state & QStyle.State_Enabled:painter.setOpacity(.4)
        rect=QRectF(option.rect);rect.setWidth(38);rect.setHeight(22)
        on=bool(option.state & QStyle.State_On)
        painter.setPen(Qt.NoPen);painter.setBrush(QColor('#438f7d' if on else '#6b7075'))
        painter.drawRoundedRect(rect,11,11)
        painter.setBrush(QColor('#ffffff'));painter.drawEllipse(QRectF(rect.x()+(19 if on else 3),rect.y()+3,16,16))
        if option.state & QStyle.State_HasFocus:
            painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#89c5b3'),1))
            painter.drawRoundedRect(rect.adjusted(-2,-2,2,2),13,13)
        painter.restore()


def switches(page):
    style=SwitchStyle(page)
    for control in page.findChildren(QCheckBox):control.setStyle(style)
    page._switch_style=style
