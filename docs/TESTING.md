# Testing Monet on real hardware

## 0.9.8-5 reinstall handoff

The [release checklist](../PLAN.md#098-5-release-checklist) records completed
tests and the remaining hardware checks. The [change list](../RELEASE_NOTES.md#new-in-098-5-everyday-reliability)
describes what to try. The [release manifest](../image/releases/0.9.8-5.json)
pins the two signed images, both ISOs, the Windows USB Maker and Bridge, the
Linux package, and all five OCI archive parts. Keep those exact files together
for testing or publication. Use the `v0.9.8-5` draft under the repository's
GitHub Releases to retrieve them after a reset.

The final Setup ISO was written to the Kingston DataTraveler and read back in
full. All 1,317,404,672 bytes matched the SHA-256 in the manifest. On the
ThinkPad, restart, press **F12** at the Lenovo logo, choose the Kingston,
and check whether Setup reaches **Hello**. Check keyboard and touchpad access
and record the Secure Boot setting and any firmware message. This smoke test
ends before selecting a drive. The ThinkPad last had Secure Boot disabled
and lacked the third-party UEFI CA used by the installer shim. Secure Boot
passed in the installer VMs.

The candidate ISOs pin exact image digests. To continue to a full reinstall
before the version is published, the installer must reach a test mirror
serving those signed digests. The USB contains the installer environment.
The signed images are in the OCI parts in the GitHub draft. For an upgrade
test, stage the signed NVIDIA image, reboot, and check the deployed digest
with `bootc status`, the update policy with `sudo bootc upgrade --check`
against the same mirror, and the GPU with `nvidia-smi` and
`systemctl status nvidia-cdi-refresh.service`. Leave at least 64 GiB free.
The VM rehearsal verified the update and rollback, while its virtual GPU
could not exercise the NVIDIA driver.

On the installed candidate, try **Settings → Light & Wallpaper → Taskbar
layout**. A fresh profile starts with **One bar**. Choose **Three bars**,
remove the middle panel, then select **Three bars** again. At larger display
scales, move a widget, select **Done**, and change the scale back and forth
to check that the saved positions return. After waking the laptop, check
whether Quick Settings and Sound reflect Ethernet and USB audio disconnected
during sleep. Repeat the Files and Store interruption checks with spare media.

### Same-hardware measurements

Record three cold boots per OS on the same laptop. Keep track of OS and app
versions, brightness, resolution, power profile, peripherals and network.
Use the same app and local workload, for example Firefox and a saved page.
Record power-on to sign-in, login submission to a usable desktop, app launch
to the first interactive view, and Shut Down confirmation to the power light
turning off. Keep firmware time separate where the OS reports it. Take the
median of comparable runs and record update restart separately. Turn off
Windows Fast Startup for the full-shutdown comparison.

For idle battery draw, compare 30 minutes with the display on, AC disconnected,
and both systems idle after startup. Use the same brightness, power profile,
network and peripherals. Record starting and ending energy in Wh where
available and divide the difference by runtime in hours for average draw in W.
Retain the OS timings alongside stopwatch or video measurements. The ThinkPad
has a Monet 0.9.8 baseline and needs a Windows install for this comparison.
Confirm the disk layout again after reinstalling before allocating space.

## Local Monet 0.9.8-5 checks

The installed 0.9.8 laptop took 52.7 s through systemd startup, including
23.1 s in firmware and the boot loader. Plasma reached its workspace target
4.6 s after the sign-in session opened. One previous update restart took
11.6 s from logind's restart request to systemd's shutdown handoff. The
NVIDIA Flatpak runtime sync took 6.9 s on the installed image's boot
critical path after the network-online wait. The candidate moves that sync
behind a timer. The hardware timing needs repeating with the rebuilt image.

Five alternating launches per build used the same laptop and a private KWin
Wayland session. Median time to the initial data-ready frame was 473 ms on
0.9.8 and 519 ms on the candidate for Settings, and 486 ms and 491 ms for
Store. Earlier runs had smaller differences or the opposite order. Files
mapped its window and finished listing a 1,000-file folder in a median
314 ms with the system launcher and 303 ms with the account preview.
These samples don't establish a repeatable speed gain.

Seven later launches per build on the ThinkPad gave data-ready medians of
653 ms on 0.9.8 and 664 ms on the candidate for Settings, and 548 ms and
576 ms for Store. Files mapped and finished listing at 417 ms with the
system launcher and 440 ms with the account preview. These runs used private
Wayland sessions, a local workload and the Intel GPU. They establish a local
Monet baseline for the comparison with Windows.

Bridge checks and downloads after Windows sign-in. Back to Monet uses the
staged package without contacting GitHub. The Windows target compiles and the
PowerShell fixtures covered success, interrupted downloads, damaged staged
packages, and restart handoff. The remaining performance runs are repeated
cold boots, sign-in, ordinary shutdown, and unplugged idle battery drain on
matching hardware for both systems.

The local performance worksheet includes matching stopwatch milestones, boot
and shutdown log commands, and 30-minute battery recorders. On the ThinkPad,
the Monet recorder read 47.5 Wh on AC, excluded the wireless mouse battery,
and refused to record an idle discharge until external power was removed.
PowerShell parsing and fixture tests passed for the Windows recorder. Its
battery API still needs checking on physical Windows hardware. The worksheet
and recorders are under `target/098-5-local/desktop/followup/try/hardware/`.

Keyboard and layout checks covered Settings, Store, Files and Transfers.
The large-text and right-to-left checks exposed clipped Settings controls
and an off-screen ranked Store card. Settings, Store, Transfers and the
Files extraction dialog passed with 16-point text, 150% scale and Arabic
translations. The fixes are in the account preview.
Orca spoke labels and control roles in Settings, Store, and Files in an
isolated Plasma session. The first pass found that Tab skipped both search
fields. After the fix, Orca spoke “Search settings” and “Find an app” when
Tab reached them. It also spoke Pause, Cancel, Open folder, Resume, and
Retry in the Transfers panel with test jobs. Speech Dispatcher generated
audio in the private session. The full manual walkthrough remains open.
All 60 focused checks passed. The 36 Settings, Store, and Transfers
navigation checks also passed at 16-point text, 150% scale, and Arabic
right-to-left layout.

Files' main window was tested separately in the signed AMD/Intel VM at
16-point text and 150% app scale with Arabic and the Monet Solid theme.
Keyboard shortcuts reached the address field, tabs, split view, details
view, and search. The file list and search read right to left, and the
Places panel retained Dolphin's left dock position. A keyboard copy into
an Arabic-named folder matched the source SHA-256. The temporary profile
and sample files were removed from the VM.

A disposable filesystem reached ENOSPC. Files reported zero free space,
and Store kept its queue and could save it again after space was freed.
Ark showed a disk-full error. After dismissal, Transfers recorded failure
and extraction succeeded on a larger filesystem. A queued Files extraction
rejected a detached mount without writing to the underlying directory.
In private network namespaces, Files' KIO backend returned an error when
a WebDAV share disappeared and copied again once it came back. Store
retained its catalog cache while disconnected and refreshed after
reconnect. A local Flatpak repository reproduced the install stall by
withholding an object response. Store now supervises the download process
and asks Flatpak to deploy from local objects once the download finishes.
A stalled download cancelled in 0.2 s without installing the app. A server
error and a silent connection both produced the offline result, and each
case installed successfully after retry. Tests covered a disposable user
installation and a system installation with Flatpak's helper on a private
session bus. Both rebuilt images passed the cancellation and server-error
tests using their installed Store helpers. The kernel disconnected the
physical Kingston USB during a Files copy from its read-only installer
volume. KIO reported a read error and removed the partial destination.
The next copy matched SHA-256 after reconnecting the device.

The shipped Store worker also ran real Flatpak transactions on a capped
96 MiB filesystem inside the signed AMD/Intel VM. The test filled it to
ENOSPC, then left 6 MiB for queue receipts before starting the install.
Both a user installation and a dedicated system installation kept the job
with a no-space error and no app deployed. Removing the filler let the
same job retry and install the app. The system test used an isolated
installation run as root.

In another signed AMD/Intel VM, the Store worker was downloading a Flatpak
when the VM process was killed. After reboot, Downloads kept the request,
marked it Interrupted and offered Retry. Flatpak showed no app deployed
before Retry. Retrying from Downloads finished both a user install and a
system-wide install through Flatpak's system helper. The installed file
matched the source checksum in both cases. The first system test lost the
test remote's trust key on reboot. Importing and flushing that key before
repeating the full test kept the fixture valid across the restart.
Screenshots, queue records and helper logs are in
`try/hardware/store-interruption/`.

The AMD/Intel and NVIDIA images were rebuilt locally against the same pinned
Bazzite bases. Each passed 13 bootc lint checks with one skip and a warning
about build mount paths under `/var`. The installed Store, Settings and
Quick Settings files match the build inputs.

Both OCI manifests were signed with the Monet release key and verified
through a loopback registry. The same policy rejected an unsigned offer
and a signature checked against a different key. Cosign also submitted the
signature records to its public transparency log. The image data and release
files stayed local.

Monet Setup and Fedora fallback were refreshed with both exact digests.
Their packaged pins, signed boot files, and media checks passed. The shared
USB writer copied both ISOs onto disposable disk files. An independent
read-back passed, and both disk files booted in Secure Boot VMs. The Linux
and Windows packages were refreshed from the image build, and Bridge is
byte-identical in both packages and both images. All five assets passed
their checksums. The 104 Rust tests, Windows-target compilation, and
PowerShell syntax and behavior tests passed.

The exact Bridge package installed on Windows 11 Enterprise Evaluation in a
two-disk Secure Boot VM. Its first restart returned to the exact AMD/Intel
Monet image with SELinux enforcing. A separate run set the installed version
record to 0.9.8 to exercise the update comparison without replacing the
candidate Bridge binary. Windows Task Scheduler downloaded and verified the
exact 0.9.8-5 ZIP from a local HTTPS mirror. With the Windows network link
disconnected, the desktop's Back to Monet shortcut started the Update task.
It installed the staged package and restarted into Monet. The mirror received
no additional requests during the restart. Windows reported 0.9.8-5 on its
next boot, and the installed Bridge and updater hashes matched the package.

A separate two-disk Secure Boot VM installed the exact published Windows
Bridge 0.9.8 package. Its update check skipped `v0.9.8-5` when the local
mirror listed both releases. Back to Monet queried the mirror again before
restarting. Installing the 0.9.8-5 ZIP over 0.9.8 added the background update
task, and the updated Bridge recognized its version. With no package staged,
its next Back to Monet run made no mirror requests. Both returns booted the
signed AMD/Intel image with SELinux enforcing. Evidence is in
`try/hardware/bridge-migration/`.

A Windows 11 Enterprise Evaluation 26H2 VM (build 26300.9457) also ran
Back to Monet while StageUpdate was downloading the exact Bridge ZIP.
The local HTTPS mirror sent 64 KiB and then paused for 160 seconds.
Windows reported the task running and no verified package ready. Bridge
requested the restart within one second of opening the desktop shortcut.
The signed AMD/Intel image was reachable over SSH 38 seconds after the
mirror sent the first chunk, with Secure Boot and SELinux enforcing. The
mirror did not finish sending the ZIP or receive a checksum request, and
the Windows disk had no update or restart receipt after the return.

Both release ISOs were written to a physical 64 GB Kingston DataTraveler
from Monet and read back in full. Each read-back matched the SHA-256 in
the release checksums. The packaged Windows USB Maker then wrote and
verified Monet Setup on the same stick through a Windows VM's virtual USB
controller. An independent read-back found 16 bytes changed in the
protective MBR and primary GPT to fit the stick. The GPT checksum was valid
and the rest of the ISO matched. The stick booted to Monet Setup's Hello
screen in a Secure Boot VM. The host recognized the 0.9.8-5 volume and the
stick was left unmounted. Booting from the laptop's firmware remains open.

The ThinkPad P16s Gen 2 test laptop currently reports Secure Boot disabled.
Its firmware trust database includes Microsoft's Windows boot certificates.
It has neither third-party UEFI CA that signed the installer shim. Both final
ISOs carry the same shim in their filesystem and embedded EFI boot image.
The shim has signatures from Microsoft's 2011 and 2023 third-party UEFI CAs.
The certificate check was read-only. The first physical USB test can record
whether Setup reaches Hello with the current firmware settings. Secure Boot
qualification also requires the firmware's third-party UEFI CA trust option.
See [Microsoft's certificate guide](https://support.microsoft.com/en-us/servicing/os/secure-boot/2025/06/windows-secure-boot-certificate-expiration-and-ca-updates).

The packaged USB Maker also tested the final Monet Setup and Fedora fallback
ISOs on Windows 11 Enterprise Evaluation build 26300.9457. With Setup
available, the Maker fetched its release checksum, downloaded the ISO, and
wrote and verified a disposable 4 GiB USB disk. An independent read-back
compared all 1,317,404,672 bytes. Windows adjusted 13 bytes of disk-sizing
metadata, and both GPT headers and their partition entries passed CRC checks.
The written USB booted to Setup's Hello screen in a Secure Boot VM.

The same Maker tested the final Fedora fallback on Windows 11
Enterprise Evaluation build 26300.9457. The private mirror returned 404
for Setup. The Maker selected the fallback, fetched its release checksum,
downloaded it, and wrote and verified a disposable 4 GiB USB disk. The
independent read-back compared all 1,264,386,048 bytes. Windows adjusted
13 bytes of disk-sizing metadata, and both GPT headers and their partition
entries passed CRC checks. The resulting USB reached the fallback's
graphical summary with Secure Boot enabled and zero writes to the test
installation disk. The Windows and USB test disks were removed.

Monet Setup resumed the pinned NVIDIA installation from its local cache
with the VM's network adapter disconnected. The recovery key unlocked the
encrypted disk. After Secure Boot enrollment, Monet rebooted through the
TPM, retired the temporary startup key, and checked the signed rolling
channel. Rollback booted the earlier deployment of the same image digest,
kept Secure Boot and SELinux enabled, and preserved a saved file.

The Fedora fallback installed the pinned AMD/Intel image and booted it with
Secure Boot and SELinux enforcing. Its first VM run stopped in an added test
script. The corrected run completed the installer, enrolled the Secure Boot
key, and checked the signed rolling channel through the local registry.

The local release archive contains both exact OCI exports, split into five
checksummed parts. The publication validator now accepts the numbered
suffix in `0.9.8-5` and verified all five parts. The archive contents
matched the local exports on read-back.
`image/releases/0.9.8-5.json` records both signed image digests, the five
archive parts and all five public downloads with their checksum list. The
qualified workflow checks the draft's public files against this record before
publishing images. The default build and direct image push both leave a new
qualified version to that workflow. A local rehearsal used the same checks
to verify the public files, unpack the OCI archive and match both manifests.
Both final ISOs carry those digests. The release files and archive are local.

A loopback OCI registry rehearsal copied both exact images to their versioned
and rolling tags. After loading the existing Monet signature attachments,
pulls of all four references passed the release-key policy. No signing key
was used for the rehearsal. The Linux package and both installed images also
matched the 11 changed desktop files, with normal install path substitutions.
The two Windows installer and updater scripts matched their source after the
version substitution. The registry and pull working copies were removed. An
hourly home snapshot taken during the rehearsal retained about 16.4 GiB of
their data, and the filesystem still had 114 GiB free.
Evidence is in `target/098-5-local/desktop/followup/publication-rehearsal/`.

The keyboard follow-up adds the Settings and Store fixes to both local
images and the Linux package. Both new images passed bootc lint, and the
archive read-back verified 385 OCI blobs across five parts. Monet Setup
and Fedora fallback were refreshed with the new digests. Their signed
boot files matched the earlier media. The fallback media check passed.
Both updated manifests were signed offline with the Monet release key.

The refreshed Monet Setup ISO completed an encrypted NVIDIA install in a
Secure Boot VM. The recovery key unlocked the test disk and a later boot
through the TPM retired the temporary startup key. The Fedora fallback
used the refreshed kickstart with a local mirror and unattended VM
settings. It completed an AMD/Intel install. Both installed guests booted
the expected manifest with Secure Boot and SELinux enforcing, and the
installed Settings and Store files matched the keyboard fix.

After an additional reboot, both guests rejected their rolling image when
the local registry withheld its signature. Restoring the release signature
let both checks succeed. Each rolling tag already pointed to the installed
digest, so both checks reported no changes.

A separate AMD/Intel VM booted the earlier 0.9.8-5 digest and then received
the keyboard follow-up through the signed rolling channel. The guest
rejected the new digest without its signature. With the signature restored,
bootc fetched the two changed layers, staged the image, and rebooted into
the new digest. The earlier digest remained available for rollback and a
saved file survived. The signed update check then reported no changes.
Secure Boot and SELinux stayed enabled. This guest also reached the full
Plasma desktop for local testing. The refreshed Setup ISO was written to
the physical Kingston and verified against its full SHA-256 checksum.
Booting the stick on the laptop's firmware remains open.

An isolated AMD/Intel VM also booted the exact published 0.9.8 image after
verifying its signature with the Monet release key. It rejected the final
0.9.8-5 digest with its signature withheld, then accepted and booted it
after the local registry restored the signature. The next signed-channel
check reported no changes. `monet rollback` returned to the published
0.9.8 digest. Secure Boot, SELinux enforcement and the checksum of a file
saved on 0.9.8 survived the upgrade and rollback. Evidence is in
`try/hardware/previous-release-upgrade/`.

The encrypted NVIDIA VM also installed the earlier 0.9.8-5 digest from
Monet Setup. It rejected the current digest while its release signature
was withheld. Restoring the signature let bootc stage the two changed
layers (97.1 kB) and reboot into the current digest. Monet's rollback
command then rebooted into the earlier digest and restored the current
digest on a second pass. Secure Boot, SELinux enforcement, TPM unlock,
and a saved file survived the full cycle. The signed update check passed
again on the restored build.
The NVIDIA runtime timer was enabled and the sync service was absent
from the graphical boot critical chain. This VM had no physical NVIDIA
device attached.

A separate encrypted VM installed the exact published 0.9.8 NVIDIA image
from the published Monet Setup ISO. The image's original signature passed
the Monet release-key policy. Setup's recovery key unlocked the disk, and
later boots unlocked through the emulated TPM after the temporary startup
key was retired. The guest rejected the unsigned 0.9.8-5 offer, staged and
booted the signed offer, then verified the signed channel again. Rollback
returned to the published 0.9.8 digest. Secure Boot, SELinux enforcement,
TPM unlock and the saved file's checksum survived the cycle. The VM used
virtual graphics. Evidence is in `try/hardware/nvidia-migration/`.

The ThinkPad has an Intel Iris Xe and an NVIDIA RTX A500. Its installed
0.9.8 deployment tracks `monet:latest` with an unverified origin. The local
staging launcher requests signature enforcement explicitly and uses a
temporary mount namespace for the registry configuration. The ThinkPad
served the exact NVIDIA manifest and signature attachment on loopback.
A Secure Boot VM rehearsed the signed switch, reboot, post-reboot check
and rollback. Its container configuration checksums matched before and
after. Staging on the ThinkPad requires administrator authentication, and
its physical boot remains open. Evidence is in `try/hardware/physical-stage/`.

The ThinkPad's preflight now verifies the NVIDIA image signature against
the installed release key and hashes its config and 282 layers. A disposable
registry rejected a modified signature and a blob with one changed byte.
The Windows 11 Enterprise Evaluation ISO used in the Bridge tests was
recovered from a local snapshot by reflink. Its full SHA-256 and installer
boot files matched the retained test media. The ISO is available locally
for physical testing. The SSD still has about 343 GiB unallocated and the
Kingston still contains Monet Setup. See `try/hardware/windows-media/`.

The exact refreshed Monet Setup ISO also completed a graphical install
with the local signed-image mirror. The walkthrough used Setup's account,
drive selection, erase review, encryption and recovery-key screens. The
Restart button led to Secure Boot enrollment and then to the installed
AMD/Intel sign-in screen. A guest-only serial report confirmed the pinned
digest, Secure Boot and SELinux enforcement. The `try/` folder includes a
launcher for repeating this walkthrough on a disposable virtual disk.

A graphical Fedora fallback test with a complete Kickstart exposed a
premature start. QEMU recorded 7.38 GB of writes to the disposable disk
before anyone pressed Begin Installation. The rebuilt fallback waits at
Anaconda's summary. Both its firmware boot menus and the embedded EFI
menu carry that setting, and the rebuilt media checksum passed.
With a complete graphical test Kickstart, QEMU recorded zero bytes
written during each 60-second hold, including after the disk review.
The install started after Begin Installation, created the chosen wheel
account, and booted the pinned AMD/Intel image with Secure Boot and SELinux
enforcing. A signed rolling-channel check passed after a second reboot.
The exact rebuilt fallback ISO also waited with zero disk writes before
confirmation when booted from a read-only virtual USB drive. It completed
the graphical install and booted the pinned image with the selected admin
account, Secure Boot and SELinux enforcing. The first restart used the VM
reset after the installer returned to its console when the virtual media
was removed. After a normal second reboot, bootc fetched the release
signature and accepted the rolling channel. The tests used a local
mirror for the unpublished image.

Repeating the restart with the virtual USB still attached produced a
guest-initiated reset from Anaconda's Reboot System button. Secure Boot
enrollment appeared, and the installed system accepted the signed update
channel after enrollment. Removing the USB once the firmware had started
let the installed system boot without a VM reset.

The fallback account check now requires an unlocked administrator with
a password. Anaconda had counted the explicitly locked root account as
sufficient. In the graphical installer, QEMU recorded zero disk writes
after attempts to start with no account, a passwordless administrator, and
a password-protected standard account. The text installer also rejected
starting with no account. Both interfaces accepted a password-protected
administrator and waited for explicit confirmation. The ISO with this
change completed the graphical install and restarted from Anaconda with
the USB still attached. The selected administrator signed in, and the
root password remained locked. After another normal reboot, bootc fetched
the local release signature and accepted the signed channel. The updated
ISO and four other release assets passed their SHA-256 checks.

The local Fedora fallback launcher also installed the exact ISO from a
read-only virtual USB using the private registry. The guest restarted from
Anaconda with the USB attached and enrolled the Secure Boot key. Reopening
the installed virtual disk without the USB reached Monet's sign-in screen
and the Plasma desktop.
The guest reported the pinned AMD/Intel digest, Secure Boot enabled and
SELinux enforcing. Its isolated network cannot fetch optional Flathub apps.

In the installed Plasma session, Orca announced the Settings search field,
the Store search field and Downloads tab, and the selected sample file in
Files. A real background extraction appeared as completed in Transfers.
Orca announced its Open folder button, which opened the extracted folder
when activated with Enter. The laptop's physical audio output still needs
checking. Its Windows firmware entry points to a partition absent from the
connected disks, so the same-hardware Windows measurements remain open.
With the VM's Ethernet link disabled, Settings reported Cable unplugged
and Quick Settings hid the LAN tile. Restoring the link brought the tile
and the wired addresses back.
In a separate Secure Boot VM on the signed AMD/Intel image, the open
Quick Settings panel switched live between four states. It showed LAN
and Connected with Ethernet alone or alongside Wi-Fi, Wi-Fi and the
active connection name with Wi-Fi alone, and Wi-Fi and Not connected
with neither connection. NetworkManager associated a simulated Wi-Fi
client with a local access point. QEMU changed the Ethernet link, and a
separate unmanaged adapter carried the test connection. The LAN tile
opened Settings at the Internet page's Ethernet section. With Settings
still open, removing the link showed Cable unplugged and restoring it
brought back the addresses, gateway and DNS.
Two suspend diagnostic cycles on the signed AMD/Intel VM froze the session
and produced logind's PrepareForSleep signals before and after the freeze.
Quick Settings removed LAN after the cable was disconnected. Sound switched
from the detached virtual USB speaker to built-in audio. Both devices
reappeared when reconnected, and the boot ID and Plasma process stayed the
same. The full deep and suspend-to-idle attempts in that VM required a
reset. The diagnostic verifies the desktop refresh; physical wake still
needs a hardware run.
Print Screen opened the region selector in the installed desktop. After
selecting an area and pressing Enter, Spectacle saved a 343 × 197 PNG in
Pictures → Screenshots and returned to the desktop with a saved notification.

On the laptop, PipeWire enumerated an unavailable stereo microphone port
and the built-in digital microphone. The candidate Sound helper omitted
the unavailable port and kept the digital microphone selected when it
received a stale request for the disconnected input. This used the laptop's
real audio devices and left the default source in place.
Speech Dispatcher also sent a short test phrase to the physical speaker
sink while ALSA reported playback running. A later check ran Orca with
the candidate Settings and Store in a private desktop session on the
laptop. Orca logged “Search settings” and “Find an app” on keyboard focus.
The speaker monitor detected the speech signal and ALSA reported the
laptop's playback device running. The check retained no audio. Human
listening and intelligibility remain open.
The same physical output check captured Orca's location control in the
host's Files and Open folder in the candidate Transfers panel. ALSA
reported active speaker playback for each announcement. The Transfers
panel used disposable jobs, and the signed VM separately covered a real
background extraction and opening its destination.

Across the full desktop run and the widget rerun, 1,697 Python checks passed
with 19 documented skips. The JavaScript test and 11 browser form checks
passed. The older test container lacked the current Archives ZIP plugin and
Plasma networking module. The reruns used the binaries from the rebuilt
AMD/Intel image, and the desktop test container now includes Plasma's
networking package.

Reports are under `target/098-5-local/performance/` and
`target/098-5-local/desktop/`. Image rebuild and Flatpak transaction logs
are under `target/098-5-local/rebuild/`. The Windows restart and physical
USB evidence is under `target/098-5-local/rebuild/bridge-vm/`.
The keyboard follow-up artifacts and reports are under
`target/098-5-local/desktop/followup/`. Its `signed-vm/` directory holds
the release signatures and post-reboot installer evidence. Its `try/`
directory holds the local desktop launcher, signed upgrade evidence and
the complete 0.9.8-5 change list. The Store disk exhaustion results and
physical Orca playback evidence are under `try/store-disk-full/` and
`try/hardware/orca-playback/`. The NVIDIA upgrade and rollback evidence
is in `nvidia-upgrade/`. The fallback installer results are under
`try/fallback/`, `try/fallback-exact/`, `try/fallback-restart/`,
`try/fallback-admin/`, `try/fallback-text/`, and `try/fallback-vm/`. The stalled
Bridge download and restart evidence is in `bridge-slow/dual/`.
Files' Arabic large-text walkthrough is under `try/files-rtl/`. Physical
speaker routing for Files and Transfers is in `try/hardware/orca-files-transfers/`.
The Windows USB Maker runs are in `try/windows-final-setup-usb/` and
`try/windows-final-usb/`. The ThinkPad firmware certificate check is in
`try/hardware/uefi-trust/`. The live Quick Settings and Internet page
checks are in `try/hardware/network-transitions/`. The sleep diagnostic
and full suspend attempt logs are in `try/hardware/resume/`.

## Monet 0.9.8 release verification

The AMD/Intel and NVIDIA images built from Bazzite's stable images and passed
bootc's image checks. Monet Setup and the Fedora fallback carry the exact
manifest digests listed in `image/releases/0.9.8.json`. The fallback's media
checksum passed, and its embedded EFI menu includes the Monet entries.

The desktop run covered 1,707 checks with 19 documented skips and no
failures. All 104 Rust workspace tests passed. The Windows-target run under Wine passed 63 tests,
and all nine PowerShell scripts passed their syntax check. Linux and
Windows-target Clippy passed with warnings treated as errors.

A Secure Boot VM installed the published 0.9.7 release and used the documented
signing-key setup. It refused the unsigned 0.9.8 AMD/Intel image and the same
image signed by a different key without staging either. It then booted the
exact image signed by the Monet release key with SELinux enforcing. Rollback
returned to the original 0.9.7 digest and preserved a saved file. The exact
NVIDIA image signature also verified against the release key in the local
registry.

The exact Monet Setup ISO installed the pinned AMD/Intel image in a
disposable VM. Choosing Continue boot on the first Secure Boot enrollment
screen brought the prompt back. After enrollment, the installed system booted.

The Fedora fallback installed the pinned AMD/Intel image from a local
registry in a disposable VM. The installed system booted with Secure Boot
and SELinux enforcing. Its booted digest matched the release record and
its update source tracked the rolling channel.

The Windows-target USB writer's shared write and read-back code copied both
release ISOs to disposable 4 GiB disk images under Wine. Independent read-back
matched the installer payloads. The written images reached the Monet Setup
boot screen and the Fedora fallback menu with Secure Boot enabled in QEMU.
Physical USB writes and GPU testing remain open.

## Local 0.9.7 release checks — 11–12 November 2026

The full desktop run used the frozen source of the previous local release images.
It passed 1,670 Python checks across 120 modules with 19 declared skips.
The JavaScript test and all 11 browser form checks passed. The two PowerShell
checks skipped in the container passed with the retained local runtime.
All 99 Rust tests, Linux and Windows-target Clippy, and the translation
catalog check passed.

The Linux bundle's Monet and Setup-check binaries match those in both images.
The Bridge binary matches in both packages and both images. The USB maker was
cross-built for 64-bit Windows. All three assets passed their checksum and
package checks. The exact writer refused a file without an ISO header, then wrote and
verified the exact Setup ISO twice on a virtual USB stick. The rewritten stick
booted Setup with Secure Boot enabled. Physical USB writing with this build
remains open. The release reports and assets are in
`target/097-clean-release/final-checks/`.

The laptop's account preview still had the older widget glass, which
looked for the Monet wallpaper once at startup. An OpenGL fixture reproduced
the paper fallback when the wallpaper loaded late. The packaged 0.9.7 widget
glass picked up both the late load and a replacement. The account preview
was refreshed and the painting was visible through the widgets on the
running desktop. Evidence is in `target/widget-glass-local.dpaSEZ/`.

A later check used the account preview's Haystacks wallpaper in a private
Plasma session. Calendar, Weather, System and Now Playing sampled the painting
in Clear. Calendar also followed all four Glass levels, used paper with KDE's
image wallpaper, and returned to Clear when The Hours was restored. The 24
focused checks passed. The reported live symptom remains unverified. Captures
are in `target/widget-glass.Z7GOLP/` and `target/widget-glass.cQlMeA/`.

The refreshed account Security preview reads the live firewalld rules
without elevation. It shows the status of the active connections on an
older system helper and keeps editing unavailable. The firmware restart
button now requires the matching method on the running Plasma session.
The read-only probe recognized the method on a private test bus. The
installed preview hid the button on a session that lacked it and
completed two real status checks. All 57 focused Security and Settings
tests passed. Evidence is in `target/097-security-local.NZJVUq/`.

The refreshed AMD/Intel and NVIDIA images include this Security page and
the widget glass fix. On both images the installed helper recognized the
firmware method on a fresh session bus, where Plasma started the shutdown
service on demand. The Linux bundle's Monet and Setup-check binaries and
the Windows Bridge binary match those shipped in both images. All 100
Rust tests, Linux and Windows-target Clippy, and the three asset checksum
checks passed. The local assets retain the previously qualified USB maker.
Its rebuild differed only in the PE timestamp and checksum.

Both refreshed images passed the local signed-update and rollback test.
Each VM rejected unsigned and wrong-key offers before booting the signed
0.9.7 digest with Secure Boot and SELinux active. The installed Security
and glass files matched the image. Firmware status recovered after the
test restored the firmware service. Each VM rolled back to its original
0.9.6 digest, retained its test file and cleared the stale boot counter.
The refreshed source manifest, image digests, package checks and VM logs
are in `target/097-security-release.0tb6wB/`.

The local Setup and Fedora fallback ISOs both record the refreshed AMD/Intel
and NVIDIA digests. Both ISO checksums passed, and the digest maps extracted
from the media matched the exported image manifests. Setup also passed the
signed boot-file checks. Media and reports are in
`target/097-security-release.0tb6wB/media/`.

The Fedora fallback VM installed and booted the pinned AMD/Intel digest
after the test registry moved the 0.9.7 tag. Secure Boot and SELinux were
active. The installed Security and widget files matched the image, and
the update check used the rolling reference. The first install stopped
at the 64 GiB SSD reserve. The retry completed with a 56 GiB reserve.
Both disposable disks were removed and both runs' logs were kept.

The rebuilt Setup ISO booted with Secure Boot and a virtual TPM. It saved
the pinned NVIDIA download after the registry tag moved, refused a
substitute cache offline, and completed an encrypted install from the
original cache. The recovery key unlocked LUKS2. The SSD guard interrupted
the installed VM during the first restart. LUKS had a TPM slot and the
temporary key was gone, while the published boot entry still referenced it.
Removing that argument in the disposable guest let it boot the pinned
image through the TPM with Secure Boot and SELinux active. The journal
records OSTree starting deployment finalization before the interruption.

The source helper now keeps the temporary key until both the running kernel
and its published deployment have boot arguments without it. All 22 seal
tests passed, including simulated loss of staged arguments and real LUKS
slot retirement. The source helper also identified the running entry in
the recovered VM while a different entry was staged. Logs are in
`target/097-security-release.0tb6wB/media/native/evidence/`.

Both images were rebuilt with the seal change and matched the frozen helper.
The rebuilt Setup ISO pinned both new digests. It refused a substitute cache
and completed an encrypted NVIDIA install offline from the verified cache.
The test confirmed that the booted entry still referenced a usable temporary
key while the staged entry omitted it. It stopped the VM before OSTree
published the staged entry. The next boot used the original entry without
asking for recovery. After an orderly restart, Monet retired the temporary
key and a further boot unlocked through the TPM. Secure Boot and SELinux
were active, and Settings reported encryption complete. The harness held the
first hardware restart and read the checks from the guest serial console.
All 115 focused Setup, recovery and seal tests passed on the frozen source.

The Linux and Windows packages match the rebuilt image binaries, and the
Linux package carries the corrected seal helper. The previously verified USB
maker is byte-for-byte unchanged. The Setup and fallback ISO checksums and
the installer, image and package evidence are in
`target/097-seal-release.Iw2cUZ/`.

Both images containing the seal fix also rejected unsigned and wrong-key
updates in the local VMs. The trusted update booted the expected 0.9.7
digest on each variant. Both then rolled back to their original 0.9.6
digests, kept the test file and cleared the stale boot counter.

The rebuilt Fedora fallback ISO installed and booted the pinned AMD/Intel
digest after the registry changed its version tag. The installed system
matched the rebuilt image's file checksums, kept Secure Boot and SELinux
active, and checked the rolling update reference. The test disks were
removed from their dedicated Btrfs subvolume.

The full desktop run on the same frozen source had 1,674 Python passes across
120 modules and 19 declared skips. All 16 JavaScript submission checks and
11 browser password-form checks passed. The two PowerShell checks skipped
in the desktop container passed with the retained local PowerShell runtime.
The translation catalog check passed. Reports are in
`target/097-seal-release.Iw2cUZ/desktop-qualification/`.

The AMD/Intel and NVIDIA customized-profile VMs each signed in on the original
0.9.6 image, on the signed 0.9.7 export with the seal fix, and after rollback.
Both kept file contents and metadata, the enabled and disabled startup choices,
the custom Files shortcut, region and weather settings, the download destination,
and the recorded power and lock preferences. Plasma reported the original
panel positions and sizes in all six desktop sessions. Each rollback booted
the original digest with Secure Boot and SELinux active. Evidence is in
`target/097-seal-release.Iw2cUZ/profiles/`.

A separate encrypted NVIDIA install on that image exposed a retained rollback
entry that still referenced the retired key. Monet queued that deployment, and
the VM reached a LUKS recovery prompt. After the test updated the retained
entry in place, the same rollback booted through the TPM with Secure Boot and
SELinux active. The deployment serial and image digest confirmed the rollback.
Evidence is in `target/097-seal-release.Iw2cUZ/media/rb/evidence/`.

The updated helper now verifies the retained entries on disk and flushes the
boot partition before retiring the temporary slot. The focused Setup, LUKS and
widget run passed 122 tests. The earlier widget glass still timed out when
switching back to Monet's wallpaper after six seconds. The updated widget
passed that switch and rendered all four Glass levels on a private OpenGL
Plasma session. Captures and checks are in `target/widget-glass-local.dpaSEZ/`.

The next AMD/Intel and NVIDIA images contain both fixes. The local Setup and
Fedora fallback ISOs pin their exact digests and passed checksum verification.
A fresh encrypted NVIDIA install from the rebuilt Setup ISO verified the
recovery key. On the installed system, the temporary file, LUKS slot and
published boot arguments were gone. Monet's rollback command switched from
deployment serial 2 to 0 on the same pinned image. That boot unlocked through
the TPM with Secure Boot and SELinux active. `/boot` and `/sysroot` stayed
read-only. The stopped test disk was removed. The image manifests and VM logs
are in `target/097-rollback-release.RyYpUm/`.

On the rebuilt images, both local update VMs rejected unsigned and wrong-key
updates, booted the trusted 0.9.7 digest, then rolled back to their original
0.9.6 digests. The Fedora fallback installed the pinned AMD/Intel digest after
the version tag moved, booted with Secure Boot and SELinux active, and checked
the rolling update reference. Installed file checksums matched the image.
The Linux and Windows bundles match the image binaries, and all three package
checksums passed. The USB maker is byte-for-byte identical to the earlier test.

The full desktop suite reran with the wallpaper assertion updated for Plasma's
binding. It passed 1,676 Python tests with 19 declared skips across 120 modules.
All 16 JavaScript submission checks, 11 browser form checks and two separate
PowerShell checks passed. The translation catalog check passed.

The Windows USB maker initially accepted the first 64 KiB of the rebuilt
Setup ISO because the ISO and boot signatures were intact. The VM recorded
five writes and the maker reported Ready. The updated preflight checks the
declared ISO volume size and the location of the backup GPT before opening
the target for writing. Both complete installer ISOs pass. The rebuilt
writer refused the same truncated file with zero writes or discards.

The rebuilt Windows executable wrote and read back the exact Setup ISO twice
on the same virtual stick. Independent read-back matched the ISO payload
and verified the relocated GPT and both partition tables. The rewritten
stick booted to Monet Setup with Secure Boot enabled. All 102 Rust workspace
tests, 23 native Windows USB tests, and Linux and Windows-target Clippy checks
passed. Evidence is in `target/097-rollback-release.RyYpUm/usb-qualification/`.

Both rebuilt images also passed the customized-profile test. Each VM signed
in on 0.9.6, on the exact signed 0.9.7 image and after rollback. All six
sessions kept the recorded files and metadata, startup choices, Files
shortcut, download folder, region, weather, power and lock settings.
Plasma reported the same panel positions and sizes. The distinct boot IDs,
image digests and profile checks are in `target/097-rollback-release.RyYpUm/profiles/`.

The same Setup ISO resumed an encrypted NVIDIA installation with the network
adapter removed. Setup rejected a substitute cache with internally matching
metadata and installed from the original cache for the pinned digest. The
recovery key unlocked the disk. An abrupt VM stop before the staged boot entry
was published left the original entry and temporary key usable on the next
boot. An orderly restart published the new entry and retired the temporary
file, slot and boot arguments. Rollback from deployment serial 3 to 0 unlocked
through the TPM with Secure Boot, SELinux and the firewall active. The installed
guest allowed the guarded desktop switch from the active session and required
administrator authentication for firewall edits, Windows preparation, direct
CLI access and a switch from a detached process. Evidence is in
`target/097-rollback-release.RyYpUm/media/offline-cut/evidence/`.

During that run, the Security page displayed check failures before its first
status reply. The page now leaves those row details blank while checking and
shows failures after the helper reports them. All 76 focused Settings and
Security tests passed, including a held first reply. The reversible account
preview contains the change.

Plasma was still running the earlier widget code after the corrected QML had
been installed in the account. Reloading the desktop shell loaded the wallpaper
binding for all four active cards and preserved the widget layout. A fresh
private Plasma run with the installed QML distinguished all four Glass levels
and verified Clear after two wallpaper replacements. Evidence is in
`target/widget-glass-live.tn1FJ2/`.

The next AMD/Intel and NVIDIA images contain the Security loading fix. Both
packaged copies match the frozen Settings source. The checked protection
helpers, boot helpers, policy and widget files match the previous candidate.
The Linux and Windows bundles match the binaries from both new images. The
Windows USB maker is byte-for-byte identical to the one already qualified.

The rebuilt Setup and Fedora fallback ISOs pin both new exported digests.
Checksums passed for both archives and both ISOs. Setup's signed boot files
passed the optical and USB packaging checks. The USB maker's preflight
accepted both new ISOs and rejected the first 64 KiB of the Setup ISO.
Reports and media are in `target/097-security-loading.jaiOtn/`.

Both new images rejected unsigned and wrong-key update offers in the VMs.
Each VM booted its trusted 0.9.7 digest and rolled back to its original 0.9.6
digest. All six sessions preserved the customized profile. Both upgraded
guests reported Secure Boot, SELinux enforcement and the firewall active.
The rendered Security page in the AMD/Intel VM showed those live results and
correctly marked its unencrypted test disk. Boot IDs, checks and the capture
are in `target/097-security-loading.jaiOtn/profiles/`.

The frozen source passed 1,677 Python tests with 19 declared skips across
120 modules. The JavaScript submission and 11 browser form checks passed.
Both PowerShell checks passed with the retained local runtime. The translation
catalog check passed. The Rust and Windows source trees match the snapshot
used for the USB maker qualification above. The desktop test reports are in
`target/097-security-loading.jaiOtn/desktop-qualification/`.

The rebuilt Fedora fallback installed and booted the exact pinned AMD/Intel
digest after the test registry moved its version tag. Secure Boot and SELinux
were active. The installed file checksums matched the rebuilt image, and the
next update check used the rolling reference. The VM disk was removed after
shutdown. Evidence is in `target/097-security-loading.jaiOtn/media/fallback/`.

The rebuilt Setup ISO installed the pinned NVIDIA digest on an encrypted
virtual disk and verified the recovery key. The installed system retired the
temporary key and removed its references from every retained boot entry.
Monet's rollback command booted the retained deployment at the same digest
through the TPM. Secure Boot and SELinux were active, and `/boot` and
`/sysroot` were read-only. Both install VMs shut down and their disposable
disks were removed. The laptop had 99 GiB free after the run. Evidence is in
`target/097-security-loading.jaiOtn/media/native/evidence/`.

The Windows USB maker also wrote and verified the newest Setup ISO twice on a
disposable 4 GiB virtual USB stick. It refused a truncated copy with zero
writes or discards. An independent read-back matched every ISO byte outside
the relocated primary GPT fields and verified both GPT headers and tables.
The written stick booted Setup with Secure Boot enabled, and the running
installer's digest map matched the one extracted from the ISO. The Windows
overlay, seed ISO and virtual stick were removed after shutdown. Evidence is
in `target/097-security-loading.jaiOtn/usb-qualification/evidence/fixed/`.

Twelve Security checks passed at 150% and 200% on the laptop's Intel Iris Xe
and NVIDIA RTX A500 client renderers. They covered a delayed first reply,
firewall keyboard controls and a failed firewall change. The RTX A500 also
rendered all four widget Glass levels and picked up the Monet wallpaper again
after it was replaced. These checks used private KWin virtual outputs. Evidence
is in `target/097-security-loading.jaiOtn/physical-security/` and
`target/097-security-loading.jaiOtn/physical-glass/`. Physical display hotplug
and removable-drive checks remain open.

The newest Setup ISO also resumed the encrypted NVIDIA install with the
virtual network adapter removed. It rejected a substitute cache with valid
internal metadata, completed from the cache for the pinned digest, and proved
the recovery key could unlock the disk. Before the new boot entry was
published, the test stopped the VM without a guest shutdown. The original
entry and temporary key were still usable on the next boot. An orderly restart
retired the temporary key. Rollback from deployment serial 3 to 0 booted through
the TPM at the same pinned digest. Secure Boot, SELinux and the firewall were
active after rollback.

An ordinary account could read the running firewall and could not add a port
without elevation. The administrator helper added a test rule, which survived
a firewalld reload, and removed it. The journal recorded the two successful
changes. The active local account could use the guarded desktop switch. A
detached process and the active Guest session required administrator approval
for that switch. Guest also needed approval for the CLI, firewall helper and
Windows preparation, and could not keep its session running after sign-out.
Security showed the live device and firewall results on the encrypted guest.
The final guest shut down cleanly and its test disk was removed. Evidence is
in `target/097-security-loading.jaiOtn/media/offline-cut/evidence/`.

The exact signed AMD/Intel candidate also passed a restart into virtual UEFI
from Settings → Security. Canceling the Settings confirmation left the boot
unchanged. Cancel Logout during KWrite's unsaved-document prompt left the
draft open and the firmware boot target unset. Plasma displayed its standard
two-minute logout countdown while the document was open. On the next attempt,
saving from that prompt let Plasma set the firmware target and request the
restart, in that order. The VM entered OVMF. After Secure Boot was restored
there, the same signed image booted, the saved draft matched its original
text, and Security showed Secure Boot on. Evidence and screenshots are in
`target/097-security-loading.jaiOtn/firmware-boot/`.

On the exact NVIDIA candidate, the automatic updater rejected an unsigned
offer and Security recorded the failure. The same image staged once the
fixture registry served its trusted signature. It reused the candidate's
layers and changed one image label. Turning automatic updates off skipped
the next run and left the staged deployment ready.

Opening Security exposed a Plasma conflict. The firmware availability probe
started `org.kde.Shutdown`, and Plasma's ordinary restart dialog exited
because it found that service already running. The corrected probe checks
the installed shutdown bundle while the service is inactive and reads the
method directly from its existing owner when active. In the VM, opening
Security reported firmware restart available and left the service inactive.
The account preview also passed the passive check against its older Plasma
runtime and left the firmware action unavailable there.

With the corrected helper mounted read-only in the guest, Cancel in Mist
left the boot ID and staged deployment unchanged. Approving Restart in Smoke
booted the signed fixture digest with Secure Boot and SELinux active. In
Updates, canceling the administrator prompt left the boot order unchanged.
Authorizing the next request and choosing Restart now returned to the original
NVIDIA digest with the test file preserved. The VM shut down cleanly and its
4.1 GiB disposable disk was removed. The laptop had 94 GiB free afterward.
Screenshots, package identities and boot checks are in
`target/097-security-loading.jaiOtn/security-restart-qualification.TvhdVX/`.

The next AMD/Intel and NVIDIA images include the corrected helper. Each
packaged helper recognized the firmware method with the D-Bus service both
inactive and running. The inactive probe left the service inactive. Each
signed VM rejected unsigned and wrong-key offers, booted the trusted 0.9.7
digest and rolled back to the original 0.9.6 digest. Both runs preserved the
custom profile, kept Secure Boot and SELinux active, and cleared the stale
boot counter. The installed Security page left the shutdown service inactive
and the native Restart dialog appeared. Canceling preserved the boot ID.

The Linux bundle contains the corrected helper. Its Monet and Setup-check
binaries and the Windows Bridge match the binaries in both images. The USB
maker matches the previously tested executable. Both VM installer ISOs passed
checksum verification. Their extracted digest maps match the exported images.
Setup's shim, GRUB, MokManager and kernel passed the signed boot-file checks.
Setup booted to its welcome screen with Secure Boot enabled in a VM with
no network adapter. The running installer reported both new digest pins.
The full desktop run passed 1,679 Python checks with 19 declared skips across
120 modules. The JavaScript test, all 11 browser form checks, both PowerShell
checks and the translation catalog check passed. The first desktop run's
archive fixture refused an oversized test tmpfs. The successful run used its
64 MiB scratch volume.

The Fedora fallback installed and booted the exact AMD/Intel digest after the
test registry moved the version tag. Secure Boot and SELinux were active, the
installed file checksums matched the image, and the next update check requested
the rolling reference. The first attempt stopped at the 72 GiB reserve. The
retry completed with a 64 GiB reserve. Both disposable disks were removed and
both sets of logs were retained. The laptop reported 73 GiB free after cleanup.

For the rebuilt Setup ISO, the Windows USB maker refused a truncated copy
with zero writes or discards. It wrote and verified the full ISO twice on
the same 4 GiB virtual USB stick. Independent read-back matched the payload
outside the relocated primary GPT fields and verified both headers and
partition-table CRCs. The rewritten stick booted Setup with Secure Boot
enabled and the same digest map as the ISO. The Windows overlay, seed ISO,
read-back file and virtual stick were removed after shutdown. Evidence is in
`target/097-passive-restart.uuUCs3/usb-qualification/evidence/fixed/`.

The exact rebuilt AMD/Intel image passed the firmware restart from Security.
Secure Boot was turned off in the disposable VM to exercise the action.
The packaged status check showed the action and left Plasma's shutdown service
inactive. Canceling in Settings kept the boot unchanged. Cancel Logout during
KWrite's save prompt kept the draft open and the firmware target unset.
On the next attempt, saving let Plasma set the firmware target and request the
restart in that order. The VM reached OVMF. After Secure Boot was restored,
the same signed image booted, the saved document matched every expected byte,
and Security showed Secure Boot on. The firmware VM shut down cleanly and its
3.2 GiB disk was removed. Evidence is in
`target/097-passive-restart.uuUCs3/firmware-qualification.lfsB4y/`.

The automatic updater staged the rebuilt signed NVIDIA image from the earlier
signed 0.9.7 image on a private registry. With the trial running, the test
stopped the VM's display manager. After five minutes the installed boot check
restarted into the previous signed digest. The user's fixture file matched its
original checksum. Secure Boot and SELinux stayed active, `/boot` was read-only,
and the boot counter was cleared. The ordinary user could read the rollback
notice. The next automatic update check saw the failed digest and skipped it
without staging another deployment. Evidence is in
`target/097-passive-restart.uuUCs3/boot-recovery.iGBetY/`.

The early boot test interrupted three starts at kernel entry. On the fourth
start GRUB selected the previous signed NVIDIA deployment. The packaged
helper ran `bootc rollback` from that deployment, which queued the failed
image again. A normal restart reproduced the wrong boot order. With the
corrected helper in the VM, the same three interruptions promoted the
booted deployment through OSTree. Another normal restart kept it as the
default. The updater skipped the failed digest and the user's fixture file
matched its checksum. Secure Boot and SELinux stayed active. Evidence is in
`target/097-passive-restart.uuUCs3/grub-qualification.lDXQhc/` and
`target/097-passive-restart.uuUCs3/grub-fixed.c6Vg0X/`.

Both local OCI exports contain the corrected helper and release notes. Each
retained 293 inherited compressed layers and added only those two files.
The Linux bundle matches both images. Its other payloads, the Windows bundle
and the USB maker were verified against the previous artifacts. Both local VM
installer ISOs were rebuilt with the new digests and passed checksum
verification. The Setup ISO passed the signed optical and USB boot-file
checks. It reached Hello with Secure Boot enabled and the network adapter
removed, and its running installer reported both expected digest pins.
Artifacts and checksums are in `target/097-grub-recovery.iWK6Ba/`.

The Windows USB maker refused a truncated copy of this Setup ISO with zero
writes or discards. The full ISO was written and read back twice on the
same 4 GiB virtual stick. Windows briefly showed Not Responding on the
first completion dialog. The dialog dismissed on a second click, and the
same maker instance completed the rewrite. Independent read-back verified
the payload and both GPT checksums. The rewritten stick booted to Hello
with Secure Boot enabled and the ISO's digest map. The Windows overlay,
seed ISO, read-back image and virtual stick were removed after shutdown.
Evidence is in `target/097-grub-recovery.iWK6Ba/usb-qualification/evidence/fixed/`.

The full desktop suite on the frozen source passed 1,681 Python checks
across 120 modules, with 19 declared skips. The JavaScript check and all
11 browser form checks passed. The two PowerShell checks passed separately
with the retained local runtime, and the translation catalog check passed.
Reports are in `target/097-grub-recovery.iWK6Ba/desktop-qualification/`.

The Windows USB maker now scans for disks off the window thread and
combines pending refresh and progress notifications. In a native Windows
VM, an eight-second discovery delay blocked the old window's 600 ms
probe. The fixed window answered immediately and kept Make USB stick
disabled until it had a fresh list. Five extra device notifications
produced one follow-up scan. Unplugging the selected virtual disk cleared
the selection while the other disk remained available.

The rebuilt release executable dismissed the completion dialog on one
click and wrote the same Setup ISO twice. Cancel and a truncated ISO
produced zero writes or discards. Independent read-back verified the
payload and both GPT headers. The rewritten stick reached Setup with
Secure Boot and the expected pins. All 21 Linux and 23 native Windows
USB-maker tests passed, as did Windows-target Clippy. The VM disks and
build scratch space were removed. The replacement executable, checksum
and reports are in `target/097-usb-responsive.c5hbXd/`.

The local candidate manifest joins the rebuilt USB maker to the checked
Linux and Windows packages, both OCI exports and both VM installer ISOs.
All seven SHA-256 checks passed. The Linux and Windows packages contain
the same Bridge executable, and both installer pin maps match the OCI
manifests. The media use the disposable VM registry. The manifest and
relative links are in `target/097-local-candidate.nFd1GK/`.

The local candidate also passed a Windows round trip after a signed
AMD/Intel upgrade from 0.9.6. Windows installed Bridge from the candidate
ZIP, and its executable matched the package hash. Both setup auto-logon
values were zero on the existing Windows evaluation guest. The active
Monet desktop could invoke the dedicated switch without authentication.
PolicyKit required authentication for the general command and for the
dedicated switch from an inactive session.

Bridge launched the fixture game without Windows administrator privileges
and returned to the same signed Monet digest after the game closed. The
VM kept Monet first in the firmware order, cleared the one-time boot and
game request, and retained the test file. An older Windows fixture stalled
during boot. The retry reused the signed Monet deployment with the Windows
fixture already exercised by the USB maker tests. Both disposable disks
were removed. Evidence is in
`target/097-local-candidate.nFd1GK/windows-roundtrip/`.

The same signed AMD/Intel image passed a separate first-sign-in check with
a Windows evaluation disk saved before its first boot. The disposable overlay
used the current rendered answer file and exact Bridge package. Windows signed
in automatically, ran Bridge setup and the cached Steam bootstrap, removed
the temporary setup volume and files, grew the Windows partition and
restarted into the same signed Monet deployment. The fixture file survived.
The offline registry and the next Windows sign-in both reported
`AutoAdminLogon=0` and `AutoLogonCount=0`. The installed Bridge hash matched
the package and Secure Boot was enabled in both systems. The VM had no
internet access, so Steam could not fetch its client update. Evidence is in
`target/097-local-candidate.nFd1GK/windows-first-logon/`.

The NVIDIA VM rejected unsigned and wrong-key offers before booting the
trusted export with Secure Boot and SELinux enabled. After three resets at
kernel entry, GRUB selected the previous signed deployment. The packaged
helper cleared the trial and boot counter, and later normal boots kept
that deployment as the default. The ordinary user could read the rollback
notice, and the customized profile matched its original values. The next
automatic update check fetched the rolling reference and skipped the failed
digest without staging it. Evidence is in
`target/097-grub-recovery.iWK6Ba/profiles/nvidia/`.

The AMD/Intel VM rejected the same two invalid offers and booted the
trusted digest. A manual rollback restored the original 0.9.6 digest,
cleared a stale boot counter and kept the customized profile intact.
Secure Boot and enforcing SELinux stayed active. Both image variants
passed the packaged Security and firmware checks. The 164 focused source
checks for Security, recovery, Setup and release packaging passed.
Reports are in `target/097-grub-recovery.iWK6Ba/profiles/mesa/` and
`target/097-grub-recovery.iWK6Ba/evidence/focused-security-and-install.log`.

The rebuilt Fedora fallback ISO installed the pinned AMD/Intel digest on
a blank VM disk after the local registry moved the version tag. The
installed image booted with Secure Boot and enforcing SELinux, and its
files matched the export. The update check requested the rolling reference
and found the same digest. The signed-update VMs used a disposable
container signature policy. The fallback install verified the media's
digest pin and kept the existing rolling update origin.
The temporary disk peaked at 15.84 GiB and was removed after shutdown.
The lowest recorded SSD and host memory reserves were 69.08 GiB and
33.39 GiB. Evidence is in `target/097-grub-recovery.iWK6Ba/media/fallback/`.

The rebuilt Setup ISO installed the pinned NVIDIA digest to a blank LUKS2
disk after the registry moved the version tag. The recovery key unlocked
the disk. After firmware key enrollment, the VM booted with Secure Boot
and enforcing SELinux. Setup's temporary key and its boot entry references
were removed. Rollback booted the retained deployment of the same digest
using the TPM, with `/boot` and `/sysroot` still read-only. The installed
boot, sealing and Security helpers and Calendar glass matched the export.
The temporary disk peaked at 23.76 GiB and was removed after shutdown.
The lowest recorded SSD and host memory reserves were 68.91 GiB and
25.69 GiB. Evidence is in `target/097-grub-recovery.iWK6Ba/media/native/evidence/`.

For the preceding pair of images, the rebuilt Setup ISO installed the
pinned NVIDIA image to a blank encrypted VM disk after the test registry
moved the version tag. The recovery key unlocked LUKS2. After firmware
key enrollment, the VM booted with Secure Boot and enforcing SELinux.
Monet retired the temporary key and removed its
references from the retained boot entries. The rollback command switched from
deployment serial 2 to 0 at the same image digest and unlocked through the TPM.
`/boot` and `/sysroot` stayed read-only. The installed Security helper, sealing
helper and Calendar glass matched the image.

Removing old Monet test artifacts reduced RAM-backed `/tmp` from 24 GiB to
270 MiB. The encrypted test used a separate temporary disk with a 25 GiB cap
and monitored SSD and memory reserves. It peaked at 23.31 GiB with at least
71.92 GiB free on the SSD and 25.86 GiB of host memory available. The first
attempt verified the install and recovery key, then hit a QMP socket path
limit in the test harness. The corrected run passed the boot and rollback
checks. SSH disconnected during the final power-off after the checks passed.
Both disposable disks were removed. The laptop reported 72 GiB free afterward.
Evidence is in `target/097-passive-restart.uuUCs3/media/native-capped.vq8UBA/evidence/`.

The frozen sources, images, bundles, media and VM reports are in
`target/097-passive-restart.uuUCs3/`.

## Local 0.9.7 source verification — 8 November 2026

The current source snapshot passed the required desktop run. Across 120 Python
modules, 1,647 checks passed and 17 declared skips covered Flatpak integration,
the private notification bus, transient user services and native disk discovery.
The JavaScript test and all 11 browser form checks passed. All 99 Rust tests,
Clippy with warnings denied, and the translation catalog check also passed.
The source manifest and run logs are in `target/097-final-verification/`.

## Local 0.9.7 second batch — 5 November 2026

The backlog remains the release checklist. These are source/build changes; the
existing account preview has not been refreshed. No production OS image, commit,
push or version number changed.

The Fedora 45 desktop test container now builds and installs the guarded native
Archives executable, retaining its matching distribution libraries/plugins. Its
build exits zero. Native tests reproduce the old false Completed result after an
actual ENOSPC error, then pass with the batch exit-status fix. Encrypted ZIP,
header-encrypted 7z, wrong passwords, native password cancellation and retry in
a new folder also pass. The full-disk fixture fills only the container's private
tmpfs; it must not run against a normal user filesystem.

The full run discovers 1,485 Python checks with 19 declared skips. It initially
finds one fixed-delay countdown-test failure. The test now waits for bounded,
observable progress; the complete affected 30-test module reruns successfully.
Combined coverage is **1,466 passed / 19 skipped**, with JavaScript and all 11
browser-form checks passing in the full run. The original result and corrected
module are retained separately; `desktop-consolidated.json` records how they
combine. The final frozen release candidate still needs a fresh whole-suite run.
Eight notification cases among the skips execute through their private-bus parent;
the remaining skips require Flatpak integration, PowerShell, real partition
discovery or the VM's transient user-service fixture. None are newly hidden skips.

Keep awake has seven backend/client tests and native Settings coverage for
duration replacement, countdown, cancellation, backend loss/recovery, crashes,
coalesced requests and pausing reads while minimized. Return, keypad Enter and
Space exercise the real Settings controls. Three additional native renders pass
in Swedish at 125%, 150% and 200%; captures verify the physical pixel sizes,
control bounds and focus. This is a focused Settings check, with the broader
app/keyboard/touchpad audit still open.

A separate 12-second laptop probe confirms real PowerDevil activation,
ScreenSaver request acceptance, automatic expiry and release. Hashes of saved
power/lock preferences stay unchanged. The first immediate-activation assertion
was premature: PowerDevil deliberately delays enforcement, observed here at
about 4.8 seconds. This probe does not qualify lid/suspend, AC transitions or
manual policy overrides.

The complete paired Files executable/library builds successfully from frozen
inputs. Both native Qt/KIO test executables pass, including an effective blocking
filesystem shim and obsolete/queued-result rejection. Two actual Dolphin/Xvfb
scenarios navigate away from a delayed loopback WebDAV folder, exercise native
Stop, load the local folder and refuse late replies. All sampled read-only UI
RPC replies remain below one millisecond in these runs; this is controlled
responsiveness evidence, not a general folder-opening speed claim. Real sleeping
USB/network devices and thumbnail stress remain release checks.

Evidence is under `target/097-goal/`: the full and corrected test reports, native
build logs/bundles, source snapshots/hashes, WebDAV results, Swedish captures and
the laptop inhibition probe. Catalogs are regenerated and placeholder validation
passes; Swedish power/search text is added. Wider translation review remains open.

## Local 0.9.7 first batch — 5 November 2026

Scope and remaining acceptance work are in [the 0.9.7 backlog](BACKLOG-0.9.7.md).
These changes are source-only; the existing reversible laptop test installation
still contains the preceding batch. No OS image, commit, push or release changed.

The affected suite reports 505 tests: 501 pass and four skip because a JavaScript
runtime and Xvfb are unavailable. The additional native startup-process test
passes, taking the distinct total to 502 passed / four skipped. Store's affected
48-test follow-up also passes (three of the same runtime skips). Six separate
native checks pass at 125%, 150% and 200%. Captures cover the new search targets;
this is not a complete keyboard, accessibility or hardware scaling qualification.

Coverage includes coalesced Settings loads, navigation without preference writes,
focus/highlights, unavailable or delayed charge-limit support, charger connection
independent of battery charging state, charging explanations and the actual Store
first-frame/catalog-start order. The initial duplicate-query regression failed
with two requests before the source fix and passes with one afterward.

`tools/bench-desktop.py` stages the native launchers in temporary directories and
isolates profiles, D-Bus and local-server sockets. It changes no installed app or
real desktop profile. Startup events are opt-in (`MONET_STARTUP_TIMING=1`) and
record phase/timing only, without arguments or helper output. Examples:

```sh
python3 tools/bench-desktop.py --samples 5 --collect-host --output /tmp/monet-startup-clean.json
python3 tools/bench-desktop.py --samples 5 --reuse-cache --verify-store-start --output /tmp/monet-startup-reused.json
python3 tools/test.py tests.test_startup_timing
```

Five clean-profile software-rendered Store samples changed from a 468.5 ms
median observed first frame to 260.1 ms after deferring the catalog worker until
the window has painted. Native Qt queues the timer to the GUI thread and a guard
allows one catalog start. Five real process traces verify frame-before-worker
ordering; the automated test also launches fresh Settings and Store windows.
Initial data readiness, Files UI timing, physical startup, battery drain and
complete-image acceptance remain separate work. Raw timing/test reports,
captures and source hashes are under `target/polish097-2026-11-05/`.

## Local Files quality-of-life checks — 5 November 2026

`tests.test_files_qol` uses disposable files, a private session bus and native
offscreen Plasma hosts. It covers read-only text/image/PDF/Word/archive previews,
bounded archive listings, virtual grouping without moving files, restoration of
desktop filters, and detached extraction with pause/resume/cancel/retry and
interruption detection. ZIP extraction also runs against the real Ark backend.
The transfer widget receives a real JobViewServer request and renders its native
progress beside Store/extraction fixture records. Both widgets are rendered in
Monet's light and dark palettes; gallery images come from those native captures.

Run the focused checks with:

```sh
python3 tools/test.py tests.test_files_qol tests.test_archive_apps tests.test_files_session tests.test_files_bundle tests.test_profile_upgrades tests.test_look
```

`image/files-recovery/tests` compiles Qt/KIO tests for Keep both and Space without
interfering with inline text input. The image's native build runs these checks.
The complete patched Dolphin 26.08.2 target was also compiled in a disposable
Fedora 45 container. These checks do not install anything into the running OS.
Release still requires the image's matching source-RPM/runtime guards and normal
installed-desktop and hardware verification. No folder-opening speed multiplier
is claimed: the change reduces speculative work and the main-thread work budget.

## 0.9.6 release candidate — 4 November 2026

Follow-up: `desktop-followup-final.json` passes **1,326 of 1,342 checks**, with
16 documented skips and no failed modules; JavaScript and browser-form checks
also pass. Both RC8 image builds and packaged-source/native-greeter checks pass.
New recovery coverage includes selected-snapshot identity, collision-safe
publication, disk-full cleanup, folders/links, UI retry feedback and reversible
account-preview retirement. An unprivileged laptop probe now correctly detects
rollback through rpm-ostree's read-only service. RC8 boots in the existing VM
with Secure Boot/SELinux and preserved work, preferences and Startup state.
Separate OCI-directory staging/boot/check acceptance validates the local-only
laptop deployment route. The older counts and image IDs below record RC6.

The current local status and boundaries are in [RELEASE-0.9.6.md](RELEASE-0.9.6.md).
Evidence is under `target/release096-2026-11-04/`; VERSION and workspace/plugin
versions are now 0.9.6. Historical runs below retain their original boundaries.

The final required desktop run (`desktop-release-confirmed.json`, runner exit zero)
discovers 1,332 Python tests across 80 modules: 1,316 pass and 16 documented
skips, with no failed modules. All JavaScript checks and the signed connector's
reproduction/form checks pass. Skipped PowerShell syntax and setup behavior
checks pass separately with the local runtime. Eight notification checks run
through their passing private-bus parent. The five native update-retry checks
also pass against the installed VM. The partition-discovery container skip
remains explicit. Rust's 99 workspace tests and warnings-denied Clippy pass.
The first run with the new greeter checks omitted the pinned browser XPI
environment variable; the separate browser check and the corrected full run
both pass. That invocation error is retained in `desktop-release.log`.

Both complete pinned-base graphics images contain the recovery, Startup,
diagnostics, performance, spelling and native sign-in changes. The final RC6
builds both exit zero; their image lint passes 14 checks, skips one inapplicable
check and emits no warnings. Packaged greeter binaries, runtime RPMs and clean
source archives match their manifests and this checkout. Earlier RC2 tool
wrappers returned 143 after writing/tagging their images; those logs remain as
historical evidence, not the final build result. Authselect factory state
restores and validates in both graphics variants.

The published 0.9.5 baseline upgrades to the exact final AMD/Intel manifest and
rolls back with Secure Boot enabled and SELinux enforcing. Documents, an app
shortcut, a KConfig preference and a disabled Startup entry retain their hashes
and values. The other qcow2 drive has no modified extents. Installed storage
recovery exports nested homes and sparse files, rejects stale/mounted deletion,
preserves the active root and releases its mount.

A real disposable 1 GiB Btrfs filesystem verifies the working-space guard before
an existing root can move. ENOSPC/EDQUOT tests preserve the download and receipt;
download-space failures stop without network retry delays. The frozen-source
Setup ISO passes signed boot-file and optical/USB consistency checks. Its
encrypted keep-data trial survives a post-download hard reset, verifies the
retained 6 GB download and finishes with the virtual link down. Finalization
releases every target/service-namespace mount, closes LUKS and clears the receipt
and runtime state. First and second encrypted boots pass under Secure Boot and
SELinux; the software TPM unlocks after removal of the bootstrap key. The
recovery phrase works, and the retained original partition and second drive
remain unchanged.

The greeter is rebuilt from the exact installed source RPM, with runtime,
link-dependency and binary/source checksum guards. Real native previews cover
compact, wide, software-rendered and 150% Arabic layouts, password rejection
and retry. A deliberately missing main page proves the original-QML fallback
can still sign in. The installed VM also exercises PAM rejection/success and
the native on-screen keyboard. The panel follows its controls when idle.

The fallback ISO passes media/embedded-EFI checks and boots its branded graphical
installer under Secure Boot. Its local Lorax EFI-image step uses mtools instead
of unavailable rootless host loop devices; the adapter is retained as evidence.
The first Setup build was invalidated by editing its shell source while it ran.
The final build uses an immutable source snapshot and exits zero.


## 0.9.6 storage, Startup and troubleshooting — 4 November 2026

Local-only evidence: `target/polish-storage-2026-11-04/`. No host configuration,
physical disk, commit, push or release was changed. VERSION remains 0.9.5.

- `final-suite.json` / `.log` / `.exit`: **1,320 discovered Python tests across
  79 modules, 1,304 passed, 16 documented skips**, no failed modules; all 27
  JavaScript tests and pinned signed-connector reproduction/form tests pass.
  Test-runner and container exits are both zero.
- `affected.json`: **459 passed, zero skips/failures**, after the final QML,
  native scan and chosen-folder export changes. It includes 22 maintenance
  checks, Settings interactions, native laptop fixtures, style/package checks
  and polling tests. The final sparse-export change was additionally rerun in
  `unit-final.json` (22 passes) and the actual VM below.
- `task-manager-bundle/`: rebuilt/sealed native Plasma 6.8.2 executable, runtime
  manifest and source archive. `native-task-manager.log` confirms the actual
  executable loads the new Startup page and invokes the real helper once with
  no idle polling. `native-task-manager.png` uses Monet's actual KDE/Kvantum
  colors. Startup interaction tests cover add, toggle, keyboard Enter, search,
  failed reads and hidden-window idleness in a disposable home.
- `render.py`, `render.log` and PNGs: native Qt RHI/Mesa via private Xvfb, at
  100%, 125%, 150% and 200%, alternating Mist and Smoke. Storage review and
  troubleshooting use synthetic status responses; Startup uses actual isolated
  desktop entries. QSettings identity warnings belong to the minimal render
  fixture. Production Settings supplies its application/organization names.
- `vm-check-final.json`: real Btrfs on an overlay of the prior disposable
  baseline VM. A selected retained root contains a nested home and another
  nested Documents subvolume, plus a 100 MiB sparse file. The archive preserves
  their contents in 40 KiB, does not dereference an outside link, and excludes
  root-only files. Stale confirmations and a separately mounted retained root
  are refused (including different Btrfs major:minor numbers). Recursive removal
  deletes only that selected root; the active root remains. Helper mounts stay
  private. `vm-user-preserved.json` also verifies the pre-existing user files,
  saved preference and second-drive sentinel.
- `vm-usb.json`: an ordinary user publishes the completed archive on a disposable
  FAT filesystem, where hard links are unsupported; a pre-existing destination
  remains untouched. The production helper uses an atomic no-replace rename.
- `storage-benchmark.json`: five warm-cache samples per implementation on the
  same 8,400-file disposable tree. Median repeated scans: **35.7 ms**; bounded
  native traversal: **13.6 ms**. The initial Python walk regressed to 90.5 ms and
  was replaced before completion. This measures only folder accounting, not
  application launch speed, battery life, installation time or OS competition.

Failures found and fixed: Enter activation in Startup; saved-status text hiding
empty search feedback; inline QML components reaching outside their scope;
Smoke text/search contrast; unsafe recursive temporary-directory cleanup after
an unmount error; FIEMAP sizes reading zero before writeback; FAT-incompatible
hard-link publication; nested Btrfs folders omitted by tar's filesystem boundary.
No snapshot quota or estimate is presented as guaranteed reclaimable space.

Boundaries: only Setup's retained roots on the running Monet Btrfs filesystem
are offered. Export needs a matching owned account home and sufficient space on
the chosen destination; it does not copy other accounts. An interrupted copy is
left with `.partial`, never reported as a complete archive. Cleanup is recursive
and not transactional; an error requires refresh before another review. Startup
covers XDG desktop-entry autostart, not arbitrary systemd services or script
folders, and does not measure per-app startup impact. Diagnostics never upload
anything and distinguish unavailable service/rollback information. Full-image
integration of these additions, translation review, broader accessibility/app
polish and all physical hardware qualification remain open.

## Automated test environments

`python3 tools/test.py` runs each Python module in a separate process, with a
ten-minute per-module deadline and process-group cleanup. On Linux it creates
a temporary HOME/XDG tree, an offscreen Qt session and a private D-Bus daemon
without desktop-service activation. The real account's wallet, display, audio
server and system bus are not used. Phone and Passwords native fixtures are
enabled when their Qt runtime is available. Individual modules/classes can be
passed as positional arguments; `--summary PATH` records counts and skip reasons.

The Build workflow's required `desktop` job builds `tests/Containerfile` using
Fedora 44's matching Qt/PySide/KDE packages, then runs as an ordinary user with
networking disabled and a read-only checkout. `--require-desktop` checks required
Python, QML, native plugins and tools before running tests, and fails on
unexpected skips. It runs the JavaScript submission checks and rebuilds the
browser form fixture from the exact upstream XPI whose hash the existing
connector builder verifies. No extension is installed or submitted for signing.
The rebuilt payload must also match the bundled signed connector and its source
receipt. Native Ark fixtures extract real ZIP and tar downloads into temporary
folders, then scan without running the downloaded programs. Failed extraction,
name collisions and cancellation/process cleanup have separate regression cases.

Reproduce that job locally:

```sh
podman build -f tests/Containerfile -t localhost/monet-desktop-tests:44 .
mkdir -p target/desktop-tests
curl --fail --location --retry 3 \
  https://addons.mozilla.org/firefox/downloads/file/5078406/keepassxc_browser-1.10.4.1.xpi \
  -o target/desktop-tests/upstream.xpi
podman run --rm --init --userns=keep-id --network=none --cap-drop=ALL \
  --security-opt=no-new-privileges \
  -v "$PWD:/src:ro" -v "$PWD/target/desktop-tests:/results" \
  -e MONET_TEST_BROWSER_UPSTREAM=/results/upstream.xpi \
  localhost/monet-desktop-tests:44 \
  python3 tools/test.py --require-desktop --summary /results/summary.json
```

On an SELinux host, add `--security-opt=label=disable` for these explicitly
mounted source/results directories. To use the host's installed runtimes,
put Node on PATH and set `MONET_TEST_BROWSER_UPSTREAM` to the downloaded archive.
Also provide `MONET_ELECTRON_BINARY` from `tests/install-electron-runtime.py`
and `MONET_TEST_ELECTRON_DBUS` pointing to `node_modules/dbus-next` installed
from `linux/share/monet/app-integration/electron/package-lock.json`. The test
image installs both pinned Electron and these locked dependencies during build.
`python3 tools/test-browser.py ARCHIVE` independently rebuilds and tests the
connector's form code without network access.

Native Electron integration tests use the real main process and isolated-world
DOM filling, with accessibility disabled. The `MONET_FLATPAK_INTEGRATION=1`
fixtures additionally require an isolated container with nested mount/user
namespaces, Flatpak and an installed Freedesktop 25.08 runtime. They build and
install disposable applications in private HOME/XDG directories, never the
real account's Flatpak installation. The native integration fixture grants only
`org.monet.PasswordOffers1` access. The separate accessibility fixture exercises
Monet's actual per-app preference and verifies undo removes the override. Do
not run these fixtures directly against a real desktop. Local fixture builds
use Electron's `--no-sandbox` flag inside the test container; the outer Flatpak
filesystem and D-Bus sandbox remain active. This is not a flag for shipping apps.

Expected skips are limited to the notification checks executed by their passing
isolated parent, PowerShell checks owned by the Windows job, absent physical
partitions, restricted nested mount namespaces, the opt-in Flatpak fixtures, and
the opt-in systemd user-manager fixtures. Read-only boot-mount recovery has a separate required Linux CI step in
a private mount namespace. The systemd fixtures still need the configured VM or
an explicitly selected disposable user manager. None of these checks replaces a
complete OS-image installation, update/rollback, physical hardware or game test.

### 0.9.6 local full-image acceptance — 4 November 2026

Evidence is in `target/image096-2026-11-04/`. These are local, unpublished
builds from the dirty checkout at `e1fc593`; VERSION remains 0.9.5. Both complete
AMD/Intel and NVIDIA images build against pinned Fedora 45 Bazzite bases.
`inputs.json`, the build logs, `source-hashes.json` and the OCI artifact records
identify the inputs. The NVIDIA image has build coverage only; GPU and physical
hardware qualification are deferred.

The AMD OCI manifest used for full installs and the published-baseline upgrade is
`sha256:742af7acf59208dae9174f0454b130193e007ac0124ec0c98ec5b7f05806cda2`.
The later desktop-fix rebuild is
`sha256:229923150d4324c89a999289797f4aeb6545a9940e95cfae9152f9ffb04a0888`;
both AMD/Intel and NVIDIA rebuilds succeeded (`candidate-v3-images.json`).
Its local image label is `0.9.6-local.20261104`; the CLI and release-notes UI still
use the unchanged source VERSION. Do not identify these test deployments by
that displayed version alone. The published 0.9.5 baseline manifest is
`sha256:d7cbc37010f71b482b1651217d8cec61c0e2ef66178cf6c82887323facd2f73e`;
the published Setup ISO was checked against its release checksum and asset digest.

The bench uses KVM, private qcow2 disks, Microsoft-trusting OVMF firmware and,
for the encrypted trial, a software TPM. Each VM has a 96 GiB target and a
separate 64 GiB drive containing a sentinel. A read-only loopback registry serves
the local OCI layouts; changing its stable alias makes the real update helper
discover the candidate. Temporary guest credentials provide the test channel and
RPC agent. They are not packaged in Monet. No host drives, firmware, desktop
configuration or TPM were changed.

**Upgrade and rollback pass.** The published installer installed the baseline,
its virtual MOK was enrolled, and the desktop started with Secure Boot enabled
and SELinux enforcing. `monet helper update` then staged the candidate; reboot
verified its exact manifest and Fedora 45 kernel. `monet helper rollback`, followed
by reboot, restored the published manifest and Fedora 44 kernel. The sequence
was repeated for the v2 candidate with the EFI ordering fix. Documents, a custom application shortcut
and a KConfig preference survived both directions. The separate drive's sentinel
and entire qcow2 file hash stayed unchanged. The final candidate and rollback
boots report no failed system units. See `baseline/v2-*.json`,
`baseline/user-data-after-v2*.json` and `baseline/upgrade-rollback-serial.log`.

The initial candidate exposed an EFI mount race: Monet's read-only ESP probes
could overlap bootupd's writable mount. Both early ESP readers now wait for
`bootloader-update.service`; the final boot journal verifies that order. The
initial failed bootloader update succeeded on retry. The later boot had no new
EFI update to apply, so this proves ordering and a clean boot rather than a second
bootloader binary transition. Full-image builds also exposed missing KF6
GlobalAccel/XmlGui dependencies and the obsolete `ostree container commit` step;
the build declares those dependencies and uses `bootc container lint`. That lint
passes 11 checks with one skip and three nonfatal warnings for build-time DNF
runtime/log/state files. The build also reports dracut's missing `/root` source
diagnostic but exits successfully; image hygiene remains follow-up work. These
diagnostics are retained in the logs, not counted as clean lint output.

The fresh install trials exposed several mount-lifetime problems. Shared chroot
`/dev` and `/sys` mounts prevented clean unmounts, so configuration now makes each
bind mount recursively slave. Bootc also left `/run/bootc/storage` mounted outside
the target tree: the encrypted install correctly reported a cleanup failure, and
the unencrypted trial retained that alias despite reaching All set. Bootc now runs
in a private mount namespace so its auxiliary mounts cannot propagate or outlive
it. The `.6` rerun still failed to close encryption: six live system services had
retained copies of the worker's own target/chroot mounts. Releasing those copies
in the disposable VM immediately allowed `cryptsetup close` to succeed. The
entire worker now enters its own recursively private mount namespace before
probing drives or starting threads; inability to isolate stops before drive
writes. A native target/device-mount test verifies that only the worker sees its
mounts and live-service namespaces stay unchanged. The `.7` keep-mode full
installation reached All set with every service mount namespace clean; checking
just the live session's main mount table is insufficient. The encrypted `.8`
full retry also passes this check. See `worker-namespace-proof.json` and
`encrypted/service-mount-root-cause.json`.
A later retry also exposed stale OSTree boot entries pointing into the preserved
root. Setup now copies and flushes the former boot files into a `saved-boot-*`
folder within a retained subvolume before removing those entries and rebuilding.
It leaves the receipt, bootstrap recovery key and separate EFI partition intact.
Regressions cover retained symlinks, unchanged unrelated data and a failed backup
flush leaving the originals available for another retry.

**Keep-data installation passes.** The final `.7` worker preserved the entire
existing 2 GiB data partition and separate drive by SHA256, removed its receipt
and runtime state, released all target mounts across every live service namespace,
and booted the exact candidate manifest with Secure Boot and SELinux enforcing.
The desktop and Welcome page opened; the existing partition hash still matched
after login. See `keep-private/clean-finish.json`, `firstboot.json`,
`kept-partition-{before,after,after-boot}.json` and `desktop-settled.png`.
The offline encrypted trial preserved its exact checkpoint, bootstrap key and
retained-root sentinel through the interruption (`encrypted/final-offline-resume.json`).

**Encrypted offline completion passes.** With the network link disconnected,
`.8` verified the saved OCI blobs, rebuilt the unfinished system without
formatting, and reached the recovery-key page and All set. All service mount
namespaces were clean, the LUKS mapping closed normally, and the receipt and
runtime key were removed. The displayed recovery phrase passed an actual
`cryptsetup --test-passphrase` check. On first boot the software TPM enrolled,
the bootstrap key file disappeared, and its original slot was revoked. The
retained document hash and archived boot entries remained intact; Secure Boot
and SELinux stayed enabled and system units reported no failures. See
`encrypted/clean-finish.json`, `recovery-key-test.json`, `all-set.png`,
`firstboot-seal.json` and `firstboot-status.json`.
The second boot unlocked automatically using the software TPM with no
`rd.luks.key` argument or bootstrap file. The recovery phrase still worked when
external token plugins were disabled and its specific key slot selected; an
incorrect phrase was rejected. This avoids mistaking a TPM token unlock for a
successful recovery-phrase test. See `secondboot-tpm.json`,
`recovery-key-after-tpm.json` and `recovery-key-negative.json`.

Setup's Fedora 45 Plymouth script plugin also crashed without its label plugin.
The ISO now explicitly includes `plymouth-plugin-label`; both root plugins, the
initrd label renderer and font links were inspected. The rebuilt `.4` ISO boots
with Secure Boot enabled, opens Setup, and reports no failed services. Its boot
evidence is under `splash/`; the installer namespace fix requires the later ISO.

**Required desktop suite passes on the candidate runtime:** 1,288 Python tests
discovered across 77 modules, 1,272 passed, 16 documented skips, no failed modules;
27 JavaScript checks and signed-connector reproduction pass. Both runner and
container exited zero (`desktop-final-suite.json`, `desktop-final-suite.log`,
`desktop-final-suite.exit`; the earlier `completion-suite.*` also passes).
The isolated test image adds Node to the candidate solely for the test runner.
The first Fedora 45 run found Python 3.15's removed `load_module` API in two test
fixtures and a systemd condition fixture using an inaccessible manager runtime;
these fixtures were corrected. The focused confirmation passed all 125 checks
without skips. Later runs under concurrent image/VM load exposed two test-fixture
races: fixed millisecond sleeps inspected Qt callbacks before completion, and
two real free-space reads differed while VM disks grew. The tests now wait for
completion with a bounded deadline and check accounting against a fixed statvfs
snapshot, respectively; real-filesystem accounting invariants remain covered.
The final complete run passes. Earlier failing evidence remains in
`full-suite.*`, `private-suite.*` and `acceptance-suite.*`.
No extension was installed or submitted for signing.

Restarting Setup also reproduced a black screen: seatd left an abandoned socket
that prevented the next compositor from starting. Startup now removes only an
owned Unix socket whose connection is refused and whose inode has not changed;
it retains active sockets, links and other file types. Real-socket regression
tests pass. The final `.8` ISO returned to the interactive Hello screen after
two service restarts, with no seatd socket errors or failed system units. See
`encrypted/display-restarts.json` and `encrypted/restart-{one,two}.png`.

Installed-desktop acceptance found two additional Plasma 6.8 issues. KWin's
uncreatable `Window` type shadowed Qt Quick's window, so Monet Snap did not load.
The overlay now explicitly uses the Qt Quick import. In the running candidate,
Windows+Z opens the picker and selecting its left half places Settings correctly
(`keep-private/snap-picker.png`, `snap-left.png`). Plasma's foreground booster
also started before the display existed and aborted four times during login.
A drop-in orders it after `plasma-core.target`, matching other graphical helpers.
A reboot/login with these local guest overrides reports no snap load error,
an active booster with zero restarts, and no failed system or user units
(`keep-private/desktop-startup-{before,after}.json`). The rebuilt image was then
staged through `monet helper update`; all temporary guest overrides were removed
before reboot. The installed files match the source hashes, Windows+Z and
half-screen placement work, and the booster has zero restarts. Documents,
shortcuts, preferences and the other drive's sentinel survive this update.
See `keep-private/v3-{update,staged,desktop}.json`, `v3-snap-*.png` and
`user-data-after-v3.json`. Rollback then booted the exact preceding manifest with
no failed system units and the same documents, shortcuts, preferences and
other-drive sentinel (`v3-rolled-back.json`, `user-data-after-v3-rollback.json`).
After shutdown, the separate drive's entire qcow2 hash also matches its value
before installation (`second-drive-final.json`). This later rebuild changes only
the snap import and foreground-helper ordering; its fresh-install path was not
repeated.

A separate 160 GiB disposable VM disk exercises the real NTFS tools with
synthetic files. `prepare_keep` shrank its 159 GiB NTFS partition to about
79.5 GiB, retaining its start, type, partition UUID and filesystem UUID. The EFI
partition's entire SHA256 and both personal-file hashes stayed unchanged; file
detection and read-only copying into a new destination also passed. See
`ntfs/shrink-result.json` and `ntfs/import-result.json`. This is filesystem-path
coverage, not a booted Windows installation or its scheduled chkdsk, BitLocker,
hibernation, fragmentation and workload matrix.

These results do not qualify physical Razer thermals, NVIDIA graphics, real TPM
firmware changes, Windows/game trips, or comparative OS performance. They also do
not cover every possible interruption boundary or a booted Windows shrink.

### Installer drive review and restart recovery

`python3 tools/test.py tests.test_setup tests.test_setup_recovery tests.test_setup_window`
uses synthetic drive metadata, temporary files and native offscreen Qt. It never
formats a host drive. Coverage includes explicit drive selection/confirmation,
live/mounted/mapped drive refusal, changed disk/partition identities, checkpoint
and bootstrap-key integrity, an interrupted worker followed by lost RAM and an
offline retry, corrupted/missing OCI blobs, preservation of an unfinished root,
checked flush failures, noisy worker output and asynchronous restart failure.
CPU affinity is tested only in a disposable subprocess; sensor reads are fixtures.
Screens were inspected at 1440×900 and 1024×768. Evidence is under
`target/setup-drives-2026-11-04/`.

Disk preparation, encryption, mounts, bootc and firmware commands are mocked in
these regressions. The following acceptance checks remain for a disposable VM
and, where relevant, physical hardware with a newly built Setup ISO:

- Attach two virtual disks with distinct sentinel files; choose one and confirm
  that erase/keep and encrypted/unencrypted installs leave the other unchanged.
- Interrupt after partitioning, mid-download, during bootc unpacking and during
  final cleanup. Restart the USB and resume the same drive, with networking
  disabled for a completed download. Verify the key, bootability and cleanup.
- Repeat a failed late retry with a missing download subvolume, retained personal
  files and low free space. Recover files from `previous-install-*` explicitly.
- Verify the Razer after its reported 6.7 GB download transition, with normal and
  gentler scheduling. Neither pointer nor Ctrl+Alt+F3 responded in the reported
  failure. Record persistent phase/health samples and kernel evidence; the cause
  and whether these changes resolve it are still unverified.

The installer uses bootc's documented
[`--skip-finalize`](https://bootc.dev/bootc/man/bootc-install-to-filesystem.8.html)
while postprocessing and scratch files still write to the target. After those
handles close, `bootc install finalize` checks the deployment; targeted flushes
and checked normal unmounts complete the installation. It does not force a
full-device discard or freeze a filesystem that still holds active scratch files.
This ordering needs full boot/install acceptance, not only command fixtures.


Phase 0 of the plan: prove the switch works before building more. Fill in the
tables as you go and commit the results.

Much of it can be tried first in the test VM, by an AI or by hand: docs/TESTBENCH.md.

2026-10-29 integration work is in progress under `ai-before-full-image-1029`. The complete
image build exposed a missing notification-stage `kf6-kitemmodels-devel` dependency; after
adding it, the notification stage compiled and sealed successfully. Full-image installation,
boot, upgrade and rollback have not passed yet. Build inputs and fixes are recorded in
`target/full-image/source-upload.json` and `source-patches.json`.
The second attempt reached the editor runtime guard, which refused development packages
that upgraded util-linux libraries absent from the final runtime. Updating that library family
before native runtime capture fixes the mismatch without weakening the compatibility guards.
The complete build now passes: unpublished image `localhost/monet-vm:1029`, ID
`91639aafadcdacc4e5cf4dcdafb4e139c35f2bc39b9867463eea06e1ee32e3e8`.
The assembled CLI starts and the restoration helpers/native binaries are present. Bootc
container lint passes 12 checks, skips one, and warns about package-manager logs and files
under `/var`. These container checks do not establish that the image boots or upgrades safely.

The PDF capture prototype separately passed five Python checks and one native three-window
scenario using real Okular 26.08.1 PDF parts in a matching nested Wayland compositor. It
checked reordered tabs, active tabs, independent pages for the same file, empty windows,
Save As paths with original files preserved, modified-state reporting, unchanged window
geometry/selection, distinct surface identities, refusal without the identity plugin, and
capture of the last survivor after the original D-Bus window disappears. Source hashes,
native proof and logs are in `target/pdf-recovery/`. Only generated documents were used.
The protected-departure follow-up passes eight focused checks and a second native fixture.
It uses actual annotations, native Save/Discard/Cancel prompts, and independent PDF reads to
verify saved content, final Save As paths, the active tab and an untouched unsaved survivor.
A late Save after switch cancellation/controller loss cannot close the window; failed receipt
writes also veto closing. The capture regression passes with the departure patch installed.
Evidence is in `target/pdf-recovery/departure-evidence.json`. Automatic switching integration,
verified reopen/retry and image packaging remain open.
The later private-session fixture runs the actual patched Okular CLI, preserving duplicate
tabs at different pages, selection and independent windows despite conflicting normal tab
preferences. Empty windows, Unicode/backslash paths, malformed state, missing-file preflight
and launch identity pass. Both native regressions and 73 focused Python checks pass, including
controller capture/final receipts and new-window watch protection. Evidence:
`target/pdf-recovery/restore-evidence.json`. PDF return/retry integration remains unfinished.
The original Notes checksum remains unchanged. Build containers are retained for the next
step, and the checkpoint is not restored while the image build is active.

The PDF late-tab retry follow-up passes 74 focused checks, the native capture/departure/retry
fixtures and the actual CLI/private-session D-Bus scenario. It preserves newer modified
parts, pages, selection and geometry; verifies duplicate-path tabs, stale-state refusal,
late files, repeated requests and manually closed tabs/windows; and distinguishes unavailable
identity support from a closed window. The CLI fixture repeats the same durable request if
a reply is delayed or missing. Final tested source hashes and proof are recorded in
`target/pdf-recovery/retry-evidence.json`; Notes retain their original checksum. Earlier
fixture method capitalization and ambiguous startup identification failures were corrected,
and the whole native batch rerun. Return-controller integration and image packaging remain
unverified; no automatic PDF switching or hardware return is claimed.

The return-controller follow-up passes 124 focused VM checks and a native three-window
scenario. It verifies durable launch ownership, competing launch refusal, duplicate-path
pages, missing-file counts, exact placement and an untouched cancelled-switch survivor.
When the missing PDF returns, automatic recovery leaves newer live work alone; explicit
Retry appends once. The fixture drops that successful reply, reloads the controller and
verifies that the recorded attempt produces no duplicate. Original PDFs, ordinary viewer
preferences and Notes stay unchanged. Evidence and tested source hashes are in
`target/pdf-recovery/return-evidence.json`. Ambiguous disappeared launches require explicit
Retry. Production PDF bundle and installed-image checks remain open.

The production PDF bundle later built and installed into a matching runtime in the VM.
The first attempt rejected a build-only Brotli upgrade; updating the shared runtime before
capture fixed that mismatch. The final install preserves exact hashes of the document part,
core and PDF generator, validates corresponding source and resolves all linked symbols.
The older runtime is rejected. Evidence: `target/pdf-recovery/bundle-evidence.json`.
Native tests of this exact packaged binary and a complete image containing it remain open.

The integration2 replacement passed its real boot trial and installed migration, including
a no-op repeat. Existing preferences, pins, Notes, a saved document and desktop shortcut
survive; all 32 title-button assets match the assembled image. Installed adapters restored
two shared-process editor windows and two Files windows with tabs/splits and placement
within one pixel, without duplicates on repeat. Disk stalls produced metadata misses and
snapshot timeouts in earlier attempts; the same retained windows were inspected afterward,
not relaunched. Startup still reported Plasma initialization/splash timeouts and a base
automount failure. Repeated sign-in, everyday entry points and controlled rollback remain.
Evidence is under `target/full-image/integration2/`.

The follow-up distinguishes failed compositor inspection from an empty desktop. All 244
focused checks pass. A live editor and isolated session bus verify that unavailable inspection
retains the checkpoint without launch; Retry on the real bus reuses the same window with
document state and contents unchanged. The fixture's initial result-list assertion was
corrected: the controller reports completed native recovery even when it reused an owner.
`snapshot-outage-evidence.json` records the final proof and source hashes. These capture fixes
still need inclusion in the next complete image.

The exact packaged PDF shell subsequently passed the real CLI/private-session and
return-controller fixtures in a matching isolated VM runtime. The tested binary hash
matches the sealed bundle. Duplicate-path pages, independent windows, selection/placement,
protected final receipts, cancelled-switch survivors, missing-file retry and interrupted
append recovery pass without duplicates. Synthetic files, viewer preferences and Notes
remain unchanged. The fixtures close their windows normally; the container is stopped.
Evidence is `target/pdf-recovery/production-native/packaged-evidence.json`. A slow rootless
container ownership conversion delayed setup but did not cause a test failure. Complete-image
PDF boot and broader office/editor/browser support remain unverified.

Rollback failure injection found that `monet-boot` ignored a failed scheduling command,
cleared its trial and could reboot while claiming success. Both the failed-desktop and
GRUB-fallback branches now stop on scheduling failure, retain the existing trial/notice
and report a nonzero result to systemd. The new regressions fail against the installed
image; all 11 `GoingBackByItself` checks pass with the source fix. Before/after logs and
hashes are in `target/full-image/integration2/rollback-regression.json` and sibling logs.
The fix remains uninstalled. The user subsequently ran the guarded staging command using
the installed `monet helper rollback`. It queued the expected earlier deployment, followed
by a normal desktop restart. Boot `f77dda8b-8daf-4a6d-812d-5a589c815905` and a repeat normal
boot `02d291e6-81cc-4ea9-8359-1853e32a96a8` both preserve the latest saved document revision,
Notes, preferences, pins and shortcut bindings. KWrite opens the latest saved text; the
test window closes normally. Only the expected desktop shortcut screen mapping differs.
Evidence is `target/full-image/integration2/controlled-rollback.json`; the complete archive
`controlled-rollback-evidence.tar` has SHA-256
`5cdbd2b5c4b1efd30836f8d7491b70836e8d03872697727e96f261b8ee31a171`.

The first rollback desktop exposed missing Sound and broken panel presentation. These were
bench preview packages deliberately removed before full-image acceptance, with backups kept
in `before-upgrade`. Restoring and hash-checking those exact 25 asset directories/launcher
entries repaired the original preview desktop; Sound opens correctly after the repeat boot.
The original deployment/data checks precede this repair and remain separate. This does not
prove automatic compatibility for new widgets across shipped versions. Future image tests
must again exclude these preview overrides before claiming bundled-asset validation.
Base input-remapper and splash startup timeouts remain under substantial VM disk stalls.
After exporting the evidence and synthetic document, the bench returns to
`ai-before-controlled-rollback-1029`; checkpoint cleanup is not a re-upgrade test.
Nothing was published.

The first complete candidate later booted as deployment
`7e2b39e14643802b1ee38175fe51fd925323b3ddee3f63d06a032b797da7575d`. Installed helper/native
manifest hashes match the assembly evidence. Preferences, pins, Notes, saved work and a
desktop shortcut survived. Installed KWrite and Dolphin passed a real four-window capture,
native final editor receipt, cancelled-switch reopen and repeated restore without duplicates.
An initial compositor timeout was preserved as a failed attempt; the same open windows were
then used to finish the check. First boot took 4m29s and Plasma's splash timed out.

This image failed acceptance. Its migration unnecessarily wrote already-matching locked
system defaults; the image installer omitted shared title-button images; and `monet-boot`
treated short SSH sessions as changes to the graphical desktop. The latter forced a false
rollback after six minutes. The original deployment booted again; preferences, Notes, pins,
saved document and shortcut remained intact. The only changed pre-existing shortcut field
was its translated/display label (the Meta+G binding stayed unchanged). The fixes avoid
claiming ownership of inherited matching defaults, install the missing assets, and restrict
boot stability to local X11/Wayland sessions. Both new regressions failed before the fix;
30 focused VM checks pass afterward. A replacement image still needs boot/sign-in/rollback
verification. Evidence is under `target/full-image/`, including `installed-restoration.json`,
`rollback-evidence.json` and the candidate boot journal; these are not hardware tests.
`live-boot-filter.json` records the corrected check accepting the real local Wayland session
after 60 seconds while excluding SSH. `profile-fix-evidence.json` records the successful live
migration and unchanged journal on repetition after rollback. Four-window geometry/flag
comparison has at most 0.5-pixel rounding (`placement-evidence.json`). The replacement
full-checkout build has completed. Replacement assembly checks verify 14 helper/native
entries and 32 title-button assets, with bootc lint passing. The exported archive is
6,069,314,048 bytes, SHA-256 `9f653fc35c3b24dc923ee7999b23c3c33aef81aa6fa412f85ea17dcc5bd89e32`.
Inputs, assembly/lint evidence and the checksum-verifying staging script are under
`target/full-image/integration2/`. The user root staging step and replacement boot checks
remain; export/assembly success does not establish upgrade acceptance.

Test machines:

| Machine | GPU | Notes |
|---|---|---|
| Laptop | RTX 2080 (Turing) | Hybrid graphics: check games use the NVIDIA GPU |
| Desktop | RTX 5080 (Blackwell) | Needs NVIDIA open kernel modules (driver 570+) |

## 1. Setup

- [ ] Bazzite installed next to Windows 11 ([INSTALL.md](INSTALL.md))
- [ ] Secure Boot **on** in both systems (`monet doctor` in Monet; in Windows, `Confirm-SecureBootUEFI` in an admin PowerShell)
- [ ] `monet doctor` shows no âœ—
- [ ] Monet Bridge installed; `monet-bridge status` (admin terminal) lists the Monet entry
- [ ] The right Monet for the graphics: `rpm-ostree status` (or `bootc status`) shows `monet` on the RTX PC and `monet-amd` on a PC with only Intel or AMD graphics (or an NVIDIA card older than the RTX 20 series)

### Making the USB stick

- 2026-11-11 Windows 11 VM. The exact 0.9.7 maker listed the 4 GiB virtual
  USB stick with 512-byte sectors and excluded the Windows system disk. An
  incomplete local ISO was refused with zero device writes. The exact local
  Setup ISO produced Ready after a first write and a rewrite, with a full
  device read-back each time.
- The stopped guest's USB image matched the ISO outside the primary GPT
  header. Its valid backup header was relocated to the end of the larger
  device, and both partition tables matched the ISO. A separate VM booted
  that read-only USB image to the Setup welcome screen with Secure Boot
  enabled. Evidence is in `target/097-clean-release/usb-vm/evidence/`.
- A Windows 11 follow-up held a file open on an NTFS stick. The writer
  refused the volume lock and the file's SHA-256 and volume label stayed
  intact. Replacing the selected stick while the confirmation was open
  reused the same Windows disk number and capacity. The writer rejected the
  new identity with zero writes or discards to the replacement.
- The refreshed maker displays the partial-write warning only after it
  attempts to change the disk layout. In the VM, the busy-stick refusal
  showed only the reason and the file kept its SHA-256. Unplugging the
  virtual stick during the actual transfer still showed the partial-write
  warning. A retry with a blank virtual stick completed a full write and
  read-back. A separate VM booted the result to Setup with Secure Boot
  enabled. All 18 USB maker tests on Linux and Windows-target Clippy passed.
  Evidence and the rebuilt Windows executable are in
  `target/097-clean-release/usb-safety.xmzz8t/`. These runs used a local ISO
  and 512-byte logical sectors.
- The earlier maker reported Ready on a native 4 KiB virtual USB after
  writing and verifying the ISO. UEFI found no bootable option on the
  written stick. The image's GPT header is at byte 512, and UEFI looks at
  byte 4096 on that drive. The refreshed maker refused the same drive
  before the erase prompt, with zero device writes or discards.
- Windows reported 512-byte logical and 4 KiB physical sectors on a
  separate 512e virtual stick. The refreshed maker wrote and verified
  the local Setup ISO on it. A separate VM booted the written stick to
  Setup with Secure Boot enabled and confirmed both sector sizes.
  All 19 USB maker tests on Linux and Windows-target Clippy passed.
  The executable, checksum and VM evidence are in
  `target/097-clean-release/usb-sector.MvjFp0/`.
- The built-in downloader used a fixture URL in an isolated Windows 11
  VM. It resumed a broken transfer at byte 16777216 and rejected a
  full-length corrupt ISO without writing to USB. The earlier build
  reused that bad cache on retry. The refreshed maker removed it after
  verification failed, then fetched a fresh Setup ISO on retry and
  verified the written stick.
- When Setup was unavailable, the maker downloaded the Fedora fallback.
  Windows reused Disk 1 for a replacement virtual stick inserted during
  the download. The maker refused the changed identity with zero writes
  or discards. A new confirmation wrote and verified the cached fallback
  without a second download. The written stick started Anaconda with
  Secure Boot enabled. Both ISO cache files were absent after the
  successful writes. All 21 native Windows tests, 19 Linux USB maker
  tests and Windows-target Clippy passed. The rebuilt release executable
  retained its official HTTPS URL. Evidence, checksums and the executable
  are in `target/097-clean-release/usb-download.Vxr97y/`.

- [ ] The new safety-preview writer lists a plugged-in USB stick, writes and verifies it,
      and the PC boots its installer. Check 512-byte logical sectors, including 512e,
      and verify that native 4 KiB logical sectors are refused before writing.
- [ ] Unplug/replace the selected stick while downloading: the replacement receives no writes.
- [ ] Keep a file open on the target: an unsuccessful volume lock stops before any dismount/write.
- [ ] An oversized/corrupt image and a failed device flush never produce a Ready message.
- [ ] Rewrite a previously flashed installer stick (ISO/Linux partitions, an EFI partition,
      multiple drive letters and an extra NTFS volume). One click clears the old layout,
      writes and verifies the image, and boots Setup without manual Disk Management steps.

2026-11-05 USB rewrite repair: volume locks and target validation precede a native
`IOCTL_DISK_DELETE_DRIVE_LAYOUT` reset, which removes stale MBR/GPT metadata including the
backup GPT at the device's end. An empty MBR is then initialized with `IOCTL_DISK_CREATE_DISK`:
the tested removable disk otherwise accepted reads but rejected all data writes with error 21.
After partition refresh, old handles are closed and the reopened physical device must pass
the same identity, USB, system-disk and capacity checks. Readiness and busy volume locks
have bounded retries; a persistent lock failure still stops before modifying the disk.
Locked ISO/Linux volumes no longer have to implement `FSCTL_DISMOUNT_VOLUME`.

All 20 native Windows GNU unit tests, the USB discovery regression and Clippy with warnings
denied pass. A hardware harness using the production `disk::write` completed two consecutive
writes of Monet 0.9.6 Setup to the same Kingston DataTraveler 3.0 (61.9 GB), with a device
flush, full byte-for-byte read-back and final partition refresh on both rounds. Results are
in `target/usb-repeat-test.log`. The release executable's administrator manifest was checked.
The window and confirmation flow are unchanged. Booting the rewritten stick and other USB
controllers are not qualified by this test. The reset's MBR/GPT behavior is documented by
[Microsoft](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ni-ntdddisk-ioctl_disk_delete_drive_layout).

2026-10-28 software evidence: `cargo test -p monet-usb` passes all 18 Windows tests, including
native SHA-256 against a known vector and a temporary source file that cannot be changed or
deleted while held. No Windows test opens a physical drive. Seventeen portable tests also
pass in the Linux VM: wrong device/system disk, capacity including padding, checksum parsing,
invalid ISO headers, simulated lock/write/flush/read failures, corruption and partial writes.
The transfer tests check aligned buffers/offsets, write the header last and preserve bytes
after the image. Clippy passes. The release executable in
`dist/Monet-0.9.3-Make-USB-Stick-safety-preview.exe` is unsigned; Defender found no threats.
These checks do not replace actual Windows disk-driver, controller, hotplug and boot tests.

### Clock format repair — 2026-10-28

Settings' 24-hour toggle updates both the large desktop clock and panel clock in the running
VM. Both directions were observed without signing out. The shared component also feeds the
world clock, lock screen and timed quiet-mode labels. A Qt regression loads two clocks,
changes the preference externally, removes the explicit override to follow the region, and
opens another instance to verify persistence. Sixty-seven focused Python/UI checks pass.
Screenshots are under `target/clock-usb/`. The VM test checkpoint was restored, its notes
checksum stayed unchanged, and the clock-only user overrides were then reapplied for use.

### 0.9's smaller things

- [ ] Upgrade an existing account with `look-0.9.3` and `names` already stamped, and Bazaar/Discover pinned: after sign-in, every Store shortcut opens Monet's gallery. Include a pinned `file:///usr/share/applications/org.kde.discover.desktop`, not just an `applications:` id. Sign out/in again: the result stays, unrelated pins and the desktop layout stay as chosen
- [ ] Settings, Store and Games in Mist and Smoke, with Clear, Frosted, Matte and Solid glass: title and sidebar change opacity together, all outer corners are rounded, and no square blur or pale strip extends outside them. Maximize removes the outer rounding; restore brings it back. Check normal, maximized and snapped windows at 100%, 125% and 150%
- [ ] Drag each app by its title, double-click to maximize/restore, and use all three title buttons with mouse and keyboard. Resize from all four edges and corners, especially above the title. Confirm Windows+Z and shared-edge resizing still work; repeat without compositor blur and with Qt Quick's software renderer
- [ ] Snap Settings beside Store, then beside a client-decorated app: both fill their tiles without an inset. Drag their shared edge in either direction, then stack two windows vertically and drag that shared edge; no gap or overlap. Stretch a window to the bottom: it reaches the work area's bottom
- [ ] Settings â†’ Updates names Monet's version ("Monet 0.9.3 is ready"), not "44.2026â€¦"
- [ ] Settings' four sides and four corners drag it bigger and smaller, taken hold of on the glass edge outside the page too, the edge staying under the pointer; it goes down to the screen's bottom; double-clicking "Settings" fills the screen; the size is kept, and it opens all on the screen
- [ ] Popovers, the tray's (Disks & Devices, Audio Volume), the menu and the bars show the painting's strokes, like the desktop widgets
- [ ] The clock's page goes back to its width after the notes close; a note written there shows in the Calendar widget within a second
- [ ] Light & Wallpaper â†’ Through the year hangs the painting of the season
- [ ] The bar stays in view; with Light & Wallpaper â†’ Bar steps aside on, a window dragged over the bar makes the island under it slide away, and pointing at the bottom edge under it brings it back
- [ ] Timer â†’ Focus, then start: notifications stay quiet, the painting goes from dawn to night over the minutes, and both come back after
- [ ] Games & Controllers â†’ Save the last 30 seconds: GPU Screen Recorder installs, KDE asks for the screen once, Windows+Alt+G saves an MP4 in Videos
- [ ] Search in the menu for "printers": Settings' Printers page is found

### Next to Windows, backups and the painting

- [ ] Monet Setup on a PC with a full Windows drive: choose that drive and "Keep existing data and add Monet"; the note offers to make room (from and to). Select Bring my files explicitly. After installing, Windows still starts (it checks its drive once).
- [ ] At the first sign-in the files from Windows are in Documents, Pictures and the rest, and a note says so
- [ ] Settings â†’ Backups: after an hour, "An hour ago" opens your files in Files; right-click a file â†’ Earlier versions â†’ Put back puts a copy beside it
- [ ] A USB drive picked in Backups gets "Monet Backup/<you>" the next time it's plugged in
- [ ] The Hours changes light near your sunrise and sunset, not at fixed hours; on a rainy day the painting is softer
- [ ] Display shows HDR and Smoother games on a monitor that can do them, and they change the monitor
- [ ] Games & Controllers lists a game installed here whose anti-cheat needs Windows

### Safety and recovery (0.9.1)

- [ ] Monet Setup's Hello shows the language's time zone with its time; once online it moves to where the PC is, unless one was chosen; the installed Monet has the zone chosen
- [ ] On the blue screen after installing, choose Continue boot on purpose: Monet doesn't start ("bad shim signature"). Start from the USB stick: Hello says Monet can't start yet and offers Ask again and restart; after it, the blue screen is back, and Enroll MOK lets Monet start
- [ ] All set shows the blue screen's five steps in pictures beside the sheet, in the language chosen (the blue screen's own words in English), and right to left in Arabic and Hebrew
- [ ] Choose Continue boot on purpose with the stick out: "bad shim signature" for about ten seconds, then "Monet needs your OK on a blue screen", and the PC restarts into the blue screen; Enroll MOK, Continue, Yes, monetsetup, Reboot, and Monet starts. The GRUB menu (Esc while starting) lists "Monet: ask again for the blue screen"
- [ ] The password twice: different, Continue waits and says so; both empty, a warning says Monet signs in by itself, and the installed Monet starts straight into the desktop without locking; after Settings â†’ Accounts gives it a password, the next start asks for it
- [ ] Monet Setup on a PC with a TPM 2.0: Encrypt this PC is ticked; after installing, the recovery key page shows eight groups of eight letters, and Continue waits for "I've kept my recovery key"
- [ ] The first start (after the blue screen) asks for no passphrase; afterwards `sudo systemd-cryptenroll /dev/disk/by-uuid/<uuid>` lists a tpm2 slot and a password slot (the recovery key), `/boot/monet-firstboot.key` is gone, and after the next restart `/proc/cmdline` has no `rd.luks.key`
- [ ] Turn Secure Boot off (or clear the TPM): the start asks for the passphrase; the recovery key opens it, and the start after that doesn't ask
- [ ] In a VM: install an update, restart, and within its first minute stop the sign-in screen (`sudo systemctl stop display-manager`): five minutes later the PC restarts into the Monet from before, Settings â†’ Updates says "Monet went back to â€¦", the next sign-in says so too, and `sudo systemctl start monet-update` skips that update
- [ ] An update that starts normally: `/var/lib/monet/trial.json` is gone a minute after the sign-in screen, and `grub2-editenv list` has no `boot_counter`
- [ ] Settings â†’ Updates â†’ Reset this PC asks for the password; after Restart now: Monet's look and welcome come back, Documents, games, apps, Wi-Fi and printers are still there, the settings from before are in `~/.local/share/monet/before-reset`, and a note says Monet is as it came
- [ ] An update that starts normally shows no start menu while the PC starts

### Fixes in 0.9.1

- [ ] The desktop and the lock screen show the painting (0.9.0 showed black)
- [ ] The bar's three islands show on an empty desktop
- [ ] Windows' clock is right after coming from Monet (and Monet's after coming back)
- [ ] Quitting a game in Windows restarts into Monet by itself; the PC doesn't switch off

### Bluetooth in both (0.9.1)

- [ ] Pair a controller (a DualSense: classic Bluetooth) in Monet, then in Windows. Back in Monet it connects without pairing again (`journalctl -u monet-pairings` says "took Windows' pairing for â€¦"), and in Windows it still connects
- [ ] The same with a Low Energy device (an Xbox controller with current firmware, or earbuds)
- [ ] Pair it again in Monet only: Monet keeps its own pairing at the next start (Windows needs pairing once more, then both work)

### Next (after 0.9.1)

- [ ] Settings â†’ About Monet â†’ Save a report: after a few seconds a notification says it's in Documents; Show opens Files on it; the file has every part (the PC, this start's errors, the start before, sleep, Monet's records), none empty where the PC has the thing
- [ ] Settings â†’ Accessibility â†’ Magnifier on: Windows key and + zooms in around the pointer, Windows key and âˆ’ zooms out; off, the keys do nothing; it stays as set after signing out and in
- [ ] Settings â†’ Phone with no phone yet: the QR code opens KDE Connect's download page on the phone; with the app open on the same Wi-Fi the phone shows up under it, Pair asks on the phone, and once accepted the phone is listed with its battery
- [ ] Ring makes the phone ring; Send a fileâ€¦ sends a file; Texts opens the phone's messages; Files on your phone opens it in Files; Forget unpairs it
- [ ] On a laptop with a fingerprint reader: Lock & Privacy shows Fingerprint; after Set upâ€¦ (Accounts â†’ Configure Fingerprint) the lock screen unlocks with a finger and an administrator question (Reset this PC) accepts one; without a reader the row isn't there
- [ ] Screenshot (Print Screen) â†’ Extract Text on a picture with text in your language (Swedish, say) reads it; Screenshot's settings list your language and English
- [ ] A Windows that Monet installed shows The Hours as its desktop; "Monet next to my Windows" keeps Windows' own wallpaper
- [ ] Monet Bridge updates itself: with an older Bridge in Windows and a newer release out, quit a game: the PC restarts into Monet a few seconds later than usual, and next time in Windows `monet-bridge status` (admin terminal) shows the new version; `C:\ProgramData\Monet\update.log` says so
- [ ] With no internet in Windows, quitting a game still restarts into Monet (at most about 20 seconds later)
- [ ] `powershell -ExecutionPolicy Bypass -File "C:\Program Files\Monet\Update-Monet.ps1" -CheckOnly` says whether a newer Bridge is out, and changes nothing

### Security at a glance

- [x] Open Settings → Security with a healthy system, then test absent and
  unreadable Secure Boot, disk, firewall and firmware status separately. An
  unavailable check gets an explanation and cannot produce the all-clear.
- [x] Test encrypted Setup before and after the temporary boot key is retired.
  Recheck after a restart. Secure Boot key enrollment and firmware restart still
  ask before leaving Monet.
- [x] Stop firewalld inside a test system. Turn it on from Security. Cancel the
  administrator prompt once and verify the page still reports that it is off.
- [x] On two different test networks, share one profile and allow a TCP port.
  Confirm it is reachable only from the sharing zone, including after a restart
  and reconnect. Stop sharing and confirm the port is blocked again. Check
  printer discovery, KDE Connect and a hosted game.
- [ ] Connect a Steam Remote Play client and stream a game on the local network.
- [x] Upgrade with an existing global exception. It appears as an older rule
  until an administrator removes it. Test refusal, successful removal and a
  failed firewall reload. Check that Protection history lists confirmed changes.
- [x] In an active local session, Play on Windows still reaches the guarded
  departure. Direct rollback and Windows preparation require administrator
  approval. Check an ordinary account, Guest and an inactive or remote session.
- [x] With an update staged, Security offers Restart. A failed automatic update
  links to Updates and is recorded in Protection history. Open and cancel the
  restart with the keyboard in Mist and Smoke.
- [x] Check the remaining Security actions with the keyboard in Mist and Smoke.

Local 0.9.7 firewall results, 8 November 2026. In a Monet VM with two isolated
networks, a TCP exception reached only the shared NetworkManager profile. The
same profile kept access after reconnect and reboot. Moving sharing moved the
access, and removing the port closed it on both networks. A rule written by the
previous helper appeared as an older exception. An unprivileged removal was
refused, and an injected reload failure restored the rule without recording a
successful change. Administrator removal closed the port on both networks and
was recorded in Protection history. Settings reported that the firewall stayed
off after canceling the administrator prompt. Approving the same action started
and enabled firewalld. The listener notification appeared for the test server,
and choosing Keep blocked left the port closed on both networks.

The packaged-image check found that an ordinary account could not read the
private firewalld policy directory. Settings now reads the loaded rules through
firewalld's read-only D-Bus interface. An ordinary account verified the sharing
rules and the older global rule, detected a port added outside Monet, and saw
unknown status while firewalld was stopped. The check did not start firewalld or
change the policy directory permissions. Logs and screenshots are in
`target/097-firewall-qualification/`.

A source-level regression covered incomplete firewall reads. Security reports an
incomplete check if the default zone, active profiles, loaded sharing policy,
or an active zone’s ports or services cannot be read. Adding sharing requires
a readable default outside the sharing zone. All 22 focused helper and offscreen
Settings checks passed. The updated helper and page still need a rebuilt VM check.

Offscreen Settings checks then exercised a firewall change while an older status
request was pending. The page waited for the post-change result, and a late reply
could no longer undo the displayed change. A helper test also verified that a
failed request to Plasma never calls a direct reboot. The Security page reports
the failure and keeps Restart available. The Security helper and full Settings
feedback suites passed all 57 checks. The real restart dialog and firewall
changes still need a check with these files packaged.

Ten Security checks passed in each of Mist and Smoke at 125% in offscreen
Settings with the KDE Qt theme plugin. Tab brought the default firewall rules,
profile sharing, app preset and port removal controls into view. Space and both
Enter keys dispatched the expected helper requests. Holding an activation key
after the status refreshed could undo a sharing change. Setting rows now ignore
key repeat, and the regression checks all three activation keys. These tests use
helper replies without making changes to the host firewall.

The current Settings file matched both 0.9.7 images. Twenty additional
keyboard checks passed in Mist and Smoke at 150% and 200% on private KWin
outputs. Tab and Shift+Tab brought the focused controls into view. The
checks opened Accounts, the exact Screen lock control and Backups, retried
status and firmware reads, and checked the automatic-update, backup and
firmware actions. Blocked firmware could not be selected. The tests used
fixture replies for system changes. Captures and results are in
`target/097-security-keyboard.c9PNX8/`.

The current signed AMD/Intel candidate also booted over a 0.9.6 installation
whose packaged firewall helper had opened a global TCP exception. The
rule files were preserved byte for byte, the port stayed reachable, and an
ordinary account saw the older rule in the Security status. Direct and
detached PolicyKit removal attempts were refused. After an injected
reload failure, the helper restored the rule and recorded no success.
Administrator removal closed the port while the listener kept running,
and the ordinary account's Protection history reported one removal.
The upgrade and firewall logs are in
`target/097-security-keyboard.c9PNX8/legacy-upgrade/`.

The exact Setup VM ISO installed the pinned NVIDIA image on a blank encrypted
disk. The recovery key unlocked LUKS2. An ordinary account's Security read
reported encryption setup pending while the temporary key still unlocked the
disk. After an orderly restart the key, its slot, the cleanup receipt and its
boot arguments were gone. Security reported setup complete on that boot and
again after a further TPM-backed restart. Secure Boot, SELinux and firewalld
stayed active. A test-only boot hold delayed SSH until its timeout, so the
qualification issued the orderly restart after taking the pending reading.

The encrypted guest exposed a second issue. Its OSTree repository and
deployment directories are private, so the ordinary account could not run
`rpm-ostree status --json`. Security now falls back to the service's read-only
D-Bus deployment property. The corrected helper reported clear, staged and
clear again after removal of the test deployment, with directory permissions
still at 0700. A private Settings run displayed the VM's healthy status and
each of eight isolated failures for Secure Boot, disk encryption, firewalld
and firmware. It gave the all-clear only on the healthy input. All 12
rendered checks passed, including the three encryption readings.

The corrected helper is installed in the reversible account preview. The
first VM run completed Setup but applied its fresh-start memory threshold
at the installed guest's restart. The corrected guard let the retry proceed
while keeping the SSD above 64 GiB free. Both disposable disks were removed.
Evidence is in `target/097-encryption-status.hqHQLM/`.

The rebuilt AMD/Intel and NVIDIA images contain that exact helper. Each export
reuses 295 unchanged layers. Both VMs rejected unsigned and wrong-key offers
and booted the exact signed 0.9.7 digest. With the command-line deployment
reader made unavailable to the ordinary account, the packaged helper
reported clear, staged and clear again. Both VMs rolled back to their
original 0.9.6 digests with their saved file intact.

The Setup and Fedora fallback ISOs pin both rebuilt images. The Setup live
filesystem comparison covered 40,122 entries and preserved file contents,
permissions, ownership, hard links and SELinux labels apart from the
intended digest-map update. The Setup ISO booted with Secure Boot, a
virtual TPM and no network adapter, and read both pins. Fedora fallback
installed the pinned AMD/Intel digest after the test registry moved its
version tag, then booted it with Secure Boot and enforcing SELinux. Its
installed files matched the export and its update check requested the
rolling reference.

The final desktop run covered 1,701 Python checks in 120 modules with 19
documented skips and zero failures. The JavaScript check, all 11 browser
password-form checks, both separate PowerShell checks and the translation
catalog check passed. The test container needed its accessibility bus set
to dbus-daemon. An earlier run reported a ZIP extraction as complete even
though a wrong password produced corrupt output. The random fixture passed
on rerun.

The seven rebuilt or retained artifacts passed their SHA-256 checks.
The Linux bundle contains the corrected helper, and the Windows Bridge
and USB writer are byte-for-byte identical to the previously qualified
executables.

The exact Windows USB writer wrote and verified the rebuilt Setup ISO on a
disposable 4 GiB virtual USB stick. Independent read-back matched the source
ISO byte for byte outside the relocated primary GPT fields. Both GPT
headers and partition tables verified. The source ISO has 340 KiB of zero
padding after its backup GPT. The writer placed the stick's backup GPT at
the final sector and preserved the protective MBR, whose size field still
produces an `fdisk` warning. The written stick reached Setup's Hello page
with Secure Boot enabled and both expected image pins. The VMs had no network
adapter and the test kept at least 64 GiB free on the SSD. The USB evidence is
in `target/097-private-update-status.GRmyV6/usb-qualification/evidence/`.
Physical USB boot, monitor and GPU checks, and Steam Remote Play remain open.
Reports are in `target/097-private-update-status.GRmyV6/`. The local
candidate manifest is in `target/097-local-candidate.gou008er/`.

The ZIP follow-up reproduced the failure using a fixed encrypted entry and a
wrong password that passed its initial check. The old Ark plugin stopped
reading at the declared size and missed the checksum error. The corrected
plugin reads through the end of the entry. The same native test now records
a failed transfer. All 55 archive, bundle, preview and Files checks passed,
including correct passwords, cancellation and recovery from a full test
filesystem. The laptop's guarded account launcher loaded the new plugin and
extracted a deflated file and an empty file.

Both refreshed 0.9.7 exports reuse 296 inherited layers and contain the six
verified Ark payload files. Each VM rejected unsigned and wrong-key offers,
booted its exact signed digest with Secure Boot and SELinux enforcing, and
matched the installed Ark binary and ZIP plugin hashes. The packaged Security
page's status reader reported clear, staged and clear again for an ordinary
account. Rollback returned each VM to its original 0.9.6 digest and preserved
its saved file. The first AMD/Intel attempt hit the 4 GiB scratch-file cap
after boot. The rerun used an 8 GiB RAM-backed cap and passed.

Both ISOs have the new digest pins. Setup's decoded filesystem comparison
covered 40,122 entries, including file contents and SELinux labels. The
Setup ISO ends at its backup GPT and its ISO volume boundary. The exact ISO
showed Hello with Secure Boot, a virtual TPM, no network adapter, and the
expected pins. The Windows USB maker wrote and verified it on a virtual stick.
Independent read-back matched the payload outside the relocated GPT fields,
and the stick booted with Secure Boot and both pins.

Fedora fallback installed the pinned AMD/Intel digest after the test registry
moved the version tag. It booted with Secure Boot and SELinux enforcing.
Installed file hashes matched the export, and its update check requested
`:latest`. The 137 installer and release checks had one documented PowerShell
skip and zero failures. The prior separate PowerShell checks cover the retained
Windows scripts. All seven artifact hashes in
`target/097-local-candidate.cxv0dsrg/manifest.json` passed. SSD space stayed
above 64 GiB and the VM scratch disks were removed. Evidence is in
`target/097-zip-integrity.p6Z5gV/`.

The Windows maker now sets the size of a pure protective MBR from the
validated USB capacity. All 104 Rust workspace checks and 25 native Windows
checks passed. The exact executable rejected a truncated ISO with zero
writes. It wrote and verified the exact Setup and Fedora fallback ISOs from
the ZIP candidate. Both virtual sticks passed independent payload read-back,
both GPT CRCs, and `fdisk` with the protective MBR covering the disk. Setup
reached Hello with Secure Boot and the expected pins. The Fedora stick
reached Anaconda with Secure Boot. Fedora's optional embedded ISO checksum
passed on the source image and failed on the written stick. Restoring only
the original protective MBR still failed, which reproduces the checksum
failure after the prior writer's GPT relocation. Restoring both original
headers passed. Evidence is in `target/097-usb-protective.iSncWj/`.

The full desktop recheck of the ZIP candidate found one wallpaper failure.
The activity handler and weather timer both started a request on unlock.
The updated fixture reproduced the duplicate while the test server held its
response. The corrected wallpaper uses the timer for that refresh. It
passed 40 focused checks, including the existing lock, display and animation
checks. The account preview contains the correction, and both new exports
reuse 297 inherited layers with one changed wallpaper file. The full rerun
covered 1,702 Python checks in 120 modules, with 19 documented skips and
zero failures. JavaScript and all 11 browser form checks passed.
Setup and Fedora fallback now pin both new exports. The rebuilt Setup ISO
reached Hello with Secure Boot, a virtual TPM and no network adapter.
Both exact images rejected unsigned and wrong-key offers, booted the signed
0.9.7 deployment and rolled back to 0.9.6 with saved data intact. Installed
wallpaper and Ark hashes matched their exports.

The Windows maker wrote both repinned ISOs and their independent read-backs
verified the payload, protective MBR size and GPT tables. The Setup stick
reached Hello with Secure Boot and read both pins. The first full fallback
test stopped at a fixture guard that expected optical media. The revised
guard allows the read-only USB while still requiring the one disposable
destination. On rerun, Fedora installed the pinned AMD/Intel image from the
Windows-written stick after the test registry moved the tag. The installed
guest booted with the stick detached, Secure Boot enabled and SELinux
enforcing. It matched the expected file hashes and checked `:latest`.
All seven artifact checksums passed for
`target/097-local-candidate.e4u63ij7/manifest.json`. The SSD stayed above
64 GiB free, and the temporary VM disks were removed. Evidence is in
`target/097-wallpaper-resume.s95TyM/`.

The 0.9.7 direct Ethernet Setup kit at `target/097-direct-setup.XA1DtT/`
serves the same pinned AMD/Intel and NVIDIA images from their existing
archives. Its Setup ISO adds the registry CA through Fedora's live updates
directory. All seven original ISO files and the embedded EFI boot images
match byte for byte. The ISO's GPT
and SHA-256 checks pass. The laptop shares the unchanged image extents with
the VM ISO, keeping at least 64 GiB free on the SSD.

The exact test ISO booted from a read-only virtual USB with Secure Boot
enabled and a virtual TPM. Setup received a DHCP address from an isolated
Ethernet bridge with no default route. A system-wide TLS request rejected
the test CA. Skopeo accepted the registry-scoped CA and read both pinned
manifests. Both image signatures also verified against the candidate key.
The Setup worker then downloaded and verified the AMD/Intel image, finished
an encrypted installation, and verified that its recovery key unlocked the
target. A change to the running test harness interrupted its shutdown step
after the worker completed. The harness stopped the VM and removed the RAM
disk.

The follow-up in `target/097-direct-setup.XA1DtT/boot-check/` repeated the
installation and shut down Setup normally. The installed VM booted with its
system disk and firmware only. After MOK enrollment it reached the Monet
desktop with Secure Boot enabled and SELinux enforcing. A normal restart
reached the desktop again. A temporary serial diagnostic boot argument let
the harness read the exact pinned AMD/Intel digest and the `:latest` update
origin. The system used the encrypted disk, had a TPM 2.0 token bound to
PCR 7, and retired the temporary key and its boot argument. Both installed
boots reached the desktop without entering the recovery key. The VM shut
down normally and the RAM disk was removed. The offline text console
printed a missing Homebrew script and a separate permission warning.

The system shell profiles are identical in both candidate exports. Using
those profiles, a partial Homebrew prefix and a private OSTree directory
reproduced both console messages. The image build now waits for the
Homebrew executable and its main script before running shell setup. The
login warning reads the booted image through rpm-ostree's read-only D-Bus
property. A test with a signed booted image and an unverified staged image
stayed quiet. Booting the unverified official image still produced the
warning. A complete Homebrew installation still loads its environment and
completions. The source fix is pending a new image build.

The kit's README gives the physical test procedure for a dedicated Ethernet
adapter and a spare installation drive. Physical USB, GPU and display checks
remain open.

On 11 November, the rebuilt AMD/Intel 0.9.7 image used Monet's default zone
on two isolated links. An ordinary account saw a shared CUPS queue marked
Ready in Settings → Printers. Avahi resolved it over IPv4 and IPv6 on both
links, and direct IPP requests returned the expected attributes. KDE Connect
paired on the first link and reconnected on the second with the same device ID.
The Phones helper reported the peer as paired and nearby. Each guest sent a
test file on the second link, and the receiving guest verified the bytes. The
printer remained discoverable on both links with only one profile shared.

The Games preset let a Cuberite Minecraft server reply on TCP 25565 and a
test listener reply on UDP 2456. Both were reachable over IPv4 and IPv6 only
from the shared profile. Moving sharing moved access to the other link. The
rules survived a firewalld reload and a full guest reboot. After reboot, a
fixture player joined the Cuberite world with authentication disabled inside
the isolated test network. Stopping sharing blocked both listeners on both
links. The Security helper reported the active profile zones and Games setting
throughout. Logs are in `target/097-current-images-v5/nearby-devices/`.

On 11 November, an ordinary desktop account saw a failed automatic update
in Protection history after the VM's local registry was stopped. In Smoke,
Tab and Enter on Open Updates went directly to the recent automatic attempts.
A signed manual update was then staged with automatic updates off. The
packaged page showed Turn on where Restart was needed. With the corrected
Settings file mounted in the test guest, Tab and Enter opened the restart
confirmation in Mist and Smoke. Escape canceled it and left the deployment
staged. Desktop fixtures also checked a healthy overview and separate missing
or unreadable Secure Boot, disk, firewall, firmware, and update status.
The full desktop run recorded 1,667 Python checks with 17 documented skips,
no failed modules, and 11 passing browser password form checks.
Evidence is in `target/097-current-images-v3/security-vm/`.

In the same VM, PolicyKit allowed the Windows switch for the ordinary account
in its active local Plasma session. The general Monet command and Windows
preparation required administrator authentication. The switch also required
administrator authentication for a process started over SSH and for a Guest
account signed in at the active local desktop. These checks queried the real
policy without dispatching any of the actions.

The AMD/Intel and NVIDIA images were rebuilt with the corrected Settings
file and updated release notes. Both images rejected unsigned and wrong-key
updates, booted the trusted 0.9.7 deployment, and rolled back to their original
0.9.6 digest. The VM checks verified the installed Settings file against the
build. The installer pins for this pair are in
`target/097-current-images-v4/installer/`.

In the next rebuilt AMD/Intel guest, Monet's automatic update service rejected
an unsigned image with the disposable signing policy. Booted, staged and
rollback deployments stayed the same. The packaged Security page recorded the
failure, and Tab and Enter on Open Updates went to the failed attempt. After
the registry offered the trusted signature for the same digest, the automatic
service staged it. With automatic updates turned off, the packaged Restart
button opened the confirmation in Mist and Smoke. Escape kept the boot ID and
all deployments unchanged in both themes. Approving it in Smoke booted the
signed digest and kept the earlier digest available for rollback. Secure Boot
and SELinux enforcement remained active. Running `monet rollback` from the
active desktop opened the real administrator prompt. Cancel left the deployed
systems unchanged. Approval queued the previous digest, and a separate
restart booted it with the test file intact.

The same guest reproduced a firmware status error. With fwupd stopped and
masked, its JSON error was shown as a successful check with no updates. The
corrected helper distinguishes successful device lists, fwupd's no-action
exit code and failed checks. The corrected Settings overview keeps firmware
installation and its pending restart visible. With the two files bind-mounted
in the guest, Settings showed the daemon error with Try again. After the
daemon was unmasked, Tab and Enter retried successfully. The 40 focused checks
passed. The desktop suite recorded 1,672 Python checks with 19 documented
skips and no failed modules, plus 16 browser submission checks and 11 password
form checks. The two skipped PowerShell checks passed separately with the local
runtime. Evidence is in `target/097-current-images-v5/security-status/`.

The local AMD/Intel and NVIDIA images were rebuilt with both corrected files.
The build verified their installed bytes. In each container, the packaged
helper reported failure from an ordinary account when fwupd's daemon was
unreachable. Both exact exported images then passed a signed update from
0.9.6 and rollback to their respective original digests. Each VM rejected
unsigned and wrong-key updates without staging a deployment. With Secure Boot
and SELinux still active, the packaged helper reported the real error while
fwupd was masked, then completed the check after the service was restored.
Build and update evidence is in `target/097-current-images-v6/`.

The firmware and older-rule reviews now open with keyboard focus on Cancel.
Escape dismisses either review and returns focus to its button. The Settings
regressions cover Tab to the separate confirmation button, a held Enter key,
failed helper calls, and a separate Restart after key enrollment is requested.
The updated Settings file was bind-mounted in the rebuilt AMD/Intel guest.
It ran in Mist and Smoke against an older TCP exception written by the
previous helper. Canceling the review or the real administrator prompt
preserved the loaded rule. Approving removal cleared it and produced one
entry in Protection history.
The desktop run recorded 1,669 Python checks with 17 documented skips,
16 browser submission checks and 11 password form checks. The only failure
was an assertion for the old Escape handler's exact source text. After
updating it, all 405 checks in that module passed on rerun.

The same guest reproduced a firmware restart issue in the earlier image.
The helper set logind's next-boot firmware flag before opening Plasma's
restart prompt. Escape closed the prompt and the flag stayed set.

The Settings confirmation now queues the firmware request with Plasma's
shutdown service. It sets the firmware target after both application close
checks finish. The native test runs the built service on private buses and
covers unavailable firmware, canceled or failed close requests, duplicate
requests, an approved restart, and a refused reboot with and without a
pre-existing firmware target.

The shutdown service and Settings changes were bind-mounted in the AMD/Intel
VM. The Settings fixture reported Secure Boot as off to expose the firmware
action, with the VM's actual Secure Boot left on. Escape in Settings and
Cancel Logout while KWrite had an unsaved file both left the boot ID and
firmware flag alone. On retry, the flag stayed clear until Save. OVMF opened
its boot menu and offered EFI Firmware Setup. Monet booted again with the
file saved, Secure Boot enabled, SELinux enforcing and the firmware flag
clear. A subsequent ordinary Plasma restart went straight back into Monet.
The native bundle passed installation and binary checks in the matching
Fedora build container. The desktop suite recorded 1,670 Python checks
with 17 documented skips and no failed modules. All 16 browser submission
checks and 11 password form checks passed. Logs and screenshots are in
`target/097-current-images-v4/security-actions/`.

The next AMD/Intel and NVIDIA images include the updated shutdown service,
Settings page and helper. Both built binaries matched the one used in the
firmware restart VM. The private-bus checks also passed as the ordinary user
inside both booted images. Each VM rejected an unsigned image and a wrong-key
signature without staging a deployment, booted the trusted 0.9.7 digest and
rolled back to its original 0.9.6 digest. Secure Boot, SELinux enforcement and
the saved test file survived. Evidence is in `target/097-current-images-v5/`.

### Installer image trust

- [x] Build a local Setup ISO from the qualified AMD/Intel and NVIDIA manifests.
  Verify the two versioned references and digests in `IMAGE_DIGESTS.json`.
  Move a test registry tag after building the ISO. A fresh download must
  use the original digest. An offline resume must accept the original cache
  and reject a replacement cache even when its receipt and blobs agree.
- [x] Qualify signed updates separately in a disposable VM. Test valid,
  wrong-key and unsigned updates and confirm that rejected images leave the
  deployed and staged systems alone. Boot the signed update and roll back
  with the disposable signing policy. Check the Fedora fallback installer
  separately from Monet Setup using the same image digests.
- [x] On fresh Windows test media, check that the first automatic sign-in
  still runs Bridge setup, clears `AutoLogonCount` and disables setup's
  `AutoAdminLogon`. Check the next sign-in and a Play on Windows round trip.

The rebuilt 0.9.7 AMD/Intel and NVIDIA images each passed a signed update
from 0.9.6 and a rollback to the original digest. Each guest rejected the
unsigned candidate without staging a deployment, then booted the exact
candidate after a signature from the disposable VM test key was available.
Secure Boot, SELinux enforcement and the saved test file survived both boots.
The corrected images were pinned in the local Setup ISO. The live ISO booted
with Secure Boot enabled and loaded both matching pins. With networking
disabled, Setup accepted the downloaded AMD/Intel cache and rejected a
replacement with a matching receipt and valid blobs but a different digest.
The desktop suite ran 1,665 Python checks with 17 skips and no failed modules.
All 11 browser password form checks passed. Evidence is in
`target/097-current-images-v2/`.

The same Setup ISO installed the pinned AMD/Intel image on a blank virtual
disk. The recovery key unlocked LUKS2. After signing key enrollment, the
guest booted with Secure Boot enabled and SELinux enforcing, and Settings
reported disk encryption complete from the ordinary desktop session. A
firmware restart booted the same digest using the virtual TPM, with no
temporary key, cleanup receipt or temporary-key kernel argument.

The Fedora fallback ISO used both digests from the same build. The loopback
registry served the NVIDIA manifest at the AMD/Intel tag, and the fallback
guest still installed and booted the AMD/Intel digest specified by the ISO.
The installed guest reported Monet 0.9.7, Secure Boot enabled and SELinux
enforcing. Evidence is in `target/097-current-images-v2/fallback/`.

On the first boot, Bazzite's hardware setup was already changing kernel
arguments when Monet attempted to remove the temporary key argument.
Monet kept its cleanup receipt and completed the operation after Bazzite's
automatic restart. The seal service now runs before Bazzite's hardware setup.
The revised unit passed systemd verification and all 24 focused checks. A
second fresh encrypted installation used the revised unit as an override in
the test guest. It retired the temporary key on the first boot, then Bazzite
changed the kernel arguments and restarted. The guest started using the TPM,
with no temporary key or kernel argument. Both rebuilt images contain the
verified unit. Evidence is in `target/097-current-images-v2/fresh/`,
`target/097-current-images-v2/seal-order-vm/` and `target/097-current-images-v3/`.

Both rebuilt images passed another update and rollback round trip. The
disposable signing policy rejected an unsigned image and a signature checked
against the wrong key without changing the booted image or staging a deployment.
Each guest then booted the trusted 0.9.7 digest with the packaged seal unit and
rolled back to its original 0.9.6 digest. Secure Boot, SELinux enforcement and
the saved test file survived. The new Setup digest list and fallback Kickstart
are in `target/097-current-images-v3/installer/`. The installer VM results above
used the previous pair of image digests.

Both installer ISOs were then rebuilt using the new digests. The embedded
Setup manifest and the Fedora Kickstart matched both qualified images. The
rebuilt Fedora fallback installed and booted the AMD/Intel image with Secure
Boot enabled and SELinux enforcing after the registry tag was moved. Its
registry log records the pinned manifest requests. The full desktop suite ran
1,665 Python checks with 19 documented skips and no failed modules, and all
11 browser password form checks passed. Both PowerShell checks skipped by the
desktop container passed separately with the local PowerShell runtime.
Evidence is in `target/097-current-images-v3/`.

Native Setup used the pinned NVIDIA digest after both registry tags moved.
The test interrupted installation after the verified download and restarted
the same ISO with the network adapter removed. Setup rediscovered the saved
checkpoint, refused a substitute cache with a valid receipt and matching blobs,
and finished the encrypted installation after the original cache was restored.
The recovery key unlocked LUKS2. The packaged seal service retired the
temporary key before Bazzite changed its kernel arguments. The automatic
restart and a separate firmware restart booted the pinned image through the
virtual TPM. Secure Boot and SELinux remained active, and the ordinary desktop
session reported encryption complete. An earlier run hit the host RAM-disk
quota. The clean run passed after the ISO files were moved to a separate
filesystem. The native VM used virtual graphics and a local registry.
Evidence is in `target/097-current-images-v3/native/`.

The next Setup and Fedora fallback ISOs were rebuilt from the images with
the corrected Security page. Both ISO checksums passed. Setup's embedded
digest list and the fallback's extracted Kickstart match both images from
the signed-update run. Setup also passed the signed EFI and kernel checks
and the optical/USB boot file comparison. These ISOs use the VM's isolated
registry. Checksums and the extracted files are in
`target/097-current-images-v4/installer/` and
`target/097-current-images-v4/fallback/`.

The rebuilt fallback installed on a blank virtual disk after both registry
tags were moved. The registry log shows the installer requesting the AMD/Intel
digest embedded in the Kickstart. The installed guest booted that digest and
reported Monet 0.9.7, Secure Boot enabled and SELinux enforcing.

Native Setup downloaded the pinned NVIDIA image after both tags were moved.
The VM shut down after the verified download and restarted the same ISO
without a network adapter. Setup refused the substitute cache, then finished
installing from the restored checkpoint. The recovery key passed the LUKS2
check. The packaged seal service retired the temporary key before Bazzite's
automatic restart. That restart and a separate firmware restart booted the
pinned image through the virtual TPM, with Secure Boot and SELinux active.
The installed Settings file matched the build, and the ordinary account's
security check reported encryption complete. The Security page screenshot
shows Secure Boot, encryption, app isolation and firewall status. The fixture
disables the automatic update timer. Evidence is in
`target/097-current-images-v4/native/`.

Setup and Fedora fallback were rebuilt again for the images with the
firmware restart fix. Both checksums passed. The extracted Setup digest
list and Fedora Kickstart match the images booted in the latest signed
update tests. Setup also passed the signed boot component checks and the
optical/USB boot file comparison. The builds use the local VM registry.
Checksums and extracted files are in `target/097-current-images-v5/installer/`
and `target/097-current-images-v5/fallback/`.

The rebuilt fallback installed on a blank virtual disk after both registry
tags moved. The installed guest booted the AMD/Intel digest from the ISO
with Secure Boot enabled and SELinux enforcing. Its shutdown binary and
Settings helper matched the built image.

Native Setup downloaded the pinned NVIDIA image after both tags moved. The
VM restarted the same ISO without a network adapter. Setup refused the
replacement cache, resumed the verified checkpoint and accepted the LUKS2
recovery key. The temporary key was retired before Bazzite's automatic
restart. Both that restart and a separate firmware restart unlocked through
the virtual TPM and booted the pinned image with Secure Boot and SELinux
active. The installed shutdown binary, Settings helper and QML matched the
build. The Security page screenshot shows the settled status from the ordinary
account. The fixture disables the automatic update timer. Evidence is in
`target/097-current-images-v5/native/`.

Setup and Fedora fallback were rebuilt using the images with the firmware
status fix. Both ISO checksums passed. The digest list extracted from Setup
and the Kickstart extracted from the fallback ISO match the exact AMD/Intel
and NVIDIA digests from the signed update and rollback tests. Setup also
passed the signed boot component checks and the optical/USB boot file
comparison. Evidence is in `target/097-current-images-v6/installer/` and
`target/097-current-images-v6/fallback/`.

The rebuilt Fedora fallback installed the pinned AMD/Intel digest on a blank
virtual disk after both registry tags moved. The guest booted with Secure Boot
enabled and SELinux enforcing. Its firmware helper, Settings page and shutdown
binary matched the build.

The matching Setup ISO saved the pinned NVIDIA download and refused a
substitute cache while offline. The first run hit the host's RAM-disk quota
while writing the virtual disk. The retry stopped before completion and the
installed boot and virtual TPM checks are still open for this image pair.
The interrupted guest disk was removed during storage cleanup. The logs and
screenshots are in `target/097-current-images-v6/native/`.

The saved bootc reports exposed an update-channel gap. Native Setup recorded
the versioned image as its future update source, and the Fedora fallback
recorded the digest itself. The native Setup worker now installs the verified
OCI cache and configures the same graphics variant's `:latest` tag for later
updates. Its offline resume still skips the update-source fetch check. The
Setup and recovery suites passed all 93 checks, including the source and target
references for both variants.

The rebuilt native Setup ISO passed its checksum, the signed boot-file
checks and the optical/USB comparison. The extracted worker and digest list
matched the build inputs. In the VM, Setup downloaded the pinned NVIDIA
image after both version tags moved. With the network adapter removed, it
refused a substitute cache with a matching receipt, resumed from the restored
cache and verified the recovery key against the LUKS2 volume. The test images
reused the retained 0.9.7 layers and packaged the updated boot helper.

After enrolling the driver key in the VM firmware, the system booted the
pinned digest. The packaged seal service retired the temporary key before
Bazzite restarted, and a separate firmware restart unlocked through the
virtual TPM. Setup left the NVIDIA `:latest` channel configured to use the
container signature policy. With the disposable policy installed in the
guest, an ordinary `bootc upgrade` rejected unsigned and wrong-key offers
without staging either one. It then staged and booted the trusted digest.
Monet's rollback returned to the pinned digest. The fixture set a stale
GRUB counter before each restart and Monet cleared it. The encrypted disk,
Secure Boot, SELinux and the test file survived both transitions. Evidence
is in `target/097-native-channel-vm/evidence/`.

The Fedora fallback now sets the matching `:latest` reference in an Anaconda
post-install step. It associates the installed OSTree commit with that reference
and preserves the deployment's signature policy. The 28 installer, graphics and
download checks passed. A disposable OSTree sysroot pulled a small pinned OCI
image from a loopback registry after `:latest` moved, rewrote the origin without
network access, and imported the newer image from `:latest` while keeping the
original deployments.

A rebuilt fallback ISO passed its checksum and installed the pinned AMD/Intel
v6 image after the registry's version tag moved. Anaconda set the update origin.
The test fixture's CA copy failed because the live environment lacked
`install`. The fixture was finished in the guest before reboot. Secure Boot
and SELinux remained active, and `bootc upgrade --check` requested `:latest`.
With the disposable signing policy, the guest rejected unsigned and wrong-key
images and staged the trusted digest.

A stale GRUB counter kept booting the running deployment after both the signed
update and Monet's queued rollback. Clearing it in the guest let the trusted
deployment boot and let rollback return to the original pinned digest. The
test file, Secure Boot and SELinux survived both transitions. In the guest,
`/boot` was mounted read-only. The source helper now uses a private writable
mount to update GRUB and preserves the trial receipt if the edit fails. All 13
focused boot-helper checks passed. Logs are in
`target/097-installer-channel-vm/fallback/`.

The shutdown helper now clears the counter when bootc has queued a rollback.
A fresh Fedora fallback VM installed the pinned AMD/Intel image after both
version tags moved. The test images reused the retained 0.9.7 layers and
packaged the new helper. The guest used the disposable signing policy to
reject unsigned and wrong-key offers and boot the trusted digest from
`:latest`. The text-mode test install defaulted to multi-user mode, so the
graphical target was enabled in the guest for the sign-in health check.

The fixture set the stale GRUB counter before each restart. The packaged
helper booted the signed update and later returned to the original digest
through Monet's rollback command. Both transitions left `/boot` read-only
from the guest's main mount namespace, and Secure Boot, SELinux and the test
file survived. All 151 installer, Setup, publication and boot-helper checks
passed, including the PowerShell parse check with the retained local runtime.
Evidence is in `target/097-boot-trial-vm/evidence/`.

The AMD/Intel and NVIDIA 0.9.7 images were built through the full Containerfile
from the same source snapshot, using the cached Bazzite bases and unchanged
build stages. The packaged Security page, firewall rules, PolicyKit policy,
boot helper and widget glass matched the snapshot. Both images passed the
packaged shutdown fixture, including canceling a firmware restart.

Separate VMs running 0.9.6 rejected unsigned and wrong-key offers from the
local registry without staging a deployment. Each guest booted its exact
0.9.7 export under the disposable signing policy. The packaged firmware check
reported the unavailable daemon and recovered after it was unmasked. Both
rollbacks cleared an injected stale GRUB counter and restored the original
digest. Secure Boot, SELinux enforcement and the test file survived.

Monet Setup and Fedora fallback were rebuilt with both exported digests.
Both ISO checksums passed, and their extracted pins matched the manifests
tested in the VMs. Setup also passed the signed boot-file and optical/USB
checks. The source manifest, build logs and VM evidence are in
`target/097-clean-release/`.

Both exact ISOs then installed on blank virtual disks after both versioned
registry tags moved. Fedora fallback booted the pinned AMD/Intel export and
its update check used the matching `:latest` channel. The ordinary account
reported Secure Boot, enforcing SELinux and Monet's firewall rules active.
The installed Security page, policy and helpers matched the signed-update VM.

Native Setup downloaded the pinned NVIDIA export. With no network adapter it
refused a replacement cache, resumed from the verified cache and checked the
recovery key against the LUKS2 volume. After VM firmware key enrollment, Monet
retired the temporary key before Bazzite restarted. A separate firmware
restart unlocked through the virtual TPM and booted the same digest. The
installed update check used the NVIDIA `:latest` channel with container
signature policy selected. The installed files matched the signed-update VM.

The installed Security page showed the active protections in the ordinary
Wayland session. PolicyKit required administrator authentication for the
general command, Windows preparation and firewall helper. The local session
could use the narrow Windows switch helper, while a process outside the
local session needed administrator authentication. A firewall change from
the desktop launcher authenticated the passwordless test administrator
through PAM. After setting a password in the guest, the same control opened
Monet's administrator prompt. Cancel left the firewall rules and Protection
history unchanged. The fixture disables automatic updates, which explains
the update notice in the screenshots. Logs and screenshots are in
`target/097-clean-release/media/fallback/` and
`target/097-clean-release/media/native/evidence/`.

For new releases, both media jobs now take the AMD/Intel and NVIDIA digests
reported by the versioned OCI image jobs. An existing release tag continues
through the rolling-image build without generating new installer media. Local
test doubles checked the digest output and failure paths. Both workflow build
steps then produced matching pins with tag resolution disabled in the fixture.
All 24 focused publication, Setup and recovery checks passed.

`tools/vm-test.py` checks the output and VM disk filesystems before starting
QEMU. The disk reserve defaults to 8 GiB. Use `--disk-reserve-gib 64` for the
laptop's release tests. QEMU starts with at least 12 GiB of host memory
available. The runner stops the guest if the disk reserve or 4 GiB of
available host memory runs low. Disposable disks live in `/var/tmp`, outside
Monet's home snapshots, and are removed when QEMU stops. The QMP socket uses
the same short runtime path even with deeply nested output folders. Screenshots
and logs stay in the output folder. With `--keep-disk`, the disk stays beside
the logs in `vm-work` for inspection.

The runner refused an unavailable reserve before launching QEMU. With the
64 GiB reserve it booted the exact Setup ISO from USB and reached the drive
picker using a nested report directory. A second invocation was refused while
the first held the report directory. The short QMP socket and temporary disk
were removed at exit, and the screenshots stayed. All 127 focused Setup,
recovery, publication and sealing checks passed. Logs are in
`target/097-passive-restart.uuUCs3/runner-storage.msNFV6/`.

Local 0.9.7 Windows results, 8 November 2026. The installer and recovery suite
passed all 124 checks, including PowerShell parsing and HTTP retry tests for
changed downloads, invalid ranges and interrupted transfers. A Linux guest rejected
malformed and linked ISOs, then verified both images in a valid x64 fixture
while the ISO was mounted read-only. In a separate guest, WinPE deployed
Microsoft's checksum-verified Windows 11 Enterprise evaluation image once.
Repeating deployment preserved the original EFI fallback and the test file.
A copy of the deployed guest ran the updated answer file at first sign-in and
recorded `AutoLogonCount` and `AutoAdminLogon` as zero. Both stayed zero after
the next boot, which still opened the desktop for the passwordless account.
The VM had no network and used a recording script in place of Bridge setup.
Local evidence is in `target/097-windows-qualification/`.

A separate two-disk VM booted Monet 0.9.7 and the evaluation copy of Windows
under the same Secure Boot firmware. Windows installed the released Bridge
and Game Profile from local media. Monet imported Bridge's game catalog from
the Windows EFI partition. From an active Monet desktop, `monet play` used
the current switch helper to restart without an administrator prompt. Bridge
started the offline test game as the signed-in user without elevation, showed
the return countdown when it closed, and restarted into Monet. Monet stayed
first in the boot order and cleared the pending trip record. The firmware's
one-time boot target and launch request were both cleared. PolicyKit required
administrator authentication for both the switch helper and the general Monet
binary when checked against an inactive process. The run used a test game,
with network launchers and physical PCs outside its scope. The boot logs and
cover captures are in `target/097-windows-qualification/trip/`.

A fresh copy of the deployed Windows evaluation guest ran the same answer file
with a recording wrapper around the released Bridge installer and Valve's signed
Steam bootstrapper. Secure Boot was on. The first sign-in installed Bridge, the
Game Profile and the Steam bootstrapper, then removed the temporary setup volume,
expanded C: and restarted into Monet. The existing Windows test file survived.
The guest was offline. Steam's client update and sign-in remain separate checks,
and Microsoft blocked the automatic consumer ISO download in this environment.
Local evidence is in `target/097-windows-qualification/first-run/`.

Local 0.9.8 VM results, 7 November 2026. The AMD/Intel and NVIDIA tests
started from separate 0.9.6 snapshots and used existing 0.9.7 OCI exports
with disposable signatures served by a read-only loopback registry. On
both variants, bootc rejected unsigned and wrong-key images during the
initial switch and again during an ordinary upgrade. No rejection staged
a deployment. Both trusted images booted, and Monet's rollback restored
the previous digest. Secure Boot, SELinux enforcement and the saved test
file survived each reboot.

Two fresh Anaconda installs used verified Fedora 45 netinstall media
and blank virtual disks. The original Kickstart followed a moved tag.
The patched Kickstart downloaded and booted the image pinned at build
time. Both guests started with Secure Boot enabled and SELinux enforcing.
A separate guest OSTree pull rejected a server that supplied different
manifest bytes for the pinned digest. The fallback's guarantee comes
from the digest on the installer media. Production signature policy is
still a release step. Local evidence is in `target/098-security-vm/`.

### A smoother trip to Windows (0.9.3)

- [ ] Play a Windows game: from Windows' sign-in until the game is up, Monet's painting covers the screen with the game's name and Back to Monet now; a launcher that opens (Riot Client, say) comes up over it; a Windows that Monet installed shows no taskbar until the pointer touches the bottom edge
- [ ] Quit the game: the cover says Back to Monet and counts down; Go now (or Enter) restarts into Monet at once, Stay in Windows (or Esc) leaves you in Windows
- [ ] Back to Monet now while the game is still starting restarts into Monet at once; a game that doesn't start within 30 minutes leaves you in Windows, the cover gone
- [ ] With Discord (or Vesktop) installed in Monet and the shared Games folder open: `ls "/run/media/Windows games/.monet/installers"` shows DiscordSetup.exe after sign-in; Game launchers â†’ Sign inâ€¦ shows Getting Discord ready, then Discord is in the list; after signing in once, a later trip to Windows has Discord running at sign-in
- [ ] Settings â†’ Play on Windows â†’ Game launchers â†’ Sign inâ€¦: Windows lists the launchers it has; Sign in opens one (not as administrator: Task Manager's Details shows it under your name, not elevated); after signing in to Steam with Remember me, its card says Signed in within a few seconds; Back to Monet goes back
- [ ] Settings â†’ Update Windows games â†’ Update & switch off: the cover says Updating your games with Windows Update's and Steam's progress; Steam and Epic open in the background; the PC switches itself off when the downloads are quiet, and Settings then says when it was last done
- [ ] With a Windows update that needs a restart: Windows restarts once (back to the cover, Windows Update finishing), then switches off; the next Play starts the game without "Working on updates"
- [ ] Switch off now on the update cover switches the PC off at once, even when Windows wanted a restart
- [ ] The cover in Arabic or Hebrew Windows: words on the right, buttons in reverse order; in Japanese or Chinese the title is in Windows' own font
- [ ] `monet-bridge cover-preview launchers %TEMP%\cover.png` (in `C:\Program Files\Monet`) paints the launchers scene into a PNG

### One game library (after 0.9.3)

- [ ] Games in the panel (the sun as a play button) lists Steam's games installed here, Heroic's (an Epic and a GOG game at least, Heroic from the Store, so the Flatpak) and the Windows games, each once, by name, with covers
- [ ] Each says Steam Â· Plays on Monet, Epic Â· Plays on Windows and so on; a game with anti-cheat that doesn't allow Linux (Apex Legends, Fortnite) says Plays on Windows even when it's installed here too
- [ ] Play on a Plays on Monet game starts it at once (Steam's or Heroic's game window), no restart; on a Plays on Windows game it asks, then restarts in Windows with it, as before
- [ ] A game installed here that needs Windows but isn't installed there says it needs Windows, and Restart opens Windows (no game) to install it
- [ ] `/usr/libexec/monet-quick library` prints the list as JSON, each with `plays`, `here` and `windows`
- [ ] In Windows, with a Battle.net game (Call of Duty, Overwatch) a Ubisoft Connect game and GTA V from the Rockstar Games Launcher installed: `monet-bridge scan` lists them as `battlenet:AUKS`, `ubisoft:ID`, `rockstar:gta5`; back in Monet they're in Games as Battle.net Â· Plays on Windows, and Play starts them in Windows (Battle.net opens and launches the game)
- [ ] Recently played (the desktop widget) shows a Heroic game and a Lutris game after playing them, and a game played in Windows (VALORANT) after the trip, with its time; clicking that one asks before restarting in Windows
- [ ] Lutris' games (installed, not its Steam ones) are there too, with Lutris' banner as the cover; Play starts them through Lutris
- [ ] Typing in Find a game filters by name (without accents: "etretat" finds Ã‰tretat), Enter plays the one game left, Esc clears it
- [ ] With games on both sides, Plays on Monet and Plays on Windows in the side show each side; a game installed on both sides says Monet Â· Windows on its cover
- [ ] Open Games with the keyboard (Windows+G): Ctrl+F or typing on the covers goes into the search; Down moves onto the games with a ring around the one you're on, the arrows move it, Enter or Space opens its page (where Enter plays), the Menu key opens its menu, Up from the top row goes back to the search
- [ ] Right-click a game in Windows games that plays on Monet too: Play on Windows asks, then restarts there with it; Show in Steam opens its page; Uninstallâ€¦ opens Steam's own uninstall question
- [ ] A game Steam is downloading shows Downloading with a percent and a green line along its cover that grows while the gallery is open
- [ ] A game that needs Windows, installed in Monet's own Steam folder, with Windows games added to Steam: Play explains moving it, and Show in Steam opens its page in Steam
- [ ] A native Linux game ProtonDB rates Borked for Proton still says Plays on Monet
- [ ] A Steam game ProtonDB rates Borked (installed here, no anti-cheat): a minute after the gallery first opens, it says Plays on Windows, and Play explains that players report it doesn't run in Monet; right-click â†’ Play in Monet starts it here anyway; `~/.cache/monet/protondb.json` has each installed game once
- [ ] With Windows games shared but not yet in Steam here, the gallery shows a green note with Add to Steam: it says Addingâ€¦ while Steam restarts, then the note goes; Ã— puts it away for good (`~/.config/monet/shared-hint-off`)

### Games, the app (after 0.9.3)

- [ ] The Games button in the bar, Windows+G and Games in the menu each open the Games window (with its own taskbar entry and the sun icon, titled Games); doing it again while it's open brings that window forward instead of a second one
- [ ] The side lists All games, Favorites, Recently played, Plays on Monet / Plays on Windows (with games on both sides) and each store under Stores, with counts; picking one shows its covers, and a store far down the list on a small window scrolls into view
- [ ] Covers are Steam's tall library pictures (also for Steam games only Windows has); a game without one shows a painted cover with its banner and name
- [ ] Recent / Name / Play time / Size sort the covers; the choice and the window's size are there again after closing and opening Games
- [ ] Continue playing shows the four games played last (Today, Yesterday, 3 days agoâ€¦); its sun plays straight away
- [ ] Hovering a cover shows its star and sun: the star makes it a favorite (it stays on the cover, and the game is in Favorites, also after a restart), the sun plays it
- [ ] Clicking a cover opens its page: the wide picture with the name, Play, Plays on, Last played, Play time and Size on disk; Esc or the arrow goes back; a Windows game's Play on Windows asks before restarting
- [ ] Play time matches Steam's for a Steam game; after playing a Windows-only game on a trip (VALORANT), its play time grows by about as long as it ran
- [ ] Right-click a cover: Play, Open its page, Add to / Remove from favorites, and for Steam's Show in Steam and Uninstallâ€¦
- [ ] In Arabic or Hebrew the window is mirrored: the side on the right, covers from the right

### Wi-Fi in both (after 0.9.3)

- [ ] Join a new Wi-Fi network in Monet (a phone's hotspot), then play a Windows game: Windows is online on it without asking; `C:\ProgramData\Monet\wifi` is empty afterwards
- [ ] Join another network in Windows (the taskbar's Wi-Fi), then Back to Monet: Monet knows it at once (Wi-Fi page lists it as saved), and `C:\ProgramData\Monet\wifi-out` is gone or empty after Monet started
- [ ] A work or school network (802.1X) in either stays where it was joined
- [ ] In Windows, as an administrator: `icacls C:\ProgramData\Monet\wifi` lists only Administrators and SYSTEM, and a file Monet left there before Bridge started (Settings â†’ Wi-Fi, join one, then restart into Windows with Bridge's tasks stopped) has the same
- [ ] Change Monet's time zone (Settings â†’ Date & Time, another city), then play a Windows game: Windows' clock shows the same time as Monet's did

### Your apps again (after 0.9.3)

- [ ] With Files, Zen and Discord open, Play a Windows game and quit it: back in Monet, a few seconds after the desktop shows, Files, Zen (with its tabs) and Discord open again; Steam isn't opened twice
- [ ] Settings â†’ Play on Windows â†’ Open your apps again off: after the next trip nothing reopens; on again, it does
- [ ] With Ready when you come back on too: the apps are open behind the lock screen when you unlock

### A guest (after 0.9.3)

- [ ] Settings â†’ Accounts â†’ Guest asks for an administrator's password, then the sign-in screen lists Guest with Monet's parasol painting; Guest signs in with no password and gets Monet's look
- [ ] As Guest, save a file in Documents and change the wallpaper, then sign out and in as Guest again: the file is gone and the look is new; Backups shows no earlier versions
- [ ] As Guest, Play on Windows asks for an administrator's password; your files (`ls /var/home/<you>`) are refused
- [ ] As Guest, Games lists no Windows games and the app menu has none either
- [ ] Power off while Guest is signed in: at the next start Guest's home is new again
- [ ] Guest off removes the account (no Guest on the sign-in screen), after the password
- [ ] As Guest, `loginctl enable-linger` is refused, and `btrfs subvolume create ~/keep` then signing out still leaves a new home
- [ ] As Guest, start `setsid sleep 1d &` in Konsole and leave a file in /tmp, then sign out: `pgrep -u guest` finds nothing, the file is gone, and Guest's next sign-in has a new home
- [ ] As another account (not an administrator), `su guest` is refused; as root it still works
- [ ] Guest off right after a guest signed out removes the account (`id guest` fails) and Settings says it's off
- [ ] On a PC where someone's own account is called `guest`, Guest doesn't turn on and their home is untouched

### Your photo, painted (after 0.9.3)

- [ ] Settings â†’ Light & Wallpaper â†’ Your photo: the file dialog opens; pick a JPEG from your phone: the tile says Paintingâ€¦ with a percent, and within about a minute (two on a 4K screen) the desktop and the lock screen show it painted, in the light of the hour; the placard says Your photo, and the light
- [ ] Choose The Hours and back to Your photo: it comes back at once, no painting again; Another photoâ€¦ paints a new one, the old one stays on the wall until it's done
- [ ] A picture Monet can't open (a .heic renamed .jpg): the card says it couldn't be painted, the wall stays as it was
- [ ] With Through the day on, the painting drifts dawn â†’ midday â†’ dusk â†’ night like The Hours
- [ ] Sideways phone photos come out the right way up

### Downloading once (after 0.9.3)

- [ ] Files lists Shared with Windows with your places; a file saved there is in Windows' Explorer under Quick Access (Shared with Monet), and one saved there in Windows is in Monet after the next start
- [ ] With Windows hibernated, the place isn't in Files (and is back after a trip that ended with Back to Monet)
- [ ] In Windows, Steam installs a game into the Games folder Monet made (no "disk write error"), and `icacls C:\Games` lists Authenticated Users with Modify
- [ ] Install an Epic game in Heroic into Windows games on a Windows without Epic's launcher: at the next sign-in `Windows games/.monet/installers` gets Epic's installer; the next trip installs the launcher without downloading it (Bridge's log says so), and the installer is gone the start after
- [ ] Battle.net in Lutris: drive W: is Windows games; install Overwatch there; Monet's Games lists it as Battle.net Â· Plays on Windows; Play: Windows' Battle.net (installed from the fetched installer, its own window) asks to install it, Locate the game â†’ C:\Games\Overwatch, and it starts with nothing downloaded; next time it starts straight away
- [ ] Ubisoft Connect in Lutris: install a game on W:; at the next start Windows' Ubisoft Connect lists it as installed (or, asked to install it, Locate installed game finds it)
- [ ] An installer that isn't signed by its maker (a renamed file in .monet/installers) isn't run: Windows downloads the real one
- [ ] Settings â†’ Games & Controllers â†’ Get Battle.net: Lutris (from Flathub if it wasn't here) installs Battle.net; W: is there in its install dialog right away; the button then says Open Battle.net
- [ ] A Battle.net game installed on W: is in Monet's Games before any trip, as Battle.net Â· Plays on Windows, and its Play sheet says where to locate it
- [ ] On a trip that installs a launcher, Windows shows Monet's painting with "Getting Battle.net ready" (or Epic Games, Ubisoft Connect) until the game starts

### Windows' keys (after 0.9.3)

- [ ] On a new account's first sign-in: Ctrl+Shift+Esc opens System Monitor, Windows+I Settings, Windows+A Quick Settings, Windows+G Games, Windows+R the run box, Windows+E Files, Windows+Shift+S a region screenshot; Windows+Up maximizes a window and Windows+Down minimizes it
- [ ] The old keys still work too (Ctrl+Esc, Alt+Space, Meta+Shift+Print, Meta+PgUp)
- [ ] An account from 0.9.3 gets them at its next sign-in; a key changed in Change shortcutsâ€¦ stays changed after another sign-in
- [ ] Settings â†’ Mouse & Keyboard lists them

### Windows programs (after 0.9.3)

- [ ] Download a small Windows program (7-Zip's or Notepad++'s installer) and double-click it in Files: Monet's sheet asks, with its name; Run in Monet installs it (the first time a note says Monet is getting ready, then the installer opens), and afterwards the program is in the app menu and opens from there
- [ ] A portable `.exe` (a single program, no installer) runs from Run in Monet, and a second one starts quicker (no getting ready)
- [ ] Open in Windows on the same file: the PC restarts in Windows and the program opens there, Windows stays (no countdown); `C:\Shared with Monet` has it, and Back to Monet goes back; a program saved in Shared with Windows opens without being copied
- [ ] With Windows' drive not open (Windows hibernated, say), the sheet says Windows can't get it this time and Open in Windows is greyed
- [ ] Right-click an `.exe` in Files: Run in Monet starts it at once; Open in Windowsâ€¦ shows the sheet
- [ ] With Office, Photoshop or another app installed in Windows: after a start of Monet with Windows' drive open, the app menu has it with its own icon on Monet's canvas, "Opens in Windows" under its name; searching "word" or "windows" finds it. Windows' own tools (Notepad, Command Prompt), Steam and its games, Edge and Chrome, uninstallers and help aren't there, and an app Monet has too (Discord) is there once, Monet's
- [ ] With iCloud or WhatsApp from the Microsoft Store in Windows: after a trip to Windows and back (and the next start of Monet), the app menu has it with its own logo; choosing it opens it in Windows. Calculator, Photos and Xbox aren't listed
- [ ] Choose one: Monet's sheet shows it with Open in Windows (no taskbar button meanwhile); Open in Windows restarts in Windows and the app opens there as you (with its own arguments: Office opens to its start page), Windows stays; Back to Monet goes back. Uninstall it in Windows: after the next trip, its entry and icon are gone
- [ ] An `.msi` installer works both ways too

### The Store (after 0.9.3)

- [ ] The bar's Store (the bouquet) and the menu's open Monet's Store, not Bazaar: today's pick hung on a painting with Install on its placard, then Monet's picks as rooms (a strip of The Hours with its placard, three framed apps, a wall of tiles), Most installed this month after the first and Fresh paint after the third; Mist by day, Smoke by night; sections down the side with counts, the window in Monet's glass. An account from 0.9.3 with Bazaar pinned in the menu or the bar opens the Store from there too, and no "Bazaar" shows anywhere
- [ ] In another language (Svenska, say) the names, summaries and descriptions are in it where Flathub has them, and the window's own words are too
- [ ] The mouse wheel and a touchpad glide through the front page, a section and an app's page, also with the pointer over the screenshots; Page Down and arrows scroll too; Settings' pages, Games' covers and a game's page glide the same way
- [ ] Settings', Games' and the Store's side is glass: the painting (or a window behind) shows through, blurred. Settings â†’ Light & Wallpaper â†’ Glass: Solid makes all three paper at once, Matte nearly paper with the painting's color, Frosted and Clear see-through again, without closing them; their pages stay paper all along
- [ ] Monet's look â†’ Put back: the card says Putting it backâ€¦ for a few seconds, then the pill says Done in lily, then Put back again
- [ ] Games: its own painting (the haystacks), a placard with how many, the top three framed and numbered. Recently updated puts the newest first with their dates, Name sorts by name (and is still chosen after the Store is opened again), Strategy narrows to strategy games (the placard says how many), Checked by Flathub to the checked ones, and the page starts from its painting each time
- [ ] Search "krita": Krita first. Search "photoshop": a note says Photoshop is made for Windows and lists GIMP, Krita and Pinta; with Photoshop in your Windows, it's under On your Windows and choosing it opens Monet's sheet for Windows. Search "zzqx": the Store says nothing goes by it, with examples
- [ ] An app's page: under its section's painting; the screenshots as a gallery (the arrows, the small ones under it and the arrow keys change the big one, a click shows it whole), the description, What it can reach in plain words, the sizes, version and website, and More like this (choosing one opens its page at the top). Install shows progress, then Open and Remove; it's in the app menu and under Installed; Remove takes it away again. A built-in app (Photos) says Part of Monet
- [ ] As a standard account (not an administrator), Install says only an administrator can. With the network off, it says the Store can't reach Flathub
- [ ] A link to `appstream://org.gimp.GIMP` (from a web page or `xdg-open`) opens the Store on GIMP's page; a second click on the bar's Store brings the open window forward

### EA's games, and launchers out of sight (after 0.9.3)

- [ ] In Windows, with EA SPORTS FC 26 installed by the EA app: back in Monet it's in Games as EA Â· Plays on Windows; Play restarts in Windows and Monet's painting says Starting until the game itself is on screen; the EA app is never seen (it's minimized in the taskbar while the game runs)
- [ ] The same with the EA app signed out: after about a minute the painting steps aside and the EA app's sign-in is there; once signed in, the game starts
- [ ] Quit the game and press Stay in Windows on the countdown: within a minute the EA app is gone from Task Manager (EABackgroundService, a Windows service, may stay); Battle.net, Ubisoft Connect and Epic's launcher close the same way after their games; Steam stays
- [ ] A Ubisoft game in Ubisoft Connect's own games folder: while it runs it isn't minimized (only Ubisoft Connect's windows are)
- [ ] Settings â†’ Games & Controllers â†’ Get EA app: Lutris installs the EA app; set its download folder to W:\ and install a game; it's in Games as Plays on Windows before any trip, and Play's sheet says to choose Download with C:\Games; in Windows the EA app checks it instead of downloading it
- [ ] In Monet, with Steam closed: Play on a Steam game starts it with Steam only in the tray; Play on a Heroic game starts it without Heroic's window

### Monet's names everywhere (after 0.9.3)

- [ ] Sign in, open Files, Terminal, Photos and Documents: their title bars end in Files, Terminal, Photos and Documents (never Dolphin, Konsole, Gwenview, Okular); in Swedish, Filer; Alt+Tab and the bar's previews say the same
- [ ] `cat /etc/os-release`: NAME and PRETTY_NAME say Monet, VERSION is Monet's, BOOTLOADER_NAME says Monet; ID still bazzite; KDE's About this System says Monet
- [ ] Files' Devices doesn't list "boot" (or EFI); a USB stick still shows, even one with a partition called boot
- [ ] Files' status bar doesn't say "0 B free"; Settings â†’ Storage shows the room left
- [ ] Input Remapper isn't in the menu and `systemctl status input-remapper` says disabled; the start isn't held up by it
- [ ] Light or Dark picked several times quickly: Monet's look follows each time, and `systemctl --user --failed` stays empty

### Settings tells the truth (after 0.9.3, found by the test bench)

- [ ] Settings â†’ Security: Secure Boot says on when the PC's firmware has it on (`mokutil --sb-state`), and the firewall says on (`systemctl is-active firewalld`)
- [ ] Settings â†’ Default Apps lists Documents for PDFs
- [ ] Zen's first start (a new account) opens one Monet new tab: no Zen welcome or what's-new page
- [ ] A PC without Wi-Fi or Bluetooth (on a cable): Quick Settings says Unavailable on both and opens at once with its sliders (no empty bar first); Settings â†’ Wi-Fi says This PC has no Wi-Fi
- [ ] A PC without speakers (or the VM): Sound says No speakers or headphones, with no Play sound through list
- [ ] Settings' search: type Games and press Enter, it opens Games (not Storage); Updates opens Updates
- [ ] Games lists no Windows game that Windows doesn't have (Slay the Spire is no longer always there); on a Monet without Windows, Games has no Open Windows
- [ ] Settings from the app menu (or any of its pages, like Sound) opens Monet Settings on that page; double-clicking a Windows program in Files asks where to open it
- [ ] Games & Controllers counts only controllers: a drawing tablet or a VM's mouse isn't one

### The bar, the glass and the sound (after 0.9.3)

- [ ] A new account: the bar's islands slide down out of the way when a window comes over them (maximize Files), and slide back up as the pointer touches the bottom of the screen, with a pen or touchscreen too; Settings â†’ Light & Wallpaper â†’ Bar steps aside is on
- [ ] An account from 0.9.3 that never turned Bar steps aside off: it's on after the update; one that turned it off keeps it off
- [ ] Bar steps aside off and on again, several times: the middle island stays in line with the other two (it stood a bar's height higher)
- [ ] In a VM, or on a PC without its graphics driver (6 or more processor threads): windows and the bar still animate (`KWIN_EFFECTS_FORCE_ANIMATIONS=1` in `cat /proc/$(pidof kwin_wayland)/environ | tr '\0' '\n'`)
- [ ] Settings â†’ Light & Wallpaper â†’ Glass is a slider: Solid, Matte, Frosted, Clear. Each step changes the bar, popovers, window frames, Files' window and the desktop widgets together: Clear shows the painting's strokes, Frosted only its light and color, Matte a light veil with a faint grain, Solid is paper; the words under the slider say what each is
- [ ] Glass right after the first sign-in (KWin may not have loaded its blur yet): Clear is frosted glass, never a sharp see-through window (`busctl --user get-property org.kde.KWin /Effects org.kde.kwin.Effects loadedEffects` lists blur)
- [ ] An account from 0.9.3 with glass off stays solid; with glass on stays clear
- [ ] Sound sits beside Quick Settings (KDE's volume item is gone from the tray): its icon follows the volume, the wheel over it changes it 5% a notch, a middle click mutes; its popover has the volume with a mute pebble, Play sound through (with two or more outputs) and Apps playing sound, and Sound settingsâ€¦ opens Settings â†’ Sound
- [ ] The volume keys still change the volume and show the level on screen
- [ ] On a PC without Windows: Settings â†’ Play on Windows says No Windows on this PC, with no Restart in Windows, games or launchers there; Games has no Open Windows

### Windows, snapped as in Windows (after 0.9.3)

- [ ] Drag a window by its title: a sliver of glass comes down at the top of the screen; bring the window up to it and it opens into five layouts; the part under the pointer lights up and a lily pane shows where the window goes; let go and the window glides there
- [ ] Drag to the left or right edge: a half; to a corner: a quarter; to the top elsewhere: the whole screen; each with the preview first, and gliding into place
- [ ] After a snap, Snap Assist offers the other windows in the rest of the layout: click one and it takes its part and comes to the front, then the next part is offered; click anywhere else, the pane's empty glass too, and it goes; Windows+Left and Windows+Right do the same for the other half
- [ ] Windows+Z: the layouts come down for the window you're in; click a part; Windows+Z again or a click elsewhere puts them away
- [ ] Settings â†’ Light & Wallpaper â†’ Snap layouts off: dragging a window to the left edge gives it the left half with no Snap Assist, the top fills the screen, Windows+Z does nothing and Mouse & Keyboard's list leaves it out; on again, the layouts and Snap Assist are back at once (no sign-out). Install an update of Monet: still off
- [ ] Keys, as in Windows: Windows+Left, then the arrows or Tab light a window's picture in Snap Assist, Enter or Space picks it, Esc closes it. Windows+Z, then the arrows walk the parts (up and down: the layouts), Enter puts the window there and Snap Assist comes; Esc closes that too. Afterwards Esc, Enter and the arrows work in apps again (the Calculator's Esc clears it)
- [ ] The left island shows the sun and the Games button (the sun as a play button); clicking it, or Windows+G, opens Games, and again brings it forward
- [ ] A notification (a screenshot taken, say) shows whole, its close button inside the screen and its right edge in line with the right island's, at 100%, 125% and 150%
- [ ] Windows+Z shows a number under each layout; 4 lights that layout's first part, numbers its parts and turns its own number lily; 3 puts the window in its third part. A number with no layout (9) does nothing; afterwards typing numbers in an app works again
- [ ] Drag a snapped window away: it's its own size again, still under the pointer where you held it
- [ ] Stretch a window's bottom edge to the bottom of the screen (or its top edge to the top): it takes the whole height, gliding there
- [ ] Snapped windows (a drag, Snap Assist, Windows+arrows) meet each other and the screen's edges: no painting shows around them
- [ ] Snap Settings to one half and another window to the other; make Settings wider by its glass edge: the other window gets narrower, and neither goes over the other. The same the other way round, from the other window's edge
- [ ] Settings is a window like the others: Monet's title bar with its three dabs, it resizes from every side, double-clicking the title fills the screen, Windows+arrows and a drag snap it, the taskbar shows it, and it keeps its size after closing. Restart the bar (or let it crash): Settings stays open. Open it from the menu, Windows+I, Quick Settings' All Settings and a tile's arrow, and the desktop's Personalize: always one window, at the page asked for, coming to the front even from behind another window. Typing in its search works; Esc closes it
- [ ] Close Settings after it was snapped and open it again: its own size, in the middle, not the snapped one
- [ ] Turn Bar steps aside off and on a few times: the three islands stay at the same height every time and look alike; off, a maximized window goes below all three of them
- [ ] Right-click the desktop â†’ Add or Manage Widgets, then Done: the three islands stay on one row the whole time (they piled up a bar's height apart), the middle one centered; add a widget to the middle island while editing and it stays centered; with Bar steps aside on, a maximized window still makes them slide away afterwards
- [ ] Glass at Solid, then back to Matte, Frosted and Clear: each one comes back
- [ ] KDE apps (Files, Terminal, Calculator, Photos, Documents, Video, Music, Archives, Text Editor) and More settings wear Monet's glass app style: rounded fields, lily selection, glass at the edges; Files' status bar shows "9 folders" whole; the desktop's right-click menu is glass with rounded corners
- [ ] In More settings' first page, press Light, then Dark: the windows and menus keep Monet's style (they turned plain), and the title says "More settings"
- [ ] More settings â†’ Keyboard: hover Back and the menu button at 100% and 125% scaling, in Mist and Smoke. Their highlights stay above the header divider with a visible gap. Use the keyboard to return to the category list too. Repeat with matte glass and no glass.
- [ ] After a fresh install, open More settings from Settings â†’ Display: it opens at Display, and from Light & Wallpaper at Fonts. Its list has no Quick Settings, Wallpaper, Activities, Colors, Global Theme, Window Decorations, Icons, KDE Wallet or Software Update, and its groups say Display, Sound, Default Apps and Desktop (in your language too). From a Settings page with no KDE page of its own (Updates, say) it opens at General Behavior, never a page saying Plasma
- [ ] Change the wallpaper in KDE's dialog, the pointer and a font, then Settings â†’ Light & Wallpaper â†’ Monet's look â†’ Put back: in a few seconds the painting, Monet's pointer, fonts and glass are back, panels and files as they were
- [ ] On a desktop PC, Num Lock is on after signing in (not changed on a laptop); Windows+Tab shows all the windows
- [ ] Right-click the desktop: Create New, Paste, Undo, Icons, Open Terminal, Add or Manage Widgets, Display settings, Personalize, and nothing of KDE's dialogs. Display settings opens Settings on Display, Personalize on Light & Wallpaper (in your language too). The lock screen still shows the painting
- [ ] Mist to Smoke and back: the colors, frames and app style change together in about a second, and the bar and Settings don't stop
- [ ] Mist with Through the day on: the painting goes through the day into the night with the colors staying light; with Through the year, the season's painting. The Mist and Smoke cards say "Light colors all day" and "Dark colors all day"
- [ ] Files: under Devices, no nameless drive with a red bar, no "boot" and no "monet"; a USB stick and Windows' drive still show; no "0 B free" at the bottom
- [ ] Pick another font (More settings), then install an update of Monet: the font is still yours
- [ ] With two keyboard layouts, Windows+Space switches between them (from the next sign-in); Settings â†’ Mouse & Keyboard lists it, and Windows+Z
- [ ] A Word file written in Calibri opens in the office apps with the same lines and pages as in Word
- [ ] The resize arrows appear on a window's glass edge and a few pixels outside it, all along the sides and bottom, and the edge follows the pointer; windows look as before
- [ ] With Bar steps aside on, maximize a window: the islands slide away in the same glass they had (Clear, Frosted, Matte), never turning white first
- [ ] Maximize and restore (double-click the title): the window grows and shrinks smoothly, once (no double animation)
- [ ] A game in full screen, dragged windows on a second screen, and a window an app resizes itself (a video player's native size): nothing snaps or glides that shouldn't

### Install a game once (after 0.9.3)

- [ ] On a PC with Monet's Windows (or a kept one with Monet Bridge, no BitLocker): `findmnt "/run/media/Windows games"` shows Windows' `Games` folder, `ls /run/monet/windows-drive/c` is refused to the person and to a second account (root's only), and `findmnt -o OPTIONS /run/monet/windows-drive/c` says `rw`; Files' Devices doesn't list Windows' drive (a USB stick still shows), and `cat /run/monet/windows-drive.json` says `"state": "open"`
- [ ] After a trip to Windows that ended with Back to Monet, the next start opens it again; after Windows crashed or lost power, the state is `unclean` and Settings â†’ Games & Controllers says Windows wants to check its drive (Windows does at its next start, and the folder is back the start after)
- [ ] Settings â†’ Games & Controllers shows Windows games with Add to Steam (Steam closes for a moment and opens again); in Steam, Settings â†’ Storage lists `/run/media/Windows games`; signing out and in adds it by itself when Steam was closed
- [ ] Install a game that needs Windows (Apex Legends) in Steam here, choosing Windows games: it downloads while you keep using Monet; Games says Plays on Windows; Play restarts in Windows and Steam there starts it without downloading it again (a quick check of its files is fine)
- [ ] The first such trip: Steam in Windows lists `C:\Games` under Storage (it closed and opened by itself once); `C:\Users\<you>\AppData\Local\Monet\bridge.log` says it added C:\Games
- [ ] Install a game in Windows' Steam into C:\Games: back in Monet, Steam here lists it as installed and keeps it up to date; one that plays here (no anti-cheat) starts in Monet from there with Proton (its Properties â†’ Compatibility says Proton Experimental), and in Windows again afterwards without a download
- [ ] In Heroic, install an Epic game that needs Windows (Fortnite) into `/run/media/Windows games`: Games says Plays on Windows; at the next sign-in `Windows games/.monet/epic/Fortnite.json` and the game's `.egstore` appear; Play restarts in Windows, Epic's launcher checks the files once and starts it, with no download
- [ ] An Epic game installed in Epic's launcher in Windows elsewhere (C:\Program Files\Epic Games) keeps its own entry; uninstalling the Heroic one in Monet makes Epic's launcher forget it at the next trip
- [ ] Without Heroic, Settings â†’ Games & Controllers â†’ Shared with Windows has Epic and GOG games with Get Heroic: it says Getting Heroicâ€¦ and then Heroic opens to sign in; the row then says how to install into Windows games
- [ ] A GOG game installed by Heroic into Windows games plays on Windows (Play on Windowsâ€¦ from Settings) straight from its folder, with no launcher; `monet-bridge status` lists it as gog:<id>
- [ ] Windows' screenshots (Windows key + Print Screen) and Game Bar clips (Windows key + Alt + R) are in Monet's Pictures â€º Screenshots and Videos after the trip, gone from Windows, and a notification says so once with Show; a screenshot taken with F12 in Windows' Steam is there too, and still in Windows' Steam
- [ ] With bookmarks in Edge (and Chrome or Firefox) in Windows, and Zen not started yet in Monet: after a trip to Windows and back (or the first sign-in after Setup), Zen's first start has them, Edge's bar on Zen's toolbar (several browsers: a folder each). Settings â†’ Default Apps â†’ From Windows says how many, from which browsers
- [ ] A GTK 4 app from Flathub (Mission Center, say) in Monet's paper or smoke, the button that goes ahead in the sun, switches lily; the window buttons are signs with a dab of paint under the pointer (lily, ochre, the sun), page titles in Fraunces. `head -3 ~/.config/gtk-4.0/gtk.css` starts with `/* Monet:` and imports `colors.css` and `kde_window_geometry.css`; changing KDE's colors in More settings doesn't take it away
- [ ] Settings â†’ Storage â†’ OneDrive â†’ Connect: Microsoft's sign-in opens in the browser; after it, the card says how full OneDrive is, Files lists OneDrive among its places, and a Word file there opens (coming down as it's opened). After a restart it's there again without asking. A file Windows keeps online-only in OneDrive opens from here too. Disconnect: the place is gone, `~/OneDrive` is gone, and the files are still in OneDrive on the web
- [ ] Connect, then close the browser without signing in and press Cancel: the card shows Connect again with no complaint, and `rclone listremotes` lists nothing
- [ ] With Zen already used: Add to Zen leaves Bookmarks from Windows in Downloads and opens Zen's bookmarks; Import and Backup â†’ Import Bookmarks from HTML adds them beside Zen's own. The Passwords row's Show the folder opens Shared with Windows; a CSV exported there from Edge imports in about:logins
- [ ] On a Windows with a second account (another person's), their screenshots stay in Windows, and F12 screenshots of a Steam account you don't use in Monet don't come over; `ls -ld /run/monet/windows-drive/c` and the shared folder's files are the person's alone (another account here can't read them)
- [ ] Settings â†’ Games & Controllers â†’ Needs Windows: a game in Windows games says it's ready there, with Play on Windowsâ€¦

### Older PCs and laptops

- [ ] `/usr/libexec/monet-quick older-pc` says `yes` with 8 GB of memory or less (or a hard disk), `no` otherwise
- [ ] On an older PC: `~/.config/monet/glass-lite` is there, Steam opens about 45 s after the desktop, and `kreadconfig6 --file baloofilerc --group General --key "only basic indexing"` says `true`
- [ ] Sign-in: `systemctl --user list-timers` shows `monet-after-sign-in` for a minute only after something changed (the first sign-in after an update, or an app installed while signed out); signing out and in again with nothing new shows none
- [ ] A normal start: `systemctl status monet-ready-boot monet-keep-prepare` say "condition unmet", and Settings â†’ About Monet â†’ Last start shows where the start's time went
- [ ] On a laptop with an NVIDIA chip beside the built-in graphics: a game from the Store's Play row (Prism Launcher, RetroArch) runs on the NVIDIA chip (`nvidia-smi` lists it), while the desktop and Steam's window don't

## 2. Switching

Time with a stopwatch, from the click to the moment you can play.

| Test | Laptop | Desktop |
|---|---|---|
| Monet â†’ Windows desktop | | |
| Play on Windows â†’ game menu | | |
| Quit game â†’ Monet desktop | | |
| Back to Monet shortcut â†’ Monet desktop | | |

Targets: under 30 s into a game, under 20 s back to Monet.

Settings â†’ About â†’ **Last start** shows where the time went on the way back:
the PC's own start (firmware), Monet's (loader, kernel, system), and your
desktop (from signing in until it's there). Note them for both PCs:

| Last start | Laptop | Desktop |
|---|---|---|
| The PC | | |
| Monet | | |
| Your desktop | | |

### Ready when you come back

Turn it on in Settings â†’ Play on Windows, then Play on Windows and come back.

- [ ] Coming back, Monet signs in by itself and the **lock screen** shows first, not the desktop
- [ ] After the password, the desktop is already there (compare the time with it off)
- [ ] The start after that asks for the password at the sign-in screen as usual
- [ ] Shut down from Windows instead of coming back, start the PC the next day: the sign-in screen asks as usual
- [ ] Turned off again: coming back from Windows shows the sign-in screen
- [ ] If the desktop ever shows before the lock screen, turn it off and note it in Logs below

## 3. Anti-cheat

For each game: Play on Windows, quit (the PC restarts into Monet by itself,
not off), then Play on Windows again.

| Game | Anti-cheat | First play | Second play | Notes |
|---|---|---|---|---|
| Valorant | Riot Vanguard | | | |
| League of Legends | Riot Vanguard | | | |
| Call of Duty | Ricochet | | | |
| Fortnite | EasyAntiCheat | | | |
| Counter-Strike 2 (FACEIT) | FACEIT AC | | | |
| Apex Legends | EasyAntiCheat | | | |

## 4. Things that can go wrong

- [ ] A Windows update restarts the PC: does it come back to Monet by default?
- [ ] BitLocker: does Windows ask for the recovery key after switching?
- [ ] Settings â†’ About Monet â†’ Get BoxBuddy installs and opens it (an administrator's yes for Flathub); it makes a container with a terminal, where `dnf install` works
- [ ] BitLocker turned on in a Windows that has Monet Bridge (Settings â†’ Privacy & security â†’ Device encryption on, or BitLocker on a Pro): after encryption finishes and Windows restarts once, the next start of Monet opens Windows' drive by itself, Settings shows no key to type, and `ls /boot/efi/EFI/Monet` (or the EFI partition) has no `bitlocker.json` left. Also on Windows 11 Home
- [ ] BitLocker (device encryption on a Windows 11 laptop): Settings â†’ Games & Controllers â†’ Shared with Windows asks for the recovery key. A wrong one says so; the right one (from aka.ms/myrecoverykey) opens it: Monet Bridge is staged and installs at Windows' next start, then games, files and Wi-Fi work in both. After a restart it opens without asking (`ls /var/lib/monet/bitlocker` as root shows one `.cred`). Windows still starts normally afterwards, without asking for its recovery key
- [ ] Unplug the charger while switching (laptop): does everything still work?
- [ ] Start Windows from the firmware boot menu instead of Monet: does it behave normally?
- [ ] Uninstall a game in Windows, then press Play on it in Monet: is the message clear?
- [ ] Clock: is the time right in both systems after switching a few times?

## Store downloads and recovery

Implemented 2026-10-27; pre-change VM checkpoint: `ai-before-store-downloads-1027`.
The Store saves each request before starting a separate user-service worker. A file lock
allows one transaction at a time; repeated clicks/workers cannot install the same job twice.
Flatpak keeps its partial downloads and owns deployment safety. Cancellation uses
[Gio.Cancellable](https://docs.gtk.org/gio/method.Cancellable.cancel.html) with
[Flatpak transactions](https://docs.flatpak.org/en/latest/libflatpak-api-reference.html);
the UI waits for cleanup and checks success against the exact installed app reference.
Closing Store keeps work running. A lost worker becomes **Interrupted** with **Retry**;
reopening or signing in does not automatically repeat removals. Completed requests offer
Open/Dismiss; failed/cancelled requests keep their app reference and installation for retry.

Automated: `python tools/vm.py tests tests.test_store_downloads tests.test_look.OurOwnStore
tests.test_store_frame_regressions tests.test_settings_feedback`. The 41 selected tests pass
with three Node-dependent skips; those three pass separately on Windows. Checks cover private
atomic state, duplicate workers/clicks, cancellation races, exact removal retries, lost workers,
reboot-style stale requests, malformed data, startup failure, injected ENOSPC writes, catalog
independence and Return/Space on queue controls. The existing catalog/shortcut/Settings checks
remain green. Unreadable state is kept rather than silently overwritten.

Live in the Monet VM, Firefox was initially absent. Its real Flathub download was cancelled
from the app page. Retry continued after Store closed, and reopening Store recovered its state.
Killing only that test worker produced an Interrupted request. A worker-only unreachable proxy
produced the connection error without changing the VM's network settings. Retry from Downloads
then installed Firefox successfully; Flatpak confirmed the reference. Remove through Store
completed successfully, returning the installed-app list to Zen alone. Test requests were dismissed.

Still required before release:

- [ ] Full reboot/power-loss testing during download and commit on a disposable installation.
- [ ] Real disk exhaustion during download, deployment and queue write; clear space and retry.
- [ ] Standard/administrator accounts, denied authorization and alternate Flatpak installations.
- [ ] Screen-reader, large-text, RTL and fractional-scale checks for the queue and app controls.

Current bounds: 100 requests, one job per app, one active transaction, explicit retry after
failure/reboot, and Flathub app install/remove only. This is not a pause/resume-by-byte API;
Flatpak decides which cached objects it can reuse. A cancellation can remain pending during
native cleanup. Updates and Windows game downloads use their existing flows.

## Upgrade preservation and profile recovery

`monet-profile` owns only the values Monet has written. `monet-look --keep` no longer
applies the global theme first. Existing unknown values, explicitly empty values, disabled
bindings and deleted owned values stay untouched. The former `look-written` ledger is
imported only when it matches the current value. Generated launchers use a three-way merge:
custom names, icons, commands, localized fields and removed shortcuts survive later updates.
Removed launchers stay removed. Known obsolete Store commands are repaired, but customized
commands and arbitrary file URLs are not redirected by dock repair. Panel order is retained.
Pre-desktop menu/tray defaults and maintenance jobs follow the same preservation policy.

Sign-in records a migration by its helper contents and arguments, rather than only the
marketing version. It records success only after successful writes. Failed/interrupted runs
remain inspectable and retryable; a previously applied revision is not replayed after a newer
one. This protection applies to releases that include the new updater, not older binaries.
An explicit **Put back** still restores Monet's appearance by request.

The private, atomic journal is `$XDG_STATE_HOME/monet/profile/state.json` (normally
`~/.local/state/monet/profile/state.json`, mode 0600). On an updated image, run these as the
affected account, without sudo:

```sh
/usr/libexec/monet-profile status
/usr/libexec/monet-profile rollback RUN_ID
```

Use a run ID from `status`. Undo restores managed keys/files only when they still match the
migration's output; later edits and symlinks are reported as conflicts and left untouched.
Undo is repeatable and blocks that revision from immediately reapplying at sign-in. The four
previous completed histories are retained alongside the newest run; failed/interrupted and
conflicted histories are retained. The record is bounded to 8 MiB and fails without discarding
its contents when full or corrupt. This is not a document backup or full desktop snapshot:
live compositor operations, light synchronization, third-party application state and system
deployment rollback have their own mechanisms. Recovery has a command-line interface for now.

Automated checks use KDE's real configuration tools in isolated profiles:
`python tools/vm.py tests tests.test_profile_upgrades tests.test_store_frame_regressions
tests.test_look`. They exercise customized and disabled settings, legacy records, launchers,
two repeated runs, separate command arguments, an older applied revision, failed writes,
a process killed just after a write, private journal permissions, corrupt state and undo
conflicts. JavaScript checks skipped without Node in the VM run separately on Windows with
`python -m unittest tests.test_store_frame_regressions.WindowGeometry`.

Validation on 2026-10-27: 409 checks passed in the broad upgrade/look suite with four
dependency skips. Four Settings feedback checks passed in a separate Qt process, and the
three JavaScript checks passed on Windows. The final shortcut-preservation adjustment also
passed all 21 Linux checks in the profile/Store regression suite.

Live check on 2026-10-27: checkpoint `ai-before-upgrade-preservation-1027`; updated helpers
installed in the VM's existing user test bench. The first migration completed, and the second
used its receipt. All pre-existing values in eight desktop configuration files, launcher
names/icons/commands/shortcuts, Monet preferences and panel configuration matched their before
snapshot. Open apps were kept running. The prepared recovery record had mode 0600.

Release gates still open:

- [ ] Install a new system image over a customized existing installation; restart and sign in twice.
- [ ] Boot the previous system deployment and return to the newer one; compare preferences and pins.
- [ ] Test actual power loss and disk exhaustion while updating the image and profile.
- [ ] Verify normal/administrator accounts and the graphical recovery route.

### Desktop scaling and calendar accessibility

The desktop coordinator uses Plasma's logical work area, preserves the arrangement for
each size during the session, and saves positions through Plasma's normal layout store.
It respects widget minimum sizes and fits the middle bar between the two side bars.
The calendar and clock share an inward-opening notes panel; opening it does not resize
or reposition the month. Notes retain the legacy date-to-text format for one-off entries;
repeating entries store text and `repeat: daily`, `weekly`, `monthly` or `yearly`. Writes are
serialized and atomically replaced. A failed save retains the pending edit and exposes Retry.
Editing or deleting an occurrence changes the series; changing the interval starts it on
the selected date. Monthly notes skip months without that date; 29 February yearly notes
appear only in leap years. Weekly notes follow calendar days across daylight-saving changes.

Automated checks: `python tools/vm.py tests tests.test_accessible_desktop tests.test_look`.
On 2026-10-27, 399 checks completed successfully (one dependency skip), including real QML
keyboard input, native-position animation handling, returning to the earlier layout, yearly
occurrences, leap days, legacy notes, empty-note deletion and failed-write preservation.
Translation extraction/check also passes; new untranslated strings fall back to English.
The final 11 focused checks also pass, including reopening/dismissing the shared notes
dialog without breaking the calendar's visibility binding.
The repeat-options extension passes 17 focused checks, covering all four intervals,
short months, century leap-day gaps, chronological Coming up entries, existing-note
precedence, interval changes, persistence, and keyboard selection of every option.

Live VM checks (checkpoint `ai-before-accessible-layout-1027`):

- [x] 1920Ã—1080 at 100%, 125%, 150%, 175%, 200%, then back to 100%: all four desktop
  widgets stay inside the work area without overlap; bottom bars have separate intervals.
- [x] Reopening Plasma preserves the layout; weather forecasts remain inside their card.
- [x] Both notes panels open toward the screen centre and keep their month stationary,
  including at 200%; panel placement calculations also cover negative monitor origins.
- [x] Type a temporary note, Tab to repetition, select Every year with the keyboard,
  see it in both calendars and Coming up, then clear it. Existing notes remain intact.
- [x] Add a weekly note in the desktop calendar and open its next Tuesday occurrence.
  Open the same note from the clock, use the keyboard to change it to daily and monthly,
  and verify both calendars and Coming up update. Reopen the monthly note: its interval
  persists. Remove the test series; the existing note remains intact.
- [x] Escape returns from a note to the clock's month; Enter reopens it, and clicking
  outside dismisses both. The decorative clock fits its width as the time changes.
- [ ] Mixed-scale physical monitors, changed font metrics, hotplug and docking.
- [ ] Complete Orca, large-text, high-contrast, reduced-motion and RTL audits through
  Settings, Store, Games and the app menu. Calendar keyboard support is the first slice.

An arbitrarily crowded desktop can exceed the space available: fallback keeps its widgets
reachable but cannot guarantee separation in that case. Screen-reader announcement quality
and real hardware behavior are release checks, not established by the VM results.

### More Settings and Store paintings (2026-10-27)

More Settings loads a private Qt proxy style, preserving the chosen base style.
Its native module containers report their layout minimum instead of allowing
explicit undersized minima to clip fields. Forms may wrap long rows, top tabs
have padding above and below, and Shift+wheel pans a wide module from its fields.
Kvantum's scrollbars reserve space and stay visible whenever content overflows.

Validation: 26 focused Python checks (`tests.test_more_settings`,
`tests.test_look.AppStyle`, `tests.test_look.OurOwnStore`) pass. The CMake/Qt
layout suite also passes: complete scroll range including dynamically added
pages, keyboard End, Shift+wheel over a field, wrapping rows, frameless tab
spacing and preservation of intentionally fixed widget widths. Linux packaging
builds and runs this suite before including the private plugin.

Live VM checks (checkpoint `ai-before-settings-layout-1027`):

- [x] Network â†’ General at 100% and 125%: scroll to the right with mouse and
  keyboard; every control's right edge and dropdown arrow is reachable.
- [x] Audio CDs: clear space between header, tabs and form; the last encoder
  tab remains reachable, with visible horizontal and vertical scrollbars.
- [x] At 200%, maximize More Settings: both scrollbars and Apply/Reset remain
  reachable. Restore the original 100% scale after checking.
- [x] Store category paintings at 960px and maximized 1920px: the selected banner
  details remain uncropped by the UI and have rounded corners.
- [x] Close the test instance and use Monet Settings â†’ More settings: the
  process loads the installed private plugin through the normal launcher.

The Store art was subsequently replaced at the user's request with actual Claude
Monet paintings: The Bridge at Argenteuil (1874), The Japanese Footbridge (1899),
The Seine at Giverny (1897), The Artist's Garden in Argenteuil (1873), and Jerusalem
Artichoke Flowers (1880). Five additional works give the remaining categories their
own art: Palazzo da Mula, Venice (1908), Waterloo Bridge, Gray Day (1903),
The Houses of Parliament, Sunset (1903), Rouen Cathedral, West FaÃ§ade (1894),
and The Artist's Garden at VÃ©theuil (1881). All ten museum reproductions come from the National
Gallery of Art's CC0 open-access collection. `branding/store/sources.json` records
their titles, accession numbers, source URLs and 2400Ã—800 crop coordinates;
uncropped reproductions are kept in `branding/store/sources`. The category
associations are curatorial choices for Monet OS, not historical claims about
the paintings. `tools/make-store.py` preserves source pixels and embedded sRGB
profiles, exports the same art for both appearance modes, and bundles
`ARTWORK-CREDITS.txt` with the installed Store. No generated additions or color
filters are used. All ten PNG details match their source crops exactly; all
30 JPEG banners decode at the expected size and have matching light/dark bytes.
The existing front-page asset check passes. Games and Music & video have also
been visually checked in the running Wayland VM with the new paintings, followed
by Writing & office after the category expansion. Generated alternatives were
rejected by the user and are not included in the source or installed Store.

### Everyday bar and shared weather (2026-10-27)

The bar uses the same Monet weather widget as the desktop, with a compact painted
sky and temperature button. Its popup uses the panel's glass without a second
opaque card, and has bounded width and height. `monet-weather` stores one private
location list and unit preference in `~/.config/monet/weather.json`, seeded once
from the existing Monet widget. Both views watch those preferences and the cached
Open-Meteo forecast. Cache keys include the coordinates and temperature unit;
requests are serialized, and a location change during a request cannot show the
old place's forecast. Failed requests keep the last forecast, show its age, and
can be retried. The wallpaper's location also reads the shared preference first.

Fresh layouts and a one-time explicit adoption of Monet's look enable network
and Bluetooth status in the bar, keep notifications, battery, removable devices
and clipboard access, and remove duplicate weather/sound/brightness widgets,
Input Method, Display Configuration, lock-key indicators and Vaults from the
default tray. Keyboard-layout switching and camera/privacy indicators remain.
Only the Xwayland Video Bridge status icon is disabled; its compatibility service
continues running. Display and input-method controls remain in Settings/More
settings, and all tray entries can be enabled in Configure System Tray. Existing
custom app entries are retained; `monet-look --keep` does not reapply this policy.

Validation: eight focused weather/tray tests pass, plus 34 existing widget,
sound, tray and profile-preservation checks. Live checks cover migration of
Stockholm, changing Celsius to Fahrenheit from the bar and seeing both views
update, and the configuration dialog's Cancel and OK behavior. Celsius was
restored afterward. The cleaned overflow menu and panel bounds were checked at
100%, 125% and 200% scaling; weather popup bounds were checked at 100% and 200%
on the 1920 by 1080 VM display. The test leaves scaling at 100%.
The VM has wired networking and no Bluetooth adapter; Wi-Fi radio control,
Bluetooth pairing and laptop battery behavior still require real hardware.

### Hourly and weekly weather details (2026-10-27)

The desktop card and bar now open the same `WeatherDetails` component. It shows
24 hours ahead, all seven days, and the hours for a selected day, using the existing
painted sky and themed popup glass. It includes precipitation probabilities,
feels-like temperature, wind, update time and sunrise/sunset. Hour pages have
explicit buttons; the week scrolls vertically with a visible scrollbar. Tab focus
reveals off-screen controls, Page Up/Down scroll and Escape closes the view.
Reopening resets to current weather. Forecast times stay local to the chosen city.

The cache upgrades from five-day summaries to a versioned seven-day/hourly response.
Incomplete responses cannot replace the previous complete forecast. Offline refresh
keeps the cached result with an error and retry; an old summary remains usable while
hourly details are unavailable. Missing values display an em dash rather than zero.

Validation: 13 shared-weather/tray/presentation tests and 15 existing desktop-widget
tests pass. Live VM checks cover both entry points at 100% and 200%, selecting a day,
the complete seven-day list and sunrise/sunset, keyboard focus scrolling, choosing
Oslo through the bar, and Fahrenheit with matching hourly temperatures/wind units.
Stockholm and Celsius were restored. Wallpapers were not edited. Restarting Plasma
at high scale exposed a separate widget-position persistence regression, tracked
under everyday polish item E in PLAN.md; ordinary scale changes alone had passed.

### Workspace return and overlapping app launches (2026-10-28)

Seventy-one targeted recovery and return-Settings tests pass. They include launching a fast
app while another is unresponsive, starting the editor before browser verification, sixteen
apps surviving capture/receipts, waiting for startup resizing, real Qt JavaScript evaluation
of desktop assignment and stacking/focus, and avoiding focus changes after user interaction.
Existing Files/browser retry, privacy, cancellation and durable-receipt checks remain green.

In the Monet VM, a controlled return reopened two test apps and a real saved KWrite document
across two virtual desktops. Geometry, minimized state, virtual desktop, stacking and active
window matched the captured values. The measured restoration phase was 2.07 seconds; this
does not include boot or a real Windows switch. An initial run exposed a Wayland startup
resize race; waiting for two stable observations fixed it and the repeated live run passed.
The test desktop/apps were removed afterward; existing minimized user windows and calendar
notes were preserved. Evidence is in `/tmp/monet-workspace-live-return.log` and
`/tmp/monet-workspace-tests.log` in the VM. Checkpoint: `ai-before-workspace-return-1028`.

The Linux-target Rust check passes for stopping the switch if checkpoint saving fails.
Translation catalog generation/check pass (1669 texts). This CLI guard needs a rebuilt
system image for an actual switch test; the live bench tests exercise the recovery helpers.

### Recovery after long Windows sessions (2026-10-28)

`python tools/vm.py tests tests.test_trip_lifetime tests.test_resume tests.test_return_summary
tests.test_files_session tests.test_browser_session tests.test_workspace_return
tests.test_look.YourAppsAgainAfterWindows` passes 78 checks without skips. In the same Linux VM,
`cargo test --workspace --locked` passes all 63 Rust tests. Linux-target Clippy and translation
catalog checks pass. Tests use isolated checkpoints and fake firmware, without restarting
the VM or changing its installed helpers.

Version-3 recovery matches the checkpoint and departure boot to a durable system return
receipt. Tests cover a month in Windows, a backward clock adjustment, same-boot rejection,
wrong/missing receipts, interrupted receipt writes, failed restart cleanup and partial
recovery across later trips/reboots. Off, Dismiss, legacy expiry and completed-launch
deduplication remain covered. System receipt failures retain retry evidence and put Monet
first again even when Windows had been placed first.

Release checks still required with a rebuilt image containing both CLI and helpers:

- [ ] Complete Monet → Windows → Monet after more than twelve hours, including Windows updates
  and a period powered off; confirm documents/tabs and window state, without duplicate apps.
- [ ] Interrupt recovery, restart Monet, and retry only pending work.
- [ ] Block/cancel a restart and then perform an unrelated reboot; do not replay that checkpoint
  or leave Windows selected.

### Unsaved work and cancelled switches (2026-10-28)

The recovery command above plus `tests.test_departure` passes 82 checks without skips and
six additional Qt cases in an isolated process. All 65 Rust workspace tests, Linux-target
Clippy and translation catalog checks pass. Tests cover veto/wait without a forced timeout,
only one close request per window, a new window before acceptance, failed inspection,
Cancel during a nested Qt event loop, Escape, exact checkpoint recovery on the same boot,
root EOF/malformed replies and the no-boot-target-before-acceptance ordering.

Live VM evidence, from checkpoint `ai-before-unsaved-switch-1028`:

- An isolated saved KWrite document was modified without saving. Its native close prompt
  appeared; pressing Cancel left the process and unsaved text intact. The worker stayed
  blocked for 172 seconds and did not send an acceptance.
- Escape in Monet's switch window sent EOF. The terminal that had already closed reopened
  once; the original editor PID stayed unchanged. The visible status said the switch was cancelled.
- Retrying and choosing Save persisted the changed text before the worker sent one acceptance.
- A simulated restart failure reopened the saved document and kept the error visible.
  The original notes checksum remained `f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`.

The root endpoint was a stand-in recording the production pipe protocol; it could not touch
firmware or reboot. The VM was restored afterward. A separate inhibitor probe was denied
interactive authorization, so its dry run does not validate actual inhibitor handling.

- [ ] Repeat with a rebuilt image and real privileged helper, including failed firmware/reboot
  requests, active logind shutdown inhibitors and another signed-in user's work.
- [ ] Test browser form/download warnings, office documents, native X11 apps and unresponsive apps.
- [ ] Verify screen readers, RTL and small/scaled screens with save dialogs and the Cancel button.
- [x] Extend document recovery to paths first saved with Save As during close prompts for
  uniquely owned Kate/KWrite native sessions (2026-10-28); shared anonymous sessions remain.

### Multiple windows and browser profiles (2026-10-28)

Run the existing recovery modules plus `tests.test_multi_restore`, `tests.test_departure`
and `tests.test_words`. For headless Qt tests over SSH, set `QT_QPA_PLATFORM=offscreen`.
This slice passed 102 tests plus seven isolated Qt cases, syntax and catalog consistency checks.
The new cases cover per-group receipts, partial return/retry, duplicate folder windows,
source-window identity during cancellation, independent browser profiles and Zen's native
sidebar synchronization without weakening actual-tab verification.

Live VM checks from `ai-before-multi-restore-1028`:

- [x] Three Files windows, with identical folders in two windows, duplicate tabs and split
  folders: close two, retain one, restore the missing pair and verify their distinct positions.
- [x] Leave the surviving Files window's original ID/PID unchanged; Retry creates no duplicates.
- [x] Two isolated Zen profiles with three normal windows, pinned tabs and a private window:
  use native Quit, reopen both profiles, verify normal window counts and native tab digests.
- [x] The private window stays closed and browser preferences remain unchanged.
- [x] Restore a missing two-window profile while the other profile keeps its original PID.
- [ ] Repeat the whole installed-image Monet → Windows → Monet flow on hardware.
- [ ] More browser families, browser spaces/splits, display changes and unusual same-process
  Files windows; editor document-to-window grouping remains separate work.

Disposable fixtures live under `~/.local/state/monet-multi-test-1028` and browser profiles
named `monet-multi-*-1028`. Marionette is confined to those test profiles. The user-facing
browser Quit path was exercised through the VM keyboard; production enables no debug access.
Host screenshots use `%TEMP%/monet-multi-*.png`. Restore the checkpoint after collecting evidence.
The checkpoint was restored after this run; the original session returned and the notes
checksum was unchanged. Host evidence is `%TEMP%/monet-multi-evidence.log`.

### Weather button highlight (2026-10-28)

The compact weather button now centers a natural-sized icon/temperature row inside
its padded control area. Its hover background follows the themed active area's
horizontal inset; Plasma alone paints the expanded highlight, avoiding two
overlapping backgrounds. Extra horizontal padding keeps both the cloud and the
temperature comfortably inside that highlight.

Live checks in the Monet VM cover hover, opening/closing the forecast, and the
expanded button at 100% and 200%. No weather QML errors appeared in the Plasma
journal. The VM was returned to 100%; calendar notes and wallpapers were unchanged.

### Microphone controls in the bar (2026-10-27)

Sound now shows the selected microphone, verified mute state, an explicit mute/unmute
button and input choices when more than one source exists. Audio capture filters
(such as a noise-reduced microphone) are included; video sources and capture streams
are not. The helper validates the displayed microphone ID before muting/unmuting,
reads the actual result back, and returns an error instead of optimistic success.
The popup has bounded height, vertical scrolling and focus-following scroll behavior.

Six focused helper/bar checks pass, covering source parsing, unplugging, denied
changes, changed defaults and rejection of non-input IDs. In the VM, temporary
null-speaker/remapped microphone nodes verified selection between two sources,
mute and keyboard unmute against `wpctl get-volume`, no-device presentation,
and layout at 100% and 200%. All three test modules were unloaded and the original
default-source setting restored. Physical microphones and Bluetooth headsets remain
hardware checks. The VM was returned to 100% and its original widget arrangement.

### Widget arrangements after a scaled restart (2026-10-27)

The layout guard now persists bounded, validated arrangements per desktop and logical
screen size in `monet/widget-layouts.conf`. It loads them before capturing startup
geometry, so restarting Plasma at a larger scale cannot replace the original layout
with temporarily resized widget positions. Plasma's `isUiReady` flag remained false
in the live VM and is not used as a startup gate; the layout's relayout lock and
settling timer protect restoration instead.

Nine desktop UI tests pass, including a fresh QML-engine restart at 200% followed by
return to 100%, animation-safe placement, all supported scale steps, recurring notes
and keyboard calendar operation. Live VM checks confirm that all four widgets stay
on screen without overlap after restarting Plasma at 200%; their complete 100%
geometry records then match the saved baseline exactly. The settings file contains
both arrangements. All local widget copies use the updated guard, and the desktop
was left at 100%. Wallpapers were not edited. Mixed monitors, hotplug and a complete
sign-out/reboot remain hardware/release checks.

### Fresh desktop and panel editing (0.9.8-5)

An isolated Plasma session with clean settings opened with one full-width bar.
The default placard, Weather and Calendar stayed within the desktop without
overlap at 100%, 125%, 150%, 175% and 200% on a virtual 1920×1080 display.
Returning to 100% restored the starting positions. The layout tests also
cover 1366×768, portrait and 4K screens.

Switching from one bar to three and back kept the existing task manager,
including its pins, and retained the Quick Settings shortcut. After removing
the middle bar, choosing Three bars restored the task manager, separator and
Trash. At 960×540 the panel editor scrolled to its footer, Done saved a dragged
card, and removing desktop Weather from the gallery left the bar's Weather in
place.

Both updated 0.9.8-5 images were signed with Monet's release key and checked in
isolated Secure Boot VMs. The Fedora fallback ISO completed a graphical
AMD/Intel install. The Monet Setup ISO booted to Hello and its installer worker
completed an encrypted NVIDIA install. The worker verified the recovery key,
and the installed VM rebooted using the TPM after retiring the temporary key.
On both installed systems, `bootc upgrade --check` rejected the image when its
signature was withheld and accepted it when the signature was restored. Both
VMs reported SELinux enforcing and booted the exact pinned digests. The first
NVIDIA attempt reached the disk-space guard and was restarted after removing
its test disk. The lowest observed free space was 72.3 GiB. No images or media
were published.

An AMD/Intel VM copied from the previous local 0.9.8-5 build also rejected the
unsigned upgrade. It staged the signed image, rebooted into the new digest,
retained the old deployment for rollback, and preserved a test file in `/var`.

The preinstalled desktop test VM then took the same signed upgrade and
reopened its Wayland session. Both installer launchers use the refreshed
ISOs and local mirror. The release bundle was checked with
`tools/publish-qualified.py --verify-local`. Its five downloads, checksum
list and five OCI parts matched the release record. The archive read-back
checked 388 OCI objects. The Windows USB Maker and Bridge executables match
the versions used in the earlier Windows VM tests.

A full graphical run of the refreshed Monet Setup ISO also installed the
AMD/Intel image with encryption on. Setup waited for drive confirmation,
displayed the recovery-key acknowledgment and restarted from All set.
The VM enrolled the Secure Boot key and booted the exact signed digest.
An isolated test service verified the signed channel after another reboot,
when the TPM unlocked the disk and Monet retired its temporary key. The
test disk was removed. The install's lowest observed free space was
70.88 GiB. Evidence is under
`target/098-5-local/desktop/followup/desktop-refresh/native-gui/`.

The packaged Windows USB Maker independently downloaded and wrote each
refreshed ISO to a separate disposable 4 GiB USB disk in an isolated Windows
11 VM. The mirror returned 404 for Setup to exercise the fallback download.
The Maker reported success in both runs. Full read-back found 13 changed
bytes on each disk, all within GPT and protective MBR fields that adapt the
ISO to the USB disk's size. Both GPT headers and partition tables passed
their CRC checks. Under Secure Boot, the written Setup media reached Hello
and the fallback reached its installation summary with zero writes to the
installation target. The temporary disks were removed. The lowest host
free space was 73.0 GiB. Evidence is under
`target/098-5-local/desktop/followup/desktop-refresh/windows-usb/`.

The physical ThinkPad verified the refreshed NVIDIA manifest, its release
signature and all 285 referenced blobs against the local mirror. The Kingston
write attempt timed out while waiting for system authorization, leaving the
earlier Setup ISO on the stick. The ThinkPad still boots Monet 0.9.8, runs on
AC and has no Windows partition. Its F12 boot check and the side-by-side
Windows performance measurements remain open.

The Windows evaluation media was rebuilt from the checksum-verified ISO
for the physical performance comparison. WinPE listed both disks but did
not mount the evaluation USB when its FAT32 partition was marked as an EFI
system partition. Using the GPT Microsoft basic-data type exposed the
split Windows image to Setup. The USB then booted with Secure Boot enabled
and reached the disk picker. QEMU recorded zero writes to its disposable
96 GiB internal disk. The Kingston writer's GPT and FAT32 read-back passed
on a file with the exact Kingston geometry. The preparation command uses
temporary memory, retaining the original ISO and test logs on the SSD.
The physical USB write and Windows installation remain open. The ThinkPad
reports 342.85 GiB of unallocated SSD space outside the Monet partition.
Evidence is under `target/098-5-local/desktop/followup/try/hardware/windows-media/`.

A disposable copy of the refreshed AMD/Intel desktop VM ran Monet's
rollback command and booted the previous signed deployment. The same
command returned it to the refreshed image. The test recorded three
distinct boot IDs and verified the SHA-256 of a saved file after each
restart. Secure Boot and SELinux enforcement stayed enabled, and the
signed update check passed after returning to the refreshed image.
The copied test disk was removed. Evidence is under
`target/098-5-local/desktop/followup/desktop-refresh/rollback-qa/`.

A separate disposable VM switched from the refreshed AMD/Intel deployment to
the exact signed NVIDIA deployment through the local registry. After reboot,
the VM reported the expected digest, passed the signed update check and showed
the NVIDIA Flatpak verification timer scheduled 30 seconds after boot. Monet's
rollback command then returned it to the AMD/Intel deployment. The check
recorded three distinct boot IDs and the same saved file checksum, Secure Boot
state and SELinux enforcement after each restart. This VM used generic graphics
and an unencrypted disk. The temporary disk was removed and host free space
stayed above 75.82 GiB. Evidence is under
`target/098-5-local/desktop/followup/desktop-refresh/exact-nvidia-stage-qa/`.

An encrypted VM using the NVIDIA image and an emulated TPM upgraded from an
earlier signed 0.9.8-5 build to the refreshed digest. Withholding the refreshed
image's signature left the staged deployment empty. Restoring the signature
let the update stage and boot. The signed channel check passed after reboot
and again after rollback, which kept the refreshed deployment as the alternate.
Secure Boot, enforcing SELinux, automatic TPM unlock and the checksum of a
saved file survived the cycle. The VM used virtual graphics. Its memory-backed
test disk was removed, and the SSD kept at least 82.97 GiB free. Evidence is
under `target/098-5-local/desktop/followup/desktop-refresh/encrypted-nvidia-upgrade/`.

All five OCI transfer part checksums were also reproduced by streaming the
retained image layout through the archive writer. The stream matched the
release record without allocating another copy of the archive.

The focused release rerun covered 603 desktop, installer, maintenance and
publication checks with zero failures. One PowerShell parser check was skipped
on Linux, where PowerShell is unavailable. The Windows VM runs above cover
execution of the packaged installer and updater scripts. The desktop rerun
updated an older test to check the Quick Settings and Sound widgets on the
new default taskbar.

The rebuilt images with the compact placard fix ran clean Plasma sessions at
1280×720 with 150% scaling, 1366×768 with 125%, 1080×1920 with 150%, and
3840×2160 with 200%. The three default widgets fit without overlap. Every
session opened with one taskbar, switched to three, restored a deleted middle
panel, and returned to one. The focused rerun passed all 445 checks.
Both exact images also ran a two-output Plasma session at 125% and 200%.
Changing the primary output to 150%, disabling the secondary, and restoring
the original output configuration kept the stock cards within each screen.
After the layout settled, both screens restored the original widget geometry
and the single taskbar remained on the primary screen. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/mixed-outputs/`.

The AMD/Intel test VM rejected the unsigned compact update and booted the
signed digest. The subsequent signed update check passed, and the saved file
and installed placard matched their expected checksums. Both rebuilt ISOs
carry the new image pins and the same signed boot files as the preceding ISOs.
Monet Setup reached Hello under Secure Boot. The Fedora fallback reached
language selection with no writes to the disposable 96 GiB target. The five
downloads and archive checksums were verified against the rebuilt release
record. Evidence is under `target/098-5-local/desktop/followup/compact-refresh/`.
All five transfer parts were then written to a memory-backed directory and
checked by `tools/publish-qualified.py --verify-local`. The verifier read all
six release files and the five parts, extracted the OCI layout and checked
both manifest digests. The transfer and extraction copies were removed
afterward. SSD free space was 76.83 GiB after this verification. The record
is `target/098-5-local/desktop/followup/compact-refresh/archive-verification.json`.

The compact NVIDIA build also completed a full Setup installation from the
updated ISO using the installer worker. The recovery key unlocked the test
disk, and the VM later rebooted with the emulated TPM after retiring the
temporary key. Secure Boot and SELinux enforcement remained enabled.
The installed placard matched the rebuilt package, a withheld signature was
rejected, and the signed update check passed when the signature was restored.
The temporary disk was removed. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/setup-full/`.

An encrypted NVIDIA VM also upgraded from the earlier signed build to the
exact compact release digest. The unsigned offer left no deployment staged.
The signed offer staged and booted, then Monet rolled back to the earlier
image. TPM unlock, Secure Boot, SELinux enforcement, and the saved file's
checksum survived both restarts. Signed channel checks passed after each
restart. The disposable disk was removed. The lowest SSD free space was
76.77 GiB. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/encrypted-nvidia-upgrade/`.

The same Setup ISO also completed the graphical wizard on AMD/Intel with
encryption enabled. QEMU recorded zero writes to the installation target
before drive confirmation. The wizard displayed the recovery-key page and
restarted into Secure Boot enrollment. The installed image rebooted with TPM
unlock and SELinux enforcing. Its signed update check passed and the clock
placard matched the package checksum. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/setup-graphical/`.

The updated Fedora fallback also completed a graphical AMD/Intel install.
The disposable disk received zero writes before confirmation. Anaconda
created the named administrator, left the root password locked, and restarted
from Reboot System into Secure Boot enrollment. It booted the rebuilt image
and, after a second boot, rejected an unsigned offer and passed the signed
update check. The disposable disk was removed. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/fallback-full/`.

Windows USB Maker also wrote both updated ISOs in an isolated Windows 11 VM
using the exact executable in the local bundle. When the mirror returned
404 for Setup, the Maker selected the Fedora fallback and fetched its release
checksum. Full read-back on both disposable 4 GiB USB disks found 13 changed
bytes per disk. All were disk-size adjustments in the GPT and protective MBR.
Both partition tables and their backup headers passed CRC checks. Under
Secure Boot, the Setup USB reached Hello and the fallback USB reached its
installation summary without writing to the target disk. The temporary
Windows and USB disks were removed. The lowest SSD free space in the two
write tests was 74.58 GiB. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/windows-usb/`.

The ThinkPad's installer launchers opened both current ISOs with roughly
77 GiB free on the SSD. Each used a memory-backed guest disk, reached its
installer and connected to its isolated registry. Disk and firmware state
survived stopping the guest. Reset removed both, and the launchers refused
to allocate a second memory-backed installer disk while the first existed.
Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/launcher-qa/`.

Seven app launch samples per variant ran on the ThinkPad with private Wayland
outputs. Median Settings ready-frame time was 647 ms at the pinned source
revision and 656 ms in the candidate preview. Store was 547 ms and 558 ms.
Files took 369 ms on the installed baseline and 385 ms in the candidate
account preview to map a window and list 1,000 local entries. The installed
Monet 0.9.8 system's recorded startup was 52.731 s, including firmware and
loader. The laptop was on AC. A candidate boot, repeated cold boots and
shutdowns, physical sign-in readiness, and the matching Windows and idle
battery measurements remain open. Evidence is under
`target/098-5-local/desktop/followup/compact-refresh/physical-bench/`.

The ThinkPad also ran eight Store rendering checks at 150% with the final
NVIDIA image's QML. All ten Store QML file checksums matched the image. The
checks covered screenshots, fallback pictures and icons, and section banners
in Qt's basic and threaded OpenGL loops. QRhi identified the physical RTX
A500 and the installed 620.70.06 driver. The laptop ran Monet 0.9.8 with a
private KWin virtual output. Evidence is in
`target/098-5-local/desktop/followup/compact-refresh/physical-bench/nvidia-store/`.

KWin's reported panel frames exposed an overlap at 1280×720 with 150%
scaling in the first compact build. On Wayland, Plasma's center anchor
ignores offsets. Monet now positions the middle panel from the left edge,
limits it to the gap between the side panels, and reapplies the limits when
the display scale changes. The Settings helper and the panel resize watcher
use the same layout code. The disposable desktop VM switched layouts,
restored the middle panel, and rescaled to 125% with all three frames on the
same edge and no overlap. The image builds and frame tests are under
`target/098-5-local/desktop/followup/panel-fit-refresh/`.
Both builds passed the frame test with animations disabled in an isolated
session. One direct NVIDIA run on a private virtual output retained its old
middle panel frame after the requested resize. A separate VM upgraded to the
exact signed NVIDIA image and verified its signed channel after reboot. In
the full Plasma session with normal animations, the panels stayed on one
edge with no overlap after restoring the middle panel, moving from 150% to
125% and back, and returning to one bar. The VM used Virtio graphics and its
disposable disk was removed. On the ThinkPad, a private Plasma session
also used the exact NVIDIA panel files and normal animations at 1280×720.
NVIDIA's process monitor confirmed that the RTX A500 rendered the
plasmashell client. Intel drove the virtual KWin output. All seven panel
states passed, including restoring the middle panel, changing between
125% and 150%, and returning to one full-width taskbar. The ThinkPad is
still running 0.9.8 and a complete candidate boot remains open. VM and
ThinkPad evidence is under
`target/098-5-local/desktop/followup/panel-fit-refresh/panel-frames/exact-nvidia-vm/`
and `target/098-5-local/desktop/followup/panel-fit-refresh/nvidia-panel-render/`.

The new images passed bootc lint and signature verification. The new Setup
and Fedora fallback ISOs pin those images. The local publication verifier
read the five rebuilt archive parts and checked both manifest digests. The
preinstalled AMD/Intel VM rejected the unsigned offer, applied the signed
image and passed the signed update check after reboot. The new Fedora ISO
completed a graphical install with zero writes before confirmation. The new
Setup ISO completed an encrypted AMD/Intel install through the graphical
wizard and an encrypted NVIDIA install through its worker. The graphical
wizard also recorded zero writes before drive confirmation. The encrypted
guests unlocked through the virtual TPM after reboot. All three boots ran
with Secure Boot and SELinux enforcing and passed the signed channel check.
Fedora fallback and the NVIDIA Setup guest rejected offers with the
signature withheld. All three disposable disks were removed. The laptop
verified the NVIDIA signature and its 288 image blobs.
Its physical staging launcher requires 74 GiB free and authentication and
stops the stage below 72 GiB. A read-only check counted 264 of the 287
candidate layers already in the ThinkPad's OSTree repository. The other
23 layers total 0.54 GiB compressed and 0.63 GiB uncompressed.

Windows USB Maker then wrote both final ISO hashes in an isolated Windows 11
VM. When the local mirror returned 404 for Setup, the Maker retrieved the
Fedora fallback and its checksum. Each stick matched the final ISO on full
read-back with 13 expected adjustments in the protective MBR and primary
GPT. The primary and backup headers and partition arrays passed their CRC
checks. With Secure Boot on, the Setup stick reached Hello and the Fedora
stick reached Installation Summary with zero writes to its separate target.
The Windows and USB test disks were removed. The SSD stayed above 74 GiB
free. Evidence is in
`target/098-5-local/desktop/followup/panel-fit-refresh/windows-usb/`.

The final NVIDIA digest also passed an update and rollback from an earlier
signed image on an encrypted VM. Withholding the signature rejected the
update before staging. The signed image booted with the virtual TPM and
passed the signed channel check. Rollback rebooted into the earlier image
and verified the signed channel again. Secure Boot, SELinux enforcement,
automatic TPM unlock and the saved file checksum survived both reboots.
The test disk was removed. The SSD stayed above 74 GiB free.
The final source also passed 608 regression checks with no skips, including
desktop layout, native audio, Settings, Store, release tooling, installers
and the Windows setup scripts. Evidence is under
`target/098-5-local/desktop/followup/panel-fit-refresh/encrypted-update-rollback/`
and `target/098-5-local/desktop/followup/panel-fit-refresh/release-full-module-sweep.json`.

### Widget gallery follow-up

At 1280×800 the status label pushed Calendar's Add button outside its card.
The status now wraps above the actions, and the actions wrap as space allows.
Remove all takes a snapshot of the matching widgets before removing them
because each removal changes Plasma's live list. In the installed AMD/Intel
test desktop, Add created a second Calendar and Remove all cleared both.
Selecting Three bars in Light & Wallpaper also restored a deleted middle
bar with its task manager and Trash.

The gallery fix was rebuilt into both signed images and the Linux package.
Both ISOs pin the refreshed image digests. The local release verifier read
all five transfer parts, checked both manifests, and matched the download
checksums. The AMD/Intel test VM rejected an unsigned offer, installed the
signed image, and passed a signed update check after reboot. The saved test
file and previous deployment were still present. The refreshed source passed
608 regression checks. The refreshed Setup ISO completed an encrypted NVIDIA
installation through its worker. The recovery key unlocked the fresh disk,
and the virtual TPM unlocked it automatically on reboot. The installed guest
rejected the unsigned offer and verified the signed channel under Secure Boot
and SELinux enforcement. The refreshed Fedora fallback ISO also completed a
graphical AMD/Intel install with zero writes before confirmation. After two
installed boots, the administrator account was in wheel, root remained locked,
and the guest rejected the unsigned offer before verifying the signed channel.
The graphical Setup wizard also completed an encrypted AMD/Intel install
with zero target writes before confirmation. The VM needed a retry at the
Secure Boot enrollment menu. After enrollment, the virtual TPM unlocked the
disk on reboot and the installed guest verified the signed channel. The
three disposable installer disks were removed. Evidence is under
`target/098-5-local/desktop/followup/gallery-refresh/`.

Windows USB Maker downloaded both refreshed ISOs in an isolated Windows 11
VM. A simulated 404 for Setup selected Fedora fallback. Full read-back found
13 expected GPT and MBR changes on each test stick. Both GPT headers and their
partition arrays passed CRC checks. Under Secure Boot, Setup reached Hello and
Fedora fallback reached Installation Summary without writing to its target.
The disposable Windows and USB disks were removed. Windows evidence is under
`target/098-5-local/desktop/followup/gallery-refresh/windows-usb/`.

The gallery build's exact NVIDIA digest also passed a signed upgrade and a
rollback on an encrypted guest. Each boot passed the signed channel check.
The guest rejected the unsigned offer before staging, kept the same test file,
and unlocked through the virtual TPM after the update and rollback.

### Files network interruption follow-up

The KIO HTTP worker returned success after an HTTP 200 response ended early,
leaving an incomplete file under the final filename. The local test advertised
12 MiB and closed the connection after sending 2 MiB. The patched worker
reported the connection failure and retained the transfer under its partial
filename. A new copy after reconnection matched the source SHA-256. The
patched worker also passed the test from both rebuilt image filesystems.
A separate 16 MiB test filesystem returned an out-of-space error, and
the copy succeeded after freeing space.

Both images were rebuilt and signed, and both installer ISOs pin the new
digests. The archive verifier checked both manifests and all five transfer
parts. A fresh graphical Fedora fallback install and an encrypted NVIDIA
Setup worker install both rejected unsigned offers and passed signed update
checks after reboot. Both installed guests repeated the Files network and
full-destination tests successfully. The NVIDIA guest also verified the
recovery key and automatic TPM unlock. The VM disks were removed. Installer
evidence is under `target/098-5-local/desktop/followup/files-http-refresh/`.

The graphical Monet Setup wizard completed an encrypted AMD/Intel install
from the refreshed Setup ISO. The VM recorded zero writes before drive
confirmation. It completed Secure Boot enrollment, restarted with TPM
unlock, and verified both the shipped HTTP worker and the signed update
channel. The installer disk ran in RAM, was removed afterward, and the SSD
had at least 65.68 GiB free during the run.

Windows USB Maker wrote both refreshed release ISOs from an isolated
Windows 11 VM. A 404 for Setup triggered the Fedora fallback. Both
sticks passed full read-back and primary and backup GPT checks. Setup
reached Hello under Secure Boot. Fedora fallback reached Installation
Summary under Secure Boot with zero writes to its target. The test disks
were removed, and the Windows runs recorded at least 65.87 GiB free.
See `target/098-5-local/desktop/followup/files-http-refresh/windows-usb/results.json`.

An encrypted NVIDIA VM first rejected the refreshed image with its signature
withheld, then installed it and verified the signed channel after reboot.
The installed gallery, panel files and HTTP worker matched the candidate.
Rollback rebooted into the previous image and passed the signed channel check
again. Both deployments unlocked with the virtual TPM and retained the saved
file checksum. The disposable disk was removed. The SSD had at least 65.59
GiB free throughout the run. Evidence is in
`target/098-5-local/desktop/followup/files-http-refresh/encrypted-update-rollback/results.json`.

The desktop test launcher opened the retained AMD/Intel VM at about
65.5 GiB free, reached Plasma with the exact signed release image and
verified the update channel again. Its loopback VNC URL completed the
RFB handshake. A shutdown requested immediately after launch completed
once the guest was ready. The lowest observed free space was 65.45 GiB.
See `target/098-5-local/desktop/followup/files-http-refresh/viewer-launcher/results.json`.

The final AMD/Intel and NVIDIA image filesystems each ran four clean Plasma
sessions using simulated displays at 1280×720/150%, 1366×768/125%,
1080×1920/150%, and 3840×2160/200%. The three default widgets fit without
overlap. Each session started with one bar, switched to three, restored
the middle bar with its task manager and Trash, and returned to one bar.
The tested filesystems' OCI layer chains matched the release manifests.
See `target/098-5-local/desktop/followup/files-http-refresh/layout-final/results.json`.

The archive verifier regenerated the five OCI transfer parts in RAM and
checked their hashes, both extracted manifests and the release downloads.
It removed its temporary files and recorded at least 65.44 GiB free on the
SSD. The local bundle's ARCHIVE-REPACK.md includes this path.

The Windows ZIP, Linux package and both final image filesystems contain
the same Bridge executable, installer and updater. The hashes match the
Windows VM evidence for no staged update, a stalled download and a verified
package installed with no additional mirror requests. The stalled-download
run requested a Windows restart about 0.2 seconds after opening Back to
Monet. The staged update run reached the installed Monet guest within a
45-second observation window. These are VM timings. See
`target/098-5-local/desktop/followup/files-http-refresh/bridge-payload/results.json`.

The final Setup and fallback ISOs both contain the same signed EFI shim
in the ISO boot directory and the USB EFI partition. The ThinkPad currently
has Secure Boot disabled and its firmware database lacks both of the shim's
Microsoft third-party CA issuers. The firmware boot test is still pending.
See `target/098-5-local/desktop/followup/files-http-refresh/efi-final/results.json`.

The retained desktop VM booted the exact final AMD/Intel manifest and
repeated the Store disk-full checks on a 96 MiB guest tmpfs. User and system
Flatpak installs each kept the failed job with a no-space error and left
the app absent. After freeing space, retry installed the app in both
scopes. The test left at least 65.40 GiB free on the SSD. See
`target/098-5-local/desktop/followup/files-http-refresh/store-destination/results.json`.

In the exact signed AMD/Intel guest, a Flatpak install used a repository on
a removable QEMU USB mass-storage device. QMP removed the device with an
object download in progress. The guest kernel recorded the disconnect and
write errors, and Store retained the failed job. After reattaching and
remounting the disk, Flatpak confirmed that the app was still absent.
Store's retry installed it and the payload checksum matched. The guest
disk overlay and USB test disk were removed. See
`target/098-5-local/desktop/followup/files-http-refresh/store-drive-disconnect/results.json`.

The ThinkPad staging script ran in a disposable VM with the final NVIDIA
image. It staged the signed image, checked its signed channel after reboot,
and rolled back to the prior AMD/Intel image. The /etc/containers file
hashes matched before staging, after staging, after the signed check and
after rollback. The NVIDIA guest reached graphical.target with Secure Boot
and SELinux enforcement. A follow-up boot of the same signed image identified
the failed units as nvidia-cdi-refresh.service and nvidia-cdi-refresh.path.
The guest had only a Virtio GPU. The CDI service logged that nvidia-smi
could not reach a driver and hit its restart limit. Both unit files matched
the installed ThinkPad files, where CDI succeeded on 0.9.8 with its RTX
A500. The new NVIDIA Flatpak timer was active in the guest. Its sync service
was absent from the graphical boot critical chain. The full candidate
still needs a physical boot. See
`target/098-5-local/desktop/followup/files-http-refresh/nvidia-boot-diagnosis/results.json`.
The SSD retained at least 65.24 GiB free and the RAM disk overlay was removed.
A read-only check on the ThinkPad found OSTree references for 264 of 289
layers. The missing layers total 0.54 GiB compressed and 0.63 GiB expanded.
See `target/098-5-local/desktop/followup/files-http-refresh/stage-launcher/`.

When the SSD dropped below 65.25 GiB free, the desktop test launcher
booted the retained signed AMD/Intel VM using a RAM disk overlay and a
RAM copy of its firmware. The persistent disk and firmware were mounted
read-only. Plasma and the signed check passed. The launcher shut down
the guest, removed the temporary files, and recorded 64.92 GiB minimum
free space. See
`target/098-5-local/desktop/followup/files-http-refresh/desktop-ram/results.json`.

Both installer launchers started at about 64.8 GiB free with their guest disks
in RAM. Both reached their local image registry, and neither wrote to its
installation target. Reset removed both temporary disks. This verifies the
lower-footprint launcher path. The full installs are recorded above. See
`target/098-5-local/desktop/followup/files-http-refresh/installer-low-space/results.json`.

The local probe, results and build rehearsal are under
`target/098-5-local/desktop/followup/gallery-refresh/files-recovery/`. The
ThinkPad's 0.9.8 boot and sign-in baseline is under
`target/098-5-local/desktop/followup/gallery-refresh/physical-baseline/`.

### Notification controls and focus-timer preferences (2026-10-27–28)

Notifications offers one hour, four hours and tomorrow at 08:00 local time, with
the actual deadline shown in Settings and a compact caption in Quick Settings.
Expired settings read as off. Hour durations align with Plasma's minute clock;
tomorrow remains 08:00 across daylight-saving changes. Settings serializes requests,
verifies the actual value, keeps failure/Retry visible and reserves feedback space
so the controls do not move when a change completes. Tab focus scrolls controls into
view. Per-app muting changes popup permission without changing history preferences.
Sound configuration opens the native per-app controls: Plasma's temporary
`NotificationSoundsMuted` marker is no longer exposed as a global sound preference.

Focus timers now keep an existing longer quiet period and restore the previous
value only while they still own the setting. A later manual choice wins, including
changes outside Monet Settings. A private, atomic record survives helper/Plasma
restarts, distinguishes overlapping timer widgets and preserves the first timer
if a second timer's write fails. Rapid start/pause/resume requests are serialized
and coalesced to the latest intent.

Validation: focused helper and QML tests cover deadlines, time zones, failed or
immutable writes, expiry, real Settings buttons and keyboard scrolling, overlapping
timers, restart recovery, newer manual choices and request ordering. Live VM checks
cover notification controls at 100% and 200%, native inhibition and expiry, per-app
muting and grouped history, plus the compact "Until tomorrow" bar caption. Real
KConfig writes confirm that focus preserves pre-existing and newer manual choices
and the remaining timer. Starting and resetting the actual Timer widget preserves
the previously selected one-hour deadline. The VM is left at 100%, with manual
quiet off and test timers closed; wallpaper artwork and appearance choices remain
unchanged.

The native popup/history findings from this pass are addressed by the next slice
below. Native app discovery still records an app when its first popup is shown,
not merely when a notification arrives during quiet time. Further accessibility
and real-hardware checks remain release work.

### Native notification retention and muted messages (2026-10-28)

`image/notifications` builds the existing Plasma notification applet with minimal
QML policy changes. Dismissing a non-transient critical popup marks it expired in
the native model without closing the sender's notification, preserving available
actions in history. The tooltip says **Dismiss to history**. Messages from muted
apps/services are placed in history immediately; unmuting cannot replay them.
Muted transient messages are closed, and native history exclusions still apply.
The native applet identity, daemon, C++ implementation, grouping, replies and job
UI are retained. History remains session-local and actions depend on the sender.

Validation on Plasma 6.7.5 / Qt 6.11.2 in the Monet VM:

- [x] Built the exact-version applet with the new QML and loaded it through a
  temporary `QT_PLUGIN_PATH` service override; confirmed the loaded binary.
- [x] Dismissed a critical popup, reopened Notifications and activated its Open
  button. The still-running sender received `open` after dismissal.
- [x] Sent normal and critical messages while the app was muted. Unmuting showed
  no old popups; grouped history retained both, and the critical action worked.
  A new message after unmuting appeared normally.
- [x] Popup/history stayed inside the screen at 200%. Clear History removed the
  two remaining test messages; reopening history at 100% showed it empty.
- [x] `tests.test_notification_bundle`,
  `tests.test_notification_policy.NotificationPolicyProcess`,
  `tests.test_notifications` and `tests.test_settings_feedback` pass: 28 outer
  tests, including a subprocess running eight checks against Plasma's real model
  on an isolated D-Bus session. These cover muted actions, service muting,
  transient messages, history filters and native ClearExpired. They also cover
  muting several active messages at once and replacing an existing message:
  its body/actions update in history without reappearing as a popup, matching
  Plasma's native replacement semantics. Seven delivery
  checks reject mismatched runtimes/plugins, damaged files, missing libraries
  and unsafe destinations, and preserve an existing file after a failed copy.
- [x] CMake install stripped the temporary sysroot library path. Captured and
  verified the real VM's runtime manifest, sealed the binary/source bundle, and
  exercised installation with its final writes redirected to a private staging
  directory. The complete patched upstream source and licenses are bundled.
- [x] Removed the temporary plugin override and test notification preferences;
  `plasmanotifyrc` matches its original empty backup. Plasma again loads the
  system applet. Scale is 100%, the four original widget positions are intact,
  and wallpaper artwork/preferences were not changed by this work.
- [ ] Build and boot the complete Monet image on both supported image variants.
  The new Containerfile stage derives from the final runtime, rejects dependency
  drift and verifies the bundle before replacing the native plugin. Its full
  package-install/image pipeline has not yet been exercised.
- [ ] Review distributor patches when moving to another Plasma release, and
  validate native replies, jobs, screen-reader navigation and real hardware.

The native fix is integrated into image sources, not permanently installed over
the VM's immutable system plugin. Its test build is in
`/tmp/monet-notifications-build`; logs are `build-install.log`, `install.log` and
`/tmp/monet-native-delivery-tests.log`. The general Linux tarball deliberately
does not carry a binary tied to one image's Plasma version.

### Everyday-language search (2026-10-28)

Settings and the app menu use `monet-quick search` with a shared catalog of 14
navigation destinations. English and translated aliases are matched together,
ignoring accents/case and optional question words. Result IDs are allowlisted;
queries cannot become commands. Settings supports `PAGE#CONTROL` links, scrolls
the destination into view and gives it visible keyboard focus. Calendar results
open the existing Monet calendar with its shared notes through `plasmawindowed`.
The Windows-files destination explains unavailable/locked/asleep states and only
offers Open folder when the current account can access the actual shared folder.

Validation:

- [x] `tests.test_everyday_search`, `tests.test_notifications.NotificationUI`
  and `tests.test_settings_feedback`: 24 checks pass in the VM. Sixteen are search
  checks, including the real Settings UI and the real menu representation with
  inert native app models. They cover immediate Enter, stale responses, failure
  and same-query retry, safe routes, translated aliases, missing audio hardware,
  narrow/wide row transitions and focus returning from a long native result list.
- [x] The menu's ListView focus-scope handoff now focuses the native delegate:
  focusing only the view could return focus to its last active suggestion.
  Returning to suggestions uses their content coordinates, so they remain visible
  after scrolling. A failed suggestion lookup cannot auto-launch a native result.
- [x] In the live VM, "make text bigger" opened and focused Size of everything;
  "headphones" opened Sound; "birthday" opened the shared calendar and showed
  the existing note. Settings Ctrl+F, "Windows files", Enter opened the actual
  Storage explanation for a VM without Windows configured.
- [x] At 200%, Settings results and destination controls fit, including Windows
  files and the no-audio-device explanation. Arrow keys moved from the menu's two
  headphone suggestions into native results and back; Enter opened the selected
  Monet result. Scale returned to 100%, all four original widget positions remained,
  the original Settings window-size file was restored, and the calendar host config
  and note-file checksum were unchanged. No wallpaper artwork/preferences changed.
- [x] Translation extraction/build and `tools/make-translations.py --check` pass.
  New messages/aliases are available for translators; this is not a claim that
  every new phrase has been translated into every supported language.
- [ ] Validate a real Windows shared folder and locked/sleeping drive states on
  dual-boot hardware; backend tests cover these states without mounting drives.
- [ ] Review real screen-reader navigation, translated phrases and RTL layouts.
  Native KRunner ranking is unchanged and can still include weak suggestions.
  The standalone calendar retains Plasma's host window; this slice does not
  introduce a separate calendar application.

The existing VM bench helper, Settings and menu copies were updated for the live
check; this is not an image/release installation. Their prior copies are at
`~/.local/state/monet/search-polish-backup-20261028`. Test logs are
`/tmp/monet-search-tests.log`; screenshots on the host include
`%TEMP%/monet-size-ready.png`, `monet-settings-files-200.png`,
`monet-menu-headphones-return-200.png` and `monet-sound-200-ready.png`.

### Return summary and recovery actions (2026-10-28)

The focused run passed **90 checks** without skips:
`tests.test_return_summary`, `tests.test_resume`, `tests.test_files_session`,
`tests.test_browser_session`, `tests.test_everyday_search`, `tests.test_settings_feedback`,
`tests.test_look.YourAppsAgainAfterWindows` and `tests.test_look.GamesTheApp`.

- [x] Durable outcome tests cover completion, missing-app reinstall/retry, stale trip buttons,
  expired/same-boot checkpoints, malformed summaries, interrupted summary writes, actual-lock
  busy state, dismissal and partially missing editor files. Browser tests distinguish verified
  tabs from normal startup and private-session exclusion.
- [x] Actual Settings QML tests cover repeated keyboard actions, persistent failure/retry,
  stale refreshes after dismissal, polling focus preservation, direct Tab entry into the card,
  narrow rows and literal filenames. The Games restart explanation and buttons fit a
  760×520 window without invoking any switch.
- [x] Live VM: saved test document reopened; missing document/app were reported honestly.
  Review return in notification history opened Settings at the card. After installing a
  controlled test app, Retry pending opened it once without reopening the existing editor.
  Open app raised its existing window. Dismiss by keyboard at 200% forgot recovery metadata
  while preserving the saved test document. Both 100/200% layouts were inspected.
- [x] Returned to 100%; original widget positions and notes checksum were unchanged.
  Restored Settings' previous size file and removed the controlled launcher/processes.
  No wallpaper artwork or preferences changed.
- [x] `cargo check -p monet --bin monet --target x86_64-unknown-linux-gnu` and translation
  extraction/build/check pass. The Linux binary cannot be tested with a Windows-native
  `cargo test`; that attempt fails on its existing Unix-specific APIs. Cross-checking is
  compilation evidence, not a Linux runtime or reboot test.
- [ ] Real Monet → Windows → Monet round trip, real interruption during reboot, measured
  switching time, other user accounts, screen readers and translated/RTL presentation.
- [ ] Explicitly reopen missing editor documents after reconnecting a drive, preserving
  existing tabs; the current recovery UI directs the person to the app and Backups.

Bench backup: `~/.local/state/monet/return-polish-backup-20261028`. The live fixture uses
`/tmp/monet-return-live-20261028/state`, separate from the user's real recovery state.
Logs: `/tmp/monet-return-suite.log`. Host screenshots include
`%TEMP%/monet-return-card.png`, `monet-return-result.png`,
`monet-return-reloaded-ready.png`, `monet-return-tab-fixed.png` and
`monet-return-dismissed.png`. The installed image/boot binary was not replaced.

### Dragging empty app backgrounds (2026-10-27)

Settings, Store and Games share a background drag surface behind their controls.
An unmodified left-button drag starts the compositor's normal window move after
the platform drag threshold. WheelHandler and Flickable leave blank mouse presses
to that surface; wheel, touchpad and touchscreen scrolling remain available.
Qt versions before 6.9 retain their previous mouse behavior inside scroll views.
More Settings' private style also supports dragging blank native widget forms,
excluding buttons, fields, sliders, editors, item views and selectable text.
This does not impose blank-area dragging on unrelated third-party applications.

Validation: the QML frame suite covers blank surfaces, nested scrolling pages,
button clicks, text selection, sliders, drag thresholds, modified drags, wheel
and synthesized touchscreen scrolling. Native Qt tests cover blank form movement
and exclusion of interactive controls. Existing frame and layout checks still pass.

Live Wayland VM checks:

- [x] Drag the Store from its blank sidebar and the gap between home-page sections.
- [x] Drag Settings from space between its wallpaper choices; drag it out of a
  half-screen tile and retain the normal compositor placement behavior.
- [x] Drag More Settings from the blank network form background.
- [ ] Physical touchpad and touchscreen checks on real hardware.

### Passwords development preview (2026-10-28)

See [PASSWORDS.md](PASSWORDS.md) for the pinned source, build and disposable VM fixtures.
This preview is outside the normal image and installer; all credentials used were synthetic.

- [x] Three source-patch checks, eight compiled vault/browser/default suites, and eight
  upstream GUI scenarios (ten Qt passes including setup/cleanup), with no failures or skips.
- [x] Live native UI: wrong password rejected, explicit unlock, lock action, and locked
  startup after restarting. The toolbar fits at the tested 800-pixel window width.
- [x] Real Flatpak Zen extension: pair and approve in the native UI, fill the local form;
  denied access, another hostname and a locked vault leave both fixture fields empty.
- [x] Native encrypted backup, private file permissions, recovery from an independent
  backup copy, and rejection of corrupted ciphertext without changing the original.
- [x] Reconnect after replacing the running app by using the extension's Reload button;
  the existing association survived. Automatic reconnect remains unfinished.
- [ ] Windows access, multiple profiles, real-site save/update, hostile frames, suspend,
  accessibility/RTL, package upgrades, and a complete integration security review.

Screenshots, logs and the development build with corresponding upstream source are saved
on the host under `target/passwords-preview/`. See the detailed record for known permission
dialog visibility and reconnect limitations. No real credentials were imported.
Restored `ai-before-passwords-1028`; the VM is running, the fixtures are absent, and the
original notes checksum is unchanged.

### Password consent and familiar app discovery (2026-10-28)

Follow-up in the Monet VM, using the isolated password preview and user-local copies of
the current Settings, menu and Store. No real credentials or documents were imported.

- [x] Real Zen extension: submit a new login, cancel without saving, then approve New and
  verify the encrypted vault contains one new account. Submit a changed password, cancel
  the native update prompt and verify the original value remains; approve the next update
  and verify the same account changed with its previous password retained in history.
- [x] The loopback fixture serves only its fixed pages, rejects file/directory requests and
  oversized submissions, and discards submitted values. Five patch/fixture tests pass.
- [x] Familiar names resolve to installed apps; user-hidden, missing and unusable TryExec
  launchers stay out of suggestions. Settings opens external results, retains a retryable
  error when the launch helper cannot start, and clears it after a successful retry.
- [x] Reproduced the menu's delayed-header clipping in the real QML test (`y = -96`);
  the fix keeps new suggestions visible without taking keyboard focus from the search.
  Existing keyboard movement between suggestions and native results still passes.
- [x] Live desktop: Settings Finder → Files and menu Task Manager → System Monitor.
  At 200%, Nautilus → Files works by keyboard and the suggestion is fully visible.
  System Monitor reports missing VM sensors; only discovery/launch was verified here.
- [x] Store: AirDrop shows LocalSend; Pages shows LibreOffice/ONLYOFFICE and opens the
  LibreOffice details page. iCloud gives the no-suggestion fallback. The new explanation
  wraps correctly at 100/200%; no install or removal was started.
- [x] **44 checks, no skips:** `tests.test_passwords_preview`, `tests.test_everyday_search`,
  `tests.test_look.OurOwnStore` and `tests.test_store_downloads.DownloadUI`.
  Translation extraction/build/check and scoped whitespace checks pass. New text has English
  fallback pending translation. No native vault rebuild was needed for fixture-only changes.
- [ ] Real-site and multi-step password detection, hostile frames, multi-profile setup,
  cancelled-update wording, accessibility/RTL and the complete integration security review.
- [ ] Actual browser/document migration, native-format round trips, nearby file transfer,
  new OS image build/boot, physical hardware and a complete Windows return.

Host screenshots and check records: `target/passwords-preview/save-update-20261028/`
and `target/switcher-preview/`. Store suggestions were checked against the official
[LocalSend](https://localsend.org/), [Kdenlive](https://kdenlive.org/),
[Ardour](https://ardour.org/requirements.html) and
[LibreOffice](https://books.libreoffice.org/en/index2.html) documentation.
LocalSend needs its app on both devices; no AirDrop protocol support is claimed.

Restored `ai-before-passwords-switchers-1028`. The VM is running, the temporary preview
build/profile and switcher overrides are absent, and the original notes checksum is
unchanged (`f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`).

### Migration and regression check (2026-10-28)

Started from checkpoint `ai-before-migration-checks-1028`. Tests used the checkout uploaded
to `/tmp/monet-tests`, a disposable Zen profile, the existing checksum-verified Passwords
preview and synthetic documents/bookmarks. LibreOffice 26.8.1.1 was installed temporarily
from the user Flathub remote. No real logins or documents were imported.

- [x] Real extension: same-origin frame fill, foreign child refusal, and refusal when the
  saved site is embedded by an unrelated parent. The negative checks were repeated with
  the vault explicitly unlocked; the last showed the untrusted-iframe warning. A username-only
  first step and password-only second step both filled through the actual UI. Idle locking
  required a fresh unlock. See [PASSWORDS.md](PASSWORDS.md) for the reusable fixture commands.
- [x] Actual Zen **Library → Import and Backup → Import Bookmarks from HTML**: import the
  Windows adapter's HTML into an existing disposable profile. Three bookmarks appeared;
  preexisting bookmark GUIDs, a nested Work folder, Swedish characters and a URL containing
  `?a=1&b=2` survived. The source export's checksum remained unchanged.
- [ ] Repeat import: the same three bookmarks are added again. Existing records are preserved,
  but duplicate handling is unfinished. Repeat the same native import to reproduce.
- [ ] Corrupt import: a file containing non-bookmark bytes adds nothing and preserves all
  bookmark GUIDs, but no visible error or zero-import explanation appears. Profile selection
  and a clear result/retry flow remain required; no real browser profile was modified.
- [x] LibreOffice reads and writes synthetic DOCX, XLSX and PPTX copies and exports each to
  PDF. Inspection of the resulting files confirms Swedish text, DOCX bold text/table/image,
  the spreadsheet's `SUM(B2:B3)` formula and cached value 20, and the presentation's slide/text.
  Each PDF has one page with the expected text.
- [x] Live default-app launch: Writer opens DOCX, saves an added sentence after the format
  warning; Calc opens XLSX, changes 12.5 to 22.5 and saves the formula and recalculated value
  30 after its format warning. Saved files were inspected independently. Impress displays
  the PPTX, Okular opens the exported PDF and Gwenview opens the PNG. Original fixture
  checksums remain unchanged.
- [ ] Complex Office documents, macros, Microsoft Office/iWork comparison, native Apple
  formats, font/layout fidelity, PDF/photo editing, removable media and phone/nearby sharing.

The broad suite exposed an actual `monet-quick` regression: assigning a local search result
to `ok` made Python treat the shared command helper as an uninitialized local in timezone,
NTP and security branches. Renamed the result to `opened`. The new regression check exercises
the affected clock/security dispatch with command execution mocked; the timezone check also
mocks the shared executor, so tests cannot change the VM's clock or security settings.
Two source scanners now ignore generated `__pycache__` directories. The native Settings
launch check mocks `execvpe`, matching the implementation; its old `execvp` mock let the
test process replace itself and crash before the suite could finish.

Validation after these fixes:

```text
python tools/vm.py tests
Ran 730 tests in 70.964s
FAILED (failures=7, skipped=13)

python tools/vm.py tests tests.test_passwords_preview tests.test_everyday_search \
  tests.test_look.Scripts.test_quick_takes_only_zones_and_locales_it_knows \
  tests.test_look.FirmwareIds tests.test_look.OneOfEachName tests.test_more_settings
Ran 39 tests in 10.352s
OK
```

That baseline was **not green**. The seven failures below were resolved in the subsequent
safe-import pass recorded below; this table preserves the original diagnosis:

| Test | Observed mismatch / next action |
|---|---|
| `ASmootherTripToWindows.test_settings_ask_bridge_for_a_task` | Old `args.extend` assertion; protected departure now passes the task through `command.args`. Update the contract check around the current route. |
| `MonetSettings.test_settings_search_speaks_every_language` | Old single-string search assertion; current search matches individual words. Update coverage without losing translated/accent-folded behavior. |
| `SnapLikeWindows.test_settings_is_a_window_like_the_others` | Old direct Escape-close assertion; Escape now clears search first. Match the current interaction. |
| `WhatOtherSystemsHave.test_a_new_account_is_welcomed_once` | Old `which` route assertion; Settings now validates the parsed destination. Retain welcome-once coverage. |
| `Scripts.test_quick_settings_commands_take_only_their_own_values` | Rejects read-only `kreadconfig6` calls used for notification error feedback; no writes occurred. Distinguish reads from mutation. |
| `PlasmaPackages.test_inline_components_do_not_reach_outside` | WeatherDetails inline components refer to their outer `details` context. Resolve the existing component-scope rule. |
| `OneGamesFolderForBoth.test_widgets_buttons_are_monets_pills` | Sound's two microphone controls use `PlasmaComponents.Button`. Bring them into the established Monet control style. |

Thirteen reported skips comprise eight notification cases deliberately delegated to an
isolated D-Bus subprocess (its wrapper passed), plus five unavailable-runtime checks:
PowerShell parsing, NumPy photo painting, and three Node-based geometry/migration checks.
No Rust rebuild, new OS image, privileged firmware/inhibitor check or real Windows return
was performed in this pass. Preexisting failed units were input-remapper, its user autostart
and plasma-ksplash; they were already failed before testing.

Host evidence: `target/vm-migration-checks/final-suite.log`, `final-focused.log`, per-group
diagnostic logs in `suites/`, document originals/results in `documents/`, bookmark snapshots
in `bookmarks/`, and live screenshots in `screenshots/`. These are ignored test artifacts.

Restored `ai-before-migration-checks-1028`. The VM is running; temporary vault build/profile,
document/bookmark fixtures and the user LibreOffice installation are absent. Zen is again
the only installed Flatpak app. The original notes checksum is unchanged:
`f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`.

### Safe bookmark import and test-baseline repair — 2026-10-28

Checkpoint: `ai-before-import-recovery-1028`. Synthetic bookmarks only, two disposable
Zen profiles, a local HTTP fixture, and an account-local Settings preview; no production
bookmark database was written by Monet. The existing wallpaper was unchanged.

Settings → Default Apps → Browser bookmarks now lets the person choose an HTML export
and a specific Zen profile. Review counts new, already bookmarked/repeated, and unsupported
links; it displays a small sample before preparing a private HTML file. Source or destination
changes require a fresh review. Existing bookmarks are read through a read-only transaction;
an open profile is refused. Zen's native Library performs the import into its own named folder.
Checking reads that folder from the chosen profile, rather than equating launch with success.
The latest import for a profile can be checked after restarting Settings. Undo remains the
native action of removing the imported folder; manually importing a prepared file twice can
still create duplicates, which the check reports.

- [x] Live review: four exported links became one new link, two duplicates and one unsupported
  `javascript:` link. The existing bookmark was made through Zen's normal Add bookmark UI.
- [x] Native Library import: the selected profile received the new link and nested folder;
  all five preexisting bookmark GUID/title/URL tuples remained unchanged. A fresh review
  reported zero new links. The other disposable profile still reported two new links, and
  the original profile's database checksum was unchanged.
- [x] Review with the target profile open returned `busy`; no empty-profile fallback.
  Verification after closing the profile reported exactly one imported link.
- [x] Deliberately importing the prepared file twice through Zen reported one duplicate.
  Removing both test import folders through Zen preserved the preexisting bookmarks;
  verification then reported no imported links, and a new review offered the missing link again.
- [x] Restart Settings, choose the same profile, and check the previous import: its receipt
  survived and the result reflected the current bookmark database. Profile selection has a
  visible label and radio-button accessibility semantics. Live layout and result controls
  remained reachable at 100% and 200% app scale.
- [x] A slow default-app query initially pushed the bookmark section below the visible area
  after following a direct link. Anchor navigation now waits for that query before scrolling.
  A delayed-helper UI regression covers the actual geometry, alongside keyboard profile
  selection, disabled/pending controls, errors, and preparation versus verified success.
- [x] Backend regressions cover corrupt and oversized exports, excessive link counts,
  unsupported URLs, non-regular input files, corrupt profile lists/databases/receipts,
  external profile paths, changed previews, private output permissions, failed export or
  receipt writes, failed launches, and exact profile selection. Failed writes clean up only
  their newly created incomplete files.

The previous seven baseline failures are fixed without dropping their contracts: five
assertions follow the current search/navigation/departure/read-only settings behavior;
weather's inline components now pass focus requests through their own signal; microphone
and notification Retry buttons share a painted control with Space/Enter and disabled-state
coverage. Installer/uninstaller and CI include the bookmark helper and shared button.
The translation catalog was regenerated; untranslated new text uses the English fallback.

The VM temporarily received Node 24.22.1, PowerShell 7.6.9 (official release checksums
verified), and NumPy 2.5.4 so the five formerly unavailable checks could run. They are test
tools only, not new dependencies of the shipped OS.

```text
python tools/vm.py tests
Ran 746 tests in 77.026s
OK (skipped=8)
```

The eight reported skips are notification cases delegated to the passing isolated D-Bus
runner. Non-fatal fork/Pillow deprecation and Qt lifetime warnings remain in the log.
Evidence: `target/import-recovery/final-suite3.log`, `live-before.json`, `live-verified.json`,
`live-duplicate.json`, `live-undo.json`, and the live PNG screenshots in that folder.

Still open: exports from real installations of each source browser, custom Zen profiles
outside its Flatpak directory, screen-reader/RTL review, translations, and a full image
build/boot. This pass does not complete password migration, missing-document reopening,
editor cursor/split recovery, USB installation, firmware/Windows return, or real hardware
sleep/wake/peripheral tests. The native portal file picker also showed a mixed light/dark
theme in this VM and needs a separate theme integration check.

Restored `ai-before-import-recovery-1028`; the VM is running and SSH responds. The temporary
Settings preview, browser profiles/import receipts, Node/PowerShell runtimes and NumPy
installation are absent. The original notes checksum is unchanged:
`f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`.
The cleanup assertion is saved as `target/import-recovery/restored.json`.

## Editor windows and missing documents — 2026-10-28

Checkpoint: `ai-before-editor-recovery-1028`. Run the focused checks inside the VM:

```text
python tools/vm.py tests tests.test_editor_session tests.test_resume tests.test_return_summary tests.test_multi_restore tests.test_departure tests.test_trip_lifetime tests.test_workspace_return tests.test_files_session tests.test_browser_session
Ran 111 tests
OK
```

The live Wayland fixtures in `target/editor-recovery/` covered two independent Kate
windows and one KWrite window. Verified horizontal and vertical two-pane Kate layouts,
active tabs and either active pane, visible cursor offsets, separate window positions,
minimized capture/restoration and multiple KWrite tabs. A file renamed out of the way
after checkpointing stayed pending without creating a blank file. Returning it and
retrying reused the existing editor; another retry left the same three window IDs.
A separate cancellation kept an editor's unsaved buffer, PID, window ID and geometry
intact while reopening the closed sibling and KWrite. Native session receipts were
private, and Notes retained its original checksum.

Regression tests include all-files-missing, a closed original editor, manually reopened
files, slow launches, duplicate saved windows, stale requests, malformed pending lists,
PID reuse and legacy checkpoint recovery. Settings' Retry documents uses the existing
serialized worker and passes keyboard and narrow-window layout checks.

The VM was returned to the checkpoint after testing; the temporary editor helper,
fixture documents/windows and recovery records were removed by rollback. Existing clock
preview changes from the preceding task remain in that checkpoint. Real USB disconnects,
Windows firmware/reboots, a rebuilt image, nested splits, same-process multi-window editors,
inactive-tab cursors remain unverified or unfinished. Save As during departure is covered below.

## Save As during protected departure — 2026-10-28

Checkpoint: `ai-before-save-as-1028`. The focused VM run passed 132 tests, including
the parent check that runs ten isolated Qt departure cases:

```powershell
python tools/vm.py tests tests.test_departure_documents tests.test_editor_session tests.test_resume tests.test_return_summary tests.test_multi_restore tests.test_departure tests.test_trip_lifetime tests.test_workspace_return tests.test_files_session tests.test_browser_session
```

Real Kate/KWrite dialogs under Wayland covered these synthetic-document flows:

- Untitled KWrite → native Save prompt → first filename → close → controlled return.
  The final checkpoint and reopened tab used the newly saved path; retry created no duplicate.
- Modified Kate → cancel its close prompt → Save As → close while Monet waited.
  Recovery opened the new name; the old file's contents were unchanged.
- Cancel KWrite's Save As chooser → switch still waiting → cancel Monet.
  No restart acceptance was sent; the same editor PID retained its modified document.
- Rename and close Kate, then cancel Monet while an unsaved KWrite still blocked departure.
  Kate reopened its latest path once; KWrite retained its PID and modified state, and the
  previous saved filename was unchanged. Retrying added no windows.

The privileged helper was replaced only in the fixture by a pipe-protocol stand-in; it
recorded acceptance/EOF without reboot or firmware access. Evidence is in
`target/save-as/live-results.json` and the screenshots/scripts alongside it. The initial live
run caught D-Bus teardown removing an editor object before its bus name; closed watched PIDs
are now excluded from that query. Regression tests also cover stale/corrupt native files,
changed files during reads, shared anonymous sessions, distinct named sessions, discarded
untitled documents, cancellation during IPC, and retention of KWrite tab order/cursors.

Source compilation and translation-catalog consistency are checked separately. Shared
anonymous editor sessions, independent exits before Monet's close request, richer layouts,
installed-image behavior and real Windows/USB round trips remain limited or untested.

Restored `ai-before-save-as-1028` after testing. Hyper-V took several minutes, then reported
the VM Running; SSH confirmed both fixture directories were absent and the original Notes
SHA-256 was unchanged (`target/save-as/cleanup-results.json`).

## Independent editor exits during switching — 2026-10-28

Checkpoint: `ai-before-independent-exit-1028`. The same focused restoration command above
passed 136 tests, including the parent run of twelve isolated Qt departure cases. Added
coverage proves all editors are watched before any app closes and before privileged
preflight, repeated polls retain the baseline, cancellation during capture cannot install
a late watch, new windows get separate watches, and a newly shared native file invalidates
the older exclusive watch.

In the live Wayland fixture, Monet requested only KWrite's close and continued waiting for
that window. Kate was then edited, saved under a new name and closed manually. Its final
path updated without a Monet close request. Cancelling Monet reopened the latest file once,
retained KWrite's PID and modified state, left the original file unchanged, and sent EOF
without any restart acceptance. Retry created no extra windows. Native dialogs and helpers
were real; only the privileged pipe endpoint was a stand-in without firmware access.
Evidence: `target/independent-exit/verified.json`, fixture scripts and screenshots.

This does not validate switching named Kate sessions mid-departure, a completely new app
family opened after capture, shared anonymous instances, or a real Windows/image round trip.

Restored `ai-before-independent-exit-1028`; the VM returned to Running, SSH confirmed all
fixture files were gone and Notes retained its original SHA-256. Cleanup evidence is in
`target/independent-exit/cleanup-results.json`. Syntax and catalog checks also passed.

## Shared editor sessions and final receipts — 2026-10-28

Checkpoint: `ai-before-shared-editors-1028`. The focused restoration suite passed 151
tests, including the parent run of twelve isolated Qt departure cases. After the final
receipt/cancellation/build guards, 41 focused tests passed (`tests.test_departure_documents`
and `tests.test_editor_bundle`). These cover identity/schema/permission checks, shared
writers, missing receipts, late cancellation, unsupported layouts, atomic-copy failure,
runtime drift and loader-path aliases.

The actual Kate/KWrite 26.08.1 shared library was built in rootless Podman inside the VM.
Disposable editors used a temporary `LD_LIBRARY_PATH`; the VM's installed library was not
replaced. Live checks verified:

- Two anonymous KWrite instances: rename one document and save an untitled document in
  the other. The close button and Quit both produce separate final receipts. Cancelling
  the Save As chooser produces none and keeps switching blocked. Cancelling Monet then
  reopens both final paths with their visible cursors, preserves an unsaved Kate survivor,
  sends no restart acceptance and creates no duplicates on retry.
- Two anonymous Kate instances: horizontal and vertical split layouts retain tab order,
  selected tabs/panes, sizes and visible cursors in their receipts and reopened windows.
- Making the private receipt directory unusable vetoes closing. Disarming permits normal
  close. Malformed tokens are rejected. Adding another main window or a third pane leaves
  the previous capture intact with an unconfirmed warning.
- Native `--tempfile` paths scheduled for deletion stay out of recovery. Saving a permanent
  copy with Save As retains that new path after the temporary original is deleted.

The production component script built and sealed the binary/full-source bundle, and its
installer succeeded in the matching container. It correctly rejected the VM's different
runtime package set (including `libcurl-minimal` versus `libcurl`); this does not validate a
complete Monet image build. Evidence is in `target/shared-editors/`, including `verified.json`,
`kate-verified.json`, `veto.json`, `unsupported-verified.json`, `temporary-verified.json`,
`bundle-verified.json`, build logs and screenshots. Original fixture files and Notes remained
unchanged in the cancellation test.

Real Windows/USB round trips, a full rebuilt image, named-session changes mid-departure,
same-process multi-window restoration and richer layouts remain open. The privileged
endpoint in the live cancellation fixture was a pipe stand-in without firmware access.

Restored `ai-before-shared-editors-1028`. Hyper-V reported Running; SSH confirmed the
fixture directories and build environment were gone, and Notes retained its original
SHA-256 (`target/shared-editors/cleanup-results.json`).

## Nested editor panes and Save As — 2026-10-28

Checkpoint: `ai-before-nested-editors-1028`. All 159 focused restoration tests passed,
including nested-session serialization, bounds/identity/schema checks, missing-pane
pruning, legacy checkpoints, per-process final receipts, D-Bus fallback and Qt departure
tests. The native Kate/KWrite 26.08.1 component compiled in the VM's rootless build
container; only disposable editors used its temporary `LD_LIBRARY_PATH`.

Live native dialogs and production recovery helpers verified:

- Four nested Kate panes (horizontal, vertical, then horizontal) and a three-pane row.
  Save As kept a renamed document in its pane; a first-save during closing kept the new
  document in the middle pane. Cancelling the chooser left the editor open with no final
  receipt and kept its departure watch pending.
- After final receipts and cancellation, both editors reopened with the final filenames,
  tab order, active tabs/panes, visible cursors and relative split sizes. A repeated restore
  made no extra windows. The original file remained intact after Save As.
- Removing a fixture file before return removed only its pane. The remaining nested
  branch retained its layout; the absent path stayed pending. Returning the file and
  retrying reused the editor, and a second retry made no duplicate window.
- Legacy one/two-pane checkpoints, KWrite, repeated views of one document with different
  visible cursors, active-pane identification in the background and refusing to overwrite
  nonzero cursors. Invalid/stale cursor requests left the editor unchanged. A real unpatched
  editor continued using its existing accessibility adapter.

Evidence: `target/nested-editors/evidence.json`, fixture scripts and screenshots. Notes'
SHA-256 stayed unchanged. This slice did not build a full Monet image or perform a Windows
or USB round trip. Same-process multiple windows, inactive-tab cursors and returning late
files to their former pane without disturbing newer work remain backlog items.

Restored `ai-before-nested-editors-1028`. Hyper-V reported Running; SSH confirmed the
fixture directories and build environment were removed and Notes retained its original
SHA-256 (`target/nested-editors/cleanup-results.json`).

## Same-process window identity prerequisite — 2026-10-28

Checkpoint: `ai-before-window-identity-1028`. Built the native prototype in rootless
Podman inside Monet, against KWin 6.7.5, Qt 6.11.2 and Wayland 1.26. The start script
verified matching x86_64 package versions, the exact KWin library hash and resolved
dynamic symbols before loading it in a nested KWin session with its own D-Bus bus.
The VM's main compositor was not modified.

Live fixture checks, repeated with the final scripts in a fresh nested session:

- Two Qt windows in one process resolved to their exact, distinct KWin UUIDs, even
  with identical titles and frame geometry. Minimized windows kept their identities.
- Repeated lookups left focus, stacking, geometry and minimized state unchanged.
- Closing one window removed its identity without assigning it to the surviving sibling.
- Zero/invalid process and surface IDs returned no match. D-Bus exposed only the
  read-only resolver, with no inherited QObject control slots.
- Two raw Wayland connections in one process deliberately reused the same surface ID.
  The resolver refused the ambiguous match; closing one let the remaining connection
  resolve to its original compositor UUID.

The native build and both live test scripts passed. The final nested-compositor log
was empty, and Notes retained its original SHA-256. Evidence is in
`target/window-identity/evidence.json` and `identity-vm.png`; reproducible code and
commands are in [the prototype](../prototypes/window-identity/README.md).

This is a prerequisite, not shipped multi-window editor restoration. Per-window
capture/close receipts, shared unsaved-buffer recovery on cancellation, cross-window
Save As, production image guards and Windows/USB validation still need implementation
or testing. Existing single-window/nested-pane restoration was not changed by this slice.

Restored `ai-before-window-identity-1028`. Hyper-V reported Running; SSH confirmed both
fixture directories and the build container were removed and Notes retained its original
SHA-256 (`target/window-identity/cleanup-results.json`).

## Native multi-window editor interfaces — 2026-10-28

Checkpoint: `ai-before-editor-window-map-1028`. All 163 focused restoration tests passed;
the eight bundle tests passed again after adding the direct Wayland dependency to the
runtime manifest. The final native library and compositor extension compiled in the VM.

Real editor checks in an isolated nested compositor:

- Kate reopened two windows in one process, including a split window, using shared
  native document IDs. Each window mapped to its exact compositor UUID.
- An invalid second cursor request left the first window untouched. A request for one
  window left the other alone; subsequent requests preserved nonzero cursors.
- Save As on a document shown in both Kate windows updated both views to the new path.
  The original file remained intact. Cancelling the native chooser preserved both states.
- Closing and reopening the process retained the two windows' tabs, splitter tree and
  visible cursors. This exercised the adapter directly, not the automatic departure flow.
- Final native checks covered Kate and KWrite: a closed window's ID could not target its
  sibling; unloading the nested compositor extension made multi-window capture return no
  result while ordinary capture still worked; reloading restored exact identity. After one
  sibling closed, the existing single-window departure receipt remained valid.
- The batch resolver rejected invalid/duplicate/over-limit/stale surfaces and real
  same-process Wayland connection collisions without returning partial matches.

The corresponding-source bundle sealed and installed into its matching Fedora container.
The full bundle guard rejected the guest's different transitive packages. Disposable live
fixtures used the separate build after checking matching editor/Qt/KDE versions, exact
Qt and TextEditor library hashes, and all linked symbols. No system editor library or
main compositor was replaced in the VM.

Reproducible final native checks: `prototypes/window-identity/verify-editor.py`, alongside
the resolver fixtures. Evidence: `target/editor-window-map/evidence.json` and screenshots.
Notes retained its original SHA-256. Per-window close receipts, shared unsaved-buffer
recovery after cancellation, compositor image packaging, automatic placement and full
Windows/USB testing remain unfinished; the automatic path still uses one window per process.

Restored `ai-before-editor-window-map-1028`. Hyper-V reported Running; SSH confirmed the
build directory (including compositor/editor fixtures) and container were removed, and
Notes retained its original SHA-256 (`target/editor-window-map/cleanup-results.json`).

## Native editor group departure — 2026-10-28

Checkpoint: `ai-before-editor-group-exit-1028`. All 165 focused restoration tests passed.
The patched editor and compositor prototype compiled in the VM. The reproducible native
fixture is `prototypes/window-identity/verify-group-exit.py BUILD_ROOT`, using the same
isolated nested compositor and runtime checks as `verify-editor.py`.

- Kate and KWrite retained both original window IDs and the same unsaved shared buffer
  when the native close prompt was cancelled.
- Cancelling Monet while a save dialog remained open, then accepting Save, saved the
  document without completing the old close. The single-window path was checked too.
- Save As changed a shared document's path in both windows. Its original file survived;
  cancelling the chooser preserved the previous paths. First-save during group exit kept
  the new document in the correct window, including cancellation and retry of its chooser.
- A failed private receipt write and an unavailable identity resolver left the whole
  group open. A successful receipt reopened both windows in one process with their final
  paths and layout.
- Controller loss invalidated a pending native close. A new controller could arm a new
  token; a stale cancellation could not disarm it. Adding a window after arming vetoed
  closing until the whole new group was captured again.

The tests exercise the native group protocol directly. Automatic multi-window switching,
exact placement, compositor image packaging and a full Windows/USB trip remain open.
The final library passed the existing native multi-window/legacy compatibility fixture too.
Its source bundle sealed and installed in the matching build container. The full runtime
guard rejected the guest's missing/different transitive packages; system editor libraries
and the main compositor were not replaced. Source/binary hashes and native results are in
`target/editor-window-cancel/evidence.json`.

Restored `ai-before-editor-group-exit-1028`. The VM is Running; SSH confirmed the disposable
build, fixtures and container are gone, and Notes retained its original SHA-256
(`target/editor-window-cancel/cleanup-results.json`).

## Native window identity image bundle — 2026-10-28

Checkpoint: `ai-before-window-identity-image-1028`. All 153 focused VM tests passed,
including nine new bundle tests. They cover changed runtime packages/compositor binaries,
invalid destinations, damaged binary/source bundles, missing symbols, build-time library
paths and failed copies preserving the previously installed module.

The production `image/window-identity/build.sh` built and sealed the module in rootless
Podman; installation into that matching container passed. The full guard rejected the
guest's differing transitive runtime. The live fixture used the exact packaged module
after separately checking KWin/Qt/Wayland binary hashes and dynamic linking; nothing was
installed into the VM's main compositor.

- A fresh nested compositor loaded the module with no plugin preference override.
- Exact identities survived identical titles/geometry and minimization; lookups left
  focus, stacking and layout unchanged. Invalid, stale, duplicate and ambiguous identities
  returned no match, including real collisions across Wayland connections in one process.
- A second nested session found the installed plugin but kept it unloaded when
  `monet_window_identityEnabled=false`. No identity object was exported; both windows
  stayed open and the preference remained disabled.

The fixtures now compile the production source, with reproducible checks in
`prototypes/window-identity/verify.py`, `verify-collision.py` and `verify-disabled.py`.
Source/binary hashes and results are in `target/window-identity-image/evidence.json`.
The module's SHA-256 is `04205d992d28a38b6d105d86232d56cb0a1339dfc593bce0014c1de2b00cc463`.

The production build ran in an already provisioned development container, so its
before/after runtime check observed no package changes. The full image build and boot
remain untested. Automatic group capture/departure/recovery, exact window placement and
Windows/USB switching still need integration or validation.

Restored `ai-before-window-identity-image-1028`. The VM is Running; SSH confirmed the
temporary build, fixtures and container are gone, and Notes retained its original SHA-256
(`target/window-identity-image/cleanup-results.json`).

## Targeted missing-file retries — 2026-10-29

Checkpoints: `ai-before-editor-group-recovery-1028` and
`ai-before-editor-retry-guards-1028`. All 152 focused VM tests passed across the runs,
with the 34 affected editor tests rerun after adding delayed-reply coverage. These include
target validation, refusal/timeout handling and the production recovery caller.

The native check is `prototypes/window-identity/verify-retry.py BUILD_ROOT`. In disposable
Kate and KWrite processes inside the isolated compositor it verifies:

- Reopening into an inactive split window adds tabs to that window's current pane.
  Its other pane, selections, cursors, geometry and desktop focus stay unchanged.
- A document modified in the other window is reused as the same unsaved buffer; its
  saved file stays unchanged until the fixture explicitly saves it.
- Duplicate retries and a file alias already open in another pane add no extra tabs.
- Missing files, directories, invalid identities, duplicate/oversized requests and extra
  fields are rejected before mutation. Missing compositor support rejects the operation.
- The production recovery generator opens available files first and retains the missing
  file as pending. An automatic recheck leaves it alone; explicit Retry uses the exact
  owned window, preserves its cursor, and completes without another process or window.
  The reopened tab's displayed text matches the saved file, rather than an empty replacement.

Existing native multi-window capture/cursor checks and group departure tests also cover
Save As, first-save, cancelled choosers, late Save after Cancel, receipt failures and
controller loss. The fixture processes can emit a GLib main-context diagnostic during
Python teardown after their assertions and JSON results; those runs exited successfully.

A fresh guarded source patch matched the compiled editor tree. The corresponding-source
bundle sealed and installed in its matching container; the full guard rejected the guest's
different transitive runtime. Live editor fixtures separately checked matching Qt/KDE/editor
versions, binary hashes and dynamic linking. The main desktop's libraries were not replaced.
Results and source/binary hashes are in `target/editor-targeted-retry/evidence.json`.
The final native library SHA-256 is
`e10fbb00f485f5e3f51ff31f704964c8545abfb62ae3dfa3bef9e33b61df2058`.

Automatic multi-window capture/departure/recovery, windows with no currently available
documents, exact return placement, a full image build and Windows/USB testing remain open.

Restored `ai-before-editor-retry-guards-1028`. Hyper-V reported Running; SSH confirmed
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-targeted-retry/cleanup-results.json`).

### Automatic editor window groups (2026-10-29)

Under `ai-before-auto-editor-groups-1029`, rebuilt the existing guarded editor library and
production compositor module in the VM. The disposable nested compositor used matching
Qt/KDE/editor versions, verified binary hashes and resolved dynamic symbols. The VM's
main desktop libraries were not replaced.

All 170 focused tests passed: editor session/retry/group recovery, final departure receipts,
protected departure, return summaries, workspace placement, trip lifetime and bundle guards.
The group tests cover exact-ID validation, changed membership, cancellation while arming,
final Save As paths, dialogs, interrupted launches, same-boot survivors, malformed receipts,
existing-process matching, missing-file retries and disabled recovery.

`prototypes/window-identity/verify-auto-groups.py BUILD_ROOT` drives the production
checkpoint, departure, final receipt, cancellation and restore helpers with real Kate and
KWrite in an isolated Wayland compositor. It checks:

- Shared unsaved buffers, window IDs and processes survive Cancel.
- Save As and a first save during closing reopen in the correct windows, with their actual
  saved text, tab grouping and distinct geometry. Native window order supplies the mapping;
  KWin enumeration order is deliberately different.
- One missing window remains an empty placeholder. Automatic rechecks leave late files
  pending; explicit Retry opens them in that exact window without replacing its sibling.
- All saved files missing launches nothing. Intentionally empty source windows reopen.
- Repeated recovery/Retry requests create no extra windows or tabs.

A small empty KWrite window widened from 490 to 504 pixels when its first document view
appeared. Retesting at 620 pixels preserved its frame, sibling frame, focus and state.
Application minimum sizes still constrain restoration. A native accessibility cache warning
occurred during an earlier fixture run; all final assertions must pass before evidence is saved.

This is controlled same-boot recovery after a cancelled switch, not a Windows reboot.
Full-image, Windows/USB and physical multi-monitor tests remain open. A manually closed
window whose siblings still run keeps its remaining files pending until a safe native
window-creation operation is available. Evidence and source hashes are saved in
`target/editor-auto-groups/evidence.json`.

Restored `ai-before-auto-editor-groups-1029`. Hyper-V reports Running; SSH verified the
temporary fixtures/build and container are gone, and Notes retained its original SHA-256.
The cleanup result is saved in `target/editor-auto-groups/cleanup-results.json`.

### Replacing a closed editor window (2026-10-29)

Under `ai-before-editor-replacement-1029`, built the updated native editor library in the
VM's matching container and tested it in the disposable nested Wayland compositor.
The main desktop's editor library remained unchanged. All 179 focused tests passed,
including durable request handling, interrupted replies, disabled recovery, malformed
identities and preservation of the previous checkpoint when a write would exceed its limit.

The final native regression run passed `verify-replacement.py`, `verify-auto-groups.py`
and `verify-group-exit.py` sequentially. For both Kate and KWrite it confirmed:

- Explicit Retry recreates a closed missing-file window in its surviving process, with
  the available nested panes, visible cursors and original frame.
- Existing windows retain their metadata, frame and focus. A shared document reuses its
  unsaved buffer; its on-disk file is not overwritten by recovery.
- A lost reply creates only one replacement. Identical native retries return that window;
  changed requests are refused and a stale retry cannot resurrect a closed replacement.
  A later Retry can recover another generation once the preceding result was confirmed.
- Focus correction leaves another active window alone and does not run after the pointer
  moves. Resumed recovery does not reposition or refocus an existing replacement.
- Invalid layouts, missing paths, unavailable identity support and an armed departure
  refuse replacement. The automatic recovery and protected-close regressions still pass
  Save As, first-save, cancelled-dialog, shared-buffer and final-receipt checks.

The first live run exposed compositor activation despite the editor's activation suppression.
The final caller corrects focus only while its captured desktop choice remains unchanged;
both positive and negative focus checks passed. Application minimum sizes still constrain
window geometry. Successful fixture teardown can emit a GLib main-context diagnostic.

A fresh guarded upstream patch matched all ten compiled source files. The sealed bundle's
source archive and binary hashes matched the tested build and installed container copies.
The full runtime guard rejected the guest's differing transitive packages; isolated editor
processes separately used verified matching Qt/KDE/editor versions, hashes and dynamic symbols.
Evidence, final hashes and native results are in `target/editor-replacement/evidence.json`.

This remains controlled same-boot cancelled-switch recovery. A replacement closed before
Monet confirms its UUID stays pending; native closed-result receipts are still needed.
The per-process replacement cache holds at most 64 records. Inactive-tab cursors, late-file
sets exceeding a pane's tab limit, full-image, Windows/USB and physical multi-monitor tests
remain open.

Restored `ai-before-editor-replacement-1029`. Hyper-V reports Running; SSH verified the
temporary build, fixtures and container are gone, and Notes retained its original SHA-256.
The cleanup result is saved in `target/editor-replacement/cleanup-results.json`.

### Closed results during interrupted editor recovery (2026-10-29)

Under `ai-before-editor-closed-receipts-1029`, all 181 focused VM tests passed. The new
cases retain pending files after an unconfirmed replacement closes, require another
explicit Retry, reuse the original durable request after a failed checkpoint write, and
reject malformed attempt IDs and replies.

The final native `verify-replacement.py` passed for both Kate and KWrite. It deliberately
drops a successful replacement reply, closes the window before Monet confirms it, then
checks that the native closed receipt clears only the attempt. The pending document remains
available for Retry, automatic recovery leaves it closed, and the next explicit Retry
reopens it once. A new attempt cannot duplicate a live replacement of the same window.
Requests written before attempt IDs were added also reopen and report their eventual closure.
Existing shared-unsaved-buffer, nested-pane/cursor, frame/focus and malformed-request checks
passed in the same fixture.

The fixture first assumed that Wayland identity was available on the first native reply;
it now waits for that identity before dropping the reply. Its return-summary check also
uses the existing `partly-restored` status when a document is pending but present on disk,
with Retry available and no missing-file warning. These test corrections did not change
the product code or weaken the pending-document and duplicate-window assertions.

The fresh guarded patch matched all ten compiled files. The sealed source/binary bundle
installed in its matching container. Evidence and final source/binary hashes are in
`target/editor-closed-receipts/evidence.json`. The guest's normal desktop libraries were
not replaced. This is a controlled same-boot VM test; full-image, Windows/USB and physical
multi-monitor checks remain open, alongside the documented 64-record per-process limit,
late-file pane limits and inactive-tab cursors.

Restored `ai-before-editor-closed-receipts-1029`. Hyper-V reports Running; SSH confirmed
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-closed-receipts/cleanup-results.json`).

### Large batches of returning documents (2026-10-29)

Under `ai-before-editor-large-retry-1029`, the 183 focused VM tests passed. Boundary cases
accept a 200-document pane/request, reject 201 documents and reject a combined window
group above 200 entries. The updated legacy final-session parser check was rerun separately
and preserved all 200 paths, their order, selection and visible cursor.

The expanded native `verify-auto-groups.py` passed for Kate and KWrite. It starts with
200 tab entries across two windows, closes through protected departure, temporarily
removes 197 files, and restores the available documents. Automatic rechecks leave the
returned files pending; explicit Retry adds all 197 to the original window's current pane.
Its existing tab selection, cursor, layout, frame and focus stay unchanged, as does the
sibling window. A shared unsaved document retains its text and original on-disk contents.
Another file is refused at the full process budget without changing either window.
Repeated Retry adds nothing. After saving the fixture text, closing and recreating the
large window restores its 199-tab layout alongside the sibling's shared tab.

The same live fixture passed Save As/first-save, cancelled-switch, missing-window
placeholder, all-files-missing, intentionally empty window and exact-placement checks.
A fresh guarded patch matched all ten compiled source files. The sealed source/binary
bundle installed in the matching container; the normal guest desktop libraries were
not replaced. Evidence and hashes are in `target/editor-large-retry/evidence.json`.

The process remains bounded to 200 tab entries. This is controlled same-boot VM recovery;
inactive-tab cursors, full-image installation, Windows/USB and physical multi-monitor
checks remain open.

Restored `ai-before-editor-large-retry-1029`. Hyper-V reports Running; SSH verified that
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-large-retry/cleanup-results.json`).

### Inactive-tab positions through Save As and recovery (2026-10-29)

Under `ai-before-editor-hidden-cursors-1029`, all 188 focused VM tests passed. The new cases
cover optional bounded per-tab metadata, malformed offsets, pruning/promoting tabs when
files are missing, shared-file position selection, late-file requests and retaining an
unconfirmed cursor-restoration launch for Retry. Legacy checkpoints remain readable.

The expanded `verify-auto-groups.py` passed for Kate and KWrite. Three panes across two
windows share one file at offsets 37, 81 and 119. Save As during protected departure and
two successive recoveries preserve those positions before any hidden tab is selected;
accessibility checks show only the three visible editor views exist. Recreating the split
window retains its own offsets, and selecting the shared tabs exposes all three actual
carets. A cursor moved to 155 survives repeated requests both while visible and hidden.
A returning missing file gets its saved position in the current pane without changing
selections. Invalid cursor arrays reject the entire native request; truncated files clamp
the pending caret to the new end. Native Save As/first-save, cancel/veto, empty placeholders,
full 200-entry groups, 197-file Retry, shared unsaved buffers and placement checks also pass.
The VM occasionally refused transient captures; the fixture now waits for complete initial
window metadata, while production retains its conservative refusal and Retry behavior.

A fresh guarded patch matched all twelve compiled source files, including the view-space
hooks. The sealed library and source archive installed in the matching container. The
full bundle guard refused the differing guest runtime; normal desktop libraries were not
replaced. Evidence and hashes are in `target/editor-hidden-cursors/evidence.json`.

These are controlled same-boot tests. Scroll/selection state, unknown cursor positions,
full-image installation, Windows/USB and physical multi-monitor checks remain open.

Restored `ai-before-editor-hidden-cursors-1029`. Hyper-V reports Running; SSH verified
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-hidden-cursors/cleanup-results.json`).

### Scroll positions through Save As and recovery (2026-10-29)

Under `ai-before-editor-view-state-1029`, all 191 focused VM tests passed. The added cases
cover optional bounded per-tab scroll metadata, pruning/promoting tabs, shared-file pane
precedence and exact-file Retry requests. Older checkpoints remain readable.

The expanded `verify-auto-groups.py` passed in native Kate and KWrite. Active tabs at
vertical positions 50/90 and horizontal 120, plus hidden shared tabs at 160/200 and
horizontal 70, survive Save As and two protected departures/recoveries. Actual scrollbar
values and lazy view creation are checked. First activation exposed KTextEditor's delayed
resize resetting the horizontal offset; restoration now waits for the initial layout.
Repeated requests preserve a scrolled view even when its caret is still zero. A closed
window sharing a document with a sibling restores its own caret/scroll state, and late-file
Retry retains the saved viewport. Wrapped top columns and per-view wrapping survive another
departure. Invalid metadata is rejected atomically; shortened files clamp to the new range.
The existing first-save, shared-unsaved-buffer cancellation, placement, missing placeholders,
200-entry group and 197-file Retry checks also passed.

A fresh guarded patch matched all twelve compiled source files. The sealed source/binary
bundle installed in the matching container, and the full guard refused the differing guest
runtime. The main desktop libraries and nested compositor plugin stayed unchanged.
Evidence and hashes are in `target/editor-view-state/evidence.json`.

These are controlled same-boot VM tests. Selections/folding, unknown positions, full-image
installation, real Windows/USB switching and physical multi-monitor behavior remain open.
Restored `ai-before-editor-view-state-1029`; Hyper-V reports Running. SSH verified the
temporary build, fixtures and container are gone and Notes retained its original checksum
(`target/editor-view-state/cleanup-results.json`).


### Text selections through Save As and recovery (2026-10-29)

Under `ai-before-editor-selections-1029`, all 194 focused VM tests passed. New checks cover
bounded selection coordinates and mode, malformed/extra fields, missing-file pruning,
original-pane precedence and exact-file Retry requests. Older checkpoints remain readable.

The expanded native group fixture passed for Kate and KWrite. Ordinary and rectangular
selections survive Save As and two recoveries before hidden shared tabs are instantiated.
Accessibility verifies an actual selected range. The fixture exposes the native selection
action in its disposable toolbar and checks that Select Character Right continues a backwards range
from the correct end; replaying the old request leaves that later selection untouched.
Rectangular mode, reversed columns and columns beyond line ends survive first activation,
replacement in a surviving process and late-file Retry. Normal selections clamp when the
files become shorter, rectangular virtual columns remain valid, and document contents are
unchanged. Invalid native requests reject the entire operation. Existing shared-unsaved-
buffer cancellation, scroll, placement, missing placeholders and 197-file Retry checks pass.

An initial broad run refused a transient identity query before arming departure, leaving
both windows open. The same identities were subsequently available; the full rerun passed.
The safety refusal remains unchanged. Test-only fixes use the embedded editor's actual
selection action and wait for its toolbar button to be visible rather than assuming that
KMainWindow's action interface includes the editor component.

A fresh guarded patch matched all twelve compiled source files. The sealed source/binary
bundle installed in its matching container; its full runtime guard refused the differing
guest runtime. Main desktop libraries and the nested identity plugin stayed unchanged.
Evidence and hashes are in `target/editor-selections/evidence.json`.

Multi-caret selection anchors, folding and unknown positions remain open, as do full-image,
real Windows/USB switching and physical multi-monitor tests. Restored
`ai-before-editor-selections-1029`; Hyper-V reports Running. SSH verified the temporary
build, fixtures and container are gone and Notes retained its original checksum
(`target/editor-selections/cleanup-results.json`).


### Folding through edited Save As and recovery (2026-10-29)

Under `ai-before-editor-folding-1029`, all 197 focused VM tests passed. New tests cover
bounded native folding metadata, checksum shape, range order/nesting, missing-file pruning,
original-pane precedence and exact-file Retry. Invalid or extra fields cannot enter native
requests. The bounds allow 1,024 ranges and 64 nested levels per tab.

The full native group fixture passed in Kate and KWrite. A generated Unicode Python file
was edited while folded, then saved under a new name during protected departure. Its final
checksum and folds survived two recoveries before hidden shared views were instantiated.
Different windows retained independent folds for the same file. Native toolbar actions
unfolded an outer range while retaining its child, then unfolded the child; replay did not
undo that later choice at caret zero. Recreating a closed window left its sibling unchanged,
and temporarily missing files regained their original folds through production Retry.
Changed files rejected stale checksums, including lazy views. Invalid native requests were
refused before mutation; all generated file contents matched their expected values.

The broad run initially caught a stale fixture comparison taken before Save All. Saving
makes folding metadata available for a previously modified buffer. The fixture now verifies
that all other metadata stays unchanged across Save All, checks the new checksum, and then
compares the replacement's surviving sibling with that post-save state. The corrected full
run passed, including previous cancellation, Save As, cursor, selection, scroll, placement,
200-entry capture and 197-file Retry checks.

A fresh guarded patch matched all twelve compiled files. The sealed source/binary bundle
installed in the matching container; its full runtime guard rejected the different guest
runtime. Desktop libraries and the nested identity plugin stayed unchanged. Evidence and
hashes: `target/editor-folding/evidence.json`.

At this checkpoint the native importer still dropped the persistent bit on plugin ranges
marked both persistent and folded; the next entry records the dedicated native fix. Multi-caret anchors,
unknown positions, full-image and real Windows/USB/multi-monitor checks remain open.
Restored `ai-before-editor-folding-1029`; Hyper-V reports Running. SSH verified the temporary
build, fixtures and container are gone and Notes retained its original checksum
(`target/editor-folding/cleanup-results.json`).


### Persistent editor folding — VM checked 2026-10-29

Under `ai-before-persistent-folds-1029`, all 201 focused VM tests passed. The engine bundle
tests cover both original hashes, valid destinations, damaged binary/source refusal before
copy, dependency and engine-symbol preservation, and guarded patch/regression application.
All twelve bundle tests passed again after distinguishing incidental Qt/std template data
from the engine's functions, vtables and owned data.

The actual production build script compiled the installed KTextEditor version with its
RPM's optimization/hardening flags and Fedora linker flags, then built Kate's library and
sealed both with their source. Earlier builds caught missing development packages, a wrong
test executable path and mismatched linker/compiler settings; the final clean build passed.
The symbol check was scoped to the engine's contract after inspecting header-generated Qt
template data differences. These checks reduce compatibility risk; they are not a full ABI
analysis or a full-image boot test.
The runtime now explicitly installs binutils for the installation-time dependency/symbol
checks; the complete image build/boot remains untested.

The added native regression failed against the original engine and passed against the
patched engine. All seven upstream-suite cases passed with the addition: persistent folded
parent/child ranges survived repeated import, unfolding retained their anchors, refolding
worked, and document contents stayed unchanged. The production fix is one flag-assignment
change in KTextEditor's importer, guarded against upstream source changes.

The complete native Kate/KWrite group fixture passed both ordinary and persistent ranges.
It covered an edit followed by Save As, two departures before hidden tabs were shown,
independent folds in shared-document views, native parent/child unfolding, later choices
at caret zero, closed-window replacement and missing-file Retry. Changed files skipped stale
folds; malformed requests were refused. The broader cancellation, first-save, cursor,
selection, scroll, window-placement, 200-entry capture and 197-file Retry checks also passed.
The two fold variants use distinct file names so the test never accidentally overwrites
the other variant's saved document.

Fresh guarded patches matched all twelve Kate files and three engine/test files. Both
sealed libraries installed in the matching container, and the source archive matched the
compiled trees and build inputs. The full runtime guard rejected the different guest
runtime. Guest desktop libraries, nested identity plugin and Notes stayed unchanged.
Evidence and hashes: `target/editor-persistent-folds/evidence.json`.

Restored `ai-before-persistent-folds-1029`; Hyper-V reports Running. SSH verified the build,
fixtures and container are gone and Notes retained its original checksum
(`target/editor-persistent-folds/cleanup-results.json`). These remain controlled same-boot
tests; multi-caret state, unknown positions, X11 identity, full-image and real
Windows/USB/multi-monitor validation remain open.


### Multi-caret editor recovery — VM checked 2026-10-29

Under `ai-before-multicaret-1029`, all 204 focused VM tests passed. Three new format tests
cover extended selection metadata through missing-file pruning, document ownership,
invalid/duplicate coordinates, missing anchors, bounds and older ordinary/rectangular
selections. The native and helper boundaries reject unknown fields and malformed requests
before changing views; only coordinates and native selection anchors are retained.

The production build compiled and sealed both editor libraries. The added native tests
round-trip backward selections twice, continue them with Shift+Right, and delete the
selected text to verify the correct anchors are active. Bare cursors, malformed requests
and shortened-file coalescing are checked too. All 32 multicursor-suite tests and seven
folding-suite tests passed. The first build caught strict Qt string-literal errors in the
new test; after correction, the clean build passed. The original engine still fails the
persistent-fold regression while the paired engine passes it.

The first broad live run caught a shortened-file clamp problem: a saved cursor on a removed
line at column zero moved to the start of the last surviving line instead of document end.
Both normal selection and multi-caret restoration now clamp such positions to document end;
rectangular virtual columns retain their existing behavior. A native zero-column regression
and live normal/multi-caret shortened-file checks cover the repair. The complete corrected
run passed.

The complete Kate/KWrite live fixture passed multiple cursors through Save As, two
departures before hidden tabs are opened, independent shared-document views, closed-window
replacement and missing-file Retry. It includes mixed selections and secondary-only
selections. The native Shift+Right action continues the restored selections. Select All,
clearing the selection and resetting the caret to zero verifies that repeated recovery
does not recreate removed cursors. The shared-file case additionally retains different
extra-cursor sets in three panes across two windows after replacement. Changed file lengths
clamp coordinates without changing file contents. The broader cancellation, first-save,
placement, ordinary/rectangular selections, scrolling, folding, 200-entry capture and
197-file Retry cases passed as well.

Fresh guarded patches matched thirteen Kate files and eight engine/test files. Both
libraries installed into the matching container; archive sources and build inputs matched
the compiled trees. The full runtime guard rejected the different guest runtime. Desktop
libraries, nested identity plugin and Notes remained unchanged. Evidence and hashes:
`target/editor-multicaret/evidence.json`.

Restored `ai-before-multicaret-1029`; Hyper-V reports Running. SSH verified temporary build,
fixtures and container state is gone and Notes retains its original checksum
(`target/editor-multicaret/cleanup-results.json`). Native mode restrictions and the bounds
of 1,024 cursors per view/200 tab entries per process remain. Unknown positions, X11 identity,
full-image, real Windows reboot and physical USB/multi-monitor checks remain open.


### Background-work departure protection — VM checked 2026-10-29

Under `ai-before-background-work-1029`, 95 focused tests passed across departure, Store
downloads, final document receipts, return summaries, workspace return and trip lifetime.
The departure suite also passed 18 isolated Qt checks: shutdown versus sleep/delay
inhibitors, malformed replies, plain-text app names, no early close/acceptance, responsive
Cancel with a late reply, and an actual stalled child process killed by the query timeout.
Translation catalog consistency passed.

The reusable `prototypes/departure/verify-background.py` fixture used the production Store
service launcher/queue and switch dialog, real systemd services and logind inhibitors,
synthetic transactions and a normal Qt companion window. A pipe stub replaced only the
privileged restart helper. At 100% and 200% application scale it verified that windows
remain open while work runs; completion authorizes exactly once; Escape leaves the worker
and app running; queue cancellation releases the veto; and stopping the fixture service
releases it while retaining an Interrupted job for Retry. Both complete runs exited zero.
Captured dialogs fit their screens with visible Cancel buttons and readable app/reason text.

Source hashes, live proof and screenshots are in `target/background-work/`. Restored
`ai-before-background-work-1029`; Hyper-V reports Running and SSH confirms fixture/service
cleanup and the unchanged Notes checksum. The tests did not install/remove real apps,
invoke the privileged restart, change firmware or perform a Windows/physical USB trip.
Apps with neither a window veto nor a shutdown inhibitor remain an integration limit.


### Save As dialogs and fallback session ownership — VM checked 2026-10-29

Under `ai-before-save-as-session-1029`, two new regression cases reproduced the fallback
accepting a changed session and forgetting an observed shared writer. After the fix, all
179 focused restoration/departure tests and 19 isolated Qt checks passed. The Qt test
executes the actual KWin script with a normal transient save dialog, checking that it stays
pending without being classified as an editor main window. Native receipts are also tested
to remain independent of fallback session discovery.

Live unpatched Kate/KWrite 26.08.1 checks used isolated config/data directories and real
native save dialogs, production Python departure/recovery helpers, and a pipe stub for the
privileged restart acceptance. No firmware/reboot request was issued. The first run exposed
that Wayland Save prompts were counted as extra main windows and cancelled departure;
excluding transients from the main-window flag fixes that while retaining the save veto.

- KWrite's first save through the close prompt captured `First saved [1].txt`, reopened
  it with its synthetic contents, and did not duplicate it on Retry.
- Kate vetoed Close, used Save As while departure waited, then closed normally. Recovery
  reopened `Renamed [1].txt` with the edited contents; `Original.txt` remained unchanged.
- Cancelling the first-save chooser and then switching left the original KWrite process
  and unsaved text alive, with no restart acceptance.
- Kate's Save Session As changed the monitored named session. Departure cancelled safely,
  kept the same editor/document open, and did not accept the old session's saved list.

Evidence, source hash and screenshots are in `target/save-as-session/`. Tests did not rebuild
the image/native libraries or cover actual Windows/USB switching. A session change and exit
entirely between fallback polls cannot be proven by this adapter; native per-process
receipts remain the supported path for exact ownership. Restored
`ai-before-save-as-session-1029`; Hyper-V reports Running, fixture directories are gone,
and the Notes checksum is unchanged (`target/save-as-session/cleanup-results.json`).


### Files view-state recovery — VM checked 2026-10-29

Under checkpoint `ai-before-files-view-state-1029b`, built the production paired Dolphin
executable/private library from Fedora's 26.08.1 source RPM. The build retained downstream
patches and validated runtime packages, original hashes, linked features and exported APIs.
The final source archive matched the compiled tree and current build inputs. Both matching
containers accepted the final bundle; the guest's different runtime was refused and its
installed Files binaries stayed unchanged. Live apps ran in a matching container on the
VM's Wayland display, using the production Python helpers and KWin placement.

- Captured/restored hidden tabs, Unicode labels, unequal split widths, current/selected
  paths, expanded folders and scrolling. Two windows returned to their exact rectangles.
- Repeated the return at the bottom of a folder with different window heights; verified
  the actual metadata after placement, not only before resizing.
- Verified two panes showing the same folder retain different selections and the secondary
  active side. A selected dangling symlink remains selected.
- Removed a current/selected file and moved an expanded folder while its window was closed.
  Recovery skipped those missing items. A surviving window's later select-all/scroll choices
  and rectangle remained unchanged, and Retry created no duplicate windows.
- An unavailable folder kept its window pending. Returning the folder opened only that
  window, preserving the other processes and views. Repeated Retry did nothing.
- The installed, unpatched guest Dolphin still passed folder-only AT-SPI capture/restore;
  native refusals are separately tested not to downgrade silently.

All 210 focused tests passed across Files sessions/bundles, multiple windows, departure,
editors, browsers, workspace placement and return UI. Run Qt tests with
`QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software` over SSH. An initial combined run without
that environment aborted while initializing the XCB plugin; the configured run passed.
The new stream decoder's backing QByteArray must outlive QDataStream; its initial temporary
was fixed before the successful runs. Bundle tests also cover malformed destinations,
changed runtime/binaries, lost exports/features, corrupted source/binaries and failed copies.

Evidence and screenshots: `target/files-view-state/`. The final native pair was installed
again and exercised with the live two-window return and same-folder split checks. Native
sources were identical across both builds. These checks do not cover the full image build,
Windows firmware/reboots, physical USB media, remote/search locations, navigation history,
same-process multiwindow or broader monitor/scaling/RTL combinations.
Restored `ai-before-files-view-state-1029b`; SSH confirms the fixture/build directories,
both containers and the temporary image are gone, with the Notes checksum unchanged.
Cleanup evidence is in `target/files-view-state/cleanup-results.json`.

### Files windows sharing one process — 2026-10-29

Built the production Files pair from Dolphin 26.08.1's distribution source RPM in the VM,
including the guarded Wayland client dependency. The existing identity plugin and a native
three-window fixture ran in a matching rootless runtime with an isolated nested KWin.
The guest's mismatched runtime was refused, and its installed binaries were unchanged.
The nested compositor used an identical unprivileged executable copy because Fedora's
file capability cannot execute in the test user namespace. This does not alter the image.

Live checks passed for three main windows in one process, exact UUID/frame association,
closing the first D-Bus object, preserving changed selections and surviving window geometry,
reopening only the closed sibling at its saved position, unavailable-folder recovery and
repeated Retry without duplicates. Unloading the identity plugin left shared captures
unconfirmed and launched nothing. After two siblings closed, the remaining `Dolphin_3`
object still captured without the plugin. The unpatched guest's folder-only fallback passed.
Recovery can reopen saved Files windows in independent processes; shared process topology
is not part of the preserved workspace state.

All 216 focused restoration tests passed with `QT_QPA_PLATFORM=offscreen` and
`QT_QUICK_BACKEND=software`, including malformed/duplicate identity rejection, mismatched
window sets, cancelled switches with changed tabs, and pending launch ownership when
multiple windows show identical folders. The live fixture initially exited/crashed before
capture: it must use Dolphin's application name, initialize a folder before restoring,
and not interpret KMainWindow's always-false restore return as failure. Those fixture issues
were corrected before the successful checks. The build's initial CMake signature mismatch
was fixed before sealing and installing the production pair.

Evidence and screenshot: `target/files-windows/evidence.json` and
`target/files-windows/shared-windows.png`; reusable native checks are in
`prototypes/files-windows/`. Packaged native sources and installed binary hashes were checked
against the checkout. Full-image boot, physical Windows/USB switching, remote/search folders,
navigation history and broader monitor/scaling/RTL combinations remain untested here.
Restored `ai-before-files-windows-1029`; the VM is Running, temporary fixture/build files,
containers and image are gone, and Notes is unchanged. Cleanup evidence is in
`target/files-windows/cleanup-results.json`.

## 5. Logs

- Monet: Settings â†’ About Monet â†’ **Save a report** (one file in Documents), or `journalctl -u monet-sync` and `monet doctor`
- Windows' drive, its Games folder, Wi-Fi in both and what came over: `journalctl -b -u monet-windows-drive -u monet-windows-files`, and `cat /run/monet/windows-drive.json`
- A guest: `journalctl -b -u monet-guest-wipe` and `journalctl -b -u 'user@*'`
- Your photo, painted: `journalctl --user -u monet-paint`
- Windows: `C:\ProgramData\Monet\bridge.log` (and `%LOCALAPPDATA%\Monet\bridge.log` for what runs as you: adding the Games folder to Steam)

## Before real hardware: a virtual machine

On a Windows 11 Pro PC, Hyper-V runs Monet the way a real PC does: UEFI
with Secure Boot on (Microsoft's keys for Linux), so it starts through its
signed shim and shows the blue driver-key screen once. There's no graphics
card in it, so everything is drawn by the processor, and Monet starts
without glass there (blurring makes everything lag). To see the glass
anyway, turn on **Glass** in Settings â†’ Light & Wallpaper: right, but slow.

1. Turn Hyper-V on, once, in PowerShell as administrator, then restart:
   `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All`
2. Download the USB stick's image (Monet-X-Setup.iso, or Monet-X-Installer.iso)
   from the release, or a build's `setup-candidate` artifact.
3. In PowerShell as administrator, from the repository:
   `.\tools\hyperv-vm.ps1 -Iso D:\VMs\Monet-X-Setup.iso`
4. Hyper-V Manager: select Monet, **Connect**, **Start**. Install as on a PC
   ([INSTALL.md](INSTALL.md)). Where it says to take out the USB stick, use
   **Media â†’ DVD Drive â†’ Eject** in the VM's window. At the blue screen, the
   password is `monetsetup`.
5. Once Monet is installed, take a checkpoint (**Action â†’ Checkpoint**), so a
   fresh Monet is a click away.

The screen size is set in Monet (Settings â†’ Display) once it's installed.


### 0.9.4 release preflight — 2026-10-29

The full checkout suite ran in the Monet VM with `tools/test.py`: 957 tests,
945 passed and 12 skipped in the outer runner. Eight of those are intentionally
run again on a private D-Bus by the passing notification subprocess test; the
remaining four require Node or Windows PowerShell. The Windows
PowerShell syntax check passed separately, as did 18 Windows USB safety tests,
15 Bridge tests and Windows Clippy with warnings denied. No physical disk was written.

The installer hardware matrix exercises both Setup's detector and the fallback
kickstart detector against Intel, AMD, modern NVIDIA, hybrid graphics, older NVIDIA
and no-display-controller fixtures. It confirms driver selection happens on the
destination, independent of the PC making the USB stick. Both OS image builds must
finish before either installer build starts. The USB binary remains common to all
supported x86-64 UEFI machines. This is not a physical-hardware compatibility test.

The combined Python process exposed a PySide assertion when unrelated QML fixtures
were loaded in succession. Running each module in a separate process keeps the
complete suite usable without disabling the affected UI tests. A JS-only test now
uses QCoreApplication, and a Qt-optional fixture no longer evaluates Qt constants
when Qt is unavailable. Full-image build and installation results are recorded
separately; these preflight results alone do not establish a bootable release.

The complete local 0.9.4 image also built successfully, including every native
bundle's runtime compatibility check. Its final image is
`a641f65661a2f4df3fa34d814ca80b23f40faae532c959e48b0f9b8bfbfca7c5`.
In an isolated VM desktop using that image, the installed Okular and installed
`monet-resume`/`monet-pdf-session` passed both the native CLI restoration fixture
and the return-controller fixture. These cover duplicate tabs, pages, independent
windows, preferences, malformed and missing documents, protected close, cancellation,
geometry, an already-open survivor and retry after controller interruption. Both
fixtures exited zero; the runtime was stopped after evidence collection.
Evidence: `target/full-image/release094/native-evidence.tar` and `native-summary.json`.
This is packaged-app execution inside the VM, not a reboot into this image.

The preceding image assembly passed `bootc container lint`: 12 checks passed, one
skipped, and two warnings for DNF logs/state under `/var`. Microsoft Defender also
found no threats in the USB executable from release run 40895588120, SHA-256
`b13647e456facf8dcecd2489fe7a3841680b4e75a35de333580cfc1a61905fa0`.
An antivirus scan does not validate physical USB writes or hardware reliability.

Release run [40895588120](https://github.com/HappyHamster135/Monet/actions/runs/40895588120)
completed successfully and published preview release `v0.9.4` from commit
`9ffbf84ac36618c724c1684c46459eaa1b1ff811`. Both NVIDIA and AMD/Intel images,
both installer ISOs, Linux/Windows packages and their checks passed. The fallback
ISO's media checksum and embedded EFI menu checks passed. Monet Setup installed
into a blank QEMU disk with Secure Boot enabled; mistakenly choosing Continue boot
returned to enrollment, and the installed system subsequently booted. Its journal,
desktop/Files screenshots and successful lock/unlock provide direct evidence.
The optional tour's Settings screenshot shows Steam instead of Settings, so that
app check is inconclusive. Windows preparation correctly refused the small test
disk for lack of space; this run does not validate Windows installation or switching.
Logs and 40 screenshots are under `target/full-image/release094/ci-screens/`
and `ci-setup-vm.log`. Physical hardware and USB writes remain untested.

All six release assets are published. Downloading the release USB executable and
`SHA256SUMS.txt` again confirmed the executable's hash matches the scanned binary
above. The published Setup ISO checksum is
`2b92642fb9e0e122bdc407828000ba0dd8e6cb7b7c91a7a2cc6bdfab5e3af839`;
the fallback Installer ISO checksum is
`85270cf07d275518164ecec8b3c91f1989b5e5457a5cb7a484ba46b1cdb0b3a0`.

### Installer completion and diagnostics follow-up — 2026-10-29

A reported physical laptop freeze is not reproduced in the VM. The user clarified
that the laptop returned to the USB installer after reboot, not the installed
desktop. Basic graphics is responsive at Setup's first page; installation in that
mode remains pending. The release CI log spent about six minutes in bootc after
downloading, compared with the reported roughly 30 minutes before noticing the freeze.

The new command regression reproduces a separate hang: the foreground helper exits
successfully but its background child holds stdout/stderr open. The old wrapper
times out; the new wrapper waits for the foreground command and reads a bounded
snapshot of its output files. Input, stdout/stderr separation, nonzero status and
genuine timeout behavior are checked. This does not establish the laptop's cause.

`python tools/vm.py tests tests.test_setup tests.test_setup_window` passes all 53
checks. Real QProcess/QML fixtures verify final output without a trailing newline,
nonzero-exit rejection, visible Details during installation, All set/Restart, and
the recovery-key page using a synthetic key. This is not an encrypted-disk install.
Screenshots of progress, Details and All set were rendered and inspected;
`target/setup-install-hang/visual-proof.tar` includes them and tested source hashes.
No real disks were written, and no replacement installer ISO is published yet.

### Setup keyboard navigation and basic-graphics menus — 2026-10-29

Both reported UI defects were reproduced against the real QML in the Monet VM:
Tab reached Continue without a focus cue, but Return did not activate the custom
AbstractButton. At 800×600 with `QT_QUICK_BACKEND=software`, ComboBox rows became
22 pixels high while inherited vertical padding consumed all their text height;
their strings were correct but `Text.lineCount` was zero. Scaling the delegate
padding leaves 16 pixels for text at that resolution. A further keyboard check
found that toggling an app recreated its tile and lost focus; stable repeater counts
now update the tile data without replacing the focused control.

`python tools/vm.py tests tests.test_setup tests.test_setup_window` passes all 58
checks. The eight QML/QProcess tests cover completion and recovery diagnostics,
Tab/Shift+Tab and both Enter keys, account validation, all selectable app tiles,
Space/Enter on encryption, refusal to install without a usable disk, and keyboard
dropdown selection/cancellation. Swedish, Europe and Stockholm are selected with
keyboard events. Popup text has positive height and rendered lines at 800×600,
1024×768 and 1440×900. The test fixture uses demo data and a temporary state file
throughout, so it does not change the VM's keyboard, network, account or disks.

The VM's Qt version was 6.11.2. Software-rendered screenshots of all four dropdowns
and the focused Continue button were captured and inspected at 800×600.
`target/setup-keyboard-dropdown/before-fix.tar` preserves the blank-menu evidence;
`target/setup-keyboard-dropdown/visual-proof.tar` contains the corrected screenshots,
text geometry and tested source hashes. The run emitted Pillow deprecation warnings
and a shutdown garbage-collection ResourceWarning, with no test failures or QML
errors. No replacement ISO was built, no physical disk was written, and the laptop
freeze is not resolved by these UI tests. Changes remain local for a future 0.9.5.

### Immediate post-download freeze audit — 2026-10-29

The user reproduced the freeze in basic graphics and confirmed that the pointer
stopped immediately after download completion. Reviewed the download/mount/bootc
handoff, encryption, subprocess handling, kiosk service, live-image build and the
released install logs. Downloaded OCI layers are in `/mnt/monet-top/download` on
the destination btrfs, and bootc's OSTree import uses the target repository.
The release used bootc 1.17.1; its matching upstream install/import source is saved
under `target/setup-freeze-audit/` for this investigation. No verified cause of
the immediate laptop freeze was found.

Two diagnostic/process-management problems were confirmed and fixed locally:
bootc output was withheld until exit, and command timeout discarded diagnostics
while killing only the direct process. `run(..., live=True)` now tails separate
output files with independent read offsets, preserving the earlier inherited-pipe
fix. Commands have their own process group; timeout kills that group and records
the final output before reporting failure. Secret input still travels through
stdin, not a temporary file or the command line. The timeout guard cannot repair
a kernel/driver hang or terminate a process stuck in uninterruptible kernel I/O.

`python tools/vm.py tests tests.test_setup tests.test_setup_window` passes **61
tests**. New tests require log output before a waiting child can exit, keep the
last unterminated diagnostic, verify that a timeout stops a real child process,
and open the real QML Details panel while a live-output worker is still running.
The same Pillow deprecation and Qt-fixture shutdown ResourceWarning remain.
Existing input/output, failure, inherited handles, completion and keyboard tests
also pass. No actual bootc install or disk formatting was run by these fixtures.

Coverage gap: `target/full-image/release094/ci-screens/serial.log` shows the full
release VM installation used `monet-amd:latest` without LUKS. It spent roughly six
minutes in bootc and completed, but that is not evidence for an encrypted NVIDIA
installation. The development VM has no usable KVM, QEMU or swtpm; no new nested
installation was attempted. Both that full path and the Razer laptop remain to
be tested before accepting 0.9.5. The existing USB still contains 0.9.4; no changes
were pushed and no replacement ISO was built or released.

### ThinkPad hardware report — 2026-10-29

The user reports that installation worked on their ThinkPad using the existing
installer, but clarified that Secure Boot had to be disabled. With Secure Boot on,
an error appeared before Setup opened from the USB. This is user-reported
physical-hardware success with Secure Boot off; no logs, exact model, error wording,
graphics type or encryption setting were supplied. It does not validate the local
0.9.5 changes, Secure Boot on that machine, or the encrypted NVIDIA path. The user suspects that
the Razer overheats during installation. No temperature measurements or thermal
shutdown evidence establish that cause; the Razer freeze remains unresolved.

USB Secure Boot follow-up: source inspection confirms that Setup's ISO copies
Fedora's shim to `EFI/BOOT/BOOTX64.EFI`, alongside its GRUB and MokManager, and
uses Fedora's kernel. The 0.9.4 build log lists shim 16.1-7 and GRUB 2.12-66.fc44.
The release VM used `OVMF_CODE_4M.ms.fd` and `OVMF_VARS_4M.ms.fd` and successfully
booted the USB with Secure Boot. This does not establish compatibility with every
physical firmware trust database or revocation state. Lenovo's documented
[third-party UEFI CA setting](https://download.lenovo.com/pccbbs/mobiles_pdf/Enable_Secure_Boot_for_Linux_Secured-core_PCs.pdf)
is a possible explanation for this ThinkPad, pending its actual setting and error.
No bootloader replacement or firmware change has been made on that assumption.

### Widget edits and desktop menu — 2026-10-29, local 0.9.5 changes

Reproduced the reset on the installed desktop, including with KDE's own edit
screen. A debugger trace identified Monet's shared LayoutGuard: edit mode changes
the available desktop height, and its delayed resize handler restored the snapshot
from before the edit. Done now captures the new positions before that handler
runs, retaining the normal screen area's dimensions. The gallery also lacked a
target when opened through Settings' D-Bus call; it now uses the current desktop.

`python tools/vm.py tests tests.test_profile_upgrades tests.test_accessible_desktop
tests.test_setup tests.test_look.EverydayScreens` passed **96 tests**. A follow-up
`python tools/vm.py tests tests.test_setup_boot tests.test_accessible_desktop`
passed **19 tests**, overlapping the first run. Real QML coverage includes adding,
moving, resizing and removing widgets, Done during pending resize work, restart,
and removal of the guard's leading widget. KConfig checks confirm the system menu
defaults apply before first login and explicit user choices override them. The
existing Pillow deprecation and Qt fixture shutdown warning remain; no tests failed.

On the live VM desktop, the gallery opened through D-Bus showed existing widget
counts, added Batteries successfully, and Done exited edit mode. Calendar moved
from (1552,48) to (1360,512) and stayed there after Done and a Plasma restart;
the new widgets also remained. Screenshots are under `target/widget-save/`, including
`fixed-gallery-loaded.png`, `fixed-added.png`, `fixed-saved.png` and
`final-desktop.png`. The desktop menu showed Monet's Display settings and Personalize
entries after restart. This was not a graphical first-login test of a new account.
Temporary user-level shell/plasmoid overrides and test layout changes were removed
after verification; the VM's installed image was not replaced.

### USB Secure Boot packaging and firmware trust — 2026-10-29

Downloaded the published `Monet-0.9.4-Setup.iso` and verified its SHA-256:
`2b92642fb9e0e122bdc407828000ba0dd8e6cb7b7c91a7a2cc6bdfab5e3af839`.
Its shim lists both Microsoft 2011 and 2023 UEFI CA signatures. The new packaging
gate passed against this actual ISO in a rootless Fedora 44 container: expected
signer identities for shim, GRUB, MokManager and kernel; matching boot files and
menu in the ISO tree, El Torito image and GPT EFI partition. Negative fixtures
reject a missing signer or a mismatched USB MokManager. Signature listing is a
packaging check, not cryptographic verification or a firmware revocation test.

A dedicated Generation 2 Hyper-V VM reached Setup's Hello page with Secure Boot
enabled and `MicrosoftUEFICertificateAuthority` trust, first using the ISO as a
DVD and then a fixed VHD containing its unchanged raw disk payload. This exercises
the GPT/EFI disk boot path used by the written USB. With the same ISO and
`MicrosoftWindows` trust, firmware rejected it with “The signed image's hash is
not allowed (DB)”. Evidence: `target/secureboot/setup.png`, `gpt-boot.png` and
`windows-only.png`. The temporary VM was removed after the checks; no target
installation disk or physical USB was written.

The build no longer swallows xorriso failures. The release QEMU test now uses a
read-only USB mass-storage device rather than a virtual optical drive; its
construction and first-disk boot order pass the unit check, but that new QEMU
configuration has not yet run end to end. The Hyper-V checks used the published
image, not a rebuilt 0.9.5 candidate, and performed no OS installation. Firmware
trust and revocation differences on the user's ThinkPad remain unverified; a
Windows-only trust database is a demonstrated possible cause, not its diagnosis.
No changes were pushed and no release was published.

### 0.9.4 replacement preflight — 2026-10-29

The user authorized pushing the accumulated fixes and replacing the existing
0.9.4 release, with VERSION unchanged. The full VM run executed 983 tests with
15 expected skips and found one stale translation-catalog failure. Regenerated
the catalogs with the existing generator; the follow-up language and real Setup
window suite passed all 16 tests. Windows bridge and USB tests passed (15 and 18
respectively), and all six PowerShell scripts passed syntax checks. Logs are in
`target/replacement094/`. Both OS images and the replacement installer still need
their build and full installer VM checks before the release assets are replaced.

The replacement also keys USB-maker downloads by the verified release checksum,
so an interrupted older 0.9.4 image is never resumed into its replacement. All
19 USB tests and Windows clippy pass. The first CI run exposed a missing Pillow
guard in the new VM-command unit test; it now skips on the minimal CI host like
the adjacent screenshot tests, while continuing to run in the configured VM.

### 0.9.4 replacement build verification — 2026-10-30

Source `555443abe650007a1c38dc27b20fb4b8dd65bb90` passed
[app/package CI](https://github.com/HappyHamster135/Monet/actions/runs/40955620065)
and [both OS images, installers and the full Setup VM job](https://github.com/HappyHamster135/Monet/actions/runs/40955632028).
The Setup image passed the signed-payload and matching optical/USB EFI checks.
The VM used the raw read-only USB device with Secure Boot enabled, reached All set
after about seven minutes, recovered the MOK prompt after Continue boot, enrolled
the key, booted the installed desktop, and locked/unlocked successfully. All set
and desktop screenshots were inspected. This run used AMD/Intel without LUKS;
it is not a physical USB, encrypted NVIDIA, or real Windows round-trip test.

The CI app tour still has a known coverage gap: `37-settings.png` shows Steam
and Terminal, so that screenshot does not validate Settings. The journal also
records a foreground-booster startup failure and SELinux denials for later
triage. Microsoft's informational download check was blocked from the CI host,
and the first-run Windows preparation failed there; no working Windows install
is claimed by this VM run. The Razer freeze and ThinkPad firmware trust setting
remain unverified on hardware.

The built Linux archive contains byte-identical copies of the tested LayoutGuard,
gallery wrapper and desktop-menu defaults. Windows Defender found no threats in
the built USB executable, SHA-256
`8ef470c0160b3a3371bf96f48c9fb01a717bdcebc4128f32a592fdedc70829a2`.
Logs, screenshots, original release metadata and replacement payload checksums
are retained under `target/replacement094/`.

The accepted `release-setup` artifact was independently downloaded and matches
the candidate byte-for-byte by SHA-256:
`ec5c269d62005f7ed8bb01de8f21a8788e8239076e0f54ff3586a5971d30e006`.
The existing release ID `428126528` was retained; its five payloads, checksum
manifest and notes were replaced, and tag `v0.9.4` moved from `9ffbf84` to the
tested `555443a` commit with an explicit lease on the old tag value. All six
GitHub asset digests and sizes match the prepared files. Fresh public downloads
of the USB maker and manifest also match. The fallback installer SHA-256 is
`b8560092d55f06b7da6ed4dc30931cc448a23f8b78ae9cd294cd9838a0630553`.
No 0.9.5 release or physical USB write was made.


## Competitive comparison protocol

For the 0.9.6 comparison, begin with Windows, Bazzite and Monet on the same
hardware; Fedora Kinoite and Ubuntu or Mint provide additional desktop baselines.
This is a future physical-hardware protocol, not evidence that a comparison has
already run. Disposable VMs establish functional correctness; do not use their
FPS, thermal or power behavior as hardware results.

Record exact OS/image versions and digests, kernel/driver/firmware versions,
application and game builds, CPU/GPU/RAM/storage, display resolution and refresh,
brightness, scaling, power mode and AC/battery state. Keep the workload, network
conditions and initial data equivalent. Report default out-of-box behavior
separately from any normalized configuration; do not silently tune one contender.
Allow initial updates/indexing to finish and record remaining background work.
Use fresh disposable test accounts and synthetic data, never the owner's normal
vault or existing installation disks.

| Question | Measurement and acceptance evidence |
| --- | --- |
| Does installation work reliably? | Time download and deployment separately. Test selected-drive preservation by comparing untouched-drive hashes, encrypted/unencrypted install, network interruption, cancellation, restart after download and late failure, verified cache reuse, first boot and recovery. Report failures and retry cost alongside successful duration. |
| Does the desktop feel responsive? | Cold and warm launch-to-interactive timings for Settings, Files, Store and Passwords; search-to-result and input-to-visible-feedback latency; animation frame-time distribution and stalls. Use explicit start/end events, not a window appearing as proof it is usable. Record idle CPU and system memory accounting separately; do not sum process RSS and call it total memory. |
| How well do games run? | Fixed game/scene/settings/resolution and documented shader-cache state. Report median FPS and p95/p99 frame time, crashes and unavailable titles. Compare native Windows against Linux/Proton explicitly. Time the complete Monet-to-Windows game trip and return to restored work separately from in-game performance. |
| What does laptop use cost? | Matched video/web/idle workloads and screen brightness; energy use, battery duration, fan behavior, temperature and throttling. Record sensor availability and ambient conditions. Repeat only after returning to a comparable starting temperature. |
| Can a normal user finish the task? | Time and errors for connecting Wi-Fi/headphones, installing/removing an app, choosing a drive, restoring a file, undoing desktop changes and returning after a game. Record assistance/terminal use and failure recovery; do not equate fewer clicks alone with better usability. |
| Can an update be trusted? | Upgrade an actual earlier image, restart, verify saved preferences/files and app availability, roll back and reboot again. Interrupt the update at documented checkpoints on disposable disks. Verify the user-visible result agrees with the installed deployment. |

Predeclare workloads and at least five timed runs per short scenario, alternate
OS order and report median, spread and all failures. Use repeated full battery
runs rather than extrapolating one brief power sample. Retain raw samples, scripts
and image identifiers. Mark unavailable measurements explicitly. Do not award an
overall numeric score or claim lower temperature, better battery life or faster
performance until comparable evidence exists.

## Performance startup and spelling suggestions — 4 November 2026

Evidence: `target/typing-performance-2026-11-04/`. The targeted desktop check
uses `tests.test_laptop_native`, `tests.test_system_info`, `tests.test_spelling`
and `tests.test_look`: **422 tests passed, zero skips/failures**, with runner and
container exit codes zero (`regression-confirm.json`/`.log`/`.exit`). The chart
fixture checks empty/single/short/full history,
paired-series alignment, real zeroes versus invalid readings, the rolling
60-second bound, timer jitter/gaps, clock changes, pause/resume and device changes.
Its additional OpenGL/Mesa render pass uses Xvfb on a private display and D-Bus
session, without host display or GPU access. It verifies visible first points at
Now and both short lines spanning the graph. Software-only QML tests cannot
establish that QuickCharts' custom scene-graph nodes draw correctly.

A separate cold-start run with real ksystemstats and the repository sensor face
captured a first point and a visible two-sample line within about two seconds,
plus the subsequent five-sample trace (`graph-*-samples.png`, `preview.log`).
These are functional startup observations, not comparative OS benchmarks.

Native Hunspell tests use disposable copies of en_US, en_GB, en_CA and en_AU,
checking first-ranked corrections, capitalization, preservation of valid words,
unchanged dictionary word lists, repeatable patching and rejection of an invalid
upstream replacement table. All 72 replacement entries were also checked against
all four regional dictionaries. The build preserves the British dictionary's
ISO8859-1 encoding and the other dictionaries' UTF-8 bytes. Fresh desktop test
images include the four dictionaries and the virtual rendering dependencies.

The local `monet-096-typing-performance` image adds these dictionary/QML changes
to the previously tested complete AMD candidate. This verifies local packaging;
it is not a new complete install/upgrade/rollback acceptance run. No live desktop
files, user spelling preferences, app-managed dictionaries or hardware settings
were changed. The ChatGPT desktop application's bundled Chromium spelling menu
remains outside this OS dictionary fix. Translations retain existing entries;
new untranslated text falls back to English. Nothing was committed or pushed.

## Dock hover reliability — 4 November 2026

Evidence: `target/dock-hover-2026-11-04/`. A cold Qt window with real Plasma
ToolTipArea children reproduces missed hover events in the previous ancestor
tracker; plain Item children do not (`probe-plain.log`, `probe-tooltip.log`).
The final per-task tracker preserves the tooltip area's own `containsMouse`
state as well as the animation. `tests/fixtures/dock-hover.qml` exercises the
production tracker and motion components with native ToolTipArea, TapHandler,
DragHandler and MouseArea input, using real Qt pointer events.

**411 tests pass, zero skips/failures**, across `tests.test_dock_motion`,
`tests.test_dock_preview` and `tests.test_look` in the required desktop container
(`regression-final.json`/`.log`/`.exit`; runner and container exit codes zero).
Coverage includes first entry, rapid traversal, neighbours, exits/re-entry,
task-to-Trash transitions, left/right clicks, drag recovery, motion preferences,
hide/show and destroying/recreating the hovered delegate. The existing stale
runtime fallback remains tested. Python/shell syntax, translations and whitespace
checks pass.

The patch is idempotent on clean Plasma 6.7.5 and 6.8.2 sources. Both 6.8.2
plugins were compiled against the matching image runtime and sealed with their
corresponding source (`bundle/`, `build.log`, `build.exit`). The C++ fixture in
`tests/native/dock-hover/` embeds the actual rebuilt task and Trash applets in a
private offscreen window and validates hover, native tooltip delivery, exit and
edit-mode recovery (`native.log`, `native.exit`). Its baseline applet run also
passes under that initialization sequence; the cold ToolTipArea fixture supplies
the failing-before evidence. The offscreen fixture has no window manager, audio
server or compositor shadows; related service warnings are expected. It does
not constitute a live Wayland-panel or physical-hardware acceptance run.

No normal desktop panel, installed plugin, user preferences or open applications
were changed. No commit, push, version bump or release was made.

## 0.9.7 shared activity and widget sampling — 5 November 2026

Evidence: `target/097-goal/`. The in-process `org.monet.activity` QML extension
shares native locker, per-output DPMS, suspend and UPower observations across
QML engines in a Plasma process. It has no periodic hardware timer, per-widget
daemon or disk-state IPC. Missing readings preserve the last complete battery
list with separate availability. Owner/revision checks reject obsolete replies.
Initial lock discovery finishes before nonessential reads start; an unavailable
locker falls back after a bounded async query rather than freezing the view.

Native private-bus/Wayland tests pass in release and AddressSanitizer/
UndefinedBehaviorSanitizer builds (`activity-native-tests-v2.log`,
`activity-asan-v2.log`). They cover independent outputs, lock races, opening a
view while already locked, missing/replaced lockers, suspend/resume, shared power
queries, no-subscriber pauses, invalid data, UPower replacement, removed outputs
and compositor reconnection. Leak detection is disabled for the sanitizer run;
this is memory/undefined-behavior checking, not a Qt leak audit.

The test image installs the same guarded module as the OS recipe and adds only
its private test fixture executable. Runtime RPM identities, library hashes,
dynamic dependencies, relocations, RPATH and bundle hashes are checked before
installation. The corresponding source and GPL license ship in
`/usr/share/doc/monet-activity/`. The OS stage excludes the fixture executable.
The source archive uses an explicit input list, excluding local build/cache files.

Build with the socket-watch permission required by the nested Wayland fixture:

```sh
podman build --security-opt label=disable -f tests/Containerfile \
  -t localhost/monet-desktop-tests:097-activity .
```

The default container labeling denied inotify access to its disposable Wayland
socket and failed reconnect coverage; running that fixture with labeling disabled
passes. No host display socket, system bus or hardware is mounted into the tests.

`activity-final.json` records **69 passing checks, zero skips/failures**, including
15 actual Plasma widgets, native sensor enable flags, closed Quick/Clock/Transfers
popups, fresh battery data after resuming, preserved inactive note/weather writes,
audio, clock format and existing accessibility/layout checks. The wallpaper
scene test supplies a window and containment configuration around the full source
and uses a loopback weather server. It checks a static locked first painting,
aborted in-flight requests, deferred painting changes and stopped animations on
lock, DPMS and window hide. This is not a running Plasma containment test.
Native rendering exposed and fixed Sound's request initialization ordering and a
Weather binding that referred outside its component scope.

After the last battery tooltip/catalog changes,
`activity-regression-final.json` records **437 passing checks, zero skips/failures**
across `test_look`, `test_words`, `test_profile_upgrades`, `test_audio_native` and
the Batteries render test. The audio fallback check now also verifies no commands
while inactive and an immediate fresh reading on resume. These targeted runs
overlap; they are not a new complete desktop/image validation. Catalog generation,
placeholder checks, Python/shell syntax and whitespace checks pass. Swedish adds
the battery availability/checking messages; wider translation review remains.

The idle comparison can be repeated inside that test image:

```sh
python3 tools/bench-widget-idle.py --samples 3 --seconds 6 \
  --output /results/activity-idle.json
```

It alternates the actual baseline Git revision and worktree source in disposable
homes/buses, with the real three-second Quick Settings interval and controlled
helper responses. Baseline is `9f6ace83b4ec26336b1f65addb94c3d09c4db582`.
In all three samples, visible views perform four status/output helper reads per
six seconds; locked/display-off baseline views continue four reads, while the
candidate performs zero. Median process voluntary context switches are 19→4
while locked and 14→0 while display-off. CPU totals of 0–10 ms are too close to
the accounting resolution to establish a CPU improvement. Context switches are
not hardware wakeup counts, and synthetic helper replies do not measure actual
hardware-query cost, whole-desktop activity or battery life. Raw samples are in
`activity-idle.json`/`.log`.

No installed laptop files or saved policy were changed by this batch. A read-only
compatibility check rejects the test-image module for the current laptop's older
libcurl package (`8.21.0-8.fc45`, versus `8.21.0-9.fc45` in the test image).
The guard was preserved; the module was not loaded into the live desktop. A
matching build, real Wayland lock/display transitions, physical power testing,
full images, upgrade/rollback and final complete test run remain release gates.

## 0.9.7 native application launch feedback — 5 November 2026

The menu, compiled dock and Monet helper use `org.monet.launcher` to share pending
native launch jobs. The coordinator survives recreated views/QML engines; it is
an in-process object, not a separate daemon. It accepts indexed desktop-entry
IDs, keeps file/URL/desktop-action handling native, and preserves menu/task-manager
activity-history reporting. A successful KIO process spawn is kept distinct from
a mapped window. Missing programs fail with a retryable message; wrapper exits
and confirmation deadlines report uncertainty without permitting accidental
repeat launches. Dismiss hides the message without discarding its pending guard.

Evidence is under `target/097-goal/`. The earlier `launch-native-reviewed.log`
records a compile error from the notification action shadowing the Retry method.
It is corrected. `launch-native-reviewed-v3.log` and `launch-asan-reviewed.log`
pass in release and AddressSanitizer/UndefinedBehaviorSanitizer builds. The native
executable reports 18 QtTest cases, including setup/cleanup. Coverage includes
real KIO processes, missing executables, explicit new-window Retry, existing or
late/unmapped windows, a model reset, concurrent apps, native startup suppression,
shared QML-engine state, D-Bus/helper calls, early exit, dismissal and the actual
30-second confirmation deadline. A private bus without service-activation
directories avoids starting unrelated activity daemons during this fixture.
Leak detection is disabled; these are not Qt leak measurements.

The test image builds and guards both the native launcher and the modified dock:

```sh
podman build --security-opt label=disable -f tests/Containerfile \
  -t localhost/monet-desktop-tests:097-launcher .
podman run --rm --security-opt label=disable --network none \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  -e MONET_LAUNCHER_CAPTURE=/results/launch-ui-with-dock \
  localhost/monet-desktop-tests:097-launcher \
  python3 tools/test.py --require-desktop \
    --summary /results/launch-regression-with-dock.json \
    tests.test_app_launch tests.test_launcher_bundle tests.test_everyday_search \
    tests.test_look tests.test_dock_motion tests.test_words
```

The compiled dock fixture clicks actual native task delegates, checking Starting,
eight repeated clicks producing one process, two apps concurrently, missing-program
feedback, and Shift/middle-click new-window actions. It verifies the private
fixture app IDs before sending input. Its settings go in the applet's General
group; writing the root group would silently test the default app list instead.
The menu fixture uses real Kicker models and native launch jobs; it exercises both
the notification Retry action and the actual menu button's clicked signal. It
also checks that a Monet helper request joins the same pending job. The latter
menu Retry check is a signal invocation, not a physical-pointer/keyboard test.
Saved menu captures were inspected for error text, pending rows and footer
clipping. Wider keyboard, translation and fractional-scaling checks remain.

The final candidate image is
`f90d5db5339df2ed2122ee91ecab7fb28ecbd2b98a87db6293459f6d129e7b47`.
`launch-regression-with-dock.json` records 459 passing Python checks, zero skips
and zero failed modules. The native executable's cases are inside one wrapper
check; they are not added again to that total. This targeted regression run is
not the final complete desktop suite.
Its native runtime/bundle metadata are retained in `launch-final-runtime.json`.
The launcher module SHA-256 is
`d8cd6f7885867f69bd06526588dd463f0e4b049f8cbc430d9ebfd10eb07e76ce`.
Runtime and private task-model package/library identities, bundle hashes,
relocations, dependencies, QML metadata and RPATH are checked before installation.
Notification configuration is also hash checked; account-specific notification
preferences are preserved. Corresponding source/license archives are installed.

A separate test uses a real private KWin compositor and the laptop's Intel render
node inside the disposable container. It has no host display/socket, session bus,
user configuration or KMS card, and cannot control the physical panels:

```sh
podman run --rm --userns=keep-id --user 1000:1000 \
  --device /dev/dri/renderD128 --security-opt label=disable --network none \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-launcher \
  python3 tests/fixtures/launch-wayland.py /results/launch-wayland-with-dock
```

`launch-wayland-with-dock/result.json` passes nine explicit checks: a working
renderer, native task discovery, immediate pending state, repeated-click
suppression, concurrent apps, mapped-window confirmation, restoring/activating a
minimized app, deliberate second windows and distinct forwarded native Wayland
activation tokens. `support.txt` confirms KWin 6.8.2, active OpenGL ES compositing
and Intel Iris Xe/Mesa rendering. The headless probes without a render node had
exposed windows but no working renderer and were not accepted as window-system
proof. These checks do not qualify the laptop's normal Plasma session, NVIDIA,
physical monitor reconnection or suspend/resume.

This batch remains local source/build work. No live laptop module or desktop
configuration was replaced. A matching laptop installation, remaining file/UI
work, final full-suite/image builds, profile upgrade/rollback and physical release
checks remain open. VERSION is still 0.9.6; no Git commit or push was made.

## 0.9.7 cancellable archive preparation — 5 November 2026

`monet-files-tools` now uses a separate process for initial archive metadata,
unused-folder suggestions, dropped-folder validation, directory reservation,
foreground Ark execution and durable queue submission. The GUI starts its loading
state without resolving/statting the source or destination. Cancellation signals
its private process group without waiting on the GUI thread or synchronously
checking/removing an unavailable folder. Partial output is kept; an interrupted
reservation can remain as an empty folder. Empty, unchanged failed-start
reservations are still removed by the worker.

Background submission uses an ID allocated before work starts. If Cancel arrives
after the queue record is committed but before acknowledgement, the submitter is
stopped first and its exact record is cancelled afterward. A late writer cannot
start an orphaned extraction. A reused ID and the queue's reserved global-lock ID
are rejected. A successfully accepted job stays detached from the dialog.

The destination field relies on the native dialog's default Extract button for
Return and keypad Enter. Connecting returnPressed as a second start handler could
disable Extract before that key reached QDialog and activate Cancel instead. The
real key-event test reproduced that race and now verifies one extraction per key.
Escape continues to cancel during initial metadata and queue preparation.

Run the affected checks in the existing matching native test image:

```sh
podman run --rm --security-opt label=disable --network none \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  -e MONET_ARCHIVE_CAPTURE=/results/archive-async-ui-v2 \
  localhost/monet-desktop-tests:097-launcher \
  python3 tools/test.py --require-desktop \
    --summary /results/archive-async-final-v2.json \
    tests.test_archive_apps tests.test_files_qol tests.test_files_tools \
    tests.test_archive_failures tests.test_download_paths tests.test_archive_bundle \
    tests.test_words
```

The image is `f90d5db5339df2ed2122ee91ecab7fb28ecbd2b98a87db6293459f6d129e7b47`;
the changed Python source is mounted read-only. Native Ark is the guarded matching
build from the earlier batch. `archive-async-final-v2.json` records **59 passing
checks, zero skips/failures**. This is a focused run, not a complete desktop or OS
image acceptance result.

The source-lookup fixture deliberately blocks a worker's os.stat for twenty
seconds. It verifies a different worker PID, six GUI timer ticks while blocked,
no corresponding Python archive stat in the GUI, and Escape returning in less
than 250 ms. The second fixture pauses after queue reservation and before launch;
Escape cancels that committed record without starting Ark. These are controlled
worker delays, not real device latency measurements. Earlier attempts patched
Path.stat, which this Python's is_file bypasses; the final fixture patches os.stat
and proves its delay was reached before making assertions. Captures/observations
are in `archive-async-ui-v2/` and were inspected for readable loading state and
available cancellation.

The same run drives Ark's actual header-encrypted 7z password and Escape dialogs
through the new foreground worker on a private X server. It also retains the
queue tests for encrypted ZIP/7z, wrong passwords, cancellation and actual ENOSPC
on the container's private small tmpfs. Literal paths, execute permissions,
existing/broken-link destinations, partial output, replaced/disappearing folders,
missing Ark, descendant cancellation and background lifetime checks pass. The
Transfers/Stacks render checks use their existing controlled job fixtures; they
do not yet prove the pending native copy/download completion-action work.

Catalogs were regenerated, including Swedish preparation/error/loading words.
The newest helper changes have not been installed in the laptop account preview.
Physical removable-drive behavior, completion actions, broader scaling/focus
checks, matching laptop installation and the final full-suite/image/upgrade/
rollback release checks remain. No Git commit, push or version bump was made.

## 0.9.7 transfer completion actions — 5 November 2026

Monet's Transfers view now uses the guarded native `FolderOpener` alongside its
existing launch module. Each explicit action asynchronously checks the real
KIO destination type. Directories use the default directory handler; files use
OpenFileManagerWindowJob to open their parent and select them. The action never
opens downloaded content. It has immediate busy feedback, cancellation, a
30-second deadline, failure text and dismissal. Revision checks protect against
obsolete replies, a removed view and a timeout racing an immediate retry.
No periodic or initial destination metadata probe is added. Older generic Linux
installs retain an external file-manager compatibility path; that fallback's
local checks run in a child process, not in the widget's GUI thread.

The shared component is installed with the widget's other common QML. The native
bundle now also fingerprints KIOCore explicitly, checks all dependency/package/
file identities and ships the corresponding folder-action sources. Normal OS
builds exclude its native fixture executables.

`target/097-goal/folder-native-final.log` records the native check before the text
formatter addition. `folder-asan-text.log` verifies the final folder-action fixture
with AddressSanitizer/UndefinedBehaviorSanitizer: **14 QtTest cases, including
setup/cleanup, pass**. Leak detection is disabled. Cases cover literal filenames,
HTML-to-plain descriptions, file-manager selection instead of executing desktop
files, direct directory opening, a directory replaced by a file, unavailable
paths and retry, nonfilesystem URI rejection, cancelled/late WebDAV replies,
responsive WebDAV directories, deadlines, view destruction and immediate retry
from a changed handler. Both native fixture executables also pass during the
final test-image build (`folder-image-build-text.log`).

The final matching test image is
`0fc562e25deaa7757bdb3b8fb2db36dc4ddf4816a0fb5e8d77dfcb5080d068e2`,
tagged `localhost/monet-desktop-tests:097-folders`. Changed scripts/QML are mounted
read-only for the workflow checks:

```sh
podman run --rm --security-opt label=disable --network none \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  -e MONET_TRANSFER_CAPTURE=/results/transfers-completion-verified \
  localhost/monet-desktop-tests:097-folders \
  python3 tools/test.py --require-desktop \
    --summary /results/folder-final-checks.json \
    tests.test_transfer_folders tests.test_files_qol.NativeWidgets \
    tests.test_widget_activity.WidgetActivity.test_transfers tests.test_words
```

That run passes **14 Python checks, zero skips/failures**. The earlier broad
`folder-regression-final.json` run passes 510 checks, before the last display and
watcher fixes. The final focused run covers those changed paths; these overlapping
runs must not be summed or presented as a fresh final whole-suite run.

The rendered workflow uses actual KIO CopyJob and FileCopyJob operations, a
loopback HTTP download and the standard KUiServerV2JobTracker. It enables native
immediate progress reporting to make fast fixture operations observable. Its
registered test application stays alive until the test finishes; otherwise Qt's
job quit-lock could exit the windowless driver before the asynchronous JobView
request/termination was processed. The test image has no Dolphin desktop entry,
so the driver uses its own registered identity instead of impersonating Dolphin.
A real Ark queue extracts a ZIP. A supplementary controlled native Ark job view
checks duplicate suppression when the same destination has display-form versus
fully encoded spaces, # and Swedish characters. It is not a second extraction.

The panel closes/reopens before invoking its actual buttons' clicked signals.
Native file-manager API/default directory-handler fixtures record the resulting
URLs. The download is a real desktop file with an execution marker; it is selected
in its parent and the marker is never created. Copy and extraction directories
open directly. The destination is then moved aside, its actual queue record
changes, and the open panel observes that update without a manual refresh. It
shows/dismisses the unavailable-folder error while extracted files remain intact.
These button checks invoke signals rather than physical pointer/keyboard input.

Visual inspection found raw `<a href>` descriptions before conversion to plain
text. The final completed, scrolled and error captures in
`transfers-completion-verified/` are readable and show the appropriate actions.
Long failure details are limited visually while retaining their accessible text.
The workflow also reproduced an incorrect watcher path: StateLocation appends
plasmawindowed/plasmashell, whereas the queues use XDG_STATE_HOME/monet. The view
now uses GenericStateLocation, starts watching after initial queue-directory
creation and refreshes an already-open panel on a new open request.

The real Wayland check uses the same isolated render-node procedure documented
above, with image tag `097-folders` and output directory
`/results/folder-wayland-text-final`. All 11 explicit checks pass. In addition to
the app launch checks, the source window is activated, FolderOpener opens the
correct directory in a controlled default directory handler, and that handler's
real Wayland window becomes active. Its distinct native activation token and
literal directory argument are recorded. This is a controlled handler, not a
Dolphin window/content audit; it also does not qualify the laptop's normal Plasma
session, physical outputs, NVIDIA, hotplug or suspend/resume.

Swedish folder messages/catalogs, syntax and whitespace checks pass. Source and
bundle metadata are retained with the results. No live laptop plugin, policy or
account preview was replaced, and no Git commit, push or version bump was made.
The remaining physical disconnect, wider keyboard/touchpad/scaling, matching
laptop installation, full image/suite and upgrade/rollback release checks remain.

## 0.9.7 Settings keyboard, scrolling and clipping — 5 November 2026

The actual Settings window now exposes More settings to Tab/Shift+Tab with a
visible outline. Return and keypad Enter work on its page tabs, tappable rows,
action pills and appearance/power choices. Disabled pills no longer take Tab
focus. Search destinations which group controls hand their next Tab to the
first visible, enabled control. The existing return-summary-specific handoff was
removed after a regression check showed that both handlers could run for one key.

The two scroll panels use a Qt WheelHandler for wheel detents and high-resolution
touchpad pixels. It consumes the gesture's zero-delta boundaries as well as its
updates, retaining the final position. Page keys and modified wheel page steps
remain available; child editors/controls get their own keys first. Actual pointer
tests also verify background window-drag requests and ordinary control clicks.
There are no added polling timers or input-helper processes.

Software-rendered Shape marks which were entirely outside the sidebar could
paint above its clipped viewport. Software-only visibility checks suppress those
marks. GPU rendering keeps its original path and does not subscribe to the
software scroll-position bindings. Qt's software renderer's handling of an empty
clip region is visible in its [corresponding source](https://raw.githubusercontent.com/qt/qtdeclarative/6.11/src/quickshapes/qquickshapesoftwarerenderer.cpp).
The checks use each mark's own bounds, including its centered position; using
only its row's bounds had still allowed a mark over the footer. The pixel test
now checks both edges and sweeps a row's worth of scroll positions.
The controlled negative case removes only those visibility bindings: the same
pixel test then detects 599 stray white pixels above the list at 200%. Its report
has one expected assertion failure and no runtime errors. Removing the two native
scroll handlers separately reproduces ignored touchpad pixels, also as one
expected assertion failure. These negative sources/results are retained under
`target/097-goal/navigation-clipping-negative-final/`, `navigation-input-negative/`,
`navigation-no-culling.qml` and `navigation-no-native-scroll.qml`.

The local image `localhost/monet-desktop-tests:097-navigation` is
`b0544fdba844467e9e00e0351e895b8f2211df8d2e43385ed75404c5b2a297d7`.
It extends the previously guarded `097-folders` test image with Inter
(`rsms-inter-fonts`); the font is also added to tests/Containerfile. The fixture
registers the repository's Fraunces fonts before creating the QML engine, requires
both font families and requires the Swedish catalog for Swedish runs. Each case
uses a private 1920×1080 Xvfb display, account, session bus and new Qt process.
No host display, physical input devices, system bus or account files are used.

Reproduce the matrix from the repository root:

```sh
podman run --rm --network none --security-opt label=disable \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-navigation \
  python3 tests/fixtures/settings-navigation.py /results/navigation-footer-matrix
```

The six combinations are 125%, 150%, 200%, each with normal 10-point English
and larger 14-point Swedish text. Each executes the same ten behavioral checks,
including real Qt key events, pointer input, wheel events and a touchpad device's
pixel gesture. `navigation-footer-matrix/result.json` records results and the
screenshots under each combination show focus, clipping and the scrolled page.
The matching reduced-motion run is:

```sh
podman run --rm --network none --security-opt label=disable \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-navigation \
  python3 tests/fixtures/settings-navigation.py /results/navigation-footer-reduced \
    --scales 1.5 --fonts 10 --reduced-motion
```

Reduced motion uses the native org.kde.desktop style/platform plugin and a private
kdeglobals with AnimationDurationFactor=0. The test verifies that the actual
Units duration has fallen to its native minimum (observed 1 ms), rather than
assuming the Basic style reads KDE preferences. This also executes all ten checks.

`navigation-footer-regression.json` covers Settings feedback/polling/search,
accessibility, display controls, window frame input, appearance helpers,
return-summary actions, notification controls and catalogs. This is an affected
regression run, not a complete desktop/image suite. Current source hashes, reports
and boundaries are collected in `navigation-validation.json`.

The current matrix passes all 60 executions, the native reduced-motion run
passes its ten executions, and the fresh affected regression run passes 556
checks with no skips or failed modules. The ten matrix checks repeat across
different environments; these figures are not a count of unique tests or a
claim that the complete release suite has passed.

The captures were inspected with the actual fonts. At this checkpoint some narrow
appearance-card captions still elided; the following batch addresses those labels
and several Store paths. Software X11 input-event evidence does not qualify physical touchpad
gestures, Wayland/graphics hardware, monitor reconnects or the laptop's normal
session. These additions remain source-only, with no new laptop installation,
Git commit, push or version bump.

## 0.9.7 readable choices and Store keyboard paths — 5 November 2026

Settings' appearance, wallpaper and power cards now wrap complete captions and
choose their column count from available width and the reading font. Three
columns remain available at the normal size; larger text can reflow to two or one.
The photo placeholder reserves enough preview space for its text. New checks
inspect each visible label for truncation and containment, check card overlap,
resize 760→900→760 logical pixels, and verify that resizing retains focus without
sending a preference change. Existing power-choice focus was confirmed through
its reply and a refresh; its model was left intact.

`choice-baseline/` reproduces the original truncated Swedish Follow the hours
caption. `choice-matrix/result.json` now passes 78 executions: thirteen cases at
each of 125%, 150%, 200%, with normal English and larger Swedish text.
`choice-reduced/result.json` passes the same thirteen cases in the native KDE
reduced-motion profile. The images in both folders were rendered using Inter and
Monet's Fraunces fonts; the enlarged card/placeholder captures were inspected.
Use the preceding scale fixture commands with output `/results/choice-matrix`
and `/results/choice-reduced` to reproduce these runs.

Store now accepts keypad Enter on its sections, sort/filter controls, ranked and
featured apps and screenshot gallery. The gallery has a visible focus outline.
Its screenshot viewer is a native modal Qt popup with an explicit Close button:
Tab/Shift+Tab stay in the viewer, Find cannot move focus behind it, Escape closes
only the image and native focus returns to the gallery. Opening a featured app's
details by keyboard does not begin installation.

Back returns to the original app card, or Search if that item was removed. A
navigation revision prevents a queued restoration from overriding a new section.
Focused items are revealed after visible layouts/content sizes change, using
signals rather than polling. The test at 150% found that restoring focus before
the hidden Home view finished layout could leave the card below the viewport;
the visible-content observers cover that transition. An absent featured app is
normalized to null before its bindings run. Hidden shelf frames also avoid
requesting an invalid Home banner.

Store's eight cases use its actual QML, controlled catalog data, a local generated
test image and a helper which only records calls. They verify no unexpected
install/open/remove action from image-viewer keys. The existing private display
fixture can run them with:

```sh
podman run --rm --network none --security-opt label=disable \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-navigation \
  python3 tests/fixtures/settings-navigation.py /results/store-keyboard-final \
    --module tests.test_store_navigation
```

`store-keyboard-final/result.json` passes 48 executions across the six scale/font/
language combinations. `store-keyboard-reduced-final/result.json` passes eight
more using `--scales 1.5 --fonts 10 --reduced-motion`. Gallery/viewer and restored
window captures were inspected. `store-back-negative/` removes the Back restoration
while retaining the other Store changes: the original-card and removed-card
fallback cases fail their intended focus assertions, with no runtime errors.

The fresh affected run `choice-store-current-regression.json` passes 588 checks
without skips/failures, including Store queue/observer/entry-point and real startup
ordering checks alongside the previous Settings/window suites. Catalog generation,
syntax and whitespace checks pass. Current source hashes and reports are in
`choice-store-validation.json`. Repeated scale executions are not unique tests;
none of these scoped runs replaces the final whole desktop/image suite.

The size fixture restores a 3000×2000 Store window and checks it against its
single screen. Multiple-output sizing remains open: Qt's
[desktopAvailableWidth/Height implementation](https://raw.githubusercontent.com/qt/qtdeclarative/6.11/src/quick/items/qquickscreen.cpp)
uses the virtual desktop's available size. Store must use its own screen's
available geometry before that behavior can be qualified across outputs. Physical
monitor changes, native Wayland/graphics, touchpads, the remaining app audit,
matching laptop installation and release acceptance remain pending. All work
stays local, source-only, uncommitted and unpushed; VERSION remains 0.9.6.

## 0.9.7 follow-up: per-output window bounds (6 November 2026)

This supersedes the multiple-output sizing gap in the preceding pass. Settings
and Store use `WindowArea` from `monet-games`, exposed by their Python entry
points. It follows the watched QWindow's own QScreen and `availableGeometry`,
including work-area changes, with Qt signals rather than polling. It keeps the
last usable rectangle during an invalid/disconnected-screen transition. Tests
check negative screen origins, work-area changes, duplicate notifications,
rewatching, unrelated observers, and window/screen/receiver destruction.

Both QML windows fit restored dimensions and their minimum sizes to that output.
A late configure for an old size is corrected on the subsequent size-change
event. A normal smaller width is retained when moving back, within the new
screen's minimum width. The correction does not change maximized/fullscreen
state or recreate the app's page/control objects.

Actual two-screen Qt plumbing, using a private 1920×1080 plus 1280×720 X server:

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-navigation \
  python3 tests/fixtures/settings-navigation.py /results/window-area-x11-verified \
    --module tests.native_window_area --two-screens --fonts 10
```

`window-area-x11-verified/result.json` passes six executions: both apps at 125%,
150% and 200%. These cover saved 3000×2000 sizes, real QWindow screen switches,
late oversized resizes, keeping a chosen width, restore, and maximized/fullscreen
guards. Each app has a separate small-screen capture. Separate X screens do not
model an extended desktop's compositor moves; those are checked with KWin below.

The private native Wayland check exposes only the Intel render node to KWin:

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 --device /dev/dri/renderD128 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-navigation \
  python3 tests/fixtures/window-area-wayland.py /results/window-area-wayland-verified
```

The fixture starts its own bus, account and KWin, with two virtual outputs. No
host display, session bus, user data or physical display-control device is
exposed. It uses logical 1536×864 at 125% and 960×540 at 200%, with the combined
desktop wider than either output, then changes one output to 175%. Native KWin
scripting moves the windows; the actual TaskManager model supplies compositor
state and frame geometry. Checks wait for that geometry to agree with the client
size and stay inside its own output. Minimized state is checked in the compositor,
since Qt's visibility flag alone does not prove native Wayland minimization.

The successful `window-area-wayland-final/` run covers nine fitted checkpoints
for each app, plus minimized-state preservation, maximized/fullscreen moves,
page/control identity and working Intel OpenGL compositing. The subsequent
`window-area-wayland-verified/` run records the current fixture sources. Qt clients
use their software renderer; this is not qualification of their GPU rendering.
The `support.txt`, `doctor.log`, JSON records and app captures are retained.

The controlled negative run `window-area-wayland-negative-current/` substitutes only
`Settings-no-late-fit.qml`, removing the two size-change corrections. It fails the
small-output check: the window and compositor retain height 520
where the available height is 540 and the intended 48-pixel allowance requires
492. The main run passes without test-side manual fitting. The earlier diagnostic
`window-area-wayland-v8/` also records that explicitly invoking the fit corrected
that old size. Neither negative substitutes a different native controller.

Fresh real-font single-screen checks pass 78 Settings and 48 Store executions
across the six scale/font/language combinations in `window-area-settings-current/`
and `window-area-store-final/`. The separate native reduced-motion runs pass 13
Settings and eight Store cases in `window-area-settings-reduced/` and
`window-area-store-reduced/`. These are repeated executions, not unique tests.
Current source hashes and all reports are recorded in `window-area-validation.json`.

The affected regression run `window-area-regression.json` covers 623 cases. All
modules except Look passed; its one failure required the obsolete virtual-desktop
minimum-width source expression. That literal assertion was retired in favor of
the native behavior tests above. `window-area-final-checks.json` reruns all 402
Look checks and the five WindowArea checks, passing 407 without skips/errors.
These runs overlap and do not constitute the final full desktop/image suite.
Catalog generation/checking, Python parsing and whitespace checks also pass.

Physical monitor reconnects, other graphics hardware, physical touchpads,
menu/extraction/Transfers and Store scrolling/narrow-content layout, matching laptop installation and
final full-suite/image/profile upgrade and rollback gates remain open. These
changes have not refreshed the laptop account preview. Work remains local and
uncommitted; VERSION remains 0.9.6.

## 0.9.7 Store scrolling, narrow layouts and shared glyph clipping (6 November 2026)

Store's five content views and sidebar now share Settings' `ScrollInput.qml`.
Native fixtures send actual Qt wheel and touchpad pixel events, including gesture
begin/update/end, reverse movement and end-of-content bounds. They check panel
isolation, modified-wheel viewport steps, Home/Page/End, mouse background-drag
requests and ordinary card clicks. A GridView's page keys include its header;
arrows retain native item selection. Focus scopes pass Enter to the selected card,
Tab focus updates the selection, and Back restores that card in view. Manual
scroll requests cancel that panel's pending focus reveal, while later real focus
and layout changes retain automatic reveal.

The shelf podium uses one to three columns with usable labels. Sort controls
wrap inside their group, and captions grow to fit. The resize case uses the
smaller of two actual X screens, so the 200% run includes a 608-pixel-wide window.
It checks labels, sort-control bounds, object/focus preservation and absence of
the offscreen checkmark over the title. Navigation never installs/opens an app
outside the controlled Shop recording fixture. A normal search without a
compatibility suggestion also has no missing-value Boolean warning.

Final native input/layout matrix:

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-navigation \
  python3 tests/fixtures/settings-navigation.py /results/store-shared-input-final \
    --module tests.test_store_scrolling --two-screens
```

`store-shared-input-final/result.json` passes 48 executions of eight cases at
125%, 150% and 200%, with English/10pt and Swedish/14pt app-default font settings.
`store-shared-reduced/result.json` passes eight more at 150% in the native KDE
reduced-motion style. Current Settings checks pass 78 executions of 13 cases in
`store-shared-settings-final/`, plus 13 in `store-shared-settings-reduced/`.
Store's existing eight navigation/image-viewer checks pass 48 executions in
`store-shared-navigation-final/`, plus eight in
`store-shared-navigation-reduced/`. Those use the same scale driver, with
`--module tests.test_store_navigation` or its default Settings module.

The scale audit found white and colored paths painted outside their viewport by
Qt's software Shape renderer. `games/Glyph.qml` now checks ancestor clips before
painting its Shape in that renderer, preserving the Item's layout slot. Geometry
reads make native coordinate mappings react to position, size, scale, rotation
and transform-origin changes. A separate actual Qt window checks colored pixels
through those changes and nested clip intersections. The normal GPU branch does
not perform the software clip walk. Settings uses the same glyph component; its
older per-sidebar guards and duplicated glyph definition are removed.

Three controlled substitutions verify the failure detectors using the current
fixture, each mounted over one source file in a disposable container:

- `store-shared-glyph-negative-final/` substitutes `Glyph-no-clip.qml`. It
  reproduces 827 white pixels above the sidebar, 368 colored title pixels at a
  608-pixel window width, and colored pixels escaping the separate nested-clip
  fixture. The main runs pass these assertions with the correction. An earlier
  opacity-only probe did not catch the title mark; the final checks use actual
  pixels and explicitly hide the Shape for the offscreen-filter comparison.
- `store-focus-negative-final/` substitutes `Shelf-no-focus-proxy.qml`, retaining
  the other changes. Arrow selection followed by Enter fails to open the selected
  controlled app. The current focus scope passes Enter and Back restoration.
- `store-cancel-negative-final/` substitutes `Store-no-scroll-cancel-final.qml`.
  Home is undone by a delayed reveal of the selected card; the current input
  signal cancels that pending reveal. Native arrow navigation remains enabled.

`store-shared-regression.json` passes 631 affected Python checks with no skipped
or failed modules. The existing native Wayland geometry fixture also passes all
18 fitted checkpoints and its window-state/scale/output tests with the final
sources in `store-shared-wayland/`. It uses software Qt clients and an actual
Intel OpenGL KWin compositor on virtual outputs, not physical monitor hotplug.
The existing commands in the preceding section apply, using that output path.

Source hashes, current reports and artifact hashes are in
`target/097-goal/store-scroll-validation.json`. The read-only account install plan
includes the new shared files; it has not been applied. The installed receipt
still points to `20261105T140838.565736Z`. Catalog generation/checks, Python
syntax and whitespace checks pass. These overlapping scoped suites do not replace
the final full desktop/image suite.

The inspected software Store capture still shows blank framed artwork; that
fallback needs investigation before qualifying artwork rendering. Physical
touchpads, normal GPU client rendering, other graphics hardware, the remaining
menu/extraction/Transfers audit, matching laptop installation and final release
acceptance remain open. All changes stay local and uncommitted; VERSION is 0.9.6.

## 0.9.7 Store artwork on software and OpenGL renderers (6 November 2026)

This closes the blank-artwork gap observed in the preceding Store pass. Qt's
[software adaptation does not render ShaderEffect](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html).
The Store's masked image layers therefore left screenshots, fallback paintings
and section banners blank. Software rendering now paints those sources directly
with rectangular clipping and visible paper mats. Unavailable shader shadows are
hidden in that renderer. GPU rendering keeps its existing rounded masks/shadows.
The software fallback intentionally does not require rounded shader masks.

`tests/test_store_artwork.py` renders the actual Store QML with distinct controlled
PNG colors. It checks screenshot pixels, painting and icon pixels when no shot
exists, return to those fallbacks after an image-load error, and the section
banner. The only accepted image warning names that deliberately missing file;
other QML warnings still fail the case. Tests record no external app actions.
The smaller actual X screen is selected before resizing, including a 608-pixel
window at 200%. Captures of software and OpenGL output were inspected.

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-artwork \
  python3 tests/fixtures/settings-navigation.py /results/store-artwork-verified \
    --module tests.test_store_artwork --two-screens
```

`store-artwork-verified/result.json` passes 24 executions: four cases at 125%,
150% and 200%, with English/10pt and Swedish/14pt app-default fonts.
`store-artwork-reduced/result.json` passes four more with
`--scales 1.5 --fonts 10 --reduced-motion`. The controlled negative
`store-artwork-negative-final/` restores only the always-enabled mask layers in
Framed/Strip, keeping the other fixes. All four image assertions fail, with no
runtime errors/skips. Its source overrides are retained beside the reports.

The new private Wayland renderer fixture verifies the active client API rather
than assuming the requested backend was selected:

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 --device /dev/dri/renderD128 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-artwork \
  python3 tests/fixtures/wayland-render.py /results/store-artwork-gpu-threaded-final \
    --renderer opengl
```

The four pixel cases also pass in `store-artwork-gpu-basic-final/` using
`--render-loop basic`, and `store-artwork-raster-final/` using
`--renderer software`. Both OpenGL loops are tested; the software client is
tested separately. All use a private 1920×1080 virtual output at native 150%
scale with an actual OpenGL KWin compositor. No host display, session bus,
physical display-control device or user account is exposed.

Per-case renderer JSON verifies the actual OpenGL/Software API. The basic-loop
GPU run additionally queries QRhi driver data after an actual frame, identifying
Intel Iris Xe (RPL-P), Mesa 26.2.6. OpenGL reports UnknownDevice and zero numeric
IDs, so the recorded device name supplies that identification. The threaded run
checks its active API and rendered pixels separately. Driver collection is
restricted to the explicit basic loop: a Python callback on the threaded render
loop can block on the GIL during GUI/render synchronization. This diagnostic
restriction does not change the application's normal threaded GPU path.

The updated test image `localhost/monet-desktop-tests:097-artwork` is
`d260bd281639ff82390e09d1a06d0648f8c00b5ae6c11eb97d1caf95dc0d1f63`.
Its incremental build adds only procps-ng 4.0.6-2.fc45 to the previous navigation
image, asserting that no existing RPM changed. Both repository image definitions
now explicitly install that dependency, and `tools/test-runtime.py` requires
`pgrep`. The missing helper seen in the earlier regression log is no longer
silently omitted from required desktop checks. Native bundle dependencies remain
unchanged.

The final affected regression run, including `--require-desktop`, passes 635
checks with no skipped or failed modules in `store-artwork-current-regression.json`.
`store-artwork-input/result.json`
retains 48 passing scroll/layout/clipping executions after images are visible.
Current source hashes and reports are in `store-artwork-validation.json`.
These scoped checks do not replace full-image or physical-device qualification.
The remaining menu/extraction/Transfers audit, matching laptop installation and
release gates remain open. No account preview refresh, commit, push or VERSION
change was made.

## 0.9.7 focused menu input and short-window checks (6 November 2026)

`tests/test_menu_navigation.py` loads the actual menu full representation and
delegates, with inert external models/helpers. It covers Tab reaching pinned,
recent and all-app views with a current selection; arrow handoff and both Enter
keys; Escape through search/All apps/close; Menu and Shift+F10 on an app; wheel
and precise touchpad events in all four lists; and usable section bounds at
short window heights. Compact layouts adapt pinned columns/rows and retain a
usable recent-files region. These tests exercise representation geometry, not
the outer Plasma popup's size limits; that qualification remains open.

The common ScrollInput now lives in `linux/share/monet/widgets/ScrollInput.qml`.
The games-directory component forwards to it so Settings/Store keep their
existing import. The full installer and reversible account installer include
the canonical file, while applets receive their self-contained common copy.

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-artwork \
  python3 tests/fixtures/settings-navigation.py /results/menu-navigation-matrix \
    --module tests.test_menu_navigation
```

`menu-navigation-matrix/result.json` passes all 36 executions: six cases at
125%, 150% and 200%, using English/10pt and Swedish-catalog/14pt contexts with
English fallback for untranslated labels. `menu-navigation-reduced/result.json`
passes six more with `--scales 1.5 --fonts 10 --reduced-motion`, using native KDE
style. The original `menu-navigation-baseline/` recorded seven failing assertions
across six cases without runtime errors, including skipped Tab targets, absent
keyboard context-menu requests, ignored pixel gestures and a zero-height recent
view. Current short-window captures were retained and inspected.

A separate real Plasma/Kicker fixture still verifies pending launch feedback,
duplicate prevention, concurrent apps and both retry paths. The affected launch,
search and profile migration run passes 60 Python checks with no skips or failed
modules in `menu-packaging-checks.json`. The native launch binary also passes its
18 QtTest cases. Settings/Store input and appearance regressions pass 431 checks
without skips or failed modules in `menu-shared-input-regression.json`.

All reports, source hashes and capture hashes are recorded in
`target/097-goal/menu-navigation-validation.json`, using the same artwork test
image as the preceding section. Changed Python sources parse, installer shell
syntax and whitespace checks pass. The read-only account preview plan contains
723 files; it was not applied, and the installed receipt remains
`20261105T140838.565736Z`. Outer popup geometry, extraction/Transfers input,
physical devices, matching laptop installation and final release acceptance
remain open. Everything stays local and uncommitted; VERSION remains 0.9.6.

## 0.9.7 actual Plasma menu popup bounds (6 November 2026)

This closes the outer-popup gap from the preceding focused menu checks. A real
Plasma panel in a private KWin session reproduced a 604-pixel popup in a
494-pixel usable area after changing to native 200% scale. Qt requested y=-72;
the compositor placed it at y=0, still overflowing the usable area. Merely
constraining the representation inside an ordinary test window did not exercise
this path.

Menu size hints now use the panel's own containment's
[available screen rectangle](https://api.kde.org/qml-org-kde-plasma-plasmoid-containment.html#availableScreenRect-attached-prop),
with room for the native frame. Queued geometry-change handlers also correct
late oversized Wayland configures. Native padding and a smaller current size
are preserved. There is no polling or replacement popup implementation.

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 --device /dev/dri/renderD128 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-artwork \
  python3 tests/fixtures/menu-popup-wayland.py /results/menu-popup-fourth
```

`menu-popup-fourth/result.json` passes 12 checkpoints, with separate private
sessions for native 10pt and 14pt fonts. Each session covers 125%, 150%, 200%,
moving the panel to another output at 200%, a live 175% change there, and moving
the panel to the top edge. Two actual QScreens have separate KWin virtual
outputs; the usable rectangle is relative to the containment's own output,
including its panel reservation. The fixture compares native compositor frame
geometry with that usable rectangle and checks Search, the view switch, Pinned
and Recent bounds inside the representation. It does not infer successful
placement merely from Qt's requested window position.

The fixture starts its own activity manager and Plasma shell. Each owned child
has a separate process group and is stopped on completion/failure. KWin logging
is explicitly sent to the capture file so its frame observations are available;
KScreen's output list is sorted by virtual output name rather than assumed to
match the panel's screen index. Only the Intel render node is exposed: the
compositor uses OpenGL, while Plasma's client rendering is software. No host
display, session bus, account or physical output-control device is exposed.

`Menu-without-popup-correction.qml` disables only `fitPopup`, keeping the bounded
hints and all other fixes. Running the same fixture with `--fonts 10 --source`
that file passes the first two scale checkpoints, then fails the actual frame
bounds at 200%. The extracted failure context and raw log are retained in
`menu-popup-negative/`. This proves that size hints alone do not resolve the
tested late-configure case.

The current representation matrix passes 36 executions in
`menu-popup-input/result.json`, plus six with native reduced motion in
`menu-popup-reduced/result.json`. The affected regression run passes 445 Python
checks without skips or failed modules in `menu-popup-regression.json` (menu,
search, native launch/dock and appearance). These overlapping scoped runs are
not a final complete suite. Source/report/artifact hashes are recorded in
`target/097-goal/menu-popup-validation.json`.

Python syntax and whitespace checks pass. The account preview is unchanged;
matching laptop installation, extraction/Transfers input/layout, physical
devices and final release acceptance remain open. No commit, push or version
bump was made.

## 0.9.7 extraction and Transfers input/layout (6 November 2026)

The archive preparation dialog previously enforced a 417-pixel height on the
tested 640×360 logical screen. It now follows its current screen's usable size,
keeps the folder drop target and native action buttons outside the scrolling
details, and stacks button captions when they do not fit horizontally. Tab focus
reveals the destination/chooser inside the details; native mouse steps and
precise touchpad pixels both scroll. Escape, worker cancellation, native password
dialogs and background queue submission retain their operation coverage.

Transfers uses a native Flickable/scrollbar with the same precise input component
as Settings, Store and menu. Both Enter keys activate a focused template button;
auto-repeat cannot repeat a transfer action. Titles, states, messages and action
groups adapt to narrow layouts. Loading/error messages and the explanatory note
are part of the scrollable content, leaving usable room for jobs at large text.
Error dismissal and cancellation have keyboard focus; errors remain plain text.

Local rows have stable job keys. Progress updates and reordering preserve the
actual control QObject and its focus, while completion selects that job's Open
folder action. Focus reveal also follows ancestor layout changes after rows
move. Manual Home and tested wheel input cancel automatic following; later
progress updates cannot undo those choices. Full-view indeterminate animation
is disabled when closed/inactive. These state checks do not measure whole-OS
CPU or battery savings.

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-artwork \
  python3 tests/fixtures/settings-navigation.py /results/transfers-navigation-verified \
    --module tests.test_transfers_navigation --two-screens
```

Use `tests.test_extraction_navigation` and output `extraction-navigation-current`
for the Widgets pass. The fixture registers the packaged reading/heading fonts
and starts new processes for each scale/font/catalog combination. The second
actual X screen is 1280×720 pixels; at 200% this supplies the 640×360 logical
screen. Reports list both screen sizes and distinguish Widgets raster rendering
from Qt Quick software rendering. Captures and geometry/control JSON were
retained and inspected. English fallback remains for untranslated messages.

| Report under target/097-goal | Passing checks | Scope |
| --- | ---: | --- |
| extraction-navigation-current/result.json | 18 | Three cases × 125%, 150%, 200% × English/10pt and Swedish-catalog/14pt |
| extraction-navigation-native-current/result.json | 3 | Native KDE style with reduced motion at 150% |
| extraction-wayland/result.json | 3 | Actual Widgets interaction on private Wayland at native 200% |
| transfers-navigation-verified/result.json | 60 | Ten cases across the same six scale/font combinations |
| transfers-navigation-native-verified/result.json | 10 | Native KDE style with reduced motion at 150% |
| transfers-popup-verified/result.json | 12 | Actual Plasma popup with completed real Ark jobs |
| transfers-menu-popup-current/result.json | 12 | Menu regression with current geometry handling |
| extraction-transfers-current-regression.json | 513 | Affected GUI, archive, file-operation, widget, appearance and catalog suites; no skips/failed modules |

The native-style test selects public template controls in QML before returning
them to Python. Recursively wrapping KDE's private style items exposed a PySide
binding assertion; keeping those private items in QML avoids that test-harness
failure. Required control/label counts prevent an empty selector from passing.
This changes test introspection, not the application's native style.

The popup fixture now also supports Transfers:

```sh
podman run --rm --network none --security-opt label=disable \
  --userns=keep-id --user 1000:1000 --device /dev/dri/renderD128 \
  -v "$PWD:/src:ro" -v "$PWD/target/097-goal:/results:rw" \
  localhost/monet-desktop-tests:097-artwork \
  python3 tests/fixtures/menu-popup-wayland.py /results/transfers-popup-verified \
    --widget transfers
```

Its private account completes three actual small ZIP extractions with the queue
and native Ark, verifies the output, and waits for those jobs to appear in the
real Plasma widget. Both 10pt/14pt sessions cover 125%, 150%, 200%, another
mixed-scale output, a live 175% change and a top-edge panel. Compositor frame
bounds, viewport and Refresh are checked against the output's panel-free area.
The fixture waits for actual placement with a bounded deadline; it does not use
Qt's requested position as proof of compositor placement. Only the Intel render
node is exposed; these are software clients on an OpenGL KWin compositor with
virtual outputs, without host display/bus/account access.

Two geometry details were exposed. Window geometry can update before anchored
content, so negative temporary frame padding must not shrink an already smaller
window again. Static popups can also retain their old compositor position until
a frame commits. Menu/Transfers now request that frame on geometry/position
events. The controlled current-source `Transfers-without-position-frame.qml`
disables only that request. It passes the first checkpoint, then leaves KWin's
frame at y=269 while Qt requests y=125 after scaling to 150%; the frame still
overflows after a five-second wait. Raw logs and extracted failure context are
in `transfers-position-negative/`.

The affected operation suites include real KIO copy/download tracking, native
Ark, completed rows after closing/reopening Transfers, literal folder arguments,
downloaded desktop files never being executed, native descriptions without HTML
markup, and a missing destination with dismissible error and retained files.
These scoped tests do not replace the final complete suite/image run.

Current source/report/capture hashes are in
`target/097-goal/extraction-transfers-validation.json`. Catalog generation/check,
changed Python syntax and whitespace checks pass. The read-only account preview
plan contains 723 files and has not been applied. The installed receipt remains
`20261105T140838.565736Z`; VERSION remains 0.9.6. Matching laptop installation,
physical input/displays/drives, measured readiness/idle activity and final image,
upgrade/rollback and release acceptance remain open. No commit or push was made.

## 0.9.7 batch 15 — matching account preview (6 November 2026)

Scope: a reversible account installation on the laptop's current Monet 0.9.6
runtime. This is not a new booted OS image, physical power/input qualification,
or a sign-in/app-readiness performance result. All work remains uncommitted.

### Matching native builds

`target/097-goal/laptop-build-inputs` captures the current five native source
directories and the host runtime manifests. The SDK initially differed only in
libcurl revision 9 versus the laptop's revision 8. The libcurl RPM's extracted
library SHA-256, `ecf513b17b10f1d619eca804d4c7b93b139ca56e4cafaed64356fda1736e142e`,
matches the laptop's library. Only disposable containers were changed. Version
locks retain the matching SDK packages during dependency installation. The
existing Monet Files/dock binaries are copied into the SDK as its captured
baseline, rather than relaxing the bundle's original-file checks. Every final
bundle verifies against the actual host's packages and original-file hashes.

Activity and launcher native CTest suites pass; Files' experience/loading CTest
suites pass. Build logs are `laptop-activity-build.log`,
`laptop-launcher-build.log`, `laptop-dock-build-v2.log`,
`laptop-files-build.log` and `laptop-archives-build.log` under
`target/097-goal`. The first dock dependency command rejected an excluded
explicit curl argument; replacing that exclusion with a version lock allowed
the matching build. The failed command is retained in `laptop-dock-build.log`.

Files and Archives packaging now strips debug sections from shipped binaries.
The original unstripped binaries stay in the local build trees. The candidate
was repackaged with the same operation, updated corresponding build instructions,
unchanged compared `.text` dumps, and the normal runtime/ABI/seal checks.
`laptop-native-package-validation.json` records the byte sizes: the Files pair
shrinks from 87,053,432 to 4,430,104 bytes; Ark from 4,981,816 to 286,688 bytes.
The current matching bundles are in `target/097-goal/laptop-native`.

### Installer, guards and native operation checks

`tools/install-desktop-preview.py --native-bundles DIR` validates all five
components before returning a plan. The directory contains `activity`,
`launcher`, `dock`, `files`, and `archives`. Apply uses the existing backup/
receipt mechanism; source archives remain beside the account-native binaries.
Each QML module has its own import root. A process rechecks immutable runtime
identities and the payloads it can load. Files/Ark validate their own binaries on
launch. Stale inherited preview QML/plugin/library paths are removed before
fallback; custom external paths remain. No sampling daemon was added.

Run the end-to-end account fixture in a matching, isolated desktop container:

```sh
podman exec --workdir /src/monet monet097-laptop-build python3 \
  tests/fixtures/native-preview-install.py /output/laptop-native \
  /output/laptop-account-final-package.json \
  tests.test_native_preview,tests.test_archive_apps,tests.test_archive_failures,tests.test_app_launch,tests.test_transfer_folders
```

The fixture creates a disposable account and bus, applies the complete plan,
checks actual mapped account QML modules and the executed Files/Ark binaries,
runs the requested operation suites through the installed wrappers, then undoes
the installation while preserving a later personal edit. The final package run
passes 40 checks without skips. Before the packaging/guard optimization, the
wider affected run passes 123 checks without skips. Reports are
`laptop-account-final-package.json`, `laptop-account-final-package-regression.json`,
`laptop-account-qualified.json`, and `laptop-account-qualified-regression.json`.
The focused installer/retirement/bundle unit run passes 43 checks in
`laptop-installer-unit-final.log`.

Real delayed-WebDAV Files navigation and cancellation pass with the matching
pair. Reports/captures are in `laptop-files-navigation-v2`,
`laptop-files-cancel`, and, after debug stripping, `laptop-files-final-navigation`.
The first GUI attempt failed because the disposable desktop image lacked the
Files/Baloo runtime, not because the app reached a loading state. Its log is
retained in `laptop-files-navigation`. The test Containerfile/runtime checker
now require Files and the relevant native dependencies/tools.

Two wider runs exposed a genuine completion-fixture isolation defect: the fake
file manager silently queued behind a real Files process left on the suite bus.
`laptop-transfer-owner-audit-transfers/filemanager.log` records expected owner
`:1.13` versus actual `:1.2`; only directory actions reached the stub. The fixture
now creates a private bus, uses `do_not_queue`, and waits for confirmed endpoint
ownership/readiness. The corrected wider and final-package runs verify all three
actions and preserve logs/captures, including `filemanager.log` and
`actions.jsonl`. This fixes the fixture; it is not evidence of a product folder-
opening regression. Earlier failing reports are retained for comparison.

### Laptop installation and bounded performance result

The reviewed plan contained 852 payloads and 264 changes. They were installed
with receipt `~/.local/state/monet/desktop-preview/20261106T030609.054604Z/receipt.json`.
The final packaging/guard optimization changed nine files, with receipt
`~/.local/state/monet/desktop-preview/20261106T031345.000395Z/receipt.json`.
`laptop-installed.json` records the final application and its preceding receipt.
All payload hashes and five native component guards pass. Neither application
changed any of the twelve checked power, lock, region, download, Files, weather
or panel preference files. The installer does not rerun profile defaults.

Plasma was refreshed with no active local transfers or native job views. PID
424063 maps the account activity/launcher/dock modules; details are in
`laptop-activation.json`. The activation journal is retained in
`laptop-plasma-activation.log`: no Monet QML loading/type errors were observed;
upstream KDE `leftInset` warnings and an unresolved ChatGPT Unity launcher entry
remain visible. Already-open Files, Settings and Store windows retain their
loaded code until reopened.

Seven warm-cache samples on this laptop measure the initial all-component
preview guard at a 76.29 ms median. Avoiding unrelated executable checks gives
an installed app-module guard median of 1.393 ms and desktop-module guard median
of 3.758 ms. The command still validates every module it can load; binary
launches retain their separate guards. These timings exclude Python/process
startup, painting, loaded data and whole-OS effects. Raw samples are in
`laptop-native-guard-timing.json` and `laptop-installed-guard-timing.json`.

To undo this update, close Files/Settings/Store, restore the two receipts in
reverse order, reload the user manager/cache and refresh Plasma:

```sh
python3 tools/install-desktop-preview.py --restore "$HOME/.local/state/monet/desktop-preview/20261106T031345.000395Z/receipt.json"
python3 tools/install-desktop-preview.py --restore "$HOME/.local/state/monet/desktop-preview/20261106T030609.054604Z/receipt.json"
systemctl --user daemon-reload
kbuildsycoca6 --noincremental
systemctl --user restart plasma-plasmashell.service
```

Later personal edits are preserved. Read-only retirement planning also verifies
the combined current and first-preview receipt history, preserving preferences
seeded by the first preview. The final source/report/artifact hashes are in
`target/097-goal/laptop-preview-validation.json`. Whole-image upgrade/rollback,
real app readiness/idle measurements, hardware/drives/input and final release
preparation remain open; VERSION is still 0.9.6.


## 0.9.7 batch 16 — app data frames and Store cache (6 November 2026)

Scope: actual source/installed app measurements on this laptop with isolated
profiles, buses and virtual displays, plus a reversible account update. Neither
these results nor systemd target timings establish physical screen readiness,
whole-OS speed, cold OS-cache performance or battery-life gains.

### Methods and current reports

`tools/bench-app-readiness.py` compares a pinned Git revision against staged
worktree or already-installed helpers. A common probe records the first submitted
frame, settlement of initial Settings helper replies/Store models, and a following
frame. It does not wait for remote artwork. Sources/probe are captured by hash;
the probe is frozen per run, and concurrent worktree changes are flagged. Per-run
profiles and optional shared per-variant app caches are temporary. OS page caches
are not flushed. Cached system catalog/Flatpak listings are read; metadata refresh
and optional Python HTTP requests are suppressed. Native mode uses private KWin
OpenGL and native KDE controls, with an absolute socket path for isolated clients.
Ready-frame captures are taken only after timing, with an explicit completion
handshake so the client cannot be killed before saving them.

```sh
python3 tools/bench-app-readiness.py --samples 5 --reuse-cache --wayland --capture \
  --candidate-helpers "$HOME/.local/libexec/monet-desktop-preview" \
  --output target/097-goal/readiness-installed-fixed.json
python3 tools/bench-app-readiness.py --apps store --samples 5 --wayland \
  --candidate-helpers "$HOME/.local/libexec/monet-desktop-preview" \
  --output target/097-goal/readiness-installed-empty-cache.json
python3 tools/bench-files-opening.py --samples 5 --entries 1000 --reuse-cache \
  --native-pair "$HOME/.local/share/monet-desktop-preview/native/dolphin" \
  --output target/097-goal/files-opening-measured
```

The baseline revision is `9f6ace83b4ec26336b1f65addb94c3d09c4db582`. Runs alternate
variant order. Native app reports retain KWin support/logs and first ready-frame
images. Files opens a disposable 1,000-file local directory on private 1280×900
outputs, verifies the native bundle before the direct-native comparison, and
records compositor-observed mapping and `monetFilesState` listing completion.
KWin does not expose `readyForPainting` to this script, so the report retains null
and claims mapped windows, not first scanout/finished thumbnail rendering. Wall/
monotonic-clock agreement is checked. The first Files observer attempt missed logs;
adding script logging and waiting for its ready marker fixed the measurement,
not the product. Its incomplete baseline is retained in `files-opening-initial`.

Five-run medians from the current installed/native reports:

| Session/metric | Baseline | Installed candidate |
| --- | ---: | ---: |
| Settings first submitted frame, shared-cache run | 387.951 ms | 391.815 ms |
| Settings initial-data frame, shared-cache run | 531.686 ms | 549.166 ms |
| Store first submitted frame, shared-cache run | 459.804 ms | 356.853 ms |
| Store initial-data frame, shared-cache run | 1,335.230 ms | 473.652 ms |
| Store process peak RSS at data frame, shared-cache run | 562.66 MiB | 280.03 MiB |
| Store first submitted frame, fresh app cache per sample | 489.167 ms | 413.852 ms |
| Store initial-data frame, fresh app cache per sample | 1,380.813 ms | 1,479.558 ms |
| Files mapped window and completed listing | 295.930 ms | 326.521 ms (account wrapper) |

The directly launched verified native Files pair measures 301.505 ms for the last
metric, with listing completion at 209.507 ms versus the baseline's 218.251 ms.
These small-directory timings do not demonstrate a convincing native opening
speedup; the wrapper adds overhead. Existing delayed-drive navigation/cancellation
reports establish responsiveness separately. Settings is slightly slower in these
measurements and remains performance work. The Store gain applies to valid cached
metadata; first uncached contents arrive later while the window appears earlier.
No result here proves faster sign-in or longer battery life. Shared-cache runs
include their first cache-building sample; detailed raw samples and ranges remain
in the reports. These are not controlled cold OS-cache experiments.

`startup-host-observation.json` records the current boot's systemd output: firmware
16.351 s, loader 8.733 s, kernel 1.790 s, initrd 9.546 s and userspace 30.834 s
(total 67.257 s). The user workspace target reaches 5.875 s, with kded/PowerDevil
on its displayed chain. Service durations overlap, some services have restarted,
and the target is not a desktop-usability timestamp. No durations are summed as
saved time, and no before/after sign-in claim is made.

### Parsed metadata cache and correctness

`cached_catalog` keys its record by catalog identity (resolved source, device,
inode, size, mtime, ctime), parser schema, languages and the current blocklist.
Each locale/source gets one replaceable cache file rather than accumulating a
new file for every catalog update. Reads are bounded to 32 MiB, require regular
files and never block on a FIFO. Malformed/stale caches reparse. Explicit Refresh
bypasses the cache. Source identity is checked again before accepting/saving a
record. Atomic replacement uses a private temporary file, and write errors leave
apps available and existing cache data intact. Only parsed app metadata is cached;
installed state/transaction permissions remain fresh.

Serialization runs on the already-existing worker, after its loaded signal has
reached the UI and a subsequent real frame. The frame connection exists only
while work waits, with a bounded wait for hidden/closing windows. The production
entry point invokes the native update slot through QMetaObject, so a generic
QWindow Python wrapper does not require extra QtQuick bindings. A deliberately
500 ms delayed save verifies frame-before-write ordering, including the raw
production helper without the measurement probe.

`catalog-real-data-equality.json` validates the actual 51,246,398-byte catalog:
3,323 app records after 17 blocked IDs, in the current English language order,
compare exactly across uncached, newly saved and cache-hit reads. The hit is run
with the XML parser disabled, proving reuse. The cache is 7,110,793 bytes. Metadata
and source digests are retained; no raw personal app inventory is logged.

The affected backend/startup/Store navigation, artwork, scrolling, queue and
observer run passes 73 checks without skips in `catalog-final-regression.json`.
The account fixture passes 29 focused checks in `catalog-preview-verified.json`,
and the expanded fixture passes 10 native-preview checks while starting the
actual installed Settings, Store and Games in `catalog-preview-all-apps.json`.
The final fixture also removes only the shared-import link, confirms that the
actual Settings entry point fails at that import, restores the link and completes
23 focused checks plus safe undo in `catalog-preview-final.json`. The broader
installer/preview unit selection passes 28 checks in
`catalog-preview-installer-tests.log`.
Reports/logs are under `target/097-goal`.

### Installed-app packaging repair and undo

The first installed-app benchmark failed at QML loading: private games' relative
`../widgets` import had no sibling directory, although the shared file existed
in account data. Earlier installation checks loaded native modules and executables
but missed these app entry points. `tools/install-desktop-preview.py` now plans a
private shared-widget directory link. The account fixture launches actual helpers
and waits for their first frame before accepting installation. The repaired
installed benchmark completes all samples and captures. The broken
`readiness-installed-native.json` report is retained as a failing baseline, not a
performance result. An earlier capture attempt also revealed a probe-only QWindow
wrapper without grabWindow; importing the public QtQuick wrapper and using a
capture-completion handshake fixes that harness issue. Neither issue is hidden
by accepting missing samples.

The Store helper update has receipt
`~/.local/state/monet/desktop-preview/20261106T041641.205546Z/receipt.json`; the
shared-import repair has receipt
`~/.local/state/monet/desktop-preview/20261106T042237.416837Z/receipt.json`.
`catalog-installed.json` and `catalog-import-installed.json` retain each
application. Both verify unchanged checked preferences and all five native
guards; all 853 current planned payloads match. Plasma remains PID 424063; app
windows must be reopened to load their new code. Reverting just the Store helper
uses its receipt and keeps the import repair. For a full preview rollback, restore
these and the two batch-15 receipts in reverse chronological order, then reload
the user manager/cache and refresh Plasma. Current local testing/undo instructions
list the exact commands.

Current-source/report/artifact hashes are recorded in
`target/097-goal/readiness-cache-validation.json`. Full-image upgrade/rollback,
physical tests, sign-in/Settings/idle improvements and final release preparation
remain open. A physical menu/screen-behavior question is pending; no result is
assumed. No commit, push, OS image change or version bump was made.

## 0.9.7 batch 17: foreground power reads and repeat sign-in preparation

The input to this batch is frozen in `target/097-goal/power-startup-before/`,
with source digests in `sources.json`. The implementation changes only
`monet-quick` and `monet-fresh`. Power & Sleep still uses native `kreadconfig6`
for inherited defaults, nested groups and immutable policy; thirteen independent
reads run with at most four request-owned workers. Results retain request order.
The workers are joined before returning. There is no persistent pool or settings
cache, and ordinary standalone lock/privacy reads keep their behavior.

At sign-in, existing region/download receipts now avoid launching two helpers
which would immediately return. Their versioned receipt paths are unchanged.
Removing a receipt retries its helper; a failure propagates and does not suppress
the next retry. Desktop-menu repair is outside these checks and still runs.

### Measurements and limits

`target/097-goal/measure-power-startup.py` retains the measurement procedure.
It stages the current Linux sources twice, replaces the four baseline helper
sources from the frozen input, and uses identical UI, native runtime, private
profiles/buses and alternating variant order. Its staging directory is retained
and the script refuses to overwrite an earlier run. Source digests and raw
samples are in `power-settings-measured.json`; the worktree did not change during
the measurements. The primary run predates the CPU-intensive image build.

Seven samples per variant, with medians below:

| Measurement | Frozen input | Candidate |
| --- | ---: | ---: |
| Power helper elapsed | 180.034 ms | 145.411 ms |
| Power helper plus child CPU | 179.733 ms | 193.892 ms |
| Completed-setup sign-in helper elapsed | 211.276 ms | 81.863 ms |
| Completed-setup sign-in helper plus child CPU | 209.853 ms | 81.210 ms |
| Settings first frame | 391.535 ms | 388.281 ms |
| Settings initial Power & Sleep data frame | 563.173 ms | 509.712 ms |

The power helper trades roughly 14 ms of CPU for about 35 ms less waiting in
this run. This is a foreground responsiveness change, not evidence of lower idle
CPU or longer battery life. The sign-in helper does less work once setup is
complete; its timing is not whole-session sign-in or boot time. The native GUI
comparison uses a private Intel KWin/OpenGL virtual output and per-variant app
caches shared after the first sample; OS page caches/background work are not
controlled. Actual GUI captures are `power-settings-before.png` and
`power-settings-candidate.png`; compositor support/logs are retained. These
data-frame checks exclude full animation settlement and physical presentation.

The preliminary 15-sample helper-only run is retained as
`power-parallel-pilot.json`; its CPU and timings are separate from the primary
seven-sample comparison. No preferences change in either primary helper run.

### Regression and installation

```sh
python3 tools/test.py tests.test_power_reads tests.test_profile_upgrades \
  tests.test_settings_polling tests.test_power_connection tests.test_keep_awake \
  --summary target/097-goal/power-startup-regression.json
python3 tools/test.py tests.test_look tests.test_more_settings \
  tests.test_settings_feedback tests.test_settings_navigation \
  tests.test_regional_defaults tests.test_download_paths tests.test_startup_timing \
  --summary target/097-goal/power-startup-ui-regression.json
podman exec --workdir /src/monet monet097-laptop-build python3 \
  tests/fixtures/native-preview-install.py /output/laptop-native \
  /output/power-startup-preview.json \
  tests.test_native_preview,tests.test_power_reads,tests.test_settings_polling,tests.test_power_connection
```

The first two reports pass 42 and 457 checks, without skips or failed modules.
The third runs in the matching disposable native-preview container: 21 checks
pass, actual Settings/Store/Games entry points paint, paired Files/Ark executables
load, removing only the shared import link reproduces the expected failure, and
undo restores unchanged payloads while preserving a later personal edit.

Native policy tests cover a locked inherited group overruling an account value,
an inherited timeout, disabled policies, malformed values and an edit observed
by the next request. Bounded delayed reads retain result order. The sign-in
fixture verifies completed receipt skips, missing receipts, failure propagation,
successful retry and unchanged explicit empty/custom desktop bindings.

`apply-power-startup-preview.py` applies the verified current plan to the account.
`power-startup-installed.json` records two changed files, all 853 payloads
matching, five valid native components and zero changes in twelve checked
preference files. Its receipt is
`~/.local/state/monet/desktop-preview/20261106T045226.375844Z/receipt.json`.
`power-laptop-readonly.json` verifies identical actual-account native power
results from the preceding helper and the newly installed one; it does not
exercise sleep or change policy. Reopen Settings to load the new helper.
Testing/undo instructions list this receipt first for a full preview rollback.

Current source/report/artifact digests are recorded in
`target/097-goal/power-startup-validation.json`. A fresh release desktop test
image is building with `podman build --security-opt label=disable -f
tests/Containerfile -t localhost/monet-desktop-tests:097-release-candidate .`;
its current log is `release-test-image-build-v2.log`. The first attempt omitted
the SELinux option documented in batch 3; its private-socket inotify denial
failed compositor-reconnect coverage. That failing log is retained as
`release-test-image-build.log`. No test assertion or native monitor code was
changed to accept it. A running build is not a completed release test.
Full-image customized-profile upgrade/rollback, physical power/drive/input
qualification, complete sign-in/idle comparisons, language review and final
release preparation remain open. VERSION is 0.9.6; no commit or push was made.

## 0.9.7 batch 18: full desktop/Rust run and OS integration preparation

The fresh desktop runtime is image
`794f6ebf86dc451b64da383cb8b2b484a9d5a8a9c1c634b8d8a2088ff0a3d1c7`.
`release-test-image-build-v2.log` records its successful build, including the
native activity and launcher CTest stages. The first build's private-socket
SELinux denial remains in its separate log; the successful build uses the
already-documented `--security-opt label=disable` container option and keeps all
native assertions.

The complete run uses that immutable image, a read-only repository mount,
private homes/buses, no network, dropped capabilities and the pinned local
browser input. Its actual command, start/end times and exit code are in
`target/097-goal/release-candidate-run.json`; the summary/log are
`release-candidate-full-suite.json` and `release-candidate-full-suite.log`.
`release-candidate-inputs.json` records 2,252 input digests. They match before and
after the entire run, which exits zero.

| Check | Result |
| --- | --- |
| Python modules | All 115 discovered modules ran; none have zero checks |
| Python tests | 1,595 passed; 19 declared skips; no failures/errors |
| JavaScript | All selected Node tests pass |
| Browser form behavior | Eleven checks pass |
| Rust Linux workspace | 99 tests pass |
| Clippy | Workspace, all targets, warnings denied; passes |
| Source syntax | 27 shell and 107 Python files pass |

Every skipped Python case matches `tools/test.py`'s explicit environment policy:
three opt-in Flatpak cases, eight notification cases run by their private-bus
parent fixture, five opt-in native user-manager retry cases, two PowerShell
cases and one physical partition-discovery case. The strict desktop run does
not accept unexpected skips. These are declared limits, not device/Windows
qualification. The final summary lists every case and reason.

Rust runs in the full image's completed builder stage `1f46cc4fdc86`, whose
2,252 copied source inputs compare exactly with the tested snapshot before the
checks. It installs the CI storage test tools only inside its disposable
container, then runs:

```sh
cargo test --locked --workspace
cargo clippy --locked --workspace --all-targets -- -D warnings
```

`release-rust-suite-v2.log` retains results; the container exits zero. The first
attempt's login shell reset Cargo's image-provided PATH; it stops at command
lookup and is retained in `release-rust-suite.log`. A fail-fast non-login shell
fixes the harness. No Rust source was changed. `release-source-syntax.json`
lists the syntax-checked inputs. Completed evidence/digests are consolidated in
`release-desktop-validation.json`. This backlog/testing update follows the run;
only these two progress documents differ from that recorded input snapshot.

### Full-image and virtual-machine work in progress

`full-image-build-run.json` records the local integration build, with its
complete command in `full-image-build.log`. The Mesa base is pinned to
`ghcr.io/ublue-os/bazzite@sha256:3c67436e214fe34be11565cd3f0065789b1f107984ab247ca6cea4bcd2c94597`.
`full-image-inputs.json` matches the tested snapshot. This integration build
retains VERSION 0.9.6 and uses only a local tag; it is not a published 0.9.7
release. No successful OS-image lint, boot or upgrade is claimed yet.

The rootless VM toolbox contains QEMU/KVM and firmware, with only the task's
directory and `/dev/kvm` forwarded. No laptop block device or home/profile is
forwarded. `vm/cloud-input.json` records Fedora Cloud 45's official image URL,
size and verified SHA-256
`50bdc5e70f6a24f540932d15411c1c6ae9fcfa40fb990d876d83c5cc823b2ad0`.
The installer boots from an overlay, with task-only SSH credentials and UEFI
variables. The read-only inventory confirms the SecureBoot variable is enabled.
The installer initially lacked the split `virtio-vga` module; it uses the
supported standard VGA device. The separate toolbox for the Monet desktop adds
the distribution's explicit virtio-vga package. Failed launch logs are retained;
the stale QMP socket was moved only after its owner had exited and connection
was refused. No live VM was restarted because an observation timed out.

The guest command in `vm/install-baseline.py` checks its fixture hostname and
QEMU identity, all three disk serials, the blank target's 128 GiB size and lack
of mounts/partitions before running bootc against `/dev/vdb`. That device is
`vm/monet-system.qcow2`, created for this task; a separate virtual disk supports
a later unchanged-drive check. The published baseline reference is pinned to
`ghcr.io/happyhamster135/monet-amd@sha256:14cbe2969fe53bc35bb7c87c02cd3bd940723970d659bf0c194810c6e3abe310`.
`vm-baseline-install.log` records installation progress. A running bootc process
and a growing target repository are not completed installation or upgrade proof.

Full-image/customized-profile upgrade and rollback, complete sign-in/idle
comparisons, physical hardware/drives/input, language review and final release
preparation remain open. Nothing was committed, pushed or installed over the
laptop's OS image.

## 0.9.7 batch 19: localized search, Settings choices and candidate preparation

`tests/test_search_localization.py` exercises the actual compiled catalogs. Four
independent native queries per language must select the exact lock, download,
battery-limit and Keep-awake control, with translated labels/descriptions;
English queries retain all four destinations. Navigation never calls the setting
writer. The controlled pre-translation run fails in 28 language subtests; Swedish
already works. `search-translation-edits.json` records the 336 filled entries in
28 catalogs and preserved existing translations. Generator/catalog checks pass.
The focused backend run (`search-localization-regression.json`) passes 38 tests.
These changes complete these search destinations, not translation of every
new help paragraph or a native-speaker review of every language.

The Settings navigation fixture now accepts a locale and applies its actual
QLocale/layout direction, restoring defaults afterward. Native Arabic at 150%
and 200%, 14-point text, exposes a clipped timer choice: 467.031 logical pixels
of choices in 406 available pixels. `search-ar-focus-negative/` retains the
failing screenshots and assertions. Segments now measure the largest label
weight, cap their width to the containing card and use Flow with wrapping
labels. Captions remain centered; focus/Return/Enter assertions are unchanged.

Final current-QML results are `search-localized-settings-v5.json` and its four
per-language reports: 104 checks, no skips/errors/failures, German/Arabic/
Japanese/Thai, 150%/200%, 14-point text. `search-segments-final-matrix/result.json`
passes 78 checks without skips for English/Swedish at 125%/150%/200%, including
large text, reduced motion, exact-control focus and scrolling. These are real
Qt/KDE controls on private Xvfb/software rendering; they do not establish physical
touchpad or monitor behavior. The broader 93-check affected run also passes,
but precedes the final caption-centering adjustment; the final matrices include it.

`apply-search-layout-preview.py` applies the already-verified account plan.
`search-layout-installed.json` records 57 changed payloads, all 853 planned
payloads matching, five valid native components and zero changes in twelve
checked preferences. Receipt:
`~/.local/state/monet/desktop-preview/20261106T061830.398101Z/receipt.json`.
Undo instructions list it before earlier receipts. No Plasma restart or OS image
replacement was needed; reopen Settings for the new QML/catalogs.

VERSION, Cargo workspace/lock package versions and the current release-note
excerpt now identify an unpublished 0.9.7 candidate. The batch-18 complete suite
was for the preceding 0.9.6 snapshot, so final-source verification remains open.
The earlier full Mesa integration image built successfully (14 bootc checks
passed, one skipped), ID
`797c77556db0495b4a00929476b957af046ce522adfaab356555a37a671842db`.
It predates this batch and keeps version 0.9.6. Its complete build command/log
and input digests remain in `full-image-build-run.json`, `full-image-build.log`
and `full-image-inputs.json`; none are relabeled as final-candidate evidence.

`vm-baseline-install.log` exits zero; `vm/baseline-install-proof.json` records
the actual installed deployment and byte-for-byte unchanged other virtual drive.
Task-only SSH configuration is labeled against the target SELinux policy, without
disabling enforcement. Only the virtual OVMF variables receive a MOK request;
the known public enrollment password matches Setup. The first request harness
incorrectly relied on mokutil's exit status despite its 'not enrolled' output;
that harness is corrected to inspect the result and require pending enrollment.
The virtual enrollment/boot is still incomplete; no upgrade/rollback pass is
claimed. The laptop firmware, block devices and profile are never forwarded.

All changes remain local with no Git commit or push. Physical power/menu/input/
drive qualification, complete sign-in/idle comparisons, final source/image
verification and customized-profile upgrade/rollback remain release gates.

## 0.9.7 batch 20: candidate build failures, fixture ordering and VM baseline

`candidate097-source-inputs.json` freezes 2,253 inputs for the first local 0.9.7
candidate. Its Mesa build succeeds, but its complete desktop run finds the
sign-in look stamp still at 0.9.6. The stamp now matches VERSION, while the
content-based profile receipt still controls whether a migration runs. The
second snapshot is `candidate097-v2-source-inputs.json`; its successful Mesa
image is `3662a41330a4bd6df32173c789f4271a3c66119450e3501f4064ce8bd1cd03f8`.
Both build logs record 14 bootc checks passed and one skipped. These images
predate the later ICU runtime correction and are not the final accepted build.

The first complete desktop report has one version-stamp failure. The second
report (`candidate097-v2-desktop.json`) runs 1,616 checks with 19 declared skips
and failures in four modules: app detector, native archive failures, return UI
and Settings feedback. Complete logs are retained separately from the original
wrapper output. Both wrappers returned 143 while their containers remained
alive; the same actual containers were observed through terminal state and
their logs recovered with Podman. Neither worker was restarted on that signal.
The run metadata records this observation and unchanged inputs.

The form fixture used independent 1,000/1,200/1,450 ms timers across two
processes. `diag-app-detector-slow.json` reproduces the false failure with a
controlled delayed observer: native fields remain empty, but no original target
was ever captured (`seen=[]`). A private inherited-pipe handshake now captures
the original target before requesting the real Qt/GTK mutation, acknowledges
that mutation, then applies/rejects and verifies the native fields. The same
delayed-observer control passes (`diag-app-detector-fixed-slow.json`). Existing
fill, save, read-only, server/action changes and two-page cases still run.

Native archive discovery now tolerates an old X11 window ID only if a fresh
visible-window query proves that it vanished. Errors for a still-visible window
remain failures, as do nonterminal workers, incorrect queue states and native
password/full-disk assertions. Settings storage and recovery focus assertions
wait for their asynchronous completion within two seconds, preserving their
original conditions. The first Return-UI harness used a QTest convenience API
not exposed by this PySide binding; its error is retained. The explicit native
event-loop wait passes all 22 Return checks. Together with the other unchanged
modules in `release-fixture-fixes.json`, all 64 affected checks pass without
skips; this does not replace the final complete-suite run.

`candidate097-rust-v2.log` records 99 Rust workspace tests and all-target Clippy
with warnings denied, using final-version builder stage `576a021080ce`. All
2,253 recorded source inputs matched that builder before testing. Subsequent
changes are outside Rust/Cargo inputs. The first disposable-container attempt
dropped capabilities needed by apt; a separate quoting error stopped a driver
before its container ran. Neither is counted as passing validation.

`candidate097-nvidia-base.json` pins the NVIDIA base to
`ghcr.io/ublue-os/bazzite-nvidia-open@sha256:9c3c4df94a7731238021549ed3fc951c3ae5e1fee37667d16754f37ae0f73134`.
Its first build fails at the PDF bundle guard because installing development
headers upgrades ICU 78.3-8 to 78.3-9 after capture. `image/Containerfile` now
updates shipped ICU along with util-linux/Brotli before native build stages.
All strict native guards remain unchanged. Both corrected variants require
new successful builds; the failed attempt is `candidate097-nvidia.log`.

### Actual customized-profile VM baseline

`vm/baseline-boot-proof-final.json` proves the published 0.9.6 digest is booted,
Secure Boot is enabled, Universal Blue's key is already enrolled, SELinux is
Enforcing and no system units are failed. This mokutil returns one for an
already-enrolled key; the probe checks the explicit result rather than treating
the exit code alone as enrollment state. Screens retain actual MOK confirmation
and normal graphical sign-in/desktop, including `vm/baseline-desktop.png`.

The first hardware setup creates deployment serial 1 and reboots. Initial
offline SSH firewall/network changes accidentally targeted serial 0; the
read-only inspection (`vm-baseline-inspection.log`) identifies the active boot
symlink. `vm-prepare-active.log` records the corrected fixture on serial 1.
Its static slirp connection and SSH port are private VM provisioning only; no
product /usr files or laptop firewall/firmware/devices were changed. The one-shot
network diagnostic is disabled after access is verified.

A synthetic ordinary account, `monettest`, signs in through the actual login
manager and reaches Plasma. Its first panel is moved to the top at height 52
using Plasma's native scripting API. The fixture sets a custom Files shortcut,
explicit US time/measurement formats despite Stockholm's system time zone,
Gothenburg weather with manually selected Fahrenheit, Documents/Incoming as
download destination, enabled/disabled startup entries and disabled Steam
autostart. It includes a Unicode-named document and a desktop symlink. No actual
laptop user profile is copied into the VM.

`vm/profile-before.json` records the post-sign-out file hashes, modes/ownership,
symlink, semantic preferences, panel groups and booted image.
`vm/baseline-customized-snapshot.json` records a clean-shutdown disk/OVMF
checkpoint and the unchanged sentinel-drive digest. This is the precondition
for upgrade/rollback, not a passing upgrade result. An exported earlier Mesa
candidate is retained with its own hash in `vm/image-share/candidate.json`; it
predates the ICU fix and must not silently stand in for the corrected image.

Final full-source/native/image verification, actual customized-profile upgrade/
rollback, complete sign-in/idle comparisons and physical power/menu/drives/input
remain required. All work stays local, uncommitted and unpushed.

## 0.9.7 batch 21: complete frozen candidate run and corrected VM layout

`candidate097-v3-source-inputs.json` records 2,253 unchanged inputs for both
image builds and the full desktop run. Both builds finish successfully:

| Variant | Immutable local image ID |
| --- | --- |
| Mesa | `52d96c33312d9461b862158bb8f88b68ad709c3690c7e13128cee5c02d96cb05` |
| NVIDIA | `613bd192628c6cc0803707da60221ba6e087af9067a287173cf5dd1d1fccefe9` |

The run metadata/logs are `candidate097-v3-{mesa,nvidia}-run.json` and matching
logs. Each records 14 bootc lint checks passed and one skipped; all native
package/binary/ABI installation guards pass, including the ICU-corrected PDF
build. `candidate097-v3-image-cli.json` starts the real binary from each immutable
image and verifies version 0.9.7. These are build/runtime-command checks, not
complete OS boot/upgrade or graphics-device qualification.

`candidate097-v3-desktop-run.json` and its summary/log record the completed
strict desktop run: all 116 discovered modules ran nonzero checks, 1,597 Python
tests pass, 19 declared cases skip, and none fail/error. The skip names/reasons
match batch 18 exactly. Selected Node checks and eleven browser-form checks pass.
The complete run exits zero and all recorded inputs match before/after. The
46 Rust/Cargo inputs are unchanged from the 99-test/warnings-denied Clippy run.
Completed evidence and artifact digests are consolidated in
`candidate097-v3-validation.json`. Later progress-document edits are recorded
separately; they do not alter product or test sources.

The private exports are `vm/image-share/monet-097-{mesa,nvidia}-v3.oci.tar` with
metadata in `mesa-v3.json` and `nvidia-v3.json`. The exporter verifies image
version/config identity, reads the actual OCI manifest descriptor and hashes
the complete archive before its final rename. These artifacts remain local.
The guest staging driver verifies size, full hash, manifest, config digest,
architecture and version before any bootc switch. Its private server exposes
only image-share on container loopback; task SSH keys are outside that folder.

`final-candidate-preview-installed.json` records one changed sign-in helper,
all 853 payloads matching, five valid native components and no differences in
twelve preference files. Receipt:
`~/.local/state/monet/desktop-preview/20261106T075025.246764Z/receipt.json`.
The testing/undo guide lists it before older receipts. The laptop OS remains
0.9.6. `laptop-current-power-readonly.json` records unchanged configuration hashes
and actual native power data: AC screen/sleep and automatic locking disabled,
lock on resume enabled. Intel/NVIDIA PCI identities are recorded for later
physical checks; no sleep, lock, firmware or graphics setting is changed.

### Discarded VM layout and corrected baseline

The initial test disk used bootc to-disk's root-bound boot directory. Its generated
boot.mount binds /sysroot/boot, while GPT auto discovery creates boot.automount
for the same path with a two-minute idle timeout. The resulting stop of
monet-boot-arm during a long import times out; shutdown then reports an invalid
/boot remount and the staged NVIDIA baseline does not become booted. Diagnostics
are `vm-boot-generated-units.log`, `vm-boot-mount-diagnostic.log` and
`vm-nvidia-trial-diagnostic.log`. The initial image staging result is not an
accepted upgrade result, and its failed health check is retained. No product
service was weakened to accommodate that fixture.

`install-canonical-baseline.py` creates only the new serial-verified virtual
/dev/vdd, with Setup's separate 1 GiB EFI / 2 GiB ext4 boot / Btrfs root-subvolume
layout, and installs the same pinned published 0.9.6 image to-filesystem. The
image installation succeeds; configuration resumes without repartitioning.
The chroot needs proc/sys/dev mounts and target account-file labels before PAM
can open the new password files. Bulk relabeling from the cloud guest encounters
contexts its loaded policy does not support; copied account/vendor labels are
therefore retained, and only fixture-created configuration/account paths receive
their target labels. SELinux is never disabled. Original failed harness logs
and the successful `vm-canonical-baseline-finish-v5.log` are retained.

The captured account is mirrored with attributes/xattrs, removing newly seeded
skeleton defaults absent from the original profile. Source filesystem mounts
use read-only `rescue=nologreplay`, as documented in the
[Btrfs mount options](https://btrfs.readthedocs.io/en/latest/ch-mount-options.html).
No filesystem repair/log-clearing command is used.

`vm/canonical-baseline-profile-check.json` passes the original document/link/
permission/ownership, region, weather, download, startup, shortcut and panel
configuration checks. Secure Boot and SELinux remain enabled and no system units
are failed. `vm/canonical-boot-mount-proof.json` proves ext4 /boot, no conflicting
automount and an active shutdown-trial service after ordinary idle time.
`vm/canonical-baseline-snapshot.json` records its clean-shutdown disk/OVMF
checkpoint and unchanged sentinel drive. A separate NVIDIA copy avoids sharing
writable OS/sentinel disks between running VMs. These are baseline preconditions;
actual 0.9.7 upgrade/rollback and native application/profile checks remain open.

Full sign-in/idle comparisons and physical power/menu/drive/monitor/input checks
also remain open. No commit, push, publication or laptop OS replacement was made.

## 0.9.7 batch 22: installed-image upgrade/rollback and native app smoke

Both canonical-layout VMs boot the exact v3 local OCI manifest recorded in
batch 21. Each signs into its actual Plasma desktop, preserves the customized
profile through clean sign-out, queues rollback, boots the pinned published
0.9.6 image and signs in again. `vm/canonical-{mesa,nvidia}-stable-` reports
cover upgrade desktop and rollback prelogin/desktop checks; corresponding
`upgrade-durable.json` and `rollback-durable.json` reports verify saved state
after sign-out. Files, links, permissions, ownership, startup choices, manual
region/weather/units, download path and shortcut checks pass. Plasma's live
panels retain IDs 5/8/12, top/bottom/bottom positions and heights 52/60/60.
Secure Boot and enforcing SELinux remain enabled throughout.

The first GUI comparisons retain two fixture diagnostics. KGlobalAccel moves
the hand-written Files shortcut into `[services][org.kde.dolphin.desktop]` and
normalizes its key representation. The collector reads either native storage
form and compares QKeySequence values; actual Meta+Ctrl+F opens Files. A missing
preferred browser is pruned by the 0.9.6 desktop as well as the candidate,
because this isolated fixture lacks the browser Flatpak. Stable baseline
captures are made after 0.9.6 GUI sign-in/sign-out; the original proof and
negative reports remain. Subsequent round trips keep every comparison enabled.

The NVIDIA virtual machine has no NVIDIA PCI device. Published 0.9.6 and the
candidate both fail `nvidia-cdi-refresh.path` and `nvidia-cdi-refresh.service`
after NVIDIA-SMI reports no driver/device. Baseline/candidate diagnostics are
`canonical-nvidia-no-gpu-{baseline,candidate}.json`. The final verifier checks
the fixture lacks an NVIDIA device and allows only those two recorded baseline
failures, rejecting additional failed units. An early probe before CDI finished
starting found no failed units; its strict equality mismatch is retained.
Mesa has no failed system units. This qualifies profile/image behavior with a
virtual GPU; actual NVIDIA driver/device acceptance remains required.

Actual installed Settings, Store and Games reach their first frames on both
variants. Settings opens `power#lock`, scrolls to the lock timer and highlights
it (`candidate-settings.png`). Initial journal collection used the caller's
user filter and missed the app's records; corrected collection explicitly
selects UID 1000 and its user unit. These smoke observations check packaging
and rendering, without claiming comparable startup-speed measurements or
fully loaded Store contents.

Both native archive dialogs offer the drop destination and default to Desktop.
Enter starts extraction through installed Ark. The actual Desktop/sample file
contents and ownership match, and each durable queue record is `done`.
`mesa-native-transfers-complete.png` shows Completed and Open folder;
`mesa-native-open-folder.png` shows Files at Desktop/sample with hello.txt.
The file is still present after each rollback. The initial nested fixture
string did not parse; its replacement is parsed before submission. An early
smoke metadata field guessed the source directory; final assertions use the
actual Desktop destination shown in the dialog.

The extraction smoke adds Transfers widget 34 to panel 12 through the normal
product flow. This intentional UI action changes AppletOrder. The fixture
checks it was absent from the saved profile, removes precisely that widget
through Plasma, and verifies the original panel configuration before clean
sign-out/rollback. The diagnostic comparison with the smoke widget still
present is retained; no panel comparison is relaxed.

`mesa-native-open-folder.png` also exposes clipped disk-space text in Files.
`mesa-096-files-layout.png` reproduces it on published 0.9.6. Read-only font,
output and Files configuration is saved in `canonical-files-layout-context.json`.
The cause/fix is still open under 097-08; theme settings have not been changed.

Only ignored VM harness files and these progress documents changed. The 2,253
frozen inputs still match except the two recorded progress documents. Full
sign-in/idle comparisons, Files label investigation and physical power/menu/
drives/monitor/input checks remain. All work stays local and uncommitted.

The final consolidated proof is `vm/candidate097-v3-image-roundtrips.json`.
Both VMs shut down cleanly with exit zero; both unrelated sentinel drives retain
their original byte-for-byte digest. No build/import job remains running.

## 0.9.7 batch 23: Files disk-space button height

The native probe in `files-statusbar-probe/` uses actual KCapacityBar and
QToolButton components. With the original child-widget height, Kvantum's default
vertical layout margins are 9+9 pixels, leaving a 12-pixel button in a 30-pixel
row. The probe reproduces clipped text at 10/12/16-point fonts. Removing only
the vertical margins gives the button the available row height and fixes the
rendered text. The initial probe used a top-level stop button and inherited its
480-pixel default height; the corrected probe uses the actual child-widget
relationship. Its original diagnostics remain separate.

`image/files-recovery/patch.py` applies the change to the distribution's actual
StatusBarSpaceInfo layout. No theme setting or frame dimension changes.
`laptop-files-label-build.log` records the guarded native build and both existing
experience/loading test executables passing. `files-label-native-negative/`
captures the original paired Files binary; `files-label-native-positive/` and
`files-label-matrix/` capture the rebuilt pair in private Xvfb sessions with the
repository's six Kvantum themes. The ten native runs cover 125%, 150% and 200%,
12-point text and 16-point text at 200%. Every controlled delayed-drive navigation
and stale-reply check passes; the maximum observed metadata RPC is below 1.3 ms.
The compact contact sheet shows the actual status bars. Vertical text is readable;
very narrow large-font windows retain native horizontal elision.

`files-label-preview-installed.json` records five changed payloads, all 853
planned payloads matching, five valid native components and no differences in
twelve checked preference files. Receipt:
`~/.local/state/monet/desktop-preview/20261106T094123.350047Z/receipt.json`.
The testing/undo guide places it before earlier receipts. No running Files
window is closed; its next process loads the new pair.

An attempted private VM preview refuses the laptop-specific pair because its
expected base-binary hash differs (`vm/label-preview-guard.log`). The mismatched
pair is not run or installed; the original guard remains intact. Updated full
images must build their own matching pair and qualify the actual VM rendering.
The earlier v3 builds/tests/round trips retain their original source identities.

The source patch changes the final inputs. Rebuild both images and verify the
new frozen sources; full sign-in/idle comparisons and physical acceptance remain
open. Everything remains local, uncommitted and unpushed.

## 0.9.7 batch 24: v4 qualification and whole-session observations

All evidence in this section is under `target/097-goal/` unless prefixed `vm/`.
`candidate097-v4-source-inputs.json` freezes 2,253 inputs. Both image builds
finish with exit zero and unchanged inputs; `candidate097-v4-validation.json`
records their identities, the native Files binary/source correspondence and
the matching OCI exports. Both archives were independently rehashed. The Mesa
export wrapper returned 143 after its complete archive/result were written;
the completed artifact, OCI manifest and image identity pass verification. No
duplicate export is submitted.

The full serial run (`candidate097-v4-serial-desktop-run.json`) passes 116
modules, 1,597 checks and 19 declared skips, plus the selected Node checks and
11 browser-form checks. The original concurrent run retains failures in three
modules involving Xvfb/Electron startup and a bounded UI-refresh wait. An isolated
recheck passes 35 tests with one declared skip. A separate Xvfb-reset hypothesis
does not reproduce the problem. No fixture or assertion is weakened, and the
same frozen inputs pass the serial full run. The 46 current Cargo/Rust inputs
still match the previous 99 tests and warnings-denied Clippy pass.

Both actual v4 installed images pass profile comparisons before sign-in, in
the desktop and after clean sign-out, followed by the same three checks after
rollback to their pinned 0.9.6 images. Files opened by the saved custom shortcut
shows readable space text in `vm/mesa-v4-files-label.png` and
`vm/nvidia-v4-files-label.png`. The earlier extracted Desktop file remains
accessible after both rollbacks. Secure Boot and SELinux stay enabled. NVIDIA
uses a virtual GPU and retains only its two recorded baseline no-device CDI
exceptions. This does not qualify physical NVIDIA graphics. Both VMs shut down
cleanly; unrelated sentinel drives are checked separately in the round-trip
report. No laptop OS image or user preferences are replaced.

`vm/session-startup-probe.py` arms an unprivileged observer before credentials
are entered. A persistent KWin script records desktop/panel mapping and geometry;
the endpoint requires the full-size fixture surfaces to settle for 500 ms and
the Plasma scripting API to return the saved panel layout. Its elapsed time is
measured from the user-manager start, excluding password entry. Initial window
lists must be empty and wall/monotonic clock drift must stay below 20 ms. The
observer removes its private KWin script after each sample. Early dry runs and
the two attempts that refused an already-signed-out fixture remain separate.
The ignored logout helper now accepts that state only after verifying both the
user manager is inactive and no UID-1000 processes remain. Timing criteria and
product code are unchanged.

All three formal startup samples per phase are retained:

| Phase | Settled/responsive seconds | Median seconds |
| --- | --- | --- |
| Original 0.9.6 | 3.646, 3.596, 5.169 | 3.646 |
| v4 candidate | 6.298, 5.510, 5.340 | 5.510 |
| 0.9.6 after rollback | 6.403, 5.143, 5.178 | 5.178 |

No startup gain is established. The return baseline is also slower than the
original, so the full initial gap cannot be assigned to candidate code. These
are repeated sign-ins with existing page/app caches in the same 4-vCPU/8-GiB
virtual-GPU fixture. Separate boots, unfrozen external weather and scheduling
variation limit the comparison. Remote widget contents and input readiness are
not inferred from mapped surfaces.

`vm/session-idle-probe.py` measures the entire fixture-user cgroup, including
short-lived children, over three 30-second samples per visible/locked phase.
It checks the actual ScreenSaver state at both ends, includes normal periodic
helper bursts and reports virtual CPU steal. Original baseline pooled CPU is
0.887% visible / 0.855% locked; candidate is 10.403% / 10.293%, expressed as a
percentage of one virtual core. A separate 30-second visible sample after
rollback is 0.857%. Most extra candidate CPU is in Plasma and KWin. These results
require investigation. They do not establish lower background activity, hardware
wakeups or battery-life savings. The candidate's initial samples may overlap
deferred sign-in work; journals and process details remain available. The
upstream KWin packages differ (6.8.2-2 versus 6.8.2-3), so the comparison also
does not isolate Monet changes from its image base.

`vm/session-benchmark-comparison.json` retains the distributions and limits;
raw startup/idle samples, screenshots and runtime journals are alongside it.
The startup and CPU concerns remain open under 097-01/097-02. No product source
is changed in response to an unisolated measurement.

`laptop-acceptance-user-report.json` records the user's confirmation that
Desktop/widget right-click menus and AC stay-awake with screen, lock and sleep
timers Never work. Sleep/wake, lid, drive disconnect, monitor/input and physical
graphics acceptance remain separate. Their question about locking versus sleep
does not request removing a control; the existing UI is retained. Only these
two progress documents change after the v4 frozen checks. No commit, push,
publication or laptop OS replacement is made.


## 0.9.7 batch 25: cursor-driven redraws and native clock screen

Evidence remains under `target/097-goal/`. The v4 source/build/round-trip reports
retain their identities; the changes in this section require a new snapshot.

`vm/candidate-desktop-cpu-profile.json` locates most extra CPU in llvmpipe and
Qt's scenegraph. Replacing Hours temporarily with the static Image wallpaper
barely changes the cost (`vm/isolate-wallpaper-cpu.log`). Native animation and
object-tree snapshots find no continuous QML animation. A breakpoint on
QQuickWindow::maybeUpdate identifies QQuickTextInput::timerEvent as its caller.
The safe entry-address trace in `vm/candidate-cursor-address.json` maps the timer
owner to Weather's city field: invisible, enabled, actively focused and cursor
visible. The earlier attempted diagnostic call at a method breakpoint lost the
original Plasma process; its recovered session is diagnostic work, not product
stability evidence. That failed probe and the original logs are retained.

Weather now disables a hidden/inactive field, releases its focus, stops pending
search work and checks visibility again before deferred focus. The regression
in `tests/fixtures/widget-activity.py` opens and focuses city search, then closes
it. `weather-cursor-negative-source.json` verifies the negative source against
the v4 digest, adding only an objectName locator. The native negative fails on
all three retained properties (enabled/focused/cursor); the fixed source passes
(`weather-cursor-regression.json`). No assertion is relaxed.

Actual v4 lock logs also show VirtualKeyboardLoader is not a type, which sends
Monet's page to the retained Plasma fallback. The current KWinVirtualKeyboard
API fixes loading. The clock retains Fraunces, adapts to narrow screens and adds
an explicit Unlock action. Focus belongs to the cover while idle and the form
while visible. Deferred focus waits for the form to appear; hidden inputs never
receive it. Pointer entry does not dismiss the form. A first keyboard smoke
exposed missing cover focus after disabling the hidden input; native input tests
now cover this transition. Earlier manual interaction gaps exceeded the ten-second
form timeout; bounded controllers replace those attempts, with their negatives
kept. The consent button receives focus for the no-password UI state.

`tests/fixtures/lockscreen-native.py` launches the distribution's actual
kscreenlocker_greet in testing mode on its own Xvfb display and private session
bus, with no host display or system services. It uses the repository's fonts.
XTest sends Enter, moves into the password field, types one character and sends
Escape. Geometry, input delivery, cover restoration and absent hidden cursors are
asserted at 1280x800, 960x540 and 480x800 logical dimensions. A seventh case checks
the no-password consent UI; this is a UI-state check, not a passwordless PAM
backend result. `lockscreen-consent.json` passes. Early fixture attempts lacked
Qt's stderr logging and native activation settlement; those original reports
remain. The final checks use QT_FORCE_STDERR_LOGGING and actual input events,
rather than setting prompt visibility as proof of keyboard operation. Runtime
preflight and container dependencies explicitly cover the greeter, XTest,
fontconfig and the keyboard module.

`vm/lockscreen-consent-final-unlocked.json` verifies that the exact current page
accepts the fixture password through the actual locker and GetActive becomes
false. The native backend, its authentication checks and both fallback layers
are retained. `clock-weather-preview-installed.json` and
`clock-consent-preview-installed.json` record two then one changed payloads.
Receipts end in 20261106T121511.287239Z and 20261106T123052.119950Z. All 853 planned
payloads match, all five native guards pass and twelve checked preferences are
unchanged. The account testing/undo guide lists newest receipts first. No live
laptop session is restarted.

The repeated observations in `vm/idle-candidate-final-cursors/result.json` include
three 30-second visible and three locked samples, with normal helper bursts
retained. Pooled user-slice CPU is 1.3751% visible / 0.6045% locked of one virtual
core, versus original candidate 10.4026% / 10.2925%. Original baseline is
0.8868% / 0.8552%. The low and burst samples are all retained. An intermediate
clock page left password focus behind its idle cover; that separate greeter
cost is recorded before the cursor fix. The repeat measurements use private
QML overrides on the v4 image, not a rebuilt final image, and do not establish
battery-life, hardware-wakeup or universal speed gains. Corrected-source startup
samples still vary; no general startup improvement is claimed.

The user's follow-up records sleep/wake, lid and touchpad as working; external
monitor testing is untried. Drive and GPU qualification remain separate. Remove
the task's two QML-package overrides and restore its original fixture panel file
before final-image checks, so local files cannot mask an image defect. Final
builds/full-suite and installed-image verification remain open. Everything stays
local, uncommitted and unpushed.

### 0.9.7 final-image clock checks and bounded weather transition (batch 26)

The frozen v5 manifest contains 2,255 inputs. Both image builds finish unchanged;
`candidate097-v5-installed-source-proof.json` checks the installed clock/Weather
sources, native Files pair and label source, and the 46 unchanged Rust/Cargo
inputs. The serial desktop run passes 117 modules, 1,598 checks and the same 19
declared skips as v4, plus Node and 11 browser forms. Both actual images pass
native password unlocking and the preserved-profile prelogin/desktop/sign-out
checks without account QML overrides. See `vm/mesa-v5-image-ui.json`,
`vm/nvidia-v5-image-ui.json` and the matching native-unlock reports.

Three serial sign-ins in `vm/signin-v5-final-serial/result.json` measure
5,595.030 / 5,585.677 / 5,269.833 ms to settled, responsive saved panels. The
parallel qualification sign-ins are separate and excluded from this series.
No general startup improvement is established. All earlier samples remain.

The visible intervals in `vm/idle-v5-final-image/result.json` expose a separate
weather-wallpaper cost: approximately 311% of one virtual core during its
three-minute opacity animation. This run retains three visible and two locked
intervals; the wrapper ended with status 143 before the last locked observation
returned. The cause of that wrapper interruption is not established; it is not a
complete six-interval pass. The two completed locked observations are below 1%.
`vm/isolate-v5-wallpaper-cpu.log` measures 12-second intervals at 311.126% with
The Hours, 0.294% with a static wallpaper and 300.043% after restoring The Hours.

The weather veil now settles in 1.5 seconds. The native wallpaper fixture waits
for the real fog transition to finish and checks its final opacity, then changes
the controlled weather and verifies that display-off/window hiding still pause
work. `wallpaper-settle-negative-source.json` proves the negative control is the
exact v5 source; its test fails at the settling deadline with no QML warnings.
`wallpaper-settle-positive.json` passes the same test with the fixed source.
`vm/idle-wallpaper-settle-probe.json` observes 262.085 ms of whole-user CPU over
30 seconds (0.874% of one core) after a sign-in with only this wallpaper override.
That targeted observation is separate from final-image performance evidence.
`vm/wallpaper-settle-probe-retired.json` confirms removal of all task QML package
overrides and restoration of the original fixture Plasma configuration.

The laptop receipt 20261106T132004.687755Z installs one changed payload, verifies
all 853 payloads and five native guards, and preserves twelve checked preference
files. The next sign-in loads the wallpaper change; no live session is restarted.
The final images/full suite must now use the v6 snapshot. Physical monitor,
drive and graphics acceptance remain open; all work is local and unpublished.

### 0.9.7 final v6 verification (batch 27)

`candidate097-v6-source-inputs.json` freezes 2,255 inputs with manifest SHA-256
`533688bb77fdabc750d7d172301a27228404573073acb8146182ce2da99f8388`.
Both builds finish with unchanged inputs. The serial complete run passes 117
modules: 1,598 passed checks and the same 19 declared skips as v5, plus Node and
11 browser forms. Image exports were still finishing shortly after suite start;
the overlap is recorded, all modules passed and no assertions were changed.
The 46 Cargo/Rust inputs still match the 99-test and Clippy pass. The installed
source proof now includes the weather wallpaper, all three clock files, Weather
and the native Files pair with its matching corrected source archive.

Both VMs independently verify the full archive hash/size and OCI index/config
before staging. They boot the exact v6 digests, pass prelogin/graphical/post-sign-
out profile checks, accept the fixture password through the native locker, and
roll back to the pinned 0.9.6 image. Rollback profile checks and the extracted
file pass before/after sign-in and sign-out. Actual installed QML hashes match
the images; all three task account overrides are absent. Secure Boot/SELinux
remain enabled. NVIDIA permits only the recorded baseline no-device CDI unit
exceptions and makes no physical NVIDIA claim. Both VMs power off cleanly;
unrelated sentinel disk SHA-256 remains
`3b107e52f63fab104395d42dbb0d08b9ef9cb3f10b1e32fe083674dba258e7f8`.
See `vm/candidate097-v6-image-roundtrips.json` for all report hashes.

The final sign-in and idle series run after builds/tests and the other VM stop,
without account QML overrides. Startup samples are 5,077.066 / 5,710.279 /
5,633.558 ms to settled, responsive panels; no general gain is established.
Idle uses one bounded invocation per 30-second interval, avoiding a single
long-lived wrapper. All six finish on the same candidate boot, with lock state
checked at both ends. Visible CPU is 279.909 / 95.671 / 5,056.968 ms; locked CPU
is 345.111 / 96.186 / 343.279 ms. Pooled percentages of one virtual core are
6.0362% visible / 0.8718% locked. The high visible interval is mostly Plasma and
KWin and is retained. Interval accounting alone cannot attribute that cost to
a particular transition or show its subinterval timing. The first two visible
intervals are low; the series does not show the prior sustained weather fade.
The controlled native old/fixed test separately establishes prompt settling.
`vm/session-benchmark-v6-comparison.json` retains baseline, v4, private override,
the incomplete five-interval v5 run and the complete v6 run with source hashes.
Live weather, caches, scheduling and short samples limit comparisons; no
uniform CPU, whole-OS, hardware wakeup or battery-life gain is claimed.

All 2,255 frozen inputs still match after the final image tests. Subsequent edits
only update this testing record and the backlog; their post-run digests are
recorded separately. The latest laptop preview is unchanged, with receipt
20261106T132004.687755Z, 853 verified payloads, five valid native guards and twelve
checked preferences preserved. Both VMs are stopped on the published baseline.
Physical external-monitor, drive and graphics qualification remains separate.
Nothing is committed, pushed, published or rebased on the laptop.

### 0.9.7 thumbnail loading/cancellation audit (batch 28, in progress)

`files-thumbnail-v6-pair-proof.json` records the pair extracted directly from the
actual v6 image and checked against its installed runtime manifest. An older
bundle failed the byte-for-byte identity check and was not used as final-image
evidence. In `files-thumbnail-v6-rerun/result.json`, 2,000 distinct JPEG paths
share four 4,800×3,200 image payloads through hardlinks. Native thumbnail cache
URI metadata is checked; entries grow 5→84 while sixty state queries stay below
2.049 ms. Native navigation away takes 131.110 ms including typing. Returning to
the original tab preserves selection/scroll, and stale work does not replace
the local view. This tests native decoding/list pressure with warm shared file
data, not physical disk throughput. The first screenshot helper aborted because
its QGui application lacked the private display environment; the corrected
helper runs in a child with that environment. The failed run remains recorded.

The same evidence shows Stop disabled while previews are generated after folder
listing completes. `tests/fixtures/files-thumbnail-native.py` requires that
control, then exercises Stop, Escape, refresh, tab switching, preference and
selection preservation, and graceful process exit. It fails on the exact v6
pair at the missing-control assertion (`files-thumbnail-v6-negative.log`).

The native fix is under verification. Its first build compiled, but the bundle
compatibility check rejected removal of an existing private exported symbol.
That rejection is retained; the check is not weakened. The current helper keeps
the original no-argument symbol and an additional overload, and stores new
transient state in QObject properties to preserve class memory layouts. No
matching laptop installation or final-image claim is made for this new code yet.

The revised prototype seals successfully with the original exported symbol
retained, and no class data members added. The generic v6 test image refuses its
different laptop-runtime package set; the actual behavior checks run inside the
matching SDK with a private home/cache/bus/Xvfb. The native case passes at 100%,
125%, 150% and 200%. It verifies Stop through the existing action, Escape through
native keyboard input, paused cache growth after scrolling, resumed previews on
Refresh, retained completed cache entries and saved preview preference, correct
active-tab Stop state, preserved original tab selection/scroll, stale-reply
rejection and clean native process exit. Visual captures show Loading and Stop.
All four report hashes are in `files-thumbnail-native-matrix.json`; maximum RPC
latency is 4.560 ms. The earlier guard failures and harness failure are retained.

Receipt 20261106T144417.965361Z installs five changed account payloads, verifies
all 853 planned payloads/five native guards and preserves twelve checked
preference files. The next Files process loads the new pair; existing windows
are not terminated. The testing/undo guide is updated. Final images/full suite
must now use a new v7 frozen source snapshot; this native prototype does not
stand in for that qualification.

The final fixture uses 401 files in the original tab, selects the last item and
requires nonzero scroll before creating the photo tab. It also verifies the
current item and selection after Refresh. All four scale cases pass in
`files-thumbnail-native-strong-matrix.json`. The initial exact-state assertion
at 200% fails because the scroll maximum settles from 19,686 to 19,680, and the
offset follows it; current/selected paths, folder, label and splitter size stay
identical. `files-thumbnail-native-state200-diagnostic/` retains those values.
The final check follows the existing recovery contract: preserve the stored
offset, clamped only to the current valid range, and still require a nonzero
offset. It does not drop selection/current/expanded/folder/tab-size checks.
No product-code change was required for that viewport adjustment. The tested
native helper and installed preview are unchanged; new image qualification
must use the final fixture/source hashes.

### 0.9.7 final v7 image qualification (batch 29)

`candidate097-v7-source-inputs.json` freezes 2,257 inputs (manifest SHA-256
`3792acc34d2316cc813409ee6cb9c1a6e95c6b5922a8c14689662d270345bb42`). Both
pinned-base image builds finish successfully, including two native CTest checks
and complete native package/ABI seals. Installed sources match the five checked
clock/Weather/wallpaper QML files and the native Files payloads. The source
archive contains the exact final `thumbnail-jobs.py` helper. All 46 Cargo/Rust
inputs still match the earlier 99-test and warnings-denied Clippy pass.

`files-thumbnail-v7-production-matrix.json` records the final fixture against
the pairs extracted directly from the actual Mesa and NVIDIA images, each at
100% and 200%. All four cases pass Stop and native Escape, resumed previews on
Refresh, retained preview preference/cache, active-tab Stop state, original-tab
selection and nonzero scroll, current/selection after Refresh, stale-result
navigation and clean native process exit. Maximum state-query latency is
4.603 ms. The matching laptop-runtime prototype also passes 125% and 150%;
these are software-rendered synthetic shared-image workloads, not physical
drive or GPU throughput measurements.

After both exports and production native cases finish, the complete desktop
suite runs serially with no build/export/VM overlap. It passes 117 modules:
1,598 checks passed and the same 19 declared skips, plus Node and 11 browser-form
checks. Run state is terminal exit 0 with no changed inputs. The skip set matches
v5 exactly. `candidate097-v7-validation.json` links the build, source, suite,
native regression and account-preview proofs.

`candidate097-v7-exports-verified.json` records exporter checksums, OCI/config
consistency and independent full archive verification in each guest before a
successful guarded bootc staging unit. Both actual images boot 0.9.7 and pass
the customized-profile check before sign-in, on the graphical desktop and after
sign-out. Native password unlocking succeeds with the shipped Monet clock.
There are no shell, Weather or wallpaper account overrides, and all five QML
hashes match the image/source proof. Both installed native Files pairs and
their embedded source helper also match the production proofs.

Both fixtures then roll back to their pinned 0.9.6 images and pass the same
three profile phases. The earlier extracted file retains its content and owner;
files, startup entries, panels, shortcuts, regional/manual Weather choices,
downloads and power preferences persist. Secure Boot and SELinux remain enabled.
The NVIDIA fixture uses a virtual GPU and only its recorded baseline no-device
CDI exceptions. The SSH disconnect during NVIDIA rollback reboot and both
poweroffs is expected; actual version/profile checks and stopped exit-0 container
states independently verify the outcomes. Neither unrelated virtual sentinel
disk changes. `vm/candidate097-v7-image-roundtrips.json` links all twelve profile
checks, native authentication, installed UI and sentinel evidence.

Concurrent sign-ins in this batch test functionality; they are not formal
performance samples. The common desktop QML remains unchanged from the measured
v6 image, whose complete sample set and limitations remain in
`vm/session-benchmark-v6-comparison.json`. No general startup, uniform CPU or
battery-life gain is claimed from this Files-only change.

All 2,257 frozen inputs still match after both roundtrips; the pre-documentation
attestation records that fact and the unchanged Git HEAD. Only this testing
record and the backlog are updated afterward, with post-run hashes recorded
separately. Latest preview receipt 20261106T144417.965361Z remains installed:
853 payloads, five native guards and twelve checked preferences verified at
installation. Files uses the new native pair after its existing windows close;
the clock loads on the next lock, desktop QML on the next sign-in. No live
laptop session is terminated. Both VMs are cleanly stopped on 0.9.6.
Physical monitor, drive and graphics acceptance remains open. Nothing is
committed, pushed, published or rebased on the laptop.

### 0.9.7 physical NVIDIA client rendering (batch 30)

`candidate097-v7-physical-renderer-check.json` records eight additional passing
Store pixel checks at 150% on the laptop. In the basic Qt loop, QRhi identifies
the physical NVIDIA RTX A500 and all four cases reject a software device. The
same four screenshot/fallback/banner assertions pass in the normal threaded
OpenGL loop with the same exclusive NVIDIA client vendor environment. The
private KWin compositor independently reports Intel Mesa OpenGL and a virtual
output. Separate temporary HOME/XDG directories, private D-Bus and a private
Wayland socket keep the active laptop session and output configuration intact.

The initial `store-artwork-v7-nvidia-hardware` attempt applies NVIDIA variables
to the Intel compositor as well and fails its active-compositing guard before
the app tests. The retained `render-v7-nvidia-client.py` adapter applies those
variables only in the isolated client process, leaving fixture and test
assertions unchanged. Passing runs are in
`store-artwork-v7-nvidia-client-hardware/` and
`store-artwork-v7-nvidia-threaded-hardware/`. Report and adapter hashes are
retained; current product/test sources still match the final v7 snapshot.

Read-only inventory shows only the built-in display connected and no removable
drive attached. The user's external-monitor response, “Cannot test yet”, is
recorded in `laptop-acceptance-user-report.json`; it is not a passing result.
These client-renderer checks do not qualify physical outputs, hotplug, suspend,
long-running stability, native-image hardware boot or battery behavior. Those
physical acceptance limits remain open. No active laptop session is restarted,
and nothing is committed, pushed or published.

### 0.9.7 archive inspection correction (batch 31)

The default managed archive desktop entry previously started `unpack`, which
opens extraction preparation rather than a contents browser. It now executes
native Ark directly. `monet-archive-open.desktop` adds top-level Open and
Extract archive… actions; only the latter starts the destination-folder UI.
Both the image/add-on installer and account-preview plan carry this service,
and the native preview rewrites the browsing command to its guarded Ark wrapper.
The handler ID is unchanged, so no MIME preference rewrite is needed.

Build `tests/native/archive-open` with CMake in the matching native SDK, then run
`tests/fixtures/archive-open-native.py MENU_FIXTURE ARK_BINARY OUTPUT` there.
The fixture uses private HOME/XDG, D-Bus, accessibility and Xvfb. Real KDE
KFileItemActions constructs the menu, verifies both top-level actions and runs
either the preferred MIME application or the actual Open service action.
AT-SPI observes a known file in the native archive table; a window title alone
is not accepted as contents readiness. Both 8-entry and 12,000-entry ZIPs include
literal Unicode, `%U` and shell-metacharacter filenames. The fixture verifies
unchanged archive bytes, no extracted files and native browser exit 0.

`archive-open-native-v4/result.json` records all four passing cases. Contents
readiness is 206.5 / 208.9 ms for the small ZIP and 1,356.2 / 1,528.1 ms for the
large ZIP. These are synthetic warm local ZIPs in the matching SDK with software
X11 rendering, not a before/after claim for the user's file. Initial harness
attempts incorrectly required KIO's completed launcher to stay alive, then
misclassified an unreaped native child as running. They remain in the earlier
`archive-open-native*` folders. The final fixture adopts KIO's forked browser as
a child and verifies/reaps its actual exit status; menu/content/no-extraction
assertions remain intact.

`archive-open-affected-tests.json` has 32 passes, zero skips/failures across
archive preparation, password/cancellation behavior, extraction navigation,
download/MIME defaults and preview compatibility/restoration. The desktop
application validates and install/uninstall shell syntax passes. KDE's Type=Service
extension is checked through native KIO rather than the application-only desktop
entry validator.

Receipt 20261106T162311.847163Z installs only the two archive desktop entries,
verifies both and all five existing native guards, leaves twelve checked
preference files unchanged and refreshes application/menu caches. The ZIP
default remains `monet-archive.desktop`, now the contents browser. Other preview
payloads and live windows remain untouched; the local undo guide records this
receipt first. The full v7 image qualification predates these metadata changes
and is not claimed as final-image qualification for this correction.

### 0.9.7 preserve double-click extraction (batch 32)

The user clarifies that double-click should retain its previous extraction box;
only right-click Open was requested as a contents browser. Batch 31's default
browsing behavior is superseded. The application desktop entry is restored to
its prior `monet-files-tools unpack` command, without browser startup metadata.
The Open service action stays on the direct guarded Ark route.

`tests/fixtures/archive-open-native.py` now asserts both behaviors independently:
default dispatch must expose the extraction drop target and literal source path,
without a contents table; right-click Open must expose a known archive member.
Both cases keep archive bytes intact and create no extracted files. Explicit
Escape cancellation of extraction is expected to exit 1, while the native browser
quits with exit 0. The native launcher/menu implementation is unchanged.

`archive-default-extract-native-v2/result.json` has four passing cases. The
8/12,000-entry extraction boxes are ready in 176/202 ms; corresponding contents
browsers are ready in 193/1,342 ms. These remain private SDK/X11/software-rendered,
synthetic warm-local measurements. The first updated harness attempt correctly
observes the drop target but fails its overly exact window-caption match because
Qt adds “— Files”; it is retained in `archive-default-extract-native/`. The final
fixture accepts that caption suffix while retaining the actual drop-target,
source-path, route, archive-integrity, no-extraction and exit-status assertions.

Fourteen preference/preview checks pass without skips in
`archive-default-extract-checks.json`; desktop application validation also passes.
Receipt 20261106T163255.663760Z changes one installed application entry, preserving
the browsing service bytes and six checked preferences. The default MIME handler
ID stays unchanged. Caches and the undo guide are updated without closing any
active laptop windows. Earlier batch 31 reports describe its superseded default;
they are not evidence for current double-click behavior. Nothing is committed or
pushed.

### 0.9.7 power-page design and shell wiring (batch 33)

The [upstream greeter loader](https://raw.githubusercontent.com/KDE/plasma-workspace/master/logout-greeter/main.cpp)
uses a Plasma/Shell package; the native test below verifies this on the installed
6.8.2 runtime. The existing Monet page was copied only to global-theme logout folders,
so the screenshot shows the stock shell controls and theme icons. The installer
now preserves the shell's native page as `KdeLogout.qml`, installs Monet's page
as `MonetLogout.qml` and puts a signal-forwarding loader at `Logout.qml`. The
account-preview plan mirrors this wiring and retains the complete shell package.
Both older global-theme entry points still receive the complete Monet page.

`tests/test_power_screen.py` renders the new page with isolated context values
and captures its signals without a session/power backend. Thirteen cases cover
Mist/Smoke, portrait/short layouts, wrapped large German text, RTL, permission
visibility, native action/update routing, duplicate activation, countdowns,
Tab/arrows, Space, both Enter keys, Escape, outside-click cancellation, shared
countdown cancellation and cross-screen action ownership/removal.
The content scrolls to focused controls while Cancel remains visible. All thirteen
pass at 100%, 125%, 150% and 200%, with no skips or QML warnings. Captures retain
the native pixel sizes. Eleven affected preview/packaging checks also pass.
`power-screen-two-screen-negative.json` retains the failing pre-guard probe:
two page instances could emit different actions during the exit fade. The shared
claim fixes that race, and removing its owner releases it for the other page.
The final warning condition also follows native semantics: other-session work
warnings are not shown for sign-out.

The private KWin/OpenGL renderer fixture runs at native 150% scaling. Its basic
loop renders all four layout variants and identifies the NVIDIA RTX A500 through
QRhi, rejecting CPU renderers. The threaded OpenGL loop passes all thirteen cases
with the same exclusive NVIDIA client environment and a private Intel compositor.
No callback reads QRhi from Python on the threaded loop. Reports are in
`power-screen-gpu-basic-final/` and `power-screen-gpu-threaded-final/`; software captures and
scaling reports are under `power-screen-*`. These client-renderer observations
do not qualify physical display connections, suspend or general GPU stability.

`tests/fixtures/power-greeter-native.py` materializes the actual account-preview
shell plan in a private home and runs the real `ksmserver-logout-greeter --windowed`
on Xvfb. It uses a private session bus and a disconnected system bus: the CLI
flag itself is not treated as a power-action sandbox. The positive case observes
`MonetPowerScreen` with fallback disabled. The negative case intentionally corrupts
the Monet component and observes the preserved native fallback. Both save native
screenshots, accept only Escape, emit no power actions and exit 0. The preserved
native source SHA-256 is
`3f9d6449c070a2dd29db40288255bac78951124f40fac2da71aa8f3956a79110`, matching
the copy installed on the laptop. Results are in
`power-greeter-native-positive-verified/result.json` and
`power-greeter-native-fallback-final/result.json`.

The initial thirteen-file installation and six-file shared-action follow-up
remain in the receipt history. Latest receipt 20261106T174648.821127Z updates
the three copies of the page. These changes stay within the two legacy
global-theme logout folders and the desktop-shell logout folder. Sixteen
selected payloads and all five existing native guards verify. Fourteen checked
preferences, including theme, panels, power, locking, MIME handlers and downloads,
stay unchanged. Existing windows/session are not closed; the next prompt loads
the new page. The receipt and undo instructions precede the archive correction
in the local guide. No restart, shutdown, suspend or sign-out is performed on
the laptop. Full image qualification predates these source changes; no new
full-image or physical acceptance claim is made, and nothing is committed or
pushed.

### 0.9.7 hover and Files archive activation correction (batch 34)

The mouse probe found six hover misses at the right edges of restart/sign-out
cards: a transient ScrollView bar intercepted the pointer even with equal
content and viewport height. The page disables that bar when content fits and
reserves space when it is needed. Explicit hover and immediate opaque tinted
fills also remove colour-animation churn. The same 105-position probe then has
zero misses. The added real-mouse regression covers icon, text, arrow and card
edges in wide, portrait and short scrolling layouts. Fourteen power cases pass
at 100%/150%, two targeted cases at 200%, and the hover case on the private
150% threaded OpenGL client path. No power backend is attached.

`tests/fixtures/files-archive-native.py` now drives actual paired Dolphin GUI
double-click and Enter activation on disposable ZIPs with 8/12,000 entries.
Both show the extraction drop target (518/378 ms in this warm local run), cancel,
leave archive bytes unchanged and create no extracted files. The earlier KIO
fixture used runPreferredApplications; its default mode now uses OpenUrlJob,
as Dolphin's single-file activation does. Its four native cases pass, including
right-click Open inspecting both archives without extraction. These tests use
private homes, Xvfb and buses; no host window input or files are used.

The default-only look migration explicitly sets BrowseThroughArchives=false;
its real migration test retains an existing true preference and supplies false
when absent. Eleven migration/preview checks pass. The requested laptop preview
sets this preference to false, refreshes launch caches, and installs the hover
changes with receipt 20261106T183554.489130Z. Five files change; seven selected
payloads and all five native guards verify. Other checked preferences, the
extraction desktop entry and the separate Open service stay unchanged. Existing
Files may retain old launch data, so close and reopen that app once; reopening
the power prompt loads its correction. A laptop restart is not needed.

Reports are `target/097-goal/power-hover-{controls,scale150,scale200,defaults-packaging}.json`,
`power-hover-gpu/result.json`, `files-archive-activation-v3/result.json`,
`archive-real-single-activation-final/result.json` and
`hover-archive-preview-installed.json`. Full-image/physical qualification has not
been repeated for this correction. Everything remains local and uncommitted.

### 0.9.7 tab-close target, app priority and RPM activation (batch 35)

The Files event filter expands input around the existing native CloseButton to
max(32, icon size + 16) logical pixels, clipped to its tab. It forwards native
enter/hover/press/release events; the style, painted geometry and close signal
remain unchanged. Native tests verify padded clicks, press/drag-away cancellation,
ordinary tab selection, reordering and RTL. Both added cases pass under
MonetDark/Kvantum at 100%, 150% and 200%. The initial scaled test had an offscreen
target beyond its virtual screen; bounding its window to the available area
corrected the fixture. CTest's experience and loading suites pass. The rebuilt
guarded Dolphin executable uses the byte-identical prior private library and
retains updated corresponding source; private preview install/load/undo passes.

Kicker supplies favoriteId for installed apps but not arbitrary running apps.
The menu now also promotes executable file URLs and KWin activation rows whose
task AppName/AppId matches the query. A file viewer's matching document title is
insufficient. Task metadata changes reapply filtering. Ten search UI cases and
six navigation cases pass; the final search source also passes after excluding
folders named like executables. A read-only real Wayland/Kicker query observes
ChatGPT as the first application, with its RPM and running Archives window left
among other results. No search result is activated by this observation.

The third screenshot shows chatgpt.x86_64.rpm (621,826,837 bytes), which was still
associated with Archives. The archive desktop entry, service menu, image defaults
and first-login MIME list now include application/x-rpm. Its suggested destination
also removes .rpm. Native Files double-click/Enter tests with the rebuilt pair
show extraction prompts for 8/12,000-entry ZIPs and this actual large RPM in
519/384/487 ms, cancel them, and retain source hashes without extraction. These
are private warm-local observations, not general cold-start/slow-drive timings.
Right-click Open retains native contents inspection. Four MIME/directory tests
pass. The broader affected run has 55 checks with one native encrypted-extractor
skip; that check passes separately in the SDK with the matching patched Ark.
Using the stock SDK Ark reproduces its already-known false success on password
cancellation; no new source workaround is introduced for that superseded runtime.

Receipt 20261106T201754.718157Z installs ten changed files and verifies thirteen
selected payloads/five native guards. Only application/x-rpm in mimeapps.list
changes among the checked preference files. The running desktop shell was
refreshed successfully, preserving the current Files and ChatGPT processes.
Reopen Files once to load its new executable. The account guide records this
receipt and undo order. No laptop restart, RPM installation, commit or push is
performed. Evidence is under target/097-goal in tab-search-archive-preview-installed.json,
tab-target-native-style-final.log, search-app-priority-installed-source.json,
search-app-priority-controls-final.json, search-live-priority.json,
archive-zip-rpm-activation-final/result.json, archive-rpm-defaults-final.json,
tab-target-native-encrypted-final.json and tab-target-preview-private.json.

### 0.9.7 archive authorization and repeat-picker positioning (batch 36)

The laptop's native KDesktopFile query authorizes the default extraction app
but rejects the 0644 user-owned service menu. KDE's
[service-file authorization](https://raw.githubusercontent.com/KDE/kconfig/master/src/core/kdesktopfile.cpp)
accepts root-owned files or executable files outside the application directories.
The account preview and Linux installer now install Monet's own service menus
at 0755. A new normal-user SDK account (UID 1000) runs the native fixtures:
four default/Open KIO cases and two actual Dolphin double-click/Enter cases pass,
with archive hashes retained and no extraction. The earlier root fixtures could
not detect this because root ownership satisfies the same authorization check.
The read-only laptop query in archive-authorization-before.json has
menu_authorized=false; archive-authorization-after.json has true. The global
launch permission and preferred extraction app remain authorized throughout.

The preview installer previously skipped identical bytes even when modes were
wrong. It now records before/after modes and installs permission-only changes.
Restore/retirement retain later permission edits. Two added tests cover mode-only
installation/undo and protection of personal chmod changes; legacy receipts
remain supported. No archive file permissions or global policy are changed.

The repeat picker is drawn from template controls and a standalone item popup.
It measures real window space and maps the anchor into the Controls overlay.
Tests reproduce Plasma Dialog's overlay at a negative half-window offset;
using window coordinates or a ComboBox popup's automatic flipping detached the
menu. The final picker accounts for that offset and controls its own placement.
It opens adjacent above/below, preserves native note recurrence persistence,
and uses rounded green rows matching the button. Pointer selection saves one
choice; Escape closes only the picker. Keyboard recurrence, reopening/resizing,
and the separate real NotesPopup window are covered. Three focused cases pass
at 100%, 150% and 200%; the separate notes-window case also passes at 150% on a
private KWin Wayland output. Software captures are in calendar-repeat-layout/.

archive-trust-calendar-final-checks.json records 34 passing installer/desktop/
notes checks without skips. Native normal-user results are in
archive-authorization-nonroot/ and files-archive-authorization-nonroot/;
calendar-repeat-scale150.json, calendar-repeat-scale200.json and
calendar-repeat-wayland/result.json retain scaled/native placement checks.
Receipt 20261106T205033.991070Z records 24 changes: four mode-only service menus
and twenty shared DayNotes copies. Selected bytes and modes/five native guards
verify, with fifteen checked preference/notes files unchanged. The desktop is
refreshed to load QML; no laptop restart, commit, push or full-image qualification
is performed. The local guide includes mode-aware undo instructions.

### Local correction batch 37: brightness memory and Home Bar names

`tests.test_brightness_memory` checks atomic private state, malformed/invalid
values, range changes and ignoring restore/profile events. Its native fixture
uses an isolated session bus, disconnected system bus and disposable HOME/XDG
paths. A fake PowerDevil arrives after the real helper, exposes an external
screen before the internal panel, emits key/slider events, then restarts with a
new internal display number. The helper restores 27%, saves 43%, restores it in
a new session and after renumbering, and saves the final 61% slider value.
External brightness is never overwritten. Sixteen focused checks, including
native-preview reversibility and dock fallback, pass with zero skips.

The native dock was rebuilt against the laptop's Plasma 6.8.2 runtime with the
same guarded bundle approach. Its actual QMenu shows Unpin from Home Bar and
Configure Home Bar, with keyboard mnemonics normalized in the assertion. The
same fixture retains pointer launch, immediate starting feedback, duplicate
suppression, concurrent launches, failure handling, Shift and middle-click
checks. Both pin actions and unpin keep their native implementations. All
catalogs pass `tools/make-translations.py --check`; Swedish wording is included.

Receipt `20261106T210319.762180Z` changes ten local preview files and verifies
twelve planned payloads/all five native guards. Fourteen preference files,
including power policy, output configuration and dock launchers, stay unchanged.
The new brightness unit is enabled, active and passes systemd verification.
Its initial state is 20%, matching the laptop's current logical value; the HDR
kernel backlight reading of 100% is intentionally not used. The desktop is
refreshed without closing apps. This is source/account-preview validation,
not a reboot, firmware/login-screen or physical-monitor qualification.

For the remaining laptop check, choose a recognizable level (for example 35%),
restart when convenient, then check the level after signing in. Repeat once
using the brightness keys. The firmware/startup logo is outside the signed-in
session's brightness control. No settings or hardware renderer are changed to
work around that distinction.

Undo this batch using the exact receipt and the instructions in
`~/.local/state/monet/local-test-build/TESTING-AND-UNDO.txt`: stop
`monet-brightness.service`, restore the receipt, reload the user manager, and
refresh plasmashell. The saved level is ordinary user state and can be kept for
future reinstalls. No archive files, commits, pushes or OS images are involved.


### Local correction batch 38: RPM header contents listing

The actual reported ChatGPT RPM is copied with reflink support into ignored
fixture storage; GUI/native probes only read that copy. The original download
matches its SHA-256 before and after installation. Native original/candidate
plugins list 4,185 members with identical paths, sizes, permissions, link
metadata and file types. Raw sequential listing takes 14,820 ms versus 67 ms
using the existing RPM header. Owner/group names are available from the header
rather than the cpio stream's numeric IDs.

`tests/fixtures/rpm-open-native.py` creates private HOME/XDG/session/accessibility
buses and Xvfb with a disconnected system bus. Readiness requires both top-level
rows and an enabled Extract action, rather than the first painted window. Actual
Archives takes 17,906 ms before and 219 ms after. A separate UID 1000 test installs
the exact preview planner's Ark payload, wrapper and guard into a temporary
account and opens the same package in 272 ms. The final packaged binary/plugin
match the installed native dependency sets and have no build RPATH. These are
warm-file X11 measurements, not cold-drive/network or physical Wayland latency
qualification. No input package is extracted in the GUI measurements.

`tests/native/rpm-list` loads actual plugins, including for selected extraction.
`tests/fixtures/rpm-list-native.py` builds but never installs a small disposable
RPM containing directories, hard links, a symlink, a ghost and a filename with
quotes, Unicode and shell syntax. Paths match the original plugin; only the
selected special-name file is extracted. The fixture reproduces ArchiveModel's
normal removal of the cpio ./ prefix at the extraction boundary. ZIP fallback,
invalid-header errors and worker-thread interruption also pass. No scriptlets
run. The helper uses a single argument-vector RPM query, not a shell. Output,
entry count and time are bounded, and incomplete queries fall back without
publishing partial header entries. Actual decompression remains native when
extracting or previewing a member.

Twenty-two focused bundle/preview/password checks pass with zero skips.
Schema 2 rejects missing/tampered plugins and query runtimes, retains schema 1
compatibility, and scopes private plugins to a guarded Ark launch. Source RPM,
prepared source, helper header and build inputs ship with the local bundle.

Receipt 20261106T212007.948436Z installs 7 changed files; all eight planned
payloads and five native guards verify. Fifteen checked preference/state files
(including brightness memory) and the original RPM stay unchanged. Reopen
Archives to load it; neither the desktop nor laptop is restarted. Undo with
Archives closed using the exact receipt in
`~/.local/state/monet/local-test-build/TESTING-AND-UNDO.txt`. No commit, push,
publication or new full-image qualification is performed.


### Local correction batch 39: session and sign-in continuity

The native logout executable is rebuilt from the exact Fedora Plasma Workspace
6.8.2 source RPM and installed only through a reversible account preview and
runtime guard. The full image has the corresponding build stage. Authentication,
updates and session policy remain KDE's. Only the accepted Monet page is retained;
a stock/fallback theme keeps its original close behavior. The surface moves
behind applications and releases keyboard input, so the native session's save
prompts stay usable. A shutdown-service disconnect removes it on cancellation;
failed requests do not leave an orphaned backdrop.

`session-backdrop-native-complete/result.json` exercises the actual rebuilt
executable in GUI_TEST mode on private X11/profile/buses with a disconnected
system bus. It retains the Monet transition, allows an independent unsaved-work
prompt to focus, and exits when a fake shutdown connection closes. The final
render includes bundled branding and private installed fonts and was inspected.
There are no laptop power/session calls or GPU/physical restart claims.

`login-brightness-native-final/result.json` runs the real rebuilt greeter with
its mock authentication backend, private X server and fake brightness service.
Brightness keys decrease/increase the level and the real slider changes it.
Special-key handling goes through the native window event filter, so password
field focus does not swallow brightness keys. Ordinary password/authentication
handling stays native. This does not test a physical laptop login or hardware
brightness controller. The runtime has matching package identities/linked ABI;
the laptop's earlier Monet-patched base greeter is pinned independently from the
SDK's stock binary for safe local fallback.

The boot-time system helper copies only the numeric internal-panel brightness
and stable output identity into the separate plasmalogin account. It retains
that account's modes, scaling, HDR, other outputs and unrelated configuration.
Unit tests cover identity matching, new greeter state, invalid values and the
absence of new greeter idle/suspend/profile-brightness defaults. Normal desktop
brightness memory stamps the most recently used account even if its level did
not change. The root-owned preview requires administrator authentication and
never restarts display-manager, changes PAM, or signs out the current desktop.
`tools/install-login-preview.py` defaults to a read-only plan and records a
root-owned undo receipt for any applied files and seeded greeter configuration.
The administrator-approved system installation completed under receipt
`/var/lib/monet/login-preview/20261106T225609.063998Z/receipt.json`.
Root verification checks all fifteen receipt entries, root-owned payloads,
the native runtime guard and the plasmalogin-owned internal brightness of 0.2.
Systemd verification caught the initial preview's duplicate power-service bus
owner. The corrected target wants the existing `plasma-powerdevil.service`;
the duplicate unit is removed and the original undo receipt is retained.
System and user unit validation now pass. The existing desktop power service
was not restarted; the desktop shell was refreshed to load the menu fixes.

Cold search metadata tests hold the running-window count at zero, publish app
metadata after a folder result, and verify application-first keyboard launch.
The native isolated runner reads the current app catalog without any running
windows and finds Zen and the newly registered portable ChatGPT launcher.
`cold-all-apps-after.json` also records both in the actual freshly constructed
Kicker All apps model, using the account's catalog without launching either.
The latter points to the already extracted executable; no archive is extracted
or package installed. Keep that portable app's folder in place.

Account receipts from 20261106T221057.706016Z through the newest batch receipt
contain the desktop changes and branding refinements. Fourteen checked user
preferences remain unchanged; all six native guards and 76 selected payloads
verify. Undo those receipts newest-first using
`~/.local/state/monet/local-test-build/TESTING-AND-UNDO.txt`. The separate system
receipt needs administrator access to undo. No commit, push,
publication or new full-image qualification is performed.

Restart when convenient to test the installed system login preview. Check the
sign-in brightness with both the slider and brightness keys, then search Zen
and ChatGPT before opening either. Check restart/shutdown continuity with saved
work, and separately cancel an application's unsaved-work prompt to verify the
backdrop disappears and the desktop remains usable.

### Local correction batch 40: search responsiveness and a covering power screen

Kicker's URL role performs synchronous QFileInfo existence/symlink checks.
Ranking now uses application IDs, match icons/names and native window metadata
without reading that role. Both filter proxies use deferred, coalesced refreshes
outside source-model update signals. The native query has a 90 ms typing delay;
Enter waits for the current query, and closing the menu cancels searches.
The metadata regression uses a real QAbstractListModel, records zero URL reads
and processes 100 metadata updates. The rapid-typing regression verifies one
runner request for ChatGPT and correct deferred Enter activation.

`tests/fixtures/menu-search-native.py` loads the actual menu representation with
the real Kicker runner, reads the account's app catalog on a private bus/cache,
and disables every launch hook. Before correction, its second-character samples
include roughly 0.5 seconds for `ch` and 1.1 seconds for `se` (including the
intentional 180 ms observation interval); it did not reproduce a permanent
hang. Corrected repeated ChatGPT, Zen and Settings queries complete with an
event-loop heartbeat. These local samples are not a general latency guarantee.

The native logout greeter now retains an overlay above ordinary apps, releases
its exclusive keyboard grab, and lowers the cover when the unfiltered native
window model reports new windows or attention. This includes windows omitted
from the Home Bar. Closing those windows restores the cover. A delayed Show
applications button handles prompts embedded inside an existing window without
forcing apps to close or changing native shutdown/update authorization.
The build intentionally adds only libtaskmanager.so.6 to the original direct
dependencies; package capture includes that library's complete linked runtime,
and normal ABI, source and account runtime guards remain required.

`tests/fixtures/session-cover-wayland.py` uses a private KWin Wayland compositor,
GUI_TEST backend and disconnected system bus. Full-compositor screenshots prove
the solid magenta fullscreen test app is hidden by Monet (#f3f1ec), visible while
a new native save prompt exists (#d700a0), and hidden after that prompt closes.
Separate restart and shutdown runs pass, and fake shutdown cancellation exits
the greeter. The X11 native handoff/cancellation case passes too. The rendered
Monet restart page was visually inspected. No test restarts the laptop.

For laptop testing, use the Windows key and type ChatGPT or Zen, including quick
typing and repeated erase/retype. Search should accept the whole word and keep
apps first. Then save your work and test Restart or Shut Down: the Monet screen
should cover apps while they close. A real save prompt should remain accessible;
Show applications is also available if an app needs attention. The account
preview's installed receipt and TESTING-AND-UNDO.txt record reversible changes.
No system-login reinstall is required for this batch. Nothing is committed or
pushed; physical restart/shutdown continuity still needs the user's check.

Account receipt 20261106T232552.998480Z installs this batch. Ten files changed;
all 69 selected payloads and six native guards verify. Fourteen checked account
preferences are unchanged, and the desktop shell was refreshed successfully.
`session-cover-final-checks.json` records 41 checks, zero skips and no failures.
`search-cover-preview-installed.json` and `search-cover-local-validation.json`
record installation and native/private-session evidence. Undo this receipt
before older account receipts using TESTING-AND-UNDO.txt.
