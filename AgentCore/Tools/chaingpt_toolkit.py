from camel.toolkits.base import BaseToolkit
from camel.toolkits.function_tool import FunctionTool

import os
import requests
from datetime import datetime
from typing import List

class ChainGPTToolkit(BaseToolkit):
    def fetch_news(self, query: str):
        """
        从 ChainGPT API 获取新闻数据。

        参数:
        - query: 搜索关键词

        返回:
        - 包含新闻数据的 JSON 对象
        """
        API_KEY = "038257c8-af97-42cd-8ee6-5a26f80bf1e4"

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        params = {
            "categoryId": "5",                 # DeFi 类别
            "subCategoryId": "15",             # Ethereum 子类别
            "fetchAfter": "2024-01-01",        # 起始日期
            "searchQuery": query,              # 关键词搜索
            "limit": 10,                       # 返回结果数量
            "offset": 0,                       # 起始位置
            "sortBy": "createdAt"              # 按创建时间排序
        }

        try:
            response = requests.get("https://api.chaingpt.org/news", headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None
    
    def get_tools(self) -> List[FunctionTool]:
        r"""Returns a list of FunctionTool objects representing the
        functions in the toolkit.

        Returns:
            List[FunctionTool]: A list of FunctionTool objects
                representing the functions in the toolkit.
        """
        return [
            FunctionTool(self.fetch_news),
        ]



