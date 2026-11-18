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
