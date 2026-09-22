@echo off
setlocal enabledelayedexpansion

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

python -c "import cryptography,argon2,PySide6,PIL,yaml" 2>NUL

if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install --upgrade pip
    python -m pip install cryptography argon2-cffi PySide6 pillow PyYAML
)

echo Launching PassCore...
python enc.py

pause