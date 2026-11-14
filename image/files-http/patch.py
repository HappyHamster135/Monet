"""Preserve KIO's error and partial-file handling when a response ends early."""

from pathlib import Path
import sys


def patch(path):
    original = path.read_text()
    anchor = '    if (reply->error() == QNetworkReply::AuthenticationRequiredError) {'
    if original.count(anchor) != 1 or 'auto emitDataOnce = qScopeGuard' not in original:
        raise ValueError('The KIO HTTP response code changed. Check the Files HTTP patch.')
    check = '''    // HTTP may have sent a successful status before the connection failed.
    if (reply->error() != QNetworkReply::NoError && statusCode >= 200 && statusCode < 300) {
        emitDataOnce.dismiss();
        return {statusCode, QByteArray(), KIO::ERR_CONNECTION_BROKEN};
    }
'''
    path.write_text(original.replace(anchor, check + anchor))


if __name__ == '__main__':
    patch(Path(sys.argv[1]))
