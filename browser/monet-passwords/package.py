#!/usr/bin/env python3
"""Verify the bundled signed connector, its source receipt and an optional rebuild."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ('build.py', 'automatic-submit.js', 'LICENSE.upstream')


def verify(root=ROOT, candidate=None):
    folder = root / 'browser/monet-passwords'
    bundled = root / 'linux/share/monet/passwords'
    spec = importlib.util.spec_from_file_location('monet_connector_release', bundled / 'connector.py')
    connector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(connector)
    data = connector.verified_bytes(bundled / 'connector.xpi')
    receipt = json.loads((folder / 'release.json').read_text())
    if (receipt['version'] != connector.VERSION or receipt['sha256'] != connector.SHA256
            or set(receipt['sources']) != set(INPUTS)):
        raise ValueError('Connector release receipt does not match the bundle')
    for name in INPUTS:
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != receipt['sources'][name]:
            raise ValueError('Connector source changed; rebuild and sign before packaging: ' + name)
    with zipfile.ZipFile(bundled / 'connector.xpi') as signed:
        manifest = json.loads(signed.read('manifest.json'))
        if (manifest['version'] != connector.VERSION
                or manifest['browser_specific_settings']['gecko']['id'] != receipt['extension_id']
                or not {'META-INF/mozilla.rsa', 'META-INF/cose.sig'}.issubset(signed.namelist())):
            raise ValueError('Unexpected signed connector identity')
        if candidate is not None:
            with zipfile.ZipFile(candidate) as rebuilt:
                def payload(archive):
                    return {name: archive.read(name) for name in archive.namelist()
                            if not name.endswith('/') and not name.startswith('META-INF/')}
                actual, expected = payload(signed), payload(rebuilt)
                # Mozilla reformats the manifest when signing. Everything else
                # must be identical to the independently rebuilt unsigned input.
                actual['manifest.json'] = json.loads(actual['manifest.json'])
                expected['manifest.json'] = json.loads(expected['manifest.json'])
                if actual != expected:
                    raise ValueError('Signed connector does not match the rebuilt source')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    verify(candidate=args.candidate)
    print('Verified signed connector and source receipt')
