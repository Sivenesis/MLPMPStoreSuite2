@echo off
title MLP Store Suite II - In-Game Store Memory Patcher
cd /d "%~dp0"
python run.py 8080
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
