"""Radial actions, organized by intent; playback uses Monet's media controller."""
from actions import ACTIONS, Action, FULL_APPLICATIONS, category_for, tr

EXCLUDED = FULL_APPLICATIONS | {'wheel', 'wheel-settings', 'notch-settings', 'quick-panel'}
MEDIA = {
    'media-play-pause': ('Play or pause', 'media-playback-start', 'playpausemedia'),
    'media-next': ('Next track', 'media-skip-forward', 'nextmedia'),
    'media-previous': ('Previous track', 'media-skip-backward', 'previousmedia'),
    'media-play': ('Play', 'media-playback-start', 'playmedia'),
    'media-pause': ('Pause', 'media-playback-pause', 'pausemedia'),
    'media-stop': ('Stop', 'media-playback-stop', 'stopmedia'),
    'media-forward': ('Forward 5 seconds', 'media-seek-forward', 'seekforwardmedia'),
    'media-back': ('Back 5 seconds', 'media-seek-backward', 'seekbackwardmedia'),
    'media-volume-up': ('Player volume up', 'audio-volume-high', 'mediavolumeup'),
    'media-volume-down': ('Player volume down', 'audio-volume-low', 'mediavolumedown'),
}
CATALOG = {key: value for key, value in ACTIONS.items() if key not in EXCLUDED}
CATALOG.update({key: Action(title, 'Media', icon) for key, (title, icon, _) in MEDIA.items()})
CATEGORIES = (('Media', 'Media', 'media-playback-start'), ('Capture', 'Capture', 'camera-photo'),
              ('Writing', 'Writing', 'document-edit'), ('Sound', 'Sound', 'audio-volume-high'),
              ('Desktop', 'Desktop', 'user-desktop'), ('Display', 'Display & power', 'video-display'),
              ('Files', 'Files', 'folder'), ('System', 'System', 'utilities-system-monitor'),
              ('Input', 'Mouse & keyboard', 'input-keyboard'))
ICONS = ('', 'media-playback-start', 'media-playback-pause', 'media-skip-forward', 'media-skip-backward',
         'rating', 'emblem-favorite', 'weather-clear', 'folder', 'text-x-generic', 'utilities-terminal',
         'internet-web-browser', 'mail-message-new', 'audio-x-generic', 'audio-headphones', 'camera-photo',
         'image-x-generic', 'media-record', 'input-gaming', 'input-keyboard', 'chronometer', 'go-home',
         'configure', 'color-picker', 'edit-paste', 'system-search', 'object-select-symbolic',
         'list-add', 'list-remove', 'system-lock-screen', 'audio-volume-high', 'audio-input-microphone')


def category(key):
    return 'Media' if key in MEDIA else category_for(key, CATALOG[key]) if key in CATALOG else 'Media'


def normalize(value):
    """Read the original string slots and richer slots without writing migrations."""
    if isinstance(value, str): value = {'action': value}
    if not isinstance(value, dict) or not isinstance(value.get('action'),str) or value['action'] not in CATALOG: return {}
    name = value.get('name', '')
    icon = value.get('icon', '')
    return {'action': value['action'], 'name': name.strip()[:64] if isinstance(name, str) else '',
            'icon': icon if isinstance(icon, str) and icon in ICONS else ''}


def entry(value):
    from wheel_profiles import Entry
    value = normalize(value)
    if not value: return Entry('empty', name=tr('Empty slot'))
    key = value['action']
    if key in MEDIA:
        title, icon, command = MEDIA[key]
        return Entry('shortcut', command, value['name'] or tr(title), value['icon'] or icon, 'mediacontrol')
    return Entry('tool', key, value['name'], value['icon'])
