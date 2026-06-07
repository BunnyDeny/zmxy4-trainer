@echo off
chcp 65001 >nul
title 造梦西游4 · 天机辅助器

cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    PowerShell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python
    pause
    exit /b 1
)

python -c "import pymem, psutil" >nul 2>&1
if %errorlevel% neq 0 (
    pip install -r requirements.txt
)

python cli.py
pause
