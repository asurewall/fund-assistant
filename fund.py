#!/usr/bin/env python3
"""基金助手统一入口 CLI"""
import json
import os
import sys
from tabulate import tabulate
from wcwidth import wcswidth

def cjk_ljust(text, width):
    """中英文混合字符串左对齐（按显示宽度计算）"""
    text = text or ""
    display_width = wcswidth(text)
    if display_width < 0:
        display_width = len(text)
    padding = width - display_width
    return text + " " * padding

def cjk_rjust(text, width):
    """中英文混合字符串右对齐（按显示宽度计算）"""
    text = text or ""
    display_width = wcswidth(text)
    if display_width < 0:
        display_width = len(text)
    padding = width - display_width
    return " " * padding + text

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL_DIR)
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

from scripts.fund_fetcher import FundFetcher
from scripts.position_manager import PositionManager
from scripts.strategy_engine import StrategyEngine

CONFIG_FILE = os.path.join(SKILL_DIR, "assets", "fund_config.json")
POSITIONS_FILE = os.path.join(SKILL_DIR, "assets", "fund_positions.json")
SIGNALS_FILE = os.path.join(SKILL_DIR, "assets", "fund_signals.json")
ASSETS_DIR = os.path.join(SKILL_DIR, "assets")

# --- Sector classification ---
SECTOR_RULES = [
    (["黄金产业", "黄金股", "黄金ETF", "金银珠宝", "黄金"], "黄金"),
    (["有色金属", "有色", "矿业", "金属"], "有色金属"),
    (["半导体", "芯片", "集成电路"], "半导体"),
    (["新能源", "光伏", "锂电", "储能", "绿色能源"], "新能源"),
    (["医药", "医疗", "健康", "生物"], "医药"),
    (["消费", "白酒", "食品"], "消费"),
    (["军工", "国防", "航天", "高端装备"], "军工/高端装备"),
    (["制造", "工业", "先进制造"], "制造业"),
    (["科技", "信息产业", "信息技术"], "科技"),
    (["FOF", "优选", "领航", "配置"], "FOF/配置"),
]

def classify(name):
    for kws, sector in SECTOR_RULES:
        for kw in kws:
            if kw in name:
                return sector
    return "其他"

def score_fund(f):
    dd = abs(f.get("drawdown", 0))
    ret = f.get("return_1y", 0)
    rec = f.get("recovery_return", 0)
    return dd * 0.4 + ret * 0.4 + (1 - min(rec, 1)) * 0.2

def load_config():
    if not os.path.exists(CONFIG_FILE):
        template_file = os.path.join(ASSETS_DIR, "config_template.json")
        if os.path.exists(template_file):
            print(f"配置文件不存在，从模板创建默认配置...")
            with open(template_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            os.makedirs(ASSETS_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ 已创建默认配置文件: {CONFIG_FILE}")
        else:
            raise FileNotFoundError(f"配置文件不存在: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_drawdown_cache():
    with open(DRAWDOWN_CACHE, "r", encoding="utf-8") as f:
        return json.load(f).get("funds", [])

def cmd_status():
    """Print current positions"""
    if not os.path.exists(POSITIONS_FILE):
        print("No positions. Run 'python fund.py reset' to initialize.")
        return
    pm = PositionManager(config_file=CONFIG_FILE)
    info = pm.get_all_positions()
    positions = info["positions"]
    if not positions:
        print("No positions.")
        return

    fetcher = FundFetcher()
    total_pending = 0

    print(f"总成本: {info['total_cost']:,.0f} | 市值: {info['total_value']:,.0f} | 收益: {info['total_profit']:,.0f} ({info['total_profit_rate']:+.2%}) | {len(positions)}只\n")

    headers = ["#", "代码", "名称", "板块", "成本", "市值", "待确认", "收益", "层", "天"]
    col_widths = [3, 10, 45, 8, 12, 10, 12, 10, 5, 5]
    aligns = ["center", "left", "left", "left", "right", "right", "right", "right", "center", "center"]

    header_line = ""
    sep_line = ""
    for h, w, a in zip(headers, col_widths, aligns):
        if a == "right":
            header_line += cjk_rjust(h, w) + " "
            sep_line += "-" * w + " "
        else:
            header_line += cjk_ljust(h, w) + " "
            sep_line += "-" * w + " "
    print(header_line)
    print(sep_line)

    for i, p in enumerate(sorted(positions, key=lambda x: -x["total_amount"]), 1):
        name = p["name"][:30]
        sector = classify(p["name"])[:4]
        cost = p["total_amount"]
        days = p.get("hold_days", 0)
        layers = p["total_layers"]

        try:
            valuation = fetcher.get_valuation(p["code"])
            if valuation and "estimated_nav" in valuation and valuation.get("nav", 0) > 0:
                estimated_nav = valuation["estimated_nav"]
                current_nav = p.get("current_nav", estimated_nav)
                shares = cost / current_nav if current_nav > 0 else cost / estimated_nav
                pending = shares * estimated_nav
            else:
                pending = cost
        except:
            pending = cost

        pnl = pending - cost
        pnl_rate = pnl / cost if cost > 0 else 0
        total_pending += pending

        row = []
        row.append(cjk_rjust(str(i), col_widths[0]))
        row.append(cjk_ljust(p["code"], col_widths[1]))
        row.append(cjk_ljust(name, col_widths[2]))
        row.append(cjk_ljust(sector, col_widths[3]))
        row.append(cjk_rjust(f"{cost:,.0f}", col_widths[4]))
        row.append(cjk_rjust(f"{p.get('current_value', 0):,.0f}", col_widths[5]))
        row.append(cjk_rjust(f"{pending:,.0f}", col_widths[6]))
        row.append(cjk_rjust(f"{pnl:>+,.0f}", col_widths[7]))
        row.append(cjk_ljust(str(layers), col_widths[8]))
        row.append(cjk_ljust(str(days), col_widths[9]))
        print(" ".join(row))

    print(f"\n待确认总额: {total_pending:,.0f}")

def cmd_update():
    """下午估值更新（盘中执行，只生成信号，不更新持仓）"""
    from datetime import datetime
    
    print("=" * 60)
    print("下午估值更新（只生成信号，不更新持仓）")
    print("=" * 60)
    
    # 初始化策略引擎
    strategy = StrategyEngine(config_file=CONFIG_FILE)
    
    # 执行估值更新和策略信号生成
    result = strategy.daily_estimate_update()
    
    # 打印结果
    print("\n📊 持仓概况")
    print(f"  总价值: ¥{result['total_value']:,.2f}")
    print(f"  累计收益: ¥{result['total_profit']:,.2f} ({result['total_profit_rate']:.2%})")
    print(f"  持仓数量: {result['position_count']} 只")
    
    print("\n📈 策略信号（仅供参考）")
    signals = result['signals']
    print(f"  建仓信号: {len(signals['initial'])} 个")
    print(f"  加仓信号: {len(signals['add'])} 个")
    print(f"  减仓信号: {len(signals['remove'])} 个")
    
    # 打印详细信号
    if signals['initial']:
        print("\n  【建仓信号详情】")
        for sig in signals['initial']:
            print(f"    + {sig['fund_code']} {sig.get('fund_name', '')}: 回撤 {sig.get('drawdown', 0):.2%}")
    
    if signals['add']:
        print("\n  【加仓信号详情】")
        for sig in signals['add']:
            print(f"    + {sig['fund_code']}: 当前层数 {sig.get('current_layers', 0)}, 建议加仓 {sig.get('layers', 0)} 层")
    
    if signals['remove']:
        print("\n  【减仓信号详情】")
        for sig in signals['remove']:
            print(f"    - {sig['fund_code']}: {sig.get('reason', '')}")

    # 保存信号到文件，供 nav-update 使用
    from datetime import datetime
    signal_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "signals": signals
    }
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(signal_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("估值更新完成（加减仓信号已保存）")
    print("=" * 60)

def cmd_report():
    """Generate text report"""
    pm = PositionManager(config_file=CONFIG_FILE)
    info = pm.get_all_positions()
    if not info["positions"]:
        print("No positions.")
        return
    print(json.dumps(info, ensure_ascii=False, indent=2))

def cmd_reset():
    """Clear positions and re-select from drawdown cache"""
    config = load_config()
    funds = load_drawdown_cache()
    
    threshold = config["drawdown_threshold"]
    eligible = [f for f in funds if f.get("drawdown", 0) < -threshold]
    eligible.sort(key=score_fund, reverse=True)
    
    max_per = config.get("max_per_sector", 2)
    fund_count = config["fund_count"]
    sector_count = {}
    selected = []
    
    for f in eligible:
        if len(selected) >= fund_count:
            break
        sector = classify(f.get("name", ""))
        if sector_count.get(sector, 0) >= max_per:
            continue
        selected.append(f)
        sector_count[sector] = sector_count.get(sector, 0) + 1
    
    print(f"Selected {len(selected)} funds across {len(sector_count)} sectors:")
    print(f"{'#':>3} {'Code':<8} {'Name':<26} {'Sector':<12} {'1Y':>8} {'DD':>8}")
    print("-" * 75)
    for i, f in enumerate(selected, 1):
        name = f.get("name", "")[:24]
        sector = classify(f.get("name", ""))
        print(f"{i:>3} {f['code']:<8} {name:<26} {sector:<12} {f.get('return_1y',0):>8.2%} {f.get('drawdown',0):>8.2%}")
    
    # Clear and rebuild positions
    fund_codes = [f["code"] for f in selected]
    pm = PositionManager(config_file=CONFIG_FILE)
    pm.initialize_positions(fund_codes)
    fetcher = FundFetcher()
    amt = config["total_capital"] / config["fund_count"] * (config["initial_position_layers"] / 10)
    
    print(f"\nInitializing positions with real-time valuation...")
    for f in selected:
        fund_code = f["code"]
        fund_name = f.get("name", "")
        
        # 使用估值接口获取实时估值来建仓，保持数据一致性
        try:
            valuation = fetcher.get_valuation(fund_code)
            if valuation and "estimated_nav" in valuation:
                nav = valuation["estimated_nav"]  # 使用实时估值
            else:
                nav = f.get("nav", 0)  # 回退到缓存数据
        except Exception as e:
            print(f"  Warning: Failed to get valuation for {fund_code}, using cached nav")
            nav = f.get("nav", 0)
        
        pm.add_initial_position(fund_code, amt, nav, fund_name)
    
    print(f"\nDone. {len(selected)} funds, {amt*len(selected):,.0f} CNY invested.")

def cmd_valuation(args):
    """Query single fund valuation"""
    code = None
    for i, a in enumerate(args):
        if a == "--code" and i + 1 < len(args):
            code = args[i + 1]
    if not code:
        print("Usage: python fund.py valuation --code <fund_code>")
        return
    fetcher = FundFetcher()
    v = fetcher.get_valuation(code)
    if v:
        print(f"Name: {v.get('name','')}")
        print(f"NAV: {v.get('nav',0):.4f} ({v.get('nav_date','')})")
        print(f"Est NAV: {v.get('estimated_nav',0):.4f}")
        print(f"Est Change: {v.get('estimated_return',0):.2%}")
        print(f"Est Time: {v.get('estimated_time','')}")
    else:
        print(f"No valuation data for {code}")

def cmd_nav_update():
    """晚上真实净值更新（更新净值和收益，并执行当天信号交易）"""
    from scripts.strategy_engine import StrategyEngine

    print("=" * 60)
    print("晚上真实净值更新")
    print("=" * 60)
    print()

    strategy = StrategyEngine(config_file=CONFIG_FILE)
    pm = strategy.position_manager

    # 读取当天的信号文件
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            signal_data = json.load(f)
        signals = signal_data.get("signals", {})
        signal_date = signal_data.get("date", "")
    else:
        signals = {"initial": [], "add": [], "remove": []}
        signal_date = ""

    positions_before = list(pm.positions.keys())
    print(f"当前持仓: {len(positions_before)} 只")

    add_signals = signals.get("add", [])
    remove_signals = signals.get("remove", [])

    if add_signals or remove_signals:
        print(f"\n📋 待执行交易 (信号日期: {signal_date}):")
        total_add_amount = 0
        total_remove_amount = 0

        if add_signals:
            print(f"\n  【加仓】{len(add_signals)} 笔:")
            for sig in add_signals:
                fund_code = sig['fund_code']
                layers = sig.get('layers', 0)
                nav_data = strategy.fetcher.get_current_nav(fund_code)
                nav = nav_data.get("nav", 1.0) if nav_data else 1.0
                amount_per_layer = strategy.position_manager.config.get("total_capital", 400000) / 10
                amount = layers * amount_per_layer
                total_add_amount += amount
                fund_name = nav_data.get("name", "") if nav_data else ""
                print(f"    + {fund_code} {fund_name}: +{layers}层 @ {nav:.4f} = ¥{amount:,.0f}")

        if remove_signals:
            print(f"\n  【减仓】{len(remove_signals)} 笔:")
            for sig in remove_signals:
                fund_code = sig['fund_code']
                if fund_code in pm.positions:
                    pos = pm.positions[fund_code]
                    amount = pos.get("total_amount", 0)
                    total_remove_amount += amount
                    fund_name = pos.get("name", "")
                    print(f"    - {fund_code} {fund_name}: 全部卖出 = ¥{amount:,.0f}")

        print(f"\n  资金变动: -¥{total_add_amount:,.0f} (加仓) / +¥{total_remove_amount:,.0f} (减仓)")

        print("\n是否执行以上交易? (y/n): ", end="")
        try:
            confirm = input().strip().lower()
        except EOFError:
            confirm = "y"

        if confirm == "y":
            # 执行加仓
            for sig in add_signals:
                try:
                    fund_code = sig["fund_code"]
                    layers = sig.get("layers", 0)
                    if fund_code not in pm.positions:
                        print(f"  ⚠ {fund_code} 不在持仓中，跳过")
                        continue
                    # 获取当前净值
                    nav_data = strategy.fetcher.get_current_nav(fund_code)
                    nav = nav_data.get("nav", 1.0) if nav_data else 1.0
                    pm.add_position(fund_code, layers, nav)
                    print(f"  ✅ {fund_code} 加仓 {layers} 层 @ {nav:.4f}")
                except Exception as e:
                    print(f"  ❌ {sig['fund_code']} 加仓失败: {e}")

            # 执行减仓
            for sig in remove_signals:
                try:
                    fund_code = sig["fund_code"]
                    layers = sig.get("layers", "all")
                    if fund_code not in pm.positions:
                        print(f"  ⚠ {fund_code} 不在持仓中，跳过")
                        continue
                    if layers == "all":
                        pm.remove_position(fund_code)
                        print(f"  ✅ {fund_code} 全部卖出")
                    else:
                        total_amount = pm.positions[fund_code]["total_amount"]
                        amount = total_amount * layers
                        pm.remove_position(fund_code, amount=amount)
                        print(f"  ✅ {fund_code} 卖出 {layers*100:.0f}% (¥{amount:,.0f})")
                except Exception as e:
                    print(f"  ❌ {sig['fund_code']} 减仓失败: {e}")
        else:
            print("  取消执行交易")

    # 执行净值更新
    result = strategy.daily_real_update()

    # 删除信号文件
    if os.path.exists(SIGNALS_FILE):
        os.remove(SIGNALS_FILE)

    # 打印汇总
    positions_after = list(pm.positions.keys())
    print(f"\n📊 持仓汇总")
    print(f"  总价值: ¥{result['total_value']:,.2f}")
    print(f"  当日收益: ¥{result.get('daily_profit', 0):,.2f} ({result.get('daily_return', 0):.2%})")
    print(f"  累计收益: ¥{result['total_profit']:,.2f} ({result['total_profit_rate']:.2%})")
    print(f"  持仓数量: {result['position_count']} 只")
    print(f"  持仓变化: {len(positions_before)} -> {len(positions_after)}")

    print("\n" + "=" * 60)
    print("净值更新完成")
    print("=" * 60)

def cmd_trade(args):
    """手动添加交易信号

    用法:
        python fund.py trade add 002207 1    # 添加加仓信号
        python fund.py trade remove 002207   # 添加减仓信号
        python fund.py trade list           # 查看当前信号
        python fund.py trade clear           # 清除所有信号
    """
    if not args:
        print("用法: python fund.py trade <add|remove|list|clear> [基金代码] [层数]")
        return

    subcmd = args[0]

    # 读取现有信号
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            signal_data = json.load(f)
        signals = signal_data.get("signals", {"initial": [], "add": [], "remove": []})
    else:
        signals = {"initial": [], "add": [], "remove": []}

    if subcmd == "list":
        print("📋 当前信号:")
        print(f"  建仓: {len(signals['initial'])} 个")
        print(f"  加仓: {len(signals['add'])} 个")
        for s in signals['add']:
            print(f"    + {s['fund_code']}: {s.get('layers', 0)}层")
        print(f"  减仓: {len(signals['remove'])} 个")
        for s in signals['remove']:
            print(f"    - {s['fund_code']}: {s.get('reason', '')[:30]}")
        return

    if subcmd == "clear":
        if os.path.exists(SIGNALS_FILE):
            os.remove(SIGNALS_FILE)
        print("已清除所有信号")
        return

    if len(args) < 2:
        print("错误: 缺少基金代码")
        return

    fund_code = args[1]

    if subcmd == "add":
        layers = int(args[2]) if len(args) > 2 else 1
        pm = PositionManager(config_file=CONFIG_FILE)
        if fund_code not in pm.positions:
            print(f"错误: {fund_code} 不在持仓中")
            return
        current_layers = pm.positions[fund_code].get("total_layers", 0)
        signals["add"].append({
            "fund_code": fund_code,
            "layers": layers,
            "current_layers": current_layers,
            "reason": f"手动添加加仓 {layers} 层"
        })
        print(f"✅ 已添加加仓信号: {fund_code} +{layers}层")

    elif subcmd == "remove":
        pm = PositionManager(config_file=CONFIG_FILE)
        if fund_code not in pm.positions:
            print(f"错误: {fund_code} 不在持仓中")
            return
        signals["remove"].append({
            "fund_code": fund_code,
            "reason": "手动添加减仓"
        })
        print(f"✅ 已添加减仓信号: {fund_code}")

    else:
        print(f"未知子命令: {subcmd}")
        return

    # 保存信号
    from datetime import datetime
    signal_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "signals": signals
    }
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(signal_data, f, ensure_ascii=False, indent=2)


def cmd_config_update():
    """更新配置文件和缓存数据

    更新内容：
    - assets/fund_drawdowns.json（基金回撤率数据）
    - assets/all_funds.json（基金列表数据）
    """
    from scripts.fetch_all_funds import fetch_all_funds
    from scripts.generate_drawdown_data import generate_drawdown_data

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    all_funds_count = config.get("all_funds_count", 3000)
    drawdown_cache_count = config.get("drawdown_cache_count", 800)
    all_funds_cache = os.path.join(ASSETS_DIR, "all_funds.json")
    drawdown_cache = os.path.join(ASSETS_DIR, "fund_drawdowns.json")

    print("=" * 60)
    print("配置更新")
    print("=" * 60)

    print(f"\n📊 更新基金列表缓存（强制从API获取，{all_funds_count}只）...")
    if os.path.exists(all_funds_cache):
        os.remove(all_funds_cache)
    try:
        funds = fetch_all_funds(all_funds_count=all_funds_count)
        print(f"✅ 基金列表缓存更新完成（{len(funds)} 只）")
    except Exception as e:
        print(f"❌ 基金列表缓存更新失败: {e}")

    print(f"\n📊 更新基金回撤率数据（强制从API获取，{drawdown_cache_count}只）...")
    if os.path.exists(drawdown_cache):
        os.remove(drawdown_cache)
    try:
        generate_drawdown_data(limit=drawdown_cache_count)
        print("✅ 回撤率数据更新完成")
    except Exception as e:
        print(f"❌ 回撤率数据更新失败: {e}")

    print("\n" + "=" * 60)
    print("配置更新完成")
    print("=" * 60)


def cmd_init():
    """引导用户初始化配置"""
    print("=" * 60)
    print("基金助手初始化")
    print("=" * 60)
    print("\n请设置以下配置项（直接回车使用默认值）：\n")

    config = {}

    print("【基础配置】")
    config["total_capital"] = ask_number("总资金", 50000, 10000, 10000000)
    config["fund_count"] = ask_number("基金数量", 10, 1, 50)
    config["drawdown_threshold"] = ask_float("建仓回撤阈值", 0.20, 0.01, 0.50, suffix="%", scale=0.01)
    config["hold_days"] = ask_number("持有天数", 30, 1, 365)
    config["low_fee_days"] = ask_number("低费率天数", 7, 0, 30)

    print("\n【缓存配置】")
    config["all_funds_count"] = ask_number("基金列表缓存数量", 3000, 100, 10000)
    config["drawdown_cache_count"] = ask_number("回撤率缓存数量", 800, 100, 10000)

    print("\n【建仓配置】")
    config["max_per_sector"] = ask_number("同板块最多几只", 2, 1, 10)
    config["initial_position_layers"] = ask_number("建仓层数", 4, 1, 10)
    config["max_layers"] = ask_number("单只基金最大层数", 10, 1, 20)

    print("\n【加仓规则】")
    config["add_position"] = {
        "enabled": True,
        "max_total_layers": ask_number("最大总层数", 10, 1, 20)
    }

    print("\n【止损规则】")
    config["stop_loss"] = {
        "enabled": True,
        "max_loss": ask_float("最大亏损", -0.15, -0.50, 0, suffix="%", scale=0.01)
    }

    print("\n【微信通知】")
    wechat_enabled = ask_yes_no("启用微信通知", False)
    config["wechat"] = {
        "enabled": wechat_enabled,
        "webhook_url": ""
    }
    if wechat_enabled:
        webhook = input("  企业微信机器人 Webhook URL: ").strip()
        config["wechat"]["webhook_url"] = webhook

    config["schedule"] = {
        "estimate_update": "45 14 * * *",
        "real_update": "0 22 * * *",
        "weekly_report": "0 10 * * 6",
        "monthly_report": "0 10 1 * *"
    }

    save_init_config(config)

    print("\n" + "=" * 60)
    print("✅ 初始化完成！配置文件已保存到 assets/fund_config.json")
    print("=" * 60)


def ask_number(prompt, default, min_val, max_val):
    """询问用户输入数字"""
    while True:
        try:
            val = input(f"  {prompt} [{default}]: ").strip()
            if not val:
                return default
            val = int(val)
            if min_val <= val <= max_val:
                return val
            print(f"    请输入 {min_val} ~ {max_val} 之间的数字")
        except ValueError:
            print(f"    请输入有效数字")


def ask_float(prompt, default, min_val, max_val, suffix="", scale=1):
    """询问用户输入浮点数"""
    while True:
        try:
            val = input(f"  {prompt} [{default*100 if suffix == '%' else default}]: ").strip()
            if not val:
                return default
            val = float(val)
            if suffix == "%":
                val = val * scale
            if min_val <= val <= max_val:
                return val
            print(f"    请输入有效范围内的数字")
        except ValueError:
            print(f"    请输入有效数字")


def ask_yes_no(prompt, default):
    """询问用户是否"""
    while True:
        val = input(f"  {prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        if not val:
            return default
        if val in ["y", "yes", "是"]:
            return True
        if val in ["n", "no", "否"]:
            return False
        print("    请输入 y 或 n")


def save_init_config(config):
    """保存初始化配置"""
    assets_dir = ASSETS_DIR
    os.makedirs(assets_dir, exist_ok=True)
    config_file = os.path.join(assets_dir, "fund_config.json")
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python fund.py <status|update|nav-update|report|reset|trade|valuation|config-update>")
        print("\n首次运行会自动从模板创建默认配置")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status()
    elif cmd == "update":
        cmd_update()
    elif cmd == "nav-update":
        cmd_nav_update()
    elif cmd == "report":
        cmd_report()
    elif cmd == "reset":
        cmd_reset()
    elif cmd == "trade":
        cmd_trade(sys.argv[2:])
    elif cmd == "valuation":
        cmd_valuation(sys.argv[2:])
    elif cmd == "config-update":
        cmd_config_update()
    else:
        print(f"Unknown command: {cmd}")
        print("Available: status, update, nav-update, report, reset, trade, valuation, config-update")

if __name__ == "__main__":
    main()
