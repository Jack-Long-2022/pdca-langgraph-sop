"""公共工具函数"""

import json
import re


def parse_json_response(response: str) -> dict | None:
    """从LLM响应中提取JSON对象"""
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            return None
    return None
