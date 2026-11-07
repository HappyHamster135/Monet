// One countdown for every screen: the greeter loads Logout.qml once per screen
// in one engine, so a key pressed on any of them stops all the countdowns.
.pragma library

var callbacks = [];
var actionOwner = null;

function addCancelAutoTriggerCallback(callback) {
    callbacks.push(callback);
}

function removeCancelAutoTriggerCallback(callback) {
    callbacks = callbacks.filter(function (entry) { return entry !== callback; });
    if (actionOwner === callback) actionOwner = null;
}

// Every screen shares this module in the greeter's engine. A short exit fade
// must not allow a second display to commit a different action in that time.
function beginAction(owner) {
    if (actionOwner !== null || typeof owner !== "function") return false;
    actionOwner = owner;
    cancelAutoTrigger();
    return true;
}

function cancelAutoTrigger() {
    callbacks.forEach(function (callback) {
        if (callback) {
            callback();
        }
    });
}
