@echo off
setlocal
cd /d "%~dp0frontend"

if not exist "node_modules\" (
  echo Frontend dependencies are missing. Run npm.cmd install in the frontend directory first.
  exit /b 1
)

npm.cmd run dev -- --host 127.0.0.1
