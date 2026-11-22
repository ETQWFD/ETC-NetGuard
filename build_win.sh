#!/usr/bin/env bash
# Build the 64-bit Windows single-file EXE on this Linux host through Wine.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export WINEPREFIX=/home/user/wine64
export WINEARCH=win64
export WINEDEBUG=-all
export HOME=/home/user/wine64/drive_c/users/user
export USERPROFILE='C:\users\user'
export PYTHONUSERBASE='C:\Python38'
export PYTHONNOUSERSITE=1
WINE=/home/user/wine9/bin/wine64
PY='C:\Python38\python.exe'

rm -rf dist build/ETC-NetGuard build/ETC-NetGuard.spec
mkdir -p dist build

# Wine's Python needs real Windows stdout handles; cmd file redirection supplies them.
cat > build/run_pyinstaller.bat <<'BAT'
@echo off
cd /d Z:\home\user\Doubao\chats\38455717127764738\etc-netguard
C:\Python38\python.exe -m PyInstaller ^
  --noconfirm --clean --onefile --windowed --uac-admin ^
  --name ETC-NetGuard ^
  --icon assets\app.ico ^
  --version-file assets\version_info.txt ^
  --add-data "assets;assets" ^
  --add-binary "assets\native\etc_guard.dll;assets\native" ^
  --hidden-import PyQt5.QtSvg ^
  --distpath dist --workpath build ^
  run.py > build\win_build.log 2>&1
echo PYINSTALLER_RC=%ERRORLEVEL% >> build\win_build.log
BAT

xvfb-run -a "$WINE" cmd /c build\\run_pyinstaller.bat || true
tail -n 80 build/win_build.log
test -f dist/ETC-NetGuard.exe
ls -lh dist/ETC-NetGuard.exe
