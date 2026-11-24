"""Simulated pointer input on a private KWin test display."""
import socket
import struct
import time


class Pointer:
    def __init__(self, display):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(3)
        self.sock.connect(str(display))
        self.send(1, 1, struct.pack('=I', 2))  # wl_display.get_registry(2)
        self.send(1, 0, struct.pack('=I', 3))  # wl_display.sync(3)
        while True:
            obj, word = struct.unpack('=II', self.sock.recv(8, socket.MSG_WAITALL))
            size, op = word >> 16, word & 0xffff
            data = self.sock.recv(size-8, socket.MSG_WAITALL)
            if obj == 2 and op == 0 and b'org_kde_kwin_fake_input\x00' in data:
                name = struct.unpack_from('=I', data)[0]
                self.send(2, 0, struct.pack('=I', name) + self.string('org_kde_kwin_fake_input')
                          + struct.pack('=II', 3, 4))
                self.send(4, 0, self.string('Monet window fixture') + self.string('Private test session'))
                break
            if obj == 3:
                raise AssertionError('Private KWin input protocol is unavailable')

    def send(self, obj, op, data):
        self.sock.sendall(struct.pack('=II', obj, ((8 + len(data)) << 16) | op) + data)

    @staticmethod
    def string(value):
        data = value.encode() + b'\0'
        return struct.pack('=I', len(data)) + data + b'\0' * (-len(data) % 4)

    def point(self, x, y):
        self.send(4, 9, struct.pack('=ii', round(x * 256), round(y * 256)))

    def click(self, button=0x110):
        self.button(True, button)
        time.sleep(.025)
        self.button(False, button)

    def button(self, down, button=0x110):
        self.send(4, 2, struct.pack('=II', button, int(down)))
