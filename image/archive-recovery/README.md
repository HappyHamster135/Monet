# Native Archives results and RPM browsing

Ark's batch application normally connects KJob completion to quit without
propagating the job error to its exit status. Monet's extraction helpers need a
reliable terminal result; a full disk must not be announced as Completed.

Build the installed distribution source RPM, retaining its patches, and change
the batch exit result and missing-input error. Password/error dialogs and
extraction keep their native paths.
Read the result before KJob deletes itself; queue only its integer exit code:
zero for completion, 130 for native cancellation, one for an extraction error.

RPM browsing reads the existing package-header file index with a single
read-only `rpm -qp` query. It avoids decompressing a potentially huge sequential
cpio payload merely to display its names. Strings use JSON escaping; paths,
sizes, permissions, dates, owners, groups and symlink targets are kept. Ghost
entries are omitted. This is contents inspection, not installation or payload
integrity verification: no scriptlets run, and extraction still reads the actual
payload through libarchive. Unsupported/malformed indexes fall back to the
native reader. Output, entry count and query time are bounded, and interruption
is checked during the query and parsing.

The image replaces `/usr/bin/ark` and its read-only libarchive plugin. Other
installed libraries/plugins stay in place. The bundle checks original executable/plugin hashes,
all linked runtime package identities, needed libraries, missing dependencies and
absence of build paths before installation. Source RPM, prepared sources, exact
patch/build inputs and the runtime manifest are preserved in `source.tar.xz`.
Schema 2 also guards the RPM query executable and plugin; schema 1 previews
remain readable. Account previews expose the replacement plugin only to a
validated Archives launch, with normal system fallback after a runtime change.

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
X server. Run the full-disk case only in the disposable desktop test container;
its small private `/dev/shm` is intentionally filled and then cleared for retry.
