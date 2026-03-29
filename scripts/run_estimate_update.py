#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下午估值更新脚本
每天下午2:45运行，更新基金估值并推送通知
"""

import os
import sys
import json
from datetime import datetime

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy_engine import StrategyEngine
from wechat_notifier import WechatNotifier
from config_manager import ConfigManager

def main():
    """主函数"""
    print(f"=== 基金估值更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    try:
        # 初始化模块
        config_manager = ConfigManager()
        strategy_engine = StrategyEngine()
        notifier = WechatNotifier()
        
        # 执行估值更新
        result = strategy_engine.daily_estimate_update()
        
        # 计算当日收益
        total_info = strategy_engine.position_manager.get_all_positions()
        
        # 从历史数据获取昨日总价值（如果有）
        yesterday_value = 0
        history_file = "fund_history.json"
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                yesterday_value = history.get("last_real_value", total_info["total_value"])
            except Exception as e:
                print(f"读取历史数据失败: {e}")
        
        # 计算当日收益
        daily_profit = total_info["total_value"] - yesterday_value
        daily_return = daily_profit / yesterday_value if yesterday_value > 0 else 0
        
        # 推送每日报告
        if notifier.enabled:
            success = notifier.send_daily_report(
                total_value=total_info["total_value"],
                daily_profit=daily_profit,
                daily_return=daily_return,
                cumulative_profit=total_info["total_profit"],
                cumulative_return=total_info["total_profit_rate"],
                signals=result["signals"]
            )
            if success:
                print("✅ 微信通知发送成功")
            else:
                print("⚠️  微信通知发送失败")
        
        # 保存历史数据
        history_data = {
            "last_estimate_value": total_info["total_value"],
            "last_estimate_time": datetime.now().isoformat(),
            "last_real_value": yesterday_value
        }
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        
        # 执行交易信号
        execute_signals(strategy_engine, result["signals"], notifier)
        
        print("=== 估值更新完成 ===")
        print(f"总价值: ¥{total_info['total_value']:.2f}")
        print(f"当日收益: ¥{daily_profit:.2f} ({daily_return*100:.2f}%)")
        print(f"累计收益: ¥{total_info['total_profit']:.2f} ({total_info['total_profit_rate']*100:.2f}%)")
        print(f"建仓信号: {len(result['signals']['initial'])}")
        print(f"加仓信号: {len(result['signals']['add'])}")
        print(f"减仓信号: {len(result['signals']['remove'])}")
        
    except Exception as e:
        print(f"更新失败: {e}")
        # 发送错误通知
        notifier = WechatNotifier()
        notifier.send_error_message(f"估值更新失败", str(e))

def execute_signals(strategy_engine: StrategyEngine, signals: dict, notifier: WechatNotifier):
    """执行交易信号
    
    Args:
        strategy_engine: 策略引擎
        signals: 交易信号
        notifier: 微信通知器
    """
    # 执行建仓信号
    for signal in signals.get("initial", []):
        try:
            strategy_engine.execute_initial_position(signal)
            print(f"✅ 建仓: {signal['fund_name']} ({signal['fund_code']})")
            if notifier.enabled:
                notifier.notify_initial_position(
                    fund_code=signal["fund_code"],
                    fund_name=signal["fund_name"],
                    amount=signal["amount"],
                    nav=signal["nav"],
                    drawdown=signal["drawdown"]
                )
        except Exception as e:
            print(f"❌ 建仓失败 {signal['fund_code']}: {e}")
    
    # 执行加仓信号
    for signal in signals.get("add", []):
        try:
            strategy_engine.execute_add_position(signal)
            print(f"✅ 加仓: {signal['fund_name']} ({signal['fund_code']})")
            if notifier.enabled:
                notifier.notify_add_position(
                    fund_code=signal["fund_code"],
                    fund_name=signal["fund_name"],
                    amount=signal["amount"],
                    layers=signal["layers"],
                    nav=signal["nav"],
                    daily_change=signal["daily_change"]
                )
        except Exception as e:
            print(f"❌ 加仓失败 {signal['fund_code']}: {e}")
    
    # 执行减仓信号
    for signal in signals.get("remove", []):
        try:
            strategy_engine.execute_remove_position(signal)
            print(f"✅ 减仓: {signal['fund_name']} ({signal['fund_code']})")
            if notifier.enabled:
                notifier.notify_remove_position(
                    fund_code=signal["fund_code"],
                    fund_name=signal["fund_name"],
                    amount=signal["amount"],
                    reason=signal["reason"]
                )
        except Exception as e:
            print(f"❌ 减仓失败 {signal['fund_code']}: {e}")

if __name__ == "__main__":
    main()
