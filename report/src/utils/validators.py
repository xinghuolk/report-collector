"""
数据验证工具
验证输入参数和数据完整性
"""
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger


class DataValidator:
    """数据验证器"""
    
    # 股票代码正则表达式
    CN_STOCK_PATTERN = re.compile(r'^[0-9]{6}$')  # A股6位数字
    HK_STOCK_PATTERN = re.compile(r'^[0-9]{5}$')  # 港股5位数字
    US_STOCK_PATTERN = re.compile(r'^[A-Z]{1,5}$')  # 美股1-5位字母
    
    @staticmethod
    def validate_stock_symbol(symbol: str, market: str) -> Tuple[bool, str]:
        """验证股票代码格式"""
        if not symbol:
            return False, "股票代码不能为空"
            
        symbol = symbol.strip().upper()
        
        if market == "CN":
            if not DataValidator.CN_STOCK_PATTERN.match(symbol):
                return False, "中国A股代码应为6位数字"
        elif market == "HK":
            if not DataValidator.HK_STOCK_PATTERN.match(symbol):
                return False, "港股代码应为5位数字"
        elif market == "US":
            if not DataValidator.US_STOCK_PATTERN.match(symbol):
                return False, "美股代码应为1-5位字母"
        else:
            return False, f"不支持的市场: {market}"
            
        return True, ""
        
    @staticmethod
    def validate_market(market: str) -> Tuple[bool, str]:
        """验证市场代码"""
        valid_markets = ["CN", "HK", "US"]
        
        if not market:
            return False, "市场代码不能为空"
            
        market = market.upper()
        if market not in valid_markets:
            return False, f"不支持的市场: {market}，支持的市场: {', '.join(valid_markets)}"
            
        return True, ""
        
    @staticmethod
    def validate_report_type(report_type: str) -> Tuple[bool, str]:
        """验证报表类型"""
        valid_types = [
            "annual",           # 年报
            "semi_annual",      # 半年报
            "quarterly",        # 季报
            "balance_sheet",    # 资产负债表
            "income_statement", # 利润表
            "cash_flow"         # 现金流量表
        ]
        
        if not report_type:
            return False, "报表类型不能为空"
            
        if report_type not in valid_types:
            return False, f"不支持的报表类型: {report_type}，支持的类型: {', '.join(valid_types)}"
            
        return True, ""
        
    @staticmethod
    def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> Tuple[bool, str]:
        """验证日期范围"""
        if start_date:
            if not DataValidator._is_valid_date(start_date):
                return False, f"起始日期格式错误: {start_date}，应为YYYY-MM-DD格式"
                
        if end_date:
            if not DataValidator._is_valid_date(end_date):
                return False, f"结束日期格式错误: {end_date}，应为YYYY-MM-DD格式"
                
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                if start > end:
                    return False, "起始日期不能晚于结束日期"
                    
                # 检查日期范围是否过大（超过10年）
                if (end - start).days > 3650:
                    return False, "日期范围不能超过10年"
                    
            except ValueError as e:
                return False, f"日期解析错误: {e}"
                
        return True, ""
        
    @staticmethod
    def validate_year(year: Optional[int]) -> Tuple[bool, str]:
        """验证年份"""
        if year is None:
            return True, ""
            
        current_year = datetime.now().year
        
        if not isinstance(year, int):
            return False, "年份必须为整数"
            
        if year < 1990:
            return False, "年份不能早于1990年"
            
        if year > current_year + 1:
            return False, f"年份不能超过{current_year + 1}年"
            
        return True, ""
        
    @staticmethod
    def validate_years_list(years: Optional[List[int]]) -> Tuple[bool, str]:
        """验证年份列表"""
        if not years:
            return True, ""
            
        if not isinstance(years, list):
            return False, "年份列表必须为数组"
            
        if len(years) > 10:
            return False, "年份列表不能超过10个"
            
        for year in years:
            is_valid, error = DataValidator.validate_year(year)
            if not is_valid:
                return False, error
                
        return True, ""
        
    @staticmethod
    def validate_search_keyword(keyword: str) -> Tuple[bool, str]:
        """验证搜索关键词"""
        if not keyword:
            return False, "搜索关键词不能为空"
            
        keyword = keyword.strip()
        
        if len(keyword) < 1:
            return False, "搜索关键词至少需要1个字符"
            
        if len(keyword) > 50:
            return False, "搜索关键词不能超过50个字符"
            
        # 检查是否包含危险字符
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`']
        for char in dangerous_chars:
            if char in keyword:
                return False, f"搜索关键词不能包含特殊字符: {char}"
                
        return True, ""
        
    @staticmethod
    def validate_financial_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证财务数据完整性"""
        errors = []
        
        # 检查必要字段
        required_fields = ["symbol", "statement_type", "source"]
        for field in required_fields:
            if field not in data:
                errors.append(f"缺少必要字段: {field}")
                
        # 验证数据字段
        if "data" in data:
            if not isinstance(data["data"], list):
                errors.append("data字段必须为数组")
            elif len(data["data"]) == 0:
                errors.append("财务数据不能为空")
            else:
                # 检查数据记录
                for i, record in enumerate(data["data"]):
                    if not isinstance(record, dict):
                        errors.append(f"数据记录{i+1}必须为对象")
                        continue
                        
                    if "report_date" not in record:
                        errors.append(f"数据记录{i+1}缺少报告日期")
                        
        return len(errors) == 0, errors
        
    @staticmethod
    def validate_mcp_request(request_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证MCP请求数据"""
        errors = []
        
        # 检查基本结构
        if "method" not in request_data:
            errors.append("缺少method字段")
            
        if "params" not in request_data:
            errors.append("缺少params字段")
        else:
            params = request_data["params"]
            
            # 根据方法验证参数
            method = request_data.get("method", "")
            
            if method.startswith("search_"):
                # 搜索类请求
                if "keyword" in params:
                    is_valid, error = DataValidator.validate_search_keyword(params["keyword"])
                    if not is_valid:
                        errors.append(error)
                        
                if "market" in params:
                    is_valid, error = DataValidator.validate_market(params["market"])
                    if not is_valid:
                        errors.append(error)
                        
            elif method.startswith("get_"):
                # 获取数据类请求
                if "symbol" in params and "market" in params:
                    is_valid, error = DataValidator.validate_stock_symbol(
                        params["symbol"], params["market"]
                    )
                    if not is_valid:
                        errors.append(error)
                        
                if "report_type" in params:
                    is_valid, error = DataValidator.validate_report_type(params["report_type"])
                    if not is_valid:
                        errors.append(error)
                        
                if "year" in params:
                    is_valid, error = DataValidator.validate_year(params["year"])
                    if not is_valid:
                        errors.append(error)
                        
                if "years" in params:
                    is_valid, error = DataValidator.validate_years_list(params["years"])
                    if not is_valid:
                        errors.append(error)
                        
        return len(errors) == 0, errors
        
    @staticmethod
    def _is_valid_date(date_string: str) -> bool:
        """检查日期格式是否有效"""
        try:
            datetime.strptime(date_string, '%Y-%m-%d')
            return True
        except ValueError:
            return False
            
    @staticmethod
    def sanitize_input(text: str) -> str:
        """清理输入文本"""
        if not text:
            return ""
            
        # 移除危险字符
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\n', '\r', '\t']
        for char in dangerous_chars:
            text = text.replace(char, '')
            
        # 限制长度
        return text.strip()[:200]
        
    @staticmethod
    def format_error_response(errors: List[str]) -> Dict[str, Any]:
        """格式化错误响应"""
        return {
            "success": False,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }