#!/usr/bin/env python3
"""
造梦西游4 · 天机辅助器 CLI
=============================
纯命令行版本。支持扫描数值、开启/关闭作弊功能。

用法:
  python cli.py                    # 交互模式
  python cli.py scan hp 16050      # 首次扫描血量
  python cli.py scan hp 15200      # 再次扫描（受伤后）
  python cli.py enable inf-hp      # 开启无限血量
  python cli.py disable all        # 关闭所有
  python cli.py status             # 查看状态
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.WARNING)

from cheats import CheatEngine

engine = CheatEngine()
scan_target = None  # 'hp', 'mp', 'atk'


def print_banner():
    print()
    print("  ╔════════════════════════════════════╗")
    print("  ║  造梦西游4 · 天机辅助器 CLI v1.0   ║")
    print("  ║  ZMXY4 Heaven's Secret             ║")
    print("  ╚════════════════════════════════════╝")
    print()


def print_help():
    print("命令列表:")
    print("  scan hp <数值>     首次/再次扫描血量")
    print("  scan mp <数值>     首次/再次扫描法力")
    print("  scan atk <数值>    首次/再次扫描攻击力")
    print("  enable <功能>      开启功能")
    print("  disable <功能>     关闭功能")
    print("  status             显示当前状态")
    print("  help               显示帮助")
    print("  exit / quit        退出")
    print()
    print("功能名: god | inf-hp | inf-mp | one-hit | all")
    print()


def do_connect() -> bool:
    ok, msg = engine.attach()
    if ok:
        print(f"  ✓ {msg}")
        return True
    else:
        print(f"  ✗ {msg}")
        return False


def do_scan(target: str, value_str: str):
    global scan_target

    if not engine.is_attached:
        print("  ✗ 未连接，请先连接")
        return

    try:
        value = float(value_str)
    except ValueError:
        print(f"  ✗ 无效数值: {value_str}")
        return

    if target == "hp":
        first = (scan_target != "hp")
        scan_target = "hp"
        label = "血量"
    elif target == "mp":
        first = (scan_target != "mp")
        scan_target = "mp"
        label = "法力"
    elif target == "atk":
        first = (scan_target != "atk")
        scan_target = "atk"
        label = "攻击力"
        value = int(value)  # atk as int
    else:
        print(f"  ✗ 未知目标: {target}")
        return

    mode = "首次扫描" if first else "再次扫描"
    print(f"  → {mode} {label}: {value}")

    if target == "hp":
        counts = engine.scan_hp(value, first)
    elif target == "mp":
        counts = engine.scan_mp(value, first)
    else:
        counts = engine.scan_attack(int(value), first)

    parts = [f"{t}: {c}" for t, c in counts.items()]
    print(f"  结果: {' | '.join(parts)}")


def do_enable(feature: str):
    if not engine.is_attached:
        print("  ✗ 未连接")
        return
    try:
        if feature == "god":
            engine.enable_god_mode()
            print("  ✓ 无敌模式已开启")
        elif feature == "inf-hp":
            engine.enable_infinite_hp()
            print("  ✓ 无限血量已开启")
        elif feature == "inf-mp":
            engine.enable_infinite_mp()
            print("  ✓ 无限法力已开启")
        elif feature == "one-hit":
            engine.enable_one_hit_kill()
            print("  ✓ 一击必杀已开启")
        else:
            print(f"  ✗ 未知功能: {feature}")
    except ValueError as e:
        print(f"  ✗ {e}")


def do_disable(feature: str):
    if not engine.is_attached:
        print("  ✗ 未连接")
        return
    if feature == "all":
        engine.disable_all()
        print("  ✓ 所有功能已关闭")
    else:
        print(f"  ✗ 未知: {feature}")


def do_status():
    s = engine.get_status()
    print(f"  连接: {'✓' if s['attached'] else '✗'}")
    if s['attached']:
        print(f"  功能:")
        features = [
            ("无敌模式", s.get('god_mode', False)),
            ("无限血量", s.get('infinite_hp', False)),
            ("无限法力", s.get('infinite_mp', False)),
            ("一击必杀", s.get('one_hit_kill', False)),
        ]
        for name, active in features:
            print(f"    {'●' if active else '○'} {name}")
        print(f"  血量地址: {s.get('hp_addresses', 0)}")
        print(f"  法力地址: {s.get('mp_addresses', 0)}")
        print(f"  攻击地址: {s.get('attack_addresses', 0)}")


def interactive():
    global scan_target
    print_banner()

    print("  正在连接游戏进程...")
    if not do_connect():
        print("  ! 连接失败，请确认微端已启动")
        print()

    print_help()

    while True:
        try:
            line = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        args = line.split()
        cmd = args[0].lower()

        if cmd in ("exit", "quit", "q"):
            engine.disable_all()
            print("  再见！")
            break

        elif cmd == "help":
            print_help()

        elif cmd == "status":
            do_status()

        elif cmd == "scan":
            if len(args) < 3:
                print("  ! 用法: scan <hp|mp|atk> <数值>")
                continue
            do_scan(args[1].lower(), args[2])

        elif cmd == "enable":
            if len(args) < 2:
                print("  ! 用法: enable <god|inf-hp|inf-mp|one-hit>")
                continue
            do_enable(args[1].lower())

        elif cmd == "disable":
            if len(args) < 2:
                print("  ! 用法: disable <功能|all>")
                continue
            do_disable(args[1].lower())

        elif cmd == "connect":
            do_connect()

        else:
            print(f"  ✗ 未知命令: {cmd}  输入 help 查看帮助")


def main():
    if len(sys.argv) > 1:
        # 非交互模式
        cmd = sys.argv[1].lower()

        if cmd == "scan":
            if len(sys.argv) < 4:
                print("用法: python cli.py scan <hp|mp|atk> <数值>")
                return
            if not engine.attach()[0]:
                print("连接失败")
                return
            do_scan(sys.argv[2].lower(), sys.argv[3])

        elif cmd == "enable":
            if len(sys.argv) < 3:
                print("用法: python cli.py enable <god|inf-hp|inf-mp|one-hit>")
                return
            if not engine.attach()[0]:
                print("连接失败")
                return
            do_enable(sys.argv[2].lower())

        elif cmd == "disable":
            if len(sys.argv) < 3:
                print("用法: python cli.py disable <all>")
                return
            if not engine.attach()[0]:
                print("连接失败")
                return
            do_disable(sys.argv[2].lower())

        elif cmd == "status":
            if not engine.attach()[0]:
                print("连接失败")
                return
            do_status()

        elif cmd == "connect":
            do_connect()

        else:
            print(f"未知命令: {cmd}")
    else:
        interactive()


if __name__ == "__main__":
    main()
