---
name: fund-assistant
description: "量化基金投资系统，基于天天基金(EastMoney) API。用于基金持仓管理、自动化交易信号生成、定时估值更新和净值跟踪。支持回撤建仓、动态加仓、止盈止损策略。触发关键词：基金、持仓、加仓、减仓、止损、净值、估值、回撤、交易信号。"
license: Proprietary
---

# Fund Assistant - 量化基金投资系统

基于天天基金 API 的自动化量化投资工具，支持回撤建仓、动态加仓、止盈止损策略。

## 快速启动
  - 首次运行 `python fund.py status` 时，若不存在 `fund_config.json`，会自动从模板创建默认配置
  - 用户可以通过对话修改配置项（参考 ### 基础参数），说"修改配置"即可
  - 配置完成后执行 `python fund.py config-update` 获取基金列表和回撤缓存

## 快速命令

所有操作通过统一入口 `fund.py`：

```python

# 查看当前持仓（首次运行自动从模板创建配置，可询问用户是否更改配置）
python fund.py status

# 早盘配置更新（每天 10:00 执行）
python fund.py config-update

# 下午估值更新（盘中实时估值，每天 14:45 执行）
python fund.py update

# 晚上真实净值更新（收盘后，每天 22:00 执行）
python fund.py nav-update  # 手动执行（需要确认）
python fund.py nav-update --auto  # 自动执行（用于定时任务，无需确认）

# 仅生成报告
python fund.py report

# 重置持仓（重新获取配置文件）
python fund.py reset

# 执行交易（添加交易信号，供 nav-update 执行）
python fund.py trade

# 单只基金估值查询
python fund.py valuation --code 002207

# 查看年收益率排名 TOP N
python fund.py top-return -n 20

# 查看回撤率排名 TOP N
python fund.py top-drawdown -n 20

```

## 交易策略
### 建仓规则
  - 触发条件：回撤 > drawdown_threshold（默认 20%）
  - 仓位：买入 initial_position_layers 层（默认 4 层 = 40% 仓位）
  - 板块限制：同板块最多 max_per_sector 只（默认 2 只）
  - 筛选逻辑：按回撤从大到小排序，优先建仓回撤更大的基金
### 加仓规则
  - 有效期：建仓后第 2 天起，至清仓前 low_fee_days - 1 天止（共 23 天）可以进行加仓
  - 触发条件：根据当日跌幅动态加仓, 可配置

  | 当日涨幅范围             | 加仓层数  |
  | ------------------ | ----- |
  | -0.85% ≤ 涨幅 < 0.5% | 0.5 层 |
  | -1.5% ≤ 涨幅 < -0.85% | 1 层   |
  | -2.25% ≤ 涨幅 < -1.5% | 1.5 层 |
  | -3% ≤ 涨幅 < -2.25%  | 2 层   |
  | -3.5% ≤ 涨幅 < -3%   | 2.5 层 |
  | -4% ≤ 涨幅 < -3.5%   | 3 层   |
  | -4.5% ≤ 涨幅 < -4%   | 3.5 层 |
  | 涨幅 < -4.5%         | 4 层   |

  - 上限：单只基金最大 max_layers 层（默认 10 层）

### 减仓/清仓规则
满足以下任一条件即触发卖出信号：
1. 持有期满：持仓 >= hold_days（默认 30 天）→ 全部卖出
2. 止损：收益率 <= stop_loss.max_loss（默认 -15%）→ 全部卖出
3. 止盈分档：
  - 收益率 >= 15% → 全部卖出
  - 收益率 >= 12% → 卖出 50%
  - 收益率 >= 10% → 卖出 50%
4. 手动减仓：通过 trade remove 命令添加

## 交易信号执行流程

```
┌─────────────────────────────────────────────────────────────┐
│  14:45  python fund.py update                               │
│  ─────────────────────────────────────────────────────────  │
│  生成交易信号（加仓/减仓/建仓）                               │
│  信号保存到 fund_signals.json，不实际执行                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  任意时间  python fund.py trade add/remove                  │
│  ─────────────────────────────────────────────────────────  │
│  手动添加/删除信号到 fund_signals.json                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  22:00  python fund.py nav-update                           │
│  ─────────────────────────────────────────────────────────  │
│  读取信号文件，展示交易详情                                  │
│  用户确认后执行交易，更新持仓                                │
│  执行完成后删除信号文件                                      │
└─────────────────────────────────────────────────────────────┘
```

## 手动交易命令

```
# 查看当前信号
python fund.py trade list

# 添加加仓信号（nav-update 时执行）
python fund.py trade add 002207 1           # 002207 加仓 1 层
python fund.py trade add 002207 ¥2000      # 002207 加仓 ¥2000（按金额，自动计算层数）

# 添加建仓信号（nav-update 时执行，用于新建仓）
python fund.py trade initial 002207 4       # 002207 建仓 4 层
python fund.py trade initial 002207 4 ¥2000 # 002207 建仓 4 层，¥2000

# 添加减仓信号（nav-update 时执行）
python fund.py trade remove 002207          # 002207 全部卖出
python fund.py trade remove 002207 1/4        # 002207 卖出 1/4 层

# 清除所有信号
python fund.py trade clear

# 撤销信号
python fund.py trade cancel 1           # 撤销第1个信号（按索引）
python fund.py trade cancel 002207      # 撤销002207的所有信号
```

## 配置文件

编辑 `assets/fund_config.json`：

### 基础参数
| 参数                        | 说明                 | 默认值   |
| ------------------------- | ------------------ | ----- |
| `total_capital`           | 总资金                | 50000 |
| `fund_count`              | 基金数量               | 10    |
| `drawdown_threshold`      | 建仓回撤阈值             | 0.20  |
| `hold_days`               | 持有天数上限             | 30    |
| `low_fee_days`            | 低费率天数（清仓前 N-1 天不买） | 7     |
| `all_funds_count`         | 基金列表缓存数量           | 3000  |
| `drawdown_cache_count`    | 回撤率缓存数量            | 800   |
| `lookback_days`           | 回撤计算回看天数           | 90    |
| `drawdown_max_workers`    | 回撤计算并发数            | 30    |
| `max_per_sector`          | 同板块最多几只            | 2     |
| `initial_position_layers` | 建仓层数               | 4     |
| `max_layers`              | 单只基金最大层数           | 10    |
| `add_position`            | 加仓规则（见下方详解）       |       |
| `stop_loss`               | 止损规则（见下方详解）       |       |
| `remove_position`         | 减仓规则（见下方详解）       |       |

### 加仓规则 (add_position)
| 字段 | 说明 | 默认值 |
| --- | --- | --- |
| `enabled` | 是否启用 | true |
| `max_total_layers` | 单只基金最大层数 | 10 |
| `rules` | 加仓规则列表 | 见下方 |

**rules 规则匹配逻辑：**
- 按 `min_return` 从大到小排序
- 找到第一个满足 `min_return <= 当日涨幅 < max_return` 的规则

| 规则示例 | 当日涨幅范围 | 加仓层数 |
| --- | --- | --- |
| `{"min_return": -0.0085, "max_return": 0.005, "layers": 0.5}` | -0.85% ≤ 涨幅 < 0.5% | 0.5 层 |
| `{"min_return": -0.015, "max_return": -0.0085, "layers": 1}` | -1.5% ≤ 涨幅 < -0.85% | 1 层 |
| `{"min_return": -0.0225, "max_return": -0.015, "layers": 1.5}` | -2.25% ≤ 涨幅 < -1.5% | 1.5 层 |
| `{"min_return": -0.03, "max_return": -0.0225, "layers": 2}` | -3% ≤ 涨幅 < -2.25% | 2 层 |
| `{"min_return": -0.035, "max_return": -0.03, "layers": 2.5}` | -3.5% ≤ 涨幅 < -3% | 2.5 层 |
| `{"min_return": -0.04, "max_return": -0.035, "layers": 3}` | -4% ≤ 涨幅 < -3.5% | 3 层 |
| `{"min_return": -0.045, "max_return": -0.04, "layers": 3.5}` | -4.5% ≤ 涨幅 < -4% | 3.5 层 |
| `{"min_return": -1, "max_return": -0.045, "layers": 4}` | 涨幅 < -4.5% | 4 层 |

### 止损规则 (stop_loss)
| 字段 | 说明 | 默认值 |
| --- | --- | --- |
| `enabled` | 是否启用 | true |
| `max_loss` | 最大亏损阈值（负数） | -0.15 |

### 减仓规则 (remove_position)
| 字段 | 说明 | 默认值 |
| --- | --- | --- |
| `enabled` | 是否启用 | true |
| `rules` | 减仓规则列表 | 见下方 |

**rules 规则匹配逻辑：**
- 按 `min_profit_rate` 从大到小排序
- 找到第一个满足 `收益率 >= min_profit_rate` 的规则

| 规则示例 | 盈利阈值 | 卖出比例 |
| --- | --- | --- |
| `{"min_profit_rate": 0.15, "layers": "all"}` | 收益率 >= 15% | 全部卖出 |
| `{"min_profit_rate": 0.12, "layers": 0.5}` | 收益率 >= 12% | 卖出 50% |
| `{"min_profit_rate": 0.10, "layers": 0.5}` | 收益率 >= 10% | 卖出 50% |

### 完整配置示例
```
{
  "total_capital": 50000,
  "fund_count": 10,
  "drawdown_threshold": 0.20,
  "hold_days": 30,
  "low_fee_days": 7,
  "all_funds_count": 3000,
  "drawdown_cache_count": 800,
  "lookback_days": 90,
  "drawdown_max_workers": 30,
  "max_per_sector": 2,
  "initial_position_layers": 4,
  "max_layers": 10,
  "add_position": {
    "enabled": true,
    "max_total_layers": 10,
    "rules": [
      {"min_return": -0.0085, "max_return": 0.005, "layers": 0.5},
      {"min_return": -0.015, "max_return": -0.0085, "layers": 1},
      {"min_return": -0.0225, "max_return": -0.015, "layers": 1.5},
      {"min_return": -0.03, "max_return": -0.0225, "layers": 2},
      {"min_return": -0.035, "max_return": -0.03, "layers": 2.5},
      {"min_return": -0.04, "max_return": -0.035, "layers": 3},
      {"min_return": -0.045, "max_return": -0.04, "layers": 3.5},
      {"min_return": -1, "max_return": -0.045, "layers": 4}
    ]
  },
  "stop_loss": {
    "enabled": true,
    "max_loss": -0.15
  },
  "remove_position": {
    "enabled": true,
    "rules": [
      {"min_profit_rate": 0.15, "layers": "all"},
      {"min_profit_rate": 0.12, "layers": 0.5},
      {"min_profit_rate": 0.10, "layers": 0.5}
    ]
  },
  "schedule": {
    "estimate_update": "45 14 * * *",
    "real_update": "0 22 * * *",
    "weekly_report": "0 10 * * 6",
    "monthly_report": "0 10 1 * *"
  }
}
```
## 数据文件
| 文件                              | 说明                                         |
| -------------------------------- | ------------------------------------------ |
| `assets/fund_config.json`        | 配置文件                                       |
| `assets/fund_positions.json`     | 持仓数据                                       |
| `assets/fund_signals.json`      | 待执行的交易信号（update/trade 生成，nav-update 执行后删除） |
| `assets/fund_drawdowns.json`     | 回撤缓存（`drawdown_cache_count` 只），每日更新        |
| `assets/all_funds.json`          | 基金列表缓存（`all_funds_count` 只），每日更新           |


## 定时任务配置
| 时间      | 命令                              | 说明                          |
| ------- | ------------------------------- | --------------------------- |
| 10:00 | `python fund.py config-update`  | 周一到周五执行更新基金列表和回撤缓存（建议交易日前一天或当日早盘执行） |
| 10:00   | `python fund.py report`         | 每周六/每月1号生成报告              |
| 14:45   | `python fund.py update`         | 周一到周五下午估值更新（生成交易信号）            |
| 22:00   | `python fund.py nav-update --auto`     | 周一到周五晚上净值更新（自动执行交易，无需用户确认）   |

Cron 表达式参考：
```
{
  "schedule": {
    "estimate_update": "45 14 * * *",
    "real_update": "0 22 * * *",
    "weekly_report": "0 10 * * 6",
    "monthly_report": "0 10 1 * *"
  }
}
```

## 注意事项
1. 交易信号非自动执行：update 命令仅生成信号，需 nav-update 时用户确认后才执行
2. 回撤缓存每日更新：config-update 会刷新基金列表和回撤率缓存
3. 手动交易灵活干预：可通过 trade add/remove 随时调整策略