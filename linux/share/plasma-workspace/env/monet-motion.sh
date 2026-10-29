# Monet's motion where the processor draws the screen (a virtual machine, a graphics card whose
# driver didn't load: no render node in /dev/dri). KWin leaves every animation out there, so the
# bar stopped sliding away and back and windows popped in; with processor to spare, Monet keeps
# them. Sourced by Plasma as it starts, before KWin.
if ! ls /dev/dri/renderD* >/dev/null 2>&1 && [ "$(nproc 2>/dev/null || echo 1)" -ge 6 ]; then
    KWIN_EFFECTS_FORCE_ANIMATIONS=1
    export KWIN_EFFECTS_FORCE_ANIMATIONS
fi
