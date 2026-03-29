#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周度月度报告模块
生成周度和月度基金投资报告
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from position_manager import PositionManager
from wechat_notifier import WechatNotifier
from config_manager import ConfigManager

class ReportGenerator:
    """报告生成器类"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.position_manager = PositionManager()
        self.notifier = WechatNotifier()
        self.config_manager = ConfigManager()
        self.history_file = "fund_history.json"
        self.report_history_file = "fund_report_history.json"
    
    def _load_history(self) -> Dict:
        """加载历史数据
        
        Returns:
            历史数据
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载历史数据失败: {e}")
        return {}
    
    def _load_report_history(self) -> Dict:
        """加载报告历史数据
        
        Returns:
            报告历史数据
        """
        if os.path.exists(self.report_history_file):
            try:
                with open(self.report_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载报告历史数据失败: {e}")
        return {
            "weekly": [],
            "monthly": []
        }
    
    def _save_report_history(self, data: Dict):
        """保存报告历史数据
        
        Args:
            data: 报告历史数据
        """
        try:
            with open(self.report_history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存报告历史数据失败: {e}")
    
    def _calculate_weekly_profit(self) -> Dict:
        """计算周收益
        
        Returns:
            周收益数据
        """
        history = self._load_history()
        report_history = self._load_report_history()
        
        # 获取当前总价值
        total_info = self.position_manager.get_all_positions()
        current_value = total_info["total_value"]
        
        # 查找上周五的价值
        last_week_value = 0
        today = datetime.now()
        last_friday = today - timedelta(days=(today.weekday() + 2) % 7)
        
        # 从报告历史中查找上周五的数据
        for report in reversed(report_history["weekly"]):
            report_date = datetime.fromisoformat(report["date"])
            if report_date.date() <= last_friday.date():
                last_week_value = report["total_value"]
                break
        
        # 如果没有历史数据，使用当前价值
        if last_week_value == 0:
            last_week_value = current_value
        
        weekly_profit = current_value - last_week_value
        weekly_return = weekly_profit / last_week_value if last_week_value > 0 else 0
        
        return {
            "weekly_profit": weekly_profit,
            "weekly_return": weekly_return,
            "last_week_value": last_week_value,
            "current_value": current_value
        }
    
    def _calculate_monthly_profit(self) -> Dict:
        """计算月收益
        
        Returns:
            月收益数据
        """
        history = self._load_history()
        report_history = self._load_report_history()
        
        # 获取当前总价值
        total_info = self.position_manager.get_all_positions()
        current_value = total_info["total_value"]
        
        # 查找上月末的价值
        last_month_value = 0
        today = datetime.now()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        
        # 从报告历史中查找上月末的数据
        for report in reversed(report_history["monthly"]):
            report_date = datetime.fromisoformat(report["date"])
            if report_date.date() <= last_month_end.date():
                last_month_value = report["total_value"]
                break
        
        # 如果没有历史数据，使用当前价值
        if last_month_value == 0:
            last_month_value = current_value
        
        monthly_profit = current_value - last_month_value
        monthly_return = monthly_profit / last_month_value if last_month_value > 0 else 0
        
        return {
            "monthly_profit": monthly_profit,
            "monthly_return": monthly_return,
            "last_month_value": last_month_value,
            "current_value": current_value
        }
    
    def _calculate_quarterly_profit(self) -> Dict:
        """计算季度收益
        
        Returns:
            季度收益数据
        """
        history = self._load_history()
        report_history = self._load_report_history()
        
        # 获取当前总价值
        total_info = self.position_manager.get_all_positions()
        current_value = total_info["total_value"]
        
        # 查找上季度末的价值
        last_quarter_value = 0
        today = datetime.now()
        
        # 计算上季度末日期
        if today.month <= 3:
            last_quarter_end = today.replace(year=today.year-1, month=12, day=31)
        elif today.month <= 6:
            last_quarter_end = today.replace(month=3, day=31)
        elif today.month <= 9:
            last_quarter_end = today.replace(month=6, day=30)
        else:
            last_quarter_end = today.replace(month=9, day=30)
        
        # 从报告历史中查找上季度末的数据
        for report in reversed(report_history["monthly"]):
            report_date = datetime.fromisoformat(report["date"])
            if report_date.date() <= last_quarter_end.date():
                last_quarter_value = report["total_value"]
                break
        
        # 如果没有历史数据，使用当前价值
        if last_quarter_value == 0:
            last_quarter_value = current_value
        
        quarterly_profit = current_value - last_quarter_value
        quarterly_return = quarterly_profit / last_quarter_value if last_quarter_value > 0 else 0
        
        return {
            "quarterly_profit": quarterly_profit,
            "quarterly_return": quarterly_return,
            "last_quarter_value": last_quarter_value,
            "current_value": current_value
        }
    
    def _get_position_stats(self) -> Dict:
        """获取持仓统计
        
        Returns:
            持仓统计数据
        """
        total_info = self.position_manager.get_all_positions()
        positions = total_info["positions"]
        
        if not positions:
            return {
                "count": 0,
                "avg_return": 0,
                "max_return": 0,
                "min_return": 0,
                "initial_count": 0,
                "add_count": 0,
                "remove_count": 0
            }
        
        # 计算收益率统计
        returns = [p["profit_rate"] for p in positions]
        avg_return = sum(returns) / len(returns)
        max_return = max(returns) if returns else 0
        min_return = min(returns) if returns else 0
        
        # 计算交易次数
        initial_count = 0
        add_count = 0
        remove_count = 0
        
        for fund_code, position in self.position_manager.positions.items():
            for pos in position["positions"]:
                if pos["type"] == "initial":
                    initial_count += 1
                elif pos["type"] == "add":
                    add_count += 1
                elif pos["type"] == "remove":
                    remove_count += 1
        
        return {
            "count": len(positions),
            "avg_return": avg_return,
            "max_return": max_return,
            "min_return": min_return,
            "initial_count": initial_count,
            "add_count": add_count,
            "remove_count": remove_count
        }
    
    def generate_weekly_report(self) -> Dict:
        """生成周度报告
        
        Returns:
            周度报告数据
        """
        print("=== 生成周度报告 ===")
        
        # 计算周收益
        weekly_data = self._calculate_weekly_profit()
        
        # 计算月收益
        monthly_data = self._calculate_monthly_profit()
        
        # 获取持仓统计
        position_stats = self._get_position_stats()
        
        # 获取总收益
        total_info = self.position_manager.get_all_positions()
        total_profit = total_info["total_profit"]
        total_return = total_info["total_profit_rate"]
        
        # 生成报告数据
        report = {
            "date": datetime.now().isoformat(),
            "total_value": total_info["total_value"],
            "weekly_profit": weekly_data["weekly_profit"],
            "weekly_return": weekly_data["weekly_return"],
            "monthly_profit": monthly_data["monthly_profit"],
            "monthly_return": monthly_data["monthly_return"],
            "total_profit": total_profit,
            "total_return": total_return,
            "position_stats": position_stats
        }
        
        # 保存报告历史
        report_history = self._load_report_history()
        report_history["weekly"].append(report)
        # 只保留最近100条记录
        if len(report_history["weekly"]) > 100:
            report_history["weekly"] = report_history["weekly"][-100:]
        self._save_report_history(report_history)
        
        # 推送周度报告
        if self.notifier.enabled:
            success = self.notifier.send_weekly_report(
                weekly_profit=weekly_data["weekly_profit"],
                weekly_return=weekly_data["weekly_return"],
                monthly_profit=monthly_data["monthly_profit"],
                monthly_return=monthly_data["monthly_return"],
                total_profit=total_profit,
                total_return=total_return,
                position_stats=position_stats
            )
            if success:
                print("✅ 周度报告推送成功")
            else:
                print("⚠️  周度报告推送失败")
        
        print("=== 周度报告生成完成 ===")
        print(f"周收益: ¥{weekly_data['weekly_profit']:.2f} ({weekly_data['weekly_return']*100:.2f}%)")
        print(f"月收益: ¥{monthly_data['monthly_profit']:.2f} ({monthly_data['monthly_return']*100:.2f}%)")
        print(f"总收益: ¥{total_profit:.2f} ({total_return*100:.2f}%)")
        print(f"持仓基金数: {position_stats['count']}")
        
        return report
    
    def generate_monthly_report(self) -> Dict:
        """生成月度报告
        
        Returns:
            月度报告数据
        """
        print("=== 生成月度报告 ===")
        
        # 计算月收益
        monthly_data = self._calculate_monthly_profit()
        
        # 计算季度收益
        quarterly_data = self._calculate_quarterly_profit()
        
        # 获取持仓统计
        position_stats = self._get_position_stats()
        
        # 获取总收益
        total_info = self.position_manager.get_all_positions()
        total_profit = total_info["total_profit"]
        total_return = total_info["total_profit_rate"]
        
        # 生成报告数据
        report = {
            "date": datetime.now().isoformat(),
            "total_value": total_info["total_value"],
            "monthly_profit": monthly_data["monthly_profit"],
            "monthly_return": monthly_data["monthly_return"],
            "quarterly_profit": quarterly_data["quarterly_profit"],
            "quarterly_return": quarterly_data["quarterly_return"],
            "total_profit": total_profit,
            "total_return": total_return,
            "position_stats": position_stats
        }
        
        # 保存报告历史
        report_history = self._load_report_history()
        report_history["monthly"].append(report)
        # 只保留最近100条记录
        if len(report_history["monthly"]) > 100:
            report_history["monthly"] = report_history["monthly"][-100:]
        self._save_report_history(report_history)
        
        # 推送月度报告
        if self.notifier.enabled:
            success = self.notifier.send_monthly_report(
                monthly_profit=monthly_data["monthly_profit"],
                monthly_return=monthly_data["monthly_return"],
                quarterly_profit=quarterly_data["quarterly_profit"],
                quarterly_return=quarterly_data["quarterly_return"],
                total_profit=total_profit,
                total_return=total_return,
                position_stats=position_stats
            )
            if success:
                print("✅ 月度报告推送成功")
            else:
                print("⚠️  月度报告推送失败")
        
        print("=== 月度报告生成完成 ===")
        print(f"月收益: ¥{monthly_data['monthly_profit']:.2f} ({monthly_data['monthly_return']*100:.2f}%)")
        print(f"季度收益: ¥{quarterly_data['quarterly_profit']:.2f} ({quarterly_data['quarterly_return']*100:.2f}%)")
        print(f"总收益: ¥{total_profit:.2f} ({total_return*100:.2f}%)")
        print(f"持仓基金数: {position_stats['count']}")
        
        return report
    
    def export_report(self, report_type: str = "weekly", format: str = "json") -> str:
        """导出报告
        
        Args:
            report_type: 报告类型 (weekly, monthly)
            format: 导出格式 (json, csv)
        
        Returns:
            报告内容
        """
        report_history = self._load_report_history()
        reports = report_history.get(report_type, [])
        
        if not reports:
            return "无报告数据"
        
        if format == "json":
            return json.dumps(reports, ensure_ascii=False, indent=2)
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            if report_type == "weekly":
                writer.writerow(["日期", "总价值", "周收益", "周收益率", "月收益", "月收益率", "总收益", "总收益率", "持仓基金数"])
                for report in reports:
                    writer.writerow([
                        report["date"].split('T')[0],
                        f"{report['total_value']:.2f}",
                        f"{report['weekly_profit']:.2f}",
                        f"{report['weekly_return']*100:.2f}%",
                        f"{report['monthly_profit']:.2f}",
                        f"{report['monthly_return']*100:.2f}%",
                        f"{report['total_profit']:.2f}",
                        f"{report['total_return']*100:.2f}%",
                        report['position_stats']['count']
                    ])
            elif report_type == "monthly":
                writer.writerow(["日期", "总价值", "月收益", "月收益率", "季度收益", "季度收益率", "总收益", "总收益率", "持仓基金数"])
                for report in reports:
                    writer.writerow([
                        report["date"].split('T')[0],
                        f"{report['total_value']:.2f}",
                        f"{report['monthly_profit']:.2f}",
                        f"{report['monthly_return']*100:.2f}%",
                        f"{report['quarterly_profit']:.2f}",
                        f"{report['quarterly_return']*100:.2f}%",
                        f"{report['total_profit']:.2f}",
                        f"{report['total_return']*100:.2f}%",
                        report['position_stats']['count']
                    ])
            
            return output.getvalue()
        else:
            return "不支持的导出格式"

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="基金报告生成器")
    parser.add_argument("type", choices=["weekly", "monthly"], help="报告类型")
    parser.add_argument("--export", action="store_true", help="导出报告")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="导出格式")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    if args.type == "weekly":
        report = generator.generate_weekly_report()
    else:
        report = generator.generate_monthly_report()
    
    if args.export:
        output = generator.export_report(args.type, args.format)
        print(output)

if __name__ == "__main__":
    main()
