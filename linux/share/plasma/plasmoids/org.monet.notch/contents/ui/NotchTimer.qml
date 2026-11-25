import QtQml

QtObject {
    id: timer
    required property QtObject settings
    readonly property double deadline: Number(settings.deadline) || 0
    readonly property double paused: Math.max(0, settings.timerPaused)
    readonly property int round: settings.focusRound
    readonly property bool active: deadline > 0 || paused > 0 || round > 0
    readonly property bool waiting: round > 0 && !deadline && !paused
    readonly property bool onBreak: round > 0 && !settings.focus
    readonly property bool longBreak: onBreak && round % settings.longBreakEvery === 0
    readonly property int phaseMinutes: onBreak
        ? (longBreak ? settings.longBreakMinutes : settings.shortBreakMinutes) : settings.timerMinutes

    readonly property string completion: settings.timerResult === "rounds" ? i18n("Focus rounds finished")
        : settings.timerResult === "focus" ? i18n("Focus session finished")
        : settings.timerResult === "timer" ? i18n("Timer finished") : ""

    function dismiss() { settings.timerResult = "" }

    signal quietRequested(double until)
    signal finished(string message)

    function remaining(now) {
        if (deadline) return Math.max(0, deadline - now)
        return waiting ? phaseMinutes * 60000 : paused
    }
    function runFor(milliseconds, now) {
        const end = now + milliseconds
        settings.deadline = String(end)
        settings.timerPaused = 0
        if (settings.focus) quietRequested(Math.ceil(end / 1000))
    }
    function start(focus, now) {
        if (active) return
        dismiss()
        settings.focus = focus
        settings.focusRound = focus ? 1 : 0
        runFor(settings.timerMinutes * 60000, now)
    }
    function pause(now) {
        if (!deadline) return
        if (now >= deadline) {
            finishIfDue(now)
            return
        }
        settings.timerPaused = deadline - now
        settings.deadline = ""
        if (settings.focus) quietRequested(0)
    }
    function resume(now) {
        if (paused || waiting) runFor(remaining(now), now)
    }
    function reset() {
        settings.focusRound = 0
        settings.focus = false
        settings.deadline = ""
        settings.timerPaused = 0
    }
    function cancel() {
        if (settings.focus && deadline) quietRequested(0)
        reset()
    }
    function finishIfDue(now) {
        if (!deadline || now < deadline) return
        const work = settings.focus
        const wasBreak = onBreak
        if (work) quietRequested(0)
        settings.deadline = ""
        if (wasBreak) {
            settings.focusRound = round + 1
            settings.focus = true
            finished(i18n("Break finished"))
        } else if (work && round > 0 && round < settings.focusSessions) {
            settings.focus = false
            finished(i18n("Focus session finished"))
        } else {
            const multiple = work && round > 1
            reset()
            settings.timerResult = multiple ? "rounds" : work ? "focus" : "timer"
            finished(completion)
        }
    }
}
