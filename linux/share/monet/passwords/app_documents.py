"""Bind embedded app forms to their live document, without inspecting browser DOMs."""
from dataclasses import dataclass
import ipaddress
from urllib.parse import urlsplit, urlunsplit

from app_logins import AppIdentity, valid_text


def document_scope(uri):
    """No opaque pages, credentials, query strings or fragments in saved identity."""
    if not valid_text(uri, 4096, False) or '\\' in uri:
        raise ValueError('Unknown document')
    parsed = urlsplit(uri)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('Unknown document')
    if parsed.scheme == 'file':
        if parsed.netloc not in ('', 'localhost') or not parsed.path.startswith('/'):
            raise ValueError('Unknown local document')
        # Local app pages have no shared web origin. Bind to the exact file.
        scope = urlunsplit(('file', '', parsed.path, '', ''))
    elif parsed.scheme in ('https', 'http', 'app', 'tauri', 'capacitor', 'ionic'):
        host = parsed.hostname
        if not host or '%' in host: raise ValueError('Unknown document host')
        host = host.encode('idna').decode('ascii').lower()
        if parsed.scheme == 'http':
            try: local = ipaddress.ip_address(host).is_loopback
            except ValueError: local = host == 'localhost'
            if not local: raise ValueError('Unencrypted remote document')
        port = parsed.port
        if ':' in host: host = '[' + host + ']'
        if port is not None and (parsed.scheme, port) not in (('https', 443), ('http', 80)):
            host += ':' + str(port)
        scope = parsed.scheme + '://' + host
    else:
        raise ValueError('Opaque document')
    if len(scope) > 2000: raise ValueError('Document identity is too long')
    return scope


def document_identity(identity, uri):
    """Same app/site key for accessibility and a cooperating app's main process."""
    scope = document_scope(uri)
    if identity.document:
        raise ValueError('Already bound to a document')
    return AppIdentity(identity.scope + '|document:' + scope,
                       (identity.name[:100] + ' · ' + scope)[:200], identity.executable)


@dataclass
class DocumentContext:
    root: object
    pages: list
    identity: AppIdentity

    @classmethod
    def capture(cls, detector, source, window, identity):
        node, pages, root = source, [], None
        roles = detector.api.Role
        form_role = getattr(roles, 'FORM', None)
        for _ in range(24):
            if node is None or node == window: break
            node.clear_cache_single()
            role = node.get_role()
            if form_role is not None and role == form_role and root is None:
                root = node
            if role in (roles.DOCUMENT_WEB, roles.DOCUMENT_FRAME):
                document = node.get_document_iface()
                uri = detector.api.Document.get_document_attribute_value(document, 'URI') if document else ''
                scope = document_scope(uri)
                if pages and document_scope(pages[0][1]) != scope:
                    raise ValueError('Embedded document has a different origin')
                pages.append((node, uri))
                if root is None: root = node
            node = node.get_parent()
        else:
            raise ValueError('Document ancestry is too deep')
        if node != window: raise ValueError('Detached document')
        if not pages: return None
        # Keep page logins separate from native app API requests and from other
        # sites opened by the same app. Full URLs (possibly containing tokens)
        # live only in this short-lived binding, never in the vault or logs.
        bound = document_identity(identity, pages[0][1])
        return cls(root, pages, bound)

    def current(self, detector, source, window, base):
        try:
            other = self.capture(detector, source, window, base)
            return (other is not None and other.root == self.root and other.pages == self.pages
                    and other.identity == self.identity)
        except Exception:
            return False

    def pages_current(self, detector, window):
        for node, uri in self.pages:
            node.clear_cache_single()
            document = node.get_document_iface()
            if (detector.window(node) != window or not document
                    or detector.api.Document.get_document_attribute_value(document, 'URI') != uri):
                return False
        return True
