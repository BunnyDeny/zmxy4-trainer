"""
cheats/engine.py - 游戏作弊引擎
==================================
造梦西游4 专属的作弊逻辑实现（Adobe AIR 微端）。
"""

import logging
from typing import Optional

from core import ProcessManager, MemoryScanner, MemoryFreezer
from core.memory import ProcessNotFoundError, ProcessAccessError

logger = logging.getLogger("zmxy4.cheats")


class CheatEngine:

    def __init__(self):
        self.pm = ProcessManager()
        self.scanner = MemoryScanner(self.pm)
        self.freezer = MemoryFreezer(self.scanner)

        # 扫描结果（按类型分组）
        self.hp_results: dict[str, list[int]] = {}
        self.mp_results: dict[str, list[int]] = {}
        self.atk_results: dict[str, list[int]] = {}

        self._attached = False

    # ── 进程管理 ──

    def attach(self) -> tuple[bool, str]:
        try:
            self.pm.find_process()
            self._attached = True
            return True, "连接成功！"
        except ProcessNotFoundError as e:
            self._attached = False
            return False, str(e)
        except ProcessAccessError as e:
            self._attached = False
            return False, str(e)
        except Exception as e:
            self._attached = False
            return False, f"未知错误: {e}"

    def detach(self):
        self.disable_all()
        self.pm.close()
        self._attached = False

    @property
    def is_attached(self) -> bool:
        return self._attached

    # ── 全类型扫描 ──

    def scan_hp(self, value: float, first_scan: bool) -> dict[str, int]:
        """扫描血量（全类型），返回 {类型: 地址数}"""
        results = self.scanner.scan_all_types(value, first_scan)
        self.hp_results = results
        return {k: len(v) for k, v in results.items()}

    def scan_mp(self, value: float, first_scan: bool) -> dict[str, int]:
        """扫描法力（全类型）"""
        results = self.scanner.scan_all_types(value, first_scan)
        self.mp_results = results
        return {k: len(v) for k, v in results.items()}

    def scan_attack(self, value: int, first_scan: bool) -> dict[str, int]:
        """扫描攻击力（全类型）"""
        results = self.scanner.scan_all_types(float(value), first_scan)
        self.atk_results = results
        return {k: len(v) for k, v in results.items()}

    def _best_type(self, results: dict[str, list[int]]) -> Optional[str]:
        """从扫描结果中选最好的类型（地址少且不为0）"""
        candidates = [(t, len(a)) for t, a in results.items() if a]
        if not candidates:
            return None
        # 优先选地址数最少的（越精确越好），但必须 > 0
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    # ── 作弊功能 ──

    def _freeze_results(self, results: dict, typ: str, value: object):
        """冻结一组地址"""
        if not results or typ not in results:
            raise ValueError("请先扫描数值，或结果为空")
        addrs = results[typ]
        for addr in addrs:
            self.freezer.freeze(addr, typ, value)
        self.freezer.start()
        logger.info(f"已锁定 {len(addrs)} 个地址 (类型={typ})")

    def enable_infinite_hp(self):
        if not self.hp_results:
            raise ValueError("请先扫描血量地址")
        typ = self._best_type(self.hp_results)
        if not typ:
            raise ValueError("扫描结果为空")
        self._freeze_results(self.hp_results, typ, 999999.0)

    def disable_infinite_hp(self):
        self.freezer.unfreeze_all()

    def enable_infinite_mp(self):
        if not self.mp_results:
            raise ValueError("请先扫描法力地址")
        typ = self._best_type(self.mp_results)
        if not typ:
            raise ValueError("扫描结果为空")
        self._freeze_results(self.mp_results, typ, 99999.0)

    def disable_infinite_mp(self):
        self.freezer.unfreeze_all()

    def enable_god_mode(self):
        if not self.hp_results:
            raise ValueError("请先扫描血量地址")
        typ = self._best_type(self.hp_results)
        if not typ:
            raise ValueError("扫描结果为空")
        self._freeze_results(self.hp_results, typ, 9999999.0)

    def disable_god_mode(self):
        self.freezer.unfreeze_all()

    def enable_one_hit_kill(self):
        if not self.atk_results:
            raise ValueError("请先扫描攻击力地址")
        typ = self._best_type(self.atk_results)
        if not typ:
            raise ValueError("扫描结果为空")
        self._freeze_results(self.atk_results, typ, 99999999)

    def disable_one_hit_kill(self):
        self.freezer.unfreeze_all()

    def enable_monster_suicide(self):
        raise NotImplementedError("怪物自杀暂未实现")

    def disable_monster_suicide(self):
        self.freezer.unfreeze_all()

    def disable_all(self):
        self.freezer.unfreeze_all()
        self.freezer.stop()

    def get_status(self) -> dict:
        return {
            "attached": self._attached,
            "god_mode": bool(self.hp_results and self.freezer._frozen),
            "infinite_hp": bool(self.hp_results and self.freezer._frozen),
            "infinite_mp": bool(self.mp_results and self.freezer._frozen),
            "one_hit_kill": bool(self.atk_results and self.freezer._frozen),
            "hp_addresses": sum(len(v) for v in self.hp_results.values()),
            "mp_addresses": sum(len(v) for v in self.mp_results.values()),
            "attack_addresses": sum(len(v) for v in self.atk_results.values()),
        }
