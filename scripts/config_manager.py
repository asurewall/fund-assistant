#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
管理基金助手的配置
"""

import json
import os
from typing import Dict, Optional

class ConfigManager:
    """配置管理类"""
    
    def __init__(self, config_file: str = "fund_config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件
        
        Returns:
            配置字典
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "total_capital": 50000,
            "fund_count": 10,
            "drawdown_threshold": 0.20,
            "hold_days": 30,
            "low_fee_days": 7,
            "all_funds_count": 3000,
            "drawdown_cache_count": 800,
            "lookback_days": 90,
            "drawdown_max_workers": 30,
            "initial_position_layers": 4,
            "max_layers": 10,
            "max_per_sector": 2,
            "add_position": {
                "enabled": True,
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
                "enabled": True,
                "max_loss": -0.15
            },
            "remove_position": {
                "enabled": True,
                "rules": [
                    {"min_profit_rate": 0.15, "layers": "all"},
                    {"min_profit_rate": 0.12, "layers": 0.5},
                    {"min_profit_rate": 0.10, "layers": 0.5}
                ]
            },
            "wechat": {
                "enabled": False,
                "webhook_url": ""
            },
            "schedule": {
                "estimate_update": "45 14 * * *",
                "real_update": "0 22 * * *",
                "weekly_report": "0 10 * * 6",
                "monthly_report": "0 10 1 * *"
            }
        }
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Optional[any] = None) -> any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: any):
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save_config()
    
    def update_config(self, updates: Dict):
        """更新配置
        
        Args:
            updates: 更新的配置字典
        """
        def _update_dict(target, source):
            for key, value in source.items():
                if isinstance(value, dict) and key in target:
                    _update_dict(target[key], value)
                else:
                    target[key] = value
        
        _update_dict(self.config, updates)
        self.save_config()
    
    def validate_config(self) -> bool:
        """验证配置
        
        Returns:
            是否有效
        """
        required_keys = [
            "total_capital",
            "fund_count",
            "drawdown_threshold",
            "hold_days",
            "low_fee_days"
        ]
        
        for key in required_keys:
            if key not in self.config:
                print(f"配置缺少必要项: {key}")
                return False
        
        # 验证数值范围
        if self.config["total_capital"] <= 0:
            print("总资金必须大于0")
            return False
        
        if self.config["fund_count"] <= 0:
            print("基金数量必须大于0")
            return False
        
        if not 0 < self.config["drawdown_threshold"] < 1:
            print("回撤率阈值必须在0-1之间")
            return False

        if self.config["hold_days"] <= 0:
            print("持有天数必须大于0")
            return False
        
        if self.config["low_fee_days"] < 0:
            print("低手续费天数不能为负数")
            return False
        
        return True
    
    def get_schedule(self, task: str) -> str:
        """获取定时任务配置
        
        Args:
            task: 任务名称
        
        Returns:
            定时任务表达式
        """
        return self.config.get("schedule", {}).get(task, "")
    
    def set_schedule(self, task: str, cron_expression: str):
        """设置定时任务配置
        
        Args:
            task: 任务名称
            cron_expression: 定时任务表达式
        """
        if "schedule" not in self.config:
            self.config["schedule"] = {}
        self.config["schedule"][task] = cron_expression
        self.save_config()
    
    def export_config(self) -> str:
        """导出配置
        
        Returns:
            配置JSON字符串
        """
        return json.dumps(self.config, ensure_ascii=False, indent=2)
    
    def import_config(self, config_str: str):
        """导入配置
        
        Args:
            config_str: 配置JSON字符串
        """
        try:
            config = json.loads(config_str)
            self.config = config
            self.save_config()
            return True
        except Exception as e:
            print(f"导入配置失败: {e}")
            return False
