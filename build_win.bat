@echo off
rem Optional native Windows build (run from this folder).
py -3 -m pip install --upgrade pyinstaller PyQt5==5.15.11
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name ETC-NetGuard ^
  --icon assets\app.ico ^
  --version-file assets\version_info.txt ^
  --add-data "assets;assets" ^
  --add-binary "assets\native\etc_guard.dll;assets\native" ^
  --hidden-import PyQt5.QtSvg ^
  run.py
