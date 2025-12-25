"""
验证器单元测试
测试 DataValidator 类的所有验证方法
"""
import pytest
from datetime import datetime

from src.utils.validators import DataValidator
from tests.fixtures.sample_data import (
    VALID_CN_STOCK_CODES,
    INVALID_CN_STOCK_CODES,
    VALID_HK_STOCK_CODES,
    INVALID_HK_STOCK_CODES,
    VALID_US_STOCK_CODES,
    INVALID_US_STOCK_CODES,
    VALID_MARKETS,
    INVALID_MARKETS,
    VALID_REPORT_TYPES,
    INVALID_REPORT_TYPES,
    VALID_DATE_RANGES,
    INVALID_DATE_RANGES,
    VALID_YEARS,
    INVALID_YEARS,
    VALID_KEYWORDS,
    INVALID_KEYWORDS,
)


class TestStockCodeValidation:
    """股票代码验证测试"""

    @pytest.mark.parametrize("stock_code", VALID_CN_STOCK_CODES)
    def test_cn_stock_code_valid(self, stock_code):
        """测试有效的A股代码"""
        is_valid, error = DataValidator.validate_stock_symbol(stock_code, "CN")
        assert is_valid is True
        assert error == ""

    def test_cn_stock_code_6_digits(self):
        """测试A股代码必须是6位数字"""
        is_valid, _ = DataValidator.validate_stock_symbol("000001", "CN")
        assert is_valid is True

    def test_cn_stock_code_5_digits_invalid(self):
        """测试5位数字对A股无效"""
        is_valid, error = DataValidator.validate_stock_symbol("00001", "CN")
        assert is_valid is False
        assert "6位数字" in error

    def test_cn_stock_code_7_digits_invalid(self):
        """测试7位数字对A股无效"""
        is_valid, error = DataValidator.validate_stock_symbol("6005190", "CN")
        assert is_valid is False
        assert "6位数字" in error

    def test_cn_stock_code_with_letters_invalid(self):
        """测试包含字母的代码无效"""
        is_valid, error = DataValidator.validate_stock_symbol("abcdef", "CN")
        assert is_valid is False

    def test_cn_stock_code_empty_invalid(self):
        """测试空代码无效"""
        is_valid, error = DataValidator.validate_stock_symbol("", "CN")
        assert is_valid is False
        assert "不能为空" in error

    @pytest.mark.parametrize("stock_code", VALID_HK_STOCK_CODES)
    def test_hk_stock_code_valid(self, stock_code):
        """测试有效的港股代码"""
        is_valid, error = DataValidator.validate_stock_symbol(stock_code, "HK")
        assert is_valid is True
        assert error == ""

    def test_hk_stock_code_5_digits(self):
        """测试港股代码必须是5位数字"""
        is_valid, _ = DataValidator.validate_stock_symbol("00700", "HK")
        assert is_valid is True

    def test_hk_stock_code_4_digits_invalid(self):
        """测试4位数字对港股无效"""
        is_valid, error = DataValidator.validate_stock_symbol("0700", "HK")
        assert is_valid is False
        assert "5位数字" in error

    def test_hk_stock_code_6_digits_invalid(self):
        """测试6位数字对港股无效"""
        is_valid, error = DataValidator.validate_stock_symbol("007000", "HK")
        assert is_valid is False

    @pytest.mark.parametrize("stock_code", VALID_US_STOCK_CODES)
    def test_us_stock_code_valid(self, stock_code):
        """测试有效的美股代码"""
        is_valid, error = DataValidator.validate_stock_symbol(stock_code, "US")
        assert is_valid is True
        assert error == ""

    def test_us_stock_code_letters_only(self):
        """测试美股代码只能是字母"""
        is_valid, _ = DataValidator.validate_stock_symbol("AAPL", "US")
        assert is_valid is True

    def test_us_stock_code_with_numbers_invalid(self):
        """测试包含数字的美股代码无效"""
        is_valid, error = DataValidator.validate_stock_symbol("12345", "US")
        assert is_valid is False

    def test_us_stock_code_too_long_invalid(self):
        """测试超过5位的美股代码无效"""
        is_valid, error = DataValidator.validate_stock_symbol("AAAAAA", "US")
        assert is_valid is False

    def test_us_stock_code_lowercase_converted(self):
        """测试小写美股代码可以被转换接受"""
        # 验证器会将小写转为大写
        is_valid, _ = DataValidator.validate_stock_symbol("aapl", "US")
        assert is_valid is True


class TestMarketValidation:
    """市场代码验证测试"""

    def test_market_cn_valid(self):
        """测试CN市场有效"""
        is_valid, error = DataValidator.validate_market("CN")
        assert is_valid is True
        assert error == ""

    def test_market_hk_valid(self):
        """测试HK市场有效"""
        is_valid, error = DataValidator.validate_market("HK")
        assert is_valid is True
        assert error == ""

    def test_market_us_valid(self):
        """测试US市场有效"""
        is_valid, error = DataValidator.validate_market("US")
        assert is_valid is True
        assert error == ""

    def test_market_lowercase_valid(self):
        """测试小写市场代码有效（会被转大写）"""
        is_valid, _ = DataValidator.validate_market("cn")
        assert is_valid is True

    def test_market_invalid(self):
        """测试无效市场代码"""
        is_valid, error = DataValidator.validate_market("JP")
        assert is_valid is False
        assert "不支持的市场" in error

    def test_market_empty_invalid(self):
        """测试空市场代码无效"""
        is_valid, error = DataValidator.validate_market("")
        assert is_valid is False
        assert "不能为空" in error

    @pytest.mark.parametrize("market", INVALID_MARKETS)
    def test_invalid_markets(self, market):
        """测试各种无效市场代码"""
        if market is None:
            pytest.skip("None需要特殊处理")
        is_valid, _ = DataValidator.validate_market(market)
        assert is_valid is False


class TestReportTypeValidation:
    """报表类型验证测试"""

    @pytest.mark.parametrize("report_type", VALID_REPORT_TYPES)
    def test_valid_report_types(self, report_type):
        """测试所有有效的报表类型"""
        is_valid, error = DataValidator.validate_report_type(report_type)
        assert is_valid is True
        assert error == ""

    def test_report_type_annual_valid(self):
        """测试年报类型有效"""
        is_valid, _ = DataValidator.validate_report_type("annual")
        assert is_valid is True

    def test_report_type_semi_annual_valid(self):
        """测试半年报类型有效"""
        is_valid, _ = DataValidator.validate_report_type("semi_annual")
        assert is_valid is True

    def test_report_type_quarterly_valid(self):
        """测试季报类型有效"""
        is_valid, _ = DataValidator.validate_report_type("quarterly")
        assert is_valid is True

    def test_report_type_invalid(self):
        """测试无效的报表类型"""
        is_valid, error = DataValidator.validate_report_type("monthly")
        assert is_valid is False
        assert "不支持的报表类型" in error

    def test_report_type_empty_invalid(self):
        """测试空报表类型无效"""
        is_valid, error = DataValidator.validate_report_type("")
        assert is_valid is False
        assert "不能为空" in error

    @pytest.mark.parametrize("report_type", INVALID_REPORT_TYPES)
    def test_invalid_report_types(self, report_type):
        """测试各种无效的报表类型"""
        if report_type is None:
            pytest.skip("None需要特殊处理")
        is_valid, _ = DataValidator.validate_report_type(report_type)
        assert is_valid is False


class TestDateValidation:
    """日期验证测试"""

    @pytest.mark.parametrize("start_date,end_date", VALID_DATE_RANGES)
    def test_valid_date_ranges(self, start_date, end_date):
        """测试有效的日期范围"""
        is_valid, error = DataValidator.validate_date_range(start_date, end_date)
        assert is_valid is True
        assert error == ""

    def test_date_range_valid(self):
        """测试正常日期范围"""
        is_valid, _ = DataValidator.validate_date_range("2020-01-01", "2020-12-31")
        assert is_valid is True

    def test_date_range_start_after_end(self):
        """测试开始日期晚于结束日期"""
        is_valid, error = DataValidator.validate_date_range("2020-12-31", "2020-01-01")
        assert is_valid is False
        assert "起始日期不能晚于结束日期" in error

    def test_date_range_invalid_format(self):
        """测试无效日期格式"""
        is_valid, error = DataValidator.validate_date_range("2020-13-01", "2020-12-31")
        assert is_valid is False
        assert "格式错误" in error

    def test_date_range_too_long(self):
        """测试日期范围超过10年"""
        is_valid, error = DataValidator.validate_date_range("2010-01-01", "2025-12-31")
        assert is_valid is False
        assert "不能超过10年" in error

    def test_date_range_none_values_valid(self):
        """测试空日期值有效"""
        is_valid, _ = DataValidator.validate_date_range(None, None)
        assert is_valid is True

    def test_date_range_only_start_valid(self):
        """测试只有开始日期有效"""
        is_valid, _ = DataValidator.validate_date_range("2020-01-01", None)
        assert is_valid is True

    def test_date_range_only_end_valid(self):
        """测试只有结束日期有效"""
        is_valid, _ = DataValidator.validate_date_range(None, "2020-12-31")
        assert is_valid is True


class TestYearValidation:
    """年份验证测试"""

    @pytest.mark.parametrize("year", VALID_YEARS)
    def test_valid_years(self, year):
        """测试有效的年份"""
        is_valid, error = DataValidator.validate_year(year)
        assert is_valid is True
        assert error == ""

    def test_year_current_valid(self):
        """测试当前年份有效"""
        current_year = datetime.now().year
        is_valid, _ = DataValidator.validate_year(current_year)
        assert is_valid is True

    def test_year_future_valid(self):
        """测试下一年有效"""
        next_year = datetime.now().year + 1
        is_valid, _ = DataValidator.validate_year(next_year)
        assert is_valid is True

    def test_year_too_future_invalid(self):
        """测试过于未来的年份无效"""
        future_year = datetime.now().year + 2
        is_valid, error = DataValidator.validate_year(future_year)
        assert is_valid is False
        assert "不能超过" in error

    def test_year_too_old_invalid(self):
        """测试太早的年份无效"""
        is_valid, error = DataValidator.validate_year(1985)
        assert is_valid is False
        assert "不能早于1990" in error

    def test_year_none_valid(self):
        """测试空年份有效"""
        is_valid, _ = DataValidator.validate_year(None)
        assert is_valid is True

    def test_year_string_invalid(self):
        """测试字符串年份无效"""
        is_valid, error = DataValidator.validate_year("2023")
        assert is_valid is False
        assert "必须为整数" in error


class TestYearsListValidation:
    """年份列表验证测试"""

    def test_years_list_valid(self):
        """测试有效的年份列表"""
        is_valid, error = DataValidator.validate_years_list([2020, 2021, 2022])
        assert is_valid is True
        assert error == ""

    def test_years_list_empty_valid(self):
        """测试空年份列表有效"""
        is_valid, _ = DataValidator.validate_years_list([])
        assert is_valid is True

    def test_years_list_none_valid(self):
        """测试None年份列表有效"""
        is_valid, _ = DataValidator.validate_years_list(None)
        assert is_valid is True

    def test_years_list_too_many_invalid(self):
        """测试年份列表超过10个无效"""
        years = list(range(2010, 2025))  # 15个年份
        is_valid, error = DataValidator.validate_years_list(years)
        assert is_valid is False
        assert "不能超过10个" in error

    def test_years_list_invalid_year(self):
        """测试列表中包含无效年份"""
        is_valid, error = DataValidator.validate_years_list([2020, 1985, 2022])
        assert is_valid is False
        assert "不能早于1990" in error

    def test_years_list_not_list_invalid(self):
        """测试非列表类型无效"""
        is_valid, error = DataValidator.validate_years_list("2020,2021")
        assert is_valid is False
        assert "必须为数组" in error


class TestSearchKeywordValidation:
    """搜索关键词验证测试"""

    @pytest.mark.parametrize("keyword", VALID_KEYWORDS)
    def test_valid_keywords(self, keyword):
        """测试有效的搜索关键词"""
        is_valid, error = DataValidator.validate_search_keyword(keyword)
        assert is_valid is True
        assert error == ""

    def test_keyword_empty_invalid(self):
        """测试空关键词无效"""
        is_valid, error = DataValidator.validate_search_keyword("")
        assert is_valid is False
        assert "不能为空" in error

    def test_keyword_whitespace_only_invalid(self):
        """测试只有空格的关键词无效"""
        is_valid, error = DataValidator.validate_search_keyword("   ")
        assert is_valid is False
        # 会被strip后变成空字符串

    def test_keyword_too_long_invalid(self):
        """测试过长的关键词无效"""
        long_keyword = "a" * 51
        is_valid, error = DataValidator.validate_search_keyword(long_keyword)
        assert is_valid is False
        assert "不能超过50个字符" in error

    def test_keyword_with_dangerous_chars_invalid(self):
        """测试包含危险字符的关键词无效"""
        is_valid, error = DataValidator.validate_search_keyword("test<script>")
        assert is_valid is False
        assert "不能包含特殊字符" in error

    def test_keyword_with_semicolon_invalid(self):
        """测试包含分号的关键词无效"""
        is_valid, error = DataValidator.validate_search_keyword("select; drop")
        assert is_valid is False

    def test_keyword_with_dollar_invalid(self):
        """测试包含$的关键词无效"""
        is_valid, error = DataValidator.validate_search_keyword("echo $HOME")
        assert is_valid is False


class TestFinancialDataValidation:
    """财务数据验证测试"""

    def test_valid_financial_data(self):
        """测试有效的财务数据"""
        data = {
            "symbol": "000001",
            "statement_type": "annual",
            "source": "巨潮资讯网",
            "data": [{"report_date": "2023-12-31", "revenue": 1000000}],
        }
        is_valid, errors = DataValidator.validate_financial_data(data)
        assert is_valid is True
        assert errors == []

    def test_financial_data_missing_required_field(self):
        """测试缺少必要字段"""
        data = {
            "symbol": "000001",
            # 缺少 statement_type 和 source
        }
        is_valid, errors = DataValidator.validate_financial_data(data)
        assert is_valid is False
        assert any("缺少必要字段" in e for e in errors)

    def test_financial_data_empty_data_array(self):
        """测试空数据数组"""
        data = {
            "symbol": "000001",
            "statement_type": "annual",
            "source": "巨潮资讯网",
            "data": [],
        }
        is_valid, errors = DataValidator.validate_financial_data(data)
        assert is_valid is False
        assert any("不能为空" in e for e in errors)

    def test_financial_data_invalid_data_type(self):
        """测试data字段类型错误"""
        data = {
            "symbol": "000001",
            "statement_type": "annual",
            "source": "巨潮资讯网",
            "data": "not a list",
        }
        is_valid, errors = DataValidator.validate_financial_data(data)
        assert is_valid is False
        assert any("必须为数组" in e for e in errors)

    def test_financial_data_missing_report_date(self):
        """测试数据记录缺少报告日期"""
        data = {
            "symbol": "000001",
            "statement_type": "annual",
            "source": "巨潮资讯网",
            "data": [{"revenue": 1000000}],  # 缺少 report_date
        }
        is_valid, errors = DataValidator.validate_financial_data(data)
        assert is_valid is False
        assert any("缺少报告日期" in e for e in errors)


class TestInputSanitization:
    """输入清理测试"""

    def test_sanitize_removes_special_chars(self):
        """测试移除特殊字符"""
        result = DataValidator.sanitize_input("test<script>alert(1)</script>")
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_removes_semicolon(self):
        """测试移除分号"""
        result = DataValidator.sanitize_input("test;drop table")
        assert ";" not in result

    def test_sanitize_removes_pipe(self):
        """测试移除管道符"""
        result = DataValidator.sanitize_input("test|ls")
        assert "|" not in result

    def test_sanitize_removes_dollar(self):
        """测试移除$符号"""
        result = DataValidator.sanitize_input("test$HOME")
        assert "$" not in result

    def test_sanitize_trims_whitespace(self):
        """测试去除首尾空格"""
        result = DataValidator.sanitize_input("  test  ")
        assert result == "test"

    def test_sanitize_max_length(self):
        """测试最大长度限制"""
        long_input = "a" * 300
        result = DataValidator.sanitize_input(long_input)
        assert len(result) <= 200

    def test_sanitize_empty_string(self):
        """测试空字符串"""
        result = DataValidator.sanitize_input("")
        assert result == ""

    def test_sanitize_none_returns_empty(self):
        """测试None返回空字符串"""
        result = DataValidator.sanitize_input(None)
        assert result == ""

    def test_sanitize_removes_newlines(self):
        """测试移除换行符"""
        result = DataValidator.sanitize_input("test\ntest\rtest")
        assert "\n" not in result
        assert "\r" not in result

    def test_sanitize_removes_tabs(self):
        """测试移除制表符"""
        result = DataValidator.sanitize_input("test\ttest")
        assert "\t" not in result


class TestErrorResponseFormatting:
    """错误响应格式化测试"""

    def test_format_error_response(self):
        """测试错误响应格式"""
        errors = ["错误1", "错误2"]
        result = DataValidator.format_error_response(errors)

        assert result["success"] is False
        assert result["errors"] == errors
        assert "timestamp" in result

    def test_format_error_response_empty_errors(self):
        """测试空错误列表"""
        result = DataValidator.format_error_response([])
        assert result["success"] is False
        assert result["errors"] == []
