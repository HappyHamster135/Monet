#!/usr/bin/env python3
"""Style the native greeter; retain KDE's authentication and emergency QML."""
from pathlib import Path
import shutil
import sys


def replace(text, before, after, count=1):
    if text.count(before) != count:
        raise ValueError(f'Greeter source changed: expected {count} occurrences of {before!r}')
    return text.replace(before, after)


def patch(source):
    greeter = Path(source) / 'src/frontend/greeter'
    qml = greeter / 'qml'
    main = (qml / 'Main.qml').read_text()
    login = (qml / 'Login.qml').read_text()
    # A load error must still leave a way to sign in, with the original components.
    (qml / 'KdeMain.qml').write_text(replace(main, 'Login {', 'KdeLogin {', 2))
    (qml / 'KdeLogin.qml').write_text(login)
    main = replace(main, '    readonly property bool softwareRendering:',
                   '    readonly property bool spacious: width >= 1100 && height >= 700\n\n    readonly property bool softwareRendering:')
    main = replace(main, '        BreezeComponents.Clock {', '        MonetClock {')
    main = replace(main, '            id: mainStack\n', '''            id: mainStack
            // A native background shares the control's render-thread fade.
            // No additional blur pass: the compositor softens the painting.
            background: Rectangle {
                visible: root.spacious
                x: (mainStack.width - width) / 2
                y: Math.max(30, (root.height - height) / 2)
                width: Math.min(mainStack.width - 24, 560)
                height: Math.min(root.height - 80, 660)
                radius: 28
                color: root.softwareRendering ? "#242321" : "#d9242321"
                border.color: "#24efece6"
                border.width: 1
            }
''')
    main = replace(main, '            anchors.horizontalCenter: parent.horizontalCenter\n            y: (userListComponent.userList.y + mainStack.y)/2 - height/2',
                   '''            spacious: root.spacious
            width: root.spacious ? root.width * 0.44 : Math.min(root.width - 32, 640)
            x: root.spacious ? root.width * 0.04 : (root.width - width) / 2
            y: root.spacious ? (root.height - height) / 2 : (userListComponent.userList.y + mainStack.y) / 2 - height / 2''')
    main = replace(main, '            anchors.left: parent.left\n            anchors.right: parent.right',
                   '            x: root.spacious ? root.width * 0.51 : 0\n            width: root.spacious ? root.width * 0.46 : root.width')
    main = replace(main, '            height: root.height + Kirigami.Units.gridUnit * 3',
                   '            height: root.spacious ? root.height : root.height + Kirigami.Units.gridUnit * 3')
    # These are native fields: reveal-password, input methods, a11y, keyboard
    # navigation, multi-screen password synchronisation and PAM stay untouched.
    for name in ('userNameInput', 'passwordBox'):
        indent = '        ' if name == 'userNameInput' else '            '
        login = replace(login, f'{indent}id: {name}\n', f'''{indent}id: {name}
{indent}implicitHeight: Math.max(48, contentHeight + topPadding + bottomPadding)
{indent}color: "#EFECE6"
{indent}placeholderTextColor: "#B4AEA5"
{indent}background: Rectangle {{
{indent}    readonly property QtObject margins: QtObject {{
{indent}        readonly property int left: 12
{indent}        readonly property int right: 12
{indent}        readonly property int top: 8
{indent}        readonly property int bottom: 8
{indent}    }}
{indent}    radius: 12
{indent}    color: "#322f2b"
{indent}    border.width: {name}.activeFocus ? 2 : 1
{indent}    border.color: {name}.activeFocus ? "#F2552C" : "#55b4aea5"
{indent}}}
''')
    login = replace(login, '            id: loginButton\n', '''            id: loginButton
            background: Rectangle {
                radius: 12
                color: loginButton.down ? "#cc4524" : loginButton.hovered ? "#fa6842" : "#F2552C"
                opacity: loginButton.enabled ? 1 : 0.5
                border.width: loginButton.visualFocus ? 2 : 0
                border.color: "#FBF7EE"
            }
            palette.buttonText: "#FBF7EE"
            icon.color: "#FBF7EE"
''')
    (qml / 'Main.qml').write_text(main)
    (qml / 'Login.qml').write_text(login)
    shutil.copy2(Path(__file__).with_name('MonetClock.qml'), qml)
    cmake = greeter / 'CMakeLists.txt'
    cmake.write_text(replace(cmake.read_text(), '    qml/Main.qml\n',
                            '    qml/Main.qml\n    qml/MonetClock.qml\n    qml/KdeMain.qml\n    qml/KdeLogin.qml\n'))
    cpp = greeter / 'main.cpp'
    cpp.write_text(replace(cpp.read_text(), '        window->setSource(QUrl("qrc:/qt/qml/org/kde/plasma/login/Main.qml"));',
                          '''        window->setSource(QUrl("qrc:/qt/qml/org/kde/plasma/login/Main.qml"));
        if (window->status() == QQuickView::Error) {
            window->setSource(QUrl("qrc:/qt/qml/org/kde/plasma/login/KdeMain.qml"));
        }'''))


if __name__ == '__main__':
    patch(Path(sys.argv[1]))
