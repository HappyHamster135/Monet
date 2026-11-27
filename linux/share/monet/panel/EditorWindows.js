.pragma library
.import QtQml 2.15 as Qml
// A library has the engine's root context. Objects created here stay functional
// after Plasma destroys the short-lived panel/picker request that called us.
// One host per QML engine, shared by every panel and the widget picker. Its
// lifetime must not depend on a panel that the user can remove in this editor.
var sharedHost = null
function forParent(parent) {
    if (!sharedHost) {
        const component = Qt.createComponent(Qt.resolvedUrl("EditorHost.qml"))
        if (component.status !== Qml.Component.Ready) throw new Error(component.errorString())
        sharedHost = component.createObject(null)
    }
    return sharedHost
}
