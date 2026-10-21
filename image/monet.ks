# Monet installer: a kickstart for the Fedora network installer.
#
# Two choices on the USB stick's start menu:
#
#   Install Monet and Windows (erases this PC)   <- default
#       Monet picks the PC's main disk and splits it between Monet and
#       Windows. At the end, Monet downloads Windows 11 from Microsoft and
#       installs it by itself after the restart: no BitLocker, no Fast
#       Startup, no questions, Monet Bridge already in place.
#
#   Install Monet next to my Windows   (adds "monet.keep" to the boot line)
#       Keeps the disk as it is; the installer asks where to put Monet.
#
# The installer still asks for Wi-Fi, your name and password. Nothing on the
# disk changes until you click Begin Installation.
# @IMAGE@ is filled in when the installer is built.

%pre --interpreter=/usr/bin/python3 --log=/tmp/monet-pre.log
# Plans the disk for "Install Monet and Windows". Only writes a plan;
# nothing is changed on any disk here.
import json, subprocess

cmdline = open("/proc/cmdline").read().split()
plan = ""

def lsblk():
    out = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,RM,RO,TRAN,PKNAME"],
                         capture_output=True, text=True).stdout
    return json.loads(out or '{"blockdevices": []}')["blockdevices"]

def flag(value):
    return value in (True, 1, "1", "true")

if "monet.keep" not in cmdline:
    devices = lsblk()
    # Never touch the USB stick Monet is running from.
    media = set()
    for arg in cmdline:
        if arg.startswith("inst.stage2=hd:LABEL="):
            label = arg.split("LABEL=", 1)[1].split(":")[0].replace("\\x20", " ")
            dev = subprocess.run(["blkid", "-L", label], capture_output=True, text=True).stdout.strip()
            media.add(dev)
    media_disks = {d.get("pkname") or d["name"] for d in devices if d["path"] in media}
    disks = [
        d for d in devices
        if d["type"] == "disk" and not flag(d.get("rm")) and not flag(d.get("ro"))
        and d.get("tran") != "usb" and d["name"] not in media_disks
        and not d["name"].startswith(("zram", "loop", "sr", "nbd"))
    ]
    if disks:
        disk = max(disks, key=lambda d: int(d["size"]))
        size_mib = int(disk["size"]) // (1024 * 1024)
        windows_mib = min(max(size_mib * 35 // 100, 100 * 1024), 500 * 1024)
        monet_mib = size_mib - windows_mib - 8 * 1024 - 4 * 1024
        if monet_mib < 64 * 1024:
            # Too small to share: Monet takes the whole disk.
            monet_mib = size_mib - 4 * 1024
        name = disk["name"]
        plan = f"""
zerombr
ignoredisk --only-use={name}
clearpart --all --initlabel --disklabel=gpt --drives={name}
reqpart --add-boot
part btrfs.monet --size={monet_mib} --ondisk={name}
btrfs none --label=monet btrfs.monet
btrfs / --subvol --name=root LABEL=monet
"""
        print(f"Monet: {name}, {size_mib} MiB: Monet {monet_mib} MiB, the rest for Windows")

open("/tmp/monet-storage.ks", "w").write(plan)
%end

%include /tmp/monet-storage.ks

# The person installing becomes the administrator; root stays locked.
rootpw --lock

%pre-install --interpreter=/usr/bin/python3 --erroronfail --log=/tmp/monet-check.log
# Before Monet is downloaded: check that it can be, and say why if not,
# instead of the installer's "unknown error".
import json, sys, urllib.error, urllib.request

image = "@IMAGE@"
registry, rest = image.split("/", 1)
repo, tag = rest.rsplit(":", 1)
accept = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
try:
    try:
        with urllib.request.urlopen(f"https://{registry}/token?scope=repository:{repo}:pull", timeout=30) as r:
            token = json.load(r)["token"]
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError("access denied") from None
        raise
    request = urllib.request.Request(f"https://{registry}/v2/{repo}/manifests/{tag}", method="HEAD",
                                     headers={"Authorization": f"Bearer {token}", "Accept": accept})
    urllib.request.urlopen(request, timeout=30).close()
    print(f"MONET: {image} can be downloaded")
except (PermissionError, urllib.error.HTTPError) as e:
    print(f"MONET: {image} can't be downloaded ({e}).")
    print("MONET: The Monet package on GitHub isn't public. Make it public in its Package settings, then try again.")
    sys.exit(1)
except (urllib.error.URLError, OSError) as e:
    print(f"MONET: No internet connection ({e}).")
    print("MONET: Connect to Wi-Fi in Network & Host Name, then try again.")
    sys.exit(1)
%end

ostreecontainer --url=@IMAGE@ --transport=registry --no-signature-verification

%post --erroronfail
# The NVIDIA driver is signed with Universal Blue's key. Ask the firmware to
# trust it, so the driver works with Secure Boot on. It is confirmed once, on
# a blue screen at the next start, with the password "monetsetup".
if [ -f /etc/pki/akmods/certs/akmods-ublue.der ]; then
    mokutil --timeout -1 || :
    printf 'monetsetup\nmonetsetup\n' | mokutil --import /etc/pki/akmods/certs/akmods-ublue.der || :
fi
%end

%post --log=/var/log/monet-install.log
# "Install Monet and Windows": download Windows and get it ready to install
# itself at the next restart. This is the long, quiet part at the end of the
# install. If it fails, Monet still works: choosing Windows in the app menu
# tries again.
if ! grep -qw monet.keep /proc/cmdline; then
    /usr/libexec/monet-prepare-windows || :
fi
%end
