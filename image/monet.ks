# Monet installer: a kickstart for the Fedora network installer.
#
# Only the system to install is fixed here. The installer still asks where to
# install (so Monet can go next to Windows), for Wi-Fi, and for your account.
# @IMAGE@ is filled in when the installer is built.

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
