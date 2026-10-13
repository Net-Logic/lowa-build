#!/usr/bin/env bash
# Build Qt 5.15.2 for WebAssembly (allotropia's 5.15.2+wasm, pinned commits) into /work/qt5/install.
# Runs in the build container. Skipped when the install matches the pinned commits.
set -euo pipefail
. /home/builder/emsdk/emsdk_env.sh >/dev/null 2>&1
STAMP=/work/qt5/install/.lowa-qt
WANT="$QT5_COMMIT $QTBASE_COMMIT"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$WANT" ]; then
	echo "Qt already built for $WANT"
	exit 0
fi
cd /work
if [ ! -d qt5-src/.git ]; then
	git clone "$QT5_REPO" qt5-src
fi
cd qt5-src
git checkout -q "$QT5_COMMIT"
[ -d qtbase/.git ] || ./init-repository -f --module-subset=qtbase
git -C qtbase fetch -q "$QTBASE_REPO" "$QTBASE_COMMIT"
git -C qtbase checkout -q "$QTBASE_COMMIT"
./configure -opensource -confirm-license -xplatform wasm-emscripten -feature-thread \
	-nomake tests -nomake examples -prefix /work/qt5/install \
	QMAKE_CFLAGS+=-sSUPPORT_LONGJMP=wasm QMAKE_CXXFLAGS+=-sSUPPORT_LONGJMP=wasm
make -j"$JOBS" module-qtbase
make -j"$JOBS" install
echo "$WANT" > "$STAMP"
