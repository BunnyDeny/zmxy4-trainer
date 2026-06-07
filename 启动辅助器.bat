@echo off
chcp 65001 >nul
title 造梦西游4 · 天机辅助器

:: 检查是否已经是管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在请求管理员权限（点击"是"继续）...
    :: 用 PowerShell 重新以管理员身份运行自己
    PowerShell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo =====================================
echo   造梦西游4 · 天机辅助器 v1.0
echo =====================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查依赖
python -c "import pymem, psutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在安装依赖库...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

:: 启动
echo [启动] 正在启动辅助器...
echo.
python main.py

pause
