"""Small system controls backed by the same commands as Monet Settings.

Reading a page never changes settings. Controls keep their last snapshot while a
request is in flight, and writes are serialized before refreshing that snapshot.
"""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget)
from notch_pages import Page, label, button, row
from actions import tr

SYSTEM_PAGES = {'display', 'power', 'sound', 'output-order', 'mouse', 'touchpad',
                'windows', 'notifications', 'theme', 'bluetooth', 'devices'}


class SystemPage(Page):
    def __init__(self, host, key):
        super().__init__(host)
        self.key, self.loading, self.pending = key, False, False
        self.state, self.controls = {}, {}
        self.body = QFrame(); self.body.setObjectName("settingsCard")
        self.form = QVBoxLayout(self.body)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(12)
        self.layout_box.addWidget(self.body)
        self.message = label(tr('Loading…'), True)
        self.layout_box.addWidget(self.message)
        self.retry = button(tr('Refresh'), self.refresh)
        self.layout_box.addWidget(self.retry)
        self.layout_box.addStretch()
        self.build()
        self.body.setEnabled(False)

    def check(self, key, title, command):
        control = QCheckBox(tr(title))
        control.clicked.connect(lambda on: self.write(command(on)))
        self.form.addWidget(control)
        self.controls[key] = control
        return control

    def choice(self, key, title, choices, command):
        self.form.addWidget(label(tr(title), True))
        control = QComboBox()
        control.setAccessibleName(tr(title))
        for name, value in choices:
            control.addItem(tr(name), value)
        control.activated.connect(lambda _: self.write(command(control.currentData())))
        self.form.addWidget(control)
        self.controls[key] = control
        return control

    def level(self, key, title, command, minimum=0):
        caption = label(tr(title), True)
        self.form.addWidget(caption)
        control = QSlider(Qt.Horizontal)
        control.setRange(minimum, 100)
        control.setAccessibleName(tr(title))
        control.valueChanged.connect(lambda value: caption.setText(f'{tr(title)} · {value}%'))
        # Keyboard increments and pointer drags both commit after release / action.
        control.sliderReleased.connect(lambda: self.write(command(control.value())))
        control.actionTriggered.connect(lambda _: self.defer_level(control, command))
        self.form.addWidget(control)
        self.controls[key] = control
        return control

    def defer_level(self, control, command):
        from PySide6.QtCore import QTimer
        if not control.isSliderDown():
            QTimer.singleShot(0, control, lambda: self.write(command(control.value())))

    def build(self):
        k = self.key
        if k == 'display':
            self.level('brightness', 'Brightness', lambda n: ['brightness', n], 1)
            self.check('night', 'Night light', lambda on: ['night', 'on' if on else 'off'])
            self.screens = QWidget(); self.screen_box = QVBoxLayout(self.screens)
            self.screen_box.setContentsMargins(0, 0, 0, 0); self.form.addWidget(self.screens)
        elif k == 'power':
            self.choice('mode', 'Power mode', [], lambda value: ['power-mode', value])
            for state, title in [('ac', 'When plugged in'), ('battery', 'On battery')]:
                self.form.addWidget(label(tr(title)))
                for what, name, times in [('screen', 'Turn off display', [120,300,600,900,1800,3600,0]),
                                          ('sleep', 'Sleep after', [300,600,900,1800,3600,7200,0])]:
                    choices = [(tr('Never') if n == 0 else tr('{n} min').format(n=n//60), n) for n in times]
                    self.choice(f'{state}.{what}', name, choices,
                                lambda value, state=state, what=what: ['power-time', state, what, value])
            self.check('saver', 'Automatic battery saver', lambda on: ['battery-saver', 'automatic' if on else 'off'])
        elif k == 'sound':
            self.choice('output', 'Play sound through', [], lambda device: ['output', device['id'], device['key']])
            self.level('volume', 'Output volume', lambda n: ['volume', n])
            self.choice('input', 'Microphone', [], lambda device: ['input', device['id'], device['key']])
            self.level('mic', 'Microphone volume', lambda n: ['mic', n])
            self.check('mic-muted', 'Mute microphone', lambda on: ['mic-mute', self.state['microphone']['id'], 'on' if on else 'off', self.state['microphone']['key']])
        elif k == 'output-order':
            self.check('enabled', 'Switch to the highest available output', lambda on: self.order_command(enabled=on))
            self.form.addWidget(label(tr('Select an output and move it up or down. Disconnected saved outputs keep their place.'), True))
            self.outputs = QListWidget(); self.outputs.setAccessibleName(tr('Preferred sound outputs'))
            self.form.addWidget(self.outputs)
            row(self.form, button(tr('Move up'), lambda: self.move_output(-1)), button(tr('Move down'), lambda: self.move_output(1)))
            self.check('headphoneLimitEnabled', 'Limit speaker volume after unplugging headphones',
                       lambda on: self.order_command(headphoneLimitEnabled=on))
            self.level('headphoneLimit', 'Speaker volume limit', lambda n: self.order_command(headphoneLimit=n))
        elif k in ('mouse', 'touchpad'):
            self.level('speed', 'Pointer speed', lambda n: ['pointer', k, 'speed', n])
            fields = [('natural', 'Natural scrolling'), ('left', 'Left-handed buttons')]
            if k == 'touchpad': fields += [('tap', 'Tap to click'), ('typing', 'Disable while typing')]
            for field, title in fields:
                self.check(field, title, lambda on, field=field: ['pointer', k, field, 'on' if on else 'off'])
        elif k == 'windows':
            self.choice('policy', 'Focus a window', [('When clicked', 'click'), ('When the pointer enters', 'hover')], lambda value: ['window-focus', 'policy', value])
            self.choice('first', 'First click in an inactive window', [('Activate and click', 'pass'), ('Activate only', 'focus')], lambda value: ['window-focus', 'first', value])
            self.choice('delay', 'Pointer focus delay', [(f'{n} ms', n) for n in [0,150,300,600,1000]], lambda value: ['window-focus', 'delay', value])
        elif k == 'notifications':
            self.check('quiet', 'Do Not Disturb', lambda on: ['quiet', 'on' if on else 'off'])
            for field, title in [('mirrored', 'Quiet while sharing the screen'), ('fullscreen', 'Quiet in full screen'), ('urgent', 'Allow urgent notifications')]:
                self.check(field, title, lambda on, field=field: ['notify-rule', field, 'on' if on else 'off'])
            self.choice('place', 'Popup position', [('Near the clock', 'clock'), ('Top right', 'topright'), ('Top center', 'topcenter')], lambda value: ['notify-place', value])
            self.choice('time', 'Popup duration', [(f'{n} seconds', n) for n in [3,5,10]], lambda value: ['notify-time', value])
        elif k == 'theme':
            self.choice('light', 'Appearance', [('Follow the hours', 'hours'), ('Mist · light', 'mist'), ('Smoke · dark', 'smoke')], lambda value: ['light', value])
            self.form.addWidget(label(tr('Uses Monet’s desktop appearance, including the taskbar, notch settings and application colors.'), True))
        elif k == 'bluetooth':
            self.check('bluetooth', 'Bluetooth', lambda on: ['bluetooth', 'on' if on else 'off'])
            self.devices = QListWidget(); self.devices.setAccessibleName(tr('Paired accessories')); self.form.addWidget(self.devices)
            self.connect_button = button(tr('Connect / disconnect'), self.connect_device)
            self.form.addWidget(self.connect_button)
        elif k == 'devices':
            from PySide6.QtWidgets import QPlainTextEdit
            self.device_text = QPlainTextEdit(); self.device_text.setReadOnly(True)
            self.device_text.setAccessibleName(tr('USB devices')); self.form.addWidget(self.device_text)

    def request(self, args, done):
        self.host.worker([self.host.helpers/'monet-quick', *args], done, self.failed)

    def refresh(self):
        if self.pending: return
        self.pending = True; self.retry.setEnabled(False)
        queries = {
            'display': [['status','display'], ['display-state']], 'power': [['power']],
            'sound': [['status','sound'], ['sound','devices']], 'output-order': [['output-order','get']],
            'mouse': [['input']], 'touchpad': [['input']], 'windows': [['input']],
            'notifications': [['notify']], 'theme': [['status','light']],
            'bluetooth': [['status','bluetooth'], ['bt-list']],
        }
        if self.key == 'devices':
            self.host.worker(['lsusb'], self.usb_loaded, self.failed); return
        requests = iter(queries[self.key]); result = {}
        def next_request():
            args = next(requests, None)
            if args is None:
                self.pending = False; self.retry.setEnabled(True)
                self.apply_snapshot(result); return
            def received(raw):
                try:
                    data = json.loads(raw)
                    if args == ['bt-list']: data = {'devices': data}
                    if not isinstance(data, dict) or data.get('ok') is False: raise ValueError()
                    result.update(data)
                except (ValueError, TypeError):
                    self.failed(tr('Could not read these settings.')); return
                next_request()
            self.request(args, received)
        next_request()

    def usb_loaded(self, text):
        self.pending = False; self.retry.setEnabled(True); self.body.setEnabled(True)
        self.device_text.setPlainText(text.strip() or tr('No USB devices reported.')); self.message.clear()

    def failed(self, message):
        self.pending = False; self.retry.setEnabled(True)
        if self.state: self.apply_snapshot(self.state)
        self.body.setEnabled(bool(self.state))
        self.message.setText(tr('Could not update. Your last known settings are still shown. ') + str(message)[:220])

    def write(self, args):
        if self.loading or self.pending or not args: return
        self.pending = True; self.body.setEnabled(False); self.retry.setEnabled(False)
        self.message.setText(tr('Applying…'))
        def finished(raw):
            try:
                result = json.loads(raw) if raw.strip() else {}
                if isinstance(result, dict) and result.get('ok') is False:
                    self.failed(tr('The change was not accepted. Refresh to try again.')); return
            except ValueError:
                self.failed(tr('Could not confirm the change.')); return
            self.pending = False; self.refresh()
        self.request([str(arg) for arg in args], finished)

    def fill_choice(self, control, entries, selected):
        control.clear()
        for name, data in entries: control.addItem(name, data)
        control.setCurrentIndex(max(0, control.findData(selected)))
        control.setEnabled(bool(entries))

    def apply_snapshot(self, state):
        self.state = state; self.loading = True; self.body.setEnabled(True)
        k = self.key; values = dict(state)
        if k in ('mouse', 'touchpad'):
            values = state.get(k) or {}
        elif k == 'windows':
            values = dict(state.get('windowFocus', {}))
            values['policy'] = {'ClickToFocus':'click','FocusFollowsMouse':'hover'}.get(values.get('policy'))
        elif k == 'power':
            values['saver'] = state.get('batterySaverAuto')
            for source in ('ac', 'battery'):
                for what in ('screen', 'sleep'): values[f'{source}.{what}'] = state.get(source, {}).get(what)
            titles = {'automatic':tr('Automatic'), 'power-saver':tr('Save power'), 'balanced':tr('Balanced'), 'performance':tr('Performance')}
            self.fill_choice(self.controls['mode'], [(titles.get(v, v), v) for v in state.get('modes', [])], state.get('mode'))
        elif k == 'sound':
            for field, source in [('output','outputs'), ('input','inputs')]:
                devices = state.get(source, [])
                self.fill_choice(self.controls[field], [(d['name'], d) for d in devices], next((d for d in devices if d.get('default')), None))
            values['mic-muted'] = (state.get('microphone') or {}).get('muted')
        elif k == 'bluetooth':
            self.devices.clear()
            for device in state.get('devices', []):
                item = QListWidgetItem(device['name'] + (' · '+tr('Connected') if device.get('connected') else ''))
                item.setData(Qt.UserRole, device); self.devices.addItem(item)
            self.connect_button.setEnabled(bool(self.devices.count()))
        elif k == 'output-order':
            self.outputs.clear(); rows = list(state.get('devices', []))
            known = {(d['key'],d['port']) for d in rows}
            rows += [d for d in state.get('connected', []) if (d['key'],d['port']) not in known]
            for device in rows:
                item = QListWidgetItem(device['name']); item.setData(Qt.UserRole, device); self.outputs.addItem(item)
            values.setdefault('headphoneLimit', 20); values.setdefault('headphoneLimitEnabled', False)
        elif k == 'display':
            while self.screen_box.count():
                item = self.screen_box.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            for screen in state.get('features', []):
                title = label(screen.get('name', ''), True); self.screen_box.addWidget(title)
                for field, name in [('hdr','HDR'), ('vrr','Adaptive refresh rate')]:
                    if screen.get(field) is None: continue
                    control = QCheckBox(tr(name)); control.setChecked(bool(screen[field]))
                    control.clicked.connect(lambda on, field=field, name=screen['name']: self.write(['screen-'+field,name,'on' if on else 'off']))
                    self.screen_box.addWidget(control)
        for name, control in self.controls.items():
            if name in ('output', 'input', 'mode'): continue
            value = values.get(name)
            control.setEnabled(value is not None)
            if isinstance(control, QCheckBox): control.setChecked(bool(value))
            elif isinstance(control, QSlider): control.setValue(int(value or 0))
            elif isinstance(control, QComboBox): control.setCurrentIndex(control.findData(value))
        self.loading = False
        self.message.setText(tr('No supported device is connected.') if k in ('mouse','touchpad') and not values else '')
        self.updateGeometry()

    def connect_device(self):
        item = self.devices.currentItem()
        if item:
            device = item.data(Qt.UserRole)
            self.write(['bt-disconnect' if device.get('connected') else 'bt-connect', device['address']])

    def order_command(self, **changes):
        value = {k:self.state[k] for k in ('enabled','headphoneLimit','headphoneLimitEnabled','revision') if k in self.state}
        value['devices'] = [self.outputs.item(i).data(Qt.UserRole) for i in range(self.outputs.count())]
        value.update(changes)
        return ['output-order', 'save', json.dumps(value).encode().hex()]

    def move_output(self, step):
        index = self.outputs.currentRow(); target = index+step
        if self.pending or index < 0 or not 0 <= target < self.outputs.count(): return
        item = self.outputs.takeItem(index); self.outputs.insertItem(target,item); self.outputs.setCurrentRow(target)
        self.write(self.order_command())
