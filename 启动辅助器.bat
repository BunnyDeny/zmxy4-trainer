@echo off
chcp 65001 >nul
title 造梦西游4 · 天机辅助器

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
echo [检查] 验证依赖库...
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
echo [提示] 请确保造梦西游4已经运行
echo.
start python main.py

echo 辅助器已启动，如果界面未出现请手动运行:
echo   python main.py
echo.
pause
