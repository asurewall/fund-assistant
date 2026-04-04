#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金数据获取模块
使用天天基金(EastMoney)真实API获取数据
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from pathlib import Path


class FundFetchError(Exception):
    """基金数据获取异常"""
    pass


class FundFetcher:
    """基金数据获取器 - 使用天天基金真实API"""
    
    SUFFIX_PRIORITY = {
        'I': 1,
        'E': 2,
        'D': 3,
        'C': 4,
        'B': 5,
        'A': 6,
    }
    
    def __init__(
        self,
        provider: str = "eastmoney",
        max_retries: int = 3,
        retry_delay_seconds: int = 2,
        timeout_seconds: int = 15,
        apply_dedup: bool = True
    ):
        """
        初始化基金获取器
        
        Args:
            provider: 数据源提供商 (eastmoney)
            max_retries: 最大重试次数
            retry_delay_seconds: 重试延迟（秒）
            timeout_seconds: 请求超时（秒）
            apply_dedup: 是否应用同名基金去重
        """
        self.provider = provider
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.apply_dedup = apply_dedup
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://fund.eastmoney.com/data/fundranking.html',
        }
    
    def _request_with_retry(self, url: str, params: Dict = None, as_text: bool = False):
        """带重试的 HTTP 请求"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout_seconds
                )
                response.encoding = 'utf-8'
                if as_text:
                    return response.text
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay_seconds)
                else:
                    raise FundFetchError(f"请求失败: {e}")
        raise FundFetchError("请求失败")
    
    def get_top_funds(
        self,
        period_days: int = 365,
        limit: int = 800,
        sort_by: str = "return"
    ) -> List[Dict]:
        """
        获取 top 基金列表
        
        Args:
            period_days: 统计周期（天）- 365=近一年, 180=近半年, 90=近三月
            limit: 返回基金数量
            sort_by: 排序方式 (return, nav, etc.)
        
        Returns:
            基金列表
        """
        # 优先从JSON文件读取
        json_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'all_funds.json')
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查数据是否过期（超过1天）
                update_time = datetime.fromisoformat(data['update_time'])
                current_time = datetime.now()
                time_diff = current_time - update_time
                
                if time_diff.days < 1:
                    print(f"从JSON文件读取基金数据（{len(data['funds'])} 只）")
                    return data['funds'][:limit]
            except Exception as e:
                print(f"读取JSON文件失败: {e}")
        
        try:
            if self.apply_dedup:
                all_funds = []
                page_index = 1
                page_size = 5000
                max_pages = 5
                
                while len(all_funds) < limit * 5 and page_index <= max_pages:
                    funds = self._fetch_rank_page(period_days, page_index, page_size)
                    if not funds:
                        break
                    all_funds.extend(funds)
                    page_index += 1
                    time.sleep(0.2)
                
                deduped_funds = self._deduplicate_funds(all_funds)
                result = deduped_funds[:limit]
            else:
                all_funds = []
                page_size = 5000
                page_index = 1
                max_pages = 5
                
                while len(all_funds) < limit and page_index <= max_pages:
                    funds = self._fetch_rank_page(period_days, page_index, page_size)
                    if not funds:
                        break
                    all_funds.extend(funds)
                    page_index += 1
                    time.sleep(0.2)
                
                result = all_funds[:limit]
            
            return result
        except Exception as e:
            raise FundFetchError(f"获取 top 基金失败: {e}")
    
    def _fetch_rank_page(self, period_days: int, page_index: int, page_size: int) -> List[Dict]:
        """获取单页排行数据"""
        sort_field = self._get_sort_field(period_days)
        
        today = datetime.now()
        start_date = (today - timedelta(days=period_days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        url = "https://fund.eastmoney.com/data/rankhandler.aspx"
        params = {
            'op': 'ph',
            'dt': 'kf',
            'ft': 'all',
            'rs': '',
            'gs': '0',
            'sc': sort_field,
            'st': 'desc',
            'sd': start_date,
            'ed': end_date,
            'qdii': '',
            'tabSubtype': ',,,,,',
            'pi': page_index,
            'pn': page_size,
            'dx': '1',
        }
        
        try:
            text = self._request_with_retry(url, params, as_text=True)
            
            match = re.search(r'var rankData\s*=\s*(\{.*?\});', text, re.DOTALL)
            if not match:
                return []
            
            data_str = match.group(1)
            datas_match = re.search(r'datas:\s*\[(.*?)\],', data_str, re.DOTALL)
            if not datas_match:
                return []
            
            datas_content = datas_match.group(1)
            items = re.findall(r'"([^"]*)"', datas_content)
            
            funds = []
            for item in items:
                fields = item.split(',')
                if len(fields) >= 20:
                    try:
                        fund = {
                            "code": fields[0],
                            "name": fields[1],
                            "type": fields[3],
                            "nav": float(fields[4]) if fields[4] else 0,
                            "nav_date": fields[5],
                            "return_1d": float(fields[6]) / 100 if fields[6] else 0,
                            "return_1w": float(fields[7]) / 100 if fields[7] else 0,
                            "return_1m": float(fields[8]) / 100 if fields[8] else 0,
                            "return_3m": float(fields[9]) / 100 if fields[9] else 0,
                            "return_6m": float(fields[10]) / 100 if fields[10] else 0,
                            "return_1y": float(fields[11]) / 100 if fields[11] else 0,
                            "return_2y": float(fields[12]) / 100 if fields[12] else 0,
                            "return_3y": float(fields[13]) / 100 if fields[13] else 0,
                            "return_this_year": float(fields[14]) / 100 if fields[14] else 0,
                            "return_total": float(fields[15]) / 100 if fields[15] else 0,
                            "update_time": datetime.now().isoformat()
                        }
                        funds.append(fund)
                    except (ValueError, IndexError):
                        continue
            
            return funds
            
        except Exception as e:
            print(f"获取排行数据失败: {e}")
            return []
    
    def _get_sort_field(self, period_days: int) -> str:
        """获取排序字段"""
        field_map = {
            30: '1yzf',
            90: '3yzf',
            180: '6yzf',
            365: '1nzf',
            730: '2nzf',
            1095: '3nzf',
        }
        return field_map.get(period_days, '1nzf')
    
    def _get_suffix(self, fund_name: str) -> str:
        if not fund_name:
            return ""
        last_char = fund_name[-1]
        return last_char if last_char in self.SUFFIX_PRIORITY else ""
    
    def _get_base_name(self, fund_name: str) -> str:
        if not fund_name:
            return ""
        last_char = fund_name[-1]
        return fund_name[:-1] if last_char in self.SUFFIX_PRIORITY else fund_name
    
    def _deduplicate_funds(self, funds: List[Dict]) -> List[Dict]:
        """同名基金去重，保留优先级最高的版本"""
        groups = {}
        for fund in funds:
            base_name = self._get_base_name(fund['name'])
            if base_name not in groups:
                groups[base_name] = []
            groups[base_name].append(fund)
        
        deduped = []
        for base_name, group in groups.items():
            if len(group) == 1:
                deduped.append(group[0])
            else:
                best = min(group, key=lambda f: self.SUFFIX_PRIORITY.get(self._get_suffix(f['name']), 999))
                deduped.append(best)
        
        return deduped
    
    def get_fund_history(
        self,
        fund_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = None
    ) -> List[Dict]:
        """
        获取基金净值历史
        
        Args:
            fund_code: 基金代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            days: 过去天数（如果指定则忽略 start_date）
        
        Returns:
            净值历史列表
        """
        try:
            page_size = min(days or 90, 365)
            
            url = "https://fundmobapi.eastmoney.com/FundMApi/FundNetDiagram.ashx"
            params = {
                'FCODE': fund_code,
                'deviceid': 'Wap',
                'plat': 'Wap',
                'product': 'EFund',
                'version': '2.0.0',
                'Uid': '',
                'pageIndex': 1,
                'pageSize': page_size,
            }
            
            data = self._request_with_retry(url, params)
            
            history = []
            if 'Datas' in data and data['Datas']:
                for item in data['Datas']:
                    try:
                        history.append({
                            "date": item.get('FSRQ', ''),
                            "nav": float(item.get('DWJZ', 0)),
                            "acc_nav": float(item.get('LJJZ', 0)),
                            "daily_return": float(item.get('JZZZL', 0)) / 100 if item.get('JZZZL') else 0,
                        })
                    except (ValueError, TypeError):
                        continue
            
            return history
        
        except Exception as e:
            raise FundFetchError(f"获取基金历史失败: {e}")
    
    def get_valuation(self, fund_code: str) -> Dict:
        """
        获取基金当日估值
        
        Args:
            fund_code: 基金代码
        
        Returns:
            估值数据
        """
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        
        try:
            text = self._request_with_retry(url, as_text=True)
            
            match = re.search(r'jsonpgz\((\{.*?\})\)', text)
            if match:
                data = json.loads(match.group(1))
                return {
                    "code": data.get('fundcode', fund_code),
                    "name": data.get('name', ''),
                    "nav": float(data.get('dwjz', 0)),
                    "nav_date": data.get('jzrq', ''),
                    "estimated_nav": float(data.get('gsz', 0)),
                    "estimated_return": float(data.get('gszzl', 0)) / 100,
                    "estimated_time": data.get('gztime', ''),
                    "update_time": datetime.now().isoformat(),
                }
        except Exception as e:
            raise FundFetchError(f"获取基金估值失败: {e}")
        
        return {}
    
    def get_current_nav(self, fund_code: str) -> Dict:
        """
        获取基金当前真实净值
        
        Args:
            fund_code: 基金代码
        
        Returns:
            净值数据
        """
        try:
            url = "https://fundmobapi.eastmoney.com/FundMApi/FundNetDiagram.ashx"
            params = {
                'FCODE': fund_code,
                'deviceid': 'Wap',
                'plat': 'Wap',
                'product': 'EFund',
                'version': '2.0.0',
                'Uid': '',
                'pageIndex': 1,
                'pageSize': 1,  # 只获取最新一条
            }
            
            data = self._request_with_retry(url, params)
            
            if 'Datas' in data and data['Datas'] and len(data['Datas']) > 0:
                item = data['Datas'][0]
                return {
                    "code": fund_code,
                    "nav": float(item.get('DWJZ', 0)),
                    "nav_date": item.get('FSRQ', ''),
                    "acc_nav": float(item.get('LJJZ', 0)),
                    "daily_return": float(item.get('JZZZL', 0)) / 100 if item.get('JZZZL') else 0,
                    "update_time": datetime.now().isoformat(),
                }
        except Exception as e:
            raise FundFetchError(f"获取基金净值失败: {e}")
        
        return {}
    
    def get_fund_sector(self, fund_code: str):
        """
        获取基金板块信息
        
        Args:
            fund_code: 基金代码
            
        Returns:
            板块名称，如果获取失败返回 None
        """
        try:
            url = "https://api.xiaobeiyangji.com/yangji-api/api/get-fund-detail-v310"
            headers = {
                "Host": "api.xiaobeiyangji.com",
                "content-type": "application/json",
                "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlvbklkIjoibzg5Nm81LTgwWmFVaWxteWg0N2lWbldaampSUSIsImlhdCI6MTc3NTI3NTE0NCwiZXhwIjoxNzc3ODY3MTQ0fQ.Tq1xXgNvNnDRGx3DFelVPgyYadG6RbRxCSMPQxXwSVg",
            }
            
            payload = {"code": fund_code}
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()
            
            if response.status_code == 200 and "data" in result:
                data = result["data"]
                
                # 尝试获取 relatedIndustryV2
                if "relatedIndustryV2" in data and data["relatedIndustryV2"]:
                    for industry in data["relatedIndustryV2"]:
                        if "themeName" in industry:
                            return industry["themeName"]
                
                # 尝试获取 relatedIndustry
                if "relatedIndustry" in data and data["relatedIndustry"]:
                    for industry in data["relatedIndustry"]:
                        if "themeName" in industry:
                            return industry["themeName"]
            
            return None
            
        except Exception as e:
            return None
    
    def calculate_drawdown(
        self,
        fund_code: str,
        lookback_days: int = 90
    ) -> Dict:
        """
        计算基金回撤率
        
        Args:
            fund_code: 基金代码
            lookback_days: 回看天数
        
        Returns:
            {
                'drawdown': 回撤率 (负数),
                'recovery_return': 需要涨幅,
                'max_nav': 最高净值,
                'max_nav_date': 最高净值日期,
                'current_nav': 当前净值,
                'current_nav_date': 当前净值日期
            }
        """
        history = self.get_fund_history(fund_code, days=lookback_days)
        
        if not history:
            return {
                'drawdown': 0.0,
                'recovery_return': 0.0,
                'max_nav': 0.0,
                'max_nav_date': '',
                'current_nav': 0.0,
                'current_nav_date': '',
                'start_date': '',
                'end_date': ''
            }
        
        max_nav = 0.0
        max_nav_date = ''
        for h in history:
            if h['nav'] > max_nav:
                max_nav = h['nav']
                max_nav_date = h['date']
        
        current_nav = history[0]['nav']
        current_nav_date = history[0]['date']
        start_date = history[-1]['date']
        end_date = history[0]['date']
        
        drawdown = (current_nav - max_nav) / max_nav if max_nav > 0 else 0
        recovery_return = (max_nav - current_nav) / current_nav if current_nav > 0 else 0
        
        return {
            'drawdown': drawdown,
            'recovery_return': recovery_return,
            'max_nav': max_nav,
            'max_nav_date': max_nav_date,
            'current_nav': current_nav,
            'current_nav_date': current_nav_date,
            'start_date': start_date,
            'end_date': end_date
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='基金数据获取工具')
    parser.add_argument('command', nargs='?', default='test', 
                        help='命令: top10, top50, top100, drawdown, valuation, history')
    parser.add_argument('--code', '-c', default=None, help='基金代码')
    parser.add_argument('--days', '-d', type=int, default=90, help='回看天数')
    parser.add_argument('--limit', '-l', type=int, default=50, help='基金数量')
    parser.add_argument('--period', '-p', type=int, default=365, help='收益周期(天)')
    
    args = parser.parse_args()
    
    fetcher = FundFetcher()
    
    if args.command == 'test':
        print("=" * 80)
        print("天天基金数据获取测试")
        print("=" * 80)
        
        print("\n[1] 获取近一年收益 Top 10 基金（带去重）")
        print("-" * 80)
        top_funds = fetcher.get_top_funds(period_days=365, limit=10)
        
        for i, fund in enumerate(top_funds, 1):
            print(f"  {i:2d}. {fund['code']} {fund['name']:<20} "
                  f"近一年: {fund['return_1y']:>7.2%}  "
                  f"近三月: {fund['return_3m']:>7.2%}  "
                  f"净值: {fund['nav']:.4f}")
        
        if top_funds:
            first_fund = top_funds[0]
            fund_code = first_fund['code']
            
            print(f"\n[2] 获取 {first_fund['name']} ({fund_code}) 净值历史")
            print("-" * 80)
            history = fetcher.get_fund_history(fund_code, days=30)
            print(f"  获取到 {len(history)} 条记录")
            if history:
                print(f"  最新: {history[0]['date']} 净值: {history[0]['nav']:.4f}")
            
            print(f"\n[3] 计算回撤率")
            print("-" * 80)
            dd_info = fetcher.calculate_drawdown(fund_code, lookback_days=90)
            print(f"  回撤率: {dd_info['drawdown']:.2%}")
            print(f"  恢复需涨幅: {dd_info['recovery_return']:.2%}")
            print(f"  最高点: {dd_info['max_nav_date']} 净值 {dd_info['max_nav']:.4f}")
            
            print(f"\n[4] 获取实时估值")
            print("-" * 80)
            valuation = fetcher.get_valuation(fund_code)
            if valuation:
                print(f"  基金名称: {valuation.get('name', '')}")
                print(f"  最新净值: {valuation.get('nav', 0):.4f} ({valuation.get('nav_date', '')})")
                print(f"  估算净值: {valuation.get('estimated_nav', 0):.4f}")
                print(f"  估算涨幅: {valuation.get('estimated_return', 0):.2%}")
        
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)
    
    elif args.command.startswith('top'):
        limit = int(args.command[3:]) if args.command[3:] else args.limit
        period = args.period
        
        print("=" * 120)
        print(f"获取近{period}天收益 Top {limit} 基金（带去重）")
        print("=" * 120)
        
        top_funds = fetcher.get_top_funds(period_days=period, limit=limit)
        
        print(f"成功获取 {len(top_funds)} 只基金")
        print("-" * 120)
        print(f"{'排名':>4} {'代码':<8} {'基金名称':<24} {'近一年':>10} {'近三月':>10} {'近一月':>10} {'净值':>10}")
        print("-" * 120)
        
        for i, f in enumerate(top_funds, 1):
            name = f['name'][:22] if len(f['name']) > 22 else f['name']
            print(f"{i:>4} {f['code']:<8} {name:<24} {f['return_1y']:>10.2%} {f['return_3m']:>10.2%} {f['return_1m']:>10.2%} {f['nav']:>10.4f}")
        
        print("-" * 120)
    
    elif args.command == 'drawdown':
        limit = args.limit
        period = args.period
        lookback = args.days
        
        print("=" * 145)
        print(f"获取近{period}天收益 Top {limit} 基金 - 近{lookback}天回撤分析")
        print("=" * 145)
        
        top_funds = fetcher.get_top_funds(period_days=period, limit=limit)
        
        print(f"成功获取 {len(top_funds)} 只基金，正在计算回撤率...")
        print("-" * 145)
        
        results = []
        for f in top_funds:
            try:
                dd_info = fetcher.calculate_drawdown(f['code'], lookback_days=lookback)
                results.append({
                    'code': f['code'],
                    'name': f['name'],
                    'return_1y': f['return_1y'],
                    'drawdown': dd_info['drawdown'],
                    'recovery': dd_info['recovery_return'],
                    'max_nav': dd_info['max_nav'],
                    'max_nav_date': dd_info['max_nav_date'],
                    'current_nav': dd_info['current_nav'],
                    'start_date': dd_info['start_date'],
                    'end_date': dd_info['end_date'],
                })
            except Exception as e:
                print(f"  计算 {f['code']} 回撤失败: {e}")
        
        results.sort(key=lambda x: x['drawdown'])
        
        print(f"{'排名':>4} {'代码':<8} {'基金名称':<18} {'近一年':>10} {'回撤率':>10} {'需涨幅':>10} {'数据区间':<24} {'最高点日期':<12} {'最高净值':>10} {'当前净值':>10}")
        print("-" * 145)
        
        for i, r in enumerate(results, 1):
            name = r['name'][:16] if len(r['name']) > 16 else r['name']
            date_range = f"{r['start_date']} ~ {r['end_date']}"
            print(f"{i:>4} {r['code']:<8} {name:<18} {r['return_1y']:>10.2%} {r['drawdown']:>10.2%} {r['recovery']:>10.2%} {date_range:<24} {r['max_nav_date']:<12} {r['max_nav']:>10.4f} {r['current_nav']:>10.4f}")
        
        print("-" * 145)
    
    elif args.command == 'valuation':
        code = args.code
        if not code:
            print("请指定基金代码: --code 011370")
            exit(1)
        
        valuation = fetcher.get_valuation(code)
        if valuation:
            print(f"基金代码: {valuation.get('code', '')}")
            print(f"基金名称: {valuation.get('name', '')}")
            print(f"最新净值: {valuation.get('nav', 0):.4f} ({valuation.get('nav_date', '')})")
            print(f"估算净值: {valuation.get('estimated_nav', 0):.4f}")
            print(f"估算涨幅: {valuation.get('estimated_return', 0):.2%}")
            print(f"估算时间: {valuation.get('estimated_time', '')}")
    
    elif args.command == 'history':
        code = args.code
        if not code:
            print("请指定基金代码: --code 011370")
            exit(1)
        
        days = args.days
        history = fetcher.get_fund_history(code, days=days)
        
        print(f"获取 {code} 近 {days} 天净值历史，共 {len(history)} 条记录")
        print("-" * 60)
        print(f"{'日期':<12} {'净值':>12} {'累计净值':>12} {'日涨跌':>10}")
        print("-" * 60)
        for h in history[:20]:
            print(f"{h['date']:<12} {h['nav']:>12.4f} {h['acc_nav']:>12.4f} {h.get('daily_return', 0):>10.2%}")
        if len(history) > 20:
            print(f"... 省略 {len(history) - 20} 条")
    
    else:
        print(f"未知命令: {args.command}")
        print("可用命令: test, top10, top50, top100, drawdown, valuation, history")
        print("示例:")
        print("  python fund_fetcher.py top50")
        print("  python fund_fetcher.py drawdown --limit 30 --days 90")
        print("  python fund_fetcher.py valuation --code 011370")
        print("  python fund_fetcher.py history --code 011370 --days 30")
