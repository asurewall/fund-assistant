#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信推送模块
通过 OpenClaw message 工具推送消息到微信
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

class WechatNotifier:
    """微信通知类"""
    
    def __init__(self, config_file: str = "fund_config.json"):
        """
        初始化微信通知器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.enabled = self.config.get("wechat", {}).get("enabled", True)
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "wechat": {
                "enabled": True
            }
        }
    
    def _send_message(self, message: str, msgtype: str = "text") -> bool:
        """发送消息到微信（通过 OpenClaw message 工具）
        
        Args:
            message: 消息内容
            msgtype: 消息类型（text 或 markdown）
        
        Returns:
            是否发送成功
        """
        if not self.enabled:
            return False
        
        try:
            # 直接调用 OpenClaw 的 message 工具
            # 通过 Python 的 message 模块
            from openclaw.tools import message as msg_tool
            
            result = msg_tool.send(
                channel="wechat",
                message=message
            )
            
            return result.get("success", False)
        except ImportError:
            # 如果 OpenClaw 模块不可用，尝试通过 HTTP 调用
            try:
                import requests
                # 假设 OpenClaw 的 message API 在本地运行
                response = requests.post(
                    "http://localhost:8080/api/message/send",
                    json={
                        "channel": "wechat",
                        "message": message
                    },
                    timeout=10
                )
                return response.status_code == 200
            except Exception as e:
                print(f"发送微信消息失败: {e}")
                return False
        except Exception as e:
            print(f"发送微信消息失败: {e}")
            return False
    
    def notify_initial_position(self, fund_code: str, fund_name: str, amount: float, nav: float, drawdown: float):
        """推送建仓提醒
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            amount: 建仓金额
            nav: 建仓净值
            drawdown: 回撤率
        """
        message = f"""【基金建仓提醒】\n\n" 
                  f"📊 **基金信息**\n" 
                  f"- 基金代码: {fund_code}\n" 
                  f"- 基金名称: {fund_name}\n" 
                  f"- 建仓金额: ¥{amount:.2f}\n" 
                  f"- 建仓净值: {nav:.4f}\n" 
                  f"- 回撤率: {drawdown*100:.2f}%\n\n" 
                  f"⏰ **建仓时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n" 
                  f"💡 **策略建议**\n" 
                  f"该基金回撤率已达到建仓阈值，建议立即建仓。"""
        
        return self._send_message(message, "markdown")
    
    def notify_add_position(self, fund_code: str, fund_name: str, amount: float, layers: float, nav: float, daily_change: float):
        """推送加仓提醒
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            amount: 加仓金额
            layers: 加仓层数
            nav: 加仓净值
            daily_change: 当日涨跌幅
        """
        message = f"""【基金加仓提醒】\n\n" 
                  f"📊 **基金信息**\n" 
                  f"- 基金代码: {fund_code}\n" 
                  f"- 基金名称: {fund_name}\n" 
                  f"- 加仓金额: ¥{amount:.2f}\n" 
                  f"- 加仓层数: {layers} 层\n" 
                  f"- 加仓净值: {nav:.4f}\n" 
                  f"- 当日涨跌幅: {daily_change*100:.2f}%\n\n" 
                  f"⏰ **加仓时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n" 
                  f"💡 **策略建议**\n" 
                  f"基金今日下跌，符合加仓条件，建议立即加仓。"""
        
        return self._send_message(message, "markdown")
    
    def notify_remove_position(self, fund_code: str, fund_name: str, amount: float, reason: str):
        """推送减仓提醒
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            amount: 减仓金额
            reason: 减仓原因
        """
        message = f"""【基金减仓提醒】\n\n" 
                  f"📊 **基金信息**\n" 
                  f"- 基金代码: {fund_code}\n" 
                  f"- 基金名称: {fund_name}\n" 
                  f"- 减仓金额: ¥{amount:.2f}\n\n" 
                  f"⏰ **减仓时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n" 
                  f"💡 **减仓原因**\n" 
                  f"{reason}\n\n" 
                  f"建议立即卖出该基金。"""
        
        return self._send_message(message, "markdown")
    
    def send_daily_report(self, total_value: float, daily_profit: float, daily_return: float, 
                         cumulative_profit: float, cumulative_return: float, signals: Dict):
        """推送每日报告
        
        Args:
            total_value: 总价值
            daily_profit: 当日收益
            daily_return: 当日收益率
            cumulative_profit: 累计收益
            cumulative_return: 累计收益率
            signals: 交易信号
        """
        # 构建信号部分
        signal_text = ""
        if signals.get("initial"):
            signal_text += f"\n📈 **建仓信号** ({len(signals['initial'])}个):\n"
            for signal in signals['initial'][:3]:  # 只显示前3个
                signal_text += f"- {signal['fund_name']} ({signal['fund_code']}): ¥{signal['amount']:.2f}\n"
            if len(signals['initial']) > 3:
                signal_text += f"- 等{len(signals['initial']) - 3}个基金\n"
        
        if signals.get("add"):
            signal_text += f"\n📈 **加仓信号** ({len(signals['add'])}个):\n"
            for signal in signals['add'][:3]:  # 只显示前3个
                signal_text += f"- {signal['fund_name']} ({signal['fund_code']}): ¥{signal['amount']:.2f}\n"
            if len(signals['add']) > 3:
                signal_text += f"- 等{len(signals['add']) - 3}个基金\n"
        
        if signals.get("remove"):
            signal_text += f"\n📉 **减仓信号** ({len(signals['remove'])}个):\n"
            for signal in signals['remove'][:3]:  # 只显示前3个
                signal_text += f"- {signal['fund_name']} ({signal['fund_code']}): ¥{signal['amount']:.2f}\n"
            if len(signals['remove']) > 3:
                signal_text += f"- 等{len(signals['remove']) - 3}个基金\n"
        
        message = f"""【基金每日报告】\n\n" 
                  f"📊 **账户概览**\n" 
                  f"- 总价值: ¥{total_value:.2f}\n" 
                  f"- 当日收益: ¥{daily_profit:.2f} ({daily_return*100:.2f}%)\n" 
                  f"- 累计收益: ¥{cumulative_profit:.2f} ({cumulative_return*100:.2f}%)\n\n" 
                  f"{signal_text}\n" 
                  f"⏰ **报告时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return self._send_message(message, "markdown")
    
    def send_weekly_report(self, weekly_profit: float, weekly_return: float, 
                          monthly_profit: float, monthly_return: float, 
                          total_profit: float, total_return: float, 
                          position_stats: Dict):
        """推送周度报告
        
        Args:
            weekly_profit: 周收益
            weekly_return: 周收益率
            monthly_profit: 月收益
            monthly_return: 月收益率
            total_profit: 总收益
            total_return: 总收益率
            position_stats: 持仓统计
        """
        message = f"""【基金周度报告】\n\n" 
                  f"📊 **收益概览**\n" 
                  f"- 周收益: ¥{weekly_profit:.2f} ({weekly_return*100:.2f}%)\n" 
                  f"- 月收益: ¥{monthly_profit:.2f} ({monthly_return*100:.2f}%)\n" 
                  f"- 总收益: ¥{total_profit:.2f} ({total_return*100:.2f}%)\n\n" 
                  f"📈 **持仓统计**\n" 
                  f"- 持仓基金数: {position_stats.get('count', 0)}\n" 
                  f"- 平均收益率: {position_stats.get('avg_return', 0)*100:.2f}%\n" 
                  f"- 最高收益率: {position_stats.get('max_return', 0)*100:.2f}%\n" 
                  f"- 最低收益率: {position_stats.get('min_return', 0)*100:.2f}%\n\n" 
                  f"⏰ **报告时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return self._send_message(message, "markdown")
    
    def send_monthly_report(self, monthly_profit: float, monthly_return: float, 
                           quarterly_profit: float, quarterly_return: float, 
                           total_profit: float, total_return: float, 
                           position_stats: Dict):
        """推送月度报告
        
        Args:
            monthly_profit: 月收益
            monthly_return: 月收益率
            quarterly_profit: 季度收益
            quarterly_return: 季度收益率
            total_profit: 总收益
            total_return: 总收益率
            position_stats: 持仓统计
        """
        message = f"""【基金月度报告】\n\n" 
                  f"📊 **收益概览**\n" 
                  f"- 月收益: ¥{monthly_profit:.2f} ({monthly_return*100:.2f}%)\n" 
                  f"- 季度收益: ¥{quarterly_profit:.2f} ({quarterly_return*100:.2f}%)\n" 
                  f"- 总收益: ¥{total_profit:.2f} ({total_return*100:.2f}%)\n\n" 
                  f"📈 **持仓统计**\n" 
                  f"- 持仓基金数: {position_stats.get('count', 0)}\n" 
                  f"- 平均收益率: {position_stats.get('avg_return', 0)*100:.2f}%\n" 
                  f"- 最高收益率: {position_stats.get('max_return', 0)*100:.2f}%\n" 
                  f"- 最低收益率: {position_stats.get('min_return', 0)*100:.2f}%\n\n" 
                  f"🔄 **交易统计**\n" 
                  f"- 建仓次数: {position_stats.get('initial_count', 0)}\n" 
                  f"- 加仓次数: {position_stats.get('add_count', 0)}\n" 
                  f"- 减仓次数: {position_stats.get('remove_count', 0)}\n\n" 
                  f"⏰ **报告时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return self._send_message(message, "markdown")
    
    def send_error_message(self, error: str, details: str = ""):
        """推送错误消息
        
        Args:
            error: 错误信息
            details: 详细信息
        """
        message = f"""【基金助手错误】\n\n" 
                  f"❌ **错误信息**\n" 
                  f"{error}\n\n" 
                  f"📋 **详细信息**\n" 
                  f"{details}\n\n" 
                  f"⏰ **错误时间**\n" 
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return self._send_message(message, "markdown")
