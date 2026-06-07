"""
cheats/engine.py - 游戏作弊引擎
==================================
造梦西游4 专属的作弊逻辑实现。
负责扫描游戏内存定位关键数值（HP、MP、攻击力等），
并提供开启/关闭各类作弊功能的方法。
"""

import logging
import time
from typing import Optional

from core import ProcessManager, MemoryScanner, MemoryFreezer
from core.memory import ProcessNotFoundError, ProcessAccessError

logger = logging.getLogger("zmxy4.cheats")


class CheatEngine:
    """
    作弊引擎 —— 管理所有作弊功能的生命周期。
    每个功能 = 一组内存地址 + 一种操作策略。
    """

    def __init__(self):
        self.pm = ProcessManager()
        self.scanner = MemoryScanner(self.pm)
        self.freezer = MemoryFreezer(self.scanner)

        # 存储扫描到的关键地址
        self.hp_addresses: list[int] = []
        self.mp_addresses: list[int] = []
        self.attack_addresses: list[int] = []
        self.level_addresses: list[int] = []

        # 功能开关状态
        self._god_mode = False        # 无敌模式
        self._infinite_hp = False     # 无限血量
        self._infinite_mp = False     # 无限法力
        self._one_hit_kill = False    # 一击必杀
        self._monster_suicide = False # 怪物自杀

        # 功能启用后的值
        self._max_hp = 999999.0
        self._max_mp = 99999.0
        self._god_hp = 9999999.0
        self._max_attack = 9999999

        self._attached = False

    # ──────────────────────────────────────
    #  进程管理
    # ──────────────────────────────────────

    def attach(self) -> tuple[bool, str]:
        """连接到游戏进程。返回 (成功?, 消息)"""
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
        """断开连接"""
        self.disable_all()
        self.pm.close()
        self._attached = False

    @property
    def is_attached(self) -> bool:
        return self._attached

    # ──────────────────────────────────────
    #  值扫描（造梦西游4 特定流程）
    # ──────────────────────────────────────

    def scan_values(self) -> dict[str, int]:
        """
        执行完整的值扫描流程。
        用户需要在游戏中进行操作（扣血、扣蓝等）来辅助定位。
        返回当前找到的地址数量统计。
        """
        if not self._attached:
            return {"error": "未连接游戏进程"}

        result = {}
        if self.hp_addresses:
            result["hp"] = len(self.hp_addresses)
        if self.mp_addresses:
            result["mp"] = len(self.mp_addresses)
        if self.attack_addresses:
            result["attack"] = len(self.attack_addresses)
        return result

    def scan_hp_first(self, current_hp: int) -> int:
        """首次扫描血量（输入当前血量值）"""
        addrs = self.scanner.scan_float(float(current_hp), first_scan=True)
        self.hp_addresses = addrs
        return len(addrs)

    def scan_hp_next(self, current_hp: int) -> int:
        """再次扫描血量（受到伤害后输入新的血量值）"""
        addrs = self.scanner.scan_float(float(current_hp), first_scan=False)
        self.hp_addresses = addrs
        return len(addrs)

    def scan_mp_first(self, current_mp: int) -> int:
        """首次扫描法力"""
        addrs = self.scanner.scan_float(float(current_mp), first_scan=True)
        self.mp_addresses = addrs
        return len(addrs)

    def scan_mp_next(self, current_mp: int) -> int:
        """再次扫描法力"""
        addrs = self.scanner.scan_float(float(current_mp), first_scan=False)
        self.mp_addresses = addrs
        return len(addrs)

    def scan_attack_first(self, current_atk: int) -> int:
        """首次扫描攻击力"""
        addrs = self.scanner.scan_int(current_atk, first_scan=True)
        self.attack_addresses = addrs
        return len(addrs)

    def scan_attack_next(self, current_atk: int) -> int:
        """再次扫描攻击力"""
        addrs = self.scanner.scan_int(current_atk, first_scan=False)
        self.attack_addresses = addrs
        return len(addrs)

    # ──────────────────────────────────────
    #  作弊功能
    # ──────────────────────────────────────

    def enable_infinite_hp(self):
        """开启无限血量"""
        if not self.hp_addresses:
            raise ValueError("请先扫描血量地址")

        self._infinite_hp = True
        for addr in self.hp_addresses:
            self.freezer.freeze_float(addr, self._max_hp)
        self.freezer.start()
        logger.info("无限血量已开启")

    def disable_infinite_hp(self):
        """关闭无限血量"""
        self._infinite_hp = False
        for addr in self.hp_addresses:
            self.freezer.unfreeze(addr)
        if not self._infinite_mp:
            self.freezer.stop()
        logger.info("无限血量已关闭")

    def enable_infinite_mp(self):
        """开启无限法力"""
        if not self.mp_addresses:
            raise ValueError("请先扫描法力地址")

        self._infinite_mp = True
        for addr in self.mp_addresses:
            self.freezer.freeze_float(addr, self._max_mp)
        self.freezer.start()
        logger.info("无限法力已开启")

    def disable_infinite_mp(self):
        """关闭无限法力"""
        self._infinite_mp = False
        for addr in self.mp_addresses:
            self.freezer.unfreeze(addr)
        if not self._infinite_hp:
            self.freezer.stop()
        logger.info("无限法力已关闭")

    def enable_god_mode(self):
        """
        开启无敌模式。
        策略：将血量锁定在极高值，并将攻击方伤害置0。
        """
        if not self.hp_addresses:
            raise ValueError("请先扫描血量地址")

        self._god_mode = True
        for addr in self.hp_addresses:
            self.freezer.freeze_float(addr, self._god_hp)
        self.freezer.start()
        logger.info("无敌模式已开启")

    def disable_god_mode(self):
        """关闭无敌模式"""
        self._god_mode = False
        for addr in self.hp_addresses:
            self.freezer.unfreeze(addr)
        if not self._infinite_hp and not self._infinite_mp:
            self.freezer.stop()
        logger.info("无敌模式已关闭")

    def enable_one_hit_kill(self):
        """开启一击必杀 —— 将攻击力锁定在极大值"""
        if not self.attack_addresses:
            raise ValueError("请先扫描攻击力地址")

        self._one_hit_kill = True
        for addr in self.attack_addresses:
            self.freezer.freeze_int(addr, self._max_attack)
        self.freezer.start()
        logger.info("一击必杀已开启")

    def disable_one_hit_kill(self):
        """关闭一击必杀"""
        self._one_hit_kill = False
        for addr in self.attack_addresses:
            self.freezer.unfreeze(addr)
        if not any([self._infinite_hp, self._infinite_mp, self._god_mode]):
            self.freezer.stop()
        logger.info("一击必杀已关闭")

    def enable_monster_suicide(self):
        """
        开启怪物自杀。
        原理：扫描怪物血量地址并写0。
        注意：需要找到怪物的血量地址（通常在玩家血量地址附近）。
        这里是尝试在玩家血量地址的偏移区域寻找。
        """
        if not self.hp_addresses:
            raise ValueError("请先扫描血量地址")

        self._monster_suicide = True
        # 策略：在游戏内存中找怪物相关地址
        # 通常在玩家血量附近 -0x10 ~ -0x100 的偏移范围
        suicide_addrs = []
        for player_hp_addr in self.hp_addresses:
            for offset in range(-0x200, 0, 4):
                try:
                    addr = player_hp_addr + offset
                    val = self.scanner.read_float(addr)
                    # 如果这个地址也在合理血量范围（1~10000），视为怪物血量
                    if 1.0 < val < 10000.0:
                        suicide_addrs.append(addr)
                        if len(suicide_addrs) >= 10:
                            break
                    if len(suicide_addrs) >= 10:
                        break
                except Exception:
                    continue

        if suicide_addrs:
            for addr in suicide_addrs:
                self.freezer.freeze_float(addr, 0.0)
            self.freezer.start()
            logger.info(f"怪物自杀已开启（{len(suicide_addrs)} 个地址）")
        else:
            raise ValueError("未找到怪物血量地址，请尝试先挨打后再试")

    def disable_monster_suicide(self):
        """关闭怪物自杀"""
        self._monster_suicide = False
        # 解冻所有
        self.freezer.unfreeze_all()
        logger.info("怪物自杀已关闭")

    def disable_all(self):
        """关闭所有作弊功能"""
        self.disable_infinite_hp()
        self.disable_infinite_mp()
        self.disable_god_mode()
        self.disable_one_hit_kill()
        self.disable_monster_suicide()
        self.freezer.unfreeze_all()
        logger.info("所有作弊功能已关闭")

    def get_status(self) -> dict:
        """获取当前所有作弊功能状态"""
        return {
            "attached": self._attached,
            "god_mode": self._god_mode,
            "infinite_hp": self._infinite_hp,
            "infinite_mp": self._infinite_mp,
            "one_hit_kill": self._one_hit_kill,
            "monster_suicide": self._monster_suicide,
            "hp_addresses": len(self.hp_addresses),
            "mp_addresses": len(self.mp_addresses),
            "attack_addresses": len(self.attack_addresses),
        }
