"""Side-effect-free page construction shared by notch Tools and preferences."""
from importlib import import_module
from actions import ACTIONS, FULL_APPLICATIONS, COMPACT_SETTINGS

# Metadata is imported before the standalone settings process adds shared modules.
SYSTEM_PAGES = COMPACT_SETTINGS - {"screenshot", "color", "ocr", "watch"}

FACTORIES = {
    'awake': ('awake_page','AwakePage','host'),
    'clipboard-expiry': ('clipboard_expiry_page','ClipboardExpiryPage','host'),
    'link-settings': ('link_settings','LinkSettings','host'),
    'media-keys': ('media_keys','MediaKeys','none'),
    'window-switcher': ('window_switcher','WindowSwitcher','none'),
    'extra-clicks': ('extra_clicks','ExtraClicks','none'),
    'wheel-scrolling': ('wheel_scrolling','WheelScrolling','none'),
    'quit-on-close': ('quit_on_close','QuitOnClose','none'),
    'quit-protection': ('quit_protection','QuitProtection','none'),
    'scripts': ('script_page','ScriptPage','settings'),
    'calendars': ('calendars','Calendars','none'),
    'network': ('network_page','NetworkPage','host'),
    'monitor-alerts': ('monitor_page','MonitorPage','host'),
    'fans': ('fan_page','Fans','none'),
    'wallpaper': ('wallpaper_page','WallpaperPage','host'),
    'compress': ('compress_page','CompressPage','none'),
    'color': ('screen_colors','ScreenColors','host'),
    'ocr': ('screen_text','ScreenText','host'),
}

# Heading and explanatory text belong to the settings shell, rather than being
# repeated inside each tool. All of these pages also have a working inline view.
SETTINGS_GROUPS = [
 ('Writing', [('snippets','Save reusable text and typing shortcuts.'), ('emoji','Find and copy emoji without leaving the notch.'),
              ('clipboard-expiry','Choose when copied content is cleared.'), ('link-settings','Remove tracking parameters and set website rules.'),
              ('text-tools','Transform text and inspect word counts.')]),
 ('Capture', [('screenshot','Choose a capture area and copy the result.'), ('record','Screen recording, audio and inline video trimming.'),
              ('watch','Watch a window or region and receive change alerts.'), ('ocr','Select screen text or a QR code to copy.'), ('color','Choose the format used by the screen color picker.'),
              ('color-tools','Convert colors and keep a personal palette.'), ('compress','Convert and reduce the size of images and videos.')]),
 ('Sound', [('sound','Choose outputs, microphones and volume.'), ('output-order','Rank devices for automatic sound output switching.'),
            ('media-keys','Choose which players respond to media keys.')]),
 ('Display & power', [('awake','Keep Monet awake with timers and automatic rules.'), ('cleaning','Pause input while cleaning your keyboard or display.'),
                     ('display','Brightness, night light and supported display features.'), ('power','Power modes and sleep timers.'),
                     ('theme','Use Mist, Smoke or automatic appearance.'), ('wallpaper','Manage your wallpaper collection.')]),
 ('Mouse & windows', [('mouse','Pointer speed, scrolling and button handedness.'), ('touchpad','Pointer speed, tap and typing behavior.'),
                     ('windows','Window activation and first-click behavior.'), ('window-switcher','Choose how Alt+Tab shows windows.'),
                     ('extra-clicks','Filter unwanted repeated mouse clicks.'), ('wheel-scrolling','Configure wheel scrolling and exceptions.'),
                     ('quit-on-close','Choose which apps quit with their last window.'), ('quit-protection','Protect against accidental quit and close shortcuts.')]),
 ('System & files', [('notifications','Popup positions, timing and Do Not Disturb.'), ('bluetooth','Connect and disconnect paired accessories.'),
                    ('network','Network activity and speed tests.'), ('monitor-alerts','Set system monitoring thresholds.'),
                    ('fans','Inspect fans and supported controllers.'), ('devices','Inspect attached USB devices.'), ('ports','Inspect listening ports and their processes.'),
                    ('process-control','Inspect, end or restart a selected process.'),
                    ('downloads','Choose the folder watched by Downloads.'), ('calendars','Manage subscribed calendars.'),
                    ('scripts','Manage saved scripts and their output.'), ('agents','View AI usage and choose local session data.')]),
]


def create_tool_page(key, host, dismiss):
    if key in SYSTEM_PAGES:
        from compact_system import SystemPage
        return SystemPage(host,key)
    if key == 'watch':
        from capture import Preview
        return Preview(host,autostart=False,inline=True)
    if key == 'screenshot':
        from compact_capture import ScreenshotPage
        return ScreenshotPage(host,dismiss)
    if key in FACTORIES:
        module, name, argument = FACTORIES[key]
        constructor = getattr(import_module(module),name)
        page = constructor(*({'host':[host],'settings':[host.settings],'none':[]}[argument]))
        from screen_selection import ScreenSelection
        if isinstance(page,ScreenSelection): page.inline_dismiss = dismiss
        # These pages are for compact controls; full desktop launchers stay in Utilities.
        if key == 'network' and hasattr(page,'manager'): page.manager.hide()
        if key == 'scripts': page.try_button.hide()
        return page
    if key in ('ports','process-control'):
        from ports import ProcessBrowser
        return ProcessBrowser(host,key == 'ports')
    if key == 'downloads':
        from pages import Downloads
        return Downloads(host.settings)
    if key == 'shelf': return host.file_shelf()
    if key == 'notes': return host.pad_page()
    if key == 'agents':
        from agent_page import AgentUsage
        return AgentUsage(host)
    if key in ('wheel-settings','radial'):
        from notch_settings import RadialPreferences
        return RadialPreferences(host, inline=True)
    from notch_pages import create_page
    return create_page('lock' if key == 'cleaning' else key,host,dismiss)


def activate_tool_page(page):
    # No constructors call run_tool(): visiting a page cannot start a capture,
    # change the clipboard, open another app or begin a destructive operation.
    if hasattr(page,'refresh'): page.refresh()
    elif hasattr(page,'reload'): page.reload()
