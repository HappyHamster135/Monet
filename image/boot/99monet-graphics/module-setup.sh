#!/bin/bash
# Include the rule in the portable initramfs, not in the running user's config.
check() { return 0; }
depends() { echo "kernel-modules udev-rules"; }
install() { inst_rules "$moddir/61-monet-nvidia-kms.rules"; }
