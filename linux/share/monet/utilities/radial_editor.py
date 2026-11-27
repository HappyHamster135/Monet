"""Edit one radial slot: category, action, then its name and symbol."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget)
from actions import tr
from radial_actions import CATALOG, CATEGORIES, ICONS, category, entry, normalize
from notch_settings_style import apply_style, heading_font, symbol


def text(value, muted=False):
    label=QLabel(tr(value));label.setWordWrap(True);label.setTextFormat(Qt.PlainText)
    label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);label.setProperty('muted',muted)
    return label


class ChoiceGrid(QWidget):
    def __init__(self, choices, callback, icons=False):
        super().__init__();self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(7)
        self.buttons={};self.columns=0;self.icons=icons
        for key,title,icon in choices:
            button=QPushButton('' if icons else tr(title).replace('&','&&'));button.setCheckable(True)
            button.setProperty('iconChoice' if icons else 'choice',True)
            button.setIcon(symbol(icon));button.setIconSize(QSize(21,21))
            button.setAccessibleName(tr(title));button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
            if icons:button.setFixedHeight(38)
            button.clicked.connect(lambda checked=False,key=key:callback(key));self.buttons[key]=button
        self.reflow()

    def select(self,key):
        for value,button in self.buttons.items():button.setChecked(key==value)

    def reflow(self):
        cell=46 if self.icons else max(140,max(button.fontMetrics().horizontalAdvance(button.text().replace('&&','&'))+52 for button in self.buttons.values()))
        columns=max(1,min(8 if self.icons else 3,self.width()//cell))
        if columns==self.columns:return
        old=self.columns;self.columns=columns
        for button in self.buttons.values():self.grid.removeWidget(button)
        for col in range(max(old,columns)):self.grid.setColumnStretch(col,1 if col<columns else 0)
        for index,button in enumerate(self.buttons.values()):self.grid.addWidget(button,index//columns,index%columns)
        self.setMinimumHeight(self.grid.sizeHint().height())

    def resizeEvent(self,event):super().resizeEvent(event);self.reflow()


class RadialSlotEditor(QDialog):
    def __init__(self, parent, index, value):
        super().__init__(parent);self.setObjectName('settingsPage');self.index=index
        self.original=normalize(value);self.result_value=dict(self.original);self.action=self.original.get('action','');self.icon=self.original.get('icon','')
        self.setWindowTitle(tr('Edit radial action'));self.setWindowModality(Qt.WindowModal)
        box=QVBoxLayout(self);box.setContentsMargins(22,20,22,18);box.setSpacing(14)
        self.title=text(tr('Slot {number}').format(number=index+1));self.title.setFont(heading_font(24));box.addWidget(self.title)
        box.addWidget(text('Choose a category, then the action this slot should run.',True))
        scroll=QScrollArea();scroll.setFrameShape(QFrame.NoFrame);scroll.setObjectName('settingsScroll')
        scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);box.addWidget(scroll,1)
        content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(0,0,7,0);layout.setSpacing(12)
        self.categories=ChoiceGrid(CATEGORIES,self.choose_category);layout.addWidget(self.section('Category'))
        self.category_button=QPushButton();self.category_button.setProperty('choice',True)
        self.category_button.clicked.connect(self.show_categories);layout.addWidget(self.category_button);layout.addWidget(self.categories)
        self.details=QWidget();layout.addWidget(self.details);details=QVBoxLayout(self.details)
        details.setContentsMargins(0,0,0,0);details.setSpacing(12)
        self.actions_title=self.section('Action');details.addWidget(self.actions_title)
        self.actions=QListWidget();self.actions.setObjectName('radialActions');self.actions.setAccessibleName(tr('Actions in this category'))
        self.actions.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.actions.setTextElideMode(Qt.ElideRight)
        self.actions.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel);self.actions.setIconSize(QSize(20,20))
        self.actions.setFixedHeight(146);self.actions.currentItemChanged.connect(self.choose_action);details.addWidget(self.actions)
        details.addWidget(self.section('Name'))
        self.name=QLineEdit(self.original.get('name',''));self.name.setMaxLength(64);self.name.setPlaceholderText(tr('Automatic'))
        self.name.setAccessibleName(tr('Action name'));details.addWidget(self.name)
        details.addWidget(self.section('Icon'))
        icons=[(key,tr('Automatic') if not key else key.replace('-',' ').capitalize(),key or 'view-refresh') for key in ICONS]
        self.icons=ChoiceGrid(icons,self.choose_icon,icons=True);self.icons.select(self.icon);details.addWidget(self.icons)
        layout.addStretch();scroll.setWidget(content)
        footer=QHBoxLayout();footer.setSpacing(10);box.addLayout(footer)
        self.remove_button=QPushButton(tr('Remove'));self.remove_button.setProperty('danger',True);self.remove_button.setEnabled(bool(self.original))
        self.remove_button.clicked.connect(self.remove);footer.addWidget(self.remove_button);footer.addStretch()
        cancel=QPushButton(tr('Cancel'));cancel.clicked.connect(self.reject);footer.addWidget(cancel)
        self.save_button=QPushButton(tr('Save'));self.save_button.setProperty('primary',True);self.save_button.clicked.connect(self.save);footer.addWidget(self.save_button)
        for button in (self.remove_button,cancel,self.save_button):button.setAutoDefault(False)
        if self.action:self.choose_category(category(self.action))
        else:self.show_categories()
        from window_interaction import install_interaction
        install_interaction(self);apply_style(self)
        area=self.screen().availableGeometry();self.resize(min(600,area.width()-32),min(740,area.height()-48))
        self.setMinimumSize(min(340,area.width()-32),min(360,area.height()-48))

    def section(self,title):
        result=text(title);result.setProperty('sectionTitle',True);return result

    def show_categories(self):
        self.categories.show();self.category_button.hide();self.details.hide();self.save_button.setEnabled(False)

    def choose_category(self,key):
        title,icon=next((title,icon) for value,title,icon in CATEGORIES if value==key)
        self.category_button.setText(tr(title).replace('&','&&')+'  ›');self.category_button.setIcon(symbol(icon))
        self.category_button.setAccessibleName(tr('Change category: {name}').format(name=tr(title)))
        self.categories.hide();self.category_button.show();self.details.show()
        self.categories.select(key);self.actions.blockSignals(True);self.actions.clear();selected=None
        for action,value in CATALOG.items():
            if category(action)!=key:continue
            item=QListWidgetItem(symbol(value.icon),value.name);item.setData(Qt.UserRole,action)
            item.setSizeHint(QSize(0,max(36,self.fontMetrics().height()+16)));self.actions.addItem(item)
            if action==self.action:selected=item
        self.actions.blockSignals(False)
        self.actions.setCurrentItem(selected)
        if selected is None:self.action=''
        self.save_button.setEnabled(bool(self.action))
        self.actions_title.setText(tr(dict((key,title) for key,title,_ in CATEGORIES)[key])+' · '+tr('Action'))

    def choose_action(self,item,*_):
        self.action=item.data(Qt.UserRole) if item else '';self.save_button.setEnabled(bool(self.action))
        self.title.setText(CATALOG[self.action].name if self.action else tr('Slot {number}').format(number=self.index+1))
        self.name.setPlaceholderText(CATALOG[self.action].name if self.action else tr('Automatic'))
        automatic=self.icons.buttons[''];automatic.setIcon(symbol(CATALOG[self.action].icon if self.action else 'view-refresh'))

    def choose_icon(self,key):self.icon=key;self.icons.select(key)

    def save(self):
        if not self.action:return
        self.result_value=normalize({'action':self.action,'name':self.name.text(),'icon':self.icon});self.accept()

    def remove(self):self.result_value={};self.accept()
