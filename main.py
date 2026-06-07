#!/usr/bin/env python3
"""
造梦西游4 · 天机辅助器
=======================
启动入口。
用法: python main.py
"""

import sys
import os

# 确保项目目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("zmxy4_assistant.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("zmxy4")


def check_dependencies():
    """检查依赖是否安装"""
    missing = []
    try:
        import pymem  # noqa: F401
    except ImportError:
        missing.append("pymem")

    try:
        import psutil  # noqa: F401
    except ImportError:
        missing.append("psutil")

    if missing:
        print("=" * 50)
        print("  缺少依赖库！请先安装：")
        print(f"  pip install {' '.join(missing)}")
        print("=" * 50)
        return False
    return True


def main():
    print("""
    ╔══════════════════════════════════╗
    ║     造梦西游4 · 天机辅助器 v1.0   ║
    ║     ZMXY4 Heaven's Secret        ║
    ╚══════════════════════════════════╝

    > 正在启动...
    > 请确保已经打开造梦西游4微端
    > 进程名: zmxy_online
    """)

    if not check_dependencies():
        input("\n按回车退出...")
        sys.exit(1)

    try:
        from gui import CheatApp
        app = CheatApp()
        logger.info("天机辅助器启动成功")
        app.run()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        print(f"\n! 启动失败: {e}")
        input("\n按回车退出...")


if __name__ == "__main__":
    main()
