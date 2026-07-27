@echo off
setlocal
cd /d "%~dp0backend"

if not exist "%~dp0backend.venv\Scripts\python.exe" (
  echo Backend environment is missing. Create backend.venv and install backend\requirements.txt first.
  exit /b 1
)

call "%~dp0backend.venv\Scripts\activate.bat"
if errorlevel 1 exit /b %errorlevel%

if not exist "%~dp0backend.venv\Scripts\alembic.exe" (
  echo Alembic is not installed in backend.venv. Install backend\requirements.txt first.
  exit /b 1
)

"%~dp0backend.venv\Scripts\alembic.exe" upgrade head
if errorlevel 1 exit /b %errorlevel%

"%~dp0backend.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000
