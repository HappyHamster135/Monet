"""Desktop actions and clipboard/file transformations, independent of the interface."""
import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from gettext import translation
from pathlib import Path
from links import clean_url

tr = translation("monet", localedir=str(Path(__file__).resolve().parents[2] / "locale"), fallback=True).gettext

def N_(text):
    """Mark the English search name for translation at display time."""
    return text


@dataclass(frozen=True)
class Action:
    source_name: str
    group: str
    icon: str
    command: tuple = ()

    @property
    def name(self):
        return tr(self.source_name)

ACTIONS = {
    "calendars": Action(N_("Notch calendars"), "Calendar subscriptions and appointments", "view-calendar"),
    "shelf": Action(N_("File shelf"), "Files", "folder-favorites"),
    "downloads": Action(N_("Watch downloads"), "Files", "folder-download"),
    "notes": Action(N_("Scratchpad"), "Writing notes pads Markdown", "accessories-text-editor"),
    "snippets": Action(N_("Text snippets"), "Writing", "edit-paste"),
    "clipboard": Action(N_("Clipboard history"), "Writing", "edit-paste", ("qdbus-qt6", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.showKlipperPopupMenu")),
    "wheel-scrolling": Action(N_("Mouse wheel scrolling"), "Input mouse smooth linear horizontal sideways scroll", "input-mouse"),
    "quit-protection": Action(N_("Quit and close protection"), "Input keyboard shortcut Ctrl+Q Ctrl+W", "preferences-desktop-keyboard"),
    "paste-shortcut": Action(N_("Paste as plain text shortcut"), "Writing", "edit-paste", ("kcmshell6", "kcm_keys")),
    "plain": Action(N_("Copy as plain text"), "Writing", "edit-copy"),
    "link-settings": Action(N_("Copied link settings"), "Writing", "preferences-system"),
    "clean": Action(N_("Clean a copied link"), "Writing", "edit-clear"),
    "color": Action(N_("Pick a screen color"), "Capture", "color-picker"),
    "screenshot": Action(N_("Screenshot and annotate"), "Capture", "spectacle", ("spectacle", "-r")),
    "ocr": Action(N_("Read text or a QR code from the screen"), "Capture", "edit-select-text"),
    "record": Action(N_("Record a screen region"), "Capture", "media-record"),
    "recordings": Action(N_("Screen recorder and editor"), "Capture video trim crop MP4 GIF", "video-x-generic"),
    "camera": Action(N_("Camera mirror"), "Capture", "camera-web"),
    "watch": Action(N_("Watch a window"), "Capture", "video-display"),
    "compress": Action(N_("Compress media"), "Files", "media-optical"),
    "trash": Action(N_("Open Trash"), "Files", "user-trash", ("dolphin", "trash:/")),
    "files": Action(N_("Browse and rename files"), "Files", "system-file-manager", ("dolphin",)),
    "storage": Action(N_("Review storage and unused files"), "Files", "drive-harddisk", ("@monet-settings", "storage")),
    "apps": Action(N_("Manage and uninstall apps"), "Files", "applications-all", ("@monet-games", "--apps")),
    "updates": Action(N_("System updates"), "System", "system-software-update", ("@monet-settings", "updates")),
    "homebrew": Action(N_("Homebrew packages"), "System brew formulae casks install uninstall upgrade updates package manager", "applications-other"),
    "store": Action(N_("App store and updates"), "System", "system-software-install", ("@monet-store",)),
    "wallpaper": Action(N_("Choose wallpaper"), "Display", "preferences-desktop-wallpaper"),
    "display": Action(N_("Brightness, displays and HDR"), "Display", "video-display", ("@monet-settings", "display")),
    "power": Action(N_("Power and battery"), "System", "battery", ("@monet-settings", "power")),
    "awake": Action(N_("Keep awake"), "Display", "preferences-system-power-management"),
    "lock": Action(N_("Cleaning mode"), "Display keyboard mouse lock screen cleaning", "input-keyboard"),
    "mouse": Action(N_("Mouse buttons, scroll direction and acceleration"), "Input", "input-mouse", ("kcmshell6", "kcm_mouse")),
    "touchpad": Action(N_("Trackpad clicks and gestures"), "Input", "input-touchpad", ("kcmshell6", "kcm_touchpad")),
    "windows": Action(N_("Window focus and click behavior"), "Input", "preferences-system-windows", ("kcmshell6", "kcm_kwinoptions")),
    "remap": Action(N_("Remap mouse buttons, scroll modifiers and keys"), "Input", "input-keyboard", ("input-remapper-gtk",)),
    "shortcuts": Action(N_("Keyboard shortcuts"), "Input", "input-keyboard", ("kcmshell6", "kcm_keys")),
    "debounce": Action(N_("Keyboard bounce and sticky keys"), "Input", "preferences-desktop-accessibility", ("kcmshell6", "kcm_access")),
    "mixer": Action(N_("Volume mixer"), "Sound volume pin mute app audio output", "audio-volume-high", ("@monet-settings", "sound#mixer")),
    "sound": Action(N_("Sound settings…"), "Sound speakers headphones microphone", "audio-volume-high", ("@monet-settings", "sound")),
    "media-keys": Action(N_("Media keys"), "Sound music playback keyboard player play pause shortcuts", "media-playback-start"),
    "output-order": Action(N_("Preferred sound output order"), "Sound headphones speakers automatic device priority", "audio-card", ("@monet-settings", "sound#output-order")),
    "output": Action(N_("Cycle sound output"), "Sound", "audio-card"),
    "mic": Action(N_("Mute or unmute microphone"), "Sound", "audio-input-microphone", ("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")),
    "media": Action(N_("Player queue and lyrics"), "Sound", "view-media-playlist"),
    "notifications": Action(N_("Notification settings"), "Desktop", "preferences-desktop-notification", ("@monet-settings", "notifications")),
    "theme": Action(N_("Light and wallpaper settings"), "Desktop", "preferences-desktop-theme", ("@monet-settings", "light")),
    "agents": Action(N_("AI session usage"), "System Codex account limits resets allowance Claude Copilot OpenCode tokens", "utilities-terminal"),
    "process-control": Action(N_("End or restart a process"), "System process tree PID force quit", "system-run"),
    "ports": Action(N_("Listening ports"), "System TCP UDP network process tree search quit", "network-wired"),
    "processes": Action(N_("Processes and system monitors"), "System", "utilities-system-monitor", ("plasma-systemmonitor",)),
    "fans": Action(N_("Fan speeds and supported controllers"), "System", "preferences-system-power-management"),
    "devices": Action(N_("USB devices and fan sensors"), "System", "computer"),
    "bluetooth": Action(N_("Bluetooth accessories"), "System", "preferences-system-bluetooth", ("@monet-settings", "bluetooth")),
    "wheel": Action(N_("Favorite actions wheel"), "Desktop", "view-more"),
}
DEFAULT_FAVORITES = ["shelf", "notes", "screenshot", "color", "awake", "sound"]


def stored(settings, key, default):
    try:
        value = json.loads(settings.value(key, "null"))
        return value if isinstance(value, type(default)) else default
    except (ValueError, TypeError):
        return default

def preferences(settings):
    favorites = stored(settings, "favorites", DEFAULT_FAVORITES)
    hidden = stored(settings, "hidden", [])
    return ([key for key in favorites if isinstance(key, str) and key in ACTIONS],
            [key for key in hidden if isinstance(key, str) and key in ACTIONS])


def words(text):
    folded = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c if c.isalnum() else " " for c in folded if not unicodedata.combining(c)).split())


@lru_cache(maxsize=len(ACTIONS))
def search_terms(key):
    action = ACTIONS[key]
    title = words(action.name)
    return title, title + " " + words(action.source_name + " " + key + " " + action.group)


def find_tools(query, favorites, hidden):
    """Rank visible actions consistently in Utilities and desktop search."""
    query = words(query[:256])
    tokens = query.split()
    ranked = []
    favorite_bonus = {key: .02 - i * .001 for i, key in enumerate(favorites[:8])}
    for key in dict.fromkeys([*favorites, *ACTIONS]):
        if key not in ACTIONS or key in hidden:
            continue
        title, terms = search_terms(key)
        if not all(token in terms for token in tokens):
            continue
        if not query:
            score = 0.30
        elif title == query:
            score = 0.95
        elif title.startswith(query):
            score = 0.88
        elif all(token in title for token in tokens):
            score = 0.76
        else:
            score = 0.53
        ranked.append((key, score + favorite_bonus.get(key, 0)))
    return sorted(ranked, key=lambda match: -match[1])
