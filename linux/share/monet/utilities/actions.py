"""Desktop actions and clipboard/file transformations, independent of the interface."""
from dataclasses import dataclass
from gettext import translation
from pathlib import Path
from links import clean_url

tr = translation("monet", localedir=str(Path(__file__).resolve().parents[2] / "locale"), fallback=True).gettext

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
    "notes": Action(tr("Scratchpad"), "Writing notes pads Markdown", "accessories-text-editor"),
    "snippets": Action("Text snippets", "Writing", "edit-paste"),
    "clipboard": Action("Clipboard history", "Writing", "edit-paste", ("qdbus-qt6", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.showKlipperPopupMenu")),
    "plain": Action("Copy as plain text", "Writing", "edit-copy"),
    "link-settings": Action(tr("Copied link settings"), "Writing", "preferences-system"),
    "clean": Action("Clean a copied link", "Writing", "edit-clear"),
    "color": Action("Pick a screen color", "Capture", "color-picker"),
    "screenshot": Action("Screenshot and annotate", "Capture", "spectacle", ("spectacle", "-r")),
    "ocr": Action("Read text or a QR code from the screen", "Capture", "edit-select-text"),
    "record": Action("Record a screen region", "Capture", "media-record"),
    "recordings": Action(tr("Screen recorder and editor"), "Capture video trim crop MP4 GIF", "video-x-generic"),
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
    "mixer": Action(tr("Volume mixer"), "Sound volume pin mute app audio output", "audio-volume-high", ("@monet-settings", "sound#mixer")),
    "sound": Action(tr("Sound settings…"), "Sound speakers headphones microphone", "audio-volume-high", ("@monet-settings", "sound")),
    "output-order": Action("Preferred sound output order", "Sound headphones speakers automatic device priority", "audio-card", ("@monet-settings", "sound#output-order")),
    "output": Action("Cycle sound output", "Sound", "audio-card"),
    "mic": Action("Mute or unmute microphone", "Sound", "audio-input-microphone", ("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")),
    "media": Action("Player queue and lyrics", "Sound", "view-media-playlist"),
    "notifications": Action("Notification settings", "Desktop", "preferences-desktop-notification", ("@monet-settings", "notifications")),
    "theme": Action("Light and wallpaper settings", "Desktop", "preferences-desktop-theme", ("@monet-settings", "light")),
    "agents": Action("AI session usage", "System", "utilities-terminal"),
    "process-control": Action(tr("End or restart a process"), "System process tree PID force quit", "system-run"),
    "ports": Action(tr("Listening ports"), "System TCP UDP network process tree search quit", "network-wired"),
    "processes": Action("Processes and system monitors", "System", "utilities-system-monitor", ("plasma-systemmonitor",)),
    "fans": Action("Fan speeds and supported controllers", "System", "preferences-system-power-management"),
    "devices": Action("USB devices and fan sensors", "System", "computer"),
    "bluetooth": Action("Bluetooth accessories", "System", "preferences-system-bluetooth", ("@monet-settings", "bluetooth")),
    "wheel": Action("Favorite actions wheel", "Desktop", "view-more"),
}
DEFAULT_FAVORITES = ["shelf", "notes", "screenshot", "color", "awake", "sound"]
