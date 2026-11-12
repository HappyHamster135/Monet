# Native Archives results and RPM browsing

Ark's batch application normally connects KJob completion to quit without
propagating the job error to its exit status. Monet's extraction helpers need a
reliable terminal result; a full disk must not be announced as Completed.

Build the installed distribution source RPM, retaining its patches, and change
the batch exit result and missing-input error. Password/error dialogs and
extraction keep their native paths.
Read the result before KJob deletes itself; queue only its integer exit code:
zero for completion, 130 for native cancellation, one for an extraction error.

ZIP extraction reads through the end of each entry so libzip can finish
checking its checksum. A wrong ZipCrypto password can pass the initial
password check and still produce the advertised number of bytes. Ark now
reports a read error when libzip detects that mismatch.

RPM browsing reads the existing package-header file index with a single
read-only `rpm -qp` query. It avoids decompressing a potentially huge sequential
cpio payload merely to display its names. Strings use JSON escaping; paths,
sizes, permissions, dates, owners, groups and symlink targets are kept. Ghost
entries are omitted. This is contents inspection, not installation or payload
integrity verification: no scriptlets run, and extraction still reads the actual
payload through libarchive. Unsupported/malformed indexes fall back to the
native reader. Output, entry count and query time are bounded, and interruption
is checked during the query and parsing.

The image replaces `/usr/bin/ark`, the read-only libarchive plugin and the ZIP
plugin. The bundle checks original binary hashes, linked runtime package
identities, required libraries, missing dependencies and build paths before
installation. It preserves the source RPM, prepared sources, patch, build
inputs and runtime manifest in `source.tar.xz`. Existing schema 1 and 2
previews remain readable. Account previews expose the replacement plugins
only to a validated Archives launch, with system fallback after a runtime change.

For the reported 621,826,837-byte ChatGPT RPM, the native sequential listing
reads 4,185 entries in 14.6 seconds; the header path takes 67 ms. Actual Archives
contents become usable in 17.9 seconds before and 219 ms after in paired private
X11 sessions on a warm local filesystem. These are measured fixture results,
not a general guarantee for cold or disconnected drives.

`tests/native/rpm-list` loads the actual original/candidate plugin and can
exercise selected extraction. `tests/fixtures/rpm-list-native.py` covers a tiny
generated RPM with quotes, Unicode, shell metacharacters, symlinks, hard links,
directories and ghost entries, plus ZIP/error fallback. The fixture package is
never installed. `tests/fixtures/rpm-open-native.py` measures the actual GUI,
waiting for contents and an enabled Extract action; it never extracts the input.

`tests.test_archive_failures` drives native error/password dialogs on a private
X server, including a fixture that fails its checksum after the password check.
Run the full-disk case only in the disposable desktop test container;
its small private `/dev/shm` is intentionally filled and then cleared for retry.
