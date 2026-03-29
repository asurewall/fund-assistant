---
name: fund-assistant
description: "量化基金投资系统，基于天天基金(EastMoney) API。用于基金持仓管理、自动化交易信号生成、定时估值更新和净值跟踪。支持回撤建仓、动态加仓、止盈止损策略。触发关键词：基金、持仓、加仓、减仓、止损、净值、估值、回撤、交易信号。"
license: Proprietary
---

# Fund Assistant - 量化基金投资系统

基于天天基金 API 的自动化量化投资工具，支持回撤建仓、动态加仓、止盈止损策略。

## 快速启动
  - 首次运行需要按照./assets/config_template.json配置文件格式初始化配置，修改后保存为./assets/fund_config.json, 可以询问用户是否要改动配置项，不改动则默认使用模板配置项
  - 配置文件中包含参数可以参考 ### 基础参数
  - ./assets/fund_config.json文件生成后，启动命令 `python fund.py config-update`  获取基金列表和缓存回撤数据就可以开始运行了

## 快速命令

所有操作通过统一入口 `fund.py`：

```python

# 查看当前持仓（首次运行自动从模板创建默认配置）
python fund.py status

# 早盘配置更新（每天 10:00 执行）
python fund.py config-update

# 下午估值更新（盘中实时估值，每天 14:45 执行）
python fund.py update

# 晚上真实净值更新（收盘后，每天 22:00 执行）
python fund.py nav-update

# 仅生成报告
python fund.py report

# 重置持仓（重新筛选+建仓）
python fund.py reset

# 执行交易（添加交易信号，供 nav-update 执行）
python fund.py trade

# 单只基金估值查询
python fund.py valuation --code 002207

```

## 交易策略
### 建仓规则
  - 触发条件：回撤 > drawdown_threshold（默认 20%）
  - 仓位：买入 initial_position_layers 层（默认 4 层 = 40% 仓位）
  - 板块限制：同板块最多 max_per_sector 只（默认 2 只）
  - 筛选逻辑：按回撤从大到小排序，优先建仓回撤更大的基金
### 加仓规则
  - 有效期：建仓后第 2 天起，至清仓前 low_fee_days - 1 天止（共 23 天）
  - 触发条件：根据当日跌幅动态加仓, 可配置

  | 当日涨幅范围             | 加仓层数  |
  | ------------------ | ----- |
  | -0.5% ≤ 涨幅 < 0.5%  | 0.5 层 |
  | -1% ≤ 涨幅 < -0.5%   | 1 层   |
  | -1.5% ≤ 涨幅 < -1%   | 1.5 层 |
  | -2.5% ≤ 涨幅 < -1.5% | 2 层   |
  | -3% ≤ 涨幅 < -2.5%   | 3 层   |
  | 涨幅 < -3%           | 4 层   |

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
python fund.py trade add 002207 1    # 002207 加仓 1 层

# 添加减仓信号（nav-update 时执行）
python fund.py trade remove 002207          # 002207 全部卖出
python fund.py trade remove 002207 1/4        # 002207 卖出 1/4 层

# 清除所有信号
python fund.py trade clear
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
| `max_per_sector`          | 同板块最多几只            | 2     |
| `initial_position_layers` | 建仓层数               | 4     |
| `max_layers`              | 单只基金最大层数           | 10    |

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
  "max_per_sector": 2,
  "initial_position_layers": 4,
  "max_layers": 10,
  "add_position": {
    "enabled": true,
    "max_total_layers": 10,
    "rules": [
      {"min_return": 0.005, "max_return": -0.005, "layers": 0.5},
      {"min_return": -0.01, "max_return": -0.005, "layers": 1},
      {"min_return": -0.015, "max_return": -0.01, "layers": 1.5},
      {"min_return": -0.025, "max_return": -0.015, "layers": 2},
      {"min_return": -0.03, "max_return": -0.025, "layers": 3},
      {"min_return": -1, "max_return": -0.03, "layers": 4}
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
  "wechat": {
    "enabled": false,
    "webhook_url": ""
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
| 文件                           | 说明                                         |
| ---------------------------- | ------------------------------------------ |
| `assets/fund_config.json`    | 配置文件                                       |
| `assets/fund_positions.json` | 持仓数据                                       |
| `fund_signals.json`          | 待执行的交易信号（update/trade 生成，nav-update 执行后删除） |
| `assets/fund_drawdowns.json` | 回撤缓存（`drawdown_cache_count` 只），每日更新        |
| `assets/all_funds.json`      | 基金列表缓存（`all_funds_count` 只），每日更新           |


## 定时任务配置
| 时间     | 命令                              | 说明                          |
| ------ | ------------------------------- | --------------------------- |
| 10:00  | `python fund.py config-update`  | 早盘配置更新（更新基金列表和回撤缓存）       |
| 10:00  | `python fund.py report`         | 每周六/每月1号生成报告              |
| 14:45  | `python fund.py update`         | 下午估值更新（生成交易信号）            |
| 22:00  | `python fund.py nav-update`     | 晚上净值更新（执行交易，用户确认后更新持仓）   |

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
4. 微信通知可选：配置 webhook 后可接收交易通知