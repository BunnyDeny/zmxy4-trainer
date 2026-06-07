"""
core/process.py - 游戏进程自动检测
=====================================
自动检测造梦西游4微端进程。
进程名：zmxy_online (任务管理器显示为 "zmxy_online(32位)")
"""

import logging
from typing import Optional

logger = logging.getLogger("zmxy4.process")


# 造梦西游4微端进程名
GAME_PROCESS_PATTERNS = [
    "zmxy_online",        # 微端进程（实际显示为 zmxy_online(32位)）
]


class GameProcessFinder:
    """
    游戏进程查找器 —— 扫描系统进程列表，找到造梦西游4微端进程。
    """

    def __init__(self):
        self.found_pid: Optional[int] = None
        self.found_name: Optional[str] = None

    def find(self) -> bool:
        """
        扫描进程列表，找到微端进程。
        使用 contains 匹配（zmxy_online 匹配 zmxy_online(32位)）。
        返回 True=找到，False=没找到。
        """
        import psutil

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                for pattern in GAME_PROCESS_PATTERNS:
                    if pattern.lower() in pname:
                        self.found_pid = proc.info["pid"]
                        self.found_name = pname
                        logger.info(f"匹配到微端进程: {pname} (PID={self.found_pid})")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        logger.warning("未找到造梦西游4微端进程，请确认微端已启动")
        return False

    def get_process_info(self) -> dict:
        """获取找到的进程信息"""
        if not self.found_pid:
            return {}
        import psutil
        try:
            proc = psutil.Process(self.found_pid)
            return {
                "pid": self.found_pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "create_time": proc.create_time(),
                "memory_mb": proc.memory_info().rss / 1024 / 1024,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"pid": self.found_pid, "name": self.found_name}
