@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [错误] 没找到可用的 Python，请安装 3.10+ 并勾选 "Add python.exe to PATH"。
    pause
    exit /b 1
)

%PY% tools\check_deps.py
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
