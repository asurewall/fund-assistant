#!/usr/bin/env python
"""查看回撤率排名靠前的基金"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from display_utils import cjk_ljust, cjk_rjust, print_table


def get_top_drawdown_funds(top: int = 100):
    """获取回撤率排名靠前的基金

    Args:
        top: 返回前N只基金
    """
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    drawdowns_file = os.path.join(assets_dir, "fund_drawdowns.json")

    # 检查文件是否存在，不存在则自动运行 config-update
    if not os.path.exists(drawdowns_file):
        print(f"回撤率数据文件不存在，自动更新...")
        try:
            from fund import cmd_config_update
            cmd_config_update()
        except Exception as e:
            print(f"错误: config-update 执行失败: {e}")
            return []
        print(f"config-update 完成，重新读取数据")

    # 读取回撤率数据
    with open(drawdowns_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 处理嵌套结构
    if isinstance(data, dict) and "funds" in data:
        all_data = data["funds"]
    elif isinstance(data, dict) and "drawdowns" in data:
        all_data = data["drawdowns"]
    elif isinstance(data, list):
        all_data = data
    else:
        print(f"错误: 回撤率数据格式不正确")
        return []

    print(f"从缓存读取回撤率数据（{len(all_data)} 只）")

    # 过滤有效数据并排序
    valid_funds = [f for f in all_data if isinstance(f, dict) and f.get("drawdown", 0) != 0]
    valid_funds.sort(key=lambda x: x.get("drawdown", 0))

    # 取前N只
    results = valid_funds[:top]

    # 打印结果
    headers = ["排名", "代码", "名称", "净值", "回撤率", "回高点涨幅", "1年收益", "最高点日期"]
    col_widths = [6, 10, 45, 10, 10, 10, 10, 20]
    aligns = ["center", "left", "left", "right", "right", "right", "right", "left"]

    total_width = sum(col_widths) + len(col_widths) - 1
    print(f"\n{'='*total_width}")
    print(f"回撤率排名 TOP {len(results)}")
    print(f"{'='*total_width}")

    rows = []
    for i, r in enumerate(results, 1):
        dd = r.get("drawdown", 0)
        dd_str = f"{dd:.2%}"
        # 计算回到高点需要的涨幅: 1/(1-回撤率) - 1
        recover_return = 1 / (1 - dd) - 1 if dd < 1 else float('inf')
        recover_str = f"{recover_return:.2%}"
        nav = r.get("current_nav", r.get("nav", 0))
        ret_1y = r.get("return_1y", 0)
        ret_str = f"{ret_1y:.2%}" if ret_1y else "N/A"
        max_date = r.get("max_nav_date", "")
        if max_date:
            try:
                days_diff = (datetime.now() - datetime.strptime(max_date, "%Y-%m-%d")).days
                max_date_str = f"{max_date} ({days_diff}天)"
            except:
                max_date_str = max_date
        else:
            max_date_str = "N/A"

        rows.append([
            i,
            r['code'],
            r['name'][:45],
            f"{nav:.4f}",
            dd_str,
            recover_str,
            ret_str,
            max_date_str
        ])

    print_table(headers, col_widths, aligns, rows)

    return results


def main():
    parser = argparse.ArgumentParser(description="查看回撤率排名靠前的基金")
    parser.add_argument("--top", "-n", type=int, default=100, help="返回前N只基金（默认100）")
    args = parser.parse_args()

    get_top_drawdown_funds(top=args.top)


if __name__ == "__main__":
    main()