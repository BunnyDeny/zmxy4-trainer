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

    TARGET_PROCESSES = [
        "zmxy_online*",
    ]

    def __init__(self, process_name: Optional[str] = None):
        self.process_name = process_name
        self.pm: Optional[pymem.Pymem] = None
        self.process_id: Optional[int] = None

    def find_process(self) -> bool:
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
        import ctypes
        access_flags = [
            ("完全访问", 0x1F0FFF),
            ("查询+读写", 0x0010 | 0x0020 | 0x0008),
            ("最小权限", 0x0010 | 0x0020),
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
            "  2. 杀毒软件拦截了内存访问"
        )

    def ensure_attached(self) -> None:
        if not self.pm or not self.pm.process_handle:
            if not self.find_process():
                raise ProcessNotFoundError("找不到造梦西游4微端进程。")

    def close(self):
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
    支持 int32 / float / double 三种类型。
    """

    def __init__(self, process_manager: ProcessManager):
        self.pm = process_manager
        self._last_addresses: list[int] = []

    def scan_all_types(self, value: float, first_scan: bool = True) -> dict:
        """
        同时搜索 int32、float、double 三种类型。
        返回 {类型: [地址列表]}
        """
        self.pm.ensure_attached()
        results: dict[str, list[int]] = {
            "int": [],
            "float": [],
            "double": [],
        }

        int_val = int(value)
        float_val = float(value)

        for region in self._iter_memory_regions():
            try:
                buf = self.pm.pm.read_bytes(region.addr, region.size)
            except Exception:
                continue

            results["int"].extend(self._scan_int(buf, region.addr, int_val))
            results["float"].extend(self._scan_float(buf, region.addr, float_val))
            results["double"].extend(self._scan_double(buf, region.addr, float_val))

        # 去重
        for k in results:
            results[k] = sorted(set(results[k]))

        if first_scan:
            self._last_results = results
        else:
            # 在上次结果中筛
            filtered = {}
            for typ, addrs in self._last_results.items():
                new_addrs = []
                for a in addrs:
                    try:
                        if typ == "int":
                            v = self.read_int(a)
                            ok = (v == int_val)
                        elif typ == "float":
                            v = self.read_float(a)
                            ok = (abs(v - float_val) < 0.001)
                        else:
                            v = self.read_double(a)
                            ok = (abs(v - float_val) < 0.001)
                        if ok:
                            new_addrs.append(a)
                    except Exception:
                        continue
                filtered[typ] = new_addrs
            results = filtered
            self._last_results = results

        return results

    def _iter_memory_regions(self):
        """遍历所有可读私有内存页"""
        import ctypes
        from ctypes import wintypes

        MEM_COMMIT = 0x1000

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
        ph = self.pm.pm.process_handle

        while True:
            ok = ctypes.windll.kernel32.VirtualQueryEx(
                ph, ctypes.c_void_p(addr), ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )
            if not ok:
                break
            base = mbi.BaseAddress or 0
            size = mbi.RegionSize or 0
            if (mbi.State == MEM_COMMIT and mbi.Type == 0x20000
                    and size > 0 and size < 0x10000000
                    and mbi.Protect not in (0x01,)
                    and not (mbi.Protect & 0x100)):
                yield type("R", (), {"addr": base, "size": size})()
            addr = base + size
            if addr <= 0 or addr > 0x7FFFFFFF:
                break

    @staticmethod
    def _scan_int(buf: bytes, base: int, val: int) -> list[int]:
        res = []
        packed = struct.pack("<i", val)
        pos = 0
        while True:
            pos = buf.find(packed, pos)
            if pos == -1:
                break
            res.append(base + pos)
            pos += 4
        return res

    @staticmethod
    def _scan_float(buf: bytes, base: int, val: float) -> list[int]:
        res = []
        packed = struct.pack("<f", val)
        pos = 0
        while True:
            pos = buf.find(packed, pos)
            if pos == -1:
                break
            res.append(base + pos)
            pos += 4
        return res

    @staticmethod
    def _scan_double(buf: bytes, base: int, val: float) -> list[int]:
        res = []
        packed = struct.pack("<d", val)
        pos = 0
        while True:
            pos = buf.find(packed, pos)
            if pos == -1:
                break
            res.append(base + pos)
            pos += 8
        return res

    def read_int(self, address: int) -> int:
        self.pm.ensure_attached()
        return self.pm.pm.read_int(address)

    def read_float(self, address: int) -> float:
        self.pm.ensure_attached()
        return self.pm.pm.read_float(address)

    def read_double(self, address: int) -> float:
        self.pm.ensure_attached()
        return self.pm.pm.read_double(address)

    def write_int(self, address: int, value: int):
        self.pm.ensure_attached()
        self.pm.pm.write_int(address, value)

    def write_float(self, address: int, value: float):
        self.pm.ensure_attached()
        self.pm.pm.write_float(address, value)

    def write_double(self, address: int, value: float):
        self.pm.ensure_attached()
        self.pm.pm.write_double(address, value)


class MemoryFreezer:
    """内存值冻结器 —— 后台线程不断将指定地址写回目标值。"""

    def __init__(self, scanner: MemoryScanner):
        self.scanner = scanner
        self._frozen: dict[int, str, object] = {}
        self._running = False
        self._thread = None

    def freeze(self, address: int, typ: str, value: object):
        self._frozen[address] = (typ, value)

    def unfreeze(self, address: int):
        self._frozen.pop(address, None)

    def unfreeze_all(self):
        self._frozen.clear()

    def _loop(self):
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
