"""Builds a fake efivarfs directory that looks like a dual-boot laptop."""
import struct, sys, os

GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"

def var(d, name, data, guid=GLOBAL):
    with open(os.path.join(d, f"{name}-{guid}"), "wb") as f:
        f.write(struct.pack("<I", 7) + data)

def load_option(desc, path):
    text = (path + "\0").encode("utf-16-le")
    fp = bytes([4, 4]) + struct.pack("<H", 4 + len(text)) + text + bytes([0x7f, 0xff, 4, 0])
    return struct.pack("<IH", 1, len(fp)) + (desc + "\0").encode("utf-16-le") + fp

d = sys.argv[1]
os.makedirs(d, exist_ok=True)
var(d, "Boot0000", load_option("Windows Boot Manager", "\\EFI\\Microsoft\\Boot\\bootmgfw.efi"))
var(d, "Boot0003", load_option("Fedora", "\\EFI\\fedora\\shimx64.efi"))
var(d, "BootOrder", struct.pack("<HH", 3, 0))
var(d, "BootCurrent", struct.pack("<H", 3))
var(d, "SecureBoot", bytes([1]))
