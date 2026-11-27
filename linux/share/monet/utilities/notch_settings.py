"""A dedicated, searchable home for notch and everyday tool preferences."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QEvent,QObject,Property,QProcess,QSize,Qt,QTimer,QUrl,Signal,Slot
from PySide6.QtDBus import QDBus,QDBusConnection,QDBusMessage
from PySide6.QtGui import QIcon,QKeySequence,QShortcut
from PySide6.QtWidgets import (QAbstractItemView,QApplication,QBoxLayout,QCheckBox,QComboBox,QFormLayout,QFrame,QHBoxLayout,
    QHeaderView,QLabel,QLayout,QLineEdit,QListWidget,QListWidgetItem,QMainWindow,QPushButton,QScrollArea,QSizePolicy,
    QSplitter,QStackedWidget,QTreeWidget,QTreeWidgetItem,QVBoxLayout,QWidget)
from actions import ACTIONS,FULL_APPLICATIONS,preferences,tr
from tool_pages import SETTINGS_GROUPS, create_tool_page, activate_tool_page
from notch_settings_style import apply_style, heading_font, badge, symbol
from notch_preferences import RADIAL_PRESETS,save_radial,announce

BACKEND = None
SERVICE = 'org.monet.NotchSettings'

def present(page):
    bus = QDBusConnection.sessionBus()
    if not bus.interface().isServiceRegistered(SERVICE).value():
        return False
    message = QDBusMessage.createMethodCall(SERVICE, '/Settings', SERVICE, 'Show')
    message.setArguments([page])
    return bus.call(message, QDBus.Block, 3000).type() != QDBusMessage.ErrorMessage

def open_settings(owner, modules, page):
    if present(page):
        owner.panelDismissed.emit()
        return
    launched = QProcess.startDetached(sys.executable, [str(Path(__file__).resolve()),
        str(modules), str(owner.helpers), page])[0]
    if launched:
        owner.panelDismissed.emit()
    else:
        owner.issue(tr('Could not open Notch & Tools settings.'))

class LayoutBridge(QObject):
    changed=Signal()
    pageRequested=Signal(int)
    def __init__(self,owner):
        super().__init__(owner); self.owner=owner; self._state={};self._screens=[];self._busy=False;self._problem="";self._page=0;self.selected=0
    state=Property('QVariantMap',lambda self:self._state,notify=changed)
    screens=Property('QVariantList',lambda self:self._screens,notify=changed)
    busy=Property(bool,lambda self:self._busy,notify=changed)
    problem=Property(str,lambda self:self._problem,notify=changed)
    page=Property(int,lambda self:self._page,notify=changed)
    def call(self,args,done):
        self._busy=True; self.changed.emit()
        def failed(message):
            self._busy=False;self._problem=message;self.changed.emit()
        def received(out):
            self._busy=False
            self._problem=""
            try: done(json.loads(out))
            except (ValueError,TypeError,KeyError): self._problem=tr("Could not load notch settings. Try reopening this page.")
            self.changed.emit()
        self.owner.worker([BACKEND or self.owner.helpers/'monet-quick',*args],received,failed)
    def discover(self):
        def received(rows):
            if not isinstance(rows,list):raise ValueError()
            self._screens=[dict(row,label=tr("Display {number}").format(number=row['screen']+1)) for row in rows]
            if rows:self.request("")
            else:self._problem=tr("No desktop panel was found.")
        self.call(['notch-screens'],received)
    @Slot(int)
    def selectScreen(self,index):
        if not self._busy and 0<=index<len(self._screens):self.selected=index;self.request("")
    @Slot(str)
    def request(self,command):
        if not self._screens or self._busy:return
        def received(state):
            if not isinstance(state,dict) or state.get('ok') is not True:raise ValueError()
            self._state=state
        self.call(['panel-notch',str(self._screens[self.selected]['id']),*([command] if command else [])],received)
    def show_page(self,page):
        self._page=page;self.changed.emit()
        if not self._screens and not self._busy:self.discover()
    @Slot(int)
    def selectPage(self,page):
        if 0 <= page < 4 and page != self._page:
            self._page=page;self.changed.emit();self.pageRequested.emit(page)

def help_label(text):
    label=QLabel(text);label.setTextFormat(Qt.PlainText);label.setWordWrap(True);label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);return label

class SettingsScroll(QScrollArea):
    """Keep wrapped help above its controls at the user's font and scale."""
    def __init__(self, page):
        super().__init__()
        self.setObjectName("settingsScroll")
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        if page.layout() is None:
            wrapper=QWidget();layout=QVBoxLayout(wrapper);layout.setContentsMargins(0,0,0,0);layout.addWidget(page)
            page=wrapper
        page.layout().setSizeConstraint(QLayout.SetNoConstraint)
        self.rows = []
        def collect(layout):
            if isinstance(layout, QHBoxLayout):
                self.rows.append(layout)
            for index in range(layout.count()):
                child = layout.itemAt(index).layout()
                if child:
                    collect(child)
        collect(page.layout())
        self.setWidget(page)
        from notch_style import ResponsiveTool
        self.reflow=ResponsiveTool(page,self)
        self.settle = QTimer(self)
        self.settle.setSingleShot(True)
        self.settle.timeout.connect(self.fit)
        self.viewport().installEventFilter(self)
        page.installEventFilter(self)
        self.settle.start(0)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest) and not self.settle.isActive():
            self.settle.start(0)
        return super().eventFilter(watched, event)

    def fit(self):
        page = self.widget()
        page.setFixedWidth(max(1, self.viewport().width()))
        layout = page.layout()
        for row in self.rows:
            natural = sum(max(row.itemAt(i).minimumSize().width(),
                              row.itemAt(i).widget().minimumSizeHint().width() if row.itemAt(i).widget() else 0)
                          for i in range(row.count())) + (row.count()-1)*row.spacing()
            row.setDirection(QBoxLayout.TopToBottom if natural > page.width()-20 else QBoxLayout.LeftToRight)
        layout.activate()
        for label in page.findChildren(QLabel):
            if label.wordWrap() and label.isVisibleTo(page):
                label.setMinimumHeight(max(0, label.heightForWidth(max(1, label.width()))))
        page.setMinimumHeight(max(layout.minimumSize().height(), layout.heightForWidth(page.width())))
        layout.activate()

class ToolsPreferences(QWidget):
    def __init__(self,owner):
        super().__init__(); self.owner=owner;self.loading=False
        box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0)
        box.addWidget(help_label(tr("Choose what appears in Tools and Favorites. Existing favorite order is kept.")))
        self.search=QLineEdit();self.search.setPlaceholderText(tr("Find a tool…"));box.addWidget(self.search)
        self.tree=QTreeWidget();self.tree.setHeaderLabels([tr("Tool"),tr("Show"),tr("Favorite")]);self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(False);self.tree.setUniformRowHeights(True);self.tree.setAccessibleName(tr("Visible tools and favorites"))
        self.tree.setIndentation(0);self.tree.setFrameShape(QFrame.NoFrame)
        self.tree.header().setSectionResizeMode(0,QHeaderView.Stretch)
        for col in (1,2):self.tree.header().setSectionResizeMode(col,QHeaderView.ResizeToContents)
        box.addWidget(self.tree,1);self.message=help_label("");box.addWidget(self.message)
        self.tree.itemChanged.connect(self.save);self.search.textChanged.connect(self.filter);self.refresh()
    def refresh(self):
        self.loading=True;self.owner.settings.sync();favorites,hidden=preferences(self.owner.settings);self.tree.clear()
        for key,action in sorted(ACTIONS.items(),key=lambda p:p[1].name.casefold()):
            if key=='notch-settings' or key in FULL_APPLICATIONS:continue
            item=QTreeWidgetItem([action.name]);item.setData(0,Qt.UserRole,key);item.setIcon(0,symbol(action.icon));item.setSizeHint(0,QSize(0,48))
            item.setCheckState(1,Qt.Unchecked if key in hidden else Qt.Checked);item.setCheckState(2,Qt.Checked if key in favorites else Qt.Unchecked)
            self.tree.addTopLevelItem(item)
        self.loading=False;self.filter()
    def filter(self):
        query=self.search.text().casefold()
        for i in range(self.tree.topLevelItemCount()):
            item=self.tree.topLevelItem(i);item.setHidden(query not in item.text(0).casefold())
    def save(self,*_):
        if self.loading:return
        self.loading=True
        old,old_hidden=preferences(self.owner.settings);hidden=[k for k in old_hidden if k in FULL_APPLICATIONS];favorites=[k for k in old if k in FULL_APPLICATIONS]
        for i in range(self.tree.topLevelItemCount()):
            item=self.tree.topLevelItem(i);key=item.data(0,Qt.UserRole)
            if item.checkState(1)!=Qt.Checked:
                hidden.append(key);item.setCheckState(2,Qt.Unchecked)
            elif item.checkState(2)==Qt.Checked:favorites.append(key)
        self.loading=False
        self.owner.hidden=hidden; self.owner.settings.setValue('hidden',json.dumps(hidden))
        self.owner.save_favorites([k for k in old if k in favorites]+[k for k in favorites if k not in old])
        announce();self.message.setText(tr("Saved. The notch and Quick Panel use these choices."))
        if ('awake' in old_hidden)!=('awake' in hidden) and self.owner.settings.contains('awakeRules'):
            self.owner.worker([self.owner.helpers/'monet-quick','keep-awake-rules'],lambda _:None,finish_on_close=True)

class RadialPreferences(QWidget):
    def __init__(self,owner,inline=False):
        super().__init__();self.owner=owner;self.editor=None;self.setProperty('settingsDesigned',True)
        box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0);box.setSpacing(16)
        from notch_shortcuts import ShortcutCard
        from radial_preview import RadialPreview
        from notch_overview import label
        self.shortcut=ShortcutCard(owner,'radial');box.addWidget(self.shortcut)
        card=QFrame();card.setObjectName('settingsCard');contents=QVBoxLayout(card);contents.setContentsMargins(16,16,16,16);contents.setSpacing(12)
        top=QHBoxLayout();title=label('Your menu');title.setProperty('sectionTitle',True);top.addWidget(title,1)
        desktop=QPushButton(tr('Try menu'));desktop.clicked.connect(lambda:owner.Open(['radial']));desktop.setVisible(not inline);top.addWidget(desktop)
        contents.addLayout(top);self.preview=RadialPreview();contents.addWidget(self.preview)
        contents.addWidget(help_label(tr('Click any slot to choose a category and an action. Customize its name and icon before saving.')))
        self.message=label('',True);contents.addWidget(self.message);box.addWidget(card)
        self.preview.selected.connect(self.select_slot)
        starter=QPushButton(tr('Starter layouts'));starter.setCheckable(True);box.addWidget(starter)
        self.presets=QWidget();presets=QVBoxLayout(self.presets);presets.setContentsMargins(0,0,0,0)
        presets.addWidget(label('Replace all eight slots with a starter layout.',True))
        from radial_editor import ChoiceGrid
        self.preset_grid=ChoiceGrid([(name,name,'view-grid') for name in RADIAL_PRESETS],lambda name:self.preset(RADIAL_PRESETS[name]))
        presets.addWidget(self.preset_grid);box.addWidget(self.presets);self.presets.hide();starter.toggled.connect(self.presets.setVisible)
        box.addWidget(label('Open at your pointer with the shortcut. Click an action or press 1–8. Esc closes the menu.',True))
        box.addStretch();self.refresh()

    def refresh(self):
        from notch_preferences import radial_records
        self.shortcut.refresh();self.owner.settings.sync();self.preview.update_slots(radial_records(self.owner.settings))

    def select_slot(self,index):
        from radial_editor import RadialSlotEditor
        from notch_preferences import radial_records,save_radial_records
        if self.editor:
            self.editor.raise_();return
        self.editor=RadialSlotEditor(self,index,radial_records(self.owner.settings)[index])
        def finished(result):
            editor=self.editor
            if result:
                self.owner.settings.sync();values=radial_records(self.owner.settings);values[index]=editor.result_value
                save_radial_records(self.owner.settings,values);announce();self.refresh()
                self.message.setText(tr('Slot {number} saved.').format(number=index+1))
            self.editor=None;editor.deleteLater()
        self.editor.finished.connect(finished);self.editor.open()

    def preset(self,keys):
        save_radial(self.owner.settings,list(keys));announce();self.refresh();self.message.setText(tr('Starter layout applied.'))

class NotchSettingsWindow(QMainWindow):
    SEARCH_TERMS = {
        'layout':'size width height corner resize shape compact spacious',
        'content':'buttons sections order left right shortcuts',
        'activity':'companion alerts music timer notifications idle',
        'behavior':'opening hover click gestures reopen navigation',
        'tools':'show hide visible favorites', 'radial':'wheel quick actions presets keyboard',
        'awake':'sleep power automatic rules applications display', 'cleaning':'keyboard input screen pause',
        'clipboard':'privacy expiry clear lock sleep', 'text-tools':'uppercase lowercase trim lines words',
        'color-tools':'hex rgb hsl css saved colors palette'
    }
    DETAILS = {key:detail for group,entries in SETTINGS_GROUPS for key,detail in entries}
    DETAILS.update(layout='Shape your notch and preview its size on your desktop.',
                   overview='Personalize your notch, shortcuts and everyday tools.',
                   content='Choose pages, arrange buttons and add shortcuts.',
                   activity='Choose what appears while your notch is resting.',
                   behavior='Choose how the notch opens and behaves.',
                   tools='Keep useful compact tools close at hand. Full apps stay in desktop Utilities.',
                   radial='A floating menu at your pointer. Open it with your own shortcut, anywhere on the desktop.')
    TITLES={'clipboard-expiry':'Clipboard privacy','record':'Screen recording','screenshot':'Screenshot',
            'ocr':'Screen text & QR codes','color':'Color picker','sound':'Sound','output-order':'Output order',
            'mouse':'Mouse','touchpad':'Touchpad','windows':'Window focus','display':'Displays',
            'power':'Power & battery','theme':'Appearance','notifications':'Notifications','agents':'AI agents',
            'extra-clicks':'Extra clicks','wheel-scrolling':'Wheel scrolling','quit-on-close':'Quit on close',
            'quit-protection':'Quit protection','fans':'Fan control','devices':'USB devices','downloads':'Downloads',
            'ports':'Listening ports','process-control':'Processes','calendars':'Calendars','emoji':'Emoji','wallpaper':'Wallpapers','watch':'Watch a window'}
    ROUTES=[('overview','Overview','Notch','go-home'),('layout','Layout','Notch','preferences-desktop'),('content','Pages & shortcuts','Notch','view-grid'),
        ('activity','Activity','Notch','view-history'),('behavior','Behavior','Notch','input-mouse'),
        ('tools','Tools & favorites','Notch','rating'),('radial','Radial menu','Quick access','view-more')]
    for group,entries in SETTINGS_GROUPS:
        for key,detail in entries:
            action = ACTIONS['lock' if key == 'cleaning' else key]
            ROUTES.append((key,TITLES.get(key,action.source_name),group,action.icon))
    # Keep links from earlier versions working.
    ALIASES = {'clipboard':'clipboard-expiry','recordings':'record','lock':'cleaning','wheel-settings':'radial'}
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.pages={};self.containers={};self.bridge=LayoutBridge(owner)
        from window_interaction import install_interaction
        install_interaction(self)
        owner.compact_pages=self.pages
        self.setAttribute(Qt.WA_QuitOnClose,False);self.setWindowTitle(tr("Notch & Tools — Monet"));self.setWindowIcon(QIcon.fromTheme('configure'))
        self.resize(980,760);self.setMinimumSize(640,460)
        central=QWidget();self.setCentralWidget(central);layout=QHBoxLayout(central);layout.setContentsMargins(10,10,10,10);layout.setSpacing(10)
        side=QWidget();side.setObjectName('settingsSidebar');side.setFixedWidth(218);side_box=QVBoxLayout(side);side_box.setContentsMargins(8,14,8,0)
        brand=QLabel(tr('MONET'));brand.setProperty('muted',True);brand.setObjectName('settingsBrand');side_box.addWidget(brand)
        sidebar_title=QLabel(tr('Notch & Tools'));sidebar_title.setFont(heading_font(20));side_box.addWidget(sidebar_title)
        side_box.addSpacing(12)
        self.search=QLineEdit();self.search.setObjectName("settingsSearch");self.search.setPlaceholderText(tr("Search settings…"));self.search.setClearButtonEnabled(True);side_box.addWidget(self.search)
        self.no_matches=help_label(tr('No matching settings.'));self.no_matches.setVisible(False);side_box.addWidget(self.no_matches)
        self.navigation=QListWidget();self.navigation.setObjectName("settingsNavigation");self.navigation.setFrameShape(QFrame.NoFrame);self.navigation.setSpacing(3);side_box.addWidget(self.navigation,1)
        nav_font=self.navigation.font();nav_font.setPixelSize(14);self.navigation.setFont(nav_font)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.navigation.setIconSize(QSize(18,18))
        last=''
        for key,title,group,icon in self.ROUTES:
            if group!=last:
                header=QListWidgetItem(tr(group));header.setFlags(Qt.NoItemFlags);font=header.font();font.setBold(True);header.setFont(font)
                header.setSizeHint(QSize(0,32));self.navigation.addItem(header);last=group
            short_titles={'content':'Pages','tools':'Tools & favorites','clipboard-expiry':'Clipboard','link-settings':'Copied links'}
            item=QListWidgetItem(symbol(icon),tr(short_titles.get(key,title)));item.setData(Qt.UserRole,key)
            item.setSizeHint(QSize(0,max(40,self.fontMetrics().height()+20)));self.navigation.addItem(item)
        layout.addWidget(side);body=QFrame();body.setObjectName('settingsPaper');right=QVBoxLayout(body);right.setContentsMargins(22,22,22,18);right.setSpacing(16)
        title_row=QHBoxLayout();title_row.setSpacing(14);self.badge=QLabel();self.badge.setFixedSize(40,40);title_row.addWidget(self.badge,0,Qt.AlignTop)
        titles=QVBoxLayout();titles.setSpacing(5);self.heading=help_label('');self.heading.setFont(heading_font(26));titles.addWidget(self.heading)
        self.description=help_label('');self.description.setProperty('muted',True);titles.addWidget(self.description);title_row.addLayout(titles,1);right.addLayout(title_row)
        self.stack=QStackedWidget();right.addWidget(self.stack,1);layout.addWidget(body,1)
        self.navigation.currentItemChanged.connect(self.selected);self.search.textChanged.connect(self.filter)
        self.bridge.pageRequested.connect(lambda index:self.select_route(['layout','content','activity','behavior'][index]))
        QShortcut(QKeySequence('Ctrl+F'),self,activated=self.search.setFocus)
        owner.status.messageChanged.connect(self.statusBar().showMessage)
        apply_style(self)
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() == QEvent.ApplicationPaletteChange:
            apply_style(self)
            if 'layout' in self.pages:self.pages['layout'].setClearColor(self.palette().window().color())

    def filter(self):
        words=self.search.text().strip().casefold().split();first=None;header=None
        for i in range(self.navigation.count()):
            item=self.navigation.item(i);key=item.data(Qt.UserRole)
            if key:
                text=item.text().casefold()+' '+self.SEARCH_TERMS.get(key,'')+' '+self.DETAILS.get(key,'').casefold()
                item.setHidden(not all(word in text for word in words))
                if not item.isHidden():
                    if first is None:first=item
                    if header:header.setHidden(False)
            else:header=item;header.setHidden(True)
        self.no_matches.setVisible(first is None)
        if first and words:self.navigation.setCurrentItem(first)
    def open_page(self,key='overview'):
        key=self.ALIASES.get(key,key)
        if key not in [r[0] for r in self.ROUTES]:key='overview'
        refresh_layout=bool(self.bridge.screens) and key in ('layout','content','activity','behavior')
        self.search.clear()
        self.select_route(key)
        if refresh_layout:self.bridge.request('')
        self.showNormal() if self.isMinimized() else self.show();self.raise_();self.activateWindow()
    def select_route(self,key):
        for i in range(self.navigation.count()):
            item=self.navigation.item(i)
            if item.data(Qt.UserRole)==key:
                if self.navigation.currentItem() is item:self.selected(item)
                else:self.navigation.setCurrentItem(item)
                break
    def selected(self,item,*_):
        key=item.data(Qt.UserRole) if item else None
        if not key:return
        self.heading.setText(item.text());self.description.setText(tr(self.DETAILS.get(key,'')))
        route=next(r for r in self.ROUTES if r[0]==key)
        category={'Notch':'display','Writing':'input','Capture':'display','Sound':'sound','Display & power':'power','Mouse & windows':'input','System & files':'apps'}.get(route[2],'display')
        self.badge.setPixmap(badge(route[3],category))
        layout_pages=['layout','content','activity','behavior'];storage='layout' if key in layout_pages else key
        if storage not in self.pages:
            if storage=='layout':
                from PySide6.QtQuickWidgets import QQuickWidget
                page=QQuickWidget();page.setResizeMode(QQuickWidget.SizeRootObjectToView);page.setClearColor(self.palette().window().color())
                page.rootContext().setContextProperty('settingsBridge',self.bridge)
                page.setSource(QUrl.fromLocalFile(str(Path(__file__).with_name('NotchSettingsLayout.qml'))))
            elif key=='overview':
                from notch_overview import Overview
                page=Overview(self.owner,self.bridge,self.select_route)
            elif key=='tools':page=ToolsPreferences(self.owner)
            elif key=='radial':page=RadialPreferences(self.owner)
            else:
                page=create_tool_page(key,self.owner,self.hide)
                from settings_sections import decorate
                from settings_controls import switches
                decorate(page,key);switches(page)
            if storage != 'layout':page.setObjectName('settingsPage')
            from screen_selection import ScreenSelection
            if isinstance(page,ScreenSelection):page.inline_completed=lambda key=key:self.open_page(key)
            self.pages[storage]=page
            if storage != 'layout' and key != 'tools':
                container=SettingsScroll(page)
            else:container=page
            self.containers[storage]=container;self.stack.addWidget(container)
        self.stack.setCurrentWidget(self.containers[storage])
        if key in layout_pages:self.bridge.show_page(layout_pages.index(key))
        else:activate_tool_page(self.pages[storage])
    def busy(self):
        return any(getattr(page,'busy',False) is True or (getattr(page,'cleaning',None) and page.cleaning.isActive()) or getattr(page,'capture_active',False) or getattr(page,'recorder',None) or getattr(page,'job',None) or (getattr(page,'clip',None) and page.clip.job) for page in self.pages.values())
    def closeEvent(self,event):
        self.owner.panelDismissed.emit();super().closeEvent(event)


def main(argv):
    # The shared utilities process can be serving an inline tool. A separate
    # application identity gives preferences their own saved window geometry.
    modules, helpers, page = argv
    sys.path.append(modules)
    from window import Window
    app = QApplication([])
    app.setApplicationName('Monet Notch & Tools')
    app.setDesktopFileName('monet-notch-settings')
    app.setQuitOnLastWindowClosed(False)
    if present(page):
        return 0

    class SettingsHost(Window):
        def Open(self, args):
            message = QDBusMessage.createMethodCall('org.monet.Utilities', '/Utilities', 'org.monet.Utilities', 'Present')
            message.setArguments([json.dumps(args)])
            QDBusConnection.sessionBus().asyncCall(message)

        def wheel(self):
            self.Open(['wheel'])

    owner = SettingsHost(helpers, defer_catalog=True)
    dialog = NotchSettingsWindow(owner)

    class Receiver(QObject):
        @Slot(str)
        def Show(self, page):
            dialog.open_page(page)

    receiver = Receiver()
    bus = QDBusConnection.sessionBus()
    if not bus.registerObject('/Settings', SERVICE, receiver, QDBusConnection.ExportAllSlots):
        return 1
    if not bus.registerService(SERVICE):
        return int(not present(page))
    dialog.open_page(page)
    idle = QTimer()
    idle.setInterval(1000)
    idle.timeout.connect(lambda: app.quit() if not dialog.isVisible() and not dialog.busy() and not owner.running else None)
    idle.start()
    result = app.exec()
    bus.unregisterService(SERVICE)
    dialog.deleteLater();owner.deleteLater()
    return result


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
