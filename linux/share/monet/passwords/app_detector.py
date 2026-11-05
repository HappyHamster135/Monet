"""Bounded, event-driven AT-SPI form detection. No keyboard or clipboard listener."""
import time

from app_logins import candidate, identify, valid_text
from app_documents import DocumentContext

SUBMIT = {'sign in', 'log in', 'login', 'sign up', 'register', 'create account',
          'change password', 'update password', 'save password', 'logga in',
          'registrera', 'skapa konto', 'byt lösenord', 'ändra lösenord', 'anmelden',
          'registrieren', 'connexion', 'se connecter', 'iniciar sesión', 'registrarse',
          'accedi', 'inloggen', 'entrar', 'logg inn', 'kirjaudu sisään', 'connect', 'anslut'}
CREATE_OR_CHANGE = {'sign up', 'register', 'create account', 'change password', 'update password',
                    'save password', 'registrera', 'skapa konto', 'byt lösenord', 'ändra lösenord',
                    'registrieren', 'registrarse'}
NEXT = {'next', 'continue', 'nästa', 'fortsätt', 'weiter', 'suivant', 'continuer', 'continuar', 'siguiente'}
USER = {'username', 'user name', 'email', 'email address', 'e-mail', 'account',
        'användarnamn', 'e-post', 'e-postadress', 'username or email', 'email or username',
        'user', 'login', 'benutzername', 'e-mail-adresse', 'identifiant', "nom d’utilisateur",
        "nom d'utilisateur", 'adresse e-mail', 'usuario', 'correo electrónico',
        'nome utente', 'gebruiker', 'gebruikersnaam', 'usuário', 'brukernavn', 'käyttäjänimi'}
SERVICE = {'server', 'host', 'hostname', 'host name', 'server address', 'service',
           'address', 'serveradress', 'värd', 'serveur', 'servidor'}
NEW = ('new password', 'nytt lösenord')
CONFIRM = ('confirm', 'repeat', 'verify', 'bekräfta', 'upprepa')
OLD = ('current', 'old password', 'nuvarande', 'gammalt lösenord')
MASKS = set('*•●·\u25cf\u2022')


def label(text):
    return text.casefold().strip().rstrip(':').replace('&', '').replace('_', '').strip()


def form_values(fields, username='', allow_empty=False, service=''):
    """Conservative semantic matching. Ambiguous forms do not offer a saved password."""
    users = [f for f in fields if f['role'] == 'text' and label(f['name']) in USER]
    passwords = [f for f in fields if f['role'] == 'password']
    servers = [f for f in fields if f['role'] == 'service']
    if len(users) > 1 or not users and not username or len(servers) > 1 or not 1 <= len(passwords) <= 3:
        return None
    kind, chosen, private_confirmation = 'login', passwords[0], False
    if len(passwords) > 1:
        confirmations = [f for f in passwords if any(x in label(f['name']) for x in CONFIRM)]
        fresh = [f for f in passwords if any(x in label(f['name']) for x in NEW) and f not in confirmations]
        if len(confirmations) != 1:
            return None
        if len(passwords) == 3:
            old = [f for f in passwords if any(x in label(f['name']) for x in OLD)]
            if len(fresh) != 1 or len(old) != 1 or len({id(old[0]), id(fresh[0]), id(confirmations[0])}) != 3:
                return None
            kind, chosen = 'change', fresh[0]
        else:
            kind = 'register'
            chosen = next(f for f in passwords if f is not confirmations[0])
        # Masked fields cannot establish equality; the prompt asks for the password.
        a, b = chosen['value'], confirmations[0]['value']
        if not b: return None
        private_confirmation = masked(b)
        if a and b and not masked(a) and not masked(b) and a != b:
            return None
    password = chosen['value']
    if not password and not allow_empty:
        return None
    return candidate({'username': users[0]['value'] if users else username,
                      'password': '' if masked(password) or private_confirmation else password,
                      'service': servers[0]['value'] if servers else service, 'kind': kind})


def masked(value):
    return bool(value) and all(c in MASKS for c in value)


class Detector:
    def __init__(self, atspi, glib, offer, permitted, resolver=identify, clock=time.monotonic, suggest=None, dismiss=None, suspended=lambda: False):
        self.api, self.glib, self.offer, self.permitted = atspi, glib, offer, permitted
        self.resolver, self.clock = resolver, clock
        self.pending = None
        self.refresh_timer = 0
        self.expiry_timer = 0
        self.submission_timer = 0
        self.previous = None
        self.previous_timer = 0
        self.suggest, self.dismiss = suggest, dismiss
        self.suspended = suspended
        self.last_fill = None

    def clear(self):
        self.pending = None
        self.previous = None
        if self.dismiss: self.dismiss()
        for name in ('refresh_timer', 'expiry_timer', 'submission_timer', 'previous_timer'):
            if getattr(self, name): self.glib.source_remove(getattr(self, name))
            setattr(self, name, 0)

    def state(self, node, name):
        return node.get_state_set().contains(getattr(self.api.StateType, name))

    def window(self, node):
        for _ in range(24):
            parent = node.get_parent()
            if not parent or parent.get_role() == self.api.Role.APPLICATION:
                if node.get_role() in (self.api.Role.DOCUMENT_WEB, self.api.Role.DOCUMENT_FRAME): return None
                return node
            node = parent
        return None

    def context(self, source):
        window = self.window(source)
        if not window: return None
        base = self.resolver(source.get_process_id())
        document = DocumentContext.capture(self, source, window, base)
        return dict(window=window, root=document.root if document else window,
                    identity=document.identity if document else base, base=base,
                    document=document, anchor=source)

    def context_current(self, context, submitted=False):
        base = self.resolver(context['window'].get_process_id())
        if base != context['base']: return False
        document = context.get('document')
        if submitted and document:
            return document.pages_current(self, context['window'])
        return not document or document.current(self, context['anchor'], context['window'], base)

    def field_name(self, node):
        name = node.get_name() or ''
        if name: return name
        # GTK frequently associates labels rather than copying their name onto
        # the entry. Only explicit label relations are used, never nearby text.
        try:
            for relation in node.get_relation_set():
                if relation.get_relation_type() == self.api.RelationType.LABELLED_BY and relation.get_n_targets() == 1:
                    return relation.get_target(0).get_name() or ''
            attributes = node.get_attributes()
            return attributes.get('placeholder-text', '')
        except (AttributeError, TypeError):
            return ''

    def scan(self, window, username_only=False):
        started = self.clock()
        fields, passwords, buttons = [], [], []
        stack = [window]; visited = set()
        while stack:
            if len(visited) >= 96 or self.clock() - started > 0.5:
                return None
            node = stack.pop()
            if node in visited: return None
            visited.add(node)
            # Toolkit caches may keep an old button label or field state after
            # a form changes. Consent must be checked against live properties.
            node.clear_cache_single()
            role = node.get_role()
            if node != window and role in (self.api.Role.DOCUMENT_WEB, self.api.Role.DOCUMENT_FRAME):
                continue
            if role in (self.api.Role.PASSWORD_TEXT, self.api.Role.TEXT, self.api.Role.ENTRY):
                if not self.state(node, 'SHOWING'):
                    continue
                name = self.field_name(node)
                is_password = role == self.api.Role.PASSWORD_TEXT
                if not is_password and label(name) not in USER | SERVICE:
                    continue
                writable = self.state(node, 'EDITABLE')
                if hasattr(self.api.StateType, 'READ_ONLY') and self.state(node, 'READ_ONLY'): writable = False
                if is_password and not writable: continue
                text = node.get_text_iface()
                if not text or not 0 <= text.get_character_count() <= 4096:
                    return None
                # Accessible.get_text() is the deprecated interface getter in GI;
                # call Text.get_text explicitly to read the bounded field value.
                value = self.api.Text.get_text(text, 0, -1)
                fields.append({'role': 'password' if is_password else 'service' if label(name) in SERVICE else 'text',
                               'name': name, 'value': value, 'node': node, 'writable': writable})
                if is_password: passwords.append(node)
            elif role == self.api.Role.PUSH_BUTTON and label(node.get_name() or '') in SUBMIT | NEXT:
                buttons.append(node)
            count = node.get_child_count()
            if count > 96: return None
            stack.extend(node.get_child_at_index(i) for i in range(count))
        if not buttons or not passwords and not username_only:
            return None
        return fields, passwords, buttons

    def password_containers(self, passwords, window):
        nodes = set()
        for node in passwords:
            for _ in range(12):
                if not node or node == window: break
                nodes.add(node)
                node = node.get_parent()
        return nodes

    def previous_user(self, identity, window):
        p = self.previous
        if p and p['window'] == window and p['identity'] == identity and self.clock() < p['expires']:
            return p['username']
        return ''

    def previous_service(self, identity, window):
        return self.previous.get('service', '') if self.previous_user(identity, window) else ''

    def remember_username(self, source):
        if label(self.field_name(source)) not in USER | SERVICE: return
        context = self.context(source)
        if not context: return
        window, identity = context['window'], context['identity']
        if not window or not self.state(window, 'ACTIVE'): return
        if not self.permitted(identity): return
        scanned = self.scan(context['root'], username_only=True)
        if not scanned or scanned[1]: return
        users = [f for f in scanned[0] if f['role'] == 'text']
        servers = [f for f in scanned[0] if f['role'] == 'service']
        if len(users) == 1 and len(servers) <= 1 and valid_text(users[0]['value'], 320, False):
            self.previous = dict(window=window, identity=identity, username=users[0]['value'],
                                 service=servers[0]['value'] if servers else '', expires=self.clock() + 90)
            if self.previous_timer: self.glib.source_remove(self.previous_timer)
            self.previous_timer = self.glib.timeout_add_seconds(90, self.expire_previous)

    def expire_previous(self):
        self.previous, self.previous_timer = None, 0
        return False

    def mark_filled(self, node):
        self.clear()
        self.last_fill = (node, self.clock())

    def refresh(self):
        self.refresh_timer = 0
        p = self.pending
        if not p: return False
        try:
            if not self.permitted(p['identity']) or not self.state(p['window'], 'ACTIVE'):
                self.clear(); return False
            if not self.context_current(p): self.clear(); return False
            scanned = self.scan(p['root'])
            p['values'] = form_values(scanned[0], self.previous_user(p['identity'], p['window']),
                                      service=self.previous_service(p['identity'], p['window'])) if scanned else None
            if scanned:
                p['passwords'], p['buttons'] = scanned[1:]
                p['password_containers'] = self.password_containers(scanned[1], p['window'])
        except Exception:
            self.clear()  # Provider failures must never print field values.
        return False

    def event(self, event, *_):
        try:
            self._event(event)
        except Exception:
            self.clear()

    def _event(self, event):
        source, kind = event.source, event.type
        if self.suspended(): return
        if self.last_fill:
            node, when = self.last_fill
            if self.clock() - when > 90:
                self.last_fill = None
            elif source == node:
                if kind.startswith('object:text-changed:') and self.clock() - when > 0.3:
                    self.last_fill = None
                    # A later edit is a new save candidate; our own fill events are not.
                    from types import SimpleNamespace
                    self._event(SimpleNamespace(source=source, type='object:state-changed:focused', detail1=1))
                else: return
        if not self.pending and (kind.startswith('object:text-changed:') or kind == 'object:state-changed:focused'):
            self.remember_username(source)
        if kind == 'object:state-changed:focused' and event.detail1:
            window = self.window(source)
            if self.previous and window != self.previous['window']: self.previous = None
            if self.pending and window != self.pending['window']:
                self.clear()
            if source.get_role() == self.api.Role.PASSWORD_TEXT and not self.pending:
                if not window or not self.state(window, 'ACTIVE'): return
                context = self.context(source)
                if not context: return
                identity = context['identity']
                if not self.permitted(identity): return
                scanned = self.scan(context['root'])
                if not scanned: return
                self.pending = {**context, 'passwords': scanned[1],
                                'buttons': scanned[2], 'values': form_values(scanned[0], self.previous_user(identity, window),
                                                                           service=self.previous_service(identity, window)),
                                'last': source, 'expires': self.clock() + 90,
                                'password_containers': self.password_containers(scanned[1], window)}
                self.expiry_timer = self.glib.timeout_add_seconds(90, self.expire)
            if self.pending: self.pending['last'] = source
            if self.pending and self.suggest and source in self.pending['passwords']:
                target = FillTarget.capture(self, self.pending)
                if target: self.suggest(target)
        p = self.pending
        if not p: return
        if self.clock() >= p['expires'] or not self.permitted(p['identity']):
            self.clear(); return
        if kind.startswith('object:text-changed:') and (source in p['passwords'] or
                (label(self.field_name(source)) in USER | SERVICE and self.window(source) == p['window'])):
            if self.dismiss: self.dismiss()
            # Never save an old partial password when submission beats the debounce.
            if p['values']:
                p['values']['password'] = ''
                if source not in p['passwords']: p['values']['username'] = ''
            if self.refresh_timer: self.glib.source_remove(self.refresh_timer)
            self.refresh_timer = self.glib.timeout_add(150, self.refresh)
        # Only a disappearing password form inside a still-active window qualifies.
        # Closing the app/window, changing apps, and merely focusing a button do not.
        hidden = kind == 'object:state-changed:showing' and not event.detail1 and source in p['passwords']
        # GTK 4 removes hidden PasswordEntry subtrees instead of sending SHOWING.
        # Match only ancestors captured with this password, never arbitrary removals.
        removed = kind.startswith('object:children-changed:remove') and getattr(event, 'any_data', None) in p['password_containers']
        if hidden or removed:
            if not p['values'] or p['last'] not in p['passwords'] + p['buttons']:
                self.clear(); return
            if self.refresh_timer:
                self.glib.source_remove(self.refresh_timer); self.refresh_timer = 0
            # Window-close events can arrive after its child fields disappear.
            # Let that event batch finish before presenting any consent window.
            if not self.submission_timer:
                self.submission_timer = self.glib.timeout_add(150, self.confirm_offer)
        elif kind == 'object:state-changed:showing' and not event.detail1 and source == p['window']:
            self.clear()
        elif kind in ('window:deactivate', 'window:destroy') and source == p['window']:
            self.clear()

    def confirm_offer(self):
        self.submission_timer = 0
        p = self.pending
        self.clear()
        try:
            if p:
                p['window'].clear_cache_single()
                if (self.clock() < p['expires'] and self.permitted(p['identity'])
                        and self.context_current(p, submitted=True)
                        and self.state(p['window'], 'ACTIVE') and self.state(p['window'], 'SHOWING')):
                    self.offer(p['identity'], p['values'])
        except Exception:
            pass
        return False

    def expire(self):
        self.expiry_timer = 0
        self.clear()
        return False

    def start(self):
        self.api.set_timeout(100, 200)
        self.listener = self.api.EventListener.new(self.event)
        for kind in ('object:state-changed:focused', 'object:text-changed',
                     'object:state-changed:showing', 'object:children-changed:remove', 'window:deactivate', 'window:destroy'):
            if not self.listener.register(kind):
                raise RuntimeError('Accessibility events unavailable')


class FillTarget:
    """A specific still-live form. Filling never uses global typing or the clipboard."""
    def __init__(self, detector, pending, fields, context, buttons):
        self.detector, self.window, self.identity = detector, pending['window'], pending['identity']
        self.destination = {key: pending[key] for key in ('window', 'root', 'identity', 'base', 'document', 'anchor')}
        self.fields, self.context, self.expires = fields, context, detector.clock() + 90
        self.buttons = [(node, label(node.get_name() or '')) for node in buttons]

    @classmethod
    def capture(cls, detector, pending):
        if not detector.context_current(pending): return None
        scanned = detector.scan(pending['root'])
        if not scanned or len(scanned[1]) != 1: return None
        if any(label(button.get_name() or '') in CREATE_OR_CHANGE for button in scanned[2]): return None
        fields = scanned[0]
        password = next(f for f in fields if f['role'] == 'password')
        if password['value']: return None  # Never replace a password the user entered.
        # Chromium/Electron advertises EDITABLE but does not implement the
        # AT-SPI EditableText interface. Do not offer a picker that cannot fill.
        if not password['node'].get_editable_text_iface(): return None
        if any(f['role'] == 'text' and not f['value'] and
               (not f['writable'] or not f['node'].get_editable_text_iface()) for f in fields): return None
        context = form_values(fields, detector.previous_user(pending['identity'], pending['window']), allow_empty=True,
                              service=detector.previous_service(pending['identity'], pending['window']))
        if not context or context['kind'] != 'login': return None
        return cls(detector, pending, fields, context, scanned[2])

    def valid(self, active=True, written_username=None):
        d = self.detector
        try:
            if d.clock() >= self.expires or not d.permitted(self.identity): return False
            self.window.clear_cache_single()
            if not d.state(self.window, 'SHOWING') or active and not d.state(self.window, 'ACTIVE'): return False
            if not d.context_current(self.destination): return False
            scanned = d.scan(self.destination['root'])
            if not scanned or len(scanned[0]) != len(self.fields) or len(scanned[1]) != 1: return False
            if [(node, label(node.get_name() or '')) for node in scanned[2]] != self.buttons: return False
            for before in self.fields:
                current = next((f for f in scanned[0] if f['node'] == before['node']), None)
                expected = written_username if before['role'] == 'text' and written_username is not None else before['value']
                if (not current or current['role'] != before['role'] or current['name'] != before['name']
                        or current['writable'] != before['writable'] or current['value'] != expected):
                    return False
            return True
        except Exception:
            return False

    def apply(self, login):
        try:
            values = candidate(login)
            if (not values['password'] or values['service'] != self.context['service']
                    or self.context['username'] and values['username'] != self.context['username']
                    or not self.valid()): return False
            api = self.detector.api
            user = next((f for f in self.fields if f['role'] == 'text'), None)
            if user and user['value'] != values['username']:
                if not user['writable']: return False
                edit = user['node'].get_editable_text_iface()
                if not edit or not api.EditableText.set_text_contents(edit, values['username']): return False
            if not self.valid(written_username=values['username']): return False
            password = next(f for f in self.fields if f['role'] == 'password')
            edit = password['node'].get_editable_text_iface()
            success = bool(edit and api.EditableText.set_text_contents(edit, values['password']))
            if success: self.detector.mark_filled(password['node'])
            return success
        except Exception:
            return False
