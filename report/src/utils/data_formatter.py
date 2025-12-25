"""
数据格式化工具
统一不同数据源的输出格式
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import pandas as pd
from loguru import logger


class DataFormatter:
    """数据格式化器"""
    
    @staticmethod
    def format_stock_info(stock_data: Dict[str, Any], source: str = "unknown") -> Dict[str, Any]:
        """格式化股票基本信息"""
        formatted = {
            "symbol": stock_data.get("symbol", ""),
            "name": stock_data.get("name", ""),
            "market": stock_data.get("market", ""),
            "industry": stock_data.get("industry", ""),
            "sector": stock_data.get("sector", ""),
            "list_date": stock_data.get("list_date", ""),
            "source": source,
            "updated_at": datetime.now().isoformat()
        }
        
        # 处理不同数据源的特殊字段
        if source == "tushare":
            formatted.update({
                "ts_code": stock_data.get("ts_code", ""),
                "area": stock_data.get("area", ""),
                "fullname": stock_data.get("fullname", "")
            })
        elif source == "alpha_vantage":
            formatted.update({
                "description": stock_data.get("description", ""),
                "market_cap": stock_data.get("market_cap", ""),
                "pe_ratio": stock_data.get("pe_ratio", ""),
                "dividend_yield": stock_data.get("dividend_yield", "")
            })
        elif source == "akshare":
            formatted.update({
                "current_price": stock_data.get("current_price", ""),
                "change_percent": stock_data.get("change_percent", "")
            })
            
        return formatted
        
    @staticmethod
    def format_financial_statement(df: pd.DataFrame, statement_type: str, 
                                  symbol: str, source: str = "unknown") -> Dict[str, Any]:
        """格式化财务报表数据"""
        if df is None or df.empty:
            return {}
            
        # 转换为标准格式
        formatted = {
            "symbol": symbol,
            "statement_type": statement_type,
            "source": source,
            "updated_at": datetime.now().isoformat(),
            "data": []
        }
        
        # 处理不同数据源的列名差异
        column_mapping = DataFormatter._get_column_mapping(statement_type, source)
        
        for _, row in df.iterrows():
            record = {}
            
            # 提取报告期
            report_date = DataFormatter._extract_report_date(row, source)
            if report_date:
                record["report_date"] = report_date
                
            # 映射财务数据字段
            for standard_name, source_names in column_mapping.items():
                for source_name in source_names:
                    if source_name in row and pd.notna(row[source_name]):
                        record[standard_name] = DataFormatter._convert_numeric(row[source_name])
                        break
                        
            if record:
                formatted["data"].append(record)
                
        return formatted
        
    @staticmethod
    def _get_column_mapping(statement_type: str, source: str) -> Dict[str, List[str]]:
        """获取字段映射表"""
        base_mapping = {
            "report_date": ["报告日期", "fiscalDateEnding", "date", "report_period"]
        }
        
        if statement_type == "balance_sheet":
            mapping = {
                **base_mapping,
                "total_assets": ["资产总计", "totalAssets", "total_assets"],
                "total_liabilities": ["负债合计", "totalLiabilities", "total_liabilities"],
                "shareholders_equity": ["股东权益合计", "totalShareholderEquity", "shareholders_equity"],
                "cash_and_equivalents": ["货币资金", "cashAndCashEquivalentsAtCarryingValue", "cash"],
                "accounts_receivable": ["应收账款", "currentNetReceivables", "accounts_receivable"],
                "inventory": ["存货", "inventory", "inventory"],
                "property_plant_equipment": ["固定资产", "propertyPlantEquipment", "ppe"]
            }
        elif statement_type == "income_statement":
            mapping = {
                **base_mapping,
                "total_revenue": ["营业总收入", "totalRevenue", "revenue"],
                "operating_income": ["营业利润", "operatingIncome", "operating_income"],
                "net_income": ["净利润", "netIncome", "net_income"],
                "gross_profit": ["毛利润", "grossProfit", "gross_profit"],
                "operating_expenses": ["营业费用", "operatingExpenses", "operating_expenses"],
                "interest_expense": ["利息费用", "interestExpense", "interest_expense"],
                "tax_expense": ["所得税费用", "incomeTaxExpense", "tax_expense"]
            }
        elif statement_type == "cash_flow":
            mapping = {
                **base_mapping,
                "operating_cash_flow": ["经营活动现金流量净额", "operatingCashflow", "operating_cash_flow"],
                "investing_cash_flow": ["投资活动现金流量净额", "cashflowFromInvestment", "investing_cash_flow"],
                "financing_cash_flow": ["筹资活动现金流量净额", "cashflowFromFinancing", "financing_cash_flow"],
                "net_cash_flow": ["现金流量净额", "changeInCash", "net_cash_flow"],
                "free_cash_flow": ["自由现金流", "freeCashFlow", "free_cash_flow"],
                "capital_expenditures": ["资本支出", "capitalExpenditures", "capex"]
            }
        else:
            mapping = base_mapping
            
        return mapping
        
    @staticmethod
    def _extract_report_date(row: pd.Series, source: str) -> Optional[str]:
        """提取报告日期"""
        date_fields = ["报告日期", "fiscalDateEnding", "date", "report_period", "end_date"]
        
        for field in date_fields:
            if field in row and pd.notna(row[field]):
                date_value = row[field]
                if isinstance(date_value, str):
                    return date_value
                elif hasattr(date_value, 'strftime'):
                    return date_value.strftime('%Y-%m-%d')
                else:
                    return str(date_value)
                    
        return None
        
    @staticmethod
    def _convert_numeric(value: Any) -> Union[float, str]:
        """转换数值类型"""
        if pd.isna(value):
            return ""
            
        try:
            # 尝试转换为数值
            if isinstance(value, str):
                # 移除千位分隔符和其他格式字符
                cleaned = value.replace(',', '').replace('$', '').replace('%', '').strip()
                if cleaned == '' or cleaned == '--' or cleaned == 'None':
                    return ""
                return float(cleaned)
            else:
                return float(value)
        except (ValueError, TypeError):
            return str(value)
            
    @staticmethod
    def format_search_results(results: List[Dict[str, Any]], source: str = "unknown") -> List[Dict[str, Any]]:
        """格式化搜索结果"""
        formatted_results = []
        
        for result in results:
            formatted = DataFormatter.format_stock_info(result, source)
            formatted_results.append(formatted)
            
        return formatted_results
        
    @staticmethod
    def format_annual_reports(reports: Dict[str, Any], symbol: str, source: str = "unknown") -> Dict[str, Any]:
        """格式化年报数据"""
        formatted = {
            "symbol": symbol,
            "source": source,
            "report_type": "annual",
            "updated_at": datetime.now().isoformat(),
            "statements": {}
        }
        
        for statement_type, data in reports.items():
            if isinstance(data, pd.DataFrame):
                formatted["statements"][statement_type] = DataFormatter.format_financial_statement(
                    data, statement_type, symbol, source
                )
            else:
                formatted["statements"][statement_type] = data
                
        return formatted
        
    @staticmethod
    def format_quarterly_reports(reports: Dict[str, Any], symbol: str, source: str = "unknown") -> Dict[str, Any]:
        """格式化季报数据"""
        formatted = {
            "symbol": symbol,
            "source": source,
            "report_type": "quarterly", 
            "updated_at": datetime.now().isoformat(),
            "statements": {}
        }
        
        for statement_type, data in reports.items():
            if isinstance(data, pd.DataFrame):
                formatted["statements"][statement_type] = DataFormatter.format_financial_statement(
                    data, statement_type, symbol, source
                )
            else:
                formatted["statements"][statement_type] = data
                
        return formatted
        
    @staticmethod
    def merge_multi_source_data(data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并多数据源的数据"""
        if not data_list:
            return {}
            
        # 以第一个数据源为基础
        merged = data_list[0].copy()
        merged["sources"] = [data_list[0].get("source", "unknown")]
        
        # 合并其他数据源的数据
        for data in data_list[1:]:
            source = data.get("source", "unknown")
            merged["sources"].append(source)
            
            # 合并报表数据
            if "statements" in data:
                for statement_type, statement_data in data["statements"].items():
                    if statement_type not in merged.get("statements", {}):
                        merged.setdefault("statements", {})[statement_type] = statement_data
                    else:
                        # 如果已存在，可以选择保留最新的或合并
                        pass
                        
        merged["updated_at"] = datetime.now().isoformat()
        return merged