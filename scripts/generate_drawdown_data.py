#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算基金回撤率并保存到JSON文件
"""

import sys
import os
import json
from datetime import datetime
from fund_fetcher import FundFetcher

def generate_drawdown_data(limit=800):
    """计算基金回撤率并保存到JSON文件"""
    fetcher = FundFetcher(apply_dedup=True)
    
    print("开始获取基金数据...")
    
    # 从JSON文件或API获取基金列表
    funds = fetcher.get_top_funds(period_days=365, limit=limit)
    
    print(f"成功获取 {len(funds)} 只基金，正在计算回撤率...")
    
    # 计算每只基金的回撤率
    drawdown_data = []
    for fund in funds:
        try:
            drawdown = fetcher.calculate_drawdown(fund['code'])
            fund_with_drawdown = {
                'code': fund['code'],
                'name': fund['name'],
                'return_1y': fund['return_1y'],
                'nav': fund['nav'],
                'drawdown': drawdown['drawdown'],
                'recovery_return': drawdown['recovery_return'],
                'max_nav': drawdown['max_nav'],
                'max_nav_date': drawdown['max_nav_date'],
                'current_nav': drawdown['current_nav'],
                'current_nav_date': drawdown['current_nav_date'],
                'start_date': drawdown['start_date'],
                'end_date': drawdown['end_date']
            }
            drawdown_data.append(fund_with_drawdown)
        except Exception as e:
            print(f"计算基金 {fund['code']} 回撤率失败: {e}")
            continue
    
    # 添加更新时间
    data = {
        'update_time': datetime.now().isoformat(),
        'total': len(drawdown_data),
        'funds': drawdown_data
    }
    
    # 保存到JSON文件
    output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'fund_drawdowns.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"回撤率数据已保存到: {output_file}")
    print(f"更新时间: {data['update_time']}")
    print(f"成功计算 {len(drawdown_data)} 只基金的回撤率")
    
    return drawdown_data

def load_drawdowns_from_json():
    """从JSON文件中加载回撤率数据"""
    json_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'fund_drawdowns.json')
    
    if not os.path.exists(json_file):
        print("错误: fund_drawdowns.json 文件不存在，请先运行 generate_drawdown_data.py")
        return None
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"从文件加载成功: {data['total']} 只基金的回撤率数据")
        print(f"更新时间: {data['update_time']}")
        
        # 检查数据是否超过1天
        update_time = datetime.fromisoformat(data['update_time'])
        current_time = datetime.now()
        time_diff = current_time - update_time
        
        if time_diff.days > 0:
            print(f"警告: 数据已过期 {time_diff.days} 天，请运行 generate_drawdown_data.py 更新")
        
        return data
    except Exception as e:
        print(f"错误: {e}")
        return None

if __name__ == "__main__":
    # 默认计算Top 800基金的回撤率
    limit = 800
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    
    generate_drawdown_data(limit)
