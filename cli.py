#!/usr/bin/env python3
"""
造梦西游4 · 天机辅助器 CLI
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.WARNING)

from cheats import CheatEngine

engine = CheatEngine()


def print_banner():
    print()
    print("  ╔════════════════════════════════════╗")
    print("  ║  造梦西游4 · 天机辅助器 CLI v1.0   ║")
    print("  ║  ZMXY4 Heaven's Secret             ║")
    print("  ╚════════════════════════════════════╝")
    print()


def print_help():
    print("命令列表:")
    print("  scan <hp|mp|atk> <数值>      扫描（自动判断首次/再次）")
    print("  scan -f <hp|mp|atk> <数值>   强制首次扫描")
    print("  scan -n <hp|mp|atk> <数值>   强制再次扫描")
    print("  enable <功能>      开启功能")
    print("  disable <功能>     关闭功能")
    print("  try <hp|mp|atk>    逐个地址测试（调试用）")
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
    else:
        print(f"  ✗ {msg}")
    return ok


def do_scan(args: list):
    """scan <hp|mp|atk> [-f|-n] <数值>"""
    if not engine.is_attached:
        print("  ✗ 未连接，请先连接")
        return

    target = args[0].lower()
    if target not in ("hp", "mp", "atk"):
        print(f"  ✗ 未知目标: {target}")
        return

    # 解析 -f / -n 标志
    if len(args) >= 3 and args[1].startswith("-"):
        flag = args[1]
        value_str = args[2]
    else:
        flag = ""
        value_str = args[1]

    try:
        value = float(value_str)
    except ValueError:
        print(f"  ✗ 无效数值: {value_str}")
        return

    # 判断首次/再次
    if flag == "-f":
        first = True
    elif flag == "-n":
        first = False
    else:
        # 自动判断：有已存结果就是再次，否则首次
        results = getattr(engine, f"{target}_results", {})
        first = not bool(results and any(results.values()))

    label = {"hp": "血量", "mp": "法力", "atk": "攻击力"}[target]
    if target == "atk":
        value = int(value)

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
        for name, key in [("无敌模式", "god_mode"), ("无限血量", "infinite_hp"),
                          ("无限法力", "infinite_mp"), ("一击必杀", "one_hit_kill")]:
            print(f"    {'●' if s.get(key, False) else '○'} {name}")
        print(f"  血量地址: {s.get('hp_addresses', 0)}")
        print(f"  法力地址: {s.get('mp_addresses', 0)}")
        print(f"  攻击地址: {s.get('attack_addresses', 0)}")


def interactive():
    print_banner()
    print("  正在连接游戏进程...")
    do_connect()
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
        elif cmd == "connect":
            do_connect()
        elif cmd == "scan":
            if len(args) < 2:
                print("  ! 用法: scan <hp|mp|atk> [-f|-n] <数值>")
                continue
            if args[1].startswith("-"):
                # scan -f hp 16050 这种格式
                if len(args) < 3:
                    print("  ! 用法: scan [-f|-n] <hp|mp|atk> <数值>")
                    continue
                do_scan([args[2], args[1], args[3]])
            else:
                do_scan(args[1:])
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
        elif cmd == "try":
            if len(args) < 2:
                print("  ! 用法: try <hp|mp|atk>")
                continue
            key = args[1] + "_results"
            results = getattr(engine, key, {})
            typ = engine._best_type(results)
            if not typ or typ not in results or not results[typ]:
                print("  ✗ 没有可测试的地址，请先扫描")
                continue
            addrs = results[typ]
            is_atk = (args[1] == "atk")
            val = 99999999 if is_atk else 999999.0
            print(f"  类型={typ}, 共 {len(addrs)} 个地址, 将写入值={val}")
            for i, addr in enumerate(addrs):
                print(f"  [{i}] 地址 0x{addr:X}")
                engine.freezer.unfreeze_all()
                engine.freezer.freeze(addr, typ, val)
                engine.freezer.start()
                input(f"      按回车测试下一个...")
            engine.freezer.unfreeze_all()
            print("  ✓ 测试完成")
        else:
            print(f"  ✗ 未知命令: {cmd}")


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "connect":
            do_connect()
            return
        if not engine.attach()[0]:
            print("连接失败")
            return
        if cmd == "scan" and len(sys.argv) >= 4:
            do_scan(sys.argv[2:])
        elif cmd == "scan" and len(sys.argv) >= 5:
            # scan -f hp 16050 格式
            do_scan([sys.argv[3], sys.argv[2], sys.argv[4]])
        elif cmd == "enable" and len(sys.argv) >= 3:
            do_enable(sys.argv[2].lower())
        elif cmd == "disable" and len(sys.argv) >= 3:
            do_disable(sys.argv[2].lower())
        elif cmd == "status":
            do_status()
        else:
            print(f"未知命令或参数不足")
    else:
        interactive()


if __name__ == "__main__":
    main()
