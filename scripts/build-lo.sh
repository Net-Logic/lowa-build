#!/usr/bin/env bash
# Configure (when the options changed) and build LibreOffice for WebAssembly. Runs in the build container.
set -euo pipefail
. /home/builder/emsdk/emsdk_env.sh >/dev/null 2>&1
cp "$EMSDK/upstream/emscripten/LICENSE" /work/stats/emscripten-LICENSE
cd "/work/src/libreoffice-$LO_VERSION"
export CCACHE_DIR=/work/ccache CCACHE_MAXSIZE=15G
{
	echo "--with-distro=LibreOfficeWASM32"
	echo "--with-wasm-module=$WASM_MODULES"
	echo "--with-lang=$LANGS"
	echo "--with-vendor=Net-Logic"
	echo "--enable-ccache"
	echo "--with-external-tar=/work/tarballs"
	echo "--disable-werror"
	echo "--with-build-platform-configure-options=--disable-werror"
	echo "QT5DIR=/work/qt5/install"
} > autogen.input.new
if [ ! -f config_host.mk ] || ! cmp -s autogen.input.new autogen.input; then
	mv autogen.input.new autogen.input
	./autogen.sh
else
	rm -f autogen.input.new
fi
make PARALLELISM="$JOBS"
ls -l workdir/installation/LibreOffice/emscripten/
