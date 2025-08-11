@echo off
setlocal
title BETA BLOCKZ (Flask)
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install Python 3.10+ from python.org and try again.
  pause
  exit /b 1
)
echo Creating virtual environment...
python -m venv .venv
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
) else (
  echo Failed to create venv. Exiting.
  pause
  exit /b 1
)
python -m pip install --upgrade pip
pip install -r requirements.txt
set FLASK_ENV=development
set ADMIN_EMAIL=admin@betablockz.local
set ADMIN_PASSWORD=admin123
set SECRET_KEY=change-this-secret-key
echo.
echo Launching BETA BLOCKZ on http://localhost:5000
python app.py
pause
