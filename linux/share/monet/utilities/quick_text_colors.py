"""Small local text transformations and a saved color palette."""
import json
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox,QLineEdit,QListWidget,QListWidgetItem,QPlainTextEdit
from notch_pages import Page,label,button,row
from actions import stored,tr

def transform_text(text,mode):
    if mode == "upper": return text.upper()
    if mode == "lower": return text.lower()
    if mode == "trim": return "\n".join(line.strip() for line in text.splitlines())
    if mode == "lines": return "\n".join(line for line in text.splitlines() if line.strip())
    if mode == "unique": return "\n".join(dict.fromkeys(text.splitlines()))
    raise ValueError("Unknown text operation")

class TextToolsPage(Page):
    def __init__(self,host):
        super().__init__(host)
        self.layout_box.addWidget(label(tr("Tidy text before you paste it."),True))
        self.edit=QPlainTextEdit(); self.edit.setPlaceholderText(tr("Paste or type text…")); self.edit.setAccessibleName(tr("Text to transform"))
        self.edit.setMinimumSize(0,100); self.edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.layout_box.addWidget(self.edit,1)
        self.count=label("",True); self.layout_box.addWidget(self.count)
        self.mode=QComboBox(); self.mode.setAccessibleName(tr("Text transformation"))
        for title,key in [("UPPERCASE","upper"),("lowercase","lower"),(tr("Trim line edges"),"trim"),(tr("Remove blank lines"),"lines"),(tr("Remove duplicate lines"),"unique")]: self.mode.addItem(title,key)
        row(self.layout_box,self.mode,button(tr("Apply"),self.apply))
        self.copy_button=button(tr("Copy text"),lambda:self.copy(self.edit.toPlainText(),tr("Text copied.")),True)
        row(self.layout_box,button(tr("Undo"),self.edit.undo),self.copy_button)
        self.edit.textChanged.connect(self.changed); self.changed()
    def changed(self):
        text=self.edit.toPlainText(); self.count.setText(tr("{words} words · {chars} characters").format(words=len(text.split()),chars=len(text)))
        self.copy_button.setEnabled(bool(text))
    def apply(self):
        cursor=self.edit.textCursor(); cursor.beginEditBlock(); cursor.select(cursor.SelectionType.Document)
        cursor.insertText(transform_text(self.edit.toPlainText(),self.mode.currentData())); cursor.endEditBlock()

def color_values(value):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}",value): return None
    color=QColor(value); h,s,l,_=color.getHslF()
    return [color.name().upper(),f"rgb({color.red()}, {color.green()}, {color.blue()})",f"hsl({round(max(h,0)*360)}, {round(s*100)}%, {round(l*100)}%)"]

class ColorToolsPage(Page):
    def __init__(self,host):
        super().__init__(host)
        self.layout_box.addWidget(label(tr("Convert a color and keep a palette for your projects."),True))
        self.input=QLineEdit("#72A99B"); self.input.setMaxLength(7); self.input.setAccessibleName(tr("Hex color")); self.input.setPlaceholderText("#72A99B")
        self.layout_box.addWidget(self.input)
        self.swatch=label(""); self.swatch.setFixedHeight(36); self.layout_box.addWidget(self.swatch)
        self.format=QComboBox(); self.format.addItems(["HEX","RGB","HSL"]); self.format.setAccessibleName(tr("Color format"))
        self.value=QLineEdit(); self.value.setReadOnly(True); self.value.setAccessibleName(tr("CSS color"))
        row(self.layout_box,self.format,self.value)
        self.copy_button=button(tr("Copy color"),lambda:self.copy(self.value.text(),tr("Color copied.")),True)
        self.save_button=button(tr("Save to palette"),self.save)
        row(self.layout_box,self.save_button,self.copy_button)
        self.palette_list=QListWidget(); self.palette_list.setAccessibleName(tr("Saved palette")); self.palette_list.setMaximumHeight(64); self.palette_list.setMinimumHeight(50)
        self.palette_list.itemClicked.connect(lambda item:self.input.setText(item.text())); self.layout_box.addWidget(self.palette_list,1)
        self.remove_button=button(tr("Remove selected color"),self.remove); self.layout_box.addWidget(self.remove_button)
        self.palette_list.itemSelectionChanged.connect(lambda:self.remove_button.setEnabled(bool(self.palette_list.selectedItems())))
        self.input.textChanged.connect(self.changed); self.format.currentIndexChanged.connect(self.changed)
        self.refresh(); self.changed()
    def changed(self):
        values=color_values(self.input.text()); self.copy_button.setEnabled(bool(values)); self.save_button.setEnabled(bool(values))
        self.value.setText(values[self.format.currentIndex()] if values else tr("Use #RRGGBB"))
        self.swatch.setStyleSheet("border-radius:12px; background:"+(values[0] if values else "#303035")+";")
    def refresh(self):
        self.settings.sync(); self.colors=[c for c in stored(self.settings,"notchPalette",[]) if isinstance(c,str) and color_values(c)][:12]
        self.palette_list.clear(); self.remove_button.setEnabled(False)
        for color in self.colors:
            item=QListWidgetItem(color); item.setData(Qt.DecorationRole,QColor(color)); self.palette_list.addItem(item)
    def save(self):
        values=color_values(self.input.text())
        if not values:return
        self.settings.setValue("notchPalette",json.dumps(list(dict.fromkeys([values[0],*self.colors]))[:12])); self.settings.sync(); self.refresh()
    def remove(self):
        item=self.palette_list.currentItem()
        if not item:return
        self.settings.setValue("notchPalette",json.dumps([c for c in self.colors if c!=item.text()])); self.settings.sync(); self.refresh()
