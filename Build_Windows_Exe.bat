@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "APP_NAME=OBS_Reaction_Overlay"
set "DIST_DIR=%~dp0dist\%APP_NAME%"

where py >nul 2>nul
if not %errorlevel%==0 (
  echo Python 실행기 py를 찾을 수 없습니다.
  echo Python 3를 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

py -3 -m pip show pyinstaller >nul 2>nul
if not %errorlevel%==0 (
  echo PyInstaller를 설치합니다.
  py -3 -m pip install --upgrade pyinstaller requests
)

py -3 -m pip show requests >nul 2>nul
if not %errorlevel%==0 (
  echo requests를 설치합니다.
  py -3 -m pip install --upgrade requests
)

echo.
echo Windows 실행 파일을 빌드합니다.
echo.

py -3 -m PyInstaller --noconfirm --clean --onedir --name "%APP_NAME%" "server.py"

if exist "%DIST_DIR%\assets" rmdir /s /q "%DIST_DIR%\assets"
if exist "%DIST_DIR%\public" rmdir /s /q "%DIST_DIR%\public"

xcopy /e /i /y "assets" "%DIST_DIR%\assets" >nul
xcopy /e /i /y "public" "%DIST_DIR%\public" >nul
copy /y "config.example.json" "%DIST_DIR%\config.json" >nul
copy /y "README.txt" "%DIST_DIR%\" >nul
copy /y "LICENSE" "%DIST_DIR%\" >nul
copy /y "THIRD_PARTY_LICENSES.txt" "%DIST_DIR%\" >nul
copy /y "Open_Control_Page.bat" "%DIST_DIR%\" >nul

if exist "%DIST_DIR%\credentials.json" del "%DIST_DIR%\credentials.json"
if exist "%DIST_DIR%\chzzk_tokens.json" del "%DIST_DIR%\chzzk_tokens.json"
if exist "%DIST_DIR%\chzzk_auth_state.json" del "%DIST_DIR%\chzzk_auth_state.json"

echo.
echo 빌드 완료:
echo %DIST_DIR%\%APP_NAME%.exe
echo.
pause
