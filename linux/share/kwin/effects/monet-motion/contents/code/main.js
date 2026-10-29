/*
    Monet Motion: windows glide to where they're put, as in Windows and macOS. Maximized and
    restored (as KWin's Stretch effect does, whose place this takes), snapped into a half, a
    quarter or a layout's part (Monet Snap, KWin's tiles, Windows+arrows), stretched to the
    screen's full height: the window's old picture grows into its new place and fades into
    the new one. A window being dragged or resized by hand is never animated, nor one an app
    resizes in place.
*/

"use strict";

class MonetMotion {
    constructor() {
        effect.configChanged.connect(this.loadConfig.bind(this));
        effect.animationEnded.connect(this.restoreForceBlurState.bind(this));
        effects.windowAdded.connect(this.manage.bind(this));
        for (const window of effects.stackingOrder) {
            this.manage(window);
        }
        this.loadConfig();
    }

    loadConfig() {
        // Monet's glide: a little longer than KWin's stretch, with a soft landing.
        this.duration = animationTime(300);
    }

    manage(window) {
        window.monetBorn = Date.now();
        window.windowFrameGeometryChanged.connect(this.onWindowFrameGeometryChanged.bind(this));
        window.windowMaximizedStateChanged.connect(this.onWindowMaximizedStateChanged.bind(this));
        window.windowMaximizedStateAboutToChange.connect(this.onWindowMaximizedStateAboutToChange.bind(this));
        window.windowStartUserMovedResized.connect(this.onStartUserMovedResized.bind(this));
        window.windowFinishUserMovedResized.connect(this.onFinishUserMovedResized.bind(this));
    }

    // The old picture, kept to fade from: cheap when nothing follows (it fades into itself).
    keepPicture(window) {
        let couldRetarget = false;
        if (window.monetFade) {
            couldRetarget = retarget(window.monetFade, 1.0, this.duration);
        }
        if (!couldRetarget) {
            window.monetFade = animate({
                window: window,
                duration: this.duration,
                animations: [{
                    type: Effect.CrossFadePrevious,
                    to: 1.0,
                    from: 0.0,
                    curve: QEasingCurve.OutCubic
                }]
            });
        }
    }

    morph(window, oldGeometry, newGeometry) {
        if (window.monetMorph) {
            cancel(window.monetMorph);
            delete window.monetMorph;
        }
        window.setData(Effect.WindowForceBlurRole, true);
        window.monetMorph = animate({
            window: window,
            duration: this.duration,
            animations: [{
                type: Effect.Size,
                to: { value1: newGeometry.width, value2: newGeometry.height },
                from: { value1: oldGeometry.width, value2: oldGeometry.height },
                curve: QEasingCurve.OutCubic
            }, {
                type: Effect.Translation,
                to: { value1: 0, value2: 0 },
                from: {
                    value1: oldGeometry.x - newGeometry.x - (newGeometry.width / 2 - oldGeometry.width / 2),
                    value2: oldGeometry.y - newGeometry.y - (newGeometry.height / 2 - oldGeometry.height / 2)
                },
                curve: QEasingCurve.OutCubic
            }]
        });
        if (window.monetFade) {
            // All of it ends on the same frame, or the blur behind goes before the picture lands.
            retarget(window.monetFade, 1.0, this.duration);
        }
    }

    onStartUserMovedResized(window) {
        window.monetHeld = true;
    }

    // Let go of: Monet Snap may put it somewhere now, so keep its picture to glide from.
    onFinishUserMovedResized(window) {
        window.monetHeld = false;
        window.monetLetGo = Date.now();
        if (window.visible) {
            this.keepPicture(window);
        }
    }

    onWindowMaximizedStateAboutToChange(window) {
        if (!window.visible) {
            return;
        }
        window.monetMaximizing = true;
        window.oldGeometry = Object.assign({}, window.geometry);
        if (window.monetMorph) {
            cancel(window.monetMorph);
            delete window.monetMorph;
        }
        this.keepPicture(window);
    }

    onWindowMaximizedStateChanged(window) {
        window.monetMaximizing = false;
        if (!window.visible || !window.oldGeometry) {
            return;
        }
        this.morph(window, window.oldGeometry, window.geometry);
    }

    restoreForceBlurState(window) {
        window.setData(Effect.WindowForceBlurRole, null);
    }

    onWindowFrameGeometryChanged(window, oldGeometry) {
        const geometry = window.geometry;
        const resized = geometry.width != oldGeometry.width || geometry.height != oldGeometry.height;
        // A morph under way and the window resized again (the app's own doing): let it be.
        if (window.monetMorph && resized && !window.monetMaximizing) {
            cancel(window.monetMorph);
            delete window.monetMorph;
        }
        if (window.monetMaximizing || window.monetHeld || window.move || window.resize || !window.visible
                || window.fullScreen || !window.normalWindow || Date.now() - window.monetBorn < 1000 || !resized) {
            return;
        }
        const moved = Math.abs(geometry.x - oldGeometry.x) + Math.abs(geometry.y - oldGeometry.y);
        const grown = Math.max(Math.abs(geometry.width - oldGeometry.width) / Math.max(oldGeometry.width, 1),
                               Math.abs(geometry.height - oldGeometry.height) / Math.max(oldGeometry.height, 1));
        // Just let go (a snap, or full height), or put somewhere else by KWin or a script: an
        // app can resize its window on Wayland but never move it, so moved and resized is ours.
        const letGo = Date.now() - (window.monetLetGo || 0) < 800;
        if (letGo || (moved > 16 && grown > 0.1)) {
            this.morph(window, oldGeometry, geometry);
        }
    }
}

new MonetMotion();
