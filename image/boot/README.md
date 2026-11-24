# Early graphics loading

The inherited NVIDIA image forcibly loaded Intel, AMD and NVIDIA graphics
modules before udev. A connected Intel/NVIDIA ThinkPad spent 6.2 seconds in
`dracut-pre-udev.service` and loaded `amdgpu` despite having no AMD GPU.

`prepare.py` changes the vendor preload file to include those same modules using
`add_drivers`. Udev's existing PCI modalias rules load the matching drivers.
The initramfs also receives a rule to load `nvidia_drm` when an NVIDIA PCI device
is bound, preserving early KMS for NVIDIA displays. It handles both coldplug and
later binding. Other force-loaded modules, including storage and VFIO, remain
as configured. User kernel arguments such as `rd.driver.pre` still work.

The generic initramfs, GPU firmware, disk unlock modules, boot health checks and
rollback remain present. The configuration is applied only inside the image
build. It never changes the running installation or its kernel modules.

Tests exercise configuration conversion, the dracut module and the udev rule.
In an isolated container with no capabilities, `udevadm test` queues NVIDIA
DRM/KMS for NVIDIA PCI add and bind events, and not for an Intel GPU add event.
That test does not execute the queued module-loading commands.
An image boot on Intel, AMD, NVIDIA and hybrid hardware is still needed to
establish cold-boot gains and display handoff behavior. The existing measured
firmware and loader time is separate; this change does not establish a
few-second power-on time.

Dracut documents [driver inclusion and force loading](https://dracut-ng.github.io/dracut/man/dracut.8.html)
and [module installation](https://dracut-ng.github.io/dracut/developer/modules.html).

## Login prerequisites

The image also moves Bazzite's tuning/package-daemon wait behind its original
hardware receipt check. An already configured PC can finish that check before
those daemons start. A changed image, branch, Fedora version or hardware-setup
revision still waits for both daemons before running the original migration.
The migration body and its completion records are unchanged. Image preparation
rejects an unrecognized upstream guard or dependency layout for review.

Windows storage preparation retains its safe-mount, key-export and login-screen
ordering, and no longer depends on NetworkManager. Wi-Fi profile exchange is a
separate low-priority unit after the login manager, network manager and confirmed
Windows mount. Settings' manual unlock starts that exchange too. This lets the
login screen start without waiting for profile export/import.

The login manager's udev-settle safeguard remains: upstream added it to avoid
[black screens when DRM devices are still initializing](https://github.com/KDE/plasma-login-manager/commit/a8c752fe28c36fa7d3b95461a7b24ce2d9de7f69).
These changes need boot qualification on the complete image; isolated dependency
and helper measurements do not establish a new power-on-to-login time.

## Certificate trust on normal boots

The inherited legacy `bootc-update-ca-trust.service` regenerates the trust bundle
on every boot, taking 1.555 seconds before `sysinit.target` in the recorded
ThinkPad baseline. Image preparation adds Fedora's current
[`ConditionNeedsUpdate=/etc` lifecycle](https://gitlab.com/fedora/bootc/base-images/-/merge_requests/663):
regenerate on first boot and after a deployment, then skip ordinary reboots.
OSTree removes `/etc/.updated` when deploying; `systemd-update-done.service`
recreates it. Regeneration remains ordered before that marker and
`systemd-resolved.service`, so DNS-over-TLS cannot read an old bundle first.
Local trust edits still require `update-ca-trust`, as in Fedora's service.

The command and existing prerequisites remain intact. Preparation rejects
unrecognized service layouts or a second trust writer. The boot benchmark checks
that the candidate runs regeneration on its initial boot and skips it on every
timed normal reboot. This is a candidate optimization until that image test
passes; the recorded service duration alone is not an end-to-end saving.
