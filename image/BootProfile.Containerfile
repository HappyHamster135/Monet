# Non-published A/B preview: hold the released kernel/native runtime constant
# while applying this commit's Linux payload and image-finish boot changes.
ARG BASE
FROM ${BASE} AS compiler
RUN version=$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}' qt6-qtdeclarative) \
 && dnf5 -y install --setopt=install_weak_deps=False "qt6-qtdeclarative-devel-$version" \
 && test -x /usr/lib64/qt6/libexec/qmlcachegen

FROM ${BASE}
ARG VERSION
ARG REVISION
COPY target/boot-profile/package/ /tmp/monet/
COPY linux/ /tmp/monet/
COPY image/boot /tmp/monet-boot-build
COPY image/finish-image.sh /tmp/monet-finish-image
COPY image/precompile-qml.py /tmp/monet-precompile-qml.py
RUN --mount=type=bind,from=compiler,source=/usr/lib64/qt6/libexec/qmlcachegen,target=/tmp/monet-qmlcachegen,ro \
    /tmp/monet/install.sh --image \
 && rm -rf /tmp/monet \
 && python3 /tmp/monet-boot-build/prepare.py / \
 && bash /tmp/monet-finish-image \
 && python3 /tmp/monet-precompile-qml.py --compiler /tmp/monet-qmlcachegen \
 && rm -rf /tmp/monet-boot-build /tmp/monet-finish-image /tmp/monet-precompile-qml.py \
 && bootc container lint
LABEL org.opencontainers.image.version="${VERSION}" version="${VERSION}" org.opencontainers.image.revision="${REVISION}"
LABEL org.opencontainers.image.title="Monet development boot benchmark (not a release)"
