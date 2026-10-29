#!/usr/bin/env python3
"""Apply Monet's presentation changes to the pinned KeePassXC source, or fail closed."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
VERSION = "2.8.0"
SHA256 = "4ed4b77d375f021fc04648c257fedfb41dc13c6bd5c4965d8ded31284c9c653c"
URL = f"https://github.com/keepassxreboot/keepassxc/releases/download/{VERSION}/keepassxc-{VERSION}-src.tar.xz"


def changes():
    return {
        "src/gui/MainWindow.cpp": [
            ('const QString MainWindow::BaseWindowTitle = "KeePassXC";',
             'const QString MainWindow::BaseWindowTitle = "Passwords — Monet preview";'),
            ('    restoreConfigState();\n    updateMenuActionState();\n}',
             '    restoreConfigState();\n    updateMenuActionState();\n#include "MonetWindow.inc"\n}'),
        ],
        "src/main.cpp": [
            ('QGuiApplication::setDesktopFileName("org.keepassxc.KeePassXC");',
             'QGuiApplication::setDesktopFileName("monet-passwords-preview");'),
        ],
        "src/gui/DatabaseOpenWidget.ui": [
            ('<string>Enter Password:</string>', '<string>Vault password:</string>'),
        ],
        "src/gui/DatabaseOpenWidget.cpp": [
            ('auto label = tr("Unlock KeePassXC Database");', 'auto label = tr("Unlock your vault");'),
        ],
        "src/gui/WelcomeWidget.cpp": [
            ('m_ui->welcomeLabel->setText(tr("Welcome to KeePassXC %1").arg(KEEPASSXC_VERSION));',
             'm_ui->welcomeLabel->setText(tr("Your passwords, close at hand."));\n'
             '    m_ui->startLabel->setText(tr("Keep your logins in an encrypted vault on this PC.\\nThis preview is for made-up logins."));\n'
             '    m_ui->startLabel->setWordWrap(true);\n'
             '    m_ui->buttonNewDatabase->setText(tr("Create a vault"));\n'
             '    m_ui->buttonOpenDatabase->setText(tr("Open a vault"));\n'
             '    m_ui->buttonImport->setText(tr("Import passwords"));\n'
             '    m_ui->recentLabel->setText(tr("Recent vaults"));'),
            ('m_ui->iconLabel->setPixmap(icons()->applicationIcon().pixmap(64));',
             'm_ui->iconLabel->setPixmap(QIcon::fromTheme("preferences-desktop-user-password", icons()->applicationIcon()).pixmap(64));'),
        ],
        "src/core/Config.cpp": [
            ('{Config::GUI_HideMenubar, {QS("GUI/HideMenubar"), Roaming, false}}',
             '{Config::GUI_HideMenubar, {QS("GUI/HideMenubar"), Roaming, true}}'),
            ('{Config::GUI_ToolButtonStyle, {QS("GUI/ToolButtonStyle"), Roaming, Qt::ToolButtonIconOnly}}',
             '{Config::GUI_ToolButtonStyle, {QS("GUI/ToolButtonStyle"), Roaming, Qt::ToolButtonTextBesideIcon}}'),
            ('{Config::BackupBeforeSave,{QS("BackupBeforeSave"), Roaming, false}}',
             '{Config::BackupBeforeSave,{QS("BackupBeforeSave"), Roaming, true}}'),
            ('{Config::GUI_ApplicationTheme, {QS("GUI/ApplicationTheme"), Roaming, QS("auto")}}',
             '{Config::GUI_ApplicationTheme, {QS("GUI/ApplicationTheme"), Roaming, QS("classic")}}'),
            ('{Config::Security_LockDatabaseIdleSeconds, {QS("Security/LockDatabaseIdleSeconds"), Roaming, 900}}',
             '{Config::Security_LockDatabaseIdleSeconds, {QS("Security/LockDatabaseIdleSeconds"), Roaming, 300}}'),
            ('{Config::Security_QuickUnlock, {QS("Security/QuickUnlock"), Local, true}}',
             '{Config::Security_QuickUnlock, {QS("Security/QuickUnlock"), Local, false}}'),
        ],
        "tests/CMakeLists.txt": [
            ('set(TEST_LIBRARIES keepassxc_gui Qt6::Test)',
             'set(TEST_LIBRARIES keepassxc_gui Qt6::Test)\n'
             'add_unit_test(NAME testmonetpasswords SOURCES TestMonetPasswords.cpp LIBS ${TEST_LIBRARIES})'),
        ],
    }


def apply(root):
    pending = {}
    for name, edits in changes().items():
        text = (root / name).read_text(encoding="utf-8")
        for before, after in edits:
            if text.count(before) != 1:
                raise ValueError(f"Upstream changed or already patched: {name}")
            text = text.replace(before, after)
        pending[root / name] = text
    pending[root / "src/gui/MonetWindow.inc"] = (HERE / "MonetWindow.inc").read_text(encoding="utf-8")
    pending[root / "tests/TestMonetPasswords.cpp"] = (HERE / "TestMonetPasswords.cpp").read_text(encoding="utf-8")
    for path, text in pending.items():
        path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    apply(Path(sys.argv[1]))
