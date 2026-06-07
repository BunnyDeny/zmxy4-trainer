"""
core/memory.py - 内存读写核心模块
====================================
封装 pymem 提供进程内存的读写、扫描和锁定功能。
所有游戏数据修改最终都经过这里。
"""

import struct
import time
from typing import Optional

import pymem
import pymem.exception
import pymem.process


class MemoryError(Exception):
    """内存操作相关错误的基类"""


class ProcessNotFoundError(MemoryError):
    """找不到目标游戏进程"""


class ProcessManager:
    """游戏进程管理 —— 查找和附加到造梦西游4进程"""

    # 造梦西游4可能的进程名列表（各种平台/版本）
    TARGET_PROCESSES = [
        "ZaoMengXiYou4.exe",
        "zaomengxiyou4.exe",
        "ZMYX4.exe",
        "FlashPlayerPlugin_*.exe",       # Flash 浏览器插件
        "flashplayer_32_sa.exe",          # 独立Flash播放器
        "4399GameBox.exe",                # 4399游戏盒
        "chromium.exe",                   # 某些H5版本
    ]

    def __init__(self, process_name: Optional[str] = None):
        """
        :param process_name: 进程名，为 None 时自动尝试匹配已知进程名
        """
        self.process_name = process_name
        self.pm: Optional[pymem.Pymem] = None
        self.process_id: Optional[int] = None

    def find_process(self) -> bool:
        """
        自动查找造梦西游4进程。
        返回 True 表示找到并成功附加，False 表示没找到。
        """
        names_to_try = (
            [self.process_name] if self.process_name
            else self.TARGET_PROCESSES
        )

        for name in names_to_try:
            if "*" in name:
                # 通配符查找 —— 遍历进程
                import psutil
                for proc in psutil.process_iter(["name", "pid"]):
                    try:
                        pname = proc.info["name"] or ""
                        pattern = name.replace("*", "").lower()
                        if pattern in pname.lower():
                            self._attach(proc.info["pid"])
                            self.process_name = pname
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            else:
                try:
                    self.pm = pymem.Pymem(name)
                    self.process_name = name
                    self.process_id = self.pm.process_id
                    return True
                except pymem.exception.ProcessNotFound:
                    continue
                except pymem.exception.CouldNotOpenProcess:
                    continue
        return False

    def _attach(self, pid: int):
        """通过 PID 附加到进程"""
        self.pm = pymem.Pymem()
        # pymem 不直接支持 PID 附加，用内部方法
        import pymem.process
        self.pm.process_handle = pymem.process.process_from_id(pid)
        self.pm.process_id = pid

    def ensure_attached(self) -> None:
        """确保已附加到进程，否则抛出异常"""
        if not self.pm:
            if not self.find_process():
                raise ProcessNotFoundError(
                    f"找不到造梦西游4进程。请先启动游戏。\n"
                    f"搜索的进程名: {', '.join(self.TARGET_PROCESSES)}"
                )

    def close(self):
        """关闭进程句柄"""
        if self.pm:
            self.pm.close_process()
            self.pm = None
            self.process_id = None


class MemoryScanner:
    """
    内存值扫描器 —— 类似 Cheat Engine 的扫描逻辑。
    首次扫描：找所有等于目标值的地址
    再次扫描：从已有地址中筛选值变化的地址
    """

    def __init__(self, process_manager: ProcessManager):
        self.pm = process_manager
        self._last_addresses: list[int] = []

    def scan_int(self, value: int, first_scan: bool = True) -> list[int]:
        """
        扫描 4 字节整数。
        :param value: 要搜索的值
        :param first_scan: True=全内存扫描, False=在上次结果中筛选
        :returns: 匹配的地址列表
        """
        self.pm.ensure_attached()
        addresses = []

        if first_scan:
            # 全内存扫描
            for module in self._iter_modules():
                try:
                    module_start = module.lpBaseOfDll
                    module_size = module.SizeOfImage
                    buffer = self.pm.pm.read_bytes(module_start, module_size)
                    self._scan_buffer_int(buffer, module_start, value, addresses)
                except Exception:
                    continue
            self._last_addresses = addresses
        else:
            # 在上次结果中筛选
            filtered = []
            for addr in self._last_addresses:
                try:
                    current = self.read_int(addr)
                    if current == value:
                        filtered.append(addr)
                except Exception:
                    continue
            self._last_addresses = filtered

        return list(self._last_addresses)

    def scan_float(self, value: float, first_scan: bool = True) -> list[int]:
        """扫描 4 字节浮点数（常用于血量/蓝量）"""
        self.pm.ensure_attached()
        if first_scan:
            addresses = []
            for module in self._iter_modules():
                try:
                    module_start = module.lpBaseOfDll
                    module_size = module.SizeOfImage
                    buffer = self.pm.pm.read_bytes(module_start, module_size)
                    self._scan_buffer_float(buffer, module_start, value, addresses)
                except Exception:
                    continue
            self._last_addresses = addresses
        else:
            filtered = []
            for addr in self._last_addresses:
                try:
                    current = self.read_float(addr)
                    if abs(current - value) < 0.001:
                        filtered.append(addr)
                except Exception:
                    continue
            self._last_addresses = filtered

        return list(self._last_addresses)

    def read_int(self, address: int) -> int:
        """从指定地址读 4 字节整数"""
        self.pm.ensure_attached()
        return self.pm.pm.read_int(address)

    def read_float(self, address: int) -> float:
        """从指定地址读 4 字节浮点数"""
        self.pm.ensure_attached()
        return self.pm.pm.read_float(address)

    def write_int(self, address: int, value: int):
        """写 4 字节整数到指定地址"""
        self.pm.ensure_attached()
        self.pm.pm.write_int(address, value)

    def write_float(self, address: int, value: float):
        """写 4 字节浮点数到指定地址"""
        self.pm.ensure_attached()
        self.pm.pm.write_float(address, value)

    def _iter_modules(self):
        """遍历进程所有模块"""
        # 用 pymem 的底层 API 枚举模块
        from ctypes import create_string_buffer, sizeof
        from pymem.ressources.structure import MODULEENTRY32

        h_module_snapshot = pymem.process.create_toolhelp32_snapshot(
            0x00000008,  # TH32CS_SNAPMODULE
            self.pm.pm.process_id
        )
        if h_module_snapshot == -1:
            return

        try:
            me = MODULEENTRY32()
            me.dwSize = sizeof(MODULEENTRY32)
            success = pymem.process.module32_first(h_module_snapshot, me)
            while success:
                yield me
                success = pymem.process.module32_next(h_module_snapshot, me)
        finally:
            from pymem.process import kernel32
            kernel32.CloseHandle(h_module_snapshot)

    @staticmethod
    def _scan_buffer_int(buffer: bytes, base: int, value: int, results: list):
        """在内存块中搜索 4 字节整数"""
        packed = struct.pack("<i", value)
        pos = 0
        while True:
            pos = buffer.find(packed, pos)
            if pos == -1:
                break
            results.append(base + pos)
            pos += 4  # 步进 4 字节

    @staticmethod
    def _scan_buffer_float(buffer: bytes, base: int, value: float, results: list):
        """在内存块中搜索 4 字节浮点数"""
        packed = struct.pack("<f", value)
        pos = 0
        while True:
            pos = buffer.find(packed, pos)
            if pos == -1:
                break
            results.append(base + pos)
            pos += 4


class MemoryFreezer:
    """
    内存值冻结器 —— 后台线程不断将指定地址写回目标值。
    实现"无限血量"、"无限蓝量"等效果。
    """

    def __init__(self, scanner: MemoryScanner):
        self.scanner = scanner
        self._frozen: dict[int, tuple] = {}   # addr -> (type, value)
        self._running = False
        self._thread = None

    def freeze_int(self, address: int, value: int):
        """锁定一个地址为指定整数值"""
        self._frozen[address] = ("int", value)

    def freeze_float(self, address: int, value: float):
        """锁定一个地址为指定浮点数值"""
        self._frozen[address] = ("float", value)

    def unfreeze(self, address: int):
        """取消锁定"""
        self._frozen.pop(address, None)

    def unfreeze_all(self):
        """取消所有锁定"""
        self._frozen.clear()

    def _loop(self):
        """冻结循环"""
        import threading
        self._running = True
        while self._running:
            for addr, (typ, value) in list(self._frozen.items()):
                try:
                    if typ == "int":
                        self.scanner.write_int(addr, value)
                    else:
                        self.scanner.write_float(addr, value)
                except Exception:
                    continue
            time.sleep(0.05)  # 每秒写 20 次，确保稳定

    def start(self):
        """启动冻结线程"""
        if self._running:
            return
        self._running = True
        import threading
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止冻结线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
