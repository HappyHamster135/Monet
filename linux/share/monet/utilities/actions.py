"""Desktop actions and clipboard/file transformations, independent of the interface."""
from dataclasses import dataclass
from urllib.parse import unquote_plus, urlsplit, urlunsplit

@dataclass(frozen=True)
class Action:
    name: str
    group: str
    icon: str
    command: tuple = ()

ACTIONS = {
    "calendars": Action("Notch calendars", "Calendar subscriptions and appointments", "view-calendar"),
    "shelf": Action("File shelf", "Files", "folder-favorites"),
    "downloads": Action("Watch downloads", "Files", "folder-download"),
    "notes": Action("Scratchpad", "Writing", "accessories-text-editor"),
    "snippets": Action("Text snippets", "Writing", "edit-paste"),
    "clipboard": Action("Clipboard history", "Writing", "edit-paste", ("qdbus-qt6", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.showKlipperPopupMenu")),
    "plain": Action("Copy as plain text", "Writing", "edit-copy"),
    "clean": Action("Clean a copied link", "Writing", "edit-clear"),
    "color": Action("Pick a screen color", "Capture", "color-picker"),
    "screenshot": Action("Screenshot and annotate", "Capture", "spectacle", ("spectacle", "-r")),
    "ocr": Action("Read text or a QR code from the screen", "Capture", "edit-select-text"),
    "record": Action("Record a screen region", "Capture", "media-record", ("spectacle", "--record", "r")),
    "camera": Action("Camera mirror", "Capture", "camera-web"),
    "watch": Action("Watch a window", "Capture", "video-display"),
    "compress": Action("Compress media", "Files", "media-optical"),
    "trash": Action("Open Trash", "Files", "user-trash", ("dolphin", "trash:/")),
    "files": Action("Browse and rename files", "Files", "system-file-manager", ("dolphin",)),
    "storage": Action("Review storage and unused files", "Files", "drive-harddisk", ("@monet-settings", "storage")),
    "apps": Action("Manage and uninstall apps", "Files", "applications-all", ("@monet-games", "--apps")),
    "updates": Action("System updates", "System", "system-software-update", ("@monet-settings", "updates")),
    "store": Action("App store and updates", "System", "system-software-install", ("@monet-store",)),
    "wallpaper": Action("Choose wallpaper", "Display", "preferences-desktop-wallpaper"),
    "display": Action("Brightness, displays and HDR", "Display", "video-display", ("@monet-settings", "display")),
    "power": Action("Power and battery", "System", "battery", ("@monet-settings", "power")),
    "awake": Action("Keep awake", "Display", "preferences-system-power-management"),
    "lock": Action("Lock the screen for cleaning", "Display", "system-lock-screen", ("loginctl", "lock-session")),
    "mouse": Action("Mouse buttons, scroll direction and acceleration", "Input", "input-mouse", ("kcmshell6", "kcm_mouse")),
    "touchpad": Action("Trackpad clicks and gestures", "Input", "input-touchpad", ("kcmshell6", "kcm_touchpad")),
    "windows": Action("Window focus and click behavior", "Input", "preferences-system-windows", ("kcmshell6", "kcm_kwinoptions")),
    "remap": Action("Remap mouse buttons, scroll modifiers and keys", "Input", "input-keyboard", ("input-remapper-gtk",)),
    "shortcuts": Action("Keyboard shortcuts", "Input", "input-keyboard", ("kcmshell6", "kcm_keys")),
    "debounce": Action("Keyboard bounce and sticky keys", "Input", "preferences-desktop-accessibility", ("kcmshell6", "kcm_access")),
    "sound": Action("Per-app volume and output devices", "Sound", "audio-volume-high", ("@monet-settings", "sound")),
    "output": Action("Cycle sound output", "Sound", "audio-card"),
    "mic": Action("Mute or unmute microphone", "Sound", "audio-input-microphone", ("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")),
    "media": Action("Player queue and lyrics", "Sound", "view-media-playlist"),
    "notifications": Action("Notification settings", "Desktop", "preferences-desktop-notification", ("@monet-settings", "notifications")),
    "theme": Action("Light and wallpaper settings", "Desktop", "preferences-desktop-theme", ("@monet-settings", "light")),
    "agents": Action("AI session usage", "System", "utilities-terminal"),
    "ports": Action("Listening ports", "System", "network-wired"),
    "processes": Action("Processes and system monitors", "System", "utilities-system-monitor", ("plasma-systemmonitor",)),
    "fans": Action("Fan speeds and supported controllers", "System", "preferences-system-power-management"),
    "devices": Action("USB devices and fan sensors", "System", "computer"),
    "bluetooth": Action("Bluetooth accessories", "System", "preferences-system-bluetooth", ("@monet-settings", "bluetooth")),
    "wheel": Action("Favorite actions wheel", "Desktop", "view-more"),
}
DEFAULT_FAVORITES = ["shelf", "notes", "screenshot", "color", "awake", "sound"]

def clean_url(text):
    """Leave signature-bearing URLs and the exact encoding of retained parameters intact."""
    value = text.strip()
    if not value or any(c.isspace() for c in value):
        raise ValueError("Copy one web link first.")
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("Copy one web link first.")
    fields = [(unquote_plus(p.partition("=")[0]).casefold(), p) for p in parts.query.split("&")]
    if any(k in ("sig", "signature", "policy", "key-pair-id") or k.startswith(("x-amz-", "x-goog-")) for k, _ in fields):
        return value
    query = "&".join(p for k, p in fields if not k.startswith("utm_") and k not in
                     {"fbclid", "gclid", "dclid", "msclkid", "mc_eid", "mc_cid"})
    return urlunsplit(parts._replace(query=query)) if query != parts.query else value
