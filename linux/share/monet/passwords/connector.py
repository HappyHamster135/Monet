"""The reviewed, Mozilla-signed connector shipped with this Monet release.

The digest pins an already signed artifact; Zen still verifies Mozilla's
signature and asks the user to accept installation or update.
"""
import hashlib
from pathlib import Path

VERSION = '0.1.1'
SHA256 = '72ffb607b98999e1e0b680ce347425b2d1cd1e4e7d6629c28c4b079a5cd97d47'
MAX_BYTES = 8 * 1024 * 1024


def verified_bytes(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name('connector.xpi')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('The browser connector is not installed completely. Update Monet and try again.')
    return data


def newer_than(installed):
    """Only compare release versions we understand; never offer a downgrade."""
    import re
    if not isinstance(installed, str) or not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,6}){0,3}', installed):
        return False
    def parts(version):
        numbers = tuple(int(part) for part in version.split('.'))
        return numbers + (0,) * (4 - len(numbers))
    return parts(VERSION) > parts(installed)


if __name__ == '__main__':
    import sys
    try:
        verified_bytes()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
    print('Verified Monet Passwords connector ' + VERSION)
