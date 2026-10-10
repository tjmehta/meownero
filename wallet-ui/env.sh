# Source this before configuring or running the native wallet build.
# Toolchain root: open-source Qt 6.12.0 (linux_gcc_64) installed by aqtinstall,
# plus Ubuntu's libxcb-cursor0, which Qt's xcb platform plugin needs.
MEOWNERO_TOOLCHAIN="${MEOWNERO_TOOLCHAIN:-$HOME/.local/share/meownero/toolchain}"
export MEOWNERO_TOOLCHAIN
export QTDIR="$MEOWNERO_TOOLCHAIN/qt/6.12.0/gcc_64"
# GL/EGL headers and link names extracted from Ubuntu -dev packages (no sudo).
export CMAKE_PREFIX_PATH="$QTDIR:$MEOWNERO_TOOLCHAIN/sysroot/usr"
export PATH="$MEOWNERO_TOOLCHAIN/venv/bin:$QTDIR/bin:$PATH"
export LD_LIBRARY_PATH="$MEOWNERO_TOOLCHAIN/sysroot/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
