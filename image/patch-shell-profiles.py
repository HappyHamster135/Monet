"""Adjust Bazzite's system shell profiles when building Monet."""

from pathlib import Path
import sys


def replace(profile, before, after):
    if not profile.is_file():
        return
    original = profile.read_text(encoding="utf-8")
    updated = original.replace(before, after, 1)
    if updated != original:
        profile.write_text(updated, encoding="utf-8")


def patch(directory):
    # The wrapper can be present before the first-boot copy reaches brew.sh.
    prefix = "/home/linuxbrew/.linuxbrew"
    main = f"{prefix}/Homebrew/Library/Homebrew/brew.sh"
    replace(
        directory / "brew.sh",
        f"&& -d {prefix} &&",
        f"&& -x {prefix}/bin/brew && -r {main} &&",
    )
    interactive = '"x${BREW_BASH_COMPLETION-}" = x ]; then'
    replace(
        directory / "brew-bash-completion.sh",
        interactive,
        f'"x${{BREW_BASH_COMPLETION-}}" = x ] &&\n'
        f'   [ -x {prefix}/bin/brew ] && [ -r {main} ]; then',
    )

    # A new encrypted system can keep its OSTree files private to root.
    # Read the booted deployment through the same system service as Settings.
    replace(
        directory / "verify_motd.sh",
        '''CURRENT_REF=$(rpm-ostree status --json | jq -r '.deployments[0]["container-image-reference"] // empty')''',
        '''CURRENT_REF=$(busctl --system --timeout=2s --allow-interactive-authorization=no --json=short \\
        get-property org.projectatomic.rpmostree1 /org/projectatomic/rpmostree1/Sysroot \\
        org.projectatomic.rpmostree1.Sysroot Deployments 2>/dev/null | \\
        jq -r '[.data[]? | select(.booted.data == true) | .["container-image-reference"].data | strings]
            | if length == 1 then .[0] else empty end' 2>/dev/null) || CURRENT_REF=''',
    )


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
