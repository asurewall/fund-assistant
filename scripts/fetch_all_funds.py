#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天获取所有基金数据并保存到JSON文件
"""

import sys
import os
import json
from datetime import datetime
from fund_fetcher import FundFetcher

def fetch_all_funds(all_funds_count=3000):
    """获取所有基金数据并保存到JSON文件"""
    fetcher = FundFetcher(apply_dedup=True)

    print("开始获取基金数据...")

    # 获取近一年收益Top基金（去重后大约60%）
    funds = fetcher.get_top_funds(period_days=365, limit=all_funds_count)
    
    print(f"成功获取 {len(funds)} 只基金")
    
    # 添加更新时间
    data = {
        'update_time': datetime.now().isoformat(),
        'total': len(funds),
        'funds': funds
    }
    
    # 保存到JSON文件
    output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'all_funds.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"数据已保存到: {output_file}")
    print(f"更新时间: {data['update_time']}")
    
    return funds

if __name__ == "__main__":
    fetch_all_funds()
