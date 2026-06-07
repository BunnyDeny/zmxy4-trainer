"""
core/process.py - 游戏进程自动检测
=====================================
自动检测造梦西游4运行在哪个进程中。
支持：360游戏大厅、造梦微端、各种浏览器（含Flash插件）、独立Flash播放器。
"""

import logging
from typing import Optional

logger = logging.getLogger("zmxy4.process")


# 所有已知的游戏进程名（按可能性排序）
GAME_PROCESS_PATTERNS = [
    # 造梦微端 / 独立客户端
    "ZaoMengXiYou4.exe",
    "zaomengxiyou4.exe",
    "ZMYX4.exe",

    # 造梦西游online
    "zaomengxiyouonline.exe",
    "ZaoMengXiYouOL.exe",

    # 360游戏大厅
    "360Game.exe",
    "360game.exe",
    "360游戏大厅.exe",
    "360GameLoader.exe",
    "360gamecenter.exe",

    # 4399游戏盒
    "4399GameBox.exe",
    "4399游戏盒.exe",

    # Flash 独立播放器
    "FlashPlayer.exe",
    "flashplayer_32_sa.exe",
    "flashplayer_32.exe",
    "FlashUtil*_ActiveX.exe",

    # 浏览器 Flash 插件进程
    "FlashPlayerPlugin_*.exe",
    "pepflashplayer*.dll",  # 内嵌在浏览器中

    # Chrome / Chromium
    "chrome.exe",
    "chromium.exe",

    # Edge
    "msedge.exe",

    # Firefox
    "firefox.exe",

    # 360安全浏览器
    "360se.exe",
    "360chrome.exe",
    "360安全浏览器.exe",

    # QQ浏览器
    "QQBrowser.exe",
    "QQ浏览器.exe",

    # 搜狗浏览器
    "SogouExplorer.exe",

    # 猎豹浏览器
    "liebao.exe",
]


class GameProcessFinder:
    """
    游戏进程查找器 —— 扫描系统进程列表，找到造梦西游4的运行进程。
    使用分层策略：先找专门进程，再找通用浏览器。
    """

    def __init__(self):
        self.found_pid: Optional[int] = None
        self.found_name: Optional[str] = None

    def find(self) -> bool:
        """
        扫描所有已知进程模式，找到正在运行的游戏进程。
        返回 True=找到，False=没找到。
        """
        import psutil

        # 策略1：精确匹配（优先匹配专用进程名）
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                for pattern in GAME_PROCESS_PATTERNS:
                    if "*" in pattern:
                        # 通配符匹配
                        base = pattern.replace("*", "").lower()
                        if base in pname:
                            self.found_pid = proc.info["pid"]
                            self.found_name = pname
                            logger.info(f"匹配到进程: {pname} (PID={self.found_pid})")
                            return True
                    else:
                        if pname == pattern.lower():
                            self.found_pid = proc.info["pid"]
                            self.found_name = pname
                            logger.info(f"匹配到进程: {pname} (PID={self.found_pid})")
                            return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 策略2：内存窗口标题匹配
        # 找不到已知进程名时，扫描所有窗口标题
        found = self._scan_by_window_title()
        if found:
            return True

        logger.warning("未找到正在运行的游戏进程")
        return False

    def _scan_by_window_title(self) -> bool:
        """通过窗口标题查找游戏进程"""
        import psutil
        try:
            import win32gui
            import win32process

            def enum_callback(hwnd, results):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                # 匹配窗口标题关键词
                keywords = ["造梦西游4", "造梦西游", "ZaoMengXiYou",
                           "zmyx4", "ZMYX4", "西游4"]
                for kw in keywords:
                    if kw.lower() in title.lower():
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        results.append((hwnd, pid, title))
                        return

            results = []
            win32gui.EnumWindows(enum_callback, results)

            if results:
                hwnd, pid, title = results[0]
                try:
                    proc = psutil.Process(pid)
                    self.found_pid = pid
                    self.found_name = proc.name()
                    logger.info(f"通过窗口标题匹配到进程: {proc.name()} "
                                f"(PID={pid}, 标题='{title}')")
                    return True
                except psutil.NoSuchProcess:
                    pass

        except ImportError:
            logger.debug("win32gui 未安装，跳过窗口标题扫描")
        except Exception as e:
            logger.debug(f"窗口标题扫描异常: {e}")

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


class ProcessMemoryInfo:
    """进程内存布局信息（调试用）"""

    def __init__(self, pid: int):
        self.pid = pid

    def list_modules(self) -> list[dict]:
        """列出进程加载的所有模块"""
        try:
            import pymem
            pm = pymem.Pymem()
            pm.process_id = self.pid
            modules = []
            for m in pm.list_modules():
                modules.append({
                    "name": m.name,
                    "base": hex(m.lpBaseOfDll),
                    "size": m.SizeOfImage,
                })
            pm.close_process()
            return modules
        except Exception as e:
            logger.error(f"列出模块失败: {e}")
            return []

    def find_module(self, name_pattern: str) -> Optional[dict]:
        """按名称查找模块"""
        for m in self.list_modules():
            if name_pattern.lower() in m["name"].lower():
                return m
        return None
