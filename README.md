# 造梦西游4 · 天机辅助器 CLI

纯命令行造梦西游4微端内存辅助工具。

## 用法

```
python cli.py                # 交互模式
python cli.py scan hp 16050  # 非交互：首次扫描血量
python cli.py enable god     # 非交互：开启无敌
```

## 安装

```
pip install -r requirements.txt
```

## 交互模式

运行 `python cli.py` 后进入交互式命令行：

```
  > connect
  ✓ 连接成功！

  > scan hp 16050
  → 首次扫描 血量: 16050.0
  结果: int: 52341 | float: 0 | double: 0

  > scan hp 15000    ← 挨打后输入新值
  → 再次扫描 血量: 15000.0
  结果: int: 328 | float: 0 | double: 0

  > scan hp 14000    ← 再挨打
  结果: int: 6 | float: 0 | double: 0

  > enable inf-hp
  ✓ 无限血量已开启

  > status
  连接: ✓
  功能:
    ○ 无敌模式
    ● 无限血量
```

### 命令列表

| 命令 | 说明 |
|------|------|
| `scan hp <数值>` | 扫描血量 |
| `scan mp <数值>` | 扫描法力 |
| `scan atk <数值>` | 扫描攻击力 |
| `enable god` | 开启无敌模式 |
| `enable inf-hp` | 开启无限血量 |
| `enable inf-mp` | 开启无限法力 |
| `enable one-hit` | 开启一击必杀 |
| `disable all` | 关闭所有功能 |
| `status` | 显示当前状态 |
| `help` | 显示帮助 |

### 扫描技巧

1. 输入当前数值 → 首次扫描 → 看到各类型结果
2. 让怪打你/换装备改变数值 → 输入新值 → 再次扫描
3. 重复到只剩几个地址 → 开启功能

## 项目文件

```
cli.py           # 命令行入口（主要使用）
core/
  memory.py      # 内存读写 + 多类型扫描
  process.py     # 进程自动检测
cheats/
  engine.py      # 作弊逻辑
```

## 免责声明

仅供学习研究。使用风险自负。
