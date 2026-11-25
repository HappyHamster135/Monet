// SPDX-License-Identifier: GPL-3.0-or-later
// A background GUI with no session-bus Quit method, for last-window-wayland.py.
#include <QApplication>
#include <QSocketNotifier>
#include <QWidget>
#include <sys/signalfd.h>
#include <signal.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    sigset_t mask;
    sigemptyset(&mask);
    sigaddset(&mask, SIGUSR1);
    sigprocmask(SIG_BLOCK, &mask, nullptr);
    QApplication app(argc, argv);
    app.setDesktopFileName("org.monet.NativeCloseFixture");
    app.setQuitOnLastWindowClosed(false);
    QWidget w;
    w.setWindowTitle("Native background app");
    const int fd = signalfd(-1, &mask, SFD_CLOEXEC | SFD_NONBLOCK);
    if (fd < 0) return 1;
    QSocketNotifier ready(fd, QSocketNotifier::Read);
    QObject::connect(&ready, &QSocketNotifier::activated, &w, [&w, fd] {
        signalfd_siginfo info;
        if (read(fd, &info, sizeof(info)) == sizeof(info)) w.show();
    });
    w.show();
    return app.exec();
}
