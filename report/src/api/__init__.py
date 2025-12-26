"""
HTTP API 模块
提供RESTful API接口访问财报收集功能
"""
from .app import create_app

__all__ = ["create_app"]
