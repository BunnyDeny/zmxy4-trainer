"""
gui/app.py - 造梦西游4 辅助器图形界面
========================================
暗黑风格，分区布局：进程连接 → 数值扫描 → 作弊开关 → 状态监控。
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from core import ProcessManager, MemoryScanner, MemoryFreezer
from core.memory import ProcessNotFoundError
from core.process import GameProcessFinder
from cheats import CheatEngine

logger = logging.getLogger("zmxy4.gui")


# ── 配色方案（暗黑游戏风）────────────────────────────────
COLORS = {
    "bg_dark": "#1a1a2e",        # 深色背景
    "bg_medium": "#16213e",      # 中灰背景
    "bg_light": "#0f3460",       # 浅色背景
    "accent": "#e94560",         # 红色强调
    "accent_green": "#00ff88",   # 绿色（已启用）
    "accent_yellow": "#ffd700",  # 金色
    "text_primary": "#ffffff",   # 主文字
    "text_secondary": "#8899aa", # 辅助文字
    "text_dim": "#556677",       # 弱文字
    "border": "#2a2a4a",         # 边框
    "success": "#00cc66",        # 成功色
    "warning": "#ff6600",        # 警告色
    "danger": "#ff3333",         # 危险色
}

FONTS = {
    "title": ("Microsoft YaHei UI", 16, "bold"),
    "heading": ("Microsoft YaHei UI", 12, "bold"),
    "normal": ("Microsoft YaHei UI", 10),
    "small": ("Microsoft YaHei UI", 9),
    "mono": ("Consolas", 10),
}


class ToolTip:
    """悬浮提示"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#333355", foreground="#ffffff",
                         relief=tk.SOLID, borderwidth=1,
                         font=FONTS["small"], padx=8, pady=4)
        label.pack()

    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ToggleButton(tk.Frame):
    """自定义开关按钮（带发光效果）"""

    def __init__(self, parent, text, on_color=COLORS["accent_green"],
                 off_color=COLORS["bg_light"], command=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.text = text
        self.on_color = on_color
        self.off_color = off_color
        self._command = command
        self._state = False

        self.btn = tk.Button(
            self,
            text=f"  {text}  ",
            font=FONTS["heading"],
            bg=self.off_color,
            fg=COLORS["text_secondary"],
            relief=tk.FLAT,
            activebackground=self.on_color,
            activeforeground=COLORS["text_primary"],
            cursor="hand2",
            padx=15, pady=8,
            bd=0,
            command=self._on_click,
        )
        self.btn.pack(fill=tk.BOTH, expand=True)

    def _on_click(self):
        self._state = not self._state
        self._update_style()
        if self._command:
            self._command(self._state)

    def _update_style(self):
        if self._state:
            self.btn.config(
                bg=self.on_color,
                fg=COLORS["text_primary"],
                text=f"  ✓ {self.text}  ",
            )
        else:
            self.btn.config(
                bg=self.off_color,
                fg=COLORS["text_secondary"],
                text=f"  {self.text}  ",
            )

    def set_state(self, state: bool):
        self._state = state
        self._update_style()

    @property
    def is_on(self) -> bool:
        return self._state


class CheatApp:
    """主应用程序"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("造梦西游4 · 天机辅助 v1.0")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        self.root.configure(bg=COLORS["bg_dark"])

        # 作弊引擎
        self.cheats = CheatEngine()

        # 设置窗口图标（可选）
        try:
            self.root.iconbitmap(default="assets/icon.ico")
        except Exception:
            pass

        # 构建界面
        self._build_ui()

        # 定时器：状态刷新
        self._update_status()

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self):
        # 主布局：左右分栏
        main_container = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── 左侧面板 ──
        left_panel = tk.Frame(main_container, bg=COLORS["bg_medium"],
                              width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_panel.pack_propagate(False)

        self._build_connection_panel(left_panel)
        self._build_scan_panel(left_panel)

        # ── 右侧面板 ──
        right_panel = tk.Frame(main_container, bg=COLORS["bg_medium"])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self._build_cheats_panel(right_panel)
        self._build_status_panel(right_panel)

    def _build_connection_panel(self, parent):
        """连接面板：查找进程 + 连接"""
        frame = tk.LabelFrame(parent, text="连 接", font=FONTS["heading"],
                              fg=COLORS["accent"], bg=COLORS["bg_medium"],
                              relief=tk.FLAT, padx=10, pady=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # 进程状态
        self._proc_status = tk.Label(frame, text="● 未连接",
                                     font=FONTS["normal"],
                                     fg=COLORS["text_dim"],
                                     bg=COLORS["bg_medium"])
        self._proc_status.pack(anchor=tk.W)

        # 进程名显示
        self._proc_name = tk.Label(frame, text="等待检测...",
                                   font=FONTS["small"],
                                   fg=COLORS["text_secondary"],
                                   bg=COLORS["bg_medium"])
        self._proc_name.pack(anchor=tk.W, pady=(2, 8))

        # 按钮行
        btn_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        btn_row.pack(fill=tk.X)

        self._btn_find = tk.Button(
            btn_row, text="查找进程", font=FONTS["normal"],
            bg=COLORS["bg_light"], fg=COLORS["text_primary"],
            relief=tk.FLAT, padx=10, cursor="hand2",
            activebackground=COLORS["accent"],
            command=self._on_find_process,
        )
        self._btn_find.pack(side=tk.LEFT, padx=(0, 5))

        self._btn_connect = tk.Button(
            btn_row, text="连接", font=FONTS["normal"],
            bg=COLORS["accent"], fg=COLORS["text_primary"],
            relief=tk.FLAT, padx=10, cursor="hand2",
            activebackground=COLORS["danger"],
            state=tk.DISABLED,
            command=self._on_connect,
        )
        self._btn_connect.pack(side=tk.LEFT)

        ToolTip(self._btn_find, "扫描系统进程，自动找到造梦西游4微端\n进程名：zmxy_online")
        ToolTip(self._btn_connect, "连接到游戏进程，建立内存通信")

    def _build_scan_panel(self, parent):
        """扫描面板：血量/法力/攻击力地址扫描"""
        frame = tk.LabelFrame(parent, text="数值扫描", font=FONTS["heading"],
                              fg=COLORS["accent_yellow"],
                              bg=COLORS["bg_medium"],
                              relief=tk.FLAT, padx=10, pady=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # 血量
        hp_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        hp_row.pack(fill=tk.X, pady=2)
        tk.Label(hp_row, text="血量:", width=8, anchor=tk.W,
                 font=FONTS["normal"], fg=COLORS["accent"],
                 bg=COLORS["bg_medium"]).pack(side=tk.LEFT)
        self._hp_entry = tk.Entry(hp_row, width=15, font=FONTS["mono"],
                                  bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                                  relief=tk.FLAT, insertbackground=COLORS["text_primary"])
        self._hp_entry.pack(side=tk.LEFT, padx=2)
        self._hp_entry.insert(0, "当前血量数值")

        hp_btn_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        hp_btn_row.pack(fill=tk.X, pady=2)
        self._btn_hp_first = tk.Button(hp_btn_row, text="首次扫描",
                                       font=FONTS["small"],
                                       bg=COLORS["bg_light"],
                                       fg=COLORS["text_primary"],
                                       relief=tk.FLAT, cursor="hand2",
                                       command=self._on_scan_hp_first)
        self._btn_hp_first.pack(side=tk.LEFT, padx=2)
        self._btn_hp_next = tk.Button(hp_btn_row, text="再次扫描",
                                      font=FONTS["small"],
                                      bg=COLORS["bg_light"],
                                      fg=COLORS["text_primary"],
                                      relief=tk.FLAT, cursor="hand2",
                                      command=self._on_scan_hp_next)
        self._btn_hp_next.pack(side=tk.LEFT, padx=2)

        # 地址计数显示
        self._hp_count = tk.Label(frame, text="地址: 未扫描",
                                  font=FONTS["small"],
                                  fg=COLORS["text_dim"],
                                  bg=COLORS["bg_medium"])
        self._hp_count.pack(anchor=tk.W, pady=(2, 0))

        # 分割线
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # 法力
        mp_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        mp_row.pack(fill=tk.X, pady=2)
        tk.Label(mp_row, text="法力:", width=8, anchor=tk.W,
                 font=FONTS["normal"], fg=COLORS["accent_green"],
                 bg=COLORS["bg_medium"]).pack(side=tk.LEFT)
        self._mp_entry = tk.Entry(mp_row, width=15, font=FONTS["mono"],
                                  bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                                  relief=tk.FLAT, insertbackground=COLORS["text_primary"])
        self._mp_entry.pack(side=tk.LEFT, padx=2)
        self._mp_entry.insert(0, "当前法力数值")

        mp_btn_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        mp_btn_row.pack(fill=tk.X, pady=2)
        self._btn_mp_first = tk.Button(mp_btn_row, text="首次扫描",
                                       font=FONTS["small"],
                                       bg=COLORS["bg_light"],
                                       fg=COLORS["text_primary"],
                                       relief=tk.FLAT, cursor="hand2",
                                       command=self._on_scan_mp_first)
        self._btn_mp_first.pack(side=tk.LEFT, padx=2)
        self._btn_mp_next = tk.Button(mp_btn_row, text="再次扫描",
                                      font=FONTS["small"],
                                      bg=COLORS["bg_light"],
                                      fg=COLORS["text_primary"],
                                      relief=tk.FLAT, cursor="hand2",
                                      command=self._on_scan_mp_next)
        self._btn_mp_next.pack(side=tk.LEFT, padx=2)

        self._mp_count = tk.Label(frame, text="地址: 未扫描",
                                  font=FONTS["small"],
                                  fg=COLORS["text_dim"],
                                  bg=COLORS["bg_medium"])
        self._mp_count.pack(anchor=tk.W, pady=(2, 0))

        # 分割线
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # 攻击力
        atk_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        atk_row.pack(fill=tk.X, pady=2)
        tk.Label(atk_row, text="攻击:", width=8, anchor=tk.W,
                 font=FONTS["normal"], fg=COLORS["warning"],
                 bg=COLORS["bg_medium"]).pack(side=tk.LEFT)
        self._atk_entry = tk.Entry(atk_row, width=15, font=FONTS["mono"],
                                   bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                                   relief=tk.FLAT, insertbackground=COLORS["text_primary"])
        self._atk_entry.pack(side=tk.LEFT, padx=2)
        self._atk_entry.insert(0, "当前攻击数值")

        atk_btn_row = tk.Frame(frame, bg=COLORS["bg_medium"])
        atk_btn_row.pack(fill=tk.X, pady=2)
        self._btn_atk_first = tk.Button(atk_btn_row, text="首次扫描",
                                        font=FONTS["small"],
                                        bg=COLORS["bg_light"],
                                        fg=COLORS["text_primary"],
                                        relief=tk.FLAT, cursor="hand2",
                                        command=self._on_scan_atk_first)
        self._btn_atk_first.pack(side=tk.LEFT, padx=2)
        self._btn_atk_next = tk.Button(atk_btn_row, text="再次扫描",
                                       font=FONTS["small"],
                                       bg=COLORS["bg_light"],
                                       fg=COLORS["text_primary"],
                                       relief=tk.FLAT, cursor="hand2",
                                       command=self._on_scan_atk_next)
        self._btn_atk_next.pack(side=tk.LEFT, padx=2)

        self._atk_count = tk.Label(frame, text="地址: 未扫描",
                                   font=FONTS["small"],
                                   fg=COLORS["text_dim"],
                                   bg=COLORS["bg_medium"])
        self._atk_count.pack(anchor=tk.W, pady=(2, 0))

    def _build_cheats_panel(self, parent):
        """作弊功能面板：开关按钮"""
        frame = tk.LabelFrame(parent, text="作弊功能", font=FONTS["heading"],
                              fg=COLORS["accent_green"],
                              bg=COLORS["bg_medium"],
                              relief=tk.FLAT, padx=15, pady=15)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 2x3 网格布局
        grid = tk.Frame(frame, bg=COLORS["bg_medium"])
        grid.pack(expand=True)

        # 第一行
        row1 = tk.Frame(grid, bg=COLORS["bg_medium"])
        row1.pack(fill=tk.X, pady=4)

        self._btn_god = ToggleButton(
            row1, "无敌模式", on_color="#00aa66",
            command=self._on_god_mode,
        )
        self._btn_god.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ToolTip(self._btn_god.btn, "血量锁定在最大值\n怪物打你不掉血")

        self._btn_infinite_hp = ToggleButton(
            row1, "无限血量", on_color="#00aa66",
            command=self._on_infinite_hp,
        )
        self._btn_infinite_hp.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ToolTip(self._btn_infinite_hp.btn, "血量始终回满\n不会被怪打死")

        # 第二行
        row2 = tk.Frame(grid, bg=COLORS["bg_medium"])
        row2.pack(fill=tk.X, pady=4)

        self._btn_infinite_mp = ToggleButton(
            row2, "无限法力", on_color="#0088ff",
            command=self._on_infinite_mp,
        )
        self._btn_infinite_mp.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ToolTip(self._btn_infinite_mp.btn, "法力始终回满\n技能随便放")

        self._btn_one_hit = ToggleButton(
            row2, "一击必杀", on_color="#ff4400",
            command=self._on_one_hit_kill,
        )
        self._btn_one_hit.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ToolTip(self._btn_one_hit.btn, "攻击力锁定为最大值\n打怪一下秒杀")

        # 第三行
        row3 = tk.Frame(grid, bg=COLORS["bg_medium"])
        row3.pack(fill=tk.X, pady=4)

        self._btn_monster_suicide = ToggleButton(
            row3, "怪物自杀", on_color="#ff00ff",
            command=self._on_monster_suicide,
        )
        self._btn_monster_suicide.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ToolTip(self._btn_monster_suicide.btn, "怪物血量设为0\n进图怪全死")

        # 重置按钮
        self._btn_reset = tk.Button(
            row3, text="  全部关闭  ",
            font=FONTS["heading"],
            bg=COLORS["danger"], fg=COLORS["text_primary"],
            relief=tk.FLAT, padx=15, pady=8,
            cursor="hand2",
            command=self._on_disable_all,
        )
        self._btn_reset.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ToolTip(self._btn_reset, "关闭所有作弊功能")

    def _build_status_panel(self, parent):
        """状态面板：日志输出"""
        frame = tk.LabelFrame(parent, text="运行日志", font=FONTS["heading"],
                              fg=COLORS["text_secondary"],
                              bg=COLORS["bg_medium"],
                              relief=tk.FLAT, padx=10, pady=5)
        frame.pack(fill=tk.X, side=tk.BOTTOM)

        self._log_text = tk.Text(
            frame, height=6, font=FONTS["mono"],
            bg=COLORS["bg_dark"], fg=COLORS["text_secondary"],
            relief=tk.FLAT, bd=0,
            state=tk.DISABLED,
        )
        self._log_text.pack(fill=tk.X, pady=5)

        # 底部信息栏
        info_bar = tk.Frame(self.root, bg=COLORS["bg_dark"])
        info_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 5))

        self._status_label = tk.Label(info_bar, text="就绪 — 请先打开游戏",
                                      font=FONTS["small"],
                                      fg=COLORS["text_dim"],
                                      bg=COLORS["bg_dark"])
        self._status_label.pack(side=tk.LEFT)

        self._version_label = tk.Label(info_bar, text="v1.0 | by 天机",
                                       font=FONTS["small"],
                                       fg=COLORS["text_dim"],
                                       bg=COLORS["bg_dark"])
        self._version_label.pack(side=tk.RIGHT)

    # ── 事件处理 ────────────────────────────────────────

    def _on_find_process(self):
        """查找游戏进程"""
        self._log("正在扫描进程...")
        finder = GameProcessFinder()

        def do_find():
            found = finder.find()
            self.root.after(0, lambda: self._on_find_result(found, finder))

        threading.Thread(target=do_find, daemon=True).start()

    def _on_find_result(self, found: bool, finder: GameProcessFinder):
        if found:
            info = finder.get_process_info()
            self._proc_status.config(text="● 进程已找到",
                                     fg=COLORS["success"])
            self._proc_name.config(
                text=f"{info.get('name', '?')} (PID: {info.get('pid', '?')})"
            )
            self._btn_connect.config(state=tk.NORMAL)
            self._log(f"找到游戏进程: {info.get('name', '?')} "
                      f"(PID={info.get('pid', '?')})")
        else:
            self._proc_status.config(text="● 未找到进程",
                                     fg=COLORS["danger"])
            self._log("未找到游戏进程，请先启动造梦西游4")

    def _on_connect(self):
        """连接到游戏进程"""
        self._log("正在连接游戏进程...")

        def do_connect():
            ok, msg = self.cheats.attach()
            self.root.after(0, lambda: self._on_connect_result(ok, msg))

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str):
        if ok:
            self._proc_status.config(text="● 已连接", fg=COLORS["success"])
            self._btn_connect.config(text="已连接", state=tk.DISABLED)
            self._btn_find.config(state=tk.DISABLED)
            self._status_label.config(text="已连接 — 可以开始扫描数值了",
                                      fg=COLORS["accent_green"])
            self._log("连接成功！造梦西游4 内存通道已建立")
        else:
            self._log(f"连接失败: {msg}")
            messagebox.showerror("连接失败", msg)

    def _on_scan_hp_first(self):
        value = self._get_scan_value(self._hp_entry)
        if value is None:
            return
        self._log(f"首次扫描血量: {value}，请稍候...")

        def do_scan():
            counts = self.cheats.scan_hp(value, first_scan=True)
            text = "  |  ".join(f"{t}: {c}" for t, c in counts.items())
            self.root.after(0, lambda: self._hp_count.config(text=text))
            self.root.after(0, lambda: self._log(f"血量结果: {text}"))

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_hp_next(self):
        value = self._get_scan_value(self._hp_entry)
        if value is None:
            return
        self._log(f"再次扫描血量: {value}")

        def do_scan():
            counts = self.cheats.scan_hp(value, first_scan=False)
            text = "  |  ".join(f"{t}: {c}" for t, c in counts.items())
            self.root.after(0, lambda: self._hp_count.config(text=text))
            self.root.after(0, lambda: self._log(f"血量剩余: {text}"))

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_mp_first(self):
        value = self._get_scan_value(self._mp_entry)
        if value is None:
            return
        self._log(f"首次扫描法力: {value}，请稍候...")

        def do_scan():
            counts = self.cheats.scan_mp(value, first_scan=True)
            text = "  |  ".join(f"{t}: {c}" for t, c in counts.items())
            self.root.after(0, lambda: self._mp_count.config(text=text))
            self.root.after(0, lambda: self._log(f"法力结果: {text}"))

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_mp_next(self):
        value = self._get_scan_value(self._mp_entry)
        if value is None:
            return
        self._log(f"再次扫描法力: {value}")

        def do_scan():
            counts = self.cheats.scan_mp(value, first_scan=False)
            text = "  |  ".join(f"{t}: {c}" for t, c in counts.items())
            self.root.after(0, lambda: self._mp_count.config(text=text))
            self.root.after(0, lambda: self._log(f"法力剩余: {text}"))

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_atk_first(self):
        value = self._get_scan_value(self._atk_entry, dtype="int")
        if value is None:
            return
        self._log(f"首次扫描攻击: {value}，请稍候...")

        def do_scan():
            counts = self.cheats.scan_attack(value, first_scan=True)
            text = "  |  ".join(f"{t}: {c}" for t, c in counts.items())
            self.root.after(0, lambda: self._atk_count.config(text=text))
            self.root.after(0, lambda: self._log(f"攻击结果: {text}"))

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_atk_next(self):
        value = self._get_scan_value(self._atk_entry, dtype="int")
        if value is None:
            return
        self._log(f"再次扫描攻击: {value}")

        def do_scan():
            counts = self.cheats.scan_attack(value, first_scan=False)
            text = "  |  ".join(f"{t}: {c}" for t, c in counts.items())
            self.root.after(0, lambda: self._atk_count.config(text=text))
            self.root.after(0, lambda: self._log(f"攻击剩余: {text}"))

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_god_mode(self, state: bool):
        try:
            if state:
                self.cheats.enable_god_mode()
                self._log("无敌模式 已开启")
            else:
                self.cheats.disable_god_mode()
                self._log("无敌模式 已关闭")
        except Exception as e:
            self._log(f"错误: {e}")
            self._btn_god.set_state(False)

    def _on_infinite_hp(self, state: bool):
        try:
            if state:
                self.cheats.enable_infinite_hp()
                self._log("无限血量 已开启")
            else:
                self.cheats.disable_infinite_hp()
                self._log("无限血量 已关闭")
        except Exception as e:
            self._log(f"错误: {e}")
            self._btn_infinite_hp.set_state(False)

    def _on_infinite_mp(self, state: bool):
        try:
            if state:
                self.cheats.enable_infinite_mp()
                self._log("无限法力 已开启")
            else:
                self.cheats.disable_infinite_mp()
                self._log("无限法力 已关闭")
        except Exception as e:
            self._log(f"错误: {e}")
            self._btn_infinite_mp.set_state(False)

    def _on_one_hit_kill(self, state: bool):
        try:
            if state:
                self.cheats.enable_one_hit_kill()
                self._log("一击必杀 已开启")
            else:
                self.cheats.disable_one_hit_kill()
                self._log("一击必杀 已关闭")
        except Exception as e:
            self._log(f"错误: {e}")
            self._btn_one_hit.set_state(False)

    def _on_monster_suicide(self, state: bool):
        try:
            if state:
                self.cheats.enable_monster_suicide()
                self._log("怪物自杀 已开启")
            else:
                self.cheats.disable_monster_suicide()
                self._log("怪物自杀 已关闭")
        except Exception as e:
            self._log(f"错误: {e}")
            self._btn_monster_suicide.set_state(False)

    def _on_disable_all(self):
        self.cheats.disable_all()
        self._btn_god.set_state(False)
        self._btn_infinite_hp.set_state(False)
        self._btn_infinite_mp.set_state(False)
        self._btn_one_hit.set_state(False)
        self._btn_monster_suicide.set_state(False)
        self._log("所有作弊功能已关闭")

    # ── 辅助方法 ────────────────────────────────────────

    def _get_scan_value(self, entry: tk.Entry, dtype: str = "float"):
        """从输入框获取数值并验证"""
        text = entry.get().strip()
        try:
            if dtype == "int":
                return int(float(text))
            return float(text)
        except ValueError:
            messagebox.showerror("输入错误",
                                 f"请输入有效数值（当前: '{text}'）")
            return None

    def _log(self, message: str):
        """输出日志到日志框"""
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"> {message}\n")
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)
        logger.info(message)

    def _update_status(self):
        """定时刷新状态（每3秒）"""
        if self.cheats.is_attached:
            status = self.cheats.get_status()
            active = []
            if status["god_mode"]:
                active.append("无敌")
            if status["infinite_hp"]:
                active.append("无限血")
            if status["infinite_mp"]:
                active.append("无限蓝")
            if status["one_hit_kill"]:
                active.append("秒杀")
            if status["monster_suicide"]:
                active.append("怪物自杀")

            if active:
                self._status_label.config(
                    text=f"运行中: {' | '.join(active)}",
                    fg=COLORS["accent_green"])
            else:
                self._status_label.config(
                    text="已连接 — 选择功能后开启",
                    fg=COLORS["text_secondary"])
        self.root.after(3000, self._update_status)

    # ── 启动 ────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
