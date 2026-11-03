"""Read only a user-selected browser export. Never log fields or write plaintext."""
import csv
import io
import os
import stat
from urllib.parse import urlsplit

from vault import VaultError, readable

MAX_FILE = 4 * 1024 * 1024
MAX_LOGINS = 2000


def read_csv(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise VaultError('Choose a regular CSV file exported by your browser.')
            raw = source.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            raise VaultError('This export is too large. Import up to 2,000 logins at a time, in a file smaller than 4 MB.')
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not {'url', 'username', 'password'} <= set(headers):
            raise VaultError('Choose a browser CSV export with url, username and password columns. Zen, Firefox and Chromium exports are supported.')
        records, skipped, seen = [], 0, set()
        for number, row in enumerate(reader):
            if number >= MAX_LOGINS:
                raise VaultError('This export is too large. Import up to 2,000 logins at a time, in a file smaller than 4 MB.')
            values = [row.get(key) or '' for key in ('username', 'password', 'url', 'note')]
            if None in row or any(row.get(key) is None for key in ('url', 'username', 'password')) or any(not readable(value) for value in values):
                raise VaultError('This export contains an unsupported or incomplete row. Nothing has been imported.')
            username, password, website, notes = values
            if not password or tuple(values) in seen:
                skipped += 1
                continue
            title = row.get('name') or urlsplit(website).hostname or website or username or 'Login'
            title = ' '.join(title.split())[:150]
            if username:
                title += ' — ' + ' '.join(username.split())[:45]
            if not readable(title):
                raise VaultError('This export contains an unsupported or incomplete row. Nothing has been imported.')
            seen.add(tuple(values))
            records.append(dict(title=title, username=username, password=password, website=website, notes=notes))
        return records, skipped
    except (OSError, UnicodeError, csv.Error, ValueError):
        raise VaultError('The export could not be read. Choose a valid UTF-8 browser CSV file.') from None
