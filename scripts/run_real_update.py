#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
晚上真实净值更新脚本
每天晚上10:00运行，更新基金真实净值并推送通知
"""

import os
import sys
import json
from datetime import datetime

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy_engine import StrategyEngine
from config_manager import ConfigManager

def main():
    """主函数"""
    print(f"=== 基金真实净值更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    try:
        # 初始化模块
        config_manager = ConfigManager()
        strategy_engine = StrategyEngine()
        
        # 执行真实净值更新
        result = strategy_engine.daily_real_update()
        
        # 获取最新持仓信息
        total_info = strategy_engine.position_manager.get_all_positions()
        
        # 从历史数据获取昨日总价值
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
        
        # 保存历史数据
        history_data = {
            "last_real_value": total_info["total_value"],
            "last_real_time": datetime.now().isoformat(),
            "last_estimate_value": total_info["total_value"]
        }
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        
        # 执行减仓信号
        execute_remove_signals(strategy_engine, result["signals"])
        
        print("=== 真实净值更新完成 ===")
        print(f"总价值: ¥{total_info['total_value']:.2f}")
        print(f"当日收益: ¥{daily_profit:.2f} ({daily_return*100:.2f}%)")
        print(f"累计收益: ¥{total_info['total_profit']:.2f} ({total_info['total_profit_rate']*100:.2f}%)")
        print(f"减仓信号: {len(result['signals'].get('remove', []))}")
        
    except Exception as e:
        print(f"更新失败: {e}")

def execute_remove_signals(strategy_engine: StrategyEngine, signals: dict):
    """执行减仓信号
    
    Args:
        strategy_engine: 策略引擎
        signals: 交易信号
    """
    # 执行减仓信号
    for signal in signals.get("remove", []):
        try:
            strategy_engine.execute_remove_position(signal)
            print(f"✅ 减仓: {signal['fund_name']} ({signal['fund_code']})")
        except Exception as e:
            print(f"❌ 减仓失败 {signal['fund_code']}: {e}")

if __name__ == "__main__":
    main()
