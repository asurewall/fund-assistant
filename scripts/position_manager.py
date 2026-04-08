#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓管理模块
管理基金持仓、建仓、加仓、减仓操作
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class PositionManager:
    """持仓管理类"""

    def __init__(self, config_file: str = "fund_config.json"):
        """
        初始化持仓管理器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        self.positions_file = os.path.join(assets_dir, "fund_positions.json")
        self.config = self._load_config()
        self.positions = self._load_positions()

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
            "initial_position_layers": 4,
            "max_layers": 10
        }

    def _load_positions(self) -> Dict:
        """加载持仓数据"""
        if os.path.exists(self.positions_file):
            with open(self.positions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "funds" not in data:
                    # 旧格式迁移
                    funds = {}
                    summary = {}
                    for key, value in data.items():
                        if key == "summary":
                            summary = value if isinstance(value, dict) else {}
                        elif key == "daily_profits":
                            summary["daily_profits"] = value if isinstance(value, dict) else {}
                        else:
                            funds[key] = value
                    data = {"funds": funds, "summary": summary}
                else:
                    # 清理 funds 中的非基金数据
                    funds = data.get("funds", {})
                    summary = data.get("summary", {})
                    keys_to_remove = []
                    for key in funds.keys():
                        if key in ("summary", "daily_profits") or not isinstance(funds[key], dict):
                            keys_to_remove.append(key)
                        elif "total_amount" not in funds[key]:
                            # 不是基金数据（基金必须有 total_amount 字段）
                            keys_to_remove.append(key)
                    for key in keys_to_remove:
                        del funds[key]
                    data["funds"] = funds
                    if "summary" not in data:
                        data["summary"] = {}
                return data
        return {"funds": {}, "summary": {}}

    def _save_positions(self):
        """保存持仓数据"""
        with open(self.positions_file, 'w', encoding='utf-8') as f:
            json.dump(self.positions, f, ensure_ascii=False, indent=2)

    @property
    def funds(self) -> Dict:
        """获取基金数据字典的快捷方式"""
        return self.positions.get("funds", {})

    def update_daily_profit(self, daily_profit: float, daily_return: float = 0, daily_changes: Optional[Dict[str, float]] = None, total_profit: float = 0, total_profit_rate: float = 0):
        """更新每日收益记录

        Args:
            daily_profit: 当日收益金额（总收益）
            daily_return: 当日收益率
            daily_changes: 每个基金的当日涨跌幅字典 {fund_code: daily_return}
            total_profit: 累计总收益
            total_profit_rate: 累计总收益率
        """
        today = datetime.now().strftime("%Y-%m-%d")
        if "daily_profits" not in self.positions["summary"]:
            self.positions["summary"]["daily_profits"] = {}
        self.positions["summary"]["daily_profits"][today] = {
            "profit": daily_profit,
            "return": daily_return
        }
        
        # 更新总收益和总收益率到 summary
        self.positions["summary"]["total_profit"] = total_profit
        self.positions["summary"]["total_profit_rate"] = total_profit_rate

        if daily_changes is None:
            daily_changes = {}

        for fund_code, position in self.funds.items():
            if "daily_profits" not in position:
                position["daily_profits"] = {}

            current_value = position.get("total_amount", 0) * (position.get("current_nav", 0) / position.get("average_nav", 1)) if position.get("average_nav", 0) > 0 else 0
            daily_change = daily_changes.get(fund_code, 0)
            fund_daily_profit = current_value * daily_change
            fund_daily_return = daily_change

            position["daily_profits"][today] = {
                "profit": fund_daily_profit,
                "return": fund_daily_return
            }
        self._save_positions()

    def get_daily_profits(self) -> Dict:
        """获取每日收益记录

        Returns:
            每日收益字典，日期为key
        """
        return self.positions.get("summary", {}).get("daily_profits", {})

    def initialize_positions(self, fund_codes: List[str]):
        """初始化持仓

        Args:
            fund_codes: 基金代码列表
        """
        self.positions = {"funds": {}, "summary": {}}
        for code in fund_codes:
            self.positions["funds"][code] = {
                "code": code,
                "name": "",
                "sector": None,
                "total_amount": 0,
                "total_layers": 0,
                "average_nav": 0,
                "current_nav": 0,
                "profit": 0,
                "profit_rate": 0,
                "positions": [],
                "created_at": datetime.now().isoformat(),
                "last_update": datetime.now().isoformat()
            }
        self._save_positions()

    def add_initial_position(self, fund_code: str, amount: float, nav: float, fund_name: str = "", sector: Optional[str] = None):
        """添加建仓

        Args:
            fund_code: 基金代码
            amount: 建仓金额
            nav: 建仓净值
            fund_name: 基金名称
            sector: 板块信息
        """
        if fund_code not in self.funds:
            self.positions["funds"][fund_code] = {
                "code": fund_code,
                "name": fund_name,
                "sector": sector,
                "total_amount": 0,
                "total_layers": 0,
                "average_nav": 0,
                "current_nav": nav,
                "profit": 0,
                "profit_rate": 0,
                "positions": [],
                "created_at": datetime.now().isoformat(),
                "last_update": datetime.now().isoformat()
            }

        position = {
            "type": "initial",
            "amount": amount,
            "nav": nav,
            "shares": amount / nav,
            "date": datetime.now().isoformat()
        }

        self.positions["funds"][fund_code]["positions"].append(position)
        self.positions["funds"][fund_code]["total_amount"] += amount
        self.positions["funds"][fund_code]["total_layers"] += self.config.get("initial_position_layers", 4)
        self.positions["funds"][fund_code]["average_nav"] = self._calculate_average_nav(fund_code)
        self.positions["funds"][fund_code]["last_update"] = datetime.now().isoformat()

        if fund_name:
            self.positions["funds"][fund_code]["name"] = fund_name
        if sector:
            self.positions["funds"][fund_code]["sector"] = sector

        self.positions["funds"][fund_code]["current_nav"] = nav
        self._calculate_profit(fund_code)
        self._save_positions()

    def add_position(self, fund_code: str, layers: float, nav: float):
        """添加加仓

        Args:
            fund_code: 基金代码
            layers: 加仓层数
            nav: 加仓净值
        """
        if fund_code not in self.funds:
            raise ValueError(f"基金 {fund_code} 未持仓")

        if self.positions["funds"][fund_code]["total_layers"] + layers > self.config.get("max_layers", 10):
            raise ValueError(f"基金 {fund_code} 已达到最大持仓层数")

        created_at = datetime.fromisoformat(self.positions["funds"][fund_code]["created_at"])
        current_date = datetime.now()

        clear_date = created_at + timedelta(days=self.config.get("hold_days", 30) - 1)

        start_date = created_at
        end_date = clear_date - timedelta(days=self.config.get("low_fee_days", 7) - 1)

        if not (start_date <= current_date <= end_date):
            raise ValueError(f"基金 {fund_code} 不在加仓有效期内")

        single_layer_amount = self.config["total_capital"] / self.config["fund_count"] / 10
        amount = single_layer_amount * layers

        position = {
            "type": "add",
            "amount": amount,
            "nav": nav,
            "shares": amount / nav,
            "layers": layers,
            "date": datetime.now().isoformat()
        }

        self.positions["funds"][fund_code]["positions"].append(position)
        self.positions["funds"][fund_code]["total_amount"] += amount
        self.positions["funds"][fund_code]["total_layers"] += layers
        self.positions["funds"][fund_code]["average_nav"] = self._calculate_average_nav(fund_code)
        self.positions["funds"][fund_code]["last_update"] = datetime.now().isoformat()
        self._calculate_profit(fund_code)

        self._save_positions()

    def remove_position(self, fund_code: str, amount: Optional[float] = None):
        """减仓

        Args:
            fund_code: 基金代码
            amount: 减仓金额，None表示全部卖出
        """
        if fund_code not in self.funds:
            raise ValueError(f"基金 {fund_code} 未持仓")

        if amount is None:
            amount = self.positions["funds"][fund_code]["total_amount"]

        position = {
            "type": "remove",
            "amount": amount,
            "nav": self.positions["funds"][fund_code]["current_nav"],
            "shares": amount / self.positions["funds"][fund_code]["current_nav"],
            "date": datetime.now().isoformat()
        }

        self.positions["funds"][fund_code]["positions"].append(position)

        original_amount = self.positions["funds"][fund_code]["total_amount"]
        reduce_ratio = amount / original_amount if original_amount > 0 else 0
        reduce_layers = self.positions["funds"][fund_code]["total_layers"] * reduce_ratio

        self.positions["funds"][fund_code]["total_amount"] -= amount
        self.positions["funds"][fund_code]["total_layers"] -= reduce_layers

        if self.positions["funds"][fund_code]["total_amount"] <= 0:
            del self.positions["funds"][fund_code]
        else:
            self.positions["funds"][fund_code]["average_nav"] = self._calculate_average_nav(fund_code)
            self.positions["funds"][fund_code]["last_update"] = datetime.now().isoformat()

        self._save_positions()

    def update_nav(self, fund_code: str, nav: float):
        """更新基金净值

        Args:
            fund_code: 基金代码
            nav: 当前净值
        """
        if fund_code in self.funds:
            self.positions["funds"][fund_code]["current_nav"] = nav
            self._calculate_profit(fund_code)
            self.positions["funds"][fund_code]["last_update"] = datetime.now().isoformat()
            self._save_positions()

    def _calculate_average_nav(self, fund_code: str) -> float:
        """计算平均成本净值

        Args:
            fund_code: 基金代码

        Returns:
            平均成本净值
        """
        total_shares = 0
        total_cost = 0

        for pos in self.positions["funds"][fund_code]["positions"]:
            if pos["type"] in ["initial", "add"]:
                total_shares += pos["shares"]
                total_cost += pos["amount"]
            elif pos["type"] == "remove":
                total_shares -= pos["shares"]
                total_cost -= pos["amount"]

        avg_nav = total_cost / total_shares if total_shares > 0 else 0
        return round(avg_nav, 4)

    def _calculate_profit(self, fund_code: str):
        """计算收益

        Args:
            fund_code: 基金代码
        """
        position = self.positions["funds"][fund_code]
        if position["current_nav"] > 0 and position["average_nav"] > 0:
            current_value = position["total_amount"] * (position["current_nav"] / position["average_nav"])
            position["profit"] = current_value - position["total_amount"]
            position["profit_rate"] = position["profit"] / position["total_amount"]
        else:
            position["profit"] = 0
            position["profit_rate"] = 0

    def get_position_info(self, fund_code: str) -> Dict:
        """获取持仓信息

        Args:
            fund_code: 基金代码

        Returns:
            持仓信息
        """
        if fund_code not in self.funds:
            raise ValueError(f"基金 {fund_code} 未持仓")

        position = self.positions["funds"][fund_code].copy()
        current_value = position["total_amount"] * (position["current_nav"] / position["average_nav"]) if position["average_nav"] > 0 else 0
        position["current_value"] = current_value

        created_at = datetime.fromisoformat(position["created_at"])
        position["hold_days"] = (datetime.now() - created_at).days

        return position

    def get_all_positions(self) -> List[Dict]:
        """获取所有持仓

        Returns:
            持仓列表
        """
        positions = []
        total_value = 0
        total_cost = 0

        for fund_code, position in self.funds.items():
            info = self.get_position_info(fund_code)
            positions.append(info)
            total_value += info["current_value"]
            total_cost += info["total_amount"]

        total_profit = total_value - total_cost
        total_profit_rate = total_profit / total_cost if total_cost > 0 else 0

        return {
            "positions": positions,
            "total_cost": total_cost,
            "total_value": total_value,
            "total_profit": total_profit,
            "total_profit_rate": total_profit_rate
        }

    def export_report(self, format: str = "json") -> str:
        """导出持仓报告

        Args:
            format: 导出格式 (json, csv)

        Returns:
            报告内容
        """
        if format == "json":
            return json.dumps(self.get_all_positions(), ensure_ascii=False, indent=2)
        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["基金代码", "基金名称", "持仓金额", "当前价值", "收益", "收益率", "持仓天数", "平均成本", "当前净值"])

            for fund_code, position in self.funds.items():
                info = self.get_position_info(fund_code)
                writer.writerow([
                    info["code"],
                    info["name"],
                    f"{info['total_amount']:.2f}",
                    f"{info['current_value']:.2f}",
                    f"{info['profit']:.2f}",
                    f"{info['profit_rate']:.2%}",
                    info["hold_days"],
                    f"{info['average_nav']:.4f}",
                    f"{info['current_nav']:.4f}"
                ])

            total_info = self.get_all_positions()
            writer.writerow(["总计", "",
                           f"{total_info['total_cost']:.2f}",
                           f"{total_info['total_value']:.2f}",
                           f"{total_info['total_profit']:.2f}",
                           f"{total_info['total_profit_rate']:.2%}",
                           "", "", ""])

            return output.getvalue()
        else:
            raise ValueError(f"不支持的导出格式: {format}")
