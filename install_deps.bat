cd /d "%~dp0"
powershell -Command "python -m pip install numpy pillow sympy matplotlib"
powershell -Command "python -m pip install PySide6"
pause