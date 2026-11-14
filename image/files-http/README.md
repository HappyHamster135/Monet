# Interrupted HTTP copies

The KDE KIO HTTP worker can receive a success status before the server closes
the connection partway through the body. Propagate the network failure and
leave the destination under KIO's partial filename. The original status
handling still applies to redirects and HTTP errors.

Monet builds the worker from the Fedora source RPM for the installed KIO
package. The image includes that source RPM and the build scripts in
`source.tar.xz`. Run `sh build.sh /out` against the matching base image.
