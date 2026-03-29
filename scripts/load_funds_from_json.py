#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从JSON文件中读取基金数据
"""

import sys
import os
import json
from datetime import datetime

def load_funds_from_json():
    """从JSON文件中加载基金数据"""
    json_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'all_funds.json')
    
    if not os.path.exists(json_file):
        print("错误: all_funds.json 文件不存在，请先运行 fetch_all_funds.py")
        return None
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"从文件加载成功: {data['total']} 只基金")
        print(f"更新时间: {data['update_time']}")
        
        # 检查数据是否超过1天
        update_time = datetime.fromisoformat(data['update_time'])
        current_time = datetime.now()
        time_diff = current_time - update_time
        
        if time_diff.days > 0:
            print(f"警告: 数据已过期 {time_diff.days} 天，请运行 fetch_all_funds.py 更新")
        
        return data
    except Exception as e:
        print(f"错误: {e}")
        return None

def get_top_funds_from_json(limit=100):
    """从JSON文件中获取Top N基金"""
    data = load_funds_from_json()
    if not data:
        return []
    
    return data['funds'][:limit]

def get_fund_by_code_from_json(fund_code):
    """从JSON文件中根据代码获取基金"""
    data = load_funds_from_json()
    if not data:
        return None
    
    for fund in data['funds']:
        if fund['code'] == fund_code:
            return fund
    
    return None

if __name__ == "__main__":
    # 示例: 读取Top 10基金
    top10 = get_top_funds_from_json(10)
    print("\nTop 10 基金:")
    for i, fund in enumerate(top10, 1):
        print(f"{i:2d} {fund['code']} {fund['name']:30s} {fund['return_1y']*100:>10.2f}% {fund['nav']:>10.4f}")
    
    # 示例: 查找特定基金
    fund = get_fund_by_code_from_json('011370')
    if fund:
        print(f"\n基金 011370: {fund['name']}")
        print(f"近一年收益: {fund['return_1y']*100:.2f}%")
        print(f"当前净值: {fund['nav']:.4f}")
