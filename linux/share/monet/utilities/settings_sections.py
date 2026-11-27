"""Group existing controls without changing their settings or signal connections."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QLabel, QLayout, QScrollArea, QSlider, QSizePolicy, QTabWidget, QVBoxLayout, QWidget
from actions import ACTIONS, tr


def card(title):
    frame=QFrame();frame.setObjectName('settingsCard')
    frame.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
    box=QVBoxLayout(frame);box.setContentsMargins(18,18,18,18);box.setSpacing(14)
    if title:
        heading=QLabel(tr(title));heading.setProperty('sectionTitle',True);heading.setWordWrap(True)
        heading.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed)
        box.addWidget(heading)
    return frame,box


def group_layout(layout, sections):
    """Sections are (title, first widget), with preceding field labels retained."""
    items=[]
    while layout.count():items.append(layout.takeAt(0))
    starts={0:sections[0][0]}
    for title,widget in sections[1:]:
        index=next((i for i,item in enumerate(items) if item.widget() is widget),None)
        if index is not None:
            if index and isinstance(items[index-1].widget(),QLabel):index-=1
            starts[index]=title
    box=None
    for index,item in enumerate(items):
        if index in starts:
            frame,box=card(starts[index]);layout.addWidget(frame)
        if item.spacerItem():layout.addItem(item)
        elif item.widget():box.addWidget(item.widget(),0,item.alignment())
        elif item.layout():box.addLayout(item.layout())
    layout.setSpacing(16)


def decorate(page,key):
    if page.property('settingsDesigned'):return
    page.setProperty('settingsDesigned',True)
    if isinstance(page,QTabWidget):
        for index in range(page.count()):decorate(page.widget(index),key)
        return
    root=page.layout()
    if not root:return
    root.setContentsMargins(0,0,0,0);root.setSpacing(16)
    from compact_system import SystemPage
    if isinstance(page,SystemPage):
        sections={
            'sound':[('Output',None),('Microphone',page.controls.get('input'))],
            'power':[('Power & sleep',None)],
            'display':[('Display comfort',None)],
            'notifications':[('Quiet time',None),('Popups',page.controls.get('place'))],
            'mouse':[('Pointer & scrolling',None)],'touchpad':[('Trackpad gestures',None)],
            'windows':[('Window behavior',None)],'output-order':[('Preferred outputs',None)],
            'theme':[('Monet appearance',None)],'bluetooth':[('Accessories',None)],'devices':[('Connected devices',None)]
        }.get(key,[('Options',None)])
        page.body.setObjectName('settingsGroups')
        group_layout(page.form,sections)
        root.setAlignment(page.retry,Qt.AlignLeft)
    elif key=='awake':
        # One page scrolls as a whole; the embedded rules scroller made it hard
        # to reach controls and left a large empty panel on tall windows.
        scroll=page.findChild(QScrollArea)
        form=scroll.takeWidget();index=root.indexOf(scroll)
        form.setAutoFillBackground(False)
        root.removeWidget(scroll);scroll.hide();scroll.deleteLater();root.insertWidget(index,form)
        form.layout().setContentsMargins(0,0,0,0)
        page.conditions.layout().setContentsMargins(0,0,0,0)
        group_layout(root,[('Manual session',None),('Automatic rules',form)])
    else:
        # Existing editors keep their own nested layouts and application state.
        titles={'snippets':'Your snippets','emoji':'Find your emoji','cleaning':'Cleaning session',
                'record':'Recording preferences','clipboard-expiry':'Clipboard privacy',
                'link-settings':'Link cleanup','media-keys':'Media controls','calendars':'Your calendars',
                'monitor-alerts':'Alert thresholds','downloads':'Watched folder','scripts':'Your scripts'}
        group_layout(root,[(titles.get(key,ACTIONS[key].source_name if key in ACTIONS else 'Options'),None)])
    for form in page.findChildren(QFormLayout):
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(14);form.setHorizontalSpacing(20)
    for control in page.findChildren(QComboBox):
        control.setMaxVisibleItems(8);control.view().setMaximumHeight(280)
    for slider in page.findChildren(QSlider):
        if slider.orientation()==Qt.Horizontal:slider.setMinimumHeight(30)
    for frame in page.findChildren(QFrame):
        if frame.objectName()=='settingsCard' and frame.layout():frame.layout().setSizeConstraint(QLayout.SetMinimumSize)
