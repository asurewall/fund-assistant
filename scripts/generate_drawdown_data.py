#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算基金回撤率并保存到JSON文件（并发版本）
"""

import sys
import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fund_fetcher import FundFetcher


def process_single_fund(fund, lookback_days):
    """处理单个基金的回撤计算（每个线程独立 fetcher）"""
    try:
        fetcher = FundFetcher(apply_dedup=True)
        drawdown = fetcher.calculate_drawdown(fund['code'], lookback_days=lookback_days)
        return {
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
    except Exception as e:
        return None


def generate_drawdown_data(limit=800, lookback_days=90, max_workers=10):
    """计算基金回撤率并保存到JSON文件（并发版本）

    Args:
        limit: 基金数量
        lookback_days: 回撤计算回看天数
        max_workers: 最大并发数（默认10）
    """
    print(f"开始获取基金数据...")

    fetcher = FundFetcher(apply_dedup=True)

    # 从JSON文件或API获取基金列表（主线程执行一次）
    funds = fetcher.get_top_funds(period_days=365, limit=limit)

    print(f"成功获取 {len(funds)} 只基金，使用 {max_workers} 并发计算回撤率...")

    drawdown_data = []
    failed_count = 0
    completed = 0
    total = len(funds)
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_fund = {
            executor.submit(process_single_fund, fund, lookback_days): fund
            for fund in funds
        }

        for future in as_completed(future_to_fund):
            result = future.result()
            completed += 1
            if result:
                drawdown_data.append(result)
            else:
                failed_count += 1

            # 每完成 10% 打印进度
            if completed % max(1, total // 10) == 0 or completed == total:
                progress = completed / total * 100
                print(f"进度: {completed}/{total} ({progress:.1f}%) - 成功: {len(drawdown_data)}, 失败: {failed_count}")

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

    elapsed_time = time.time() - start_time
    if elapsed_time < 60:
        print(f"成功计算 {len(drawdown_data)} 只基金的回撤率，失败 {failed_count} 只，耗时 {elapsed_time:.1f} 秒")
    else:
        print(f"成功计算 {len(drawdown_data)} 只基金的回撤率，失败 {failed_count} 只，耗时 {elapsed_time/60:.1f} 分钟")

    return drawdown_data


def load_drawdowns_from_json():
    """从JSON文件中的加载回撤率数据"""
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
    lookback_days = 90
    max_workers = 10
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            lookback_days = int(sys.argv[2])
        except ValueError:
            pass
    if len(sys.argv) > 3:
        try:
            max_workers = int(sys.argv[3])
        except ValueError:
            pass

    generate_drawdown_data(limit, lookback_days, max_workers)
