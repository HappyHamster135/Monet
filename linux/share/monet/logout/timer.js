// One countdown for every screen: the greeter loads Logout.qml once per screen
// in one engine, so a key pressed on any of them stops all the countdowns.
.pragma library

var callbacks = [];

function addCancelAutoTriggerCallback(callback) {
    callbacks.push(callback);
}

function cancelAutoTrigger() {
    callbacks.forEach(function (callback) {
        if (callback) {
            callback();
        }
    });
}
