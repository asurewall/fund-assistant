#!/usr/bin/env python
"""查看年收益率排名靠前的基金"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from display_utils import print_table


def get_top_return_funds(top: int = 100):
    """获取年收益率排名靠前的基金

    Args:
        top: 返回前N只基金
    """
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    all_funds_file = os.path.join(assets_dir, "all_funds.json")

    # 检查文件是否存在，不存在则自动运行 config-update
    if not os.path.exists(all_funds_file):
        print(f"基金数据文件不存在，自动更新...")
        try:
            from fund import cmd_config_update
            cmd_config_update()
        except Exception as e:
            print(f"错误: config-update 执行失败: {e}")
            return []
        print(f"config-update 完成，重新读取数据")

    # 读取基金数据
    with open(all_funds_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 处理嵌套结构
    if isinstance(data, dict) and "funds" in data:
        all_funds = data["funds"]
    elif isinstance(data, list):
        all_funds = data
    else:
        print(f"错误: 基金数据格式不正确")
        return []

    print(f"从缓存读取基金数据（{len(all_funds)} 只）")

    # 过滤有效数据（1年收益不为0）
    valid_funds = [f for f in all_funds if isinstance(f, dict) and f.get("code") and f.get("return_1y", 0) != 0]
    valid_funds.sort(key=lambda x: x.get("return_1y", 0), reverse=True)

    # 取前N只
    results = valid_funds[:top]

    # 打印结果
    headers = ["排名", "代码", "名称", "净值", "1年收益"]
    col_widths = [6, 10, 45, 10, 10]
    aligns = ["center", "left", "left", "right", "right"]

    total_width = sum(col_widths) + len(col_widths) - 1
    print(f"\n{'='*total_width}")
    print(f"年收益率排名 TOP {len(results)}")
    print(f"{'='*total_width}")

    rows = []
    for i, r in enumerate(results, 1):
        ret = r.get("return_1y", 0)
        ret_str = f"{ret:.2%}"
        rows.append([
            i,
            r['code'],
            r['name'][:45],
            f"{r.get('nav', 0):.4f}",
            ret_str
        ])

    print_table(headers, col_widths, aligns, rows)

    return results


def main():
    parser = argparse.ArgumentParser(description="查看年收益率排名靠前的基金")
    parser.add_argument("--top", "-n", type=int, default=100, help="返回前N只基金（默认100）")
    args = parser.parse_args()

    get_top_return_funds(top=args.top)


if __name__ == "__main__":
    main()