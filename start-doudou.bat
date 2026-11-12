@echo off
cd /d "%~dp0"
if not exist services\api\.venv\Scripts\python.exe python -m venv services\api\.venv
services\api\.venv\Scripts\python.exe -m pip install -r services\api\requirements.txt
if errorlevel 1 exit /b 1
if not exist node_modules\electron\path.txt call npm ci --no-audit --no-fund
if errorlevel 1 exit /b 1
if not exist .env copy .env.example .env
call npm run build
if errorlevel 1 exit /b 1
services\api\.venv\Scripts\python.exe scripts\run_desktop.py
