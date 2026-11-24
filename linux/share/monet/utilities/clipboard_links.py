"""Clean a newly copied plain web link when enabled for this Wayland session."""
import asyncio
import ctypes as C
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys

from links import clean_url

UNIT = "monet-clean-links.service"
LIMIT = 8192
RECEIVE = C.CFUNCTYPE(None, C.c_int)
SEND = C.CFUNCTYPE(None, C.c_int, C.c_void_p, C.c_size_t)


class Clipboard:
    def __init__(self, loop):
        self.loop = loop
        self.lib = C.CDLL(str(Path(__file__).with_name("libmonetclipboard.so")))
        self.lib.clip_open.argtypes = [RECEIVE, SEND]
        self.lib.clip_replace.argtypes = [C.c_char_p, C.c_size_t]
        self.lib.clip_replace.restype = None
        self.lib.clip_watch.argtypes = [C.c_int]
        self.lib.clip_watch.restype = None
        self.watching = True
        self.drained = False
        self.writers = 0
        self.callbacks = RECEIVE(self.selection), SEND(self.send)
        self.input_fd = None
        self.timeout = None
        self.fd = self.lib.clip_open(*self.callbacks)
        if self.fd < 0:
            raise RuntimeError("This desktop does not provide Wayland clipboard management.")
        loop.add_reader(self.fd, self.dispatch)
        self.flush()

    def flush(self):
        status = self.lib.clip_flush()
        if status < 0:
            self.loop.stop()
        elif status > 0:
            self.loop.add_writer(self.fd, self.flush)
        else:
            self.loop.remove_writer(self.fd)

    def dispatch(self):
        if self.lib.clip_dispatch() < 0:
            self.loop.stop()
        else:
            self.flush()
            self.finish_if_idle()

    def watch(self, on):
        self.watching = on
        self.lib.clip_watch(self.watching)
        if not self.watching:
            self.close_input()
            self.finish_if_idle()

    def finish_if_idle(self):
        if not self.watching and not self.writers and not self.lib.clip_retaining():
            self.drained = True
            self.loop.stop()

    def close_input(self):
        if self.input_fd is not None:
            self.loop.remove_reader(self.input_fd)
            os.close(self.input_fd)
            self.input_fd = None
            self.timeout.cancel()
            self.buffer = None

    def selection(self, fd):
        self.close_input()
        if fd >= 0:
            os.set_blocking(fd, False)
            self.input_fd = fd
            self.buffer = bytearray()
            self.timeout = self.loop.call_later(1.5, self.close_input)
            self.loop.add_reader(fd, self.read, fd)

    def read(self, fd):
        if self.input_fd != fd:
            return
        try:
            data = os.read(fd, LIMIT + 1 - len(self.buffer))
        except BlockingIOError:
            return
        except OSError:
            self.close_input()
            return
        if data:
            self.buffer.extend(data)
            prefix = self.buffer[:8].lower()
            if len(self.buffer) > LIMIT or not any(s.startswith(prefix) or prefix.startswith(s)
                                                   for s in (b"http://", b"https://")):
                self.close_input()
            return
        data = self.buffer
        self.close_input()
        try:
            original = data.decode("utf-8")
            if original.strip() != original:
                return
            clean = clean_url(original)
        except ValueError:
            return
        if clean != original:
            payload = clean.encode()
            self.lib.clip_replace(payload, len(payload))
            self.flush()

    def send(self, fd, address, length):
        self.writers += 1
        payload = memoryview(C.string_at(address, length))
        os.set_blocking(fd, False)

        def close():
            self.loop.remove_writer(fd)
            os.close(fd)
            timeout.cancel()
            self.writers -= 1
            self.finish_if_idle()

        def write():
            nonlocal payload
            try:
                payload = payload[os.write(fd, payload):]
            except BlockingIOError:
                pass
            except OSError:
                close()
                return
            if payload:
                self.loop.add_writer(fd, write)
            else:
                close()

        timeout = self.loop.call_later(2, close)
        write()


def control(*args):
    return subprocess.run(["systemctl", "--user", *args, UNIT], capture_output=True, text=True, timeout=12)


def enabled():
    return control("is-enabled").stdout.strip() in ("enabled", "enabled-runtime")


def configure(on):
    before = enabled()
    result = control("enable" if on else "disable")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not change copied link settings.")
    # A disabled service can finish serving the last clean link until its
    # clipboard owner changes. Re-enabling it resumes observation in place.
    if on:
        result = control("reload-or-restart")
        if result.returncode and not before:
            control("disable")
    elif control("is-active").returncode == 0:
        result = control("kill", "--kill-whom=main", "--signal=SIGUSR2")
        if result.returncode and control("is-active").returncode:
            return  # The draining instance has already exited.
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not apply copied link settings.")


def main():
    args = sys.argv[1:]
    if args == ["status"]:
        print("on" if enabled() else "off")
        return 0
    if args in (["on"], ["off"]):
        configure(args == ["on"])
        return 0
    if args:
        return 2
    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        clipboard = Clipboard(loop)
        loop.add_signal_handler(signal.SIGUSR1, clipboard.watch, True)
        loop.add_signal_handler(signal.SIGUSR2, clipboard.watch, False)
        address = os.environ.get("NOTIFY_SOCKET")
        if address:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify:
                notify.sendto(b"READY=1", "\0" + address[1:] if address.startswith("@") else address)
        loop.run_forever()
        return 0 if clipboard.drained else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
