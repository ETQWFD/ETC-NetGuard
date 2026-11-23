; ETC NetGuard installer - NSIS 3 / Modern UI 2 (Unicode)
Unicode true
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define APP_NAME "ETC NetGuard"
!define APP_VERSION "1.2.0"
!define APP_PUBLISHER "etc"
!define APP_EXE "ETC-NetGuard.exe"
!define APP_REPO "https://github.com/ETQWFD/ETC-NetGuard"
!define APP_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ETCNetGuard"

Name "${APP_NAME} ${APP_VERSION}"
Caption "${APP_NAME} 安装程序"
OutFile "..\dist\ETC-NetGuard-Setup-${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\ETC NetGuard"
InstallDirRegKey HKLM "${APP_KEY}" "InstallLocation"
RequestExecutionLevel admin
BrandingText "${APP_NAME} · by etc"

VIProductVersion "1.2.0.0"
VIAddVersionKey /LANG=2052 "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=2052 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=2052 "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey /LANG=2052 "FileDescription" "${APP_NAME} 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "1.2.0.0"
VIAddVersionKey /LANG=2052 "LegalCopyright" "Copyright (c) 2026 etc"
VIAddVersionKey /LANG=2052 "OriginalFilename" "ETC-NetGuard-Setup-${APP_VERSION}.exe"

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\app.ico"
!define MUI_UNICON "..\assets\app.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "header.bmp"
!define MUI_HEADERIMAGE_RIGHT
!define MUI_WELCOMEFINISHPAGE_BITMAP "welcome.bmp"

!define MUI_WELCOMEPAGE_TITLE "欢迎安装 ${APP_NAME}"
!define MUI_WELCOMEPAGE_TEXT "ETC NetGuard 是一款本地网络与家长控制工具，可按进程限速/断网、让指定网站返回 404，并用密码保护退出与托盘操作。$\r$\n$\r$\n本安装包需要管理员权限，支持 64 位 Windows。$\r$\n$\r$\n点击“下一步”继续。"

!define MUI_LICENSEPAGE_CHECKBOX
!define MUI_LICENSEPAGE_TEXT_TOP "请阅读以下许可协议。安装即表示您确认自己有权管理这台电脑，并已了解软件的安全边界。"
!define MUI_LICENSEPAGE_CHECKBOX_TEXT "我接受本许可协议"

!define MUI_COMPONENTSPAGE_TEXT_TOP "选择要安装的组件与快捷方式。主程序为必需组件。"

!define MUI_DIRECTORYPAGE_TEXT_TOP "选择 ${APP_NAME} 的安装位置。"

!define MUI_FINISHPAGE_TITLE "安装完成"
!define MUI_FINISHPAGE_TEXT "${APP_NAME} 已安装完成。$\r$\n$\r$\n首次启动会显示七步引导；如需密码保护，请在左上角“设置”中启用。$\r$\n$\r$\n提醒：本软件不修改安全模式、不拦截 Ctrl+Alt+Delete，请妥善保管密码与安装包。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "立即运行 ${APP_NAME}"
!define MUI_FINISHPAGE_LINK "打开 GitHub 开源仓库"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_REPO}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "本软件需要 64 位 Windows，当前系统不受支持。"
    Abort
  ${EndIf}
  ; Close a running copy so files can be replaced. Configuration is saved live.
  nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'
  Pop $0
  Sleep 300
FunctionEnd

Section "ETC NetGuard 主程序（必需）" SEC_MAIN
  SectionIn RO
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  SetOverwrite on
  File "..\dist\${APP_EXE}"
  File "LICENSE.txt"
  File "..\README.md"
  WriteUninstaller "$INSTDIR\uninstall.exe"

  WriteRegStr HKLM "${APP_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${APP_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${APP_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${APP_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE},0"
  WriteRegStr HKLM "${APP_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${APP_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "${APP_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegStr HKLM "${APP_KEY}" "URLInfoAbout" "${APP_REPO}"
  WriteRegDWORD HKLM "${APP_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${APP_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${APP_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "桌面快捷方式" SEC_DESKTOP
  SetShellVarContext all
  CreateShortCut "$DESKTOP\ETC NetGuard.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

Section "开始菜单快捷方式" SEC_START
  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\ETC NetGuard"
  CreateShortCut "$SMPROGRAMS\ETC NetGuard\ETC NetGuard.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortCut "$SMPROGRAMS\ETC NetGuard\卸载 ETC NetGuard.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'
  Pop $0
  Sleep 250

  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$DESKTOP\ETC NetGuard.lnk"
  Delete "$SMPROGRAMS\ETC NetGuard\ETC NetGuard.lnk"
  Delete "$SMPROGRAMS\ETC NetGuard\卸载 ETC NetGuard.lnk"
  RMDir "$SMPROGRAMS\ETC NetGuard"

  DeleteRegKey HKLM "${APP_KEY}"

  MessageBox MB_YESNO|MB_ICONQUESTION "是否同时删除本机配置（密码、限速规则、黑名单与引导记录）？$\r$\n$\r$\n选择“否”将保留配置，便于以后重新安装。" IDNO keep_config
  Delete "$APPDATA\ETCNetGuard\config.json"
  RMDir "$APPDATA\ETCNetGuard"
  keep_config:
SectionEnd
