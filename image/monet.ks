# Monet installer: a kickstart for the Fedora network installer.
#
# Two choices on the USB stick's start menu:
#
#   Install Monet and Windows (erases this PC)   <- default
#       Monet picks the PC's main disk and splits it between Monet and
#       Windows. After the first sign-in, Monet downloads Windows 11 from
#       Microsoft (showing its progress) and, when you say so, restarts to
#       install it by itself: no BitLocker, no Fast Startup, no questions,
#       Monet Bridge already in place.
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

def run(cmd, timeout=60):
    """What a tool printed; nothing if it failed or hung."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception as e:
        print(f"Monet: {cmd[0]} didn't answer ({e})")
        return ""

def lsblk():
    # -l: one flat list with the partitions too, so the USB stick's
    # partition can be traced back to its disk.
    out = run(["lsblk", "-J", "-l", "-b", "-o", "NAME,PATH,SIZE,TYPE,RM,RO,TRAN,PKNAME"])
    try:
        return json.loads(out or "{}").get("blockdevices", [])
    except ValueError:
        return []

def flag(value):
    return value in (True, 1, "1", "true")

if "monet.keep" not in cmdline:
    # Let every disk finish showing up before choosing one.
    run(["udevadm", "settle", "--timeout=30"], timeout=40)
    devices = lsblk()
    # Never touch the USB stick Monet is running from.
    media = set()
    for arg in cmdline:
        if arg.startswith(("inst.stage2=hd:LABEL=", "inst.ks=hd:LABEL=")):
            label = arg.split("LABEL=", 1)[1].split(":")[0].replace("\\x20", " ")
            dev = run(["blkid", "-L", label], timeout=20).strip()
            if dev:
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
    print(f"Monet: the USB stick is {sorted(media_disks) or 'not found'}")

open("/tmp/monet-storage.ks", "w").write(plan)
%end

%include /tmp/monet-storage.ks

# The person installing becomes the administrator; root stays locked.
rootpw --lock

# The PC's name on the network.
network --hostname=monet

%pre-install --interpreter=/usr/bin/python3 --erroronfail --log=/tmp/monet-check.log
# Before the installer downloads Monet: wait for the internet, check Monet can
# be downloaded (and say why if not, instead of "unknown error"), then
# download it here, trying again whenever the connection drops. The installer
# then finds it already downloaded. Lines starting with MONET: are what the
# installer shows if something goes wrong.
import json, os, subprocess, sys, time, urllib.error, urllib.request

image = "@IMAGE@"
registry, rest = image.split("/", 1)
repo, tag = rest.rsplit(":", 1)
accept = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])

def say(text):
    print(f"MONET: {text}", flush=True)

def check():
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

# 1. Wi-Fi can take a moment to connect.
try:
    subprocess.run(["nm-online", "-s", "-q", "-t", "60"], timeout=90)
except Exception:
    pass

# 2. Can Monet be downloaded? A few tries, waiting longer each time.
for attempt in range(6):
    try:
        check()
        say(f"{image} can be downloaded")
        break
    except PermissionError as e:
        say(f"{image} can't be downloaded ({e}).")
        say("The Monet package on GitHub isn't public. Make it public in its Package settings, then try again.")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            say(f"{image} can't be downloaded ({e}).")
            say("The Monet package on GitHub isn't public. Make it public in its Package settings, then try again.")
            sys.exit(1)
        error = e
    except (urllib.error.URLError, OSError) as e:
        error = e
    if attempt == 5:
        say(f"No internet connection ({error}).")
        say("Connect to Wi-Fi in Network & Host Name, then try again.")
        sys.exit(1)
    time.sleep(5 * 2 ** attempt)

# 3. Download Monet into the new system now, with its progress on screen (the
# installer itself only says "Running pre-installation scripts"). A download
# that stops moving for a few minutes is started again; it keeps the pieces it
# already has. Best effort: if this can't finish, the installer downloads it
# once more itself, as it always did.
STALL = 240        # seconds without a byte downloaded or written
STATUS = "/tmp/monet-download.json"

def image_size():
    """Monet's download size: the compressed layers in its manifest."""
    try:
        with urllib.request.urlopen(f"https://{registry}/token?scope=repository:{repo}:pull", timeout=30) as r:
            token = json.load(r)["token"]
        def manifest(ref):
            request = urllib.request.Request(f"https://{registry}/v2/{repo}/manifests/{ref}",
                                             headers={"Authorization": f"Bearer {token}", "Accept": accept})
            with urllib.request.urlopen(request, timeout=30) as r:
                return json.load(r)
        m = manifest(tag)
        if "manifests" in m:
            m = manifest(next(x["digest"] for x in m["manifests"]
                              if x.get("platform", {}).get("architecture") == "amd64"))
        return sum(layer["size"] for layer in m["layers"])
    except Exception as e:
        print(f"Monet: size unknown ({e})", flush=True)
        return 0

def received():
    """Bytes received on every network connection so far."""
    total = 0
    try:
        for line in open("/proc/net/dev").read().splitlines()[2:]:
            name, data = line.split(":", 1)
            if name.strip() != "lo":
                total += int(data.split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return total

def written(path):
    st = os.statvfs(path)
    return (st.f_blocks - st.f_bfree) * st.f_frsize

def display_env():
    """The installer's screen, from the nearest parent that has one."""
    pid = os.getpid()
    for _ in range(12):
        try:
            env = dict(item.split("=", 1) for item in
                       open(f"/proc/{pid}/environ", "rb").read().decode(errors="replace").split("\0") if "=" in item)
            pid = int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
        if env.get("WAYLAND_DISPLAY") or env.get("DISPLAY"):
            return {k: env[k] for k in ("WAYLAND_DISPLAY", "DISPLAY", "XDG_RUNTIME_DIR", "XAUTHORITY") if k in env}
    return {}

def tell(**status):
    try:
        with open(STATUS + ".new", "w") as f:
            json.dump(status, f)
        os.replace(STATUS + ".new", STATUS)
    except OSError:
        pass

def show_window():
    if not os.path.exists("/usr/libexec/monet-download"):
        return None
    try:
        return subprocess.Popen(["/usr/bin/python3", "/usr/libexec/monet-download", STATUS],
                                env=dict(os.environ, **display_env()), stdout=subprocess.DEVNULL,
                                stderr=open("/tmp/monet-download-window.log", "w"))
    except OSError:
        return None

def pull(root, total, start, log):
    """One try: True when done; False when it failed or stopped moving."""
    env = dict(os.environ, LC_ALL="C.UTF-8")
    proc = subprocess.Popen(["ostree", "container", "image", "pull", f"{root}/ostree/repo",
                             f"ostree-unverified-registry:{image}"], stdout=log, stderr=subprocess.STDOUT, env=env)
    seen = (received(), written(root))
    moved = time.time()
    rates = []
    while proc.poll() is None:
        time.sleep(3)
        now = (received(), written(root))
        if now[0] - seen[0] > 256 * 1024 or now[1] - seen[1] > 1024 * 1024:
            seen, moved = now, time.time()
        elif time.time() - moved > STALL:
            print("Monet: the download stopped moving; starting it again", flush=True)
            proc.kill()
            proc.wait()
            return False
        got = max(0, now[0] - start)
        rates = (rates + [(time.time(), got)])[-20:]
        speed = (rates[-1][1] - rates[0][1]) / max(1, rates[-1][0] - rates[0][0])
        eta = (total - got) / speed if total and speed > 0 and got < total else None
        tell(got=got, total=total, eta=eta)
    return proc.returncode == 0

root = next((r for r in ("/mnt/sysimage", "/mnt/sysroot") if os.path.ismount(r)), None)
if root:
    window = None
    try:
        subprocess.run(["ostree", "admin", f"--sysroot={root}", "init-fs", root], check=True, timeout=120)
        total = image_size()
        start = received()
        tell(got=0, total=total)
        window = show_window()
        with open("/tmp/monet-download.log", "a") as log:
            for attempt in range(8):
                if pull(root, total, start, log):
                    say("Monet is downloaded")
                    break
                tell(got=max(0, received() - start), total=total,
                     note="The connection dropped. Picking up where it stopped…")
                time.sleep(min(10 * (attempt + 1), 60))
    except Exception as e:
        print(f"Monet: couldn't download ahead ({e}); the installer will", flush=True)
    finally:
        tell(done=True)
        if window:
            try:
                window.wait(timeout=5)
            except Exception:
                window.kill()
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

%post --nochroot
# Keep the Wi-Fi networks used during the install, so Windows can use them
# too. monet-prepare-windows turns them into Windows profiles, then deletes them.
mkdir -p "$ANA_INSTALL_PATH/var/lib/monet/wifi"
cp /etc/NetworkManager/system-connections/*.nmconnection "$ANA_INSTALL_PATH/var/lib/monet/wifi/" 2>/dev/null || :
chmod -R go-rwx "$ANA_INSTALL_PATH/var/lib/monet/wifi"
%end

%post --log=/var/log/monet-install.log
# "Install Monet and Windows": Windows downloads after the first sign-in,
# where Monet shows its progress, instead of quietly here at the end of the
# install (where a 7 GB download looked like the installer had stopped).
if ! grep -qw monet.keep /proc/cmdline; then
    mkdir -p /var/lib/monet
    echo waiting > /var/lib/monet/windows-setup
fi
%end
