# Toolchain for the LibreOffice WebAssembly build: LibreOffice build dependencies and emsdk.
# Qt and LibreOffice are built by build.sh steps in memory-capped containers, not here.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG UID=1000
ARG GID=1000
ARG EMSDK_VERSION
ARG EMSDK_COMMIT
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources \
	&& apt-get update \
	&& apt-get build-dep -y libreoffice \
	&& apt-get install -y --no-install-recommends git ca-certificates curl xz-utils python3 ccache \
		meson ninja-build nasm gperf bison flex autoconf automake libtool pkg-config zip unzip \
		xsltproc libxml2-utils gettext locales \
	&& rm -rf /var/lib/apt/lists/*
# ubuntu:24.04 ships a user "ubuntu" with uid 1000: replace it by "builder" with the host user's ids
RUN userdel -r ubuntu 2>/dev/null || true; \
	groupadd -g "${GID}" builder && useradd -m -u "${UID}" -g "${GID}" -s /bin/bash builder
USER builder
WORKDIR /home/builder
RUN git clone https://github.com/emscripten-core/emsdk.git \
	&& cd emsdk && git checkout -q "${EMSDK_COMMIT}" \
	&& ./emsdk install "${EMSDK_VERSION}" && ./emsdk activate "${EMSDK_VERSION}" \
	&& . ./emsdk_env.sh \
	&& printf 'int main(void){return 0;}\n' > /tmp/t.c && emcc /tmp/t.c -o /tmp/t.js && rm -f /tmp/t.*
RUN echo '. /home/builder/emsdk/emsdk_env.sh >/dev/null 2>&1' >> /home/builder/.bashrc
