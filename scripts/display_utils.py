#!/usr/bin/env python
"""通用显示工具函数"""

from wcwidth import wcswidth


def cjk_ljust(text, width):
    """中英文混合字符串左对齐（按显示宽度计算）"""
    text = text or ""
    display_width = wcswidth(text)
    if display_width < 0:
        display_width = len(text)
    padding = width - display_width
    return text + " " * padding


def cjk_rjust(text, width):
    """中英文混合字符串右对齐（按显示宽度计算）"""
    text = text or ""
    display_width = wcswidth(text)
    if display_width < 0:
        display_width = len(text)
    padding = width - display_width
    return " " * padding + text


def print_table(headers, col_widths, aligns, rows):
    """通用表格打印函数

    Args:
        headers: 表头列表
        col_widths: 每列宽度列表
        aligns: 每列对齐方式列表 ("left" 或 "right")
        rows: 行数据列表，每行是一个列表
    """
    total_width = sum(col_widths) + len(col_widths) - 1

    header_line = ""
    sep_line = ""
    for h, w, a in zip(headers, col_widths, aligns):
        if a == "right":
            header_line += cjk_rjust(h, w) + " "
        else:
            header_line += cjk_ljust(h, w) + " "
        sep_line += "-" * w + " "

    print(header_line)
    print(sep_line)

    for row in rows:
        row_str = []
        for cell, w, a in zip(row, col_widths, aligns):
            if a == "right":
                row_str.append(cjk_rjust(str(cell), w))
            else:
                row_str.append(cjk_ljust(str(cell), w))
        print(" ".join(row_str))