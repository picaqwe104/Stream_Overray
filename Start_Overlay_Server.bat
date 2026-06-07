@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title OBS Reaction Overlay Server

set "PYTHON_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
  goto run
)

where python >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=python"
  goto run
)

where python3 >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=python3"
  goto run
)

echo.
echo Python을 찾을 수 없습니다.
echo.
echo 이 프로그램을 실행하려면 Python 3가 필요합니다.
echo Python 설치 후 이 파일을 다시 더블클릭하세요.
echo.
echo Python 다운로드:
echo https://www.python.org/downloads/
echo.
pause
exit /b 1

:run
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:39291/control'"
%PYTHON_CMD% "%~dp0server.py"

:done
echo.
echo 서버가 종료되었습니다.
pause
