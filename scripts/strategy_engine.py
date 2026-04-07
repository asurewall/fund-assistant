#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略引擎模块
实现基金投资策略，包括建仓、加仓、减仓规则
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from wcwidth import wcswidth
from concurrent.futures import ThreadPoolExecutor, as_completed

from fund_fetcher import FundFetcher
from position_manager import PositionManager


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

class StrategyEngine:
    """策略引擎类"""
    
    def __init__(self, config_file: str = "fund_config.json"):
        """
        初始化策略引擎
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.fetcher = FundFetcher(apply_dedup=True)
        self.position_manager = PositionManager(config_file)
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "total_capital": 50000,
            "fund_count": 10,
            "drawdown_threshold": 0.20,
            "hold_days": 30,
            "low_fee_days": 7,
            "all_funds_count": 3000,
            "drawdown_cache_count": 800,
            "lookback_days": 90,
            "drawdown_max_workers": 30,
            "initial_position_layers": 4,
            "max_layers": 10,
            "max_per_sector": 2,
            "add_position": {
                "enabled": True,
                "max_total_layers": 10,
                "rules": [
                    [
                        {"min_return": -0.0085, "max_return": 0.005, "layers": 0.5},
                        {"min_return": -0.015, "max_return": -0.0085, "layers": 1},
                        {"min_return": -0.0225, "max_return": -0.015, "layers": 1.5},
                        {"min_return": -0.03, "max_return": -0.0225, "layers": 2},
                        {"min_return": -0.035, "max_return": -0.03, "layers": 2.5},
                        {"min_return": -0.04, "max_return": -0.035, "layers": 3},
                        {"min_return": -0.045, "max_return": -0.04, "layers": 3.5},
                        {"min_return": -1, "max_return": -0.045, "layers": 4}
                    ]
                ]
            },
            "stop_loss": {
                "enabled": True,
                "max_loss": -0.15
            },
            "remove_position": {
                "enabled": True,
                "rules": [
                    {"min_profit_rate": 0.15, "layers": "all"},
                    {"min_profit_rate": 0.12, "layers": 0.5},
                    {"min_profit_rate": 0.10, "layers": 0.5}
                ]
            }
        }
    
    def get_top_funds(self, limit: int = None) -> List[Dict]:
        """获取Top N基金
        
        Args:
            limit: 获取数量
        
        Returns:
            基金列表
        """
        if limit is None:
            limit = self.config.get("drawdown_cache_count", 800)
        
        return self.fetcher.get_top_funds(period_days=365, limit=limit)
    
    def calculate_drawdowns(self, funds: List[Dict], lookback_days: int = None) -> List[Dict]:
        """计算基金回撤率（优先从缓存读取）
        
        Args:
            funds: 基金列表
            lookback_days: 回溯天数（未使用，保留用于兼容）
    
        Returns:
            带回撤率的基金列表
        """
        # 尝试从缓存文件读取回撤率数据
        drawdown_cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fund_drawdowns.json")
        drawdown_map = {}
        
        if os.path.exists(drawdown_cache_file):
            try:
                with open(drawdown_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    for fund in cache_data.get("funds", []):
                        drawdown_map[fund["code"]] = {
                            "drawdown": fund.get("drawdown", 0),
                            "recovery_return": fund.get("recovery_return", 0),
                            "max_nav_date": fund.get("max_nav_date", "")
                        }
                print(f"从缓存读取了 {len(drawdown_map)} 只基金的回撤率数据")
            except Exception as e:
                print(f"读取回撤率缓存失败: {e}")
        
        funds_with_drawdown = []
        for fund in funds:
            fund_with_drawdown = fund.copy()
            fund_code = fund["code"]
            
            # 优先使用缓存数据
            if fund_code in drawdown_map:
                fund_with_drawdown["drawdown"] = drawdown_map[fund_code]["drawdown"]
                fund_with_drawdown["recovery_return"] = drawdown_map[fund_code]["recovery_return"]
                fund_with_drawdown["max_nav_date"] = drawdown_map[fund_code]["max_nav_date"]
            else:
                # 缓存中没有，使用默认值
                fund_with_drawdown["drawdown"] = 0
                fund_with_drawdown["recovery_return"] = 0
                fund_with_drawdown["max_nav_date"] = ""
            
            funds_with_drawdown.append(fund_with_drawdown)
        
        return funds_with_drawdown
    
    def _classify_sector(self, fund_name: str) -> str:
        """根据基金名称分类板块
        
        Args:
            fund_name: 基金名称
        
        Returns:
            板块名称
        """
        # 关键词 -> 板块映射（顺序敏感，长的先匹配）
        sector_rules = [
            (["黄金产业", "黄金股", "黄金ETF", "金银珠宝", "黄金"], "黄金"),
            (["有色金属", "有色", "矿业", "金属"], "有色金属"),
            (["半导体", "芯片", "集成电路", "电子"], "半导体/电子"),
            (["新能源", "光伏", "锂电", "储能", "碳中和", "绿色能源", "绿色电机"], "新能源"),
            (["医药", "医疗", "健康", "生物", "创新药"], "医药"),
            (["消费", "白酒", "食品"], "消费"),
            (["金融", "银行", "证券", "保险"], "金融"),
            (["军工", "国防", "航天", "高端装备", "装备制造"], "军工/高端装备"),
            (["制造", "工业", "先进制造", "智能制造"], "制造业"),
            (["科技", "信息产业", "信息技术", "人工智能", "AI"], "科技/TMT"),
            (["互联网", "数字经济", "数字经济"], "数字经济"),
            (["房地产", "地产", "基建", "建筑"], "地产/基建"),
            (["汽车", "新能源车", "智能汽车"], "汽车"),
            (["农业", "养殖", "种业"], "农业"),
            (["FOF", "优选", "领航", "配置"], "FOF/配置"),
        ]
        
        for keywords, sector in sector_rules:
            for kw in keywords:
                if kw in fund_name:
                    return sector
        
        return "其他"
    
    def _get_consecutive_chars(self, s: str) -> list:
        """获取字符串中的所有连续两个字的组合
        
        Args:
            s: 字符串
            
        Returns:
            连续两字列表
        """
        if len(s) < 2:
            return []
        return [s[i:i+2] for i in range(len(s) - 1)]
    
    def _are_sectors_similar(self, sector1: str, sector2: str) -> bool:
        """判断两个板块是否相似（有连续两个字相同）
        
        Args:
            sector1: 板块1
            sector2: 板块2
            
        Returns:
            是否相似
        """
        if not sector1 or not sector2:
            return False
        if sector1 == sector2:
            return True
        
        chars1 = self._get_consecutive_chars(sector1)
        chars2 = self._get_consecutive_chars(sector2)
        
        for c1 in chars1:
            if c1 in chars2:
                return True
        
        return False
    
    def _add_sector_count(self, sector_count: dict, sector: str):
        """添加板块计数（同时增加相似板块的计数）
        
        Args:
            sector_count: 板块计数字典
            sector: 要添加的板块
        """
        # 首先统计完全相同的板块
        sector_count[sector] = sector_count.get(sector, 0) + 1
        
        # 然后更新相似板块的计数
        for existing_sector in list(sector_count.keys()):
            if existing_sector != sector and self._are_sectors_similar(existing_sector, sector):
                sector_count[existing_sector] = sector_count.get(existing_sector, 0) + 1
    
    def _check_similar_sector_limit(self, sector_count: dict, sector: str, max_per_sector: int) -> bool:
        """检查相似板块是否已超过限制
        
        Args:
            sector_count: 板块计数字典
            sector: 要检查的板块
            max_per_sector: 每个板块最大数量
            
        Returns:
            是否超过限制
        """
        # 检查完全相同的板块
        if sector_count.get(sector, 0) >= max_per_sector:
            return True
        
        # 检查所有相似板块
        for existing_sector, count in sector_count.items():
            if self._are_sectors_similar(existing_sector, sector):
                if count >= max_per_sector:
                    return True
        
        return False
    
    def _calculate_add_layers(self, daily_change: float) -> float:
        """计算加仓层数（基于配置规则）

        Args:
            daily_change: 当日涨跌幅

        Returns:
            加仓层数
        """
        add_position_config = self.config.get("add_position", {})
        if not add_position_config.get("enabled", True):
            return 0

        rules = add_position_config.get("rules", [])
        if not rules:
            return 0

        for rule in rules:
            min_return = rule.get("min_return", -1)  # 较负的值（如 -0.025），区间下限
            max_return = rule.get("max_return", 0)   # 较正的值（如 -0.015），区间上限
            # 条件：min_return <= daily_change < max_return
            # 即：daily_change 在 [min_return, max_return) 区间内
            # 例如：-0.025 <= -0.02 < -0.015 为真
            if min_return <= daily_change < max_return:
                return rule.get("layers", 0)

        return 0
    
    def generate_initial_position_signals(self, funds: List[Dict]) -> List[Dict]:
        """生成建仓信号
        
        板块分散策略：同一板块最多2只基金，优先选回撤最深、近一年收益最高的
        
        Args:
            funds: 带回撤率的基金列表
        
        Returns:
            建仓信号列表
        """
        signals = []
        existing_codes = set(self.position_manager.positions.keys())
        
        # 统计已持仓板块（使用数据中的 sector 字段）
        sector_count = {}
        for code in existing_codes:
            pos = self.position_manager.positions.get(code, {})
            sector = pos.get("sector")
            if sector:
                self._add_sector_count(sector_count, sector)
        
        # 筛选回撤率大于阈值的基金
        eligible_funds = [f for f in funds if f.get("drawdown", 0) < -self.config["drawdown_threshold"]]

        # 并发获取所有符合条件基金的板块信息
        def fetch_sector(fund):
            sector = self.fetcher.get_fund_sector(fund.get("code", ""))
            if not sector:
                sector = self._classify_sector(fund.get("name", ""))
            fund["sector"] = sector
            return fund

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_sector, f): f for f in eligible_funds}
            for future in as_completed(futures):
                pass

        print(f"\n📋 符合条件的基金 ({len(eligible_funds)} 只，回撤 > {self.config['drawdown_threshold']:.0%}):")
        if eligible_funds:
            headers = ["代码", "名称", "板块", "1年收益", "回撤", "恢复涨幅"]
            col_widths = [10, 45, 10, 10, 10, 10]
            header_line = ""
            sep_line = ""
            for h, w in zip(headers, col_widths):
                header_line += cjk_ljust(h, w) + " "
                sep_line += "-" * w + " "
            print(header_line)
            print(sep_line)
            for f in sorted(eligible_funds, key=lambda x: x.get("drawdown", 0)):
                name = f.get("name", "")[:45]
                sector = f.get("sector", "")[:8]
                row = (
                    cjk_ljust(f.get("code", ""), col_widths[0]) + " " +
                    cjk_ljust(name, col_widths[1]) + " " +
                    cjk_ljust(sector, col_widths[2]) + " " +
                    cjk_rjust(f"{f.get('return_1y', 0):.2%}", col_widths[3]) + " " +
                    cjk_rjust(f"{f.get('drawdown', 0):.2%}", col_widths[4]) + " " +
                    cjk_rjust(f"{f.get('recovery_return', 0):.2%}", col_widths[5])
                )
                print(row)
        
        # 限制基金数量
        target_count = self.config["fund_count"] - len(existing_codes)
        if target_count <= 0:
            return signals
        
        # 每个板块最多2只
        max_per_sector = self.config.get("max_per_sector", 2)
        
        # 综合评分排序：回撤深度(40%) + 近一年收益(40%) + 恢复难度反向(20%)
        def score_fund(f):
            dd = abs(f.get("drawdown", 0))
            ret = f.get("return_1y", 0)
            rec = f.get("recovery_return", 0)
            # 回撤越深分越高，收益越高分越高，恢复需涨幅越低分越高
            return dd * 0.4 + ret * 0.4 + (1 - min(rec, 1)) * 0.2
        
        eligible_funds.sort(key=score_fund, reverse=True)
        
        selected_count = 0
        for fund in eligible_funds:
            if fund["code"] in existing_codes:
                continue
            if selected_count >= target_count:
                break
            
            # 使用之前获取并保存的板块信息
            sector = fund.get("sector")
            if not sector:
                sector = self.fetcher.get_fund_sector(fund["code"])
                if not sector:
                    sector = self._classify_sector(fund["name"])
            
            # 检查相似板块是否已超过限制
            if self._check_similar_sector_limit(sector_count, sector, max_per_sector):
                continue
            
            # 计算建仓金额
            single_fund_amount = self.config["total_capital"] / self.config["fund_count"]
            initial_amount = single_fund_amount * (self.config["initial_position_layers"] / 10)
            
            signal = {
                "type": "initial_position",
                "fund_code": fund["code"],
                "fund_name": fund["name"],
                "amount": initial_amount,
                "nav": fund["nav"],
                "drawdown": fund.get("drawdown", 0),
                "recovery_return": fund.get("recovery_return", 0),
                "sector": sector,
                "reason": f"回撤率 {abs(fund.get('drawdown', 0))*100:.1f}% 大于阈值 {self.config['drawdown_threshold']*100:.1f}%，板块: {sector}"
            }
            signals.append(signal)
            
            self._add_sector_count(sector_count, sector)
            selected_count += 1
        
        # 最终安全检查：确保没有已持仓的基金
        final_signals = []
        for sig in signals:
            if sig["fund_code"] not in self.position_manager.positions:
                final_signals.append(sig)
        
        return final_signals
    
    def generate_add_position_signals(self, daily_changes: Dict[str, float]) -> List[Dict]:
        """生成加仓信号

        Args:
            daily_changes: 基金当日涨跌幅

        Returns:
            加仓信号列表
        """
        signals = []
        for fund_code, daily_change in daily_changes.items():
            if fund_code not in self.position_manager.positions:
                continue
            position = self.position_manager.get_position_info(fund_code)
            # 检查是否达到最大层数
            if position["total_layers"] >= self.config["max_layers"]:
                continue
            
            # 检查建仓日期是否在加仓有效期内
            created_at = datetime.fromisoformat(position["created_at"])
            current_date = datetime.now()
            
            # 计算清仓日期（建仓后第hold_days天）
            clear_date = created_at + timedelta(days=self.config["hold_days"] - 1)  # 建仓当天算第1天
            
            # 计算加仓有效期
            start_date = created_at + timedelta(days=1)  # 建仓次日开始
            end_date = clear_date - timedelta(days=self.config["low_fee_days"] - 1)  # 清仓前low_fee_days - 1天
            
            # 检查是否在加仓有效期内
            if not (start_date <= current_date <= end_date):
                continue
            
            # 计算加仓层数
            layers = self._calculate_add_layers(daily_change)
            if layers > 0:
                # 计算最多能加多少层（不能超过最大层数）
                max_add_layers = self.config["max_layers"] - position["total_layers"]
                if max_add_layers <= 0:
                    continue
                # 取较小值
                layers = min(layers, max_add_layers)
                # 计算加仓金额
                single_layer_amount = self.config["total_capital"] / self.config["fund_count"] / 10
                add_amount = single_layer_amount * layers
                
                signal = {
                    "type": "add_position",
                    "fund_code": fund_code,
                    "fund_name": position["name"],
                    "sector": self.position_manager.positions.get(fund_code, {}).get("sector", ""),
                    "amount": add_amount,
                    "layers": layers,
                    "nav": position["current_nav"],
                    "daily_change": daily_change,
                    "current_layers": position["total_layers"],
                    "reason": f"当日跌幅 {daily_change*100:.1f}%，加仓 {layers} 层"
                }
                signals.append(signal)
                print(f"  {fund_code}: ✅ 生成加仓信号（{daily_change*100:.2f}%, {layers}层）")
            else:
                print(f"  {fund_code}: 涨幅{daily_change*100:.2f}%未达到加仓条件")

        print(f"=== 共生成 {len(signals)} 个加仓信号 ===\n")
        return signals
    
    def generate_remove_position_signals(self) -> List[Dict]:
        """生成减仓信号

        Returns:
            减仓信号列表
        """
        signals = []
        stop_loss_config = self.config.get("stop_loss", {})
        remove_config = self.config.get("remove_position", {})
        rules = remove_config.get("rules", [])

        for fund_code, position in self.position_manager.positions.items():
            info = self.position_manager.get_position_info(fund_code)

            # 止损检查
            if stop_loss_config.get("enabled", False):
                max_loss = stop_loss_config.get("max_loss", -0.15)
                if info["profit_rate"] <= max_loss:
                    signal = {
                        "type": "remove_position",
                        "fund_code": fund_code,
                        "fund_name": info["name"],
                        "sector": self.position_manager.positions.get(fund_code, {}).get("sector", ""),
                        "layers": "all",
                        "amount": info["total_amount"],
                        "reason": f"收益率 {info['profit_rate']*100:.1f}%，触发止损"
                    }
                    signals.append(signal)
                    continue

            # 检查持仓天数
            if info["hold_days"] >= self.config["hold_days"]:
                signal = {
                    "type": "remove_position",
                    "fund_code": fund_code,
                    "fund_name": info["name"],
                    "sector": self.position_manager.positions.get(fund_code, {}).get("sector", ""),
                    "layers": "all",
                    "amount": info["total_amount"],
                    "reason": f"持仓天数 {info['hold_days']} 天，达到持有期限"
                }
                signals.append(signal)
                continue

            # 检查收益率规则（按配置顺序匹配）
            profit_rate = info["profit_rate"]
            for rule in rules:
                min_profit = rule.get("min_profit_rate", 0)
                layers = rule.get("layers", "all")
                if profit_rate >= min_profit:
                    amount = info["total_amount"] * (layers if layers != "all" else 1)
                    signal = {
                        "type": "remove_position",
                        "fund_code": fund_code,
                        "fund_name": info["name"],
                        "sector": self.position_manager.positions.get(fund_code, {}).get("sector", ""),
                        "layers": layers,
                        "amount": amount,
                        "reason": f"收益率 {profit_rate*100:.1f}%，触发减仓规则"
                    }
                    signals.append(signal)
                    break

        return signals
    
    def execute_initial_position(self, signal: Dict):
        """执行建仓
        
        Args:
            signal: 建仓信号
        """
        self.position_manager.add_initial_position(
            fund_code=signal["fund_code"],
            amount=signal["amount"],
            nav=signal["nav"],
            fund_name=signal["fund_name"],
            sector=signal.get("sector")
        )
    
    def execute_add_position(self, signal: Dict):
        """执行加仓
        
        Args:
            signal: 加仓信号
        """
        self.position_manager.add_position(
            fund_code=signal["fund_code"],
            layers=signal["layers"],
            nav=signal["nav"]
        )
    
    def execute_remove_position(self, signal: Dict):
        """执行减仓
        
        Args:
            signal: 减仓信号
        """
        self.position_manager.remove_position(
            fund_code=signal["fund_code"],
            amount=signal["amount"]
        )
    
    def daily_estimate_update(self) -> Dict:
        """每日估值更新（盘中执行，只生成信号，不更新持仓）
        
        功能：
        1. 获取Top 1000基金，生成建仓信号
        2. 获取持仓基金估值，生成加仓/减仓信号
        3. 只生成信号，不实际更新持仓（晚上nav-update才更新）
        
        Returns:
            更新结果，包含所有信号
        """
        # 获取Top 1000基金（用于建仓信号）
        top_funds = self.get_top_funds()
        
        # 计算回撤率
        funds_with_drawdown = self.calculate_drawdowns(top_funds);
        
        # 生成建仓信号
        initial_signals = self.generate_initial_position_signals(funds_with_drawdown)
        
        # 获取持仓基金的当日实时估值涨跌幅（只获取持仓的基金，减少API调用）
        daily_changes = {}
        position_valuations = []  # 存储持仓估值信息用于打印
        
        print("\n📋 持仓基金估值详情")
        headers = ["基金代码", "基金名称", "估值", "当日涨幅", "持仓市值"]
        col_widths = [10, 45, 10, 10, 12]
        
        header_line = ""
        sep_line = ""
        for h, w in zip(headers, col_widths):
            header_line += cjk_ljust(h, w) + " "
            sep_line += "-" * w + " "
        print(header_line)
        print(sep_line)
        
        for fund_code in self.position_manager.positions.keys():
            try:
                position_info = self.position_manager.get_position_info(fund_code)
                valuation = self.fetcher.get_valuation(fund_code)
                if valuation and "estimated_return" in valuation:
                    daily_changes[fund_code] = valuation["estimated_return"]
                    
                    # 记录估值信息（不更新持仓）
                    position_valuations.append({
                        "code": fund_code,
                        "name": position_info.get("name", "")[:20],
                        "nav": valuation.get("nav", 0),
                        "estimated_nav": valuation.get("estimated_nav", 0),
                        "estimated_return": valuation["estimated_return"],
                        "value": position_info.get("current_value", 0)
                    })
                    
                    # 打印单只基金信息
                    name = position_info.get("name", "")[:28]
                    row = (
                        cjk_ljust(fund_code, col_widths[0]) + " " +
                        cjk_ljust(name, col_widths[1]) + " " +
                        cjk_rjust(f"{valuation.get('estimated_nav', 0):.4f}", col_widths[2]) + " " +
                        cjk_rjust(f"{valuation['estimated_return']:.2%}", col_widths[3]) + " " +
                        cjk_rjust(f"{position_info.get('current_value', 0):,.2f}", col_widths[4])
                    )
                    print(row)
                else:
                    daily_changes[fund_code] = 0.0
                    print(f"基金 {fund_code} 获取估值失败")
            except Exception as e:
                print(f"获取基金 {fund_code} 估值失败: {e}")
                daily_changes[fund_code] = 0.0
        # 计算当日预估总收益
        total_info = self.position_manager.get_all_positions()
        total_value = total_info["total_value"]
        daily_profit = sum(
            self.position_manager.get_position_info(code).get("current_value", 0) * daily_changes.get(code, 0) 
            for code in self.position_manager.positions.keys()
        )
        daily_return = daily_profit / total_value if total_value > 0 else 0
        
        print(sep_line)
        total_row = (
            cjk_ljust("合计", col_widths[0]) + " " +
            cjk_ljust("", col_widths[1]) + " " +
            cjk_rjust("", col_widths[2]) + " " +
            cjk_rjust(f"{daily_return:.2%}", col_widths[3]) + " " +
            cjk_rjust(f"{total_value:,.2f}", col_widths[4])
        )
        print(total_row)
        print(f"\n💰 当日预估收益: ¥{daily_profit:,.2f} ({daily_return:.2%})")
        
        # 生成加仓信号
        add_signals = self.generate_add_position_signals(daily_changes)
        
        # 生成减仓信号
        remove_signals = self.generate_remove_position_signals()
        
        # 获取总体持仓信息
        total_info = self.position_manager.get_all_positions()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_value": total_info["total_value"],
            "total_profit": total_info["total_profit"],
            "total_profit_rate": total_info["total_profit_rate"],
            "daily_profit": daily_profit,
            "daily_return": daily_return,
            "signals": {
                "initial": initial_signals,
                "add": add_signals,
                "remove": remove_signals
            },
            "position_count": len(total_info["positions"])
        }
    
    def daily_real_update(self, signals: Dict = None) -> Dict:
        """每日真实净值更新（晚上执行）

        功能：
        1. 更新持仓真实净值
        2. 计算当日收益
        3. 不执行任何交易（加减仓只在盘中update时提示）

        Args:
            signals: 当天生成的信号（已废弃，晚上不执行交易）

        Returns:
            更新结果
        """
        print("\n📋 持仓基金净值详情")
        print(f"{'基金代码':<10} {'基金名称':<22} {'净值':>10} {'当日涨幅':>10} {'当前市值':>14} {'累计收益':>12}")
        print("-" * 95)

        # 更新持仓真实净值（直接从API获取最新净值，不使用缓存）
        daily_changes = {}
        for fund_code, position in self.position_manager.positions.items():
            try:
                nav_data = self.fetcher.get_current_nav(fund_code)
                if nav_data and "nav" in nav_data:
                    # 记录涨幅
                    daily_changes[fund_code] = nav_data.get("daily_return", 0)
                    # 更新持仓净值
                    self.position_manager.update_nav(fund_code, nav_data["nav"])

                    # 打印单只基金信息
                    profit = position.get("profit", 0)
                    profit_rate = position.get("profit_rate", 0)
                    print(f"{fund_code:<10} {position.get('name', '')[:20]:<22} "
                          f"{nav_data['nav']:>10.4f} "
                          f"{daily_changes[fund_code]:>9.2%} "
                          f"{position.get('current_value', 0):>14,.2f} "
                          f"{profit:>10,.2f} ({profit_rate:>+.2%})")
                else:
                    print(f"基金 {fund_code} 获取净值失败")
            except Exception as e:
                print(f"更新基金 {fund_code} 净值失败: {e}")

        # 计算当日收益
        daily_profit = 0
        for code, p in self.position_manager.positions.items():
            total_amount = p.get("total_amount", 0)
            current_nav = p.get("current_nav", 0)
            average_nav = p.get("average_nav", 0)
            if average_nav > 0:
                current_value = total_amount * (current_nav / average_nav)
            else:
                current_value = 0
            daily_profit += current_value * daily_changes.get(code, 0)

        # 获取总体持仓信息
        total_info = self.position_manager.get_all_positions()
        daily_return = daily_profit / total_info["total_value"] if total_info["total_value"] > 0 else 0

        print("-" * 95)
        print(f"{'合计':<10} {'':<22} {'':>10} {daily_return:>9.2%} {total_info['total_value']:>14,.2f} "
              f"{total_info['total_profit']:>10,.2f} ({total_info['total_profit_rate']:>+.2%})")
        print(f"\n💰 当日收益: ¥{daily_profit:,.2f} ({daily_return:.2%})")

        return {
            "timestamp": datetime.now().isoformat(),
            "total_value": total_info["total_value"],
            "total_profit": total_info["total_profit"],
            "total_profit_rate": total_info["total_profit_rate"],
            "daily_profit": daily_profit,
            "daily_return": daily_return,
            "position_count": len(total_info["positions"])
        }
    
    def get_strategy_summary(self) -> Dict:
        """获取策略摘要
        
        Returns:
            策略摘要
        """
        total_info = self.position_manager.get_all_positions()
        
        return {
            "config": self.config,
            "total_investment": total_info["total_cost"],
            "current_value": total_info["total_value"],
            "total_profit": total_info["total_profit"],
            "total_profit_rate": total_info["total_profit_rate"],
            "position_count": len(total_info["positions"]),
            "last_updated": datetime.now().isoformat()
        }
