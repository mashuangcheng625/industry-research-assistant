"""
公司名称 -> 股票代码映射

用于自动识别用户查询中的上市公司并获取股票数据。
股票代码格式：sh600xxx (上海), sz000xxx/sz002xxx/sz300xxx (深圳)
"""

# 半导体产业链 A 股公司映射。港股、美股与未上市公司不进入当前行情 API。
COMPANY_STOCK_MAP = {
    "中芯国际": "sh688981",
    "韦尔股份": "sh603501",
    "北方华创": "sz002371",
    "中微公司": "sh688012",
    "寒武纪": "sh688256",
    "长电科技": "sh600584",
    "通富微电": "sz002156",
    "华天科技": "sz002185",
    "沪硅产业": "sh688126",
    "安集科技": "sh688019",
    "盛美上海": "sh688082",
    "拓荆科技": "sh688072",
    "芯源微": "sh688037",
    "江丰电子": "sz300666",
}


from typing import Optional, List, Tuple


def get_stock_code(company_name: str) -> Optional[str]:
    """
    根据公司名称获取股票代码

    Args:
        company_name: 公司名称

    Returns:
        股票代码（如 sh600519）或 None
    """
    return COMPANY_STOCK_MAP.get(company_name)


def find_company_in_query(query: str) -> List[Tuple[str, str]]:
    """
    在查询文本中查找公司名称

    Args:
        query: 用户查询文本

    Returns:
        [(公司名称, 股票代码), ...] 列表
    """
    found = []
    for company, code in COMPANY_STOCK_MAP.items():
        if company in query and code is not None:
            found.append((company, code))
    return found
