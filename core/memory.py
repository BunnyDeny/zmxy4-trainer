"""
core/memory.py - 内存读写核心模块
====================================
封装 pymem 提供进程内存的读写、扫描和锁定功能。
所有游戏数据修改最终都经过这里。
"""

import struct
import time
import logging
from typing import Optional

import pymem
import pymem.exception
import pymem.process

logger = logging.getLogger("zmxy4.memory")


class MemoryError(Exception):
    """内存操作相关错误的基类"""


class ProcessNotFoundError(MemoryError):
    """找不到目标游戏进程"""


class ProcessAccessError(MemoryError):
    """无法访问目标进程（权限不足或被保护）"""


class ProcessManager:
    """游戏进程管理 —— 查找和附加到造梦西游4微端进程"""

    # 造梦西游4微端进程名
    TARGET_PROCESSES = [
        "zmxy_online*",        # 微端进程（显示为 zmxy_online(32位)）
    ]

    def __init__(self, process_name: Optional[str] = None):
        self.process_name = process_name
        self.pm: Optional[pymem.Pymem] = None
        self.process_id: Optional[int] = None

    def find_process(self) -> bool:
        """
        扫描进程列表，查找造梦微端。
        使用 contains 匹配（zmxy_online 匹配 zmxy_online(32位)）。
        返回 True=找到，False=没找到。
        """
        import psutil

        names_to_try = (
            [self.process_name] if self.process_name
            else self.TARGET_PROCESSES
        )

        for name in names_to_try:
            pattern = name.replace("*", "").lower()
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    if pattern in pname:
                        pid = proc.info["pid"]
                        logger.info(f"找到微端进程: {pname} (PID={pid})")
                        self._attach(pid)
                        self.process_name = pname
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return False

    def _attach(self, pid: int):
        """通过 PID 打开进程句柄"""
        import ctypes
        from ctypes import wintypes

        # 获取进程完整路径，用于日志
        try:
            import psutil
            proc = psutil.Process(pid)
            exe_path = proc.exe()
            is_32bit = not (proc.exe().lower().endswith("64.exe"))
            logger.debug(f"进程信息: {exe_path}, 32位={is_32bit}")
        except Exception:
            pass

        # 先尝试完全访问权限
        access_flags = [
            ("完全访问", 0x1F0FFF),                    # PROCESS_ALL_ACCESS
            ("查询+读写", 0x0010 | 0x0020 | 0x0008),   # QUERY | VM_READ | VM_WRITE
            ("最小权限", 0x0010 | 0x0020),              # QUERY | VM_READ
        ]

        last_error = ""
        for access_name, access_flag in access_flags:
            try:
                handle = ctypes.windll.kernel32.OpenProcess(
                    access_flag, False, pid
                )
                if handle:
                    self.pm = pymem.Pymem()
                    self.pm.process_handle = handle
                    self.pm.process_id = pid
                    logger.info(f"进程句柄已打开 ({access_name})")
                    return
                else:
                    err = ctypes.windll.kernel32.GetLastError()
                    last_error = f"{access_name}失败: Windows错误码 {err}"
                    logger.debug(last_error)
            except Exception as e:
                last_error = f"{access_name}异常: {e}"
                logger.debug(last_error)
                continue

        raise ProcessAccessError(
            f"无法打开进程 (PID={pid})。\n"
            f"最后错误: {last_error}\n\n"
            "可能的原因:\n"
            "  1. 请以管理员身份运行本辅助器\n"
            "     (右键 → 以管理员身份运行)\n"
            "  2. 杀毒软件拦截了内存访问\n"
            "  3. 微端有反调试保护"
        )

    def ensure_attached(self) -> None:
        """确保已附加到进程，否则抛出异常"""
        if not self.pm or not self.pm.process_handle:
            if not self.find_process():
                raise ProcessNotFoundError(
                    f"找不到造梦西游4微端进程。请先启动游戏。\n"
                    f"搜索: zmxy_online"
                )

    def close(self):
        """关闭进程句柄"""
        if self.pm and self.pm.process_handle:
            try:
                from ctypes import windll
                windll.kernel32.CloseHandle(self.pm.process_handle)
            except Exception:
                pass
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
        """扫描 4 字节整数"""
        self.pm.ensure_attached()
        addresses = []

        if first_scan:
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
        """扫描 4 字节浮点数"""
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

    def scan_double(self, value: float, first_scan: bool = True) -> list[int]:
        """扫描 8 字节双精度浮点数（Flash 游戏的 Number 类型）"""
        self.pm.ensure_attached()
        if first_scan:
            addresses = []
            for module in self._iter_modules():
                try:
                    module_start = module.lpBaseOfDll
                    module_size = module.SizeOfImage
                    buffer = self.pm.pm.read_bytes(module_start, module_size)
                    self._scan_buffer_double(buffer, module_start, value, addresses)
                except Exception:
                    continue
            self._last_addresses = addresses
        else:
            filtered = []
            for addr in self._last_addresses:
                try:
                    current = self.read_double(addr)
                    if abs(current - value) < 0.001:
                        filtered.append(addr)
                except Exception:
                    continue
            self._last_addresses = filtered
        return list(self._last_addresses)

    def read_int(self, address: int) -> int:
        self.pm.ensure_attached()
        return self.pm.pm.read_int(address)

    def read_float(self, address: int) -> float:
        self.pm.ensure_attached()
        return self.pm.pm.read_float(address)

    def read_double(self, address: int) -> float:
        """读取 8 字节双精度浮点数"""
        self.pm.ensure_attached()
        return self.pm.pm.read_double(address)

    def write_int(self, address: int, value: int):
        self.pm.ensure_attached()
        self.pm.pm.write_int(address, value)

    def write_float(self, address: int, value: float):
        self.pm.ensure_attached()
        self.pm.pm.write_float(address, value)

    def write_double(self, address: int, value: float):
        """写入 8 字节双精度浮点数"""
        self.pm.ensure_attached()
        self.pm.pm.write_double(address, value)

    def _iter_modules(self):
        """遍历所有可读内存页（使用 VirtualQueryEx 枚举）"""
        import ctypes
        from ctypes import wintypes

        SYSTEM_INFO = ctypes.wintypes.SYSTEM_INFO()
        ctypes.windll.kernel32.GetSystemInfo(ctypes.byref(SYSTEM_INFO))
        page_size = SYSTEM_INFO.dwPageSize

        # 内存状态常量
        MEM_COMMIT = 0x1000
        PAGE_READABLE = 0x02  # PAGE_READONLY
        PAGE_READWRITE = 0x04
        PAGE_EXECUTE_READ = 0x20
        PAGE_EXECUTE_READWRITE = 0x40

        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD),
                ("Type", wintypes.DWORD),
            ]

        mbi = MEMORY_BASIC_INFORMATION()
        addr = 0
        process_handle = self.pm.pm.process_handle

        while True:
            result = ctypes.windll.kernel32.VirtualQueryEx(
                process_handle,
                ctypes.c_void_p(addr),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )
            if not result:
                break

            # 只扫描已提交、可读的内存
            if (mbi.State == MEM_COMMIT
                and mbi.Protect in (PAGE_READABLE, PAGE_READWRITE,
                                    PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE)):
                # yield 一个模拟模块的对象
                class _MemRegion:
                    lpBaseOfDll = mbi.BaseAddress
                    SizeOfImage = mbi.RegionSize

                yield _MemRegion()

            addr = mbi.BaseAddress + mbi.RegionSize
            if addr > 0x7FFFFFFF:  # 32位进程上限
                break

    @staticmethod
    def _scan_buffer_int(buffer: bytes, base: int, value: int, results: list):
        packed = struct.pack("<i", value)
        pos = 0
        while True:
            pos = buffer.find(packed, pos)
            if pos == -1:
                break
            results.append(base + pos)
            pos += 4

    @staticmethod
    def _scan_buffer_float(buffer: bytes, base: int, value: float, results: list):
        packed = struct.pack("<f", value)
        pos = 0
        while True:
            pos = buffer.find(packed, pos)
            if pos == -1:
                break
            results.append(base + pos)
            pos += 4

    @staticmethod
    def _scan_buffer_double(buffer: bytes, base: int, value: float, results: list):
        """在内存块中搜索 8 字节双精度浮点数（Flash Number 类型）"""
        packed = struct.pack("<d", value)
        pos = 0
        while True:
            pos = buffer.find(packed, pos)
            if pos == -1:
                break
            results.append(base + pos)
            pos += 8


class MemoryFreezer:
    """
    内存值冻结器 —— 后台线程不断将指定地址写回目标值。
    """

    def __init__(self, scanner: MemoryScanner):
        self.scanner = scanner
        self._frozen: dict[int, tuple] = {}
        self._running = False
        self._thread = None

    def freeze_int(self, address: int, value: int):
        self._frozen[address] = ("int", value)

    def freeze_float(self, address: int, value: float):
        self._frozen[address] = ("float", value)

    def freeze_double(self, address: int, value: float):
        """锁定一个地址为指定双精度浮点数值"""
        self._frozen[address] = ("double", value)

    def unfreeze(self, address: int):
        self._frozen.pop(address, None)

    def unfreeze_all(self):
        self._frozen.clear()

    def _loop(self):
        import threading
        self._running = True
        while self._running:
            for addr, (typ, value) in list(self._frozen.items()):
                try:
                    if typ == "int":
                        self.scanner.write_int(addr, value)
                    elif typ == "double":
                        self.scanner.write_double(addr, value)
                    else:
                        self.scanner.write_float(addr, value)
                except Exception:
                    continue
            time.sleep(0.05)

    def start(self):
        if self._running:
            return
        self._running = True
        import threading
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
