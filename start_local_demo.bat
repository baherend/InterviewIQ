@echo off
setlocal
start "InterviewIQ Backend" cmd /k call "%~dp0start_backend.bat"
start "InterviewIQ Frontend" cmd /k call "%~dp0start_frontend.bat"
