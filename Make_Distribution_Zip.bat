@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PACKAGE_NAME=OBS_Reaction_Overlay_Package"
set "APP_DIR=%~dp0dist\OBS_Reaction_Overlay"
set "STAGE=%TEMP%\%PACKAGE_NAME%"
set "ZIP_PATH=%~dp0%PACKAGE_NAME%.zip"

if not exist "%APP_DIR%\OBS_Reaction_Overlay.exe" (
  echo.
  echo dist\OBS_Reaction_Overlay\OBS_Reaction_Overlay.exe 파일이 없습니다.
  echo 먼저 Build_Windows_Exe.bat을 실행해 주세요.
  echo.
  pause
  exit /b 1
)

if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%"

xcopy /e /i /y "%APP_DIR%" "%STAGE%" >nul

if exist "%ZIP_PATH%" del "%ZIP_PATH%"
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%ZIP_PATH%' -Force"

echo.
echo 공유용 ZIP 파일을 만들었습니다.
echo.
echo %ZIP_PATH%
echo.
echo 이 ZIP에는 credentials.json, chzzk_tokens.json, chzzk_auth_state.json이 포함되지 않습니다.
echo.
pause
