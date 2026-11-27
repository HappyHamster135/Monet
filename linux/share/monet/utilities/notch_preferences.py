"""Shared choices for the notch's quick actions. No actions run while reading."""
import json
from actions import stored
from radial_actions import CATALOG, EXCLUDED, normalize, entry

RADIAL_DEFAULT = ["screenshot", "record", "color", "text-tools", "emoji", "snippets", "mic", "awake"]
RADIAL_PRESETS = {
    "Everyday": RADIAL_DEFAULT,
    "Capture": ["screenshot", "record", "ocr", "color", "color-tools", "camera", "watch", "compress"],
    "Writing": ["plain", "clean", "text-tools", "snippets", "emoji", "clipboard", "notes", "ocr"],
    "Media": ["media-play-pause", "media-next", "media-volume-up", "mic", "media-stop", "media-volume-down", "media-previous", "output"],
}

def radial_records(settings):
    saved = stored(settings, "notchRadial", RADIAL_DEFAULT)
    return [normalize(value) for value in (saved+['']*8)[:8]]

def radial_slots(settings):
    return [value.get('action','') for value in radial_records(settings)]

def radial_entries(settings):
    return tuple(entry(value) for value in radial_records(settings))

def save_radial_records(settings, values):
    if not isinstance(values,list) or len(values)!=8:
        raise ValueError('Choose eight radial slots')
    cleaned=[normalize(value) for value in values]
    if any(value and not clean for value,clean in zip(values,cleaned)):
        raise ValueError('Choose valid radial actions')
    settings.setValue('notchRadial',json.dumps(cleaned,ensure_ascii=False));settings.sync()

def save_radial(settings, keys):
    if not isinstance(keys,list) or len(keys)!=8 or any(not isinstance(k,str) or k and k not in CATALOG for k in keys):
        raise ValueError("Choose eight valid radial slots")
    settings.setValue("notchRadial",json.dumps(keys))
    settings.sync()

def announce():
    from PySide6.QtDBus import QDBusConnection,QDBusMessage
    QDBusConnection.sessionBus().send(QDBusMessage.createSignal("/Utilities","org.monet.Utilities","ToolVisibilityChanged"))
